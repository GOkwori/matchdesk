"""Customer-only BFF cookie and CSRF controls, not a live login endpoint.

This offline contract uses the existing durable session store. Caller-owned HTTP
transport must separately enforce HTTPS, explicit CORS, no-store responses and
cookie redaction; producer/admin operations use an independent workforce realm.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from matchdesk.domain.customer_sessions import (
    CustomerSession,
    CustomerSessionStore,
    resolve_customer_session,
)

_COOKIE = "__Host-matchdesk_customer"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class CustomerBrowserPolicy:
    """Host-configured HTTPS origin and maximum browser cookie lifetime."""

    public_origin: str
    max_cookie_age_seconds: int = 3600

    def __post_init__(self) -> None:
        """Reject untrusted hosts and permissive cookie lifetimes."""
        try:
            url = urlsplit(self.public_origin)
            port = url.port
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Customer browser origin must be exact HTTPS") from exc
        if (
            not isinstance(self.public_origin, str)
            or url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.path
            or url.query
            or url.fragment
            or "*" in self.public_origin
            or url.hostname.startswith(".")
            or self.public_origin != f"https://{url.netloc}"
            or (port is not None and port < 1)
            or type(self.max_cookie_age_seconds) is not int
            or not 1 <= self.max_cookie_age_seconds <= 3600
        ):
            raise ValueError("Customer browser origin must be exact HTTPS")


def _csrf_key(secret: bytes) -> bytes:
    """Require a protected 256-bit host-owned HMAC key, never a JWT claim."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("Customer CSRF signing key must have at least 256 bits")
    return secret


def _csrf_digest(token: str, *, policy: CustomerBrowserPolicy, secret: bytes) -> str:
    """Bind CSRF proof to one high-entropy session and its approved HTTPS origin."""
    message = (
        b"matchdesk-customer-csrf-v1\x00"
        + policy.public_origin.encode("ascii")
        + b"\x00"
        + token.encode("ascii")
    )
    return hmac.new(_csrf_key(secret), message, hashlib.sha256).hexdigest()


def customer_session_cookie(
    token: str,
    *,
    store: CustomerSessionStore,
    policy: CustomerBrowserPolicy,
    now: datetime | None = None,
) -> str:
    """Issue the host-prefixed cookie only for a currently valid persisted session.

    Use a host-only cookie with no Domain attribute. The browser max-age never
    exceeds the database's immutable absolute expiry or the configured bound.
    """
    current = now or datetime.now(timezone.utc)
    record = resolve_customer_session(token, store=store, now=current)
    remaining = int((record.expires_at - current).total_seconds())
    max_age = min(remaining, policy.max_cookie_age_seconds)
    if max_age <= 0:
        raise PermissionError("Customer browser session has expired")
    return (
        f"{_COOKIE}={record.session_id}; Max-Age={max_age}; Path=/; Secure; HttpOnly; SameSite=Lax"
    )


def clear_customer_session_cookie() -> str:
    """Expire the exact same host-only cookie during a server-owned logout."""
    return (
        f"{_COOKIE}=; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; "
        "Path=/; Secure; HttpOnly; SameSite=Lax"
    )


def issue_customer_csrf(
    token: str,
    *,
    store: CustomerSessionStore,
    policy: CustomerBrowserPolicy,
    secret: bytes,
    now: datetime | None = None,
) -> str:
    """Return a session-bound synchronizer proof only after server-side lookup.

    The BFF must emit this token through a same-origin, non-cacheable endpoint
    or HTML response. The value is not a cookie, bearer session, or OAuth token.
    """
    resolve_customer_session(token, store=store, now=now)
    return _csrf_digest(token, policy=policy, secret=secret)


def authorize_customer_mutation(
    token: str,
    *,
    store: CustomerSessionStore,
    policy: CustomerBrowserPolicy,
    secret: bytes,
    method: str,
    request_origin: str | None,
    csrf_header: str | None,
    fetch_site: str | None = None,
    now: datetime | None = None,
) -> CustomerSession:
    """Verify a live customer session, exact origin and HMAC before unsafe work.

    This returns customer identity only; downstream match access is resolved by
    separate server-side entitlements. Never use for producer approvals.
    """
    if method not in _UNSAFE_METHODS:
        raise PermissionError("Customer mutation must use an explicit unsafe method")
    if request_origin != policy.public_origin:
        raise PermissionError("Customer mutation origin is not trusted")
    if fetch_site is not None and fetch_site != "same-origin":
        raise PermissionError("Customer mutation fetch origin is not trusted")
    if (
        not isinstance(csrf_header, str)
        or len(csrf_header) != 64
        or any(char not in "0123456789abcdef" for char in csrf_header)
    ):
        raise PermissionError("Missing or invalid customer CSRF proof")
    record = resolve_customer_session(token, store=store, now=now)
    expected = _csrf_digest(token, policy=policy, secret=secret)
    if not hmac.compare_digest(csrf_header, expected):
        raise PermissionError("Customer CSRF proof does not match this session")
    return record
