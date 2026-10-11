"""ID3L: bind synthetic signed principals to one real disposable PostgreSQL session.

This is an isolated CI integration harness, NOT a real Entra login, trusted
workload-federation service, cluster attestation or mutation authorizer.
Keys and grants are generated and held in this CI process only; no token,
private key, DSN password or identity data is printed to the logs.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
import psycopg
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK

from matchdesk.domain.id3h_release_approval import ReleaseDenied
from matchdesk.domain.id3j_postgres_catalog import inspect_disposable_catalog
from matchdesk.domain.id3k_principal_catalog_binding import (
    DisposablePrincipalPolicy,
    inspect_disposable_principal_binding,
)
from matchdesk.domain.producer_identity import StaticTrustedKeys

_TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_HUMAN = "11111111-1111-1111-1111-111111111111"
_WORKLOAD = "22222222-2222-2222-2222-222222222222"
_ISSUER = f"https://login.microsoftonline.com/{_TENANT}/v2.0"
_DATABASE = "matchdesk_id3j_ci"
_ROLE = "matchdesk_id3j_reader_ci"
_DENIED = "ID3L disposable read-only identity/database boundary denied"


@dataclass
class HostEntitlements:
    """CI host-owned inspection grants, never taken from token claims."""

    enabled: bool = True
    revoke_on_second: bool = False
    checks: int = 0

    def may_inspect(self, *, tenant_id: str, human_oid: str, database: str) -> bool:
        """Allow the one scoped human and support an injected post-check revoke."""
        self.checks += 1
        return (
            self.enabled
            and (not self.revoke_on_second or self.checks < 2)
            and tenant_id == _TENANT
            and human_oid == _HUMAN
            and database == _DATABASE
        )


def _key(kid: str) -> tuple[rsa.RSAPrivateKey, PyJWK]:
    """Generate a fresh, unexported synthetic RSA signing key for one actor."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()

    def b64(value: int) -> str:
        """Encode RSA public limbs for the pinned local JWK representation."""
        data = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return jwt.utils.base64url_encode(data).decode("ascii")

    public = PyJWK.from_dict(
        {
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "kid": kid,
            "n": b64(numbers.n),
            "e": b64(numbers.e),
        }
    )
    return private, public


def _sign(private: rsa.RSAPrivateKey, kid: str, claims: dict[str, object]) -> str:
    """Sign a short-lived, test-only JWT; never log or persist it."""
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": kid})


def _session(connection: psycopg.Connection) -> tuple[int, str, str, str]:
    """Read physical connection identity rather than a caller-supplied target."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_backend_pid(), current_database()::text, "
            "current_user::text, session_user::text"
        )
        observed = cursor.fetchone()
    if (
        not isinstance(observed, tuple)
        or len(observed) != 4
        or type(observed[0]) is not int
        or observed[1:] != (_DATABASE, _ROLE, _ROLE)
    ):
        raise ReleaseDenied(_DENIED)
    return observed


def _denied(call, reason: str) -> None:
    """Demand a fail-closed denial; never interpret a different exception as success."""
    try:
        call()
    except ReleaseDenied:
        return
    raise AssertionError(f"ID3L unexpectedly permitted {reason}")


def main() -> None:
    """Exercise one protected CI connection with identity and permission probes."""
    # The fixed host and database are generated only by the disposable runner.
    # Neither the request nor the tokens may specify a database connection.
    if (
        os.environ.get("CI") != "true"
        or not os.environ.get("PGPASSWORD")
        or os.environ.get("ID3L_EXPECT_ELEVATION_DENIAL") not in (None, "true")
    ):
        raise ReleaseDenied(_DENIED)
    policy = DisposablePrincipalPolicy(
        tenant_id=_TENANT,
        issuer=_ISSUER,
        human_audience="api://id3l-human-ci",
        workload_audience="api://id3l-workload-ci",
        human_client_id="id3l-human-client-ci",
        workload_client_id="id3l-workload-client-ci",
        workload_oid=_WORKLOAD,
    )
    human_private, human_public = _key("id3l-human")
    workload_private, workload_public = _key("id3l-workload")
    pinned_keys = StaticTrustedKeys(
        _ISSUER, {"id3l-human": human_public, "id3l-workload": workload_public}
    )
    now = datetime.now(timezone.utc)
    common: dict[str, object] = {
        "iss": _ISSUER,
        "tid": _TENANT,
        "iat": int((now - timedelta(seconds=10)).timestamp()),
        "nbf": int((now - timedelta(seconds=10)).timestamp()),
        "exp": int((now + timedelta(seconds=120)).timestamp()),
        "jti": secrets.token_hex(16),
    }
    human: dict[str, object] = {
        **common,
        "aud": policy.human_audience,
        "sub": "disposable-human-ci",
        "oid": _HUMAN,
        "azp": policy.human_client_id,
        "idtyp": "user",
        "scp": "MatchDesk.Catalog.Inspect",
        "amr": ["pwd", "mfa"],
    }
    workload: dict[str, object] = {
        **common,
        "aud": policy.workload_audience,
        "sub": "disposable-workload-ci",
        "oid": _WORKLOAD,
        "azp": policy.workload_client_id,
        "idtyp": "app",
        "roles": ["MatchDesk.Catalog.ReadOnly"],
    }
    human_token = _sign(human_private, "id3l-human", human)
    workload_token = _sign(workload_private, "id3l-workload", workload)
    entitlements = HostEntitlements()

    with psycopg.connect(
        "host=postgres dbname=matchdesk_id3j_ci user=matchdesk_id3j_reader_ci "
        "sslmode=prefer connect_timeout=5",
        autocommit=True,
    ) as connection:
        before = _session(connection)

        def inspect(*, user: str = human_token, app: str = workload_token) -> None:
            """Bind both independently signed tokens to the SAME real PG session."""
            receipt = inspect_disposable_principal_binding(
                connection,
                human_token=user,
                workload_token=app,
                policy=policy,
                keys=pinned_keys,
                entitlements=entitlements,
                clock=lambda: datetime.now(timezone.utc),
            )
            if (
                receipt.human_oid != _HUMAN
                or receipt.workload_oid != _WORKLOAD
                or receipt.physical_role != _ROLE
                or receipt.database != _DATABASE
                or receipt.execution_authorized is not False
                or receipt.database_writes_authorized is not False
            ):
                raise ReleaseDenied(_DENIED)

        if os.environ.get("ID3L_EXPECT_ELEVATION_DENIAL") == "true":
            # The CI runner granted CREATE to this exact physical role before
            # invoking the script. Prove catalog detection independently of
            # identity validation so an unrelated denial cannot mask a bypass.
            _denied(lambda: inspect_disposable_catalog(connection), "elevated catalog")
            _denied(inspect, "elevated identity-bound catalog")
            assert _session(connection) == before
            print("MATCHDESK_ID3L_ELEVATED_ROLE_REJECTED")
            return

        inspect()
        assert _session(connection) == before

        entitlements.enabled = False
        _denied(inspect, "revoked human entitlement")
        entitlements.enabled = True
        entitlements.checks = 0
        entitlements.revoke_on_second = True
        _denied(inspect, "entitlement revoked during recheck")
        entitlements.revoke_on_second = False
        entitlements.checks = 0

        no_mfa = {**human, "amr": ["pwd"]}
        _denied(
            lambda: inspect(user=_sign(human_private, "id3l-human", no_mfa)),
            "human without MFA assertion",
        )
        wrong_workload = {**workload, "aud": policy.human_audience}
        _denied(
            lambda: inspect(app=_sign(workload_private, "id3l-workload", wrong_workload)),
            "cross-audience workload token",
        )
        rogue_private, _ = _key("untrusted-ci")
        _denied(
            lambda: inspect(user=_sign(rogue_private, "id3l-human", human)),
            "forged human signing key",
        )
        # Rechecking after all denial cases confirms the same DB session,
        # intact grants and a final explicitly non-executing result.
        inspect()
        assert _session(connection) == before
        print("MATCHDESK_ID3L_REAL_POSTGRESQL_DUAL_PRINCIPAL_PASS")


if __name__ == "__main__":
    main()
