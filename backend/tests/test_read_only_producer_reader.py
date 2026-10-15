"""Fail-closed producer SQL reader qualification without live credentials."""

from unittest.mock import MagicMock

import pytest

from matchdesk.domain.postgres_producer_store import (
    ReadOnlyPostgresProducerReader,
    _READ_ONLY_ROLE_QUERY,
)

ROLE = "matchdesk_producer_reader"


def connection_for_role(observed):
    """Provide a disposable fake with a fixed physical PostgreSQL role verdict."""
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = observed
    return connection, cursor


@pytest.mark.parametrize(
    "role",
    ["", "postgres", "matchdesk_Reader", "matchdesk_reader;DROP", "other_reader"],
)
def test_constructor_rejects_unpinned_or_invalid_role(role):
    """A caller must specify an explicitly bounded MatchDesk physical reader."""
    with pytest.raises(ValueError, match="pinned non-writing"):
        ReadOnlyPostgresProducerReader(lambda: MagicMock(), expected_role=role)


@pytest.mark.parametrize(
    "observed",
    [
        None,
        (),
        ("matchdesk_other", ROLE, True),
        (ROLE, "postgres", True),
        (ROLE, ROLE, False),
        (ROLE, ROLE, 1),
        (ROLE, ROLE, None),
    ],
)
def test_denied_or_drifted_database_role_fails_before_case_select(observed):
    """No lookup may proceed after missing, elevated or ambiguous role verdict."""
    connection, cursor = connection_for_role(observed)
    reader = ReadOnlyPostgresProducerReader(lambda: connection, expected_role=ROLE)
    with pytest.raises(PermissionError, match="pinned non-writing"):
        reader.load("tenant-1", "demo-preview-only", "demo-story-output")
    sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert "SET LOCAL search_path TO pg_catalog, public" in sql
    assert _READ_ONLY_ROLE_QUERY in sql
    assert not any("FROM matchdesk_producer_cases" in text for text in sql)
    connection.close.assert_called_once()


def test_valid_role_permits_only_scoped_selects_and_returns_missing_case():
    """A permitted role cannot acquire mutation capability through this reader."""
    connection, cursor = connection_for_role((ROLE, ROLE, True))
    reader = ReadOnlyPostgresProducerReader(lambda: connection, expected_role=ROLE)
    assert reader.load("tenant-1", "demo-preview-only", "missing") is None
    sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert sql.index(_READ_ONLY_ROLE_QUERY) < next(
        i for i, query in enumerate(sql) if "FROM matchdesk_producer_cases" in query
    )
    assert not any(
        query.lstrip().startswith(("INSERT", "UPDATE", "DELETE", "TRUNCATE"))
        for query in sql
    )
    assert not hasattr(reader, "create")
    assert not hasattr(reader, "replace_if_generation")
    connection.close.assert_called_once()


def test_permission_query_checks_effective_database_capabilities():
    """Detect database-level and indirect role or DML privilege drift."""
    for part in (
        "current_user::text",
        "session_user::text",
        "rolsuper",
        "rolbypassrls",
        "pg_auth_members",
        "has_database_privilege",
        "has_schema_privilege",
        "has_table_privilege",
        "has_any_column_privilege",
        "has_sequence_privilege",
        "has_function_privilege",
        "matchdesk_producer_cases",
        "matchdesk_producer_audit",
    ):
        assert part in _READ_ONLY_ROLE_QUERY
