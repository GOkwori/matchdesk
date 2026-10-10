"""Real Psycopg customer-session acceptance tests in disposable CI PostgreSQL.

The session bearer never goes to database storage or logs. A fixed synthetic
fixture is intentionally used only for restart recovery in an isolated CI
container; production session tokens remain randomly generated.
"""

from __future__ import annotations

import hashlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import psycopg

from matchdesk.domain.customer_identity import CustomerIdentityKey
from matchdesk.domain.customer_sessions import (
    new_customer_session,
    resolve_customer_session,
)
from matchdesk.domain.postgres_customer_sessions import PostgresCustomerSessionStore
from matchdesk.domain.psycopg_producer_driver import producer_connection_factory


TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://matchdesk.ciamlogin.com/{TENANT}/v2.0"
RESTART_TOKEN = "a" * 64  # Deterministic disposable test fixture; not a real bearer.
IDENTITY = CustomerIdentityKey(issuer=ISSUER, tenant_id=TENANT, subject="ci-fan")


def _dsn() -> str:
    """Require the short-lived least-privileged integration identity."""
    if os.environ.get("CI") != "true" or not os.environ.get("PGPASSWORD"):
        raise RuntimeError("Real customer session tests require disposable CI credentials")
    return "host=postgres dbname=matchdesk user=matchdesk_customer_session_ci sslmode=prefer"


def _store() -> PostgresCustomerSessionStore:
    """Use a fresh real Psycopg connection for every store transaction."""
    return PostgresCustomerSessionStore(producer_connection_factory(conninfo=_dsn()))


def _issue(account_id: str, *, now: datetime, ttl: timedelta = timedelta(hours=1)):
    """Create one unpersisted synthetic customer session with a random token."""
    return new_customer_session(
        identity=IDENTITY, account_id=account_id, now=now, ttl=ttl
    )


def _expect_denial(session_id: str, *, now: datetime) -> None:
    """Explicitly qualify the domain's server-side expiry/revocation enforcement."""
    try:
        resolve_customer_session(session_id, store=_store(), now=now)
    except PermissionError:
        return
    raise AssertionError("Revoked, idle, expired or unknown customer token was accepted")


def _count(account_id: str) -> list[tuple[object, object]]:
    """Independently inspect committed session rows through the restricted role."""
    with psycopg.connect(_dsn(), autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT revoked, token_hash FROM matchdesk_customer_sessions "
                "WHERE account_id = %s ORDER BY token_hash",
                (account_id,),
            )
            return list(cursor.fetchall())


def _role_controls() -> None:
    """Prove app credentials cannot delete rows, modify schema or read producer data."""
    with psycopg.connect(_dsn(), autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = current_user"
            )
            assert cursor.fetchone() == (False, False)
            for action, permitted in (
                ("SELECT", True),
                ("INSERT", True),
                ("UPDATE", True),
                ("DELETE", False),
                ("TRUNCATE", False),
            ):
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, %s)",
                    ("matchdesk_customer_sessions", action),
                )
                assert cursor.fetchone() == (permitted,)
            cursor.execute(
                "SELECT has_table_privilege(current_user, "
                "'matchdesk_producer_cases', 'SELECT')"
            )
            assert cursor.fetchone() == (False,)
            cursor.execute(
                "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
            )
            assert cursor.fetchone() == (False,)
            for command in (
                "DELETE FROM matchdesk_customer_sessions WHERE account_id='ci-revoke'",
                "ALTER TABLE matchdesk_customer_sessions ADD COLUMN forbidden text",
                "SET ROLE matchdesk",
            ):
                try:
                    cursor.execute(command)
                except psycopg.errors.InsufficientPrivilege:
                    pass
                else:
                    raise AssertionError("Restricted session role permitted forbidden action")
    print("PASS: customer session role cannot delete, alter, own or read producer cases")


def _assert_hash_only(token: str) -> None:
    """Verify database schema has no raw session column and stores only a digest."""
    with psycopg.connect(_dsn(), autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='matchdesk_customer_sessions'"
            )
            columns = {row[0] for row in cursor.fetchall()}
            assert "token_hash" in columns
            assert "session_id" not in columns
            assert "raw_token" not in columns
            cursor.execute(
                "SELECT token_hash FROM matchdesk_customer_sessions "
                "WHERE token_hash = %s",
                (hashlib.sha256(token.encode("ascii")).hexdigest(),),
            )
            digest = cursor.fetchone()
            assert digest is not None
            assert digest[0] != token


def _initial() -> None:
    """Exercise real create/revoke, idle/expiry, rollback and concurrent rotation."""
    store = _store()
    now = datetime.now(timezone.utc)
    fresh = _issue("ci-revoke", now=now)
    assert store.create(fresh)
    assert not store.create(fresh)
    assert store.load(fresh.session_id) == fresh
    assert resolve_customer_session(fresh.session_id, store=store, now=now) == fresh
    assert store.touch(fresh.session_id, now=now + timedelta(seconds=1))
    assert not store.load(fresh.session_id).revoked
    assert store.revoke(fresh.session_id)
    assert not store.revoke(fresh.session_id)
    assert not store.touch(fresh.session_id, now=now + timedelta(seconds=2))
    assert store.rotate(fresh.session_id, now=now + timedelta(seconds=2)) is None
    _expect_denial(fresh.session_id, now=now + timedelta(seconds=2))
    _assert_hash_only(fresh.session_id)
    print("PASS: actual Psycopg duplicate handling, touch and durable revocation")

    expired = _issue(
        "ci-expired", now=now - timedelta(minutes=5), ttl=timedelta(minutes=1)
    )
    idle = _issue(
        "ci-idle", now=now - timedelta(minutes=40), ttl=timedelta(hours=2)
    )
    assert store.create(expired)
    assert store.create(idle)
    for record in (expired, idle):
        assert not store.touch(record.session_id, now=now)
        assert store.rotate(record.session_id, now=now) is None
        _expect_denial(record.session_id, now=now)
    print("PASS: PostgreSQL expiry and 30-minute idle guard reject stale sessions")

    predecessor = _issue("ci-concurrent", now=now)
    assert store.create(predecessor)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: _store().rotate(
                    predecessor.session_id, now=now + timedelta(seconds=2)
                ),
                range(2),
            )
        )
    winners = [value for value in results if value is not None]
    assert len(winners) == 1
    assert winners[0].session_id != predecessor.session_id
    assert winners[0].expires_at == predecessor.expires_at
    _expect_denial(predecessor.session_id, now=now + timedelta(seconds=2))
    assert resolve_customer_session(
        winners[0].session_id, store=store, now=now + timedelta(seconds=2)
    ) == winners[0]
    rows = _count("ci-concurrent")
    assert len(rows) == 2
    assert sum(not row[0] for row in rows) == 1
    _assert_hash_only(winners[0].session_id)
    print("PASS: two real Psycopg session rotations yield exactly one active successor")

    rollback = _issue("ci-rollback", now=now)
    assert store.create(rollback)
    try:
        store.rotate(rollback.session_id, now=now + timedelta(seconds=2))
    except psycopg.errors.RaiseException as exc:
        assert "MatchDesk CI forced session insert rollback" in str(exc)
    else:
        raise AssertionError("Injected successor failure did not abort transaction")
    assert store.load(rollback.session_id) == rollback
    assert len(_count("ci-rollback")) == 1
    assert not _count("ci-rollback")[0][0]
    print("PASS: database audit of failed successor insert preserves old session")

    # Fixed, public synthetic fixture allows a separate process to inspect the
    # post-restart record without saving any generated bearer outside memory.
    surviving = replace(_issue("ci-restart", now=now), session_id=RESTART_TOKEN)
    assert store.create(surviving)
    _assert_hash_only(RESTART_TOKEN)
    _role_controls()
    print("MATCHDESK_CI_CUSTOMER_SESSIONS_INITIAL_PASS")


def _after_restart() -> None:
    """Verify persisted revocation and independently reconnect following DB restart."""
    store = _store()
    now = datetime.now(timezone.utc)
    surviving = store.load(RESTART_TOKEN)
    assert surviving is not None and surviving.account_id == "ci-restart"
    assert resolve_customer_session(RESTART_TOKEN, store=store, now=now) == surviving
    replacement = store.rotate(RESTART_TOKEN, now=now)
    assert replacement is not None
    assert replacement.session_id != RESTART_TOKEN
    assert replacement.expires_at == surviving.expires_at
    _expect_denial(RESTART_TOKEN, now=now)
    assert resolve_customer_session(
        replacement.session_id, store=store, now=now
    ) == replacement
    revoked = _count("ci-revoke")
    assert len(revoked) == 1 and revoked[0][0] is True
    _assert_hash_only(replacement.session_id)
    _role_controls()
    print("MATCHDESK_CI_CUSTOMER_SESSIONS_RESTART_PASS")


def main() -> None:
    """Separate phases enforce a real database restart between checks."""
    if len(sys.argv) != 2 or sys.argv[1] not in ("initial", "after-restart"):
        raise RuntimeError("Specify initial or after-restart")
    if sys.argv[1] == "initial":
        _initial()
    else:
        _after_restart()


if __name__ == "__main__":
    main()
