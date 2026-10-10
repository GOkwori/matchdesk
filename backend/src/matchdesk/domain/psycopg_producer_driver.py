"""Trusted-host Psycopg connection factory for the P3-05 producer-case store.

The caller supplies credentials from a protected secret source. This adapter never
authorizes a producer, accepts an HTTP token or enables publication.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import psycopg

from matchdesk.domain.postgres_producer_store import DbConnection


def producer_connection_factory(
    *, conninfo: str, connect_timeout: int = 5
) -> Callable[[], DbConnection]:
    """Create short-lived, explicitly transactional PostgreSQL connections.

    Using autocommit means transaction() owns the entire atomic state/audit write.
    Secrets are held by the host and must never be logged or interpolated into SQL.
    An empty DSN, unbounded timeout or externally supplied session options are
    not accepted by this narrow production-facing boundary.
    """
    if not conninfo.strip():
        raise ValueError("A protected PostgreSQL connection string is required")
    if not 1 <= connect_timeout <= 30:
        raise ValueError("PostgreSQL connect timeout must be between 1 and 30 seconds")

    def open_connection() -> DbConnection:
        """Open a new connection for one exact scoped store operation."""
        connection = psycopg.connect(
            conninfo, autocommit=True, connect_timeout=connect_timeout
        )
        return cast(DbConnection, connection)

    return open_connection
