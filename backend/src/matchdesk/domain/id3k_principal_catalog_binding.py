"""ID3K CI-only dual-principal identity binding for non-executing catalog reads.

Offline test keys cryptographically model separate delegated human and app-only
workload credentials; they are NOT a live identity provider or release authority.
A future protected host must own key sources, entitlements, clock and DB connection.
No request route, action executor, migration or publishing permission exists here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Literal, Protocol

import jwt

from matchdesk.domain.id3h_release_approval import ReleaseDenied
from matchdesk.domain.id3j_postgres_catalog import inspect_disposable_catalog
from matchdesk.domain.producer_identity import TrustedKeyResolver

_DENIED = "ID3K disposable identity/catalog binding denied"
_TENANT = re.compile(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\Z")
_HUMAN_SCOPE = "MatchDesk.Catalog.Inspect"
_WORKLOAD_ROLE = "MatchDesk.Catalog.ReadOnly"


@dataclass(frozen=True, slots=True)
class DisposablePrincipalPolicy:
    """Host-pinned CI-only authorities and audiences for distinct actors."""

    tenant_id: str
    issuer: str
    human_audience: str
    workload_audience: str
    human_client_id: str
    workload_client_id: str
    workload_oid: str
    max_token_age_seconds: int = 300
    clock_leeway_seconds: int = 15

    def __post_init__(self) -> None:
        """Reject generic/multitenant authorities and confused audiences."""
        values = (
            self.human_audience,
            self.workload_audience,
            self.human_client_id,
            self.workload_client_id,
        )
        if (
            type(self.tenant_id) is not str
            or _TENANT.fullmatch(self.tenant_id) is None
            or self.issuer != f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"
            or any(type(value) is not str or not value or len(value) > 128 for value in values)
            or self.human_audience == self.workload_audience
            or self.human_client_id == self.workload_client_id
            or type(self.workload_oid) is not str
            or _TENANT.fullmatch(self.workload_oid) is None
            or type(self.max_token_age_seconds) is not int
            or not 60 <= self.max_token_age_seconds <= 600
            or type(self.clock_leeway_seconds) is not int
            or not 0 <= self.clock_leeway_seconds <= 30
        ):
            raise ValueError("ID3K requires explicit separate CI identity authorities")


class InspectionEntitlements(Protocol):
    """Protected host-owned authorization, not a token 'roles' claim."""

    def may_inspect(self, *, tenant_id: str, human_oid: str, database: str) -> bool:
        """Resolve current read-only human inspection rights or deny."""
        ...


@dataclass(frozen=True, slots=True)
class IdentityBoundCatalogReceipt:
    """CI catalog observation tied to both verified principals, never authority."""

    human_oid: str
    workload_oid: str
    database: Literal["matchdesk_id3j_ci"] = "matchdesk_id3j_ci"
    physical_role: Literal["matchdesk_id3j_reader_ci"] = "matchdesk_id3j_reader_ci"
    environment: Literal["disposable-ci"] = "disposable-ci"
    execution_authorized: Literal[False] = False
    database_writes_authorized: Literal[False] = False


def _verified_claims(
    token: str,
    *,
    policy: DisposablePrincipalPolicy,
    audience: str,
    keys: TrustedKeyResolver,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Verify a pinned RS256 JWT, then enforce explicit bounded CI timestamps."""
    if type(token) is not str or not 0 < len(token) <= 8192 or token.count(".") != 2:
        raise ReleaseDenied(_DENIED)
    header = jwt.get_unverified_header(token)
    if (
        type(header) is not dict
        or header.get("alg") != "RS256"
        or type(header.get("kid")) is not str
        or not 1 <= len(header["kid"]) <= 128
        or any(field in header for field in ("crit", "jku", "jwk", "x5u", "x5c"))
    ):
        raise ReleaseDenied(_DENIED)
    key = keys.resolve(issuer=policy.issuer, kid=header["kid"])
    if key is None or key.key_type != "RSA" or key.algorithm_name != "RS256":
        raise ReleaseDenied(_DENIED)
    claims: dict[str, Any] = jwt.decode(
        token,
        key=key.key,
        algorithms=["RS256"],
        issuer=policy.issuer,
        audience=audience,
        options={
            "require": [
                "iss", "aud", "tid", "sub", "oid", "azp", "jti", "iat", "nbf", "exp"
            ],
            # Test clock comes from the host; PyJWT's implicit system clock
            # would make deterministic offline samples non-reproducible.
            "verify_exp": False,
            "verify_nbf": False,
            "verify_iat": False,
        },
    )
    current = clock()
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ReleaseDenied(_DENIED)
    timestamp = current.timestamp()
    if (
        claims.get("tid") != policy.tenant_id
        or type(claims.get("aud")) is not str
        or claims["aud"] != audience
        or any(type(claims.get(field)) is not int for field in ("iat", "nbf", "exp"))
        or not (
            0 < claims["iat"] <= claims["nbf"] < claims["exp"]
            and claims["exp"] - claims["iat"] <= policy.max_token_age_seconds
            and claims["iat"] <= timestamp + policy.clock_leeway_seconds
            and claims["nbf"] <= timestamp + policy.clock_leeway_seconds
            and claims["exp"] > timestamp - policy.clock_leeway_seconds
            and timestamp - claims["iat"]
            <= policy.max_token_age_seconds + policy.clock_leeway_seconds
        )
        or any(
            type(claims.get(field)) is not str
            or not 1 <= len(claims[field]) <= 128
            for field in ("sub", "oid", "azp", "jti")
        )
    ):
        raise ReleaseDenied(_DENIED)
    return claims


def inspect_disposable_principal_binding(
    connection: Any,
    *,
    human_token: str,
    workload_token: str,
    policy: DisposablePrincipalPolicy,
    keys: TrustedKeyResolver,
    entitlements: InspectionEntitlements,
    clock: Callable[[], datetime],
) -> IdentityBoundCatalogReceipt:
    """Verify two cryptographic principals around real read-only SQL observations.

    This is a disposable *inspection* gate. Server-owned keys/entitlements and
    the database connection must never originate from a request or model tool.
    Pre/post checks do not create atomic write-time authorization.
    """
    try:
        if type(policy) is not DisposablePrincipalPolicy:
            raise ReleaseDenied(_DENIED)

        def principals() -> tuple[str, str]:
            """Revalidate signatures, token times and fixed separate audiences."""
            human = _verified_claims(
                human_token,
                policy=policy,
                audience=policy.human_audience,
                keys=keys,
                clock=clock,
            )
            workload = _verified_claims(
                workload_token,
                policy=policy,
                audience=policy.workload_audience,
                keys=keys,
                clock=clock,
            )
            if (
                human.get("idtyp") != "user"
                or human.get("azp") != policy.human_client_id
                or type(human.get("scp")) is not str
                or _HUMAN_SCOPE not in human["scp"].split()
                or type(human.get("amr")) is not list
                or "mfa" not in human["amr"]
                or type(human.get("oid")) is not str
                or _TENANT.fullmatch(human["oid"]) is None
                or workload.get("idtyp") != "app"
                or workload.get("azp") != policy.workload_client_id
                or workload.get("oid") != policy.workload_oid
                or workload.get("roles") != [_WORKLOAD_ROLE]
                or "scp" in workload
                or workload["oid"] == human["oid"]
            ):
                raise ReleaseDenied(_DENIED)
            return human["oid"], workload["oid"]

        human_oid, workload_oid = principals()
        if (
            entitlements.may_inspect(
                tenant_id=policy.tenant_id,
                human_oid=human_oid,
                database="matchdesk_id3j_ci",
            )
            is not True
        ):
            raise ReleaseDenied(_DENIED)
        # ID3J inspects actual effective grants in a separate read-only DB
        # transaction, including the physical session role and target DB.
        first = inspect_disposable_catalog(connection)
        if principals() != (human_oid, workload_oid):
            raise ReleaseDenied(_DENIED)
        if (
            entitlements.may_inspect(
                tenant_id=policy.tenant_id,
                human_oid=human_oid,
                database=first.database,
            )
            is not True
        ):
            raise ReleaseDenied(_DENIED)
        second = inspect_disposable_catalog(connection)
        if first != second or first.execution_authorized is not False:
            raise ReleaseDenied(_DENIED)
        return IdentityBoundCatalogReceipt(human_oid=human_oid, workload_oid=workload_oid)
    except Exception:
        # Identity/key outages, revoked grants, missing catalog and drift deny.
        raise ReleaseDenied(_DENIED) from None
