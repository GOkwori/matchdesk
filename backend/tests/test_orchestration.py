"""Phase 2A tests for the deterministic specialist orchestration control plane."""

import pytest
from matchdesk.domain.orchestration import (
    DEFAULT_ROLE_POLICIES,
    RolePolicy,
    WorkflowState,
    apply_verification_gate,
    record_specialist_attempt,
    recover_workflow,
    start_workflow,
)


def _start() -> WorkflowState:
    """Build one explicit workflow starting at the tactical specialist."""
    return start_workflow(
        workflow_id="wf-1",
        match_id="match-1",
        replay_id="replay-1",
        revision=1,
        moment_id="moment-1",
    )


def _succeed_current(state: WorkflowState, reason: str = "ok") -> WorkflowState:
    """Record one successful current-role attempt for compact transition tests."""
    assert state.current_role is not None
    return record_specialist_attempt(
        state,
        state.current_role,
        duration_ms=500,
        outcome="success",
        reason=reason,
    )


def test_workflow_starts_with_tactical_analyst_and_no_hidden_authority() -> None:
    """The controller always starts at the first locked specialist stage."""
    state = _start()

    assert state.status == "running"
    assert state.current_role == "tactical_analyst"
    assert state.completed_roles == ()
    assert state.attempts == ()
    assert state.recovery_count == 0
    assert state.terminal_reason is None


def test_happy_path_requires_verification_before_audience_adapter() -> None:
    """Audience adaptation cannot run until deterministic verification explicitly passes."""
    state = _start()
    state = _succeed_current(state, "analysis complete")
    state = _succeed_current(state, "narrative drafted")
    state = _succeed_current(state, "editorial review complete")

    assert state.status == "awaiting_verification"
    assert state.current_role is None
    assert state.completed_roles == (
        "tactical_analyst",
        "narrative_composer",
        "editorial_reviewer",
    )

    with pytest.raises(ValueError, match="current running specialist"):
        record_specialist_attempt(
            state,
            "audience_adapter",
            duration_ms=100,
            outcome="success",
            reason="must not bypass verification",
        )

    state = apply_verification_gate(state, passed=True, reason="claims verified")

    assert state.status == "running"
    assert state.current_role == "audience_adapter"

    state = _succeed_current(state, "audience variants produced")

    assert state.status == "completed"
    assert state.current_role is None
    assert state.completed_roles == (
        "tactical_analyst",
        "narrative_composer",
        "editorial_reviewer",
        "audience_adapter",
    )
    assert state.terminal_reason == "All four specialist stages completed within policy"


def test_retryable_failure_retries_same_role_with_bounded_attempt_numbers() -> None:
    """Retryable failure consumes one role-local attempt without advancing the workflow."""
    state = _start()

    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        duration_ms=1_000,
        outcome="retryable_failure",
        reason="transient provider error",
    )

    assert state.status == "running"
    assert state.current_role == "tactical_analyst"
    assert len(state.attempts) == 1
    assert state.attempts[0].attempt == 1

    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        duration_ms=750,
        outcome="success",
        reason="retry succeeded",
    )

    assert state.current_role == "narrative_composer"
    assert [attempt.attempt for attempt in state.attempts] == [1, 2]


def test_retry_budget_exhaustion_falls_back_instead_of_looping() -> None:
    """The controller fails closed after the configured per-role attempt budget."""
    state = _start()

    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        duration_ms=100,
        outcome="retryable_failure",
        reason="first failure",
    )
    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        duration_ms=100,
        outcome="retryable_failure",
        reason="second failure",
    )

    assert state.status == "fallback"
    assert state.current_role is None
    assert state.terminal_reason == "tactical_analyst exhausted its 2-attempt budget"

    with pytest.raises(ValueError, match="current running specialist"):
        record_specialist_attempt(
            state,
            "tactical_analyst",
            duration_ms=100,
            outcome="success",
            reason="late success must not revive fallback",
        )


def test_timeout_is_controller_classified_and_consumes_attempt_budget() -> None:
    """Runtime duration above policy timeout cannot be reported as success."""
    state = _start()
    policies = dict(DEFAULT_ROLE_POLICIES)
    policies["tactical_analyst"] = RolePolicy(
        role="tactical_analyst",
        max_attempts=2,
        timeout_ms=1_000,
    )

    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        duration_ms=1_001,
        outcome="success",
        reason="provider returned too late",
        policies=policies,
    )

    assert state.current_role == "tactical_analyst"
    assert state.attempts[0].outcome == "timeout"
    assert "exceeded 1000 ms" in state.attempts[0].reason

    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        duration_ms=2_000,
        outcome="success",
        reason="second timeout",
        policies=policies,
    )

    assert state.status == "fallback"
    assert state.current_role is None


def test_blocked_outcome_is_immediately_terminal() -> None:
    """Policy or safety block does not consume further retries."""
    state = _start()

    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        duration_ms=100,
        outcome="blocked",
        reason="required evidence unavailable",
    )

    assert state.status == "blocked"
    assert state.current_role is None
    assert state.terminal_reason == "required evidence unavailable"


def test_verification_failure_rewinds_to_narrative_when_budget_remains() -> None:
    """Failed deterministic verification requests bounded narrative/editorial revision."""
    state = _start()
    state = _succeed_current(state)
    state = _succeed_current(state)
    state = _succeed_current(state)

    state = apply_verification_gate(
        state,
        passed=False,
        reason="measured claim does not match registered metric",
    )

    assert state.status == "running"
    assert state.current_role == "narrative_composer"
    assert state.completed_roles == ("tactical_analyst",)

    state = _succeed_current(state, "revised narrative")
    state = _succeed_current(state, "re-reviewed")
    assert state.status == "awaiting_verification"

    state = apply_verification_gate(
        state,
        passed=True,
        reason="revised claims verified",
    )
    assert state.current_role == "audience_adapter"


def test_verification_failure_falls_back_when_revision_budget_is_exhausted() -> None:
    """A second verification failure cannot create an unbounded revision loop."""
    state = _start()
    state = _succeed_current(state)
    state = _succeed_current(state)
    state = _succeed_current(state)

    state = apply_verification_gate(state, passed=False, reason="first verification failure")
    state = _succeed_current(state)
    state = _succeed_current(state)

    state = apply_verification_gate(state, passed=False, reason="second verification failure")

    assert state.status == "fallback"
    assert state.current_role is None
    assert state.terminal_reason is not None
    assert "bounded revision budget" in state.terminal_reason


def test_recovery_budget_is_bounded_and_never_skips_current_gate() -> None:
    """Restart recovery counts are explicit and cannot jump workflow stages."""
    state = _start()

    state = recover_workflow(state, "worker restart 1")
    assert state.recovery_count == 1
    assert state.current_role == "tactical_analyst"

    state = recover_workflow(state, "worker restart 2")
    assert state.recovery_count == 2
    assert state.current_role == "tactical_analyst"

    state = recover_workflow(state, "worker restart 3")
    assert state.status == "fallback"
    assert state.current_role is None
    assert state.recovery_count == 3
    assert state.terminal_reason is not None


def test_terminal_workflow_cannot_be_recovered() -> None:
    """Recovery never reopens a completed, fallback or blocked workflow."""
    state = _start()
    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        duration_ms=10,
        outcome="blocked",
        reason="blocked",
    )

    with pytest.raises(ValueError, match="Terminal workflows"):
        recover_workflow(state, "restart after terminal state")


def test_wrong_role_and_partial_policy_sets_fail_closed() -> None:
    """Callers cannot execute a role out of order or omit its execution policy."""
    state = _start()

    with pytest.raises(ValueError, match="current running specialist"):
        record_specialist_attempt(
            state,
            "narrative_composer",
            duration_ms=10,
            outcome="success",
            reason="out of order",
        )

    with pytest.raises(ValueError, match="Missing policy"):
        record_specialist_attempt(
            state,
            "tactical_analyst",
            duration_ms=10,
            outcome="success",
            reason="no policy",
            policies={},
        )


def test_policy_key_and_embedded_role_must_match() -> None:
    """A malformed external policy map cannot silently govern the wrong specialist."""
    state = _start()
    policies = dict(DEFAULT_ROLE_POLICIES)
    policies["tactical_analyst"] = RolePolicy(role="narrative_composer")

    with pytest.raises(ValueError, match="policy key"):
        record_specialist_attempt(
            state,
            "tactical_analyst",
            duration_ms=10,
            outcome="success",
            reason="mismatched policy",
            policies=policies,
        )


def test_state_contract_rejects_inconsistent_terminal_and_active_shapes() -> None:
    """Persisted workflow state cannot claim terminal and active authority together."""
    with pytest.raises(ValueError, match="Terminal workflows"):
        WorkflowState(
            workflow_id="wf-1",
            match_id="match-1",
            replay_id="replay-1",
            revision=1,
            moment_id="moment-1",
            status="completed",
            current_role="audience_adapter",
            terminal_reason="done",
        )

    with pytest.raises(ValueError, match="terminal reason"):
        WorkflowState(
            workflow_id="wf-1",
            match_id="match-1",
            replay_id="replay-1",
            revision=1,
            moment_id="moment-1",
            status="running",
            current_role="tactical_analyst",
            terminal_reason="should not exist",
        )


def test_verification_gate_requires_boolean_and_nonblank_reason() -> None:
    """Verification inputs remain strict rather than truthy/coerced."""
    state = _start()
    state = _succeed_current(state)
    state = _succeed_current(state)
    state = _succeed_current(state)

    with pytest.raises(ValueError, match="real boolean"):
        apply_verification_gate(state, passed=1, reason="invalid")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="cannot be blank"):
        apply_verification_gate(state, passed=True, reason="   ")


def test_attempt_contract_and_controller_reject_blank_or_invalid_inputs() -> None:
    """Attempt records and controller inputs reject blank reasons and invalid durations."""
    from matchdesk.domain.orchestration import SpecialistAttempt

    with pytest.raises(ValueError, match="cannot be blank"):
        SpecialistAttempt(
            role="tactical_analyst",
            attempt=1,
            duration_ms=1,
            outcome="success",
            reason="   ",
        )

    state = _start()
    with pytest.raises(ValueError, match="duration_ms"):
        record_specialist_attempt(
            state,
            "tactical_analyst",
            duration_ms=-1,
            outcome="success",
            reason="invalid duration",
        )
    with pytest.raises(ValueError, match="duration_ms"):
        record_specialist_attempt(
            state,
            "tactical_analyst",
            duration_ms=True,
            outcome="success",
            reason="boolean duration",
        )
    with pytest.raises(ValueError, match="cannot be blank"):
        record_specialist_attempt(
            state,
            "tactical_analyst",
            duration_ms=1,
            outcome="success",
            reason="   ",
        )


def test_state_contract_rejects_missing_role_verification_role_and_duplicate_completion() -> None:
    """Persisted state cannot omit active authority or duplicate completed specialists."""
    with pytest.raises(ValueError, match="Running workflows require"):
        WorkflowState(
            workflow_id="wf-1",
            match_id="match-1",
            replay_id="replay-1",
            revision=1,
            moment_id="moment-1",
            status="running",
            current_role=None,
        )

    with pytest.raises(ValueError, match="Verification hand-off"):
        WorkflowState(
            workflow_id="wf-1",
            match_id="match-1",
            replay_id="replay-1",
            revision=1,
            moment_id="moment-1",
            status="awaiting_verification",
            current_role="editorial_reviewer",
        )

    with pytest.raises(ValueError, match="must be unique"):
        WorkflowState(
            workflow_id="wf-1",
            match_id="match-1",
            replay_id="replay-1",
            revision=1,
            moment_id="moment-1",
            status="running",
            current_role="narrative_composer",
            completed_roles=("tactical_analyst", "tactical_analyst"),
        )


def test_preexhausted_retry_budget_fails_closed() -> None:
    """A restored running state cannot execute beyond its role-local attempt budget."""
    from matchdesk.domain.orchestration import SpecialistAttempt

    state = WorkflowState(
        workflow_id="wf-1",
        match_id="match-1",
        replay_id="replay-1",
        revision=1,
        moment_id="moment-1",
        status="running",
        current_role="tactical_analyst",
        attempts=(
            SpecialistAttempt(
                role="tactical_analyst",
                attempt=1,
                duration_ms=1,
                outcome="retryable_failure",
                reason="first",
            ),
            SpecialistAttempt(
                role="tactical_analyst",
                attempt=2,
                duration_ms=1,
                outcome="retryable_failure",
                reason="second",
            ),
        ),
    )

    with pytest.raises(ValueError, match="already exhausted"):
        record_specialist_attempt(
            state,
            "tactical_analyst",
            duration_ms=1,
            outcome="success",
            reason="third attempt",
        )


def test_existing_completed_role_is_not_duplicated_on_success() -> None:
    """A restored state retains unique completed-role history when replaying success."""
    state = WorkflowState(
        workflow_id="wf-1",
        match_id="match-1",
        replay_id="replay-1",
        revision=1,
        moment_id="moment-1",
        status="running",
        current_role="tactical_analyst",
        completed_roles=("tactical_analyst",),
    )

    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        duration_ms=1,
        outcome="success",
        reason="idempotent restored success",
    )

    assert state.completed_roles == ("tactical_analyst",)
    assert state.current_role == "narrative_composer"


def test_verification_and_recovery_require_their_exact_gate_and_reason() -> None:
    """Verification and recovery cannot be invoked from the wrong state or without audit text."""
    state = _start()

    with pytest.raises(ValueError, match="editorial hand-off"):
        apply_verification_gate(state, passed=True, reason="too early")

    with pytest.raises(ValueError, match="cannot be blank"):
        recover_workflow(state, "   ")
