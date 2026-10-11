"""ID3J catalogue regression tests: deny forged, elevated and unavailable grants."""

from contextlib import contextmanager

import pytest
from matchdesk.domain.id3h_release_approval import ReleaseDenied
from matchdesk.domain.id3j_postgres_catalog import (
    DisposableCatalogReceipt,
    inspect_disposable_catalog,
)

GOOD = (
    "matchdesk_id3j_ci",
    "matchdesk_id3j_reader_ci",
    "matchdesk_id3j_reader_ci",
    True,
    *(False for _ in range(13)),
)


class Cursor:
    """Fake DB cursor only for parser-failure regression; not a live DB proof."""

    def __init__(self, row=GOOD, failure=False):
        """Preserve one exact row and optional injected database outage."""
        self.row = row
        self.failure = failure
        self.calls = []

    def __enter__(self):
        """Provide the standard context-manager surface."""
        return self

    def __exit__(self, *_):
        """Exit the disposable context."""
        return False

    def execute(self, query):
        """Record queries while simulating an unavailable catalog."""
        self.calls.append(query)
        if self.failure:
            raise OSError("private DB inaccessible")

    def fetchone(self):
        """Return the injected catalog observation."""
        return self.row


class Connection:
    """Synthetic connection: no database operation is performed by these tests."""

    def __init__(self, row=GOOD, failure=False):
        """Create the cursor fixture."""
        self.test_cursor = Cursor(row, failure)

    @contextmanager
    def transaction(self):
        """Model one isolated transaction."""
        yield

    def cursor(self):
        """Return the synthetic cursor fixture."""
        return self.test_cursor


def test_non_execution_receipt_and_read_only_transaction():
    """Successful inspection is deliberately not an execution grant."""
    conn = Connection()
    result = inspect_disposable_catalog(conn)
    assert result == DisposableCatalogReceipt(
        database="matchdesk_id3j_ci", physical_role="matchdesk_id3j_reader_ci"
    )
    assert result.execution_authorized is False
    assert result.database_writes_authorized is False
    assert conn.test_cursor.calls[0] == "SET TRANSACTION READ ONLY"
    assert "pg_catalog.pg_roles" in conn.test_cursor.calls[1]
    assert "has_any_column_privilege" in conn.test_cursor.calls[1]


def test_catalog_privilege_functions_are_guarded_by_object_kind():
    """Protect against PostgreSQL planner reordering and SQLSTATE 42809.

    Filtering with a separate AND c.relkind predicate is insufficient: the
    planner can evaluate has_sequence_privilege on a non-sequence pg_class row.
    The disposable integration workflow executes this query on real PostgreSQL.
    """
    conn = Connection()
    inspect_disposable_catalog(conn)
    query = conn.test_cursor.calls[1]
    assert "WHEN c.relkind IN ('r', 'p', 'v', 'm', 'f') THEN" in query
    assert "WHEN c.relkind = 'S'" in query
    assert "ELSE FALSE" in query
    assert query.count("ELSE FALSE") == 2


@pytest.mark.parametrize("column", range(4, 17))
def test_any_elevated_or_inherited_capability_is_denied(column):
    """One role, schema, table, column, sequence or routine right must block."""
    changed = list(GOOD)
    changed[column] = True
    with pytest.raises(ReleaseDenied, match="ID3J disposable catalog preflight denied"):
        inspect_disposable_catalog(Connection(tuple(changed)))


@pytest.mark.parametrize(
    "row",
    [
        None,
        (),
        GOOD[:-1],
        GOOD + (False,),
        ("other-db",) + GOOD[1:],
        (GOOD[0], "postgres") + GOOD[2:],
        GOOD[:2] + ("postgres",) + GOOD[3:],
        GOOD[:3] + (1,) + GOOD[4:],
        GOOD[:5] + ("false",) + GOOD[6:],
    ],
)
def test_identity_or_malformed_catalog_is_denied(row):
    """A mismatched database/session user or weakly typed flag never passes."""
    with pytest.raises(ReleaseDenied):
        inspect_disposable_catalog(Connection(row))


def test_catalog_outage_denied():
    """An unavailable PostgreSQL catalog never becomes a permissive success."""
    with pytest.raises(ReleaseDenied):
        inspect_disposable_catalog(Connection(failure=True))
