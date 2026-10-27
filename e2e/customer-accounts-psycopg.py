"""Verify customer account registration using disposable real PostgreSQL."""

from __future__ import annotations

import os
import sys

import psycopg

from matchdesk.domain.customer_identity import CustomerIdentityKey, resolve_customer_account
from matchdesk.domain.postgres_customer_accounts import PostgresCustomerAccountDirectory
from matchdesk.domain.psycopg_producer_driver import producer_connection_factory

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://ci.ciamlogin.com/{TENANT}/v2.0"


def directory() -> PostgresCustomerAccountDirectory:
    """Connect using only the disposable CI SELECT-only role."""
    if os.environ.get("CI") != "true" or not os.environ.get("PGPASSWORD"):
        raise RuntimeError("Disposable CI credentials are mandatory")
    dsn = "host=postgres dbname=matchdesk user=matchdesk_customer_registry_ci sslmode=prefer"
    return PostgresCustomerAccountDirectory(producer_connection_factory(conninfo=dsn))


def qualify() -> None:
    """Reject inactive and foreign identities, then enforce SQL read-only grants."""
    accounts = directory()
    for subject, expected in (
        ("ci-registered", "ci-1"),
        ("ci-pending", None),
        ("ci-suspended", None),
        ("unknown", None),
    ):
        key = CustomerIdentityKey(issuer=ISSUER, tenant_id=TENANT, subject=subject)
        assert accounts.lookup(**dict(zip(("issuer", "tenant_id", "subject"), key.lookup_key))) == expected
        if expected is None:
            try:
                resolve_customer_account(key, directory=accounts)
            except PermissionError:
                pass
            else:
                raise AssertionError("Inactive identity passed customer session account gate")
        else:
            assert resolve_customer_account(key, directory=accounts) == expected
    assert accounts.lookup(issuer=ISSUER, tenant_id="foreign", subject="ci-registered") is None
    assert accounts.lookup(issuer=ISSUER + "changed", tenant_id=TENANT, subject="ci-registered") is None

    dsn = "host=postgres dbname=matchdesk user=matchdesk_customer_registry_ci sslmode=prefer"
    with psycopg.connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            for right, expected in (
                ("SELECT", True),
                ("INSERT", False),
                ("UPDATE", False),
                ("DELETE", False),
                ("TRUNCATE", False),
            ):
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, %s)",
                    ("matchdesk_customer_accounts", right),
                )
                assert cursor.fetchone() == (expected,)
            for table in (
                "matchdesk_customer_sessions",
                "matchdesk_oidc_login_attempts",
                "matchdesk_producer_cases",
            ):
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, 'SELECT')", (table,)
                )
                assert cursor.fetchone() == (False,)
            cursor.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
            assert cursor.fetchone() == (False,)
            cursor.execute(
                "SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = current_user"
            )
            assert cursor.fetchone() == (False, False)


def main() -> None:
    """Qualify before and after the existing database is restarted."""
    if len(sys.argv) != 2 or sys.argv[1] not in ("initial", "after-restart"):
        raise RuntimeError("Specify initial or after-restart")
    qualify()
    print("MATCHDESK_CUSTOMER_REGISTRY_" + sys.argv[1].upper().replace("-", "_") + "_PASS")


if __name__ == "__main__":
    main()
