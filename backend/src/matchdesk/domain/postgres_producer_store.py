"""Tenant-scoped PostgreSQL producer review storage with transactional audit.

The host supplies a reviewed PostgreSQL driver and trusted connection factory.
This module cannot authenticate an actor or publish; caller authorization remains
the responsibility of execute_producer_command and the future HTTP identity edge.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from pydantic import TypeAdapter

from matchdesk.domain.producer_commands import ProducerCase, _validate_case
from matchdesk.domain.producer_execution_grants import (
    ProducerGrantAttempt,
    consume_execution_grant,
)
from matchdesk.domain.producer_review import ProducerAuditEntry


class DbCursor(Protocol):
    """Limited DB-API operations required for PostgreSQL parameterized statements."""

    def execute(self, sql: str, parameters: tuple[object, ...]) -> object:
        """Execute one parameterized statement without interpolating identifiers."""

    def fetchone(self) -> tuple[object, ...] | None:
        """Read one row, or None if the exact-generation write did not apply."""

    def fetchall(self) -> list[tuple[object, ...]]:
        """Read complete scoped audit history for independent reconciliation."""


class DbConnection(Protocol):
    """Host-owned transaction and cursor provider, supplied by a pinned DB driver."""

    def transaction(self) -> AbstractContextManager[object]:
        """Commit on success and roll back the entire operation on any exception."""

    def cursor(self) -> AbstractContextManager[DbCursor]:
        """Acquire a context-managed PostgreSQL cursor."""

    def close(self) -> None:
        """Release the connection without leaking it on failure."""


_CASE = TypeAdapter(ProducerCase)
_AUDIT = TypeAdapter(tuple[ProducerAuditEntry, ...])
_ENTRY = TypeAdapter(ProducerAuditEntry)

_LOAD = """
SELECT generation, case_json, audit_digest
FROM matchdesk_producer_cases
WHERE tenant_id = %s AND session_id = %s AND output_id = %s
"""
_LOAD_AUDIT = """
SELECT generation, entry_json, audit_digest
FROM matchdesk_producer_audit
WHERE tenant_id = %s AND session_id = %s AND output_id = %s
ORDER BY generation
"""
_CREATE = """
INSERT INTO matchdesk_producer_cases
(tenant_id, session_id, output_id, generation, case_json, audit_digest)
VALUES (%s, %s, %s, %s, %s::jsonb, %s)
ON CONFLICT DO NOTHING RETURNING generation
"""
_COMPARE_AND_SWAP = """
UPDATE matchdesk_producer_cases
SET generation = %s, case_json = %s::jsonb,
    audit_digest = %s, updated_at = clock_timestamp()
WHERE tenant_id = %s AND session_id = %s AND output_id = %s
  AND generation = %s AND audit_digest = %s
RETURNING generation
"""
_APPEND_AUDIT = """
INSERT INTO matchdesk_producer_audit
(tenant_id, session_id, output_id, generation, entry_json, audit_digest)
VALUES (%s, %s, %s, %s, %s::jsonb, %s)
"""


# The physical login is checked inside the same read-only snapshot as the
# scoped case/audit. Effective DML and role membership count even when granted
# indirectly through PUBLIC. Token claims never select the database principal.
_READ_ONLY_ROLE_QUERY = """
SELECT current_user::text, session_user::text,
       (
           r.rolcanlogin
           AND NOT (
               r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
               OR r.rolreplication OR r.rolbypassrls
           )
           AND NOT EXISTS (
               SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid
           )
           AND NOT pg_catalog.has_database_privilege(current_database(), 'CREATE')
           AND NOT pg_catalog.has_database_privilege(current_database(), 'TEMP')
           AND NOT EXISTS (
               SELECT 1 FROM pg_catalog.pg_namespace ns
               WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
                 AND pg_catalog.has_schema_privilege(ns.oid, 'CREATE')
           )
           AND NOT EXISTS (
               SELECT 1 FROM pg_catalog.pg_class c
               JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
               WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
                 AND CASE
                     WHEN c.relkind IN ('r', 'p', 'v', 'm', 'f') THEN
                         pg_catalog.has_table_privilege(
                             c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'
                         )
                         OR pg_catalog.has_any_column_privilege(
                             c.oid, 'INSERT, UPDATE, REFERENCES'
                         )
                     ELSE FALSE
                 END
           )
           AND NOT EXISTS (
               SELECT 1 FROM pg_catalog.pg_class c
               JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
               WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
                 AND CASE WHEN c.relkind = 'S'
                     THEN pg_catalog.has_sequence_privilege(c.oid, 'USAGE, UPDATE')
                     ELSE FALSE
                 END
           )
           AND NOT EXISTS (
               SELECT 1 FROM pg_catalog.pg_proc p
               JOIN pg_catalog.pg_namespace ns ON ns.oid = p.pronamespace
               WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
                 AND pg_catalog.has_function_privilege(p.oid, 'EXECUTE')
           )
           AND pg_catalog.has_table_privilege('public.matchdesk_producer_cases', 'SELECT')
           AND pg_catalog.has_table_privilege('public.matchdesk_producer_audit', 'SELECT')
       )
FROM pg_catalog.pg_roles r WHERE r.rolname = current_user
"""
_EXPECTED_ROLE = re.compile(r"matchdesk_[a-z][a-z0-9_]{0,54}\Z")


def _audit_digest(entries: tuple[ProducerAuditEntry, ...]) -> str:
    """Hash the entire ordered audit history to detect rewritten prior transitions."""
    return hashlib.sha256(_AUDIT.dump_json(entries)).hexdigest()


def _case_json(case: ProducerCase) -> str:
    """Serialize the immutable case, including the evidence and verified claim objects."""
    return _CASE.dump_json(case).decode("utf-8")


def _reconcile_audit(case: ProducerCase, rows: list[tuple[object, ...]]) -> None:
    """Match every immutable audit-table row with the exact stored review history.

    Case snapshots and audit records are separate physical tables. Comparing a
    snapshot's self-contained hash alone is insufficient: an altered snapshot could
    claim approvals that were never appended to the protected audit table.
    """
    history = case.review.audit
    if len(rows) != len(history):
        raise ValueError("Producer audit table does not match case generation")
    for generation, (row, expected) in enumerate(zip(rows, history, strict=True), start=1):
        if (
            not isinstance(row, tuple)
            or len(row) != 3
            or type(row[0]) is not int
            or row[0] != generation
            or not isinstance(row[2], str)
            or row[2] != _audit_digest(history[:generation])
        ):
            raise ValueError("Producer audit table has a missing or inconsistent generation")
        raw_entry = row[1]
        entry_json = (
            raw_entry if isinstance(raw_entry, (str, bytes, bytearray)) else json.dumps(raw_entry)
        )
        if _ENTRY.validate_json(entry_json) != expected:
            raise ValueError("Producer audit entry differs from the review snapshot")


class PostgresProducerCaseStore:
    """Atomically persist a case and its append-only audit for one exact tenant/session.

    The caller must run open_producer_case or execute_producer_command with a
    host-authenticated actor; the store is a persistence adapter, not a permission
    decision point. No driver installation or database creation occurs here.
    """

    def __init__(
        self,
        connection_factory: Callable[[], DbConnection],
        *,
        _read_role: str | None = None,
    ) -> None:
        """Accept a trusted connection factory and optional physical role pin."""
        if not callable(connection_factory):
            raise ValueError("Producer store requires a host-owned connection factory")
        self._connect = connection_factory
        self._read_role = _read_role

    def load(self, tenant_id: str, session_id: str, output_id: str) -> ProducerCase | None:
        """Read the exact scoped generation, then fail closed on invalid stored history."""
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    # One stable read snapshot avoids a false audit mismatch if a
                    # concurrent transaction commits between the two queries.
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", ())
                    if self._read_role is not None:
                        # Pin a trusted search path before reading application tables.
                        cursor.execute("SET LOCAL search_path TO pg_catalog, public", ())
                        cursor.execute(_READ_ONLY_ROLE_QUERY, ())
                        role = cursor.fetchone()
                        if (
                            role is None
                            or len(role) != 3
                            or role[0] != self._read_role
                            or role[1] != self._read_role
                            or role[2] is not True
                        ):
                            raise PermissionError(
                                "Producer inspection requires a pinned non-writing DB role"
                            )
                    cursor.execute(_LOAD, (tenant_id, session_id, output_id))
                    row = cursor.fetchone()
                    audit_rows: list[tuple[object, ...]] = []
                    if row is not None:
                        cursor.execute(_LOAD_AUDIT, (tenant_id, session_id, output_id))
                        audit_rows = cursor.fetchall()
            if row is None:
                return None
            if len(row) != 3 or type(row[0]) is not int or not isinstance(row[2], str):
                raise ValueError("Producer storage returned an invalid row")
            payload = row[1] if isinstance(row[1], (str, bytes)) else json.dumps(row[1])
            case = _CASE.validate_json(payload)
            _validate_case(case)
            if (
                case.tenant_id != tenant_id
                or case.output.session_id != session_id
                or case.output.output_id != output_id
                or case.generation != row[0]
                or _audit_digest(case.review.audit) != row[2]
            ):
                raise ValueError("Producer storage snapshot does not match its scope or audit")
            _reconcile_audit(case, audit_rows)
            return case
        finally:
            connection.close()

    def create(self, case: ProducerCase) -> bool:
        """Insert the initial unapproved review and first audit in one transaction."""
        _validate_case(case)
        if case.generation != 1 or case.review.status != "pending_verification":
            raise ValueError("New producer cases must begin unapproved at generation one")
        digest = _audit_digest(case.review.audit)
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        _CREATE,
                        (
                            case.tenant_id,
                            case.output.session_id,
                            case.output.output_id,
                            case.generation,
                            _case_json(case),
                            digest,
                        ),
                    )
                    if cursor.fetchone() is None:
                        return False
                    cursor.execute(
                        _APPEND_AUDIT,
                        (
                            case.tenant_id,
                            case.output.session_id,
                            case.output.output_id,
                            case.generation,
                            _ENTRY.dump_json(case.review.audit[-1]).decode("utf-8"),
                            digest,
                        ),
                    )
            return True
        finally:
            connection.close()

    def replace_if_generation(self, case: ProducerCase, *, expected_generation: int) -> bool:
        """Commit exactly one reviewed transition or reject any CAS/audit-chain race."""
        _validate_case(case)
        if expected_generation < 1 or case.generation != expected_generation + 1:
            raise ValueError("Producer CAS must advance exactly one positive generation")
        digest = _audit_digest(case.review.audit)
        prior_digest = _audit_digest(case.review.audit[:-1])
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        _COMPARE_AND_SWAP,
                        (
                            case.generation,
                            _case_json(case),
                            digest,
                            case.tenant_id,
                            case.output.session_id,
                            case.output.output_id,
                            expected_generation,
                            prior_digest,
                        ),
                    )
                    if cursor.fetchone() is None:
                        return False
                    cursor.execute(
                        _APPEND_AUDIT,
                        (
                            case.tenant_id,
                            case.output.session_id,
                            case.output.output_id,
                            case.generation,
                            _ENTRY.dump_json(case.review.audit[-1]).decode("utf-8"),
                            digest,
                        ),
                    )
            return True
        finally:
            connection.close()


    def create_with_execution_grant(self, case: ProducerCase, *, grant: ProducerGrantAttempt) -> bool:
        """Consume a locked grant with the initial case and audit in one transaction.

        This opt-in method is a future host-authenticated HTTP candidate; the
        legacy create method alone does not prove an execution-time grant.
        """
        _validate_case(case)
        if case.generation != 1 or case.review.status != "pending_verification":
            raise ValueError("New producer cases must begin unapproved at generation one")
        digest = _audit_digest(case.review.audit)
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    if not consume_execution_grant(cursor, attempt=grant, case=case, creating=True):
                        return False
                    cursor.execute(
                        _CREATE,
                        (
                            case.tenant_id,
                            case.output.session_id,
                            case.output.output_id,
                            case.generation,
                            _case_json(case),
                            digest,
                        ),
                    )
                    if cursor.fetchone() is None:
                        return False
                    cursor.execute(
                        _APPEND_AUDIT,
                        (
                            case.tenant_id,
                            case.output.session_id,
                            case.output.output_id,
                            case.generation,
                            _ENTRY.dump_json(case.review.audit[-1]).decode("utf-8"),
                            digest,
                        ),
                    )
            return True
        finally:
            connection.close()

    def replace_with_execution_grant(
        self, case: ProducerCase, *, expected_generation: int, grant: ProducerGrantAttempt
    ) -> bool:
        """Consume grant, CAS exact generation, and append audit in one transaction.

        Revocation committed before the grant UPDATE rejects the write. Once the
        grant row is locked, a concurrent revoker waits for the whole commit.
        """
        _validate_case(case)
        if (
            type(expected_generation) is not int
            or expected_generation < 1
            or case.generation != expected_generation + 1
            or type(grant) is not ProducerGrantAttempt
            or grant.expected_generation != expected_generation
        ):
            raise ValueError("Execution-grant CAS requires one exact positive generation")
        digest = _audit_digest(case.review.audit)
        prior_digest = _audit_digest(case.review.audit[:-1])
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    if not consume_execution_grant(cursor, attempt=grant, case=case, creating=False):
                        return False
                    cursor.execute(
                        _COMPARE_AND_SWAP,
                        (
                            case.generation,
                            _case_json(case),
                            digest,
                            case.tenant_id,
                            case.output.session_id,
                            case.output.output_id,
                            expected_generation,
                            prior_digest,
                        ),
                    )
                    if cursor.fetchone() is None:
                        return False
                    cursor.execute(
                        _APPEND_AUDIT,
                        (
                            case.tenant_id,
                            case.output.session_id,
                            case.output.output_id,
                            case.generation,
                            _ENTRY.dump_json(case.review.audit[-1]).decode("utf-8"),
                            digest,
                        ),
                    )
            return True
        finally:
            connection.close()

class ReadOnlyPostgresProducerReader:
    """Expose only scoped audited SELECTs through a pinned physical read role.

    The existing PostgreSQL case/audit verifier is reused without exporting its
    mutators. Role privileges are checked in the same repeatable-read snapshot.
    Host code must inject isolated credentials; nothing reads HTTP or environment.
    """

    def __init__(
        self, connection_factory: Callable[[], DbConnection], *, expected_role: str
    ) -> None:
        """Require an explicitly named non-writing MatchDesk database principal."""
        if (
            type(expected_role) is not str
            or _EXPECTED_ROLE.fullmatch(expected_role) is None
            or not callable(connection_factory)
        ):
            raise ValueError("A pinned non-writing MatchDesk DB reader role is required")
        self.__store = PostgresProducerCaseStore(connection_factory, _read_role=expected_role)

    def load(self, tenant_id: str, session_id: str, output_id: str) -> ProducerCase | None:
        """Load exact tenant/session/output under one checked read-only snapshot."""
        return self.__store.load(tenant_id, session_id, output_id)
