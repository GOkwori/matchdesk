"""Offline customer broker and non-linking identity security regression tests."""

from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from matchdesk.domain.customer_identity import (
    CustomerBrokerPolicy,
    CustomerIdentityKey,
    resolve_customer_account,
    verify_customer_access_token,
)
from matchdesk.domain.producer_identity import StaticTrustedKeys

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://matchdesk.ciamlogin.com/{TENANT}/v2.0"
AUDIENCE = "api://matchdesk-customer-test"
CLIENT = "matchdesk-customer-client"
NOW = datetime.now(timezone.utc)


class RegisteredAccounts:
    """A host-owned lookup whose keys include broker issuer, tenant and subject."""

    def __init__(self) -> None:
        """Keep mapping separate from the JWT and display-email contents."""
        self.rows: dict[tuple[str, str, str], str] = {}

    def lookup(self, *, issuer: str, tenant_id: str, subject: str) -> str | None:
        """Read only the exact immutable identity key."""
        return self.rows.get((issuer, tenant_id, subject))


@pytest.fixture
def signer():
    """Create an ephemeral RSA signer for a simulated customer External ID issuer."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()

    def b64(number: int) -> str:
        """Convert public RSA integers into JWK base64url."""
        value = number.to_bytes((number.bit_length() + 7) // 8, "big")
        return jwt.utils.base64url_encode(value).decode()

    jwk = PyJWK.from_dict(
        {
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "kid": "customer-test-kid",
            "n": b64(numbers.n),
            "e": b64(numbers.e),
        }
    )
    return private, StaticTrustedKeys(ISSUER, {"customer-test-kid": jwk})


def policy(**overrides):
    """Return a single registered External ID broker trust policy."""
    values = dict(
        issuer=ISSUER,
        tenant_id=TENANT,
        audience=AUDIENCE,
        client_ids=frozenset({CLIENT}),
    )
    values.update(overrides)
    return CustomerBrokerPolicy(**values)


def token(private, **overrides):
    """Sign a synthetic access token for the broker-controlled API audience."""
    now = int(NOW.timestamp())
    claims = dict(
        iss=ISSUER,
        aud=AUDIENCE,
        tid=TENANT,
        sub="broker-subject-1",
        azp=CLIENT,
        scp="MatchDesk.Customer.Access",
        iat=now - 10,
        nbf=now - 10,
        exp=now + 500,
    )
    claims.update(overrides)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "customer-test-kid"})


def test_external_id_broker_creates_role_free_identity(signer) -> None:
    """Upstream login data cannot assign producer roles or link email accounts."""
    private, keys = signer
    result = verify_customer_access_token(
        token(
            private,
            idp="google.com",
            email="producer@example.com",
            email_verified=True,
            roles=["producer", "administrator"],
            permitted_sessions=["another-match"],
        ),
        policy=policy(),
        keys=keys,
        now=NOW,
    )
    assert result.lookup_key == (ISSUER, TENANT, "broker-subject-1")
    assert not hasattr(result, "roles")
    assert not hasattr(result, "email")
    assert not hasattr(result, "permitted_sessions")


@pytest.mark.parametrize(
    "bad",
    [
        {"issuer": "https://login.microsoftonline.com/common/v2.0"},
        {"issuer": "https://accounts.google.com"},
        {"issuer": "https://appleid.apple.com"},
        {"issuer": f"http://matchdesk.ciamlogin.com/{TENANT}/v2.0"},
        {"issuer": f"https://matchdesk.ciamlogin.com/{TENANT}/v1.0"},
        {"issuer": f"https://evil.ciamlogin.com.evil.example/{TENANT}/v2.0"},
        {"issuer": f"https://matchdesk.ciamlogin.com:8443/{TENANT}/v2.0"},
        {"issuer": f"https://matchdesk.ciamlogin.com/{TENANT}/v2.0?user=1"},
        {"tenant_id": str(uuid4())},
        {"tenant_id": "consumers"},
        {"audience": ""},
        {"audience": "*"},
        {"client_ids": frozenset()},
        {"client_ids": frozenset({"*"})},
        {"required_scope": " "},
        {"max_token_age_seconds": 4000},
        {"clock_leeway_seconds": 120},
    ],
)
def test_policy_rejects_non_broker_or_unsafe_configuration(bad) -> None:
    """No direct upstream provider or generic Microsoft issuer is a customer API issuer."""
    with pytest.raises(ValueError):
        policy(**bad)


@pytest.mark.parametrize(
    "invalid",
    [
        {"iss": "https://accounts.google.com"},
        {"iss": "https://appleid.apple.com"},
        {"iss": f"https://other.ciamlogin.com/{TENANT}/v2.0"},
        {"aud": "api://matchdesk-producer"},
        {"aud": [AUDIENCE]},
        {"tid": str(uuid4())},
        {"azp": "unregistered-client"},
        {"scp": ""},
        {"scp": "unrelated.scope"},
        {"sub": ""},
        {"sub": " subject "},
        {"idtyp": "app"},
        {"exp": int(NOW.timestamp()) - 300},
        {"nbf": int(NOW.timestamp()) + 300},
        {"iat": int(NOW.timestamp()) + 300},
        {"exp": int(NOW.timestamp()) + 5000},
        {"iat": int(NOW.timestamp()) - 5000},
        {"exp": "invalid-expiry"},
        {"nbf": False},
        {"iat": "invalid"},
    ],
)
def test_token_claim_substitution_and_invalid_timing_fail_closed(signer, invalid) -> None:
    """A provider-token substitution cannot reach the internal account directory."""
    private, keys = signer
    with pytest.raises(PermissionError):
        verify_customer_access_token(token(private, **invalid), policy=policy(), keys=keys, now=NOW)


@pytest.mark.parametrize("value", ["", "opaque", "a.b", "a.b.c.d", "x" * 17000, None])
def test_bearer_token_framing_is_bounded(signer, value) -> None:
    """No opaque, excessive or incomplete input proceeds to JWK validation."""
    _, keys = signer
    with pytest.raises(PermissionError):
        verify_customer_access_token(value, policy=policy(), keys=keys, now=NOW)


def test_forged_signing_key_unknown_rotation_and_remote_jwk_header_fail(signer) -> None:
    """Keys are explicitly issuer-scoped; token headers may not supply trust URLs."""
    private, keys = signer
    untrusted = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tokens = (
        token(untrusted),
        jwt.encode({"sub": "x"}, private, algorithm="RS256", headers={"kid": "unknown-kid"}),
        jwt.encode(
            {"sub": "x"},
            private,
            algorithm="RS256",
            headers={"kid": "customer-test-kid", "jku": "https://evil.example/jwks"},
        ),
    )
    for signed in tokens:
        with pytest.raises(PermissionError):
            verify_customer_access_token(signed, policy=policy(), keys=keys, now=NOW)


@pytest.mark.parametrize("subject", ["", " ", " leading", "trailing ", "x" * 257, None])
def test_identity_key_requires_an_exact_subject(subject) -> None:
    """Invalid broker subject identifiers cannot become account mappings."""
    with pytest.raises(ValueError):
        CustomerIdentityKey(issuer=ISSUER, tenant_id=TENANT, subject=subject)


def test_unknown_customer_never_self_provisions_or_inherits_permissions(signer) -> None:
    """A valid identity requires explicit directory registration, not claimed roles."""
    private, keys = signer
    customer = verify_customer_access_token(
        token(private, roles=["producer"]), policy=policy(), keys=keys, now=NOW
    )
    directory = RegisteredAccounts()
    with pytest.raises(PermissionError, match="not registered"):
        resolve_customer_account(customer, directory=directory)
    assert directory.rows == {}


def test_same_email_different_subjects_cannot_merge_accounts(signer) -> None:
    """Email and social-provider hints cannot override the immutable broker subject."""
    private, keys = signer
    one = verify_customer_access_token(
        token(private, sub="account-A", email="same@example.com", idp="google.com"),
        policy=policy(),
        keys=keys,
        now=NOW,
    )
    two = verify_customer_access_token(
        token(private, sub="account-B", email="same@example.com", idp="apple.com"),
        policy=policy(),
        keys=keys,
        now=NOW,
    )
    assert one.lookup_key != two.lookup_key
    directory = RegisteredAccounts()
    directory.rows[one.lookup_key] = "customer-A"
    directory.rows[two.lookup_key] = "customer-B"
    assert resolve_customer_account(one, directory=directory) == "customer-A"
    assert resolve_customer_account(two, directory=directory) == "customer-B"


@pytest.mark.parametrize("account_id", [None, "", " ", " " * 150, False])
def test_directory_rejects_missing_or_invalid_account_id(signer, account_id) -> None:
    """Malformed host mappings fail closed instead of allocating a new account."""
    private, keys = signer
    customer = verify_customer_access_token(token(private), policy=policy(), keys=keys, now=NOW)
    directory = RegisteredAccounts()
    directory.rows[customer.lookup_key] = account_id
    with pytest.raises(PermissionError):
        resolve_customer_account(customer, directory=directory)


def test_identity_same_subject_isolated_across_trusted_issuer_and_tenant() -> None:
    """Even identical broker subjects stay distinct when realm ownership differs."""
    a = CustomerIdentityKey(issuer=ISSUER, tenant_id=TENANT, subject="subject")
    b = CustomerIdentityKey(
        issuer=f"https://other.ciamlogin.com/{TENANT}/v2.0",
        tenant_id=TENANT,
        subject="subject",
    )
    assert a.lookup_key != b.lookup_key
