"""Tenant-scoped PostgreSQL producer review storage with transactional audit.

The host supplies a reviewed PostgreSQL driver and trusted connection factory.
This module cannot authenticate an actor or publish; caller authorization remains
the responsibility of execute_producer_command and the future HTTP identity edge.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from pydantic import TypeAdapter

from matchdesk.domain.producer_commands import ProducerCase, _validate_case
from matchdesk.domain.producer_review import ProducerAuditEntry


class DbCursor(Protocol):
    """Limited DB-API operations required for PostgreSQL parameterized statements."""

    def execute(self, sql: str, parameters: tuple[object, ...]) -> object:
        """Execute one parameterized statement without interpolating identifiers."""

    def fetchone(self) -> tuple[object, ...] | None:
        """Read one row, or None if the exact-generation write did not apply."""


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


def _audit_digest(entries: tuple[ProducerAuditEntry, ...]) -> str:
    """Hash the entire ordered audit history to detect rewritten prior transitions."""
    return hashlib.sha256(_AUDIT.dump_json(entries)).hexdigest()


def _case_json(case: ProducerCase) -> str:
    """Serialize the immutable case, including the evidence and verified claim objects."""
    return _CASE.dump_json(case).decode("utf-8")


class PostgresProducerCaseStore:
    """Atomically persist a case and its append-only audit for one exact tenant/session.

    The caller must run open_producer_case or execute_producer_command with a
    host-authenticated actor; the store is a persistence adapter, not a permission
    decision point. No driver installation or database creation occurs here.
    """

    def __init__(self, connection_factory: Callable[[], DbConnection]) -> None:
        """Accept a trusted connection factory without embedding a DSN or credential."""
        self._connect = connection_factory

    def load(self, tenant_id: str, session_id: str, output_id: str) -> ProducerCase | None:
        """Read the exact scoped generation, then fail closed on invalid stored history."""
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(_LOAD, (tenant_id, session_id, output_id))
                    row = cursor.fetchone()
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
