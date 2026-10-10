"""Unit tests for encrypted one-time PostgreSQL OIDC state storage."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from matchdesk.domain.oidc_login import PendingOidcLogin
from matchdesk.domain.postgres_oidc_login_attempts import (
    PostgresOidcLoginAttemptStore,
    _associated_data,
    _decode,
    _state_hash,
)

NOW = datetime.now(timezone.utc)
KEY = b"k" * 32


class FakeConnection:
    """Provide one controlled DB transaction and query capture."""

    def __init__(self) -> None:
        """Track transaction calls and connection cleanup."""
        self.cursor_obj = MagicMock()
        self.transaction_obj = MagicMock()
        self.closed = False

    def transaction(self):
        """Provide a transaction context for the host-owned adapter."""
        return self.transaction_obj

    def cursor(self):
        """Provide a controlled cursor context."""
        manager = MagicMock()
        manager.__enter__.return_value = self.cursor_obj
        return manager

    def close(self) -> None:
        """Detect connection leaks on success or error."""
        self.closed = True


def attempt() -> PendingOidcLogin:
    """Create a synthetic, five-minute OIDC transaction."""
    return PendingOidcLogin(
        state_hash=hashlib.sha256(b"state").hexdigest(),
        binding_hash=hashlib.sha256(b"binding").hexdigest(),
        issuer="https://tenant.ciamlogin.com/tenant/v2.0",
        client_id="test-client",
        redirect_uri="https://matchdesk.example/api/customer/oidc/callback",
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        nonce=secrets.token_urlsafe(32),
        code_verifier=secrets.token_urlsafe(32),
    )


def encrypted_row(a: PendingOidcLogin):
    """Capture the exact production encryption output without persisting a secret."""
    conn = FakeConnection()
    conn.cursor_obj.fetchone.return_value = (a.state_hash,)
    assert PostgresOidcLoginAttemptStore(lambda: conn, encryption_key=KEY).create(a)
    params = conn.cursor_obj.execute.call_args.args[1]
    return conn, (a.state_hash, a.binding_hash, a.issuer, a.client_id,
                  a.redirect_uri, a.issued_at, a.expires_at, params[7], params[8])


def test_encrypted_create_and_consume() -> None:
    """Only encrypted PKCE/nonce are persisted, then claimed through conditional UPDATE."""
    a = attempt()
    conn, row = encrypted_row(a)
    assert conn.closed
    assert len(row[7]) == 12 and len(row[8]) == 103
    assert a.nonce.encode() not in row[8]
    assert a.code_verifier.encode() not in row[8]
    assert a.nonce not in repr(conn.cursor_obj.execute.call_args)
    reader = FakeConnection()
    reader.cursor_obj.fetchone.side_effect = [row, None]
    store = PostgresOidcLoginAttemptStore(lambda: reader, encryption_key=KEY)
    assert store.consume(a.state_hash) == a
    assert store.consume(a.state_hash) is None
    sql = reader.cursor_obj.execute.call_args_list[0].args[0]
    assert "consumed_at IS NULL" in sql
    assert "expires_at > clock_timestamp()" in sql
    assert "issued_at <= clock_timestamp()" in sql
    assert reader.closed


@pytest.mark.parametrize("bad", [None, "", "A" * 64, "z" * 64, "a" * 63])
def test_invalid_state_hash_fails_before_connection(bad) -> None:
    """Reject malformed browser state without issuing any SQL."""
    with pytest.raises(ValueError):
        _state_hash(bad)
    conn = FakeConnection()
    with pytest.raises(ValueError):
        PostgresOidcLoginAttemptStore(lambda: conn, encryption_key=KEY).consume(bad)
    assert not conn.cursor_obj.execute.called


@pytest.mark.parametrize("key", [None, "", b"", b"k" * 31, b"k" * 33])
def test_secret_key_must_have_256_bits(key) -> None:
    """Reject provider or browser-supplied encryption material."""
    with pytest.raises(ValueError, match="256-bit"):
        PostgresOidcLoginAttemptStore(lambda: FakeConnection(), encryption_key=key)


def test_duplicate_state_create_is_denied() -> None:
    """An existing state tombstone prevents reserve-again."""
    conn = FakeConnection()
    conn.cursor_obj.fetchone.return_value = None
    assert not PostgresOidcLoginAttemptStore(lambda: conn, encryption_key=KEY).create(
        attempt()
    )
    assert conn.closed


@pytest.mark.parametrize(
    "column,replacement",
    [
        (0, "b" * 64), (1, "b" * 64), (2, "evil-issuer"),
        (3, "other-client"), (4, "https://evil.example"),
        (5, NOW - timedelta(seconds=1)),
        (6, NOW + timedelta(seconds=1)),
        (7, b"x" * 12), (8, b"x" * 103),
        (0, None), (1, None), (2, None), (3, None), (4, None),
        (5, "bad-date"), (6, "bad-date"),
        (5, NOW.replace(tzinfo=None)),
        (6, NOW.replace(tzinfo=None)),
        (7, b"invalid"), (8, b"invalid"),
    ],
)
def test_changed_stored_columns_cannot_reveal_pkce(column, replacement) -> None:
    """Any modification to encrypted metadata or types fails closed."""
    a = attempt()
    _, row = encrypted_row(a)
    changed = list(row)
    changed[column] = replacement
    with pytest.raises(PermissionError):
        _decode(a.state_hash, tuple(changed), encryption_key=KEY)


def test_missing_or_bad_row_never_authenticates() -> None:
    """Unknown state and malformed adapter rows fail closed."""
    with pytest.raises(PermissionError):
        _decode("a" * 64, ("bad",), encryption_key=KEY)
    conn = FakeConnection()
    conn.cursor_obj.fetchone.return_value = None
    assert PostgresOidcLoginAttemptStore(
        lambda: conn, encryption_key=KEY
    ).consume("a" * 64) is None


def test_wrong_key_and_authenticated_bad_payload_fail_closed() -> None:
    """Key rotation and corrupt authenticated payload do not issue a code exchange."""
    a = attempt()
    _, row = encrypted_row(a)
    with pytest.raises(PermissionError):
        _decode(a.state_hash, row, encryption_key=b"z" * 32)
    nonce = b"not-valid"
    iv = b"y" * 12
    cipher = AESGCM(KEY).encrypt(iv, nonce, _associated_data(*row[:7]))
    with pytest.raises(PermissionError):
        _decode(a.state_hash, (*row[:7], iv, cipher), encryption_key=KEY)


def test_storage_failure_closes_connection() -> None:
    """Transactions must roll back if the database raises an error."""
    conn = FakeConnection()
    conn.cursor_obj.execute.side_effect = RuntimeError("database offline")
    with pytest.raises(RuntimeError, match="database offline"):
        PostgresOidcLoginAttemptStore(
            lambda: conn, encryption_key=KEY
        ).create(attempt())
    assert conn.closed


def test_invalid_host_attempt_does_not_reach_database() -> None:
    """A caller cannot insert a fake attempt with arbitrary attributes."""
    conn = FakeConnection()
    with pytest.raises(ValueError):
        PostgresOidcLoginAttemptStore(
            lambda: conn, encryption_key=KEY
        ).create("untrusted")
    assert not conn.cursor_obj.execute.called
