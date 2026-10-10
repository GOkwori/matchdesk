"""PostgreSQL customer sessions: hashed tokens, atomic revocation and rotation.

This is a host-owned persistence adapter, not a login or publication endpoint.
Raw 256-bit session secrets exist only in a caller's memory/cookie; the database
stores their SHA-256 digest. The host remains responsible for identity proof,
protected cookies, CSRF, current account membership and session creation.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Literal, cast

from matchdesk.domain.customer_identity import CustomerIdentityKey
from matchdesk.domain.customer_sessions import (
    CustomerSession,
    new_customer_session,
    resolve_customer_session,
)
from matchdesk.domain.postgres_producer_store import DbConnection, DbCursor

_LOAD = """
SELECT issuer, tenant_id, subject, account_id, realm,
       created_at, expires_at, last_seen_at, revoked
FROM matchdesk_customer_sessions
WHERE token_hash = %s
"""
_LOCK = _LOAD + " FOR UPDATE"
_CREATE = """
INSERT INTO matchdesk_customer_sessions
(token_hash, issuer, tenant_id, subject, account_id, realm,
 created_at, expires_at, last_seen_at, revoked)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING RETURNING token_hash
"""
_REVOKE = """
UPDATE matchdesk_customer_sessions SET revoked = TRUE
WHERE token_hash = %s AND realm = 'customer' AND revoked = FALSE
RETURNING token_hash
"""
_TOUCH = """
UPDATE matchdesk_customer_sessions SET last_seen_at = %s
WHERE token_hash = %s AND realm = 'customer' AND revoked = FALSE
  AND created_at <= %s AND expires_at > %s
  AND last_seen_at <= %s AND last_seen_at >= %s
RETURNING token_hash
"""


def _token_hash(token: str) -> str:
    """Hash only a correctly formed random bearer; never persist or log the bearer."""
    if (
        not isinstance(token, str)
        or len(token) != 64
        or any(char not in "0123456789abcdef" for char in token)
    ):
        raise ValueError("Customer session secret must be 256-bit lowercase hex")
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _decode(token: str, row: tuple[object, ...]) -> CustomerSession:
    """Rebuild a strictly checked session without retrieving the raw stored secret."""
    if not isinstance(row, tuple) or len(row) != 9:
        raise ValueError("Invalid stored customer session")
    issuer, tenant, subject, account, realm, created, expires, seen, revoked = row
    if (
        not isinstance(issuer, str)
        or not isinstance(tenant, str)
        or not isinstance(subject, str)
        or not isinstance(account, str)
        or realm != "customer"
        or not isinstance(created, datetime)
        or not isinstance(expires, datetime)
        or not isinstance(seen, datetime)
        or type(revoked) is not bool
    ):
        raise ValueError("Invalid stored customer identity or session")
    return CustomerSession(
        session_id=token,
        identity=CustomerIdentityKey(issuer=issuer, tenant_id=tenant, subject=subject),
        account_id=account,
        realm=cast("Literal['customer', 'workforce']", realm),
        created_at=created,
        expires_at=expires,
        last_seen_at=seen,
        revoked=revoked,
    )


class _Loaded:
    """Return one locked server-owned snapshot to the existing session validator."""

    def __init__(self, record: CustomerSession) -> None:
        """Hold the snapshot inside the caller's database transaction."""
        self.record = record

    def load(self, opaque_session_id: str) -> CustomerSession | None:
        """Leave matching, expiry and revocation validation to the domain boundary."""
        return self.record if self.record.session_id == opaque_session_id else None


class PostgresCustomerSessionStore:
    """Durable customer-only session store with no raw token column.

    All mutation operations create their own short-lived transaction and close
    connections even after rollback. This is not production tenant RLS, a
    browser cookie issuer or a substitute for BFF authentication.
    """

    def __init__(self, connection_factory: Callable[[], DbConnection]) -> None:
        """Accept the already pinned, separately protected Psycopg connection factory."""
        self._connect = connection_factory

    @staticmethod
    def _insert(cursor: DbCursor, record: CustomerSession) -> bool:
        """Insert one validated, initially active session by digest, never secret."""
        record.__post_init__()
        if record.revoked or record.last_seen_at != record.created_at:
            raise ValueError("Only a fresh, unrevoked customer session can be created")
        cursor.execute(
            _CREATE,
            (
                _token_hash(record.session_id),
                record.identity.issuer,
                record.identity.tenant_id,
                record.identity.subject,
                record.account_id,
                record.realm,
                record.created_at,
                record.expires_at,
                record.last_seen_at,
                record.revoked,
            ),
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _read(cursor: DbCursor, token: str, *, locked: bool = False) -> CustomerSession | None:
        """Select by digest, optionally locking the predecessor against rotation races."""
        cursor.execute(_LOCK if locked else _LOAD, (_token_hash(token),))
        row = cursor.fetchone()
        return None if row is None else _decode(token, row)

    def create(self, record: CustomerSession) -> bool:
        """Atomically create a customer record without persisting its bearer token."""
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    return self._insert(cursor, record)
        finally:
            connection.close()

    def load(self, opaque_session_id: str) -> CustomerSession | None:
        """Return a server-owned record for domain expiry and revocation enforcement."""
        _token_hash(opaque_session_id)
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    return self._read(cursor, opaque_session_id)
        finally:
            connection.close()

    def revoke(self, opaque_session_id: str) -> bool:
        """Persist immediate logout/revocation; repeated or absent tokens return False."""
        digest = _token_hash(opaque_session_id)
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(_REVOKE, (digest,))
                    return cursor.fetchone() is not None
        finally:
            connection.close()

    def touch(self, opaque_session_id: str, *, now: datetime | None = None) -> bool:
        """Refresh idle activity only for an active session, without extending expiry."""
        digest = _token_hash(opaque_session_id)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("Customer session clock must be timezone-aware")
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        _TOUCH,
                        (
                            current,
                            digest,
                            current,
                            current,
                            current,
                            current - timedelta(minutes=30),
                        ),
                    )
                    return cursor.fetchone() is not None
        finally:
            connection.close()

    def rotate(
        self, opaque_session_id: str, *, now: datetime | None = None
    ) -> CustomerSession | None:
        """Invalidate exactly one old token and create its successor atomically.

        SELECT FOR UPDATE serialises concurrent rotations/revocations. Successor
        retains the *original absolute expiry*, so repeated rotation cannot
        extend an authenticated session. An insertion failure rolls back the
        predecessor revocation in the same transaction.
        """
        _token_hash(opaque_session_id)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("Customer session clock must be timezone-aware")
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    original = self._read(cursor, opaque_session_id, locked=True)
                    if original is None:
                        return None
                    try:
                        resolve_customer_session(
                            opaque_session_id, store=_Loaded(original), now=current
                        )
                    except PermissionError:
                        return None
                    successor = new_customer_session(
                        identity=original.identity,
                        account_id=original.account_id,
                        now=current,
                        ttl=original.expires_at - current,
                    )
                    cursor.execute(_REVOKE, (_token_hash(opaque_session_id),))
                    if cursor.fetchone() is None:
                        return None
                    if not self._insert(cursor, successor):
                        raise RuntimeError("Customer session rotation collision")
                    return successor
        finally:
            connection.close()
