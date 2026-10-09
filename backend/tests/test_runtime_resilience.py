"""P2-05 tests for bounded specialist retry and timeout control."""

import asyncio

from matchdesk.domain.orchestration import start_workflow
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
