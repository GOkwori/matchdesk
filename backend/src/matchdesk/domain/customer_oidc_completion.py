"""Offline completion of a consumed External ID login into a customer-only session.

The trusted BFF must first consume browser-bound OIDC state with
finish_customer_oidc_login(). Its separately reviewed code exchanger redeems
the one-use code against the host-pinned token endpoint. This module verifies
the returned broker ID token, requires a registered account, and persists a
customer-only session before returning a host-only cookie.

No network client, HTTP route, provider account linking, producer authority,
or live login activation is implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from matchdesk.domain.browser_session_security import (
    CustomerBrowserPolicy,
    customer_session_cookie,
)
from matchdesk.domain.customer_identity import (
    CustomerAccountDirectory,
    CustomerSigningKeys,
    resolve_customer_account,
)
from matchdesk.domain.customer_sessions import (
    CustomerSession,
    CustomerSessionStore,
    new_customer_session,
    resolve_customer_session,
)
from matchdesk.domain.oidc_id_token import verify_broker_id_token
from matchdesk.domain.oidc_login import CustomerOidcPolicy, PendingOidcExchange


class CustomerCodeExchanger(Protocol):
    """Redeem one consumed code through a separately reviewed, pinned BFF adapter."""

    def redeem(self, *, pending: PendingOidcExchange) -> str:
        """Return the broker's ID token, never a social-provider or API token."""


class CustomerSessionWriter(CustomerSessionStore, Protocol):
    """Persist customer-only sessions and revoke an orphan on post-commit failure."""

    def create(self, record: CustomerSession) -> bool:
        """Insert a new session atomically, refusing collision or storage failure."""

    def revoke(self, opaque_session_id: str) -> bool:
        """Revoke a session before an unsuccessful login can expose its cookie."""


@dataclass(frozen=True)
class CompletedCustomerLogin:
    """A browser response header and expiry; never an identity or privileged grant."""

    set_cookie: str = field(repr=False)
    expires_at: datetime


def _secret(value: object) -> bool:
    """Accept only the BFF's 256-bit unpadded base64url nonce and PKCE verifier."""
    return (
        isinstance(value, str)
        and len(value) == 43
        and all(char.isascii() and (char.isalnum() or char in "_-") for char in value)
    )


def _preflight(
    pending: PendingOidcExchange,
    *,
    policy: CustomerOidcPolicy,
    browser: CustomerBrowserPolicy,
) -> None:
    """Reject forged exchange destinations *before* passing a code to the exchanger."""
    if (
        not isinstance(policy, CustomerOidcPolicy)
        or not isinstance(browser, CustomerBrowserPolicy)
        or not isinstance(pending, PendingOidcExchange)
    ):
        raise ValueError("Customer login requires host-owned OIDC policy and exchange")
    policy.__post_init__()
    browser.__post_init__()
    if browser.public_origin != policy.public_origin:
        raise ValueError("OIDC and session cookie origins must agree")
    if (
        pending.issuer != policy.broker.issuer
        or pending.client_id != policy.client_id
        or pending.token_endpoint != policy.token_endpoint
        or pending.redirect_uri != policy.redirect_uri
        or not _secret(pending.nonce)
        or not _secret(pending.code_verifier)
        or not isinstance(pending.authorization_code, str)
        or not 1 <= len(pending.authorization_code) <= 2048
        or any(not "!" <= char <= "~" for char in pending.authorization_code)
    ):
        raise PermissionError("Customer OIDC exchange is not host-bound")


def _revoke_after_failure(store: CustomerSessionWriter, session_id: str) -> None:
    """Best-effort invalidate an unexposed bearer after an uncertain database write."""
    try:
        store.revoke(session_id)
    except Exception:
        # A store outage cannot make a login successful: no cookie was sent.
        # The random bearer is not disclosed, even when revocation is unavailable.
        pass


def complete_customer_oidc_sign_in(
    *,
    pending: PendingOidcExchange,
    policy: CustomerOidcPolicy,
    browser: CustomerBrowserPolicy,
    exchanger: CustomerCodeExchanger,
    keys: CustomerSigningKeys,
    directory: CustomerAccountDirectory,
    sessions: CustomerSessionWriter,
    now: datetime | None = None,
) -> CompletedCustomerLogin:
    """Require a signed broker identity and existing account before session issuance.

    The caller must supply a *consumed* state from the durable one-use login
    store and must never retry a failed code exchange. A session's only realm
    is customer; producer roles, email and upstream provider identity never
    enter the login result. The existing same-origin /csrf endpoint supplies
    a proof after the browser receives this secure session cookie.
    """
    _preflight(pending, policy=policy, browser=browser)
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Customer login clock must be timezone-aware")

    try:
        id_token = exchanger.redeem(pending=pending)
    except Exception:
        # Avoid surfacing broker URLs, client secrets or HTTP bodies from adapters.
        raise PermissionError("Customer OIDC code exchange denied") from None

    try:
        identity = verify_broker_id_token(
            id_token, pending=pending, policy=policy, keys=keys, now=current
        )
        account_id = resolve_customer_account(identity, directory=directory)
    except Exception:
        # Successful social sign-in cannot create or silently link an account.
        raise PermissionError("Customer OIDC identity or account denied") from None

    candidate = new_customer_session(identity=identity, account_id=account_id, now=current)
    try:
        if sessions.create(candidate) is not True:
            raise PermissionError("Customer session was not persisted")
    except Exception:
        _revoke_after_failure(sessions, candidate.session_id)
        raise PermissionError("Customer session persistence denied") from None

    try:
        # Detect a corrupt or substituted storage row, not merely a valid token.
        stored = resolve_customer_session(candidate.session_id, store=sessions, now=current)
        if stored != candidate:
            raise PermissionError("Persisted customer identity differs from signed identity")
        cookie = customer_session_cookie(
            candidate.session_id, store=sessions, policy=browser, now=current
        )
    except Exception:
        _revoke_after_failure(sessions, candidate.session_id)
        raise PermissionError("Customer session issuance denied") from None

    return CompletedCustomerLogin(set_cookie=cookie, expires_at=candidate.expires_at)
