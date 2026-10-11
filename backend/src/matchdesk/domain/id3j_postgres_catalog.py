"""ID3J disposable PostgreSQL privilege inspection without execution authority.

Only a CI host may supply the independently established database connection.
This inspector re-reads actual PostgreSQL role and effective grant state; it
does not authenticate a human, attest a cluster, sign an approval or run a
migration. Passing an inspection never authorizes a mutating operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from psycopg import Connection

from matchdesk.domain.id3h_release_approval import ReleaseDenied

_DENIED = "ID3J disposable catalog preflight denied"
_DATABASE = "matchdesk_id3j_ci"
_ROLE = "matchdesk_id3j_reader_ci"

# Read effective capabilities rather than assuming that a GRANT/REVOKE command
# took effect. Include PUBLIC, inherited, column-level and routine privileges.
# pg_catalog/information_schema are excluded only from *application objects*;
# privileged built-in routines are not exposed through a caller-supplied query.
_CATALOG_QUERY = """
SELECT current_database()::text, current_user::text, session_user::text,
       r.rolcanlogin, r.rolsuper, r.rolcreatedb, r.rolcreaterole,
       r.rolreplication, r.rolbypassrls, r.rolinherit,
       EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid),
       pg_catalog.has_database_privilege(current_database(), 'CREATE'),
       pg_catalog.has_database_privilege(current_database(), 'TEMP'),
       EXISTS (
           SELECT 1 FROM pg_catalog.pg_namespace ns
           WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
             AND pg_catalog.has_schema_privilege(ns.oid, 'CREATE')
       ),
       EXISTS (
           SELECT 1 FROM pg_catalog.pg_class c
           JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
           WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
             AND CASE
                 -- The planner may reorder AND predicates: a privilege probe
                 -- must never be evaluated for an incompatible object kind.
                 WHEN c.relkind IN ('r', 'p', 'v', 'm', 'f') THEN
                     pg_catalog.has_table_privilege(
                         c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'
                     )
                     OR pg_catalog.has_any_column_privilege(
                         c.oid, 'INSERT, UPDATE, REFERENCES'
                     )
                 ELSE FALSE
             END
       ),
       EXISTS (
           SELECT 1 FROM pg_catalog.pg_class c
           JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
           WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
             AND CASE WHEN c.relkind = 'S'
                 THEN pg_catalog.has_sequence_privilege(c.oid, 'USAGE, UPDATE')
                 ELSE FALSE
             END
       ),
       EXISTS (
           SELECT 1 FROM pg_catalog.pg_proc p
           JOIN pg_catalog.pg_namespace ns ON ns.oid = p.pronamespace
           WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
             AND pg_catalog.has_function_privilege(p.oid, 'EXECUTE')
       )
FROM pg_catalog.pg_roles r WHERE r.rolname = current_user
"""
# Columns 3-16 are exact PostgreSQL booleans. The only permitted capability
# is a login session; no memberships, DDL, DML or application-routine execution.
_REQUIRED_FLAGS = (True,) + (False,) * 13


@dataclass(frozen=True, slots=True)
class DisposableCatalogReceipt:
    """Evidence of one CI-only read; an explicit denial of all database writes."""

    database: str
    physical_role: str
    environment: Literal["disposable-ci"] = "disposable-ci"
    execution_authorized: Literal[False] = False
    database_writes_authorized: Literal[False] = False


def inspect_disposable_catalog(
    connection: Connection[tuple[Any, ...]],
) -> DisposableCatalogReceipt:
    """Check real PostgreSQL grant state inside a read-only transaction.

    The connection is furnished by the isolated CI host, never an HTTP caller
    or AI tool. A real release must separately bind cluster identity, workload
    credentials, actor, tenant and approval at the mutation boundary.
    A failing database read or malformed driver result is always a denial.
    """
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                # This protects the probe itself even if the CI role is later
                # mistakenly granted DML. It does not make that role safe.
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(_CATALOG_QUERY)
                row = cursor.fetchone()
                if (
                    not isinstance(row, tuple)
                    or len(row) != 17
                    or type(row[0]) is not str
                    or row[0] != _DATABASE
                    or type(row[1]) is not str
                    or row[1] != _ROLE
                    or type(row[2]) is not str
                    or row[2] != row[1]
                    or any(type(flag) is not bool for flag in row[3:])
                    or row[3:] != _REQUIRED_FLAGS
                ):
                    raise ReleaseDenied(_DENIED)
        return DisposableCatalogReceipt(database=_DATABASE, physical_role=_ROLE)
    except Exception:
        # Never let a driver outage, permission error or spoofed result pass.
        raise ReleaseDenied(_DENIED) from None
