"""Record the four-specialist workflow on the canonical match's 58:17 goal (M-05)."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.agent_rehearsal import RehearsalExecutor
from matchdesk.domain.agent_workflow import WorkflowExecutor, run_agent_workflow
from matchdesk.domain.demo_claims import DISPLAY_NAMES, REPLAY_END_MS, evidence_record
from matchdesk.domain.match_digest import build_match_digest

FOCUS: dict[str, str] = {
    "moment_id": "M-05",
    "event_id": "E-1366",
    "team_id": canonical.HOME,
    "opponent_id": canonical.AWAY,
    "player_id": "nbr-09",
}


async def record_agent_run(
    executor: WorkflowExecutor, *, clock: Callable[[], int | None] | None = None
) -> dict[str, Any]:
    """Run the workflow once on the canonical log, as the studio shows it at 67:12."""
    events = canonical.generate_canonical_match()
    return await run_agent_workflow(
        executor,
        events=events,
        evidence=evidence_record(events),
        names=DISPLAY_NAMES,
        digest=build_match_digest(events, DISPLAY_NAMES, to_ms=REPLAY_END_MS),
        focus=FOCUS,
        clock=clock,
    )


def rehearsal_trace() -> dict[str, Any]:
    """The deterministic rehearsal trace; identical bytes on every run."""
    return asyncio.run(record_agent_run(RehearsalExecutor(), clock=lambda: None))
