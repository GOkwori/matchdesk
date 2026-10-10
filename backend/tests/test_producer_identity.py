"""Offline RS256 producer access-token and server entitlement security regressions."""

from datetime import datetime, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from matchdesk.domain.producer_identity import (
    ProducerIdentityPolicy,
    StaticTrustedKeys,
    verify_producer_access_token,
)

ISSUER = "https://login.microsoftonline.com/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/v2.0"
TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
AUDIENCE = "api://matchdesk-ci"
CLIENT = "matchdesk-frontend-ci"
NOW = datetime.now(timezone.utc)


class Grants:
    """Immutable, host-owned role/session fixture; no JWT roles are consulted."""

    def resolve(self, *, tenant_id: str, subject: str):
        """Return exact server grants to a single test producer."""
        if tenant_id == TENANT and subject == "person-1":
            return frozenset({"producer"}), frozenset({"match-1"})
        return None


class NoProducerGrants:
    """Simulate a valid token whose producer rights were revoked."""

    def resolve(self, *, tenant_id: str, subject: str):
        """Provide no authorized sessions or producer roles."""
        del tenant_id, subject
        return frozenset({"auditor"}), frozenset({"match-1"})


@pytest.fixture
def signing():
    """Generate a disposable 2048-bit private RSA key; no production keys are used."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()

    def b64(number: int) -> str:
        """Convert an RSA integer to unsigned base64url for a public JWK."""
        raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
        return jwt.utils.base64url_encode(raw).decode()

    public = PyJWK.from_dict(
        {
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "kid": "kid-1",
            "n": b64(numbers.n),
            "e": b64(numbers.e),
        }
    )
    return private, StaticTrustedKeys(ISSUER, {"kid-1": public})


def policy(**changes):
    """Construct an explicit one-tenant resource-server policy."""
    fields = dict(
        issuer=ISSUER, audience=AUDIENCE, tenant_id=TENANT, client_ids=frozenset({CLIENT})
    )
    fields.update(changes)
    return ProducerIdentityPolicy(**fields)


def token(private, **changes):
    """Sign a test-only delegated access token with controlled claims."""
    now = int(NOW.timestamp())
    claims = dict(
        iss=ISSUER,
        aud=AUDIENCE,
        tid=TENANT,
        sub="person-1",
        azp=CLIENT,
        scp="MatchDesk.Producer.Access",
        iat=now - 10,
        nbf=now - 10,
        exp=now + 500,
    )
    claims.update(changes)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "kid-1"})


def test_valid_signature_and_server_grants_create_producer_actor(signing) -> None:
    """Only a signed delegated API token with independent host grants succeeds."""
    private, keys = signing
    actor = verify_producer_access_token(
        token(private, roles=["admin"], permitted_sessions=["foreign-match"]),
        policy=policy(),
            keys=keys,
            entitlements=Grants(),
            now=NOW,
    )
    assert actor.subject == "person-1"
    assert actor.roles == frozenset({"producer"})
    assert actor.permitted_sessions == frozenset({"match-1"})


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://evil.example/v2.0"},
        {"aud": "api://another-api"},
        {"tid": "other-tenant"},
        {"azp": "untrusted-client"},
        {"scp": "other.scope"},
        {"scp": ""},
        {"sub": ""},
        {"idtyp": "app"},
        {"exp": int(NOW.timestamp()) - 300},
        {"nbf": int(NOW.timestamp()) + 300},
        {"iat": int(NOW.timestamp()) + 300},
        {"exp": int(NOW.timestamp()) + 5000},
        {"iat": int(NOW.timestamp()) - 5000},
        {"exp": "not-a-date"},
    ],
)
def test_rejects_invalid_scope_tenant_times_or_delegation(signing, changes) -> None:
    """Access-token trust, lifetime and delegation claims all fail closed."""
    private, keys = signing
    with pytest.raises(PermissionError):
        verify_producer_access_token(
            token(private, **changes),
            policy=policy(),
            keys=keys,
            entitlements=Grants(),
            now=NOW,
        )


def test_wrong_signing_key_and_untrusted_header_are_rejected(signing) -> None:
    """An attacker-signed JWT or attacker-provided JWK endpoint cannot supply trust."""
    private, keys = signing
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cases = (
        token(other),
        jwt.encode({"sub": "person-1"}, private, algorithm="RS256", headers={"kid": "unknown"}),
        jwt.encode(
            {"sub": "person-1"},
            private,
            algorithm="RS256",
            headers={"kid": "kid-1", "jku": "https://evil.example/keys"},
        ),
    )
    for value in cases:
        with pytest.raises(PermissionError):
            verify_producer_access_token(
                value, policy=policy(),
            keys=keys,
            entitlements=Grants(),
            now=NOW,
            )


def test_missing_grants_cannot_be_replaced_by_jwt_roles(signing) -> None:
    """Signed producer-like JWT claims do not grant server-side permission."""
    private, keys = signing
    with pytest.raises(PermissionError):
        verify_producer_access_token(
            token(private, roles=["producer"], permitted_sessions=["match-1"]),
            policy=policy(),
            keys=keys,
            entitlements=NoProducerGrants(),
            now=NOW,
        )


@pytest.mark.parametrize("invalid", ["", "opaque", "a.b", "a.b.c.d", "x" * 17000])
def test_invalid_token_framing_fails_closed(signing, invalid) -> None:
    """Reject opaque tokens and unreasonable bearer sizes before key resolution."""
    _, keys = signing
    with pytest.raises(PermissionError):
        verify_producer_access_token(
            invalid, policy=policy(),
            keys=keys,
            entitlements=Grants(),
            now=NOW,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"issuer": "http://unsafe/v2.0"},
        {"issuer": "https://unsafe"},
        {"issuer": "https://{tenant}/v2.0"},
        {"client_ids": frozenset()},
        {"required_scope": ""},
        {"max_token_age_seconds": 20000},
        {"clock_leeway_seconds": 900},
    ],
)
def test_invalid_server_policy_fails_closed(changes) -> None:
    """Hosts must supply concrete bounded identity trust without wildcards."""
    with pytest.raises(ValueError):
        policy(**changes)


def test_keys_are_issuer_bound_and_unknown_rotation_fails_closed(signing) -> None:
    """Unknown key identifiers require a separately trusted key-set refresh."""
    _, keys = signing
    assert keys.resolve(issuer=ISSUER, kid="not-registered") is None
    assert keys.resolve(issuer="https://other.example/v2.0", kid="kid-1") is None
