"""Offline checks for the default-unused restricted producer grant host adapter.

These tests cannot prove live Entra/MFA, a genuine identity provider, or a real
PostgreSQL execution role. Real restricted-login integration remains required.
"""

import json
from contextlib import contextmanager
from dataclasses import replace

import pytest
from matchdesk.domain.postgres_producer_grant_writer import PostgresProducerGrantWriter
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    apply_producer_command,
    open_producer_case,
)
from matchdesk.domain.producer_preview import build_producer_desk_preview

_ROLE = "matchdesk_grant_executor"
_GRANT = "grant-ci-1234567890"
_COMMAND = "command-ci-12345678"


def _actor() -> HostVerifiedActor:
    """Create an offline-only principal; never parse one from user input."""
    return HostVerifiedActor(
        subject="ci-producer",
        tenant_id="ci-tenant",
        issuer="https://ci-issuer.example.invalid",
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )


def _case():
    """Create valid source-bound synthetic metrics and generation-one audit."""
    preview = build_producer_desk_preview()
    return open_producer_case(
        actor=_actor(),
        tenant_id="ci-tenant",
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )


class FakeConnection:
    """Minimal unit-test driver that records bounded SQL and role verification."""

    def __init__(
        self,
        *,
        role: tuple[object, object, object] = (_ROLE, _ROLE, True),
        outcome: object = True,
        error: Exception | None = None,
    ) -> None:
        """Keep unit-test responses separate from any real database session."""
        self.role = role
        self.outcome = outcome
        self.error = error
        self.queries: list[tuple[str, tuple[object, ...]]] = []
        self.last_query = ""
        self.closed = False
        self.transactions = 0
        self.rollback = False

    def __call__(self):
        """Expose a new-connection factory for the unmounted writer."""
        return self

    @contextmanager
    def transaction(self):
        """Simulate transactional success or fail-closed rollback."""
        self.transactions += 1
        try:
            yield
        except Exception:
            self.rollback = True
            raise

    @contextmanager
    def cursor(self):
        """Supply this deterministic cursor to the fake connection."""
        yield self

    def execute(self, sql: str, parameters: tuple[object, ...]) -> None:
        """Record statement arguments and optionally inject a database error."""
        self.last_query = sql
        self.queries.append((sql, parameters))
        if "matchdesk_commit_producer_grant(" in sql and self.error is not None:
            raise self.error

    def fetchone(self):
        """Return the distinct physical role or atomic function result."""
        if "SELECT current_user::text" in self.last_query:
            return self.role
        if "SELECT public.matchdesk_commit_producer_grant(" in self.last_query:
            return (self.outcome,)
        raise AssertionError("Unexpected SQL result fetch")

    def close(self) -> None:
        """Verify the connection closes on every success or failure path."""
        self.closed = True


def _writer(db: FakeConnection) -> PostgresProducerGrantWriter:
    """Use a fixed dedicated writer role, never the database owner."""
    return PostgresProducerGrantWriter(db, expected_role=_ROLE)


def _commit(db: FakeConnection, **overrides):
    """Invoke the exact synthetic first-generation writer call."""
    params = {
        "actor": _actor(),
        "case": _case(),
        "grant_id": _GRANT,
        "command_id": _COMMAND,
        "action": "create",
        "expected_generation": 0,
    }
    params.update(overrides)
    return _writer(db).commit(**params)


def test_success_binds_exact_actor_issuer_scope_case_and_audit() -> None:
    """A verified host-bound action produces one parameterized DB operation."""
    db = FakeConnection()
    assert _commit(db) is True
    assert db.closed and db.transactions == 1 and not db.rollback
    statements = [sql for sql, _ in db.queries]
    assert len(statements) == 4
    assert "SET LOCAL statement_timeout" in statements[0]
    assert "SET LOCAL search_path" in statements[1]
    assert "SELECT current_user::text" in statements[2]
    assert "SELECT public.matchdesk_commit_producer_grant(" in statements[3]
    sql, values = db.queries[-1]
    assert _GRANT not in sql and _COMMAND not in sql
    assert len(values) == 13
    assert values[:3] == (_GRANT, "ci-producer", "https://ci-issuer.example.invalid")
    assert values[3:8] == (
        "ci-tenant",
        "demo-preview-only",
        _case().output.output_id,
        "create",
        _COMMAND,
    )
    assert values[8] == 0 and values[9] is None
    assert len(values[10]) == 64
    assert json.loads(values[11])["review"]["status"] == "pending_verification"
    assert json.loads(values[12])["action"] == "review_started"


def test_denied_grant_returns_false_not_approval() -> None:
    """An exhausted, revoked or mismatched capability grants no write."""
    db = FakeConnection(outcome=False)
    assert _commit(db) is False
    assert db.closed and not db.rollback


@pytest.mark.parametrize(
    "bad_role",
    [
        ("matchdesk_database_owner", _ROLE, True),
        (_ROLE, "matchdesk_database_owner", True),
        (_ROLE, _ROLE, False),
        (_ROLE, _ROLE, 1),
    ],
)
def test_different_or_privileged_database_login_denied(bad_role) -> None:
    """SET ROLE from an owner never satisfies real session-user pinning."""
    db = FakeConnection(role=bad_role)
    with pytest.raises(PermissionError, match="pinned restricted login"):
        _commit(db)
    assert db.closed and db.rollback
    assert all("SELECT public.matchdesk_commit_producer_grant(" not in sql for sql, _ in db.queries)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("grant_id", "weak"),
        ("grant_id", "evil token with whitespace"),
        ("command_id", ""),
        ("expected_generation", True),
        ("expected_generation", -1),
        ("expected_generation", 1),
        ("action", "publish"),
        ("action", "approve"),
    ],
)
def test_invalid_action_or_capability_rejected_before_connection(field: str, value) -> None:
    """Reject malformed grants or inconsistent action/generation before DB use."""
    db = FakeConnection()
    with pytest.raises(ValueError):
        _commit(db, **{field: value})
    assert db.transactions == 0
    assert not db.queries


def test_tenant_mismatch_denied_before_database_call() -> None:
    """A valid producer cannot mutate another tenant's case."""
    db = FakeConnection()
    bad_actor = replace(_actor(), tenant_id="foreign-tenant")
    with pytest.raises(PermissionError):
        _commit(db, actor=bad_actor)
    assert db.transactions == 0


def test_draft_case_cannot_be_claimed_as_approved() -> None:
    """An unverified case cannot be forged into an approved review state."""
    db = FakeConnection()
    case = _case()
    forged = replace(case, review=replace(case.review, status="approved"))
    with pytest.raises(ValueError, match="review state"):
        _commit(db, case=forged)
    assert db.transactions == 0


def test_reverification_recomputes_source_before_sql() -> None:
    """A verifiable generation-two producer transition reaches the DB function."""
    db = FakeConnection()
    case = _case()
    reverified = apply_producer_command(
        case,
        actor=_actor(),
        expected_generation=1,
        command="reverify",
        reason="offline metric reverified",
    )
    assert _commit(db, case=reverified, action="reverify", expected_generation=1) is True
    assert db.queries[-1][1][6] == "reverify"
    assert db.queries[-1][1][8] == 1
    assert isinstance(db.queries[-1][1][9], str)


def test_db_exception_rolls_back_and_connection_closes() -> None:
    """An unknown database outcome is never treated as an authorized receipt."""
    db = FakeConnection(error=RuntimeError("injected DB rejection"))
    with pytest.raises(RuntimeError, match="injected DB rejection"):
        _commit(db)
    assert db.rollback and db.closed


def test_malformed_receipt_fails_closed() -> None:
    """No integer truthiness, text or missing result grants an action."""
    db = FakeConnection(outcome=1)
    with pytest.raises(RuntimeError, match="invalid receipt"):
        _commit(db)
    assert db.rollback and db.closed


def test_constructing_writer_rejects_unpinned_owner() -> None:
    """An application cannot use the database owner's login by default."""
    db = FakeConnection()
    with pytest.raises(ValueError, match="non-owner role"):
        PostgresProducerGrantWriter(db, expected_role="matchdesk")
    assert not db.queries
