"""Exercise isolated HTTP OIDC callback isolation with real signed broker tokens."""

from datetime import datetime, timezone
from threading import Lock
from unittest.mock import Mock
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt import PyJWK
from matchdesk.api.app import create_app
from matchdesk.api.customer_oidc_routes import create_customer_oidc_router
from matchdesk.domain.browser_session_security import CustomerBrowserPolicy
from matchdesk.domain.customer_identity import CustomerBrokerPolicy
from matchdesk.domain.oidc_login import CustomerOidcPolicy

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://test.ciamlogin.com/{TENANT}/v2.0"
BASE = f"https://test.ciamlogin.com/{TENANT}"
CLIENT = "test-customer-client"
ORIGIN = "https://matchdesk.example"


class Attempts:
    """In-memory locked state; PostgreSQL atomic claims are tested separately."""

    def __init__(self) -> None:
        """Retain hashed state for exactly one browser-bound redemption."""
        self.rows = {}
        self.lock = Lock()
        self.fail_create = False
        self.fail_consume = False

    def create(self, attempt) -> bool:
        """Reserve a unique state or emulate a durable-store outage."""
        if self.fail_create:
            raise RuntimeError("secret Postgres DSN")
        with self.lock:
            if attempt.state_hash in self.rows:
                return False
            self.rows[attempt.state_hash] = attempt
            return True

    def consume(self, state_hash: str):
        """Return and remove at most one matching login transaction."""
        if self.fail_consume:
            raise RuntimeError("secret Postgres DSN")
        with self.lock:
            return self.rows.pop(state_hash, None)


class Sessions:
    """Persist opaque customer sessions, without granting any producer roles."""

    def __init__(self) -> None:
        """Keep in-memory rows for HTTP assertions without cloud dependencies."""
        self.rows = {}
        self.fail_create = False

    def create(self, record) -> bool:
        """Persist an exact customer-only candidate or reject simulated outage."""
        if self.fail_create:
            raise RuntimeError("secret Postgres DSN")
        if record.session_id in self.rows:
            return False
        self.rows[record.session_id] = record
        return True

    def load(self, opaque_session_id: str):
        """Resolve an active session only by its unguessable opaque token."""
        return self.rows.get(opaque_session_id)

    def revoke(self, opaque_session_id: str) -> bool:
        """Invalidate the created bearer during post-persistence failure."""
        from dataclasses import replace

        record = self.rows.get(opaque_session_id)
        if record is None or record.revoked:
            return False
        self.rows[opaque_session_id] = replace(record, revoked=True)
        return True


def b64(number: int) -> str:
    """Encode RSA public parameters for offline PyJWK verification."""
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
    return jwt.utils.base64url_encode(raw).decode("ascii")


@pytest.fixture
def configured():
    """Build opt-in HTTP route and one ephemeral, issuer-qualified signer."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    jwk = PyJWK.from_dict(
        {
            "kty": "RSA",
            "alg": "RS256",
            "kid": "host-reviewed-test-key",
            "use": "sig",
            "n": b64(numbers.n),
            "e": b64(numbers.e),
        }
    )
    policy = CustomerOidcPolicy(
        broker=CustomerBrokerPolicy(
            issuer=ISSUER,
            tenant_id=TENANT,
            audience="api://test-customer",
            client_ids=frozenset({CLIENT}),
        ),
        client_id=CLIENT,
        public_origin=ORIGIN,
        authorization_endpoint=f"{BASE}/oauth2/v2.0/authorize",
        token_endpoint=f"{BASE}/oauth2/v2.0/token",
        jwks_uri=f"{BASE}/discovery/v2.0/keys",
    )
    attempts = Attempts()
    sessions = Sessions()
    keys = Mock()
    keys.resolve.return_value = jwk
    directory = Mock()
    directory.lookup.return_value = "registered-customer"
    exchanger = Mock()

    def signed(*, pending):
        """Sign an exact broker ID token using the secret server-side nonce."""
        now = int(datetime.now(timezone.utc).timestamp())
        return jwt.encode(
            {
                "iss": ISSUER,
                "aud": CLIENT,
                "tid": TENANT,
                "sub": "broker-subject",
                "nonce": pending.nonce,
                "iat": now - 10,
                "nbf": now - 10,
                "exp": now + 600,
                "email": "forged-privileged@example.com",
                "roles": ["producer", "administrator"],
            },
            private,
            algorithm="RS256",
            headers={"kid": "host-reviewed-test-key"},
        )

    exchanger.redeem.side_effect = signed
    router = create_customer_oidc_router(
        policy=policy,
        browser=CustomerBrowserPolicy(public_origin=ORIGIN),
        attempts=attempts,
        exchanger=exchanger,
        keys=keys,
        directory=directory,
        sessions=sessions,
    )
    client = TestClient(create_app(customer_oidc_router=router), base_url=ORIGIN)
    return client, attempts, sessions, exchanger, directory, policy


def started(configured):
    """Perform a legitimate top-level login start and capture callback secrets."""
    client, _, _, _, _, _ = configured
    response = client.post(
        "/api/customer/oidc/start",
        headers={"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    params = parse_qs(urlsplit(response.headers["location"]).query)
    binding = response.headers["set-cookie"].split(";", 1)[0]
    return response, params, binding


def callback(configured, params, binding, **changes):
    """Navigate from the broker with a single issuer-bound authorization code."""
    client, _, _, _, _, _ = configured
    query = {
        "iss": ISSUER,
        "state": params["state"][0],
        "code": "fresh-code",
    }
    query.update(changes)
    return client.get(
        f"/api/customer/oidc/callback?{urlencode(query)}",
        headers={
            "Cookie": binding,
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
        },
        follow_redirects=False,
    )


def test_default_app_does_not_expose_login() -> None:
    """The actual deployed app never automatically activates federation."""
    client = TestClient(create_app(), base_url=ORIGIN)
    assert client.post("/api/customer/oidc/start").status_code == 404
    assert client.get("/api/customer/oidc/callback").status_code == 404


def test_signed_callback_consumes_once_and_creates_customer_only_cookie(configured) -> None:
    """Return two independent cookie headers, never upstream secrets or roles."""
    first, params, binding = started(configured)
    assert first.headers["Cache-Control"].startswith("no-store")
    assert first.headers["Referrer-Policy"] == "no-referrer"
    assert params["client_id"] == [CLIENT]
    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["redirect_uri"] == [f"{ORIGIN}/api/customer/oidc/callback"]
    response = callback(configured, params, binding)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2
    assert cookies[0].startswith("__Host-matchdesk_oidc=; Max-Age=0")
    assert cookies[1].startswith("__Host-matchdesk_customer=")
    assert "Secure; HttpOnly; SameSite=Lax" in cookies[1]
    assert "Domain=" not in cookies[1]
    assert "fresh-code" not in response.text
    assert "forged-privileged@example.com" not in str(response.headers)
    client, attempts, sessions, exchanger, directory, _ = configured
    assert len(attempts.rows) == 0
    assert len(sessions.rows) == 1
    record = next(iter(sessions.rows.values()))
    assert record.realm == "customer"
    assert not hasattr(record, "roles")
    assert record.identity.subject == "broker-subject"
    directory.lookup.assert_called_once_with(
        issuer=ISSUER, tenant_id=TENANT, subject="broker-subject"
    )
    exchanger.redeem.assert_called_once()
    assert callback(configured, params, binding).status_code == 401
    assert len(sessions.rows) == 1
    assert client.get("/api/ready").status_code == 503


@pytest.mark.parametrize(
    "bad_headers",
    [
        {"Origin": "https://evil.example"},
        {},
        {"Origin": ORIGIN, "Sec-Fetch-Site": "cross-site"},
        {"Origin": ORIGIN, "X-Forwarded-Proto": "https"},
    ],
)
def test_start_denies_untrusted_origins_without_reserving_state(configured, bad_headers) -> None:
    """Cross-site POST and proxy spoofing never create a login attempt."""
    client, attempts, _, _, _, _ = configured
    response = client.post("/api/customer/oidc/start", headers=bad_headers, follow_redirects=False)
    assert response.status_code == 401
    assert not attempts.rows
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_start_does_not_accept_redirect_input_or_raw_query(configured) -> None:
    """No caller-provided URL can change the broker redirect or callback."""
    client, attempts, _, _, _, _ = configured
    response = client.post(
        "/api/customer/oidc/start?returnUrl=https://evil.example",
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert not attempts.rows


@pytest.mark.parametrize(
    "changed",
    [
        {"iss": "https://accounts.google.com"},
        {"iss": "https://appleid.apple.com"},
        {"state": "a" * 43},
        {"code": "invalid with spaces"},
        {"code": ""},
        {"error": "access_denied", "code": None},
    ],
)
def test_invalid_or_cancelled_callback_cannot_issue_session(configured, changed) -> None:
    """Issuer mix-up, tampered state, code and cancellation deny login."""
    _, params, binding = started(configured)
    if changed.get("code") is None:
        client, _, sessions, exchanger, _, _ = configured
        query = {"iss": ISSUER, "state": params["state"][0], "error": "access_denied"}
        response = client.get(
            "/api/customer/oidc/callback?" + urlencode(query),
            headers={"Cookie": binding},
            follow_redirects=False,
        )
    else:
        response = callback(configured, params, binding, **changed)
        _, _, sessions, exchanger, _, _ = configured
    assert response.status_code == 401
    assert response.headers["Cache-Control"].startswith("no-store")
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert not sessions.rows
    exchanger.redeem.assert_not_called()


@pytest.mark.parametrize(
    "append",
    [
        "&state=duplicate",
        "&code=duplicate",
        "&iss=duplicate",
        "&returnUrl=https%3A%2F%2Fevil.example",
        "&error=access_denied",
        "&error_description=private",
    ],
)
def test_callback_rejects_duplicate_and_extra_query_values(configured, append) -> None:
    """Parameter pollution is blocked before the one-time code is sent to the broker."""
    client, _, sessions, exchanger, _, _ = configured
    _, params, binding = started(configured)
    query = urlencode({"state": params["state"][0], "iss": ISSUER, "code": "fresh-code"})
    response = client.get(
        f"/api/customer/oidc/callback?{query}{append}",
        headers={"Cookie": binding},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert not sessions.rows
    exchanger.redeem.assert_not_called()


@pytest.mark.parametrize(
    "binding",
    ["", "wrong", "a" * 43, "__Host-matchdesk_oidc=missing", "__Host-matchdesk_oidc=a; bad=1"],
)
def test_malformed_or_unknown_browser_binding_denies_callback(configured, binding) -> None:
    """OIDC authorization codes cannot be stolen across browser sessions."""
    client, _, sessions, exchanger, _, _ = configured
    _, params, _ = started(configured)
    raw = binding if binding.startswith("__Host-matchdesk_oidc=") else f"x={binding}"
    query = urlencode({"state": params["state"][0], "iss": ISSUER, "code": "fresh-code"})
    response = client.get(
        "/api/customer/oidc/callback?" + query,
        headers={"Cookie": raw},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert not sessions.rows
    exchanger.redeem.assert_not_called()


def test_duplicate_binding_cookie_denied_even_with_same_valid_value(configured) -> None:
    """Cookie tossing cannot establish or replace an existing account session."""
    client, _, sessions, exchanger, _, _ = configured
    _, params, binding = started(configured)
    query = urlencode({"state": params["state"][0], "iss": ISSUER, "code": "fresh-code"})
    response = client.get(
        "/api/customer/oidc/callback?" + query,
        headers={"Cookie": binding + "; " + binding},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert not sessions.rows
    exchanger.redeem.assert_not_called()


def test_unregistered_account_rejected_without_provisioning(configured) -> None:
    """A signed broker identity is never sufficient to auto-link an account."""
    _, params, binding = started(configured)
    _, _, sessions, exchanger, directory, _ = configured
    directory.lookup.return_value = None
    response = callback(configured, params, binding)
    assert response.status_code == 401
    assert not sessions.rows
    exchanger.redeem.assert_called_once()


def test_start_and_callback_storage_faults_hide_database_details(configured) -> None:
    """Database outages return bounded generic errors and no session bearer."""
    client, attempts, sessions, exchanger, _, _ = configured
    attempts.fail_create = True
    start_response = client.post(
        "/api/customer/oidc/start", headers={"Origin": ORIGIN}, follow_redirects=False
    )
    assert start_response.status_code == 503
    assert "secret Postgres DSN" not in start_response.text
    attempts.fail_create = False
    _, params, binding = started(configured)
    sessions.fail_create = True
    result = callback(configured, params, binding)
    assert result.status_code == 401
    assert "secret Postgres DSN" not in result.text
    assert "__Host-matchdesk_customer=" not in str(result.headers)
    assert not sessions.rows
    exchanger.redeem.assert_called_once()


def test_callback_rejects_bad_browser_transport_and_wrong_navigation(configured) -> None:
    """Host mismatch, proxy spoofing and XHR cannot reach the code exchanger."""
    client, _, sessions, exchanger, _, _ = configured
    _, params, binding = started(configured)
    query = urlencode({"state": params["state"][0], "iss": ISSUER, "code": "fresh-code"})
    for extra in (
        {"X-Forwarded-Host": "evil.example"},
        {"Sec-Fetch-Mode": "cors"},
        {"Sec-Fetch-Dest": "empty"},
        {"Origin": "https://evil.example"},
        {"Host": "evil.example"},
    ):
        headers = {"Cookie": binding, "Sec-Fetch-Mode": "navigate"}
        headers.update(extra)
        response = client.get(
            "/api/customer/oidc/callback?" + query,
            headers=headers,
            follow_redirects=False,
        )
        assert response.status_code == 401
    assert not sessions.rows
    exchanger.redeem.assert_not_called()


def test_wrong_callback_signing_key_never_returns_session(configured) -> None:
    """The broker's unknown key must not establish an account or cookie."""
    _, params, binding = started(configured)
    _, _, sessions, exchanger, _, _ = configured
    exchanger.redeem.return_value = "header.payload.signature"
    exchanger.redeem.side_effect = None
    response = callback(configured, params, binding)
    assert response.status_code == 401
    assert not sessions.rows
    assert "__Host-matchdesk_customer=" not in str(response.headers)


def test_constructor_requires_host_reviewed_dependencies(configured) -> None:
    """No implicit configuration may silently activate a login router."""
    _, attempts, sessions, exchanger, directory, policy = configured
    with pytest.raises(ValueError):
        create_customer_oidc_router(
            policy=policy,
            browser=CustomerBrowserPolicy(public_origin="https://different.example"),
            attempts=attempts,
            exchanger=exchanger,
            keys=Mock(),
            directory=directory,
            sessions=sessions,
        )
