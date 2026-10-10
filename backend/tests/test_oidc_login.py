"""Offline broker discovery, PKCE, state, nonce and callback isolation tests."""

import base64
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from matchdesk.domain.customer_identity import CustomerBrokerPolicy
from matchdesk.domain.oidc_login import (
    CustomerOidcPolicy,
    OidcBrowserRedirect,
    PendingOidcExchange,
    begin_customer_oidc_login,
    clear_oidc_login_cookie,
    finish_customer_oidc_login,
    verify_broker_discovery,
)

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://{TENANT}.ciamlogin.com/{TENANT}/v2.0"
PREFIX = f"https://{TENANT}.ciamlogin.com/{TENANT}"
ORIGIN = "https://matchdesk.example"
CLIENT = "11111111-2222-3333-4444-555555555555"
NOW = datetime.now(timezone.utc)


class AtomicAttempts:
    """Test-only locked simulation of a host-managed, single-use state store."""

    def __init__(self) -> None:
        """Persist only hashed states and hide the verifier from browser callers."""
        self._rows = {}
        self._lock = threading.Lock()

    def create(self, attempt) -> bool:
        """Atomically reject reuse of the same hashed state."""
        with self._lock:
            if attempt.state_hash in self._rows:
                return False
            self._rows[attempt.state_hash] = attempt
            return True

    def consume(self, state_hash: str):
        """Remove at most one record across concurrent callback attempts."""
        with self._lock:
            return self._rows.pop(state_hash, None)


def policy(**overrides) -> CustomerOidcPolicy:
    """Pin a fake External ID broker, registered client and exact HTTPS callback."""
    params = dict(
        broker=CustomerBrokerPolicy(
            issuer=ISSUER,
            tenant_id=TENANT,
            audience="api://customer-test",
            client_ids=frozenset({CLIENT}),
        ),
        client_id=CLIENT,
        public_origin=ORIGIN,
        authorization_endpoint=f"{PREFIX}/oauth2/v2.0/authorize",
        token_endpoint=f"{PREFIX}/oauth2/v2.0/token",
        jwks_uri=f"{PREFIX}/discovery/v2.0/keys",
    )
    params.update(overrides)
    return CustomerOidcPolicy(**params)


def metadata(**overrides) -> dict[str, object]:
    """Return host-expected discovery metadata without any network I/O."""
    values: dict[str, object] = {
        "issuer": ISSUER,
        "authorization_endpoint": f"{PREFIX}/oauth2/v2.0/authorize",
        "token_endpoint": f"{PREFIX}/oauth2/v2.0/token",
        "jwks_uri": f"{PREFIX}/discovery/v2.0/keys",
        "code_challenge_methods_supported": ["S256"],
        "response_types_supported": ["code"],
    }
    values.update(overrides)
    return values


def started(store: AtomicAttempts, *, clock: datetime = NOW):
    """Create one pending login and extract browser-facing state and binding."""
    redirect = begin_customer_oidc_login(policy=policy(), store=store, now=clock)
    query = parse_qs(urlsplit(redirect.authorization_url).query)
    binding = redirect.set_cookie.split(";", 1)[0].split("=", 1)[1]
    return redirect, query, binding


def complete(store: AtomicAttempts, state: str, binding: str, **overrides):
    """Send a host-controlled synthetic callback to the single-use verifier."""
    args = dict(
        policy=policy(),
        store=store,
        state=state,
        browser_binding=binding,
        issuer=ISSUER,
        code="sample-authorisation-code",
        now=NOW,
    )
    args.update(overrides)
    return finish_customer_oidc_login(**args)


def test_offline_redirect_uses_code_pkce_s256_nonce_and_exact_callback() -> None:
    """The browser sees no verifier, client credential or arbitrary redirect."""
    store = AtomicAttempts()
    first, query, cookie = started(store)
    second, other, other_cookie = started(store)
    assert isinstance(first, OidcBrowserRedirect)
    assert urlsplit(first.authorization_url).scheme == "https"
    assert urlsplit(first.authorization_url).netloc == f"{TENANT}.ciamlogin.com"
    assert urlsplit(first.authorization_url).path == f"/{TENANT}/oauth2/v2.0/authorize"
    for key, expected in (
        ("response_type", "code"),
        ("response_mode", "query"),
        ("code_challenge_method", "S256"),
        ("redirect_uri", f"{ORIGIN}/api/customer/oidc/callback"),
        ("client_id", CLIENT),
        ("scope", "openid"),
    ):
        assert query[key] == [expected]
    assert len(query["state"][0]) == 43
    assert len(query["nonce"][0]) == 43
    assert len(cookie) == 43
    assert len(query["code_challenge"][0]) == 43
    assert query["state"] != other["state"]
    assert query["nonce"] != other["nonce"]
    assert cookie != other_cookie
    assert "code_verifier" not in query
    assert "access_token" not in first.authorization_url
    assert "Domain=" not in first.set_cookie
    for flag in ("Max-Age=300", "Path=/", "Secure", "HttpOnly", "SameSite=Lax"):
        assert flag in first.set_cookie


def test_callback_recovers_server_only_verifier_with_exact_state_and_issuer() -> None:
    """Successful callback remains a *pending exchange*, never a logged-in user."""
    store = AtomicAttempts()
    redirect, query, cookie = started(store)
    state = query["state"][0]
    pending = complete(store, state, cookie)
    assert isinstance(pending, PendingOidcExchange)
    assert pending.authorization_code == "sample-authorisation-code"
    assert pending.issuer == ISSUER
    assert pending.token_endpoint == f"{PREFIX}/oauth2/v2.0/token"
    assert pending.redirect_uri == f"{ORIGIN}/api/customer/oidc/callback"
    assert pending.client_id == CLIENT
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(pending.code_verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == query["code_challenge"][0]
    assert pending.nonce == query["nonce"][0]
    assert pending.code_verifier not in redirect.authorization_url
    assert pending.code_verifier not in repr(pending)
    assert pending.authorization_code not in repr(pending)
    assert pending.nonce not in repr(pending)
    assert cookie not in repr(redirect)
    assert not hasattr(pending, "identity")
    assert not hasattr(pending, "account_id")
    assert not hasattr(pending, "roles")


def test_state_can_be_consumed_only_once_even_after_success() -> None:
    """No replay of the same browser state into multiple token exchanges."""
    store = AtomicAttempts()
    _, query, binding = started(store)
    state = query["state"][0]
    assert complete(store, state, binding).authorization_code
    with pytest.raises(PermissionError, match="already consumed"):
        complete(store, state, binding)


@pytest.mark.parametrize(
    "malicious",
    [
        {"browser_binding": "a" * 43},
        {"browser_binding": ""},
        {"browser_binding": None},
        {"issuer": "https://accounts.google.com"},
        {"issuer": "https://appleid.apple.com"},
        {"issuer": f"https://other.ciamlogin.com/{TENANT}/v2.0"},
        {"issuer": ""},
        {"code": None},
        {"code": ""},
        {"code": "space code"},
        {"code": "line\nbreak"},
        {"code": "x" * 2049},
        {"code": 12},
        {"error": "access_denied"},
        {"now": NOW - timedelta(seconds=1)},
        {"now": NOW + timedelta(minutes=5)},
    ],
)
def test_callback_tampering_expiry_and_user_cancel_are_denied(malicious) -> None:
    """Tampered return parameters never establish identity and burn the state."""
    store = AtomicAttempts()
    _, query, binding = started(store)
    state = query["state"][0]
    with pytest.raises(PermissionError):
        complete(store, state, binding, **malicious)
    with pytest.raises(PermissionError, match="already consumed"):
        complete(store, state, binding)


@pytest.mark.parametrize("bad_state", ["", None, "invalid", "a" * 42, "x" * 44, "+" * 43])
def test_missing_or_malformed_state_never_consumes_a_real_attempt(bad_state) -> None:
    """State validation occurs before the atomic storage operation."""
    store = AtomicAttempts()
    _, query, binding = started(store)
    with pytest.raises(PermissionError):
        complete(store, bad_state, binding)
    assert complete(store, query["state"][0], binding).issuer == ISSUER


def test_unknown_well_formed_state_never_creates_session() -> None:
    """A random but unregistered callback is not an authentication credential."""
    store = AtomicAttempts()
    with pytest.raises(PermissionError, match="missing or already consumed"):
        complete(store, "A" * 43, "B" * 43)


def test_concurrent_callbacks_allow_exactly_one_winner() -> None:
    """The store's atomic consume contract prevents simultaneous callback replay."""
    store = AtomicAttempts()
    _, query, binding = started(store)
    state = query["state"][0]

    def attempt(_: int) -> bool:
        """Run one independent callback and report whether its state was accepted."""
        try:
            complete(store, state, binding)
            return True
        except PermissionError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(attempt, range(2))) == 1


@pytest.mark.parametrize(
    "invalid",
    [
        {"client_id": "unregistered-client"},
        {"public_origin": "http://matchdesk.example"},
        {"public_origin": "https://matchdesk.example/redirect"},
        {"authorization_endpoint": "https://evil.example/authorize"},
        {"authorization_endpoint": f"{PREFIX}/oauth2/v2.0/authorize?redirect=evil"},
        {"token_endpoint": "https://evil.example/token"},
        {"jwks_uri": "https://evil.example/keys"},
        {"scopes": ("email",)},
        {"scopes": ("openid", "openid")},
        {"scopes": ("openid", "some scope")},
        {"scopes": ("openid", "admin*")},
        {"scopes": ("openid",) * 9},
        {"scopes": ["openid"]},
        {"pending_seconds": 0},
        {"pending_seconds": 301},
        {"pending_seconds": True},
        {"broker": "https://accounts.google.com"},
    ],
)
def test_oidc_policy_rejects_open_redirect_or_untrusted_config(invalid) -> None:
    """Auth and token endpoints are pinned to the single configured broker."""
    with pytest.raises(ValueError):
        policy(**invalid)


@pytest.mark.parametrize(
    "tampered",
    [
        {"issuer": "https://accounts.google.com"},
        {"authorization_endpoint": "https://evil.example/authorize"},
        {"token_endpoint": "https://evil.example/token"},
        {"jwks_uri": "https://evil.example/jwks"},
        {"code_challenge_methods_supported": ["plain"]},
        {"code_challenge_methods_supported": []},
        {"code_challenge_methods_supported": None},
        {"response_types_supported": ["token"]},
        {"response_types_supported": "code"},
    ],
)
def test_untrusted_oidc_discovery_metadata_fails_closed(tampered) -> None:
    """No metadata may expand the configured issuer, scopes, token host or keys."""
    with pytest.raises(PermissionError):
        verify_broker_discovery(policy(), metadata(**tampered))


def test_pinned_oidc_discovery_accepts_valid_code_and_pkce_advertisement() -> None:
    """Expected offline broker metadata must match the exact configured URLs."""
    assert verify_broker_discovery(policy(), metadata()) is None


def test_discovery_refuses_nonmapping_payload() -> None:
    """A malformed HTTP discovery response cannot become a trusted endpoint."""
    with pytest.raises(PermissionError):
        verify_broker_discovery(policy(), ["not a metadata document"])


def test_explicit_short_pending_lifetime_expires_at_boundary() -> None:
    """Expiry is strict; shortening the window cannot be overwritten at callback."""
    p = policy(pending_seconds=30)
    store = AtomicAttempts()
    redirect = begin_customer_oidc_login(policy=p, store=store, now=NOW)
    query = parse_qs(urlsplit(redirect.authorization_url).query)
    cookie = redirect.set_cookie.split(";", 1)[0].split("=", 1)[1]
    assert "Max-Age=30" in redirect.set_cookie
    with pytest.raises(PermissionError):
        finish_customer_oidc_login(
            policy=p,
            store=store,
            state=query["state"][0],
            browser_binding=cookie,
            issuer=ISSUER,
            code="code",
            now=NOW + timedelta(seconds=30),
        )


def test_hash_collision_refuses_redirect_and_does_not_create_second_record() -> None:
    """A storage insert collision cannot return a browser-auth URL."""
    store = AtomicAttempts()
    store.create = lambda attempt: False
    with pytest.raises(PermissionError, match="could not be reserved"):
        begin_customer_oidc_login(policy=policy(), store=store, now=NOW)


@pytest.mark.parametrize("clock", [NOW.replace(tzinfo=None), "today", 42])
def test_naive_or_untyped_login_clocks_are_rejected(clock) -> None:
    """Explicit host clock overrides require timezone-aware datetimes."""
    with pytest.raises(ValueError):
        begin_customer_oidc_login(policy=policy(), store=AtomicAttempts(), now=clock)


def test_forged_stored_browser_binding_and_issuer_fail_closed() -> None:
    """Even a compromised stored record cannot switch tenants or browser context."""
    store = AtomicAttempts()
    _, query, binding = started(store)
    state = query["state"][0]
    key = hashlib.sha256(state.encode()).hexdigest()
    stored = store._rows[key]
    store._rows[key] = replace(stored, issuer="https://other.ciamlogin.com")
    with pytest.raises(PermissionError):
        complete(store, state, binding)


def test_explicit_login_cookie_expiry_matches_host_security_contract() -> None:
    """The login secret can be cleared without retaining a session credential."""
    header = clear_oidc_login_cookie()
    assert header.startswith("__Host-matchdesk_oidc=; Max-Age=0;")
    assert "Expires=Thu, 01 Jan 1970" in header
    assert "Domain=" not in header
    assert "Secure; HttpOnly; SameSite=Lax" in header



def test_invalid_broker_scopes_and_callback_time_are_rejected() -> None:
    """Reject malformed browser-broker policy values and callback clocks."""
    with pytest.raises(ValueError):
        policy(scopes=("openid", "custom\nscope"))
    store = AtomicAttempts()
    _, query, binding = started(store)
    with pytest.raises(ValueError):
        complete(store, query["state"][0], binding, now=NOW.replace(tzinfo=None))


@pytest.mark.parametrize("bad_hash", [None, "x" * 64, "a" * 63])
def test_untrusted_saved_login_hash_is_rejected(bad_hash) -> None:
    """Never honor malformed state or binding hashes after storage reads."""
    store = AtomicAttempts()
    _, query, binding = started(store)
    state = query["state"][0]
    key = hashlib.sha256(state.encode()).hexdigest()
    # Persisted rows may be corrupted after construction; simulate a bad row
    # without invoking dataclass validation before the callback guard.
    object.__setattr__(store._rows[key], "binding_hash", bad_hash)
    with pytest.raises(ValueError):
        complete(store, state, binding)


@pytest.mark.parametrize(
    "bad",
    [
        {"nonce": "a" * 42},
        {"code_verifier": "invalid-verifier"},
        {"issued_at": NOW.replace(tzinfo=None)},
        {"expires_at": NOW + timedelta(minutes=6)},
    ],
)
def test_invalid_stored_login_secrets_and_lifetime_fail_closed(bad) -> None:
    """Tampered one-time storage records cannot authorize code exchange."""
    store = AtomicAttempts()
    _, query, binding = started(store)
    state = query["state"][0]
    key = hashlib.sha256(state.encode()).hexdigest()
    for name, value in bad.items():
        object.__setattr__(store._rows[key], name, value)
    with pytest.raises(ValueError):
        complete(store, state, binding)


def test_secure_random_generator_fault_denies_authorisation_redirect() -> None:
    """Malformed RNG output cannot reserve state or expose an unusable URL."""
    from unittest.mock import patch

    store = AtomicAttempts()
    with patch(
        "matchdesk.domain.oidc_login.secrets.token_urlsafe",
        return_value="not-a-secure-256-bit-value",
    ):
        with pytest.raises(RuntimeError, match="random generator"):
            begin_customer_oidc_login(policy=policy(), store=store, now=NOW)
    assert store._rows == {}
