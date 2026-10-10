"""Offline session isolation, timeout and revocation regression tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from matchdesk.domain.customer_identity import CustomerIdentityKey
from matchdesk.domain.customer_sessions import (
    new_customer_session,
    resolve_customer_session,
)

NOW = datetime.now(timezone.utc)
IDENTITY = CustomerIdentityKey(
    issuer="https://demo.ciamlogin.com/example/v2.0",
    tenant_id="example",
    subject="broker-subject",
)


class Store:
    """Server-owned test store; never derives roles from incoming cookies."""

    def __init__(self, record):
        """Retain only one seeded trusted identity record."""
        self.record = record

    def load(self, opaque_session_id):
        """Return the record as though read from a transactional database."""
        del opaque_session_id
        return self.record


def test_new_session_is_opaque_unique_and_customer_only() -> None:
    """Session IDs cannot reuse customer identity, email, or upstream access tokens."""
    first = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    second = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    assert first.session_id != second.session_id
    assert len(first.session_id) == 64
    assert first.realm == "customer"
    assert first.account_id == "account-1"
    assert resolve_customer_session(first.session_id, store=Store(first), now=NOW) == first


@pytest.mark.parametrize(
    "change",
    [
        {"revoked": True},
        {"realm": "workforce"},
        {"session_id": "f" * 64},
        {"expires_at": NOW - timedelta(seconds=1)},
        {"last_seen_at": NOW - timedelta(hours=1)},
        {"account_id": " "},
        {"created_at": NOW - timedelta(hours=10)},
        {"created_at": NOW.replace(tzinfo=None)},
    ],
)
def test_invalid_or_revoked_server_sessions_never_authorize(change) -> None:
    """Privilege crossover, expiry, idle timeout and corrupt snapshots fail closed."""
    original = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    # Simulate a corrupted or forged persisted snapshot. dataclasses.replace()
    # would fail in __post_init__ before the resolver could exercise its
    # fail-closed revalidation of a retrieved record.
    for field, value in change.items():
        object.__setattr__(original, field, value)
    with pytest.raises(PermissionError):
        resolve_customer_session(original.session_id if "session_id" not in change else "a" * 64, store=Store(original), now=NOW)


@pytest.mark.parametrize("bad", [None, "", "x", "z" * 64, "0" * 63])
def test_missing_or_malformed_session_identifier_fails_closed(bad) -> None:
    """Malformed browser-controlled session material must not reach the store."""
    with pytest.raises(PermissionError):
        resolve_customer_session(bad, store=Store(None), now=NOW)


def test_unknown_session_is_not_auto_provisioned() -> None:
    """Successful broker sign-in alone cannot create an unregistered session."""
    with pytest.raises(PermissionError):
        resolve_customer_session("a" * 64, store=Store(None), now=NOW)


@pytest.mark.parametrize("ttl", [timedelta(0), timedelta(seconds=-1), timedelta(hours=9)])
def test_session_lifetime_is_bounded(ttl) -> None:
    """Session issuance cannot extend beyond the approved lifetime."""
    with pytest.raises(ValueError):
        new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW, ttl=ttl)


def test_expiry_boundary_is_exclusive() -> None:
    """A session expires precisely at the configured expiry instant."""
    value = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    with pytest.raises(PermissionError):
        resolve_customer_session(value.session_id, store=Store(value), now=value.expires_at)


def test_future_last_seen_is_not_accepted_as_active() -> None:
    """A future last-activity timestamp cannot extend the idle window."""
    active = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    forged = replace(active, last_seen_at=NOW + timedelta(minutes=5))
    with pytest.raises(PermissionError):
        resolve_customer_session(active.session_id, store=Store(forged), now=NOW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("account_id", object()),
        ("revoked", 0),
        ("created_at", "not-a-datetime"),
        ("identity", None),
        ("last_seen_at", None),
    ],
)
def test_malformed_persisted_types_fail_closed(field: str, value: object) -> None:
    """The trust boundary must revalidate types even if deserialization was bypassed."""
    active = new_customer_session(identity=IDENTITY, account_id="account-1", now=NOW)
    object.__setattr__(active, field, value)
    with pytest.raises(PermissionError):
        resolve_customer_session(active.session_id, store=Store(active), now=NOW)


def test_non_session_storage_response_is_rejected() -> None:
    """Malformed database row objects cannot impersonate a trusted session."""
    with pytest.raises(PermissionError, match="Invalid customer session record"):
        resolve_customer_session("a" * 64, store=Store(object()), now=NOW)
