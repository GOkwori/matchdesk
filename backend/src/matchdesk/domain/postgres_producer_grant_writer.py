"""Default-unused host-owned writer for one exact scoped producer action grant.

This adapter does not authenticate users, verify Entra MFA, issue action grants,
expose HTTP endpoints or publish. Only a separately trusted host may supply a
HostVerifiedActor and a PostgreSQL connection to a pinned least-privilege login.
Actual grant consumption and case/audit commit occur in one DB function call.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from pydantic import TypeAdapter

from matchdesk.domain.postgres_producer_store import DbConnection, _audit_digest
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    ProducerCase,
    _authorize,
    _recompute_claims,
    _validate_case,
)
from matchdesk.domain.producer_review import ProducerAuditEntry

GrantAction = Literal["create", "edit", "reverify", "approve", "reject"]
_ROLE_NAME = re.compile(r"matchdesk_[a-z][a-z0-9_]{0,54}\Z")
_CAPABILITY = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
_CASE_ADAPTER = TypeAdapter(ProducerCase)
_ENTRY_ADAPTER = TypeAdapter(ProducerAuditEntry)

# PostgreSQL SECURITY DEFINER changes current_user only inside the function.
# Check both real session_user and current_user BEFORE invoking it. CI's SET ROLE
# impersonation from an owner is deliberately insufficient for this new adapter.
_PINNED_WRITER_QUERY = """
SELECT current_user::text, session_user::text,
       (
         r.rolcanlogin
         AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
                  OR r.rolreplication OR r.rolbypassrls)
         AND NOT EXISTS (
             SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid
         )
         AND NOT pg_catalog.has_database_privilege(
             current_database(), 'CREATE, TEMP'
         )
         -- Check all non-system schemas. An unrelated writable table or
         -- sequence is still unacceptable for this fixed-purpose workload.
         AND NOT EXISTS (
             SELECT 1 FROM pg_catalog.pg_namespace ns
             WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
               AND pg_catalog.has_schema_privilege(ns.oid, 'CREATE')
         )
         AND NOT EXISTS (
             SELECT 1 FROM pg_catalog.pg_class c
             JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
             WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
               AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
               AND (
                   pg_catalog.has_table_privilege(
                       c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'
                   )
                   OR pg_catalog.has_any_column_privilege(
                       c.oid, 'INSERT, UPDATE, REFERENCES'
                   )
               )
         )
         AND NOT EXISTS (
             SELECT 1 FROM pg_catalog.pg_class c
             JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
             WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
               AND c.relkind = 'S'
               AND pg_catalog.has_sequence_privilege(c.oid, 'USAGE, UPDATE')
         )
         AND pg_catalog.has_function_privilege(
             'public.matchdesk_commit_producer_grant('
             || 'text,text,text,text,text,text,text,text,bigint,text,text,jsonb,jsonb)',
             'EXECUTE'
         )
       )
FROM pg_catalog.pg_roles r WHERE r.rolname = current_user
"""

_COMMIT = """
SELECT public.matchdesk_commit_producer_grant(
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
)
"""
_AUDIT_ACTION: dict[str, str] = {
    "create": "review_started",
    "edit": "revision_opened",
    "reverify": "reverified",
    "approve": "approved",
    "reject": "rejected",
}


class PostgresProducerGrantWriter:
    """Invoke the database-owned single-use grant writer without a direct DML path.

    The host must prove actor provenance, freshness, MFA, tenant entitlement
    and human execution approval before calling this method. These cannot be
    established by constructing a Python dataclass or passing an HTTP header.
    """

    def __init__(
        self,
        connection_factory: Callable[[], DbConnection],
        *,
        expected_role: str,
    ) -> None:
        """Pin a single separately provisioned least-privilege workload login."""
        if not callable(connection_factory):
            raise ValueError("Atomic producer writer requires a trusted connection factory")
        if not _ROLE_NAME.fullmatch(expected_role):
            raise ValueError("Atomic producer writer requires a pinned non-owner role")
        self._connect = connection_factory
        self._expected_role = expected_role

    def commit(
        self,
        *,
        actor: HostVerifiedActor,
        case: ProducerCase,
        grant_id: str,
        command_id: str,
        action: GrantAction,
        expected_generation: int,
    ) -> bool:
        """Commit one version-bound action and consume its grant in one DB transaction.

        False means authorization, case CAS, or grant consumption was denied; no
        retry or publication is implied. Database exceptions fail closed and
        must be handled by the trusted host as unreconciled until read back.
        """
        if type(actor) is not HostVerifiedActor:
            raise PermissionError("Producer identity must come from a trusted host")
        if type(expected_generation) is not int or expected_generation < 0:
            raise ValueError("Producer grant requires a nonnegative exact generation")
        if not _CAPABILITY.fullmatch(grant_id) or not _CAPABILITY.fullmatch(command_id):
            raise ValueError("Producer grant and command IDs must be bounded opaque identifiers")
        if action not in _AUDIT_ACTION:
            raise ValueError("Producer grant action is unsupported")
        if (expected_generation == 0) != (action == "create"):
            raise ValueError("Producer creation requires generation zero and vice versa")

        # Typed objects may contain model_copy(update=...) bypasses; deserialize
        # from JSON to restore nested Pydantic constraints before any DB use.
        case = _CASE_ADAPTER.validate_json(_CASE_ADAPTER.dump_json(case))
        _authorize(actor, case.tenant_id, case.output.session_id)
        _validate_case(case)
        if (
            case.generation != expected_generation + 1
            or case.review.audit[-1].action != _AUDIT_ACTION[action]
            or case.review.audit[-1].actor_id != actor.subject
        ):
            raise ValueError("Producer action must match its exact audited generation")
        if action in ("reverify", "approve"):
            # Registered numeric claims must pass independent source verification.
            # This does NOT verify freeform prose or substitute for human approval.
            _recompute_claims(case)

        digest = _audit_digest(case.review.audit)
        prior_digest = _audit_digest(case.review.audit[:-1]) if expected_generation else None
        case_json = _CASE_ADAPTER.dump_json(case).decode("utf-8")
        entry_json = _ENTRY_ADAPTER.dump_json(case.review.audit[-1]).decode("utf-8")
        params: tuple[object, ...] = (
            grant_id,
            actor.subject,
            actor.issuer,
            case.tenant_id,
            case.output.session_id,
            case.output.output_id,
            action,
            command_id,
            expected_generation,
            prior_digest,
            digest,
            case_json,
            entry_json,
        )
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    # Bound lock waits and remove inherited session search paths.
                    cursor.execute("SET LOCAL statement_timeout = '15000ms'", ())
                    cursor.execute("SET LOCAL search_path TO pg_catalog, public", ())
                    cursor.execute(_PINNED_WRITER_QUERY, ())
                    role = cursor.fetchone()
                    if (
                        role is None
                        or len(role) != 3
                        or role[0] != self._expected_role
                        or role[1] != self._expected_role
                        or role[2] is not True
                    ):
                        raise PermissionError("Producer write requires a pinned restricted login")
                    cursor.execute(_COMMIT, params)
                    receipt = cursor.fetchone()
                    if receipt is None or len(receipt) != 1 or type(receipt[0]) is not bool:
                        raise RuntimeError("Producer grant writer returned an invalid receipt")
                    return receipt[0]
        finally:
            connection.close()
