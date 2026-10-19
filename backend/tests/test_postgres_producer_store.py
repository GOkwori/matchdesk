"""Offline SQL-boundary regressions for the PostgreSQL producer store.

The fake cursor models atomic PostgreSQL transaction results. A separate hosted
integration check must execute the migration against an actual PostgreSQL server.
"""

import copy
import json
from contextlib import contextmanager
from dataclasses import replace
from uuid import UUID

import pytest
from matchdesk.domain.postgres_producer_store import PostgresProducerCaseStore
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.producer_execution_grants import ProducerGrantAttempt
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    apply_producer_command,
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
        self.grants = {}
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
        saved = (copy.deepcopy(self.db.cases), copy.deepcopy(self.db.audit), copy.deepcopy(self.db.grants))
        try:
            yield
        except Exception:
            self.db.cases, self.db.audit, self.db.grants = saved
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
        self.rows: list[tuple[object, ...]] = []

    def execute(self, sql: str, parameters: tuple[object, ...]) -> None:
        """Emulate scoped SELECT, unique CREATE, exact CAS and atomic audit append."""
        self.db.statements.append((sql, parameters))
        self.result = None
        self.rows = []
        if sql.lstrip().startswith("UPDATE matchdesk_producer_execution_grants"):
            if self.db.grants.get(parameters) == "active":
                self.db.grants[parameters] = "consumed"
                self.result = (UUID(parameters[0]),)
            return
        if sql.lstrip().startswith("SET TRANSACTION ISOLATION LEVEL"):
            return
        if sql.lstrip().startswith("SELECT generation, entry_json, audit_digest"):
            tenant, session, output = parameters
            self.rows = [
                (generation, entry, digest)
                for (t, s, o, generation), (entry, digest) in sorted(self.db.audit.items())
                if (t, s, o) == (tenant, session, output)
            ]
        elif sql.lstrip().startswith("SELECT generation"):
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

    def fetchall(self) -> list[tuple[object, ...]]:
        """Return separately stored rows for the independently scoped audit query."""
        return self.rows


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
    assert db.closed == 5


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


def test_malformed_storage_row_is_rejected_before_deserializing() -> None:
    """A broken database cursor must never return a trusted producer snapshot."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    assert store.create(case)
    key = ("tenant-1", "demo-preview-only", "demo-story-output")
    db.cases[key] = ("1", {}, "0" * 64)
    with pytest.raises(ValueError, match="invalid row"):
        store.load(*key)


def test_failed_cas_with_changed_prior_audit_digest_does_not_append() -> None:
    """A same-generation snapshot with a different audit root rejects the write."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    assert store.create(case)
    key = ("tenant-1", "demo-preview-only", "demo-story-output")
    generation, content, _ = db.cases[key]
    db.cases[key] = (generation, content, "f" * 64)
    updated = apply_producer_command(
        case,
        actor=_actor(),
        expected_generation=1,
        command="reverify",
        reason="Check audit drift",
    )
    assert not store.replace_if_generation(updated, expected_generation=1)
    assert len(db.audit) == 1


@pytest.mark.parametrize(
    "corruption",
    ["missing", "forged_actor", "wrong_digest", "wrong_generation", "extra"],
)
def test_append_only_audit_must_match_independent_case_snapshot(corruption: str) -> None:
    """Valid-looking case JSON cannot conceal absent, forged or extra audit rows."""
    database = FakeDatabase()
    store = PostgresProducerCaseStore(database)
    case = _case()
    assert store.create(case)
    key = ("tenant-1", "demo-preview-only", "demo-story-output", 1)
    entry, digest = database.audit[key]
    if corruption == "missing":
        del database.audit[key]
    elif corruption == "forged_actor":
        entry["actor_id"] = "fabricated-actor"
    elif corruption == "wrong_digest":
        database.audit[key] = (entry, "0" * 64)
    elif corruption == "wrong_generation":
        del database.audit[key]
        database.audit[(*key[:3], 2)] = (entry, digest)
    else:
        database.audit[(*key[:3], 2)] = (entry, digest)
    with pytest.raises(ValueError, match="audit"):
        store.load(*key[:3])


def _grant_for(case, *, action="create", generation=0, grant_id=None):
    """Use a test-only UUID and exact host-derived binding; never a browser grant."""
    binding = case.output.binding if action == "create" else case.review.audit[-2].binding
    return ProducerGrantAttempt(
        grant_id=grant_id or UUID("11111111-2222-4333-8444-555555555555"),
        actor=_actor(),
        action=action,
        session_id=case.output.session_id,
        output_id=case.output.output_id,
        binding=binding,
        expected_generation=generation,
    )


def _register_grant(db, attempt, *, state="active"):
    """Model an independently stored issuer-owned row, not a resolver boolean."""
    db.grants[
        (
            str(attempt.grant_id),
            attempt.actor.tenant_id,
            attempt.actor.subject,
            attempt.actor.issuer,
            attempt.action,
            attempt.session_id,
            attempt.output_id,
            attempt.expected_generation,
            content_digest(attempt.binding),
        )
    ] = state


def test_locked_create_grant_denies_absence_revocation_replay_and_wrong_scope() -> None:
    """An exact one-time grant must be present and active at the write boundary."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    attempt = _grant_for(case)
    assert not store.create_with_execution_grant(case, grant=attempt)
    _register_grant(db, attempt, state="revoked")
    assert not store.create_with_execution_grant(case, grant=attempt)
    assert not db.cases and not db.audit
    _register_grant(db, attempt)
    assert store.create_with_execution_grant(case, grant=attempt)
    assert len(db.cases) == len(db.audit) == 1
    assert not store.create_with_execution_grant(case, grant=attempt)
    assert len(db.audit) == 1


def test_grant_cannot_retarget_an_actor_or_a_different_binding() -> None:
    """Wrong actor and version/content binding are rejected before SQL mutation."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    attempt = _grant_for(case)
    _register_grant(db, attempt)
    foreign = replace(attempt, actor=replace(attempt.actor, tenant_id="other-tenant"))
    with pytest.raises(PermissionError, match="scope"):
        store.create_with_execution_grant(case, grant=foreign)
    other_binding = attempt.binding.model_copy(update={"item_version": 999})
    with pytest.raises(PermissionError, match="initial"):
        store.create_with_execution_grant(case, grant=replace(attempt, binding=other_binding))
    assert not db.cases and not db.audit


def test_grant_and_case_audit_rollback_together_on_insert_failure() -> None:
    """A failed audit cannot commit a consumed grant or an unaudited case."""
    db = FakeDatabase()
    db.fail_audit = True
    store = PostgresProducerCaseStore(db)
    case = _case()
    attempt = _grant_for(case)
    _register_grant(db, attempt)
    with pytest.raises(RuntimeError, match="audit"):
        store.create_with_execution_grant(case, grant=attempt)
    assert not db.cases and not db.audit
    assert "active" in db.grants.values()


def test_locked_reverification_grant_uses_previous_binding_and_cas() -> None:
    """An exact generation-bound grant permits one reverify, not cross-action reuse."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    assert store.create(case)
    updated = apply_producer_command(
        case, actor=_actor(), expected_generation=1, command="reverify", reason="Checked"
    )
    attempt = _grant_for(updated, action="reverify", generation=1)
    assert not store.replace_with_execution_grant(
        updated, expected_generation=1, grant=attempt
    )
    _register_grant(db, attempt)
    assert store.replace_with_execution_grant(updated, expected_generation=1, grant=attempt)
    assert len(db.audit) == 2
    assert not store.replace_with_execution_grant(
        updated, expected_generation=1, grant=attempt
    )
    wrong_action = replace(attempt, action="reject")
    with pytest.raises(PermissionError, match="transition"):
        store.replace_with_execution_grant(
            updated, expected_generation=1, grant=wrong_action
        )
    assert len(db.audit) == 2


def test_revoked_grant_blocks_mutation_after_case_preparation() -> None:
    """Model revocation after a valid candidate was prepared but before DB claim."""
    db = FakeDatabase()
    store = PostgresProducerCaseStore(db)
    case = _case()
    assert store.create(case)
    updated = apply_producer_command(
        case, actor=_actor(), expected_generation=1, command="reject", reason="Checked"
    )
    attempt = _grant_for(updated, action="reject", generation=1)
    _register_grant(db, attempt)
    _register_grant(db, attempt, state="revoked")
    assert not store.replace_with_execution_grant(
        updated, expected_generation=1, grant=attempt
    )
    assert len(db.audit) == 1
    assert store.load("tenant-1", "demo-preview-only", "demo-story-output") == case
