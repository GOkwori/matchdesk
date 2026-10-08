"""Deterministic orchestration control plane for MatchDesk Phase 2A.

This module owns workflow order, retry budgets, timeout classification, recovery
budgets and the deterministic verification hand-off. It does not call a model,
Foundry, Agent Framework, Azure or publication APIs. Specialist runtimes plug into
this control plane later and cannot expand their own authority.
"""

from __future__ import annotations

from typing import Annotated, Literal, Mapping

from pydantic import BeforeValidator, Field, model_validator

from matchdesk.domain.models import Contract, Identifier, immutable_array, plain_integer

SpecialistRole = Literal[
    "tactical_analyst",
    "narrative_composer",
    "editorial_reviewer",
    "audience_adapter",
]
WorkflowStatus = Literal[
    "running",
    "awaiting_verification",
    "completed",
    "fallback",
    "blocked",
]
AttemptOutcome = Literal["success", "retryable_failure", "blocked", "timeout"]
AttemptOutcomeInput = Literal["success", "retryable_failure", "blocked"]

SPECIALIST_SEQUENCE: tuple[SpecialistRole, ...] = (
    "tactical_analyst",
    "narrative_composer",
    "editorial_reviewer",
    "audience_adapter",
)

_DEFAULT_MAX_ATTEMPTS = 2
_DEFAULT_TIMEOUT_MS = 30_000
_MAX_RECOVERIES = 2


class RolePolicy(Contract):
    """Bound one specialist's execution without granting any model authority."""

    role: SpecialistRole
    max_attempts: Annotated[int, BeforeValidator(plain_integer), Field(ge=1, le=5)] = (
        _DEFAULT_MAX_ATTEMPTS
    )
    timeout_ms: Annotated[int, BeforeValidator(plain_integer), Field(ge=1, le=120_000)] = (
        _DEFAULT_TIMEOUT_MS
    )


DEFAULT_ROLE_POLICIES: Mapping[SpecialistRole, RolePolicy] = {
    role: RolePolicy(role=role) for role in SPECIALIST_SEQUENCE
}


class SpecialistAttempt(Contract):
    """Audit one bounded specialist attempt and its controller-classified outcome."""

    role: SpecialistRole
    attempt: Annotated[int, BeforeValidator(plain_integer), Field(ge=1, le=5)]
    duration_ms: Annotated[int, BeforeValidator(plain_integer), Field(ge=0)]
    outcome: AttemptOutcome
    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def validate_reason(self) -> "SpecialistAttempt":
        """Reject whitespace-only audit reasons."""
        if not self.reason.strip():
            raise ValueError("Attempt reason cannot be blank")
        return self


AttemptHistory = Annotated[
    tuple[SpecialistAttempt, ...],
    BeforeValidator(immutable_array),
]
CompletedRoles = Annotated[
    tuple[SpecialistRole, ...],
    BeforeValidator(immutable_array),
]


class WorkflowState(Contract):
    """Persistable shared state for one bounded four-specialist workflow."""

    workflow_id: Identifier
    match_id: Identifier
    replay_id: Identifier
    revision: Annotated[int, BeforeValidator(plain_integer), Field(ge=1)]
    moment_id: Identifier
    status: WorkflowStatus
    current_role: SpecialistRole | None
    completed_roles: CompletedRoles = ()
    attempts: AttemptHistory = ()
    recovery_count: Annotated[int, BeforeValidator(plain_integer), Field(ge=0)] = 0
    terminal_reason: Annotated[str, Field(min_length=1, max_length=500)] | None = None

    @model_validator(mode="after")
    def validate_state_shape(self) -> "WorkflowState":
        """Keep terminal and active workflow fields mutually consistent."""
        terminal = self.status in {"completed", "fallback", "blocked"}
        if terminal and self.current_role is not None:
            raise ValueError("Terminal workflows cannot retain a current specialist")
        if not terminal and self.status == "running" and self.current_role is None:
            raise ValueError("Running workflows require a current specialist")
        if self.status == "awaiting_verification" and self.current_role is not None:
            raise ValueError("Verification hand-off cannot retain a current specialist")
        if terminal != (self.terminal_reason is not None):
            raise ValueError("Exactly terminal workflows require a terminal reason")
        if len(set(self.completed_roles)) != len(self.completed_roles):
            raise ValueError("Completed specialist roles must be unique")
        return self


def start_workflow(
    workflow_id: Identifier,
    match_id: Identifier,
    replay_id: Identifier,
    revision: int,
    moment_id: Identifier,
) -> WorkflowState:
    """Create a workflow at the first specialist without invoking any runtime."""
    return WorkflowState(
        workflow_id=workflow_id,
        match_id=match_id,
        replay_id=replay_id,
        revision=revision,
        moment_id=moment_id,
        status="running",
        current_role="tactical_analyst",
    )


def _policy_for(
    role: SpecialistRole,
    policies: Mapping[SpecialistRole, RolePolicy],
) -> RolePolicy:
    """Return a complete role policy or fail closed for a partial policy set."""
    try:
        policy = policies[role]
    except KeyError as error:
        raise ValueError(f"Missing policy for specialist role: {role}") from error
    if policy.role != role:
        raise ValueError("Role policy key must match its embedded specialist role")
    return policy


def _attempt_number(state: WorkflowState, role: SpecialistRole) -> int:
    """Return the one-based attempt number that the role would execute next."""
    return 1 + sum(attempt.role == role for attempt in state.attempts)


def _next_role(role: SpecialistRole) -> SpecialistRole | None:
    """Return the next specialist in the locked Phase 2A sequence."""
    index = SPECIALIST_SEQUENCE.index(role)
    if index == len(SPECIALIST_SEQUENCE) - 1:
        return None
    return SPECIALIST_SEQUENCE[index + 1]


def record_specialist_attempt(
    state: WorkflowState,
    role: SpecialistRole,
    duration_ms: int,
    outcome: AttemptOutcomeInput,
    reason: str,
    *,
    policies: Mapping[SpecialistRole, RolePolicy] = DEFAULT_ROLE_POLICIES,
) -> WorkflowState:
    """Record one attempt and deterministically advance, retry or stop the workflow."""
    if state.status != "running" or state.current_role != role:
        raise ValueError("Only the current running specialist can record an attempt")
    if type(duration_ms) is not int or duration_ms < 0:
        raise ValueError("duration_ms must be a non-negative integer")
    if not reason.strip():
        raise ValueError("Attempt reason cannot be blank")

    policy = _policy_for(role, policies)
    attempt_number = _attempt_number(state, role)
    if attempt_number > policy.max_attempts:
        raise ValueError("Specialist retry budget is already exhausted")

    effective_outcome: AttemptOutcome = outcome
    effective_reason = reason
    if duration_ms > policy.timeout_ms:
        effective_outcome = "timeout"
        effective_reason = (
            f"Attempt exceeded {policy.timeout_ms} ms policy timeout: {reason.strip()}"
        )

    attempt = SpecialistAttempt(
        role=role,
        attempt=attempt_number,
        duration_ms=duration_ms,
        outcome=effective_outcome,
        reason=effective_reason,
    )
    attempts = state.attempts + (attempt,)

    if effective_outcome == "blocked":
        return state.model_copy(
            update={
                "status": "blocked",
                "current_role": None,
                "attempts": attempts,
                "terminal_reason": effective_reason,
            }
        )

    if effective_outcome in {"retryable_failure", "timeout"}:
        if attempt_number < policy.max_attempts:
            return state.model_copy(update={"attempts": attempts})
        return state.model_copy(
            update={
                "status": "fallback",
                "current_role": None,
                "attempts": attempts,
                "terminal_reason": (
                    f"{role} exhausted its {policy.max_attempts}-attempt budget"
                ),
            }
        )

    completed_roles = state.completed_roles
    if role not in completed_roles:
        completed_roles = completed_roles + (role,)

    if role == "editorial_reviewer":
        return state.model_copy(
            update={
                "status": "awaiting_verification",
                "current_role": None,
                "completed_roles": completed_roles,
                "attempts": attempts,
            }
        )

    next_role = _next_role(role)
    if next_role is None:
        return state.model_copy(
            update={
                "status": "completed",
                "current_role": None,
                "completed_roles": completed_roles,
                "attempts": attempts,
                "terminal_reason": "All four specialist stages completed within policy",
            }
        )

    return state.model_copy(
        update={
            "current_role": next_role,
            "completed_roles": completed_roles,
            "attempts": attempts,
        }
    )


def apply_verification_gate(
    state: WorkflowState,
    *,
    passed: bool,
    reason: str,
    policies: Mapping[SpecialistRole, RolePolicy] = DEFAULT_ROLE_POLICIES,
) -> WorkflowState:
    """Bind the external deterministic verification gate before audience adaptation."""
    if state.status != "awaiting_verification":
        raise ValueError("Verification can only bind at the editorial hand-off")
    if type(passed) is not bool:
        raise ValueError("passed must be a real boolean")
    if not reason.strip():
        raise ValueError("Verification reason cannot be blank")

    if passed:
        return state.model_copy(update={"status": "running", "current_role": "audience_adapter"})

    narrative_policy = _policy_for("narrative_composer", policies)
    editorial_policy = _policy_for("editorial_reviewer", policies)
    narrative_next = _attempt_number(state, "narrative_composer")
    editorial_next = _attempt_number(state, "editorial_reviewer")

    if (
        narrative_next <= narrative_policy.max_attempts
        and editorial_next <= editorial_policy.max_attempts
    ):
        retained_roles = tuple(
            role
            for role in state.completed_roles
            if role not in {"narrative_composer", "editorial_reviewer"}
        )
        return state.model_copy(
            update={
                "status": "running",
                "current_role": "narrative_composer",
                "completed_roles": retained_roles,
            }
        )

    return state.model_copy(
        update={
            "status": "fallback",
            "current_role": None,
            "terminal_reason": f"Verification failed after bounded revision budget: {reason.strip()}",
        }
    )


def recover_workflow(state: WorkflowState, reason: str) -> WorkflowState:
    """Record restart recovery without skipping a specialist or verification gate."""
    if state.status in {"completed", "fallback", "blocked"}:
        raise ValueError("Terminal workflows cannot be recovered")
    if not reason.strip():
        raise ValueError("Recovery reason cannot be blank")

    recovery_count = state.recovery_count + 1
    if recovery_count > _MAX_RECOVERIES:
        return state.model_copy(
            update={
                "status": "fallback",
                "current_role": None,
                "recovery_count": recovery_count,
                "terminal_reason": (
                    f"Workflow exceeded {_MAX_RECOVERIES} restart recoveries: {reason.strip()}"
                ),
            }
        )
    return state.model_copy(update={"recovery_count": recovery_count})
