"""Offline OIDC code-flow initiation and callback trust for customer External ID.

The customer browser delegates social sign-in to a *single, pinned* Entra
External ID broker. This module neither contacts the broker nor redeems a code,
validates an ID token, creates a customer session, or authorizes a producer.
Only the trusted BFF may store, read, and expire these ephemeral login records.

RFC 9700: PKCE S256, exact redirects, browser-bound state, issuer mix-up guard.
RFC 9207: require the expected authorization response issuer.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Mapping, Protocol
from urllib.parse import urlencode, urlsplit

from matchdesk.domain.browser_session_security import CustomerBrowserPolicy
from matchdesk.domain.customer_identity import CustomerBrokerPolicy

_LOGIN_COOKIE = "__Host-matchdesk_oidc"


def _secret_digest(secret: str) -> str:
    """Return a hash for keyed lookup or constant-time browser binding checks."""
    return hashlib.sha256(secret.encode("ascii")).hexdigest()


def _random_value(value: object) -> bool:
    """Require exactly 256 bits encoded as unpadded base64url from the BFF."""
    return (
        isinstance(value, str)
        and len(value) == 43
        and all(char.isascii() and (char.isalnum() or char in "_-") for char in value)
    )


def _clock(now: datetime | None) -> datetime:
    """Use an aware wall clock; never accept naive or non-datetime overrides."""
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("OIDC login clock must be timezone-aware")
    return current


@dataclass(frozen=True)
class CustomerOidcPolicy:
    """Explicitly pin the customer broker, client, callback and metadata endpoints."""

    broker: CustomerBrokerPolicy
    client_id: str
    public_origin: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    scopes: tuple[str, ...] = ("openid",)
    pending_seconds: int = 300

    def __post_init__(self) -> None:
        """Reject untrusted issuer families, open redirects and broad OAuth grants."""
        if not isinstance(self.broker, CustomerBrokerPolicy):
            raise ValueError("OIDC requires trusted External ID broker policy")
        self.broker.__post_init__()
        if not isinstance(self.public_origin, str):
            raise ValueError("OIDC callback requires a reviewed HTTPS origin")
        CustomerBrowserPolicy(public_origin=self.public_origin)
        issuer = urlsplit(self.broker.issuer)
        prefix = f"https://{issuer.netloc}/{self.broker.tenant_id}"
        if (
            not isinstance(self.client_id, str)
            or self.client_id not in self.broker.client_ids
            or self.authorization_endpoint != f"{prefix}/oauth2/v2.0/authorize"
            or self.token_endpoint != f"{prefix}/oauth2/v2.0/token"
            or self.jwks_uri != f"{prefix}/discovery/v2.0/keys"
            or not isinstance(self.scopes, tuple)
            or "openid" not in self.scopes
            or len(set(self.scopes)) != len(self.scopes)
            or len(self.scopes) > 8
            or any(
                not isinstance(scope, str)
                or not 1 <= len(scope) <= 160
                or any(char.isspace() or not char.isascii() for char in scope)
                or "*" in scope
                for scope in self.scopes
            )
            or type(self.pending_seconds) is not int
            or not 30 <= self.pending_seconds <= 300
        ):
            raise ValueError("OIDC requires exact broker endpoints and delegated scopes")

    @property
    def redirect_uri(self) -> str:
        """A fixed host-owned callback; never derived from returnUrl query input."""
        return f"{self.public_origin}/api/customer/oidc/callback"


def verify_broker_discovery(
    policy: CustomerOidcPolicy, document: Mapping[str, object]
) -> None:
    """Check already-fetched metadata against host-pinned broker trust.

    Fetching, redirect handling, cache expiry and JWKS rotation require a
    separate reviewed adapter; this function does not make network requests.
    """
    if not isinstance(document, Mapping):
        raise PermissionError("OIDC discovery document is not trusted")
    expected = {
        "issuer": policy.broker.issuer,
        "authorization_endpoint": policy.authorization_endpoint,
        "token_endpoint": policy.token_endpoint,
        "jwks_uri": policy.jwks_uri,
    }
    if any(document.get(key) != value for key, value in expected.items()):
        raise PermissionError("OIDC discovery endpoints differ from host trust")
    pkce = document.get("code_challenge_methods_supported")
    response = document.get("response_types_supported")
    if (
        not isinstance(pkce, (list, tuple))
        or "S256" not in pkce
        or not isinstance(response, (list, tuple))
        or "code" not in response
    ):
        raise PermissionError("OIDC broker does not advertise required code/PKCE support")


@dataclass(frozen=True)
class PendingOidcLogin:
    """Server-owned single-use transaction, including secrets never sent to UI."""

    state_hash: str
    binding_hash: str
    issuer: str
    client_id: str
    redirect_uri: str
    issued_at: datetime
    expires_at: datetime
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)

    def __post_init__(self) -> None:
        """Reject malformed or overlong persisted login transactions."""
        for value in (self.state_hash, self.binding_hash):
            if not isinstance(value, str) or len(value) != 64 or any(
                char not in "0123456789abcdef" for char in value
            ):
                raise ValueError("OIDC transaction requires hashed browser state")
        if (
            not _random_value(self.nonce)
            or not _random_value(self.code_verifier)
            or not isinstance(self.issuer, str)
            or not isinstance(self.client_id, str)
            or not isinstance(self.redirect_uri, str)
        ):
            raise ValueError("OIDC transaction has untrusted secret or identity")
        _clock(self.issued_at)
        _clock(self.expires_at)
        if not timedelta(0) < self.expires_at - self.issued_at <= timedelta(minutes=5):
            raise ValueError("OIDC login lifetime outside bounded policy")


class OidcLoginAttemptStore(Protocol):
    """Host-owned durable, one-time state store; both methods must be atomic."""

    def create(self, attempt: PendingOidcLogin) -> bool:
        """Insert the unique hashed state, refusing collisions or reused attempts."""

    def consume(self, state_hash: str) -> PendingOidcLogin | None:
        """Delete/mark consumed in one transaction; only one caller can win."""


@dataclass(frozen=True)
class OidcBrowserRedirect:
    """Only the browser redirect URL and its independent host-prefixed cookie."""

    authorization_url: str = field(repr=False)
    set_cookie: str = field(repr=False)


@dataclass(frozen=True)
class PendingOidcExchange:
    """Trusted BFF input for a *future* token exchange; not an authenticated user."""

    issuer: str
    client_id: str
    token_endpoint: str
    redirect_uri: str
    authorization_code: str = field(repr=False)
    code_verifier: str = field(repr=False)
    nonce: str = field(repr=False)


def begin_customer_oidc_login(
    *, policy: CustomerOidcPolicy, store: OidcLoginAttemptStore, now: datetime | None = None
) -> OidcBrowserRedirect:
    """Atomically store state, then create a code+PKCE S256 authorization request.

    Only the state, challenge and nonce travel to the broker. The PKCE verifier
    stays in a server-owned record and the independent binding stays in a
    Secure/HttpOnly/SameSite=Lax host-only cookie for the top-level callback.
    """
    current = _clock(now)
    state = secrets.token_urlsafe(32)
    binding = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(32)
    if not all(_random_value(value) for value in (state, binding, nonce, verifier)):
        raise RuntimeError("Secure OIDC random generator returned malformed state")
    attempt = PendingOidcLogin(
        state_hash=_secret_digest(state),
        binding_hash=_secret_digest(binding),
        issuer=policy.broker.issuer,
        client_id=policy.client_id,
        redirect_uri=policy.redirect_uri,
        issued_at=current,
        expires_at=current + timedelta(seconds=policy.pending_seconds),
        nonce=nonce,
        code_verifier=verifier,
    )
    if not store.create(attempt):
        raise PermissionError("OIDC login state could not be reserved")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
    url = policy.authorization_endpoint + "?" + urlencode(
        {
            "response_type": "code",
            "response_mode": "query",
            "client_id": policy.client_id,
            "redirect_uri": policy.redirect_uri,
            "scope": " ".join(policy.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge_method": "S256",
            "code_challenge": challenge.rstrip(b"=").decode("ascii"),
        }
    )
    cookie = (
        f"{_LOGIN_COOKIE}={binding}; Max-Age={policy.pending_seconds}; "
        "Path=/; Secure; HttpOnly; SameSite=Lax"
    )
    return OidcBrowserRedirect(authorization_url=url, set_cookie=cookie)


def finish_customer_oidc_login(
    *,
    policy: CustomerOidcPolicy,
    store: OidcLoginAttemptStore,
    state: str,
    browser_binding: str,
    issuer: str,
    code: str | None,
    error: str | None = None,
    now: datetime | None = None,
) -> PendingOidcExchange:
    """Consume an exact issuer/browser-bound OIDC response once, then stop.

    The host callback must reject duplicate state/code/iss query parameters and
    clear the temporary browser cookie. Return value is strictly a pending code
    exchange. A separate trusted token adapter MUST validate audience, issuer,
    signature, nonce, lifetime and account registration before making a session.
    """
    current = _clock(now)
    if not _random_value(state):
        raise PermissionError("OIDC response state is missing or invalid")
    attempt = store.consume(_secret_digest(state))
    if attempt is None:
        raise PermissionError("OIDC login state is missing or already consumed")
    attempt.__post_init__()
    if (
        not _random_value(browser_binding)
        or not hmac.compare_digest(
            attempt.binding_hash, _secret_digest(browser_binding)
        )
        or attempt.issued_at > current
        or current >= attempt.expires_at
        or attempt.issuer != policy.broker.issuer
        or attempt.client_id != policy.client_id
        or attempt.redirect_uri != policy.redirect_uri
        or issuer != policy.broker.issuer
        or error is not None
        or not isinstance(code, str)
        or not 1 <= len(code) <= 2048
        or any(not "!" <= char <= "~" for char in code)
    ):
        raise PermissionError("OIDC response is not an authorised code exchange")
    return PendingOidcExchange(
        issuer=attempt.issuer,
        client_id=attempt.client_id,
        token_endpoint=policy.token_endpoint,
        redirect_uri=attempt.redirect_uri,
        authorization_code=code,
        code_verifier=attempt.code_verifier,
        nonce=attempt.nonce,
    )


def clear_oidc_login_cookie() -> str:
    """Expire the login-binding cookie following success, denial or cancellation."""
    return (
        f"{_LOGIN_COOKIE}=; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; "
        "Path=/; Secure; HttpOnly; SameSite=Lax"
    )
