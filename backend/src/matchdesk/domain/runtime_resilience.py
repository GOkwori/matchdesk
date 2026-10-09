"""P2-05 bounded specialist retry and timeout execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic_ns
from typing import Literal

from matchdesk.domain.orchestration import (
    DEFAULT_ROLE_POLICIES,
    RolePolicy,
    WorkflowState,
    record_specialist_attempt,
)
from matchdesk.domain.specialists import (
    AsyncSpecialistExecutor,
    ScopedReadTools,
    SpecialistRequest,
    SpecialistResponse,
)

FailureKind = Literal["timeout", "retryable_failure", "blocked", "invalid_response"]


class RetryableSpecialistError(RuntimeError):
    """Signal a transient runtime failure that may consume one bounded retry."""


@dataclass(frozen=True)
class BoundedExecutionResult:
    """Host-controlled specialist result with explicit failure history."""

    state: WorkflowState
    response: SpecialistResponse | None
    failure_kinds: tuple[FailureKind, ...]


def _elapsed_ms(start_ns: int) -> int:
    """Return non-negative monotonic elapsed milliseconds."""
    return max(0, (monotonic_ns() - start_ns) // 1_000_000)


async def execute_bounded_specialist(
    state: WorkflowState,
    *,
    instruction: str,
    executor: AsyncSpecialistExecutor,
    tools: ScopedReadTools,
    policy: RolePolicy | None = None,
) -> BoundedExecutionResult:
    """Execute one specialist within host-owned retry and timeout budgets."""
    if state.status != "running" or state.current_role is None:
        raise ValueError("Bounded specialist execution requires a running workflow role")

    role = state.current_role
    selected_policy = policy or DEFAULT_ROLE_POLICIES[role]
    if selected_policy.role != role:
        raise ValueError("Execution policy role must match the current workflow role")

    policies = {**DEFAULT_ROLE_POLICIES, role: selected_policy}
    failures: list[FailureKind] = []
    current = state

    while current.status == "running" and current.current_role == role:
        request = SpecialistRequest(
            workflow=current,
            role=role,
            instruction=instruction,
        )
        start_ns = monotonic_ns()
        try:
            response = await asyncio.wait_for(
                executor.execute(request, tools),
                timeout=selected_policy.timeout_ms / 1000,
            )
        except TimeoutError:
            failures.append("timeout")
            current = record_specialist_attempt(
                current,
                role,
                duration_ms=selected_policy.timeout_ms + 1,
                outcome="retryable_failure",
                reason="Specialist runtime exceeded the host timeout",
                policies=policies,
            )
            continue
        except RetryableSpecialistError as error:
            failures.append("retryable_failure")
            current = record_specialist_attempt(
                current,
                role,
                duration_ms=_elapsed_ms(start_ns),
                outcome="retryable_failure",
                reason=f"Retryable specialist runtime failure: {type(error).__name__}",
                policies=policies,
            )
            continue
        except PermissionError:
            failures.append("blocked")
            current = record_specialist_attempt(
                current,
                role,
                duration_ms=_elapsed_ms(start_ns),
                outcome="blocked",
                reason="Specialist runtime was denied by the host authority boundary",
                policies=policies,
            )
            return BoundedExecutionResult(current, None, tuple(failures))

        if response.role != role:
            failures.append("invalid_response")
            current = record_specialist_attempt(
                current,
                role,
                duration_ms=_elapsed_ms(start_ns),
                outcome="blocked",
                reason="Specialist response role did not match requested authority",
                policies=policies,
            )
            return BoundedExecutionResult(current, None, tuple(failures))

        current = record_specialist_attempt(
            current,
            role,
            duration_ms=_elapsed_ms(start_ns),
            outcome="success",
            reason="Specialist runtime completed within host policy",
            policies=policies,
        )
        return BoundedExecutionResult(current, response, tuple(failures))

    return BoundedExecutionResult(current, None, tuple(failures))
