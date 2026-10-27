"""P3-05: qualify the actual Python producer store against disposable PostgreSQL.

Run through stdin in the existing locked, read-only API container. The PostgreSQL
role has only SELECT/INSERT/UPDATE on cases and SELECT/INSERT on audit entries.
No authenticated HTTP endpoint, cloud deployment or production secret is involved.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor

import psycopg

from matchdesk.domain.postgres_producer_store import PostgresProducerCaseStore
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    apply_producer_command,
    execute_producer_command,
    open_producer_case,
)
from matchdesk.domain.producer_preview import build_producer_desk_preview
from matchdesk.domain.psycopg_producer_driver import producer_connection_factory


def _db_dsn() -> str:
    """Require the short-lived CI role; let libpq read its masked password."""
    if os.environ.get("CI") != "true" or not os.environ.get("PGPASSWORD"):
        raise RuntimeError("Real producer-store testing is restricted to disposable CI")
    return "host=postgres dbname=matchdesk user=matchdesk_producer_ci sslmode=prefer"


def _actor() -> HostVerifiedActor:
    """Construct test-only producer identity, never derived from an HTTP header."""
    return HostVerifiedActor(
        subject="ci-producer",
        tenant_id="ci-tenant",
        issuer="https://ci.example.invalid",
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )


def _scope() -> tuple[str, str, str]:
    """Rebuild the deterministic offline fixture's stable identifier tuple."""
    output = build_producer_desk_preview().output
    return ("ci-tenant", output.session_id, output.output_id)


def _assert_audit(conninfo: str, expected_generation: int) -> None:
    """Read actual persisted rows through the restricted role, not a fake cursor."""
    with psycopg.connect(conninfo, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT generation, audit_digest FROM matchdesk_producer_cases "
                "WHERE tenant_id=%s AND session_id=%s AND output_id=%s",
                _scope(),
            )
            state = cursor.fetchone()
            assert state is not None
            assert state[0] == expected_generation
            cursor.execute(
                "SELECT generation, audit_digest FROM matchdesk_producer_audit "
                "WHERE tenant_id=%s AND session_id=%s AND output_id=%s ORDER BY generation",
                _scope(),
            )
            entries = cursor.fetchall()
            assert [entry[0] for entry in entries] == list(
                range(1, expected_generation + 1)
            )
            assert entries[-1][1] == state[1]


def _check_role_privileges(conninfo: str) -> None:
    """Verify that the CI writer cannot delete rows, change DDL or impersonate owner."""
    with psycopg.connect(conninfo, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname=current_user"
            )
            flags = cursor.fetchone()
            assert flags == (False, False)
            for table_name in ("matchdesk_producer_cases", "matchdesk_producer_audit"):
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, 'DELETE')",
                    (table_name,),
                )
                assert cursor.fetchone() == (False,)
            cursor.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            assert cursor.fetchone() == (False,)
            for statement in (
                "DELETE FROM matchdesk_producer_cases WHERE tenant_id='ci-tenant'",
                "DELETE FROM matchdesk_producer_audit WHERE tenant_id='ci-tenant'",
                "ALTER TABLE matchdesk_producer_cases ADD COLUMN disallowed text",
                "SET ROLE matchdesk",
            ):
                try:
                    cursor.execute(statement)
                except psycopg.errors.InsufficientPrivilege:
                    pass
                else:
                    raise AssertionError("Producer CI DB role accepted a forbidden action")
    print("PASS: restricted role cannot delete, alter schema or assume database owner")


def _initial() -> None:
    """Qualify real create/load/reverify, rollback and competing producer transitions."""
    conninfo = _db_dsn()
    store = PostgresProducerCaseStore(producer_connection_factory(conninfo=conninfo))
    actor = _actor()
    preview = build_producer_desk_preview()
    initial = open_producer_case(
        actor=actor,
        tenant_id="ci-tenant",
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )
    assert store.create(initial)
    assert not store.create(initial)
    assert store.load(*_scope()) == initial
    assert store.load("foreign-tenant", *_scope()[1:]) is None
    print("PASS: restricted real driver created and loaded one scoped, unapproved case")

    reviewed = execute_producer_command(
        store,
        actor=actor,
        tenant_id="ci-tenant",
        session_id=preview.output.session_id,
        output_id=preview.output.output_id,
        expected_generation=1,
        command="reverify",
        reason="Verified synthetic source evidence",
    )
    assert reviewed.generation == 2
    assert reviewed.review.status == "ready_for_decision"
    _assert_audit(conninfo, 2)
    print("PASS: actual Psycopg transaction committed reverified state and audit")

    # The CI-only database trigger rejects this audit insert after a valid CAS
    # case UPDATE. PostgreSQL must roll back both statements together.
    rollback_candidate = apply_producer_command(
        reviewed,
        actor=actor,
        expected_generation=2,
        command="reject",
        reason="ci-rollback-probe",
    )
    try:
        store.replace_if_generation(rollback_candidate, expected_generation=2)
    except psycopg.errors.RaiseException as exc:
        assert "MatchDesk CI forced audit rollback" in str(exc)
    else:
        raise AssertionError("Injected audit failure did not roll back the case update")
    assert store.load(*_scope()) == reviewed
    _assert_audit(conninfo, 2)
    print("PASS: real Psycopg audit failure rolled back the case state")

    contenders = (
        apply_producer_command(
            reviewed,
            actor=actor,
            expected_generation=2,
            command="approve",
            reason="Synthetic CI review option A",
        ),
        apply_producer_command(
            reviewed,
            actor=actor,
            expected_generation=2,
            command="reject",
            reason="Synthetic CI review option B",
        ),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda candidate: store.replace_if_generation(
                    candidate, expected_generation=2
                ),
                contenders,
            )
        )
    assert sorted(outcomes) == [False, True]
    final = store.load(*_scope())
    assert final is not None
    assert final.generation == 3
    assert final.review.status in ("approved", "rejected")
    _assert_audit(conninfo, 3)
    print("PASS: two real Python writers produced one CAS winner and one audit")

    _check_role_privileges(conninfo)

    # A restricted writer can append an audit row, but it must not be able to
    # make an unreviewed snapshot appear to be a valid producer state.
    isolated = initial.output.model_copy(update={"output_id": "ci-audit-tamper-probe"})
    tamper_case = open_producer_case(
        actor=actor,
        tenant_id="ci-tenant",
        output=isolated,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )
    assert store.create(tamper_case)
    with psycopg.connect(conninfo, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO matchdesk_producer_audit "
                "(tenant_id, session_id, output_id, generation, entry_json, audit_digest) "
                "VALUES (%s, %s, %s, 2, %s::jsonb, %s)",
                (
                    "ci-tenant",
                    isolated.session_id,
                    isolated.output_id,
                    '{"action":"forged"}',
                    "0" * 64,
                ),
            )
    try:
        store.load("ci-tenant", isolated.session_id, isolated.output_id)
    except ValueError as exc:
        assert "audit table" in str(exc)
    else:
        raise AssertionError("Unrecorded audit insert was accepted as a valid review state")
    print("PASS: separate audit-table reconciliation fails closed on forged extra row")


def _after_restart() -> None:
    """Prove a fresh Psycopg connection can reconstruct audit and state after restart."""
    conninfo = _db_dsn()
    store = PostgresProducerCaseStore(producer_connection_factory(conninfo=conninfo))
    case = store.load(*_scope())
    assert case is not None
    assert case.generation == 3
    assert case.review.status in ("approved", "rejected")
    _assert_audit(conninfo, 3)
    _check_role_privileges(conninfo)
    print("MATCHDESK_P3E_REAL_PSYCOPG_PASS: scoped store and audit survived DB restart")


def main() -> None:
    """Restrict commands to the two explicit qualification phases."""
    if len(sys.argv) != 2 or sys.argv[1] not in ("initial", "after-restart"):
        raise RuntimeError("Expected initial or after-restart phase")
    if sys.argv[1] == "initial":
        _initial()
    else:
        _after_restart()


if __name__ == "__main__":
    main()
