"""Exercise opt-in customer HTTP session status, CSRF, renewal and logout."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from matchdesk.api.app import create_app
from matchdesk.api.customer_session_routes import create_customer_session_router
from matchdesk.domain.browser_session_security import CustomerBrowserPolicy
from matchdesk.domain.customer_identity import CustomerIdentityKey
from matchdesk.domain.customer_sessions import new_customer_session

ORIGIN = "https://matchdesk.example"
SECRET = b"offline-session-security-key-for-tests"
COOKIE_NAME = "__Host-matchdesk_customer"
POLICY = CustomerBrowserPolicy(public_origin=ORIGIN)


class Store:
    """A test-only trusted session store; real PostgreSQL tested independently."""

    def __init__(self) -> None:
        """Seed one valid customer without allowing HTTP to provision accounts."""
        identity = CustomerIdentityKey(issuer=ORIGIN, tenant_id="ci", subject="fan")
        original = new_customer_session(identity=identity, account_id="fan")
        self.original = original
        self.rows = {original.session_id: original}
        self.reject_rotate = False
        self.reject_revoke = False

    def load(self, opaque_session_id: str):
        """Resolve only the exact persisted session."""
        return self.rows.get(opaque_session_id)

    def rotate(self, opaque_session_id: str, *, now: datetime | None = None):
        """Simulate one-winner replacement, preserving the absolute expiry."""
        if self.reject_rotate:
            return None
        previous = self.rows.get(opaque_session_id)
        if previous is None or previous.revoked:
            return None
        current = now or datetime.now(timezone.utc)
        successor = new_customer_session(
            identity=previous.identity,
            account_id=previous.account_id,
            now=current,
            ttl=previous.expires_at - current,
        )
        self.rows[opaque_session_id] = replace(previous, revoked=True)
        self.rows[successor.session_id] = successor
        return successor

    def revoke(self, opaque_session_id: str) -> bool:
        """Mark one live record revoked, fail for absent or repeated requests."""
        if self.reject_revoke:
            return False
        previous = self.rows.get(opaque_session_id)
        if previous is None or previous.revoked:
            return False
        self.rows[opaque_session_id] = replace(previous, revoked=True)
        return True


def configured() -> tuple[TestClient, Store]:
    """Mount the router on an isolated test app only."""
    store = Store()
    router = create_customer_session_router(store=store, policy=POLICY, csrf_secret=SECRET)
    return TestClient(create_app(customer_session_router=router), base_url=ORIGIN), store


def headers(proof: str) -> dict[str, str]:
    """Create an explicit same-origin write with a session HMAC."""
    return {"Origin": ORIGIN, "X-MatchDesk-CSRF": proof, "Sec-Fetch-Site": "same-origin"}


def test_default_app_still_has_no_session_routes() -> None:
    """Shipped app must remain independent of the customer OIDC design."""
    client = TestClient(create_app(), base_url=ORIGIN)
    assert client.get("/api/customer/session").status_code == 404


def test_status_and_csrf_for_persisted_customer_only() -> None:
    """Authenticated reads return no email, roles, account key or bearer."""
    client, store = configured()
    token = store.original.session_id
    client.cookies.set(COOKIE_NAME, token)
    response = client.get("/api/customer/session")
    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert token not in response.text
    assert "fan" not in response.text
    assert response.headers["Cache-Control"].startswith("no-store")
    csrf = client.get("/api/customer/session/csrf")
    assert csrf.status_code == 200
    assert len(csrf.json()["csrf_token"]) == 64


def test_renew_replaces_token_and_logout_revokes_successor() -> None:
    """The browser can renew with CSRF, then log out using the new proof."""
    client, store = configured()
    old_token = store.original.session_id
    client.cookies.set(COOKIE_NAME, old_token)
    first_proof = client.get("/api/customer/session/csrf").json()["csrf_token"]
    renewed = client.post("/api/customer/session/renew", headers=headers(first_proof))
    assert renewed.status_code == 200
    successor_id = renewed.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    assert successor_id != old_token
    assert store.rows[old_token].revoked
    assert store.rows[successor_id].expires_at == store.original.expires_at
    assert "Domain=" not in renewed.headers["set-cookie"]
    assert "Secure; HttpOnly; SameSite=Lax" in renewed.headers["set-cookie"]
    assert successor_id not in renewed.text
    client.cookies.set(COOKIE_NAME, successor_id)
    logged_out = client.post(
        "/api/customer/session/logout", headers=headers(renewed.json()["csrf_token"])
    )
    assert logged_out.status_code == 204
    assert store.rows[successor_id].revoked
    assert "Max-Age=0" in logged_out.headers["set-cookie"]


@pytest.mark.parametrize(
    "cookie",
    ["", "bad", "A" * 64, "a" * 64, "x" * 5000],
)
def test_invalid_or_absent_session_cookie_never_authenticates(cookie: str) -> None:
    """Tokens cannot be manufactured through headers, guessing or malformed cookies."""
    client, _ = configured()
    if cookie:
        client.cookies.set(COOKIE_NAME, cookie)
    assert client.get("/api/customer/session").status_code == 401


@pytest.mark.parametrize("origin", ["http://matchdesk.example", "https://evil.example"])
def test_insecure_or_wrong_host_cannot_read_session(origin: str) -> None:
    """A valid cookie cannot be used under a different scheme or host."""
    store = Store()
    router = create_customer_session_router(store=store, policy=POLICY, csrf_secret=SECRET)
    client = TestClient(create_app(customer_session_router=router), base_url=origin)
    client.cookies.set(COOKIE_NAME, store.original.session_id)
    assert client.get("/api/customer/session").status_code == 403


@pytest.mark.parametrize(
    "bad",
    [
        {"Origin": "https://evil.example"},
        {"X-MatchDesk-CSRF": "f" * 64},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_forged_csrf_and_wrong_origin_reject_mutations(bad: dict[str, str]) -> None:
    """A hostile request cannot rotate or revoke a valid customer token."""
    client, store = configured()
    client.cookies.set(COOKIE_NAME, store.original.session_id)
    proof = client.get("/api/customer/session/csrf").json()["csrf_token"]
    sent = headers(proof)
    sent.update(bad)
    assert client.post("/api/customer/session/logout", headers=sent).status_code == 403
    assert not store.rows[store.original.session_id].revoked


@pytest.mark.parametrize("operation", ["renew", "logout"])
def test_store_rejection_denies_lifecycle_operation(operation: str) -> None:
    """A failed database mutation cannot claim a successful HTTP session change."""
    client, store = configured()
    client.cookies.set(COOKIE_NAME, store.original.session_id)
    proof = client.get("/api/customer/session/csrf").json()["csrf_token"]
    if operation == "renew":
        store.reject_rotate = True
    else:
        store.reject_revoke = True
    response = client.post(f"/api/customer/session/{operation}", headers=headers(proof))
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    "change",
    [
        {"csrf_secret": b"short"},
        {"policy": "invalid"},
        {"store": object()},
    ],
)
def test_router_refuses_untrusted_configuration(change: dict[str, object]) -> None:
    """Configuration errors fail closed rather than enabling a public login."""
    options: dict[str, object] = {"store": Store(), "policy": POLICY, "csrf_secret": SECRET}
    options.update(change)
    with pytest.raises(ValueError):
        create_customer_session_router(**options)
