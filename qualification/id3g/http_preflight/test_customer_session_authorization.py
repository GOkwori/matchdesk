"""Current-account authorization regression tests for customer sessions."""

from datetime import datetime, timezone

import pytest
from matchdesk.domain.customer_identity import CustomerIdentityKey
from matchdesk.domain.customer_session_authorization import resolve_authorized_customer_session
from matchdesk.domain.customer_sessions import new_customer_session

NOW = datetime.now(timezone.utc)
IDENTITY = CustomerIdentityKey(
    issuer="https://demo.ciamlogin.com/example/v2.0",
    tenant_id="example",
    subject="exact-broker-subject",
)


class Store:
    """One server-owned session, with observable database lookups."""

    def __init__(self, record):
        """Seed one record without trusting an incoming cookie claim."""
        self.record = record

    def load(self, opaque_session_id):
        """Resolve only the exact stored bearer."""
        return self.record if self.record.session_id == opaque_session_id else None


class Directory:
    """Server-owned account state for an exact broker identity."""

    def __init__(self, account_id):
        """Keep the current account association separately from a session."""
        self.account_id = account_id
        self.lookups = []
        self.fail = False

    def lookup(self, *, issuer, tenant_id, subject):
        """Return an account only for the verified broker identity tuple."""
        self.lookups.append((issuer, tenant_id, subject))
        if self.fail:
            raise RuntimeError("private registry credentials")
        if (issuer, tenant_id, subject) != IDENTITY.lookup_key:
            return None
        return self.account_id


def test_active_registered_customer_can_use_existing_session() -> None:
    """An active registration authorizes exactly the matching account."""
    record = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    directory = Directory("account-1")
    assert (
        resolve_authorized_customer_session(
            record.session_id, store=Store(record), directory=directory, now=NOW
        )
        == record
    )
    assert directory.lookups == [IDENTITY.lookup_key]


@pytest.mark.parametrize("current_account", [None, "", "account-2", 123])
def test_inactive_unregistered_or_reassigned_account_fails_closed(current_account) -> None:
    """No historical bearer authenticates after account state/owner changes."""
    record = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    with pytest.raises(PermissionError):
        resolve_authorized_customer_session(
            record.session_id,
            store=Store(record),
            directory=Directory(current_account),
            now=NOW,
        )


def test_revoked_session_is_denied_before_registry_lookup() -> None:
    """A revoked bearer must not reach registry authorization."""
    record = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    object.__setattr__(record, "revoked", True)
    directory = Directory("account-1")
    with pytest.raises(PermissionError):
        resolve_authorized_customer_session(
            record.session_id, store=Store(record), directory=directory, now=NOW
        )
    assert directory.lookups == []


def test_unknown_session_is_denied_before_registry_lookup() -> None:
    """An unknown cookie is never grounds to look up an account."""
    record = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    directory = Directory("account-1")
    with pytest.raises(PermissionError):
        resolve_authorized_customer_session(
            "f" * 64, store=Store(record), directory=directory, now=NOW
        )
    assert directory.lookups == []


def test_registry_outage_never_falls_back_to_persisted_account() -> None:
    """The HTTP adapter must return a generic failure for directory outages."""
    record = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    directory = Directory("account-1")
    directory.fail = True
    with pytest.raises(RuntimeError, match="private registry credentials"):
        resolve_authorized_customer_session(
            record.session_id, store=Store(record), directory=directory, now=NOW
        )
