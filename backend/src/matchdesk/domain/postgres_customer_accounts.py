"""Read-only PostgreSQL binding from verified broker subject to registered account.

Registrations and changes require a separate reviewed provisioning authority.
The runtime never inserts, updates, deletes, links by email, or trusts a social
provider hint. Only an explicitly active, issuer/tenant/subject-bound row can
identify an existing customer account; it grants no producer permissions.
"""

from __future__ import annotations

from collections.abc import Callable

from matchdesk.domain.customer_identity import CustomerIdentityKey
from matchdesk.domain.postgres_producer_store import DbConnection

_LOOKUP = """
SELECT account_id
FROM matchdesk_customer_accounts
WHERE issuer = %s AND tenant_id = %s AND subject = %s AND state = 'active'
"""


class PostgresCustomerAccountDirectory:
    """Resolve customer identities with a read-only, least-privileged DB role.

    This is a customer-account lookup boundary, not account registration or
    authorization for an individual match. The host must supply a reviewed
    connection factory with SELECT-only access to this one table.
    """

    def __init__(self, connection_factory: Callable[[], DbConnection]) -> None:
        """Hold a host-owned connection factory, never a user-selected DSN."""
        if not callable(connection_factory):
            raise ValueError("Customer account directory requires a database factory")
        self._connect = connection_factory

    def lookup(self, *, issuer: str, tenant_id: str, subject: str) -> str | None:
        """Resolve one active immutable broker identity, failing closed on bad rows.

        Exact issuer, tenant and subject are all predicates. No email, upstream
        provider name, groups or token-supplied role is accepted as a key.
        """
        identity = CustomerIdentityKey(issuer=issuer, tenant_id=tenant_id, subject=subject)
        identity.__post_init__()
        if (
            not isinstance(identity.issuer, str)
            or not isinstance(identity.tenant_id, str)
            or not 1 <= len(identity.issuer) <= 512
            or not 1 <= len(identity.tenant_id) <= 96
            or identity.issuer != identity.issuer.strip()
            or identity.tenant_id != identity.tenant_id.strip()
        ):
            raise ValueError("Customer account lookup identity is malformed")
        connection = self._connect()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(_LOOKUP, identity.lookup_key)
                    result = cursor.fetchone()
                    if result is None:
                        return None
                    if not isinstance(result, tuple) or len(result) != 1:
                        raise PermissionError("Registered customer account row is untrusted")
                    account_id = result[0]
                    if (
                        not isinstance(account_id, str)
                        or not 1 <= len(account_id) <= 128
                        or account_id != account_id.strip()
                    ):
                        raise PermissionError("Registered customer account row is untrusted")
                    return account_id
        finally:
            connection.close()
