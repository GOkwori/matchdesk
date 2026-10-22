"""Disposable restricted confirmation-stager qualification.

A physical SCRAM staging principal has only EXECUTE on the staging function.
The CI database owner establishes synthetic fixtures and later reconciles rows.
This never verifies real Entra MFA, human approval or a signed confirmation.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg
from psycopg import errors, sql

_STAGER = "matchdesk_stager_executor_ci"
_DEFINER = "matchdesk_stager_definer_ci"
_ISSUER = "matchdesk_issuer_executor_ci"
_REVOKER = "matchdesk_revoker_executor_ci"
_STAGE_FUNCTION = (
    "public.matchdesk_stage_producer_confirmation("
    "text,text,text,text,text,text,text,bigint,jsonb,text,text,text,timestamptz)"
)
_ISSUE_FUNCTION = (
    "public.matchdesk_issue_confirmed_producer_grant("
    "text,text,text,text,text,text,text,text,bigint,jsonb,text,text)"
)
_REVOKE_FUNCTION = "public.matchdesk_revoke_confirmed_producer_grant(text)"
_TENANT = "ci-staging-tenant"
_SESSION = "ci-staging-session"
_OUTPUT = "ci-staging-output"
_ACTOR = "ci-staging-producer"
_TOKEN_ISSUER = "https://issuer-ci.example.invalid"
_BINDING = '{"ci":"staging"}'
_CASE_SHA = "a" * 64
_AUDIT_SHA = "d" * 64
_PROOF_SHA = "b" * 64
_VALID = "4" * 32
_CONCURRENT = "5" * 32
_INVALID_IDS = ("6" * 32, "7" * 32, "8" * 32, "9" * 32)
_GRANT = "ci-staging-confirmed-grant-01"


def _connect(role: str, password: str):
    """Physically authenticate with password: never impersonate via SET ROLE."""
    if os.getenv("CI") != "true" or len(password) < 32:
        raise RuntimeError("Disposable CI and independent SCRAM secret are required")
    return psycopg.connect(
        host="postgres",
        dbname="matchdesk",
        user=role,
        password=password,
        sslmode="prefer",
        connect_timeout=10,
        autocommit=True,
    )


def _owner():
    """Open the CI-only owner for role setup and independent readback."""
    return _connect("matchdesk", os.environ.get("PGPASSWORD", ""))


def _role_setup() -> None:
    """Own the resource with NOLOGIN and expose only function EXECUTE to stager."""
    password = os.environ.get("STAGER_CI_PASSWORD", "")
    if len(password) < 32:
        raise RuntimeError("Missing masked ephemeral stager secret")
    with _owner() as connection:
        with connection.cursor() as cursor:
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cursor.execute("REVOKE TEMP ON DATABASE matchdesk FROM PUBLIC")
            cursor.execute(
                sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION NOBYPASSRLS").format(
                    sql.Identifier(_DEFINER)
                )
            )
            cursor.execute(
                sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                    sql.Identifier(_DEFINER)
                )
            )
            cursor.execute(
                sql.SQL("GRANT SELECT, INSERT ON "
                        "public.matchdesk_producer_confirmations TO {}").format(
                    sql.Identifier(_DEFINER)
                )
            )
            cursor.execute(
                sql.SQL("ALTER FUNCTION " + _STAGE_FUNCTION + " OWNER TO {}").format(
                    sql.Identifier(_DEFINER)
                )
            )
            cursor.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(
                    sql.Identifier(_DEFINER)
                )
            )
            cursor.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION NOBYPASSRLS").format(
                    sql.Identifier(_STAGER)
                )
            )
            cursor.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(_STAGER), sql.Literal(password)
                )
            )
            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE matchdesk TO {}").format(
                    sql.Identifier(_STAGER)
                )
            )
            cursor.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier(_STAGER)
                )
            )
            cursor.execute(
                sql.SQL("GRANT EXECUTE ON FUNCTION " + _STAGE_FUNCTION + " TO {}").format(
                    sql.Identifier(_STAGER)
                )
            )
    print("PASS: staging owner NOLOGIN and separate SCRAM EXECUTE-only principal")


def _role_check(cursor) -> None:
    """Reject inherited roles, direct DML, issuer/revoker rights and ownership."""
    cursor.execute(
        "SELECT current_user::text, session_user::text, "
        "r.rolcanlogin, r.rolsuper, r.rolcreatedb, r.rolcreaterole, "
        "r.rolbypassrls, EXISTS ("
        "SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid) "
        "FROM pg_catalog.pg_roles r WHERE r.rolname = current_user"
    )
    assert cursor.fetchone() == (
        _STAGER, _STAGER, True, False, False, False, False, False
    )
    for table in (
        "public.matchdesk_producer_confirmations",
        "public.matchdesk_producer_action_grants",
        "public.matchdesk_producer_cases",
        "public.matchdesk_producer_audit",
    ):
        cursor.execute(
            "SELECT has_table_privilege(current_user, %s, "
            "'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'), "
            "has_any_column_privilege(current_user, %s, "
            "'SELECT, INSERT, UPDATE, REFERENCES')",
            (table, table),
        )
        assert cursor.fetchone() == (False, False), table
    cursor.execute(
        "SELECT has_function_privilege(current_user,%s,'EXECUTE'),"
        "has_function_privilege(current_user,%s,'EXECUTE'),"
        "has_function_privilege(current_user,%s,'EXECUTE')",
        (_STAGE_FUNCTION, _ISSUE_FUNCTION, _REVOKE_FUNCTION),
    )
    assert cursor.fetchone() == (True, False, False)
    cursor.execute(
        "SELECT has_schema_privilege(current_user, 'public', 'CREATE'), "
        "has_database_privilege(current_user, 'matchdesk', 'TEMPORARY')"
    )
    assert cursor.fetchone() == (False, False)
    try:
        cursor.execute("SELECT count(*) FROM public.matchdesk_producer_confirmations")
    except errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("Stager can read confirmation rows without authorization")


def _stage(
    cursor,
    confirmation: str,
    *,
    tenant: str = _TENANT,
    actor: str = _ACTOR,
    action: str = "create",
    generation: int = 0,
    binding: str = _BINDING,
    case_hash: str = _CASE_SHA,
    proof_hash: str = _PROOF_SHA,
    ttl_seconds: int = 90,
) -> bool:
    """Pass only typed arguments to the narrow, default-denied SQL function."""
    cursor.execute(
        "SELECT public.matchdesk_stage_producer_confirmation("
        "%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,"
        "clock_timestamp() + %s * interval '1 second')",
        (
            confirmation, tenant, _SESSION, _OUTPUT, actor, _TOKEN_ISSUER,
            action, generation, binding, case_hash, _AUDIT_SHA, proof_hash,
            ttl_seconds,
        ),
    )
    receipt = cursor.fetchone()
    assert receipt is not None and type(receipt[0]) is bool
    return receipt[0]


def _issue_by_authorized_role(confirmation: str) -> None:
    """Prove a staged row can be consumed only via a distinct issuer login."""
    password = os.getenv("ISSUER_CI_PASSWORD", "")
    with _connect(_ISSUER, password) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT public.matchdesk_issue_confirmed_producer_grant("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                (
                    confirmation, _GRANT, _TENANT, _SESSION, _OUTPUT,
                    _ACTOR, _TOKEN_ISSUER, "create", 0, _BINDING,
                    _CASE_SHA, _AUDIT_SHA,
                ),
            )
            assert cursor.fetchone() == (True,)
            cursor.execute(
                "SELECT public.matchdesk_issue_confirmed_producer_grant("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                (
                    confirmation, "ci-staging-replay-grant-01", _TENANT,
                    _SESSION, _OUTPUT, _ACTOR, _TOKEN_ISSUER, "create",
                    0, _BINDING, _CASE_SHA, _AUDIT_SHA,
                ),
            )
            assert cursor.fetchone() == (False,)


def _revoke_by_authorized_role(confirmation: str) -> None:
    """The separate physical revoker invalidates the unused issued grant."""
    with _connect(_REVOKER, os.getenv("REVOKER_CI_PASSWORD", "")) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT public.matchdesk_revoke_confirmed_producer_grant(%s)",
                (confirmation,),
            )
            assert cursor.fetchone() == (True,)


def _exercise() -> None:
    """Test malformed, duplicate and race staging with a real limited login."""
    password = os.getenv("STAGER_CI_PASSWORD", "")
    with _connect(_STAGER, password) as connection:
        with connection.cursor() as cursor:
            _role_check(cursor)
            assert _stage(cursor, _VALID) is True
            assert _stage(cursor, _VALID, actor="forged-operator") is False
            assert _stage(cursor, _INVALID_IDS[0], tenant="") is False
            assert _stage(cursor, _INVALID_IDS[1], action="publish") is False
            assert _stage(cursor, _INVALID_IDS[2], generation=1) is False
            assert _stage(cursor, _INVALID_IDS[3], proof_hash="x" * 64) is False
            assert _stage(cursor, "invalid-id") is False
            assert _stage(cursor, "a" * 32, binding="[]") is False
            assert _stage(cursor, "b" * 32, ttl_seconds=-1) is False
            assert _stage(cursor, "c" * 32, ttl_seconds=130) is False
    start = Barrier(3)

    def contender() -> bool:
        """Each contender authenticates independently and races one nonce."""
        with _connect(_STAGER, password) as connection:
            with connection.cursor() as cursor:
                start.wait(timeout=15)
                return _stage(cursor, _CONCURRENT)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = [future.result(timeout=30) for future in
                   [pool.submit(contender) for _ in range(3)]]
    assert results.count(True) == 1 and results.count(False) == 2, results
    _issue_by_authorized_role(_VALID)
    _revoke_by_authorized_role(_VALID)
    print("PASS: physical stager rejects malformed, replay and overprivileged actions")


def _verify() -> None:
    """Independently inspect immutable expected state after PostgreSQL restart."""
    with _owner() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT confirmation_id, consumed_at IS NOT NULL, "
                "revoked_at IS NOT NULL, issued_grant_id "
                "FROM public.matchdesk_producer_confirmations "
                "WHERE confirmation_id IN (%s,%s)",
                (_VALID, _CONCURRENT),
            )
            records = {cid: (consumed, revoked, issued)
                       for cid, consumed, revoked, issued in cursor.fetchall()}
            assert records == {
                _VALID: (True, True, _GRANT),
                _CONCURRENT: (False, False, None),
            }, records
            cursor.execute(
                "SELECT grant_id, revoked_at IS NOT NULL, consumed_at IS NOT NULL "
                "FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=%s",
                (_VALID,),
            )
            assert cursor.fetchall() == [(_GRANT, True, False)]
            cursor.execute(
                "SELECT count(*) FROM public.matchdesk_producer_confirmations "
                "WHERE tenant_id=%s AND "
                "confirmation_id IN (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    _TENANT,
                    *_INVALID_IDS,
                    "invalid-id",
                    "a" * 32,
                    "b" * 32,
                    "c" * 32,
                    "d" * 32,
                    "e" * 32,
                ),
            )
            assert cursor.fetchone() == (0,)
    print("MATCHDESK_P4_STAGER_RESTART_RECONCILED: one atomic grant, no replay")


def main() -> None:
    """Execute only a fixed synthetic CI phase; no live issuer is mounted."""
    if len(sys.argv) != 2 or sys.argv[1] not in ("setup", "exercise", "verify"):
        raise ValueError("Expected disposable staging setup/exercise/verify")
    if sys.argv[1] == "setup":
        _role_setup()
    elif sys.argv[1] == "exercise":
        _exercise()
    else:
        _verify()


if __name__ == "__main__":
    main()
