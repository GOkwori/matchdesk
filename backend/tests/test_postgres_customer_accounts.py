"""Regression tests for the read-only PostgreSQL customer account directory."""

from unittest.mock import MagicMock

import pytest
from matchdesk.domain.postgres_customer_accounts import PostgresCustomerAccountDirectory

ISSUER = "https://tenant.ciamlogin.com/tenant/v2.0"
TENANT = "tenant"
SUBJECT = "broker-subject"


class Connection:
    """Mock a single bounded database transaction."""

    def __init__(self, result):
        """Capture statements and ensure all connections are closed."""
        self.cursor_obj = MagicMock()
        self.cursor_obj.fetchone.return_value = result
        self.closed = False

    def transaction(self):
        """Return transaction context."""
        return MagicMock()

    def cursor(self):
        """Return cursor context."""
        context = MagicMock()
        context.__enter__.return_value = self.cursor_obj
        return context

    def close(self):
        """Track unconditional cleanup."""
        self.closed = True


def test_exact_broker_identity_resolves_only_active_registration():
    """SQL must bind issuer, tenant and subject, not profile email."""
    db = Connection(("account-1",))
    result = PostgresCustomerAccountDirectory(lambda: db).lookup(
        issuer=ISSUER, tenant_id=TENANT, subject=SUBJECT
    )
    assert result == "account-1"
    sql, params = db.cursor_obj.execute.call_args.args
    assert params == (ISSUER, TENANT, SUBJECT)
    assert "state = 'active'" in sql
    assert "email" not in sql.lower()
    assert db.closed


@pytest.mark.parametrize("row", [None, (), (None,), ("",), (" invalid",), (123,), ("x" * 129,), ("a", "b")])
def test_missing_or_corrupt_rows_fail_closed(row):
    """Unknown accounts return None; malformed results cannot authenticate."""
    db = Connection(row)
    lookup = lambda: PostgresCustomerAccountDirectory(lambda: db).lookup(
        issuer=ISSUER, tenant_id=TENANT, subject=SUBJECT
    )
    if row is None:
        assert lookup() is None
    else:
        with pytest.raises(PermissionError):
            lookup()
    assert db.closed


def test_database_error_is_not_treated_as_registration():
    """Storage errors cannot authenticate and must close connections."""
    db = Connection(("account-1",))
    db.cursor_obj.execute.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError):
        PostgresCustomerAccountDirectory(lambda: db).lookup(
            issuer=ISSUER, tenant_id=TENANT, subject=SUBJECT
        )
    assert db.closed
