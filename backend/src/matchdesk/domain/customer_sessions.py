"""Offline, realm-separated customer session policy for MatchDesk.

A browser supplies only an opaque session identifier. All identity, expiry,
revocation and tenant scope are loaded from a trusted server-owned store.
This module neither issues cookies nor exposes a login or mutation endpoint.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Protocol

from matchdesk.domain.customer_identity import CustomerIdentityKey

Realm = Literal["customer", "workforce"]


@dataclass(frozen=True)
class CustomerSession:
    """Server-owned customer session record without provider access tokens."""

    session_id: str
    identity: CustomerIdentityKey
    account_id: str
    realm: Realm
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    revoked: bool = False

    def __post_init__(self) -> None:
        """Reject malformed or privileged customer session snapshots."""
        if (
            self.realm != "customer"
            or not isinstance(self.session_id, str)
            or len(self.session_id) != 64
            or any(ch not in "0123456789abcdef" for ch in self.session_id)
            or not isinstance(self.account_id, str)
            or not self.account_id.strip()
            or any(
                value.tzinfo is None or value.utcoffset() is None
                for value in (self.created_at, self.expires_at, self.last_seen_at)
            )
            or not self.created_at <= self.last_seen_at <= self.expires_at
            or not timedelta(0) < self.expires_at - self.created_at <= timedelta(hours=8)
        ):
            raise ValueError("Invalid or privileged customer session record")


class CustomerSessionStore(Protocol):
    """Trusted store; its lookup must enforce current revocation and owner scope."""

    def load(self, opaque_session_id: str) -> CustomerSession | None:
        """Read one persisted record; missing sessions are always denied."""


def new_customer_session(
    *,
    identity: CustomerIdentityKey,
    account_id: str,
    now: datetime | None = None,
    ttl: timedelta = timedelta(hours=1),
) -> CustomerSession:
    """Create an unpersisted high-entropy, customer-only session candidate.

    The host must persist it atomically and set a Secure, HttpOnly, SameSite
    cookie with CSRF, rotation, logout and transport controls. Returning this
    record does not activate browser login or issue any role permission.
    """
    current = now or datetime.now(timezone.utc)
    if not timedelta(0) < ttl <= timedelta(hours=8):
        raise ValueError("Customer session lifetime is outside policy")
    return CustomerSession(
        session_id=secrets.token_hex(32),
        identity=identity,
        account_id=account_id,
        realm="customer",
        created_at=current,
        expires_at=current + ttl,
        last_seen_at=current,
    )


def resolve_customer_session(
    opaque_session_id: str, *, store: CustomerSessionStore, now: datetime | None = None
) -> CustomerSession:
    """Fail closed on missing, revoked, stale or privilege-confused sessions."""
    if (
        not isinstance(opaque_session_id, str)
        or len(opaque_session_id) != 64
        or any(ch not in "0123456789abcdef" for ch in opaque_session_id)
    ):
        raise PermissionError("Invalid customer session")
    record = store.load(opaque_session_id)
    if record is None:
        raise PermissionError("Customer session is unavailable")
    try:
        record.__post_init__()
        current = now or datetime.now(timezone.utc)
        if (
            record.session_id != opaque_session_id
            or record.revoked
            or current < record.created_at
            or current >= record.expires_at
            or current - record.last_seen_at > timedelta(minutes=30)
        ):
            raise PermissionError("Customer session is expired or revoked")
    except (ValueError, TypeError) as exc:
        raise PermissionError("Customer session record is untrusted") from exc
    return record
