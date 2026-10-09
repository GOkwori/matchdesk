"""One bounded P2-05 live Foundry model-evaluation qualification.

The script performs exactly one tactical-specialist invocation, then evaluates the
returned claims through the deterministic P2-02 verifier via the P2-05 evaluation gate.
It emits only non-secret qualification evidence and has no publication authority.
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
from matchdesk.domain.runtime_evaluation import evaluate_specialist_response
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.specialists import ScopedReadTools, SpecialistRequest


@dataclass(frozen=True)
class LiveEvaluationEvidence:
    """Non-secret evidence from one bounded live P2-05 model evaluation."""

    runtime: str
    model: str
    specialist_role: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    proposed_claim_count: int
    evaluation_status: str
    verification_statuses: tuple[str, ...]
    evidence_digest: str
    store: bool
    max_output_tokens: int


async def _run() -> LiveEvaluationEvidence:
    """Execute one live tactical proposal and deterministically evaluate its claims."""
    config = FoundryRuntimeConfig.from_env()
    config.validate_activation()

    events = generate_scenario("counter_attack_goal", 7).events
    workflow = start_workflow(
        workflow_id="p2e-live-evaluation",
        match_id=events[0].match_id,
        replay_id="p2e-live-evaluation-replay",
        revision=1,
        moment_id="ca-goal-home",
    )
    request = SpecialistRequest(
        workflow=workflow,
        role="tactical_analyst",
        instruction=(
            "Return one concise tactical inference grounded only in supplied event IDs. "
            "Do not invent measured statistics or unsupported event facts."
        ),
    )
    tools = ScopedReadTools(role="tactical_analyst", events=events)

    started = time.perf_counter()
    execution = await AgentFrameworkFoundryExecutor(config=config).execute_with_evidence(
        request,
        tools,
    )
    latency_ms = round((time.perf_counter() - started) * 1_000)

    if execution.input_tokens is None:
        raise AssertionError("live evaluation requires input token telemetry")
    if execution.output_tokens is None:
        raise AssertionError("live evaluation requires output token telemetry")
    if execution.total_tokens is None:
        raise AssertionError("live evaluation requires total token telemetry")

    evidence = EvidenceRecord(
        evidence_id="p2e-live-evaluation-evidence",
        match_id=events[0].match_id,
        replay_id="p2e-live-evaluation-replay",
        revision=1,
        window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
        event_ids=tuple(event.event_id for event in events),
        engine_version="engine-v1",
        source_digest="a" * 64,
    )
    evaluation = evaluate_specialist_response(execution.response, evidence, events)
    if evaluation.status != "pass":
        raise AssertionError(f"live model evaluation did not pass: {evaluation.status}")

    return LiveEvaluationEvidence(
        runtime="microsoft-agent-framework-foundry",
        model=config.model or "",
        specialist_role=execution.response.role,
        latency_ms=latency_ms,
        input_tokens=execution.input_tokens,
        output_tokens=execution.output_tokens,
        total_tokens=execution.total_tokens,
        proposed_claim_count=len(execution.response.proposed_claims),
        evaluation_status=evaluation.status,
        verification_statuses=tuple(result.status for result in evaluation.verification_results),
        evidence_digest=content_digest(evidence),
        store=False,
        max_output_tokens=config.max_output_tokens,
    )


def main() -> None:
    """Run one live evaluation and print only non-secret qualification evidence."""
    evidence = asyncio.run(_run())
    print(json.dumps(asdict(evidence), indent=2, sort_keys=True))


if __name__ == "__main__":
    if os.environ.get("MATCHDESK_FOUNDRY_ENABLED", "").lower() != "true":
        raise SystemExit("MATCHDESK_FOUNDRY_ENABLED=true is required")
    main()
