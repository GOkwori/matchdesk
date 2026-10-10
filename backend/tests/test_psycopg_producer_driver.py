"""Fail-closed checks for the host-owned Psycopg producer connection factory."""

from unittest.mock import MagicMock, patch

import pytest
from matchdesk.domain.psycopg_producer_driver import producer_connection_factory


@pytest.mark.parametrize("dsn", ["", " ", "\t\n"])
def test_empty_connection_configuration_is_rejected(dsn: str) -> None:
    """Missing protected DB credentials cannot silently fall back to a default."""
    with pytest.raises(ValueError, match="connection string"):
        producer_connection_factory(conninfo=dsn)


@pytest.mark.parametrize("timeout", [0, -1, 31, 120])
def test_timeout_is_bounded(timeout: int) -> None:
    """Network waits cannot run indefinitely at the producer command boundary."""
    with pytest.raises(ValueError, match="timeout"):
        producer_connection_factory(conninfo="host=localhost dbname=test", connect_timeout=timeout)


def test_connections_are_explicitly_autocommit_and_host_scoped() -> None:
    """Psycopg handles per-operation transaction() and cursor() contexts itself."""
    conn = MagicMock()
    with patch(
        "matchdesk.domain.psycopg_producer_driver.psycopg.connect", return_value=conn
    ) as call:
        factory = producer_connection_factory(
            conninfo="host=localhost dbname=synthetic", connect_timeout=7
        )
        assert factory() is conn
        assert factory() is conn
    assert call.call_count == 2
    call.assert_called_with("host=localhost dbname=synthetic", autocommit=True, connect_timeout=7)
