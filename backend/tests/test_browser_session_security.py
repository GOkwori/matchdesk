"""Offline BFF cookie and CSRF security regressions; no live HTTP routes."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from matchdesk.domain.browser_session_security import (
    CustomerBrowserPolicy,
    authorize_customer_mutation,
    clear_customer_session_cookie,
    customer_session_cookie,
    issue_customer_csrf,
)
from matchdesk.domain.customer_identity import CustomerIdentityKey
from matchdesk.domain.customer_sessions import new_customer_session

NOW = datetime.now(timezone.utc)
POLICY = CustomerBrowserPolicy(public_origin="https://matchdesk.example")
SECRET = b"s" * 32
IDENTITY = CustomerIdentityKey(
    issuer="https://matchdesk.ciamlogin.com/example/v2.0",
    tenant_id="example",
    subject="customer-subject",
)


class Store:
    """In-memory representation of an authoritative BFF session lookup."""

    def __init__(self, session=None):
        """Retain exactly one server-owned session, not user-supplied claims."""
        self.session = session

    def load(self, opaque_session_id: str):
        """Reject unknown bearer secrets even when an account exists."""
        if self.session is not None and self.session.session_id == opaque_session_id:
            return self.session
        return None


def session(*, ttl: timedelta = timedelta(hours=1)):
    """Issue a synthetic valid offline customer session."""
    return new_customer_session(
        identity=IDENTITY, account_id="account-1", now=NOW, ttl=ttl
    )


def test_cookie_is_host_only_http_only_and_lifetime_bounded() -> None:
    """Session cookies cannot use an insecure, domain-wide or JS-readable scope."""
    s = session()
    header = customer_session_cookie(s.session_id, store=Store(s), policy=POLICY, now=NOW)
    assert header.startswith(f"__Host-matchdesk_customer={s.session_id}; Max-Age=3600;")
    for required in ("Path=/", "Secure", "HttpOnly", "SameSite=Lax"):
        assert required in header
    assert "Domain=" not in header


def test_cookie_lifetime_never_outlives_db_expiry() -> None:
    """Browser expiry follows the immutable PostgreSQL expiry, not a renewal."""
    s = session(ttl=timedelta(seconds=20))
    header = customer_session_cookie(
        s.session_id, store=Store(s), policy=POLICY, now=NOW + timedelta(seconds=7)
    )
    assert "Max-Age=13" in header


def test_logout_cookie_uses_identical_host_only_attributes() -> None:
    """Clearing the cookie never returns the previous raw session secret."""
    header = clear_customer_session_cookie()
    assert header.startswith("__Host-matchdesk_customer=; Max-Age=0;")
    assert "Expires=Thu, 01 Jan 1970" in header
    assert "Domain=" not in header
    assert "Secure; HttpOnly; SameSite=Lax" in header


@pytest.mark.parametrize(
    "origin",
    [
        "http://matchdesk.example",
        "https://matchdesk.example/",
        "https://*.matchdesk.example",
        "https://matchdesk.example/path",
        "https://matchdesk.example?target=elsewhere",
        "https://matchdesk.example#fragment",
        "https://user@matchdesk.example",
        "https://.matchdesk.example",
        "https://matchdesk.example:bad",
        "https://matchdesk.example:0",
        "https://",
        "",
    ],
)
def test_untrusted_or_noncanonical_browser_origins_are_rejected(origin: str) -> None:
    """Host policy must be precise and HTTPS-only before emitting a cookie."""
    with pytest.raises(ValueError, match="origin"):
        CustomerBrowserPolicy(public_origin=origin)


@pytest.mark.parametrize("max_age", [0, -1, 3601, True, "3600"])
def test_cookie_max_age_has_an_explicit_bounded_integer(max_age) -> None:
    """Neither unbounded nor coercible values control session persistence."""
    with pytest.raises(ValueError):
        CustomerBrowserPolicy(
            public_origin="https://matchdesk.example",
            max_cookie_age_seconds=max_age,
        )


def test_csrf_is_bound_to_current_persisted_session() -> None:
    """Only server-owned sessions can mint or validate a same-origin CSRF token."""
    s = session()
    store = Store(s)
    csrf = issue_customer_csrf(
        s.session_id, store=store, policy=POLICY, secret=SECRET, now=NOW
    )
    assert len(csrf) == 64
    assert csrf != s.session_id
    assert authorize_customer_mutation(
        s.session_id,
        store=store,
        policy=POLICY,
        secret=SECRET,
        method="POST",
        request_origin=POLICY.public_origin,
        csrf_header=csrf,
        fetch_site="same-origin",
        now=NOW,
    ) == s


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "post", "TRACE"])
def test_nonmutation_or_unexpected_methods_fail_closed(method: str) -> None:
    """The mutation guard must never be repurposed to approve safe or unknown calls."""
    s = session()
    csrf = issue_customer_csrf(
        s.session_id, store=Store(s), policy=POLICY, secret=SECRET, now=NOW
    )
    with pytest.raises(PermissionError):
        authorize_customer_mutation(
            s.session_id,
            store=Store(s),
            policy=POLICY,
            secret=SECRET,
            method=method,
            request_origin=POLICY.public_origin,
            csrf_header=csrf,
            now=NOW,
        )


@pytest.mark.parametrize(
    "request_origin",
    ["https://evil.example", "null", "https://matchdesk.example.evil", None],
)
def test_cross_site_mutation_origin_is_rejected(request_origin) -> None:
    """CORS and third-party cookies cannot override the authoritative origin."""
    s = session()
    with pytest.raises(PermissionError, match="origin"):
        authorize_customer_mutation(
            s.session_id,
            store=Store(s),
            policy=POLICY,
            secret=SECRET,
            method="PATCH",
            request_origin=request_origin,
            csrf_header="a" * 64,
            now=NOW,
        )


@pytest.mark.parametrize("fetch_site", ["cross-site", "same-site", "none"])
def test_untrusted_fetch_metadata_fails_closed(fetch_site: str) -> None:
    """Same-site but cross-origin requests are not trusted mutations."""
    s = session()
    with pytest.raises(PermissionError, match="fetch origin"):
        authorize_customer_mutation(
            s.session_id,
            store=Store(s),
            policy=POLICY,
            secret=SECRET,
            method="DELETE",
            request_origin=POLICY.public_origin,
            csrf_header="a" * 64,
            fetch_site=fetch_site,
            now=NOW,
        )


@pytest.mark.parametrize("invalid", ["", "a" * 63, "A" * 64, "x" * 64, None])
def test_invalid_csrf_header_rejected_before_state_change(invalid) -> None:
    """Malformed synchronizer proof must never reach downstream mutation code."""
    s = session()
    with pytest.raises(PermissionError, match="CSRF"):
        authorize_customer_mutation(
            s.session_id,
            store=Store(s),
            policy=POLICY,
            secret=SECRET,
            method="PUT",
            request_origin=POLICY.public_origin,
            csrf_header=invalid,
            now=NOW,
        )


def test_csrf_proof_for_another_session_is_rejected() -> None:
    """Rotation invalidates stale CSRF even for the same canonical account."""
    original = session()
    rotated = session()
    csrf = issue_customer_csrf(
        original.session_id, store=Store(original), policy=POLICY, secret=SECRET, now=NOW
    )
    with pytest.raises(PermissionError, match="does not match"):
        authorize_customer_mutation(
            rotated.session_id,
            store=Store(rotated),
            policy=POLICY,
            secret=SECRET,
            method="POST",
            request_origin=POLICY.public_origin,
            csrf_header=csrf,
            now=NOW,
        )


@pytest.mark.parametrize("secret", [b"", b"too-short", "not bytes"])
def test_csrf_requires_a_protected_256_bit_server_key(secret) -> None:
    """Client-supplied or low-entropy material cannot control HMAC signing."""
    s = session()
    with pytest.raises(ValueError, match="256 bits"):
        issue_customer_csrf(
            s.session_id, store=Store(s), policy=POLICY, secret=secret, now=NOW
        )


def test_revoked_or_missing_session_cannot_get_csrf_or_cookie() -> None:
    """Identity alone cannot mint tokens after session removal or revocation."""
    s = session()
    for store in (Store(None), Store(replace(s, revoked=True))):
        with pytest.raises(PermissionError):
            issue_customer_csrf(
                s.session_id, store=store, policy=POLICY, secret=SECRET, now=NOW
            )
        with pytest.raises(PermissionError):
            customer_session_cookie(s.session_id, store=store, policy=POLICY, now=NOW)


def test_expired_session_cannot_authorize_mutation() -> None:
    """A correct HMAC never overrides server-side expiry."""
    s = session(ttl=timedelta(seconds=5))
    token = issue_customer_csrf(
        s.session_id, store=Store(s), policy=POLICY, secret=SECRET, now=NOW
    )
    with pytest.raises(PermissionError):
        authorize_customer_mutation(
            s.session_id,
            store=Store(s),
            policy=POLICY,
            secret=SECRET,
            method="POST",
            request_origin=POLICY.public_origin,
            csrf_header=token,
            now=NOW + timedelta(seconds=5),
        )


def test_browser_cookie_expiry_rounding_fails_closed() -> None:
    """A subsecond-only remaining lifetime cannot produce a zero-age live cookie."""
    s = session(ttl=timedelta(milliseconds=500))
    with pytest.raises(PermissionError, match="expired"):
        customer_session_cookie(s.session_id, store=Store(s), policy=POLICY, now=NOW)
