"""P2-05 tests for bounded specialist retry and timeout control."""

import asyncio

from matchdesk.domain.orchestration import RolePolicy, start_workflow
from matchdesk.domain.runtime_resilience import (
    RetryableSpecialistError,
    execute_bounded_specialist,
)
from matchdesk.domain.specialists import ScopedReadTools, SpecialistResponse


def _state():
    """Create one workflow at the tactical specialist."""
    return start_workflow("wf-p2e", "match-1", "replay-1", 1, "moment-1")


def test_retryable_failure_consumes_one_attempt_then_succeeds() -> None:
    """A transient runtime failure retries the same role within policy."""

    class Executor:
        """Fail once with an explicit transient error, then return a valid response."""

        def __init__(self):
            """Initialize the deterministic call counter."""
            self.calls = 0

        async def execute(self, request, tools):
            """Raise once, then return a role-matched specialist response."""
            self.calls += 1
            if self.calls == 1:
                raise RetryableSpecialistError("temporary provider failure")
            return SpecialistResponse(role=request.role, content="Recovered response")

    result = asyncio.run(
        execute_bounded_specialist(
            _state(),
            instruction="Analyse the bounded event context.",
            executor=Executor(),
            tools=ScopedReadTools(role="tactical_analyst", events=()),
        )
    )

    assert result.response is not None
    assert result.failure_kinds == ("retryable_failure",)
    assert result.state.current_role == "narrative_composer"
    assert [attempt.attempt for attempt in result.state.attempts] == [1, 2]


def test_repeated_retryable_failure_stops_at_budget() -> None:
    """The controller stops after the configured role-local attempt budget."""

    class Executor:
        """Always return the same explicit transient runtime failure."""

        async def execute(self, request, tools):
            """Raise the transient signal on every invocation."""
            raise RetryableSpecialistError("temporary provider failure")

    result = asyncio.run(
        execute_bounded_specialist(
            _state(),
            instruction="Analyse the bounded event context.",
            executor=Executor(),
            tools=ScopedReadTools(role="tactical_analyst", events=()),
        )
    )

    assert result.response is None
    assert result.failure_kinds == ("retryable_failure", "retryable_failure")
    assert result.state.status == "fallback"
    assert result.state.current_role is None


def test_timeout_is_classified_and_bounded() -> None:
    """The host timeout consumes attempts and finishes in fallback."""

    class Executor:
        """Sleep beyond the deliberately tiny host timeout."""

        async def execute(self, request, tools):
            """Wait long enough for asyncio.wait_for to cancel the call."""
            await asyncio.sleep(0.02)
            return SpecialistResponse(role=request.role, content="late")

    result = asyncio.run(
        execute_bounded_specialist(
            _state(),
            instruction="Analyse the bounded event context.",
            executor=Executor(),
            tools=ScopedReadTools(role="tactical_analyst", events=()),
            policy=RolePolicy(
                role="tactical_analyst",
                max_attempts=2,
                timeout_ms=1,
            ),
        )
    )

    assert result.response is None
    assert result.failure_kinds == ("timeout", "timeout")
    assert result.state.status == "fallback"
    assert [attempt.outcome for attempt in result.state.attempts] == ["timeout", "timeout"]
