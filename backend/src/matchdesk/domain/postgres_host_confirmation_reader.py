"""Read-only PostgreSQL adapter for host-confirmation provenance (DEV-only).

This reader does NOT authenticate a person or mint signed approvals. Its caller
must provide a dedicated, physically authenticated SELECT-only PostgreSQL role.
A SQL row can corroborate a separately verified signed confirmation, but the
authenticity of the host writer still requires independent human/operator UAT.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal, cast

from matchdesk.domain.postgres_producer_store import DbConnection
from matchdesk.domain.producer_confirmation_provenance import HostConfirmationRecord
from matchdesk.domain.producer_grant_preflight import GrantAction

_ROLE = re.compile(r"matchdesk_[a-z][a-z0-9_]{0,54}\Z")
_ID = re.compile(r"[a-f0-9]{32}\Z")
_PIN = """
SELECT current_user::text, session_user::text,
    (
      r.rolcanlogin AND NOT (
        r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
        OR r.rolreplication OR r.rolbypassrls
      )
      AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member=r.oid
      )
      AND NOT pg_catalog.has_database_privilege(current_database(), 'CREATE, TEMP')
      AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_namespace n
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND pg_catalog.has_schema_privilege(n.oid, 'CREATE')
      )
      AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND CASE WHEN c.relkind IN ('r','p','v','m','f') THEN
            pg_catalog.has_table_privilege(
              c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'
            )
            OR pg_catalog.has_any_column_privilege(
              c.oid, 'INSERT, UPDATE, REFERENCES'
            )
          WHEN c.relkind='S' THEN
            pg_catalog.has_sequence_privilege(c.oid, 'USAGE, UPDATE')
          ELSE FALSE END
      )
      AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND c.relkind IN ('r','p','v','m','f')
          AND pg_catalog.has_table_privilege(c.oid, 'SELECT')
          AND c.oid NOT IN (
            'public.matchdesk_producer_host_confirmation_events'::regclass,
            'public.matchdesk_producer_host_confirmation_terminals'::regclass
          )
      )
      AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='public'
          AND pg_catalog.has_function_privilege(p.oid,'EXECUTE')
      )
      AND pg_catalog.has_table_privilege(
        'public.matchdesk_producer_host_confirmation_events','SELECT'
      )
      AND pg_catalog.has_table_privilege(
        'public.matchdesk_producer_host_confirmation_terminals','SELECT'
      )
    )
FROM pg_catalog.pg_roles r WHERE r.rolname=current_user
"""
_READ = """
SELECT e.confirmation_id, e.tenant_id, e.actor_id, e.token_issuer,
       e.session_id, e.output_id, e.action, e.expected_generation,
       e.authorized_case_sha256, e.authorized_audit_digest,
       e.signed_envelope_sha256, e.event_id, e.event_channel,
       CASE WHEN t.terminal_state IS NULL THEN 'confirmed'
            ELSE t.terminal_state END,
       e.confirmed_at, e.recorded_at
FROM public.matchdesk_producer_host_confirmation_events e
LEFT JOIN public.matchdesk_producer_host_confirmation_terminals t
    ON t.confirmation_id=e.confirmation_id AND t.tenant_id=e.tenant_id
WHERE e.confirmation_id=%s AND e.tenant_id=%s
"""


class PostgresHostConfirmationReader:
    """Scoped SELECT-only provenance reader with physical role drift detection."""

    def __init__(
        self, connection_factory: Callable[[], DbConnection], *, expected_role: str
    ) -> None:
        """Require a host-supplied login factory and pinned restricted role."""
        if not callable(connection_factory) or not _ROLE.fullmatch(expected_role):
            raise ValueError("Provenance reader requires a pinned restricted login")
        self._connect = connection_factory
        self._role = expected_role

    def read_verified_confirmation(
        self, *, confirmation_id: str, tenant_id: str
    ) -> HostConfirmationRecord | None:
        """Read one tenant-scoped event + terminal state under a stable snapshot.

        Unknown or invalid database outcomes deny authorization. The caller
        never chooses the SQL principal, query, event channel or evidence state.
        """
        if (
            type(confirmation_id) is not str
            or _ID.fullmatch(confirmation_id) is None
            or type(tenant_id) is not str
            or not 1 <= len(tenant_id) <= 96
            or tenant_id != tenant_id.strip()
        ):
            raise PermissionError("Host confirmation read denied")
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", ()
                    )
                    cursor.execute("SET LOCAL search_path TO pg_catalog, public", ())
                    cursor.execute(_PIN, ())
                    role = cursor.fetchone()
                    if (
                        role is None or len(role) != 3
                        or role[0] != self._role
                        or role[1] != self._role
                        or role[2] is not True
                    ):
                        raise PermissionError("Provenance reader login lacks isolation")
                    cursor.execute(_READ, (confirmation_id, tenant_id))
                    row = cursor.fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        if (
            not isinstance(row, tuple)
            or len(row) != 16
            or not isinstance(row[14], datetime)
            or not isinstance(row[15], datetime)
            or row[14].tzinfo is None
            or row[15].tzinfo is None
        ):
            raise PermissionError("Malformed host provenance database record")
        # PostgreSQL provides dynamic row values; strictly narrow every field
        # before constructing trusted provenance (no implicit coercion).
        string_columns = (0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13)
        if (
            any(type(row[index]) is not str for index in string_columns)
            or type(row[7]) is not int
            or row[6] not in ("create", "edit", "reverify", "approve", "reject")
            or row[12] != "workforce_authenticated_custom_dialog"
            or row[13] not in ("confirmed", "revoked", "cancelled")
        ):
            raise PermissionError("Malformed host provenance database record")
        try:
            return HostConfirmationRecord(
                confirmation_id=cast(str, row[0]),
                tenant_id=cast(str, row[1]),
                actor_id=cast(str, row[2]),
                token_issuer=cast(str, row[3]),
                session_id=cast(str, row[4]),
                output_id=cast(str, row[5]),
                action=cast(GrantAction, row[6]),
                expected_generation=cast(int, row[7]),
                authorized_case_sha256=cast(str, row[8]),
                authorized_audit_digest=cast(str, row[9]),
                signed_envelope_sha256=cast(str, row[10]),
                event_id=cast(str, row[11]),
                event_channel="workforce_authenticated_custom_dialog",
                state=cast(Literal["confirmed", "revoked", "cancelled"], row[13]),
                confirmed_at_seconds=int(
                    cast(datetime, row[14]).astimezone(timezone.utc).timestamp()
                ),
                recorded_at_seconds=int(
                    cast(datetime, row[15]).astimezone(timezone.utc).timestamp()
                ),
            )
        except Exception:
            raise PermissionError("Malformed host provenance database record") from None
