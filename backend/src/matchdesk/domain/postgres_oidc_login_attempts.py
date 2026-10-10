"""PostgreSQL OIDC state: atomic replay defense and encrypted PKCE secrets.

The caller owns credentials and a distinct host-held AES-256-GCM key. No
browser session, token exchange, HTTP handler, or producer permission is
created here. State and browser-binding hashes are never stored as raw secrets.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from datetime import datetime, timezone

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from matchdesk.domain.oidc_login import PendingOidcLogin
from matchdesk.domain.postgres_producer_store import DbConnection, DbCursor

_INSERT = """
INSERT INTO matchdesk_oidc_login_attempts (
    state_hash, binding_hash, issuer, client_id, redirect_uri, issued_at,
    expires_at, secret_iv, secret_ciphertext
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING RETURNING state_hash
"""
_CONSUME = """
UPDATE matchdesk_oidc_login_attempts
SET consumed_at = clock_timestamp()
WHERE state_hash = %s
  AND consumed_at IS NULL
  AND issued_at <= clock_timestamp()
  AND expires_at > clock_timestamp()
RETURNING state_hash, binding_hash, issuer, client_id, redirect_uri,
          issued_at, expires_at, secret_iv, secret_ciphertext
"""


def _state_hash(value: str) -> str:
    """Validate SHA-256 state keys before accessing a connection."""
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError("OIDC state key must be a canonical SHA-256 digest")
    return value


def _associated_data(
    state_hash: str,
    binding_hash: str,
    issuer: str,
    client_id: str,
    redirect_uri: str,
    issued_at: datetime,
    expires_at: datetime,
) -> bytes:
    """Authenticate the immutable state envelope together with its secrets."""
    values = (
        state_hash,
        binding_hash,
        issuer,
        client_id,
        redirect_uri,
        issued_at.astimezone(timezone.utc).isoformat(),
        expires_at.astimezone(timezone.utc).isoformat(),
    )
    return json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _decode(
    expected_hash: str,
    row: tuple[object, ...],
    *,
    encryption_key: bytes,
) -> PendingOidcLogin:
    """Reject tampered rows before yielding server-only nonce and PKCE verifier."""
    if not isinstance(row, tuple) or len(row) != 9:
        raise PermissionError("OIDC state record is invalid")
    state_hash, binding_hash, issuer, client_id, redirect_uri, issued, expires, iv, encrypted = row
    if (
        not isinstance(state_hash, str)
        or state_hash != expected_hash
        or not isinstance(binding_hash, str)
        or not isinstance(issuer, str)
        or not isinstance(client_id, str)
        or not isinstance(redirect_uri, str)
        or not isinstance(issued, datetime)
        or not isinstance(expires, datetime)
        or issued.tzinfo is None
        or issued.utcoffset() is None
        or expires.tzinfo is None
        or expires.utcoffset() is None
        or not isinstance(iv, bytes)
        or len(iv) != 12
        or not isinstance(encrypted, bytes)
        or len(encrypted) != 103
    ):
        raise PermissionError("OIDC state record is untrusted")
    try:
        aad = _associated_data(
            state_hash, binding_hash, issuer, client_id, redirect_uri, issued, expires
        )
        plaintext = AESGCM(encryption_key).decrypt(iv, encrypted, aad)
        nonce, verifier = plaintext.decode("ascii").split(":")
        return PendingOidcLogin(
            state_hash=state_hash,
            binding_hash=binding_hash,
            issuer=issuer,
            client_id=client_id,
            redirect_uri=redirect_uri,
            issued_at=issued,
            expires_at=expires,
            nonce=nonce,
            code_verifier=verifier,
        )
    except (InvalidTag, ValueError, UnicodeError) as exc:
        raise PermissionError("OIDC state encryption or contents are invalid") from exc


class PostgresOidcLoginAttemptStore:
    """Isolated one-time login state under a restricted PostgreSQL role.

    Each operation uses a short transaction and closes the connection after
    success or rollback. A separate approved maintenance role may eventually
    prune expired/consumed tombstones; this role has no DELETE or DDL authority.
    """

    def __init__(
        self, connection_factory: Callable[[], DbConnection], *, encryption_key: bytes
    ) -> None:
        """Require exactly 256 bits of key material supplied by the trusted host."""
        if type(encryption_key) is not bytes or len(encryption_key) != 32:
            raise ValueError("OIDC state encryption requires a 256-bit host key")
        self._connect = connection_factory
        self._key = encryption_key

    def create(self, attempt: PendingOidcLogin) -> bool:
        """Insert encrypted secrets by immutable state digest; reject collisions."""
        if not isinstance(attempt, PendingOidcLogin):
            raise ValueError("OIDC login attempt must be server-owned")
        attempt.__post_init__()
        state_hash = _state_hash(attempt.state_hash)
        aad = _associated_data(
            state_hash,
            attempt.binding_hash,
            attempt.issuer,
            attempt.client_id,
            attempt.redirect_uri,
            attempt.issued_at,
            attempt.expires_at,
        )
        iv = secrets.token_bytes(12)
        # A validated nonce and PKCE verifier are each 43 base64url characters.
        secret = f"{attempt.nonce}:{attempt.code_verifier}".encode("ascii")
        encrypted = AESGCM(self._key).encrypt(iv, secret, aad)
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        _INSERT,
                        (
                            state_hash,
                            attempt.binding_hash,
                            attempt.issuer,
                            attempt.client_id,
                            attempt.redirect_uri,
                            attempt.issued_at,
                            attempt.expires_at,
                            iv,
                            encrypted,
                        ),
                    )
                    return cursor.fetchone() is not None
        finally:
            connection.close()

    def consume(self, state_hash: str) -> PendingOidcLogin | None:
        """Claim once by database-clock conditional UPDATE, even under races.

        Consumed and expired state rows remain tombstones. UPDATE ... RETURNING
        returns only the winning claim; a replay receives None.
        """
        digest = _state_hash(state_hash)
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(_CONSUME, (digest,))
                    row = cursor.fetchone()
                    return None if row is None else _decode(digest, row, encryption_key=self._key)
        finally:
            connection.close()
