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
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import EvidenceRecord, MatchWindow
from matchdesk.domain.orchestration import start_workflow
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.specialists import ScopedReadTools, SpecialistRequest
from matchdesk.domain.verification import verify_claim


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
    input_tokens: int
    output_tokens: int
    total_tokens: int
    verification_status: str
    evidence_digest: str


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
    execution = await AgentFrameworkFoundryExecutor(config=config).execute_with_evidence(
        request,
        tools,
    )
    latency_ms = round((time.perf_counter() - started) * 1_000)
    response = execution.response

    assert response.role == "tactical_analyst"
    assert response.proposed_claims, "live smoke requires at least one evidence-bound claim"
    assert execution.input_tokens is not None
    assert execution.output_tokens is not None
    assert execution.total_tokens is not None
    assert execution.total_tokens <= execution.input_tokens + config.max_output_tokens

    event_ids = {event.event_id for event in events}
    claim = response.proposed_claims[0]
    assert claim.kind == "tactical_inference"
    assert set(claim.evidence_event_ids).issubset(event_ids)
    assert claim.evidence_event_ids

    evidence = EvidenceRecord(
        evidence_id="p2d-live-smoke-evidence",
        match_id=events[0].match_id,
        replay_id="p2d-live-smoke-replay",
        revision=1,
        window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
        event_ids=tuple(event.event_id for event in events),
        engine_version="engine-v1",
        source_digest="a" * 64,
    )
    verification = verify_claim(claim, evidence, events)
    assert verification.status == "supported_inference"

    return LiveSmokeEvidence(
        runtime="microsoft-agent-framework-foundry",
        model=config.model or "",
        specialist_role=response.role,
        latency_ms=latency_ms,
        max_output_tokens=config.max_output_tokens,
        store=False,
        proposed_claim_count=len(response.proposed_claims),
        content_present=bool(response.content.strip()),
        input_tokens=execution.input_tokens,
        output_tokens=execution.output_tokens,
        total_tokens=execution.total_tokens,
        verification_status=verification.status,
        evidence_digest=content_digest(evidence),
    )


def main() -> None:
    """Run the live smoke and print only non-secret qualification evidence."""
    evidence = asyncio.run(_run())
    print(json.dumps(asdict(evidence), indent=2, sort_keys=True))


if __name__ == "__main__":
    if os.environ.get("MATCHDESK_FOUNDRY_ENABLED", "").lower() != "true":
        raise SystemExit("MATCHDESK_FOUNDRY_ENABLED=true is required for the live smoke")
    main()
