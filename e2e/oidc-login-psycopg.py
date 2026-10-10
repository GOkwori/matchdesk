"""Disposable real PostgreSQL acceptance for encrypted, one-time OIDC state."""

import hashlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg

from matchdesk.domain.oidc_login import PendingOidcLogin
from matchdesk.domain.postgres_oidc_login_attempts import PostgresOidcLoginAttemptStore
from matchdesk.domain.psycopg_producer_driver import producer_connection_factory

KEY = b"o" * 32  # CI-only symmetric key; production keys belong in managed secrets.
RESTART = hashlib.sha256(b"fixed CI restart fixture").hexdigest()


def dsn() -> str:
    """Use only a short-lived role in the pre-existing disposable CI database."""
    if os.environ.get("CI") != "true" or not os.environ.get("PGPASSWORD"):
        raise RuntimeError("OIDC real DB qualification requires disposable CI")
    return "host=postgres dbname=matchdesk user=matchdesk_oidc_ci sslmode=prefer"


def store() -> PostgresOidcLoginAttemptStore:
    """Allocate a fresh real Psycopg connection for every store operation."""
    return PostgresOidcLoginAttemptStore(
        producer_connection_factory(conninfo=dsn()), encryption_key=KEY
    )


def fixture(label: bytes, *, now: datetime, expiry: datetime) -> PendingOidcLogin:
    """Construct synthetic state independent of live identity providers."""
    return PendingOidcLogin(
        state_hash=hashlib.sha256(label).hexdigest(),
        binding_hash=hashlib.sha256(b"test browser binding").hexdigest(),
        issuer="https://ci.ciamlogin.com/tenant/v2.0",
        client_id="ci-client",
        redirect_uri="https://matchdesk.example/api/customer/oidc/callback",
        issued_at=now,
        expires_at=expiry,
        nonce="A" * 43,
        code_verifier="B" * 43,
    )


def inspect() -> list[tuple[object, ...]]:
    """Inspect committed rows using only the restricted application role."""
    with psycopg.connect(dsn(), autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT secret_iv, secret_ciphertext, consumed_at "
                "FROM matchdesk_oidc_login_attempts ORDER BY state_hash"
            )
            rows = list(cursor.fetchall())
            for privilege, expected in (
                ("SELECT", True), ("INSERT", True), ("UPDATE", True),
                ("DELETE", False), ("TRUNCATE", False),
            ):
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, %s)",
                    ("matchdesk_oidc_login_attempts", privilege),
                )
                assert cursor.fetchone() == (expected,)
            for table in ("matchdesk_producer_cases", "matchdesk_customer_sessions"):
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, 'SELECT')", (table,)
                )
                assert cursor.fetchone() == (False,)
            cursor.execute(
                "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
            )
            assert cursor.fetchone() == (False,)
            return rows


def initial() -> None:
    """Verify CAS, concurrent replay denial, expiry, and encrypted storage."""
    now = datetime.now(timezone.utc)
    entry = fixture(b"concurrent CI OIDC", now=now, expiry=now + timedelta(minutes=4))
    assert store().create(entry)
    assert not store().create(entry)
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = list(pool.map(lambda _: store().consume(entry.state_hash), range(2)))
    assert [x for x in attempts if x is not None] == [entry]
    assert store().consume(entry.state_hash) is None
    expired = fixture(
        b"expired CI OIDC",
        now=now - timedelta(minutes=6),
        expiry=now - timedelta(minutes=2),
    )
    assert store().create(expired)
    assert store().consume(expired.state_hash) is None
    assert store().consume(hashlib.sha256(b"unknown").hexdigest()) is None
    restart = fixture(b"fixed CI restart fixture", now=now, expiry=now + timedelta(minutes=4))
    assert restart.state_hash == RESTART
    assert store().create(restart)
    rows = inspect()
    assert len(rows) == 3
    assert all(len(row[0]) == 12 and len(row[1]) == 103 for row in rows)
    assert all(b"A" * 43 not in row[1] and b"B" * 43 not in row[1] for row in rows)
    assert sum(row[2] is not None for row in rows) == 1
    print("MATCHDESK_OIDC_REAL_POSTGRES_INITIAL_PASS")


def after_restart() -> None:
    """Prove unconsumed state survives restart and is still single-use."""
    restored = store().consume(RESTART)
    assert restored is not None and restored.code_verifier == "B" * 43
    assert restored.nonce == "A" * 43
    assert store().consume(RESTART) is None
    rows = inspect()
    assert len(rows) == 3
    assert sum(row[2] is not None for row in rows) == 2
    print("MATCHDESK_OIDC_REAL_POSTGRES_RESTART_PASS")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("initial", "after-restart"):
        raise RuntimeError("Supply initial or after-restart")
    initial() if sys.argv[1] == "initial" else after_restart()
