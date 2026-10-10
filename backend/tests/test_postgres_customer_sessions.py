"""Unit tests for hashed PostgreSQL customer-session transactions and rotation."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from matchdesk.domain.customer_identity import CustomerIdentityKey
from matchdesk.domain.customer_sessions import new_customer_session
from matchdesk.domain.postgres_customer_sessions import (
    PostgresCustomerSessionStore,
    _decode,
    _token_hash,
)

NOW = datetime.now(timezone.utc)
IDENTITY = CustomerIdentityKey(
    issuer="https://example.ciamlogin.com/tenant/v2.0",
    tenant_id="tenant",
    subject="customer-1",
)


class FakeConnection:
    """Minimal transactional connection that records SQL and simulates rollback."""

    def __init__(self) -> None:
        """Create an isolated cursor and track whether the connection closes."""
        self.cursor_obj = MagicMock()
        self.transaction_obj = MagicMock()
        self.closed = False

    def transaction(self):
        """Return the database transaction context."""
        return self.transaction_obj

    def cursor(self):
        """Return a context manager with the same fake cursor."""
        manager = MagicMock()
        manager.__enter__.return_value = self.cursor_obj
        return manager

    def close(self) -> None:
        """Track cleanup on success and failure."""
        self.closed = True


def record():
    """Create one synthetic fresh customer session."""
    return new_customer_session(identity=IDENTITY, account_id="customer-1", now=NOW)


def test_session_secret_hash_is_not_raw_bearer() -> None:
    """Stored keys must be cryptographic hashes, not recoverable bearer strings."""
    value = record().session_id
    digest = _token_hash(value)
    assert len(digest) == 64
    assert digest != value
    assert _token_hash(value) == digest


@pytest.mark.parametrize("bad", ["", "A" * 64, "z" * 64, "a" * 63, None])
def test_bad_token_cannot_reach_database(bad) -> None:
    """Malformed input must fail before a connection is opened."""
    with pytest.raises(ValueError):
        _token_hash(bad)


def test_create_and_load_use_digest_only() -> None:
    """Session tokens must never occur in SQL parameters or stored row values."""
    connection = FakeConnection()
    session = record()
    connection.cursor_obj.fetchone.side_effect = [
        ("created",),
        (
            session.identity.issuer,
            session.identity.tenant_id,
            session.identity.subject,
            session.account_id,
            "customer",
            session.created_at,
            session.expires_at,
            session.last_seen_at,
            False,
        ),
    ]
    store = PostgresCustomerSessionStore(lambda: connection)
    assert store.create(session)
    assert store.load(session.session_id) == session
    executed = connection.cursor_obj.execute.call_args_list
    assert len(executed) == 2
    for call in executed:
        assert session.session_id not in str(call.args)
    assert connection.closed


def test_revocation_is_idempotent() -> None:
    """Repeated logout and unknown hashes cannot recreate an active session."""
    connection = FakeConnection()
    connection.cursor_obj.fetchone.side_effect = [("revoked",), None]
    store = PostgresCustomerSessionStore(lambda: connection)
    token = record().session_id
    assert store.revoke(token)
    assert not store.revoke(token)
    assert connection.closed


def test_touch_rejects_naive_clock_and_uses_expiry_predicate() -> None:
    """Idle refresh requires a trusted clock and conditional active-row update."""
    connection = FakeConnection()
    store = PostgresCustomerSessionStore(lambda: connection)
    token = record().session_id
    with pytest.raises(ValueError):
        store.touch(token, now=NOW.replace(tzinfo=None))
    assert not connection.cursor_obj.execute.called
    connection.cursor_obj.fetchone.return_value = ("touched",)
    assert store.touch(token, now=NOW)
    sql = connection.cursor_obj.execute.call_args.args[0]
    assert "revoked = FALSE" in sql
    assert "expires_at >" in sql


def test_rotation_missing_or_expired_predecessor_returns_none() -> None:
    """A missing or expired bearer may never be rotated into a fresh session."""
    connection = FakeConnection()
    store = PostgresCustomerSessionStore(lambda: connection)
    session = record()
    connection.cursor_obj.fetchone.return_value = None
    assert store.rotate(session.session_id, now=NOW) is None
    connection.cursor_obj.fetchone.return_value = (
        session.identity.issuer,
        session.identity.tenant_id,
        session.identity.subject,
        session.account_id,
        "customer",
        session.created_at,
        session.expires_at,
        session.last_seen_at,
        True,
    )
    assert store.rotate(session.session_id, now=NOW) is None


def test_rotation_replaces_token_without_extending_absolute_expiry() -> None:
    """Successful CAS rotation invalidates predecessor in the same transaction."""
    connection = FakeConnection()
    session = record()
    connection.cursor_obj.fetchone.side_effect = [
        (
            session.identity.issuer,
            session.identity.tenant_id,
            session.identity.subject,
            session.account_id,
            "customer",
            session.created_at,
            session.expires_at,
            session.last_seen_at,
            False,
        ),
        ("revoked",),
        ("created",),
    ]
    updated = PostgresCustomerSessionStore(lambda: connection).rotate(
        session.session_id, now=NOW + timedelta(seconds=1)
    )
    assert updated is not None
    assert updated.session_id != session.session_id
    assert updated.expires_at == session.expires_at
    assert updated.identity == session.identity
    sql_calls = connection.cursor_obj.execute.call_args_list
    assert len(sql_calls) == 3
    assert "FOR UPDATE" in sql_calls[0].args[0]
    assert "revoked = TRUE" in sql_calls[1].args[0]


def test_rotation_failed_insert_raises_for_transaction_rollback() -> None:
    """A successor collision cannot silently commit predecessor revocation."""
    connection = FakeConnection()
    session = record()
    connection.cursor_obj.fetchone.side_effect = [
        (
            session.identity.issuer,
            session.identity.tenant_id,
            session.identity.subject,
            session.account_id,
            "customer",
            session.created_at,
            session.expires_at,
            session.last_seen_at,
            False,
        ),
        ("revoked",),
        None,
    ]
    store = PostgresCustomerSessionStore(lambda: connection)
    with pytest.raises(RuntimeError, match="collision"):
        store.rotate(session.session_id, now=NOW + timedelta(seconds=1))
    assert connection.closed


def test_invalid_stored_row_fails_closed() -> None:
    """Malformed stored session snapshots must not turn into valid identities."""
    with pytest.raises(ValueError):
        _decode("a" * 64, ("bad",))
