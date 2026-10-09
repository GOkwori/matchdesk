"""One bounded P2-04 live Foundry smoke test.

This script is intentionally not part of normal CI. It requires explicit live-runtime
activation and an authenticated Azure CLI context, executes one tactical specialist turn,
and emits a redacted evidence record. It has no publication or Azure-provisioning authority.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass

from matchdesk.domain.foundry_runtime import AgentFrameworkFoundryExecutor, FoundryRuntimeConfig
from matchdesk.domain.orchestration import start_workflow
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.specialists import ScopedReadTools, SpecialistRequest


@dataclass(frozen=True)
class LiveSmokeEvidence:
    """Non-secret evidence captured from one bounded live specialist invocation."""

    runtime: str
    model: str
    specialist_role: str
    latency_ms: int
    max_output_tokens: int
    store: bool
    proposed_claim_count: int
    content_present: bool


async def _run() -> LiveSmokeEvidence:
    """Execute exactly one live tactical-specialist turn."""
    config = FoundryRuntimeConfig.from_env()
    config.validate_activation()

    events = generate_scenario("counter_attack_goal", 7).events
    workflow = start_workflow(
        workflow_id="p2d-live-smoke",
        match_id=events[0].match_id,
        replay_id="p2d-live-smoke-replay",
        revision=1,
        moment_id="ca-goal-home",
    )
    request = SpecialistRequest(
        workflow=workflow,
        role="tactical_analyst",
        instruction=(
            "Analyse the supplied deterministic counter-attack sequence. Return one concise "
            "non-authoritative tactical observation grounded only in supplied event IDs."
        ),
    )
    tools = ScopedReadTools(role="tactical_analyst", events=events)

    started = time.perf_counter()
    response = await AgentFrameworkFoundryExecutor(config=config).execute(request, tools)
    latency_ms = round((time.perf_counter() - started) * 1_000)

    assert response.role == "tactical_analyst"
    assert response.content.strip() or response.proposed_claims
    for claim in response.proposed_claims:
        assert set(claim.evidence_event_ids).issubset({event.event_id for event in events})

    return LiveSmokeEvidence(
        runtime="microsoft-agent-framework-foundry",
        model=config.model or "",
        specialist_role=response.role,
        latency_ms=latency_ms,
        max_output_tokens=config.max_output_tokens,
        store=False,
        proposed_claim_count=len(response.proposed_claims),
        content_present=bool(response.content.strip()),
    )


def main() -> None:
    """Run the live smoke and print only non-secret qualification evidence."""
    evidence = asyncio.run(_run())
    print(json.dumps(asdict(evidence), indent=2, sort_keys=True))


if __name__ == "__main__":
    if os.environ.get("MATCHDESK_FOUNDRY_ENABLED", "").lower() != "true":
        raise SystemExit("MATCHDESK_FOUNDRY_ENABLED=true is required for the live smoke")
    main()
