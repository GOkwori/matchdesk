"""Offline one-use OIDC completion and customer-only session issuance tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from matchdesk.domain.browser_session_security import CustomerBrowserPolicy
from matchdesk.domain.customer_identity import CustomerBrokerPolicy, CustomerIdentityKey
from matchdesk.domain.customer_oidc_completion import complete_customer_oidc_sign_in
from matchdesk.domain.oidc_login import CustomerOidcPolicy, PendingOidcExchange

NOW = datetime.now(timezone.utc)
TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://test.ciamlogin.com/{TENANT}/v2.0"
BASE = f"https://test.ciamlogin.com/{TENANT}"
ORIGIN = "https://matchdesk.example"
CLIENT = "test-client"


class Sessions:
    """Test-only persisted customer records with mutation and corruption controls."""

    def __init__(self) -> None:
        """Keep the exact created row and each attempted orphan revocation."""
        self.rows = {}
        self.revoked = []
        self.reject = False
        self.corrupt = False
        self.fail_read = False
        self.raise_after_write = False

    def create(self, record) -> bool:
        """Persist a candidate or simulate a refused/uncertain atomic insert."""
        if self.reject or record.session_id in self.rows:
            return False
        self.rows[record.session_id] = record
        if self.raise_after_write:
            raise RuntimeError("private database DSN")
        return True

    def load(self, opaque_session_id):
        """Return only persisted rows and simulate a mismatched server-owned identity."""
        if self.fail_read:
            raise RuntimeError("private database DSN")
        record = self.rows.get(opaque_session_id)
        if record is not None and self.corrupt:
            identity = replace(record.identity, subject="other-broker-subject")
            return replace(record, identity=identity)
        return record

    def revoke(self, opaque_session_id: str) -> bool:
        """Mark a leaked-on-failure candidate unusable without disclosing its bearer."""
        self.revoked.append(opaque_session_id)
        record = self.rows.get(opaque_session_id)
        if record is None:
            return False
        self.rows[opaque_session_id] = replace(record, revoked=True)
        return True


@pytest.fixture
def setup():
    """Provide a synthetic signed broker, host policy, directory and session store."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()

    def b64(number: int) -> str:
        """Encode an RSA public parameter as unpadded base64url."""
        raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
        return jwt.utils.base64url_encode(raw).decode("ascii")

    public = PyJWK.from_dict(
        {
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "kid": "trusted-key",
            "n": b64(numbers.n),
            "e": b64(numbers.e),
        }
    )
    broker = CustomerBrokerPolicy(
        issuer=ISSUER,
        tenant_id=TENANT,
        audience="api://customer",
        client_ids=frozenset({CLIENT}),
    )
    policy = CustomerOidcPolicy(
        broker=broker,
        client_id=CLIENT,
        public_origin=ORIGIN,
        authorization_endpoint=f"{BASE}/oauth2/v2.0/authorize",
        token_endpoint=f"{BASE}/oauth2/v2.0/token",
        jwks_uri=f"{BASE}/discovery/v2.0/keys",
    )
    pending = PendingOidcExchange(
        issuer=ISSUER,
        client_id=CLIENT,
        token_endpoint=policy.token_endpoint,
        redirect_uri=policy.redirect_uri,
        authorization_code="one-use-code",
        code_verifier="a" * 43,
        nonce="b" * 43,
    )
    keys = Mock()
    keys.resolve.return_value = public
    directory = Mock()
    directory.lookup.return_value = "registered-customer-1"
    exchanger = Mock()
    sessions = Sessions()
    return {
        "private": private,
        "pending": pending,
        "policy": policy,
        "browser": CustomerBrowserPolicy(public_origin=ORIGIN),
        "keys": keys,
        "directory": directory,
        "exchanger": exchanger,
        "sessions": sessions,
    }


def signed(setup, **changes) -> str:
    """Return one synthetic broker ID token bound to the pending nonce."""
    now = int(NOW.timestamp())
    claims = {
        "iss": ISSUER,
        "aud": CLIENT,
        "tid": TENANT,
        "sub": "broker-subject",
        "nonce": setup["pending"].nonce,
        "iat": now - 5,
        "nbf": now - 5,
        "exp": now + 500,
    }
    claims.update(changes)
    return jwt.encode(claims, setup["private"], algorithm="RS256", headers={"kid": "trusted-key"})


def complete(setup):
    """Call the offline host completion seam with no deployed login route."""
    return complete_customer_oidc_sign_in(
        pending=setup["pending"],
        policy=setup["policy"],
        browser=setup["browser"],
        exchanger=setup["exchanger"],
        keys=setup["keys"],
        directory=setup["directory"],
        sessions=setup["sessions"],
        now=NOW,
    )


def test_signed_broker_existing_account_issues_only_customer_cookie(setup) -> None:
    """Ignore social email/role claims and issue only a persisted customer session."""
    setup["exchanger"].redeem.return_value = signed(
        setup, email="producer@example.com", roles=["admin", "producer"], idp="google"
    )
    result = complete(setup)
    rows = list(setup["sessions"].rows.values())
    assert len(rows) == 1
    assert rows[0].realm == "customer"
    assert rows[0].identity == CustomerIdentityKey(
        issuer=ISSUER, tenant_id=TENANT, subject="broker-subject"
    )
    assert rows[0].account_id == "registered-customer-1"
    assert rows[0].expires_at == NOW + timedelta(hours=1)
    assert result.expires_at == rows[0].expires_at
    assert result.set_cookie.startswith("__Host-matchdesk_customer=")
    assert "Secure; HttpOnly; SameSite=Lax" in result.set_cookie
    assert "Domain=" not in result.set_cookie
    assert "producer@example.com" not in result.set_cookie
    assert rows[0].session_id not in repr(result)
    assert not hasattr(result, "roles")
    setup["directory"].lookup.assert_called_once_with(
        issuer=ISSUER, tenant_id=TENANT, subject="broker-subject"
    )
    setup["exchanger"].redeem.assert_called_once_with(pending=setup["pending"])


@pytest.mark.parametrize(
    "change",
    [
        {"issuer": "https://accounts.google.com"},
        {"client_id": "different-client"},
        {"token_endpoint": "https://attacker.example/token"},
        {"redirect_uri": "https://attacker.example/callback"},
        {"nonce": "invalid"},
        {"code_verifier": "invalid"},
        {"authorization_code": "code with spaces"},
        {"authorization_code": ""},
        {"authorization_code": "line\nbreak"},
        {"authorization_code": "x" * 2049},
    ],
)
def test_invalid_exchange_is_rejected_before_code_redemption(setup, change) -> None:
    """Never forward a forged callback destination or bad PKCE material to the adapter."""
    setup["pending"] = replace(setup["pending"], **change)
    with pytest.raises(PermissionError):
        complete(setup)
    setup["exchanger"].redeem.assert_not_called()
    assert not setup["sessions"].rows


def test_mismatched_cookie_origin_rejected_before_code_redemption(setup) -> None:
    """A trusted token endpoint cannot issue cookies on another browser origin."""
    setup["browser"] = CustomerBrowserPolicy(public_origin="https://other.example")
    with pytest.raises(ValueError):
        complete(setup)
    setup["exchanger"].redeem.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "https://accounts.google.com"},
        {"aud": "api://customer"},
        {"tid": "some-other-tenant"},
        {"nonce": "wrong-nonce"},
        {"sub": ""},
        {"idtyp": "app"},
        {"exp": int(NOW.timestamp()) - 120},
    ],
)
def test_signed_but_untrusted_claims_cannot_issue_session(setup, change) -> None:
    """Provider identities, mismatched audience and invalid nonce fail closed."""
    setup["exchanger"].redeem.return_value = signed(setup, **change)
    with pytest.raises(PermissionError, match="identity or account denied"):
        complete(setup)
    assert not setup["sessions"].rows


def test_unsigned_and_wrong_signing_key_cannot_issue_session(setup) -> None:
    """Trusted issuer key resolver, not returned token metadata, controls trust."""
    setup["exchanger"].redeem.return_value = "a.b.c"
    with pytest.raises(PermissionError):
        complete(setup)
    setup["exchanger"].redeem.return_value = signed(setup)
    setup["keys"].resolve.return_value = None
    with pytest.raises(PermissionError):
        complete(setup)
    assert not setup["sessions"].rows


def test_unregistered_identity_is_never_auto_provisioned(setup) -> None:
    """A valid provider login is not registration, account linking or role grant."""
    setup["exchanger"].redeem.return_value = signed(setup)
    setup["directory"].lookup.return_value = None
    with pytest.raises(PermissionError, match="identity or account denied"):
        complete(setup)
    assert not setup["sessions"].rows


def test_broker_error_is_redacted_and_cannot_create_session(setup) -> None:
    """Do not expose token endpoint failures or protected client credentials."""
    setup["exchanger"].redeem.side_effect = RuntimeError("private client credential")
    with pytest.raises(PermissionError, match="code exchange denied") as failure:
        complete(setup)
    assert "private client credential" not in str(failure.value)
    assert not setup["sessions"].rows


@pytest.mark.parametrize("flag", ["reject", "raise_after_write"])
def test_failed_or_uncertain_session_insert_never_issues_cookie(setup, flag) -> None:
    """Reject a refused write and best-effort revoke a possibly committed write."""
    setup["exchanger"].redeem.return_value = signed(setup)
    setattr(setup["sessions"], flag, True)
    with pytest.raises(PermissionError, match="persistence denied"):
        complete(setup)
    assert len(setup["sessions"].revoked) == 1
    assert all(row.revoked for row in setup["sessions"].rows.values())


@pytest.mark.parametrize("flag", ["corrupt", "fail_read"])
def test_storage_substitution_or_read_error_revokes_orphan(setup, flag) -> None:
    """Do not issue a bearer whose stored owner differs or cannot be re-read."""
    setup["exchanger"].redeem.return_value = signed(setup)
    setattr(setup["sessions"], flag, True)
    with pytest.raises(PermissionError, match="issuance denied"):
        complete(setup)
    assert len(setup["sessions"].revoked) == 1
    assert all(row.revoked for row in setup["sessions"].rows.values())


def test_postcommit_cookie_failure_revokes_hidden_session(setup) -> None:
    """No response cookie escapes if host-only cookie generation fails."""
    setup["exchanger"].redeem.return_value = signed(setup)
    with patch(
        "matchdesk.domain.customer_oidc_completion.customer_session_cookie",
        side_effect=RuntimeError("private database DSN"),
    ):
        with pytest.raises(PermissionError, match="issuance denied") as failure:
            complete(setup)
    assert "private database DSN" not in str(failure.value)
    assert len(setup["sessions"].revoked) == 1
    assert all(row.revoked for row in setup["sessions"].rows.values())


def test_naive_clock_never_redeems_code(setup) -> None:
    """Callers must not override the validation clock with an ambiguous value."""
    setup["exchanger"].redeem.return_value = signed(setup)
    with pytest.raises(ValueError, match="timezone-aware"):
        complete_customer_oidc_sign_in(
            pending=setup["pending"],
            policy=setup["policy"],
            browser=setup["browser"],
            exchanger=setup["exchanger"],
            keys=setup["keys"],
            directory=setup["directory"],
            sessions=setup["sessions"],
            now=NOW.replace(tzinfo=None),
        )
    setup["exchanger"].redeem.assert_not_called()
