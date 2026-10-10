"""Signed, synthetic External ID ID-token verification regression tests."""

from datetime import datetime, timezone
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from matchdesk.domain.customer_identity import CustomerBrokerPolicy
from matchdesk.domain.oidc_id_token import verify_broker_id_token
from matchdesk.domain.oidc_login import CustomerOidcPolicy, PendingOidcExchange

NOW = datetime.now(timezone.utc)
TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://test.ciamlogin.com/{TENANT}/v2.0"
BASE = f"https://test.ciamlogin.com/{TENANT}"
CLIENT = "test-client"
ORIGIN = "https://matchdesk.example"


@pytest.fixture
def materials():
    """Build ephemeral signing material and reviewed host policy."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()

    def b64(n: int) -> str:
        """Serialize RSA public parameters into base64url JWK values."""
        return jwt.utils.base64url_encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).decode()

    jwk = PyJWK.from_dict(
        {"kty": "RSA", "alg": "RS256", "kid": "signed-test-key", "use": "sig",
         "n": b64(numbers.n), "e": b64(numbers.e)}
    )
    broker = CustomerBrokerPolicy(
        issuer=ISSUER, tenant_id=TENANT, audience="api://customer",
        client_ids=frozenset({CLIENT}),
    )
    policy = CustomerOidcPolicy(
        broker=broker, client_id=CLIENT, public_origin=ORIGIN,
        authorization_endpoint=f"{BASE}/oauth2/v2.0/authorize",
        token_endpoint=f"{BASE}/oauth2/v2.0/token",
        jwks_uri=f"{BASE}/discovery/v2.0/keys",
    )
    pending = PendingOidcExchange(
        issuer=ISSUER, client_id=CLIENT,
        token_endpoint=policy.token_endpoint, redirect_uri=policy.redirect_uri,
        authorization_code="code", code_verifier="a" * 43, nonce="b" * 43,
    )
    resolver = Mock()
    resolver.resolve.return_value = jwk
    return private, resolver, policy, pending


def signed(materials, **changes) -> str:
    """Sign an exact broker ID token, never a third-party provider credential."""
    private, _, _, pending = materials
    now = int(NOW.timestamp())
    claims = {
        "iss": ISSUER, "aud": CLIENT, "tid": TENANT, "sub": "broker-subject",
        "nonce": pending.nonce, "iat": now - 5, "nbf": now - 5, "exp": now + 500,
    }
    claims.update(changes)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "signed-test-key"})


def test_valid_broker_identity_has_no_roles_or_social_email(materials) -> None:
    """A valid signature establishes only an issuer-qualified customer identity."""
    _, resolver, policy, pending = materials
    token = signed(materials, roles=["producer"], email="admin@example.com")
    result = verify_broker_id_token(
        token, pending=pending, policy=policy, keys=resolver, now=NOW
    )
    assert result.lookup_key == (ISSUER, TENANT, "broker-subject")
    assert not hasattr(result, "email")
    assert not hasattr(result, "roles")
    resolver.resolve.assert_called_once_with(issuer=ISSUER, kid="signed-test-key")


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://accounts.google.com"},
        {"iss": "https://appleid.apple.com"},
        {"aud": "api://customer"},
        {"aud": [CLIENT]},
        {"tid": "different-tenant"},
        {"nonce": "x" * 43},
        {"nonce": None},
        {"sub": ""},
        {"iat": "bad"},
        {"nbf": False},
        {"exp": "bad"},
        {"iat": int(NOW.timestamp()) + 400},
        {"exp": int(NOW.timestamp()) - 400},
        {"exp": int(NOW.timestamp()) + 7200},
        {"idtyp": "app"},
    ],
)
def test_claim_substitutions_are_denied(materials, claims) -> None:
    """Bad signed claims never become a customer account or BFF session."""
    _, keys, policy, pending = materials
    with pytest.raises(PermissionError):
        verify_broker_id_token(
            signed(materials, **claims), pending=pending, policy=policy, keys=keys, now=NOW
        )


@pytest.mark.parametrize("token", ["", "a.b", "a.b.c.d", "x" * 17000, None])
def test_unframed_tokens_denied(materials, token) -> None:
    """Opaque or oversized input cannot trigger trusted JWKS resolution."""
    _, keys, policy, pending = materials
    with pytest.raises(PermissionError):
        verify_broker_id_token(token, pending=pending, policy=policy, keys=keys, now=NOW)


def test_wrong_key_or_unknown_key_is_denied(materials) -> None:
    """Host-owned resolver controls signing trust, never the JWT kid alone."""
    _, keys, policy, pending = materials
    keys.resolve.return_value = None
    with pytest.raises(PermissionError):
        verify_broker_id_token(
            signed(materials), pending=pending, policy=policy, keys=keys, now=NOW
        )


def test_mismatched_exchange_context_is_rejected(materials) -> None:
    """A code from another broker client cannot be replayed into this verifier."""
    from dataclasses import replace

    _, keys, policy, pending = materials
    with pytest.raises(PermissionError):
        verify_broker_id_token(
            signed(materials), pending=replace(pending, client_id="another-client"),
            policy=policy, keys=keys, now=NOW
        )
