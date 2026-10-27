"""Disposable real-PostgreSQL acceptance for irreversible customer revocation.

This script runs ONLY with explicit CI flag and short-lived DB role passwords.
It never provisions real accounts or contacts an identity provider. Concurrent
lock checks use separate physical connections, not mock transaction managers.
The caller must first apply and review the ID3G migration candidate.
"""

from __future__ import annotations

import hashlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import psycopg

from matchdesk.domain.customer_identity import CustomerIdentityKey
from matchdesk.domain.customer_sessions import new_customer_session, resolve_customer_session
from matchdesk.domain.postgres_customer_sessions import PostgresCustomerSessionStore

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://ci.ciamlogin.com/{TENANT}/v2.0"
SESSION_USER = "matchdesk_session_revocation_ci"
OPERATOR_USER = "matchdesk_account_operator_ci"


def _connection(user: str) -> psycopg.Connection:
    """Create a fresh, bounded disposable connection for one trusted DB role."""
    if os.environ.get("CI") != "true":
        raise RuntimeError("Customer revocation acceptance is disposable-CI only")
    env_key = {
        SESSION_USER: "CI_REVOCATION_SESSION_PASSWORD",
        OPERATOR_USER: "CI_REVOCATION_OPERATOR_PASSWORD",
    }.get(user)
    if env_key is None or not os.environ.get(env_key):
        raise RuntimeError("Dedicated disposable database credential is missing")
    return psycopg.connect(
        host="postgres",
        dbname="matchdesk",
        user=user,
        password=os.environ[env_key],
        sslmode="prefer",
        connect_timeout=5,
        options="-c statement_timeout=8000",
    )


def _sessions() -> PostgresCustomerSessionStore:
    """Bind the production session adapter to the restricted CI writer role."""
    return PostgresCustomerSessionStore(lambda: _connection(SESSION_USER))


def _identity(subject: str) -> CustomerIdentityKey:
    """Construct one exact test broker identity without any email or roles."""
    return CustomerIdentityKey(issuer=ISSUER, tenant_id=TENANT, subject=subject)


def _candidate(subject: str, account_id: str):
    """Issue an unexposed bearer whose identity and account are independently bound."""
    return new_customer_session(
        identity=_identity(subject),
        account_id=account_id,
        now=datetime.now(timezone.utc),
    )


def _set_state(subject: str, state: str) -> None:
    """Commit a governed synthetic account-status change in its own transaction."""
    with _connection(OPERATOR_USER) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE matchdesk_customer_accounts SET state = %s "
                "WHERE issuer = %s AND tenant_id = %s AND subject = %s",
                (state, ISSUER, TENANT, subject),
            )
            assert cursor.rowcount == 1


def _account_change(subject: str, next_account: str) -> None:
    """Exercise a separately granted synthetic account reassignment."""
    with _connection(OPERATOR_USER) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE matchdesk_customer_accounts SET account_id = %s "
                "WHERE issuer = %s AND tenant_id = %s AND subject = %s",
                (next_account, ISSUER, TENANT, subject),
            )
            assert cursor.rowcount == 1


def _expect_denied(record) -> None:
    """Verify a revoked bearer can never be resolved into customer authority."""
    try:
        resolve_customer_session(record.session_id, store=_sessions())
    except PermissionError:
        return
    raise AssertionError("An old or revoked customer session was accepted")


def _expect_insertion_denied(record) -> None:
    """Require the database insertion trigger to reject an untrusted account."""
    try:
        _sessions().create(record)
    except psycopg.errors.InsufficientPrivilege:
        return
    raise AssertionError("Database admitted a session without an active exact account")


def _insert_in_open_transaction(connection: psycopg.Connection, record) -> None:
    """Hold an uncommitted insert to inspect the account-row lock ordering."""
    digest = hashlib.sha256(record.session_id.encode("ascii")).hexdigest()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO matchdesk_customer_sessions "
            "(token_hash, issuer, tenant_id, subject, account_id, realm, "
            "created_at, expires_at, last_seen_at, revoked) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                digest,
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


def _lock_timeout_expected(action) -> None:
    """Require a real lock conflict, not an accidentally permitted race."""
    try:
        action()
    except psycopg.errors.LockNotAvailable:
        return
    raise AssertionError("Expected a conflicting account/session transaction lock")


def _run_legacy_reconciliation() -> None:
    """No active pre-migration bearer may survive the new security boundary."""
    with _connection(SESSION_USER) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT revoked FROM public.matchdesk_customer_sessions "
                "WHERE token_hash = repeat('e', 64)"
            )
            assert cursor.fetchone() == (True,), (
                "An active-looking legacy customer session survived migration"
            )
    print("MATCHDESK_CUSTOMER_REVOCATION_LEGACY_INVALIDATION_PASS")


def _run_revocation_semantics() -> None:
    """Prove state transitions irreversibly invalidate all existing bearers."""
    sessions = _sessions()
    current = _candidate("ci-revive", "ci-revive-account")
    assert sessions.create(current) is True
    assert resolve_customer_session(current.session_id, store=sessions) == current
    _set_state("ci-revive", "suspended")
    assert sessions.load(current.session_id).revoked is True
    _expect_denied(current)
    _set_state("ci-revive", "active")
    assert sessions.load(current.session_id).revoked is True
    _expect_denied(current)
    _expect_insertion_denied(_candidate("ci-revive", "wrong-account"))

    before = _candidate("ci-reassign", "ci-reassign-account")
    assert sessions.create(before) is True
    _account_change("ci-reassign", "ci-reassign-next")
    assert sessions.load(before.session_id).revoked is True
    _expect_denied(before)
    _expect_insertion_denied(_candidate("ci-reassign", "ci-reassign-account"))
    assert sessions.create(_candidate("ci-reassign", "ci-reassign-next")) is True

    _set_state("ci-pending-new", "pending")
    _expect_insertion_denied(_candidate("ci-pending-new", "ci-pending-new-account"))

    deleted = _candidate("ci-delete", "ci-delete-account")
    assert sessions.create(deleted) is True
    with _connection(OPERATOR_USER) as operator:
        with operator.cursor() as cursor:
            cursor.execute(
                "DELETE FROM matchdesk_customer_accounts "
                "WHERE issuer = %s AND tenant_id = %s AND subject = %s",
                (ISSUER, TENANT, "ci-delete"),
            )
            assert cursor.rowcount == 1
    assert sessions.load(deleted.session_id).revoked is True
    _expect_denied(deleted)
    _expect_insertion_denied(_candidate("ci-delete", "ci-delete-account"))

    with _connection(SESSION_USER) as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    "UPDATE matchdesk_customer_sessions SET revoked = FALSE "
                    "WHERE token_hash = %s",
                    (hashlib.sha256(current.session_id.encode("ascii")).hexdigest(),),
                )
            except psycopg.errors.InsufficientPrivilege:
                # Reset the PostgreSQL transaction after the expected 42501.
                connection.rollback()
            else:
                raise AssertionError("Database allowed revoked session resurrection")
    assert sessions.load(current.session_id).revoked is True
    print("MATCHDESK_CUSTOMER_REVOCATION_IRREVERSIBLE_PASS")


def _run_insert_first_race() -> None:
    """An in-flight session insert must block suspension until insertion commits."""
    record = _candidate("ci-insert-first", "ci-insert-first-account")
    with _connection(SESSION_USER) as writer:
        with _connection(OPERATOR_USER) as operator:
            _insert_in_open_transaction(writer, record)

            def attempt_suspend() -> None:
                """Use a short SQL lock timeout while the writer holds FOR SHARE."""
                with operator.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '300ms'")
                    cursor.execute(
                        "UPDATE matchdesk_customer_accounts SET state = 'suspended' "
                        "WHERE subject = %s AND issuer = %s AND tenant_id = %s",
                        ("ci-insert-first", ISSUER, TENANT),
                    )

            _lock_timeout_expected(attempt_suspend)
            operator.rollback()
            writer.commit()
    _set_state("ci-insert-first", "suspended")
    assert _sessions().load(record.session_id).revoked is True
    _expect_denied(record)
    print("MATCHDESK_CUSTOMER_REVOCATION_INSERT_FIRST_LOCK_PASS")


def _run_suspension_first_race() -> None:
    """An open suspension transaction must block any concurrent session insert."""
    record = _candidate("ci-suspend-first", "ci-suspend-first-account")
    with _connection(OPERATOR_USER) as operator:
        with _connection(SESSION_USER) as writer:
            with operator.cursor() as cursor:
                cursor.execute(
                    "UPDATE matchdesk_customer_accounts SET state = 'suspended' "
                    "WHERE subject = %s AND issuer = %s AND tenant_id = %s",
                    ("ci-suspend-first", ISSUER, TENANT),
                )
                assert cursor.rowcount == 1

            def attempt_insert() -> None:
                """Demand the writer wait on the account row held by suspension."""
                with writer.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '300ms'")
                _insert_in_open_transaction(writer, record)

            _lock_timeout_expected(attempt_insert)
            writer.rollback()
            operator.commit()
    _expect_insertion_denied(record)
    print("MATCHDESK_CUSTOMER_REVOCATION_SUSPEND_FIRST_LOCK_PASS")


def _run_simultaneous_rotation() -> None:
    """Racing rotation must never leave a usable bearer after suspension commits."""
    original = _candidate("ci-rotate-race", "ci-rotate-race-account")
    assert _sessions().create(original) is True
    barrier = Barrier(3, timeout=8)

    def rotate():
        """Attempt a genuine production-adapter rotation concurrently."""
        barrier.wait()
        try:
            return _sessions().rotate(original.session_id)
        except (psycopg.errors.DeadlockDetected, psycopg.errors.LockNotAvailable):
            # PostgreSQL aborts the conflicting transaction; no cookie is sent.
            return None

    def suspend() -> None:
        """Commit the governed account-status transition; retry deadlock once."""
        barrier.wait()
        try:
            _set_state("ci-rotate-race", "suspended")
        except (psycopg.errors.DeadlockDetected, psycopg.errors.LockNotAvailable):
            _set_state("ci-rotate-race", "suspended")

    with ThreadPoolExecutor(max_workers=2) as pool:
        rotated = pool.submit(rotate)
        suspended = pool.submit(suspend)
        barrier.wait()
        successor = rotated.result(timeout=15)
        suspended.result(timeout=15)
    assert _sessions().load(original.session_id).revoked is True
    _expect_denied(original)
    if successor is not None:
        assert _sessions().load(successor.session_id).revoked is True
        _expect_denied(successor)
    print("MATCHDESK_CUSTOMER_REVOCATION_ROTATE_RACE_PASS")


def _run_db_role_boundaries() -> None:
    """Reject unauthorized account writes, customer session deletions and DDL."""
    with _connection(SESSION_USER) as connection:
        with connection.cursor() as cursor:
            for table, action, expected in (
                ("matchdesk_customer_accounts", "SELECT", False),
                ("matchdesk_customer_accounts", "UPDATE", False),
                ("matchdesk_customer_accounts", "DELETE", False),
                ("matchdesk_customer_sessions", "SELECT", True),
                ("matchdesk_customer_sessions", "INSERT", True),
                ("matchdesk_customer_sessions", "UPDATE", True),
                ("matchdesk_customer_sessions", "DELETE", False),
            ):
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, %s)",
                    (table, action),
                )
                assert cursor.fetchone() == (expected,)
            cursor.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            assert cursor.fetchone() == (False,)
    with _connection(OPERATOR_USER) as connection:
        with connection.cursor() as cursor:
            # Suspensions operate through the owner-owned trigger; giving the
            # operator SELECT/UPDATE on session rows would leak customer data.
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, %s)",
                    ("matchdesk_customer_sessions", privilege),
                )
                assert cursor.fetchone() == (False,)
            cursor.execute(
                "SELECT has_column_privilege(current_user, "
                "'matchdesk_customer_accounts', 'issuer', 'UPDATE')"
            )
            assert cursor.fetchone() == (False,)
            cursor.execute(
                "SELECT has_column_privilege(current_user, "
                "'matchdesk_customer_accounts', 'state', 'UPDATE')"
            )
            assert cursor.fetchone() == (True,)
    # The bootstrap account is a PostgreSQL superuser: SECURITY DEFINER must
    # never execute with its privileges. Reject a login, member, or superuser
    # function owner, or missing required definer ownership.
    with _connection(SESSION_USER) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT p.proname, r.rolname, r.rolsuper, r.rolcanlogin, "
                "r.rolbypassrls, p.prosecdef FROM pg_catalog.pg_proc p "
                "JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
                "JOIN pg_catalog.pg_roles r ON r.oid = p.proowner "
                "WHERE n.nspname = 'public' AND p.proname IN "
                "('matchdesk_require_active_customer_for_insert', "
                " 'matchdesk_revoke_sessions_for_customer_change')"
            )
            owner_rows = cursor.fetchall()
            assert len(owner_rows) == 2, "Missing reviewed security definer"
            assert all(
                owner == "matchdesk_revocation_guard_owner"
                and not superuser and not login and not bypass and definer
                for _name, owner, superuser, login, bypass, definer in owner_rows
            ), "Security definer must not be bootstrap superuser-owned"
            cursor.execute(
                "SELECT 1 FROM pg_catalog.pg_auth_members m "
                "JOIN pg_catalog.pg_roles r ON r.oid = m.roleid "
                "WHERE r.rolname = 'matchdesk_revocation_guard_owner'"
            )
            assert cursor.fetchone() is None, "Definer role membership prohibited"
    print("MATCHDESK_CUSTOMER_REVOCATION_ROLES_PASS")


def main() -> None:
    """Exercise the disposable database, never touching deployment settings."""
    if len(sys.argv) != 1:
        raise RuntimeError("No user-supplied session or database parameters accepted")
    _run_db_role_boundaries()
    _run_legacy_reconciliation()
    _run_revocation_semantics()
    _run_insert_first_race()
    _run_suspension_first_race()
    _run_simultaneous_rotation()
    print("MATCHDESK_CUSTOMER_REVOCATION_REAL_POSTGRES_PASS")


if __name__ == "__main__":
    main()
