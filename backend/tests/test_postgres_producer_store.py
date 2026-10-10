"""Offline SQL-boundary regressions for the PostgreSQL producer store.

The fake cursor models atomic PostgreSQL transaction results. A separate hosted
integration check must execute the migration against an actual PostgreSQL server.
"""

import copy
import json
from contextlib import contextmanager
from dataclasses import replace

import pytest
from matchdesk.domain.postgres_producer_store import PostgresProducerCaseStore
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    execute_producer_command,
    open_producer_case,
)
from matchdesk.domain.producer_preview import build_producer_desk_preview


def _actor() -> HostVerifiedActor:
    """Build host-verified identity as a test-only fixture, never from HTTP."""
    return HostVerifiedActor(
        subject="producer-1",
        tenant_id="tenant-1",
        issuer="https://issuer.example",
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )


def _case():
    """Construct one true metric-verified synthetic case at generation one."""
    preview = build_producer_desk_preview()
    return open_producer_case(
        actor=_actor(),
        tenant_id="tenant-1",
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )


class FakeDatabase:
    """Shared transaction-controlled state for two simulated PostgreSQL connections."""

    def __init__(self) -> None:
        """Start a fresh database with no review or audit rows."""
        self.cases = {}
        self.audit = {}
        self.fail_audit = False
        self.closed = 0
        self.statements = []

    def __call__(self):
        """Return a new independent connection sharing committed rows."""
        return FakeConnection(self)


class FakeConnection:
    """Transactional driver double that rolls back every failed append."""

    def __init__(self, database: FakeDatabase) -> None:
        """Bind one connection to a shared in-memory database."""
        self.db = database

    @contextmanager
    def transaction(self):
        """Restore the case and audit tables on any raised exception."""
        saved = (copy.deepcopy(self.db.cases), copy.deepcopy(self.db.audit))
        try:
            yield
        except Exception:
            self.db.cases, self.db.audit = saved
            raise

    @contextmanager
    def cursor(self):
        """Supply one cursor with an isolated latest fetch result."""
        yield FakeCursor(self.db)

    def close(self) -> None:
        """Track closure even on absent records, failures and thrown exceptions."""
        self.db.closed += 1


class FakeCursor:
    """Dispatch the four reviewed SQL statements while preserving bind parameters."""

    def __init__(self, database: FakeDatabase) -> None:
        """Remember the shared table and one prospective fetched row."""
        self.db = database
        self.result = None

    def execute(self, sql: str, parameters: tuple[object, ...]) -> None:
        """Emulate scoped SELECT, unique CREATE, exact CAS and atomic audit append."""
        self.db.statements.append((sql, parameters))
        self.result = None
        if sql.lstrip().startswith("SELECT generation"):
            self.result = self.db.cases.get(parameters)
        elif sql.lstrip().startswith("INSERT INTO matchdesk_producer_cases"):
            tenant, session, output, generation, payload, digest = parameters
            key = (tenant, session, output)
            if key not in self.db.cases:
                self.db.cases[key] = (generation, json.loads(payload), digest)
                self.result = (generation,)
        elif sql.lstrip().startswith("UPDATE matchdesk_producer_cases"):
            generation, payload, digest, tenant, session, output, expected, previous = parameters
            key = (tenant, session, output)
            current = self.db.cases.get(key)
            if current is not None and current[0] == expected and current[2] == previous:
                self.db.cases[key] = (generation, json.loads(payload), digest)
                self.result = (generation,)
        elif sql.lstrip().startswith("INSERT INTO matchdesk_producer_audit"):
            if self.db.fail_audit:
                raise RuntimeError("simulated audit insert failure")
            tenant, session, output, generation, entry, digest = parameters
            key = (tenant, session, output, generation)
            if key in self.db.audit:
                raise RuntimeError("duplicate audit generation")
            self.db.audit[key] = (json.loads(entry), digest)
        else:
            raise AssertionError("Unrecognised or unparameterized SQL command")

    def fetchone(self):
        """Return the row from this cursor's most recent SQL statement."""
        return self.result


def test_create_reload_review_and_audit_are_atomic() -> None:
    """A new case survives a read and one command writes an aligned audit generation."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    assert store.create(case) is True
    assert store.load("tenant-1", "demo-preview-only", "demo-story-output") == case
    updated = execute_producer_command(
        store,
        actor=_actor(),
        tenant_id="tenant-1",
        session_id="demo-preview-only",
        output_id="demo-story-output",
        expected_generation=1,
        command="reverify",
        reason="Source checked",
    )
    assert updated.generation == 2
    assert len(db.audit) == 2
    assert store.load("tenant-1", "demo-preview-only", "demo-story-output") == updated
    assert db.closed == 4


def test_duplicate_initial_insert_never_overwrites_history() -> None:
    """A second creator cannot reset an existing tenant-scoped case."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    assert store.create(case)
    assert not store.create(case)
    assert len(db.audit) == 1


def test_tenant_and_session_reads_cannot_leak_cases() -> None:
    """Every SELECT is bound to all three identity dimensions."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    assert store.create(_case())
    assert store.load("wrong-tenant", "demo-preview-only", "demo-story-output") is None
    assert store.load("tenant-1", "wrong-session", "demo-story-output") is None
    assert store.load("tenant-1", "demo-preview-only", "wrong-output") is None
    for sql, _ in db.statements:
        assert "FROM matchdesk_producer_cases" not in sql or (
            "tenant_id = %s" in sql and "session_id = %s" in sql and "output_id = %s" in sql
        )


def test_stale_generation_and_prior_audit_digest_reject_overwrite() -> None:
    """Stale or rewritten history cannot update an otherwise valid generation."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    original = _case()
    assert store.create(original)
    reviewed = execute_producer_command(
        store,
        actor=_actor(),
        tenant_id="tenant-1",
        session_id="demo-preview-only",
        output_id="demo-story-output",
        expected_generation=1,
        command="reverify",
        reason="Checked",
    )
    with pytest.raises(RuntimeError, match="generation"):
        execute_producer_command(
            store,
            actor=_actor(),
            tenant_id="tenant-1",
            session_id="demo-preview-only",
            output_id="demo-story-output",
            expected_generation=1,
            command="reverify",
            reason="Stale attempt",
        )
    forged = replace(reviewed, generation=reviewed.generation + 1)
    with pytest.raises(ValueError, match="audit entry"):
        store.replace_if_generation(forged, expected_generation=2)
    assert len(db.audit) == 2


def test_audit_insert_failure_rolls_back_case_mutation() -> None:
    """An audit failure must never leave a newer approved or reverified snapshot."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    assert store.create(case)
    db.fail_audit = True
    with pytest.raises(RuntimeError, match="audit"):
        execute_producer_command(
            store,
            actor=_actor(),
            tenant_id="tenant-1",
            session_id="demo-preview-only",
            output_id="demo-story-output",
            expected_generation=1,
            command="reverify",
            reason="Test rollback",
        )
    assert store.load("tenant-1", "demo-preview-only", "demo-story-output") == case
    assert len(db.audit) == 1


@pytest.mark.parametrize("failure", ["generation", "digest", "tenant", "payload"])
def test_corrupted_case_fails_closed_on_load(failure: str) -> None:
    """Loaded JSON and its generation/audit identity cannot be silently trusted."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    assert store.create(_case())
    key = ("tenant-1", "demo-preview-only", "demo-story-output")
    generation, data, digest = db.cases[key]
    if failure == "generation":
        db.cases[key] = (generation + 1, data, digest)
    elif failure == "digest":
        db.cases[key] = (generation, data, "0" * 64)
    elif failure == "tenant":
        data["tenant_id"] = "changed-tenant"
    else:
        data["review"]["status"] = "approved"
    with pytest.raises(ValueError):
        store.load(*key)


def test_create_refuses_approved_or_untrusted_case() -> None:
    """A preapproved snapshot is not an acceptable initial persistence operation."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    case = replace(case, review=replace(case.review, status="approved"))
    with pytest.raises(ValueError):
        store.create(case)
    assert not db.cases


def test_cas_rejects_skipped_or_negative_generation() -> None:
    """Storage transitions must move exactly one generation from a positive value."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    assert store.create(case)
    with pytest.raises(ValueError, match="exactly one"):
        store.replace_if_generation(case, expected_generation=-1)
