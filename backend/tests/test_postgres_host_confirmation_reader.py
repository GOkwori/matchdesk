"""Read-only host confirmation store boundary; no live signing or HTTP."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from matchdesk.domain.postgres_host_confirmation_reader import (
    PostgresHostConfirmationReader,
)
from matchdesk.domain.producer_confirmation_provenance import HostConfirmationRecord

ROLE = "matchdesk_host_confirmation_reader_ci"
SCOPE = ("a" * 32, "ci-tenant")


class Db:
    """Synthetic PostgreSQL cursor exercising only fixed SQL role assertions."""

    def __init__(self, *, role=ROLE, allow=True, row=None):
        """Configure identity, isolation result and optional provenance row."""
        self.role = role
        self.allow = allow
        self.row = row
        self.calls = []
        self.closed = False

    def __call__(self):
        """Return this fake as a short-lived physical connection."""
        return self

    @contextmanager
    def transaction(self):
        """Represent a read-only repeatable-read database transaction."""
        yield

    @contextmanager
    def cursor(self):
        """Provide the minimal cursor contract."""
        yield self

    def execute(self, sql, params):
        """Record fixed SQL and bound values for negative authorization tests."""
        self.calls.append((sql, params))

    def fetchone(self):
        """Return simulated role privileges or immutable event state."""
        if "current_user::text" in self.calls[-1][0]:
            return self.role, self.role, self.allow
        return self.row

    def close(self):
        """Ensure the database connection is always released."""
        self.closed = True


def event(*, state="confirmed"):
    """Build an exact synthetic database event with UTC timestamps."""
    now = datetime.now(timezone.utc)
    return (
        SCOPE[0],
        SCOPE[1],
        "ci-operator",
        "https://issuer.invalid",
        "ci-session",
        "ci-output",
        "approve",
        2,
        "b" * 64,
        "c" * 64,
        "d" * 64,
        "e" * 32,
        "workforce_authenticated_custom_dialog",
        state,
        now,
        now,
    )


def test_reader_is_pinned_to_same_physical_role_and_scope():
    """Only the dedicated LOGIN may fetch an exact tenant-scoped confirmation."""
    db = Db(row=event())
    reader = PostgresHostConfirmationReader(db, expected_role=ROLE)
    proof = reader.read_verified_confirmation(confirmation_id=SCOPE[0], tenant_id=SCOPE[1])
    assert type(proof) is HostConfirmationRecord
    assert proof.state == "confirmed"
    assert proof.actor_id == "ci-operator"
    assert db.closed and len(db.calls) == 4
    assert "REPEATABLE READ, READ ONLY" in db.calls[0][0]
    assert "current_user::text" in db.calls[2][0]
    assert db.calls[3][1] == SCOPE
    assert "INSERT" not in db.calls[3][0] and "UPDATE" not in db.calls[3][0]


@pytest.mark.parametrize("role,allowed", [("matchdesk_owner", True), (ROLE, False)])
def test_reader_denies_impersonated_or_privileged_login(role, allowed):
    """A failed physical role or effective SQL privilege check stops SELECT."""
    db = Db(role=role, allow=allowed, row=event())
    reader = PostgresHostConfirmationReader(db, expected_role=ROLE)
    with pytest.raises(PermissionError, match="isolation"):
        reader.read_verified_confirmation(confirmation_id=SCOPE[0], tenant_id=SCOPE[1])
    assert db.closed and not any("LEFT JOIN" in sql for sql, _ in db.calls)


def test_reader_never_rewrites_terminal_revocation():
    """A terminal event is reported as revoked rather than dropped or cleared."""
    db = Db(row=event(state="revoked"))
    proof = PostgresHostConfirmationReader(db, expected_role=ROLE).read_verified_confirmation(
        confirmation_id=SCOPE[0], tenant_id=SCOPE[1]
    )
    assert proof is not None and proof.state == "revoked"
    assert any("LEFT JOIN" in sql for sql, _ in db.calls)


def test_wrong_tenant_cannot_select_event():
    """The requested tenant remains bound as a SQL parameter, not a string."""
    db = Db()
    proof = PostgresHostConfirmationReader(db, expected_role=ROLE).read_verified_confirmation(
        confirmation_id=SCOPE[0], tenant_id="other-tenant"
    )
    assert proof is None and db.calls[-1][1] == (SCOPE[0], "other-tenant")


@pytest.mark.parametrize(
    "scope",
    [
        ("", SCOPE[1]),
        ("a" * 31, SCOPE[1]),
        (SCOPE[0], ""),
        (SCOPE[0], " tenant"),
        (SCOPE[0], "x" * 97),
    ],
)
def test_invalid_scope_never_opens_database(scope):
    """Malformed tenant or confirmation IDs fail closed before a connection."""
    db = Db(row=event())
    reader = PostgresHostConfirmationReader(db, expected_role=ROLE)
    with pytest.raises(PermissionError):
        reader.read_verified_confirmation(confirmation_id=scope[0], tenant_id=scope[1])
    assert not db.calls and not db.closed


@pytest.mark.parametrize(
    "row",
    [
        ("incorrect",),
        (*event()[:14], "bad-time", "bad-time"),
        (*event()[:13], "unspecified", *event()[14:]),
    ],
)
def test_malformed_rows_are_never_trusted(row):
    """Type and schema drift cannot be treated as a confirmed human event."""
    db = Db(row=row)
    with pytest.raises(PermissionError, match="Malformed"):
        PostgresHostConfirmationReader(db, expected_role=ROLE).read_verified_confirmation(
            confirmation_id=SCOPE[0], tenant_id=SCOPE[1]
        )
    assert db.closed
