"""Run the four-specialist workflow end to end and record what happened.

This is the runtime caller the Phase 2 control plane lacked. It drives
``orchestration`` (role order, retry budgets, the verification gate and its revision
loop) through ``execute_bounded_specialist`` (host timeouts and retries), gives each
role only its scoped read tools, verifies every proposed claim with the real verifier,
and records a replayable trace: each turn, each tool call, each verdict and each
revision. The executor decides what the specialists say; it never decides a verdict
and cannot approve or publish anything.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, Protocol

from pydantic import ValidationError

from matchdesk.domain.match_digest import clock_text, digest_json
from matchdesk.domain.models import (
    Claim,
    EvidenceRecord,
    MatchEvent,
    MatchWindow,
    Subject,
    VerificationResult,
)
from matchdesk.domain.orchestration import (
    RolePolicy,
    SpecialistRole,
    WorkflowState,
    apply_verification_gate,
    start_workflow,
)
from matchdesk.domain.runtime_resilience import (
    RetryableSpecialistError,
    execute_bounded_specialist,
)
from matchdesk.domain.specialists import ScopedReadTools, SpecialistRequest, SpecialistResponse
from matchdesk.domain.verification import verify_claim

TRACE_SCHEMA = "matchdesk-agent-trace/1"
MAX_INSTRUCTION_CHARS = 4_000
MAX_EVENTS_PER_READ = 40
LANGUAGES = ("en", "es", "fr")
PERSONAS = ("analyst", "casual_fan", "broadcast_caption")
ProviderKind = Literal["rehearsal", "foundry"]


@dataclass
class ToolCall:
    """One read-tool call a specialist made, with a short JSON-ready result."""

    tool: str
    args: dict[str, Any]
    result: Any


class TracedReadTools:
    """Role-scoped read tools that record every call for the trace.

    Permission is enforced by the wrapped ``ScopedReadTools``: a role calling a tool
    outside its scope raises PermissionError, which the bounded executor records as a
    blocked attempt. Arguments use minutes and plain identifiers so a model can call
    them as functions.
    """

    def __init__(self, scoped: ScopedReadTools, verification: Mapping[str, VerificationResult]):
        """Wrap one role's scoped tools and the verdicts that role may read."""
        self._scoped = scoped
        self._verification = dict(verification)
        self.calls: list[ToolCall] = []

    @property
    def allowed_tools(self) -> frozenset[str]:
        """The host-enforced tool names for this role."""
        return frozenset(self._scoped.allowed_tools)

    def _record(self, tool: str, args: dict[str, Any], result: Any) -> Any:
        """Append one call to the trace and return its result."""
        self.calls.append(ToolCall(tool=tool, args=args, result=result))
        return result

    @staticmethod
    def _window(from_minute: float, to_minute: float) -> MatchWindow:
        """A whole-match window between two display minutes."""
        return MatchWindow(from_ms=round(from_minute * 60_000), to_ms=round(to_minute * 60_000))

    def metric(
        self,
        metric_id: str,
        team_id: str,
        player_id: str | None = None,
        from_minute: float = 0,
        to_minute: float = 90,
    ) -> float:
        """Recompute one registered metric for a team or player between two minutes."""
        args = {"metric_id": metric_id, "team_id": team_id, "from_minute": from_minute}
        args["to_minute"] = to_minute
        if player_id is not None:
            args["player_id"] = player_id
        value = self._scoped.metric(
            metric_id,
            Subject(team_id=team_id, player_id=player_id),
            self._window(from_minute, to_minute),
        )
        return float(self._record("metric", args, round(value, 6)))

    def event_by_id(self, event_id: str) -> dict[str, Any] | None:
        """Read one accepted event by identity."""
        event = self._scoped.event_by_id(event_id)
        return self._record("event_by_id", {"event_id": event_id}, _event_row(event))  # type: ignore[no-any-return]

    def events_in_window(
        self, from_minute: float, to_minute: float, types: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Read up to 40 accepted events between two minutes, optionally of given types."""
        args: dict[str, Any] = {"from_minute": from_minute, "to_minute": to_minute}
        if types:
            args["types"] = list(types)
        rows = [
            _event_row(event)
            for event in self._scoped.events_in_window(self._window(from_minute, to_minute))
            if not types or event.type in types
        ][:MAX_EVENTS_PER_READ]
        return self._record("events_in_window", args, rows)  # type: ignore[no-any-return]

    def verification_result(self, claim_id: str) -> dict[str, Any] | None:
        """Read the verifier's latest result for one claim."""
        self._scoped.verification_result(claim_id)  # permission check only
        found = self._verification.get(claim_id)
        result = None if found is None else _verdict_row(found)
        return self._record("verification_result", {"claim_id": claim_id}, result)  # type: ignore[no-any-return]


def _event_row(event: MatchEvent | None) -> dict[str, Any] | None:
    """A compact JSON view of one event."""
    if event is None:
        return None
    row: dict[str, Any] = {
        "event_id": event.event_id,
        "clock": clock_text(event.match_clock_ms),
        "type": event.type,
        "team_id": event.team_id,
        "player_id": event.player_id,
    }
    if event.outcome is not None:
        row["outcome"] = event.outcome
    if event.tags:
        row["tags"] = list(event.tags)
    return row


def _verdict_row(result: VerificationResult) -> dict[str, Any]:
    """The verifier fields a specialist or the screen needs."""
    return {
        "claim_id": result.claim_id,
        "status": result.status,
        "query_id": result.query_id,
        "reason": result.reason,
        "expected": result.expected,
        "observed": result.observed,
    }


@dataclass
class TurnTelemetry:
    """Non-secret usage for one specialist call; None where a provider has none."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class WorkflowExecutor(Protocol):
    """One provider for every specialist turn: a live model or the rehearsal."""

    kind: ProviderKind
    label: str

    async def execute(
        self, request: SpecialistRequest, tools: TracedReadTools, *, digest: str
    ) -> tuple[SpecialistResponse, TurnTelemetry]:
        """Return one role's proposal using only the given tools and the match digest."""


_URL = re.compile(r"https?://\S+")
MAX_ERROR_CHARS = 300


def describe_error(error: BaseException) -> str:
    """A short, non-secret description of a provider error for the trace.

    Endpoint URLs are removed; the message is cut to a fixed length. The trace is
    committed, so it never carries a credential, an endpoint or a deployment name.
    """
    message = _URL.sub("<url>", " ".join(str(error).split()))
    text = f"{type(error).__name__}: {message}" if message else type(error).__name__
    return text[:MAX_ERROR_CHARS]


@dataclass
class _BoundAdapter:
    """Adapt a WorkflowExecutor to the host's bounded executor, collecting telemetry.

    Malformed model output (a claim that fails its contract) becomes a retryable
    failure, so the host retries it within the role's budget instead of crashing.
    """

    executor: WorkflowExecutor
    digest: str
    tools: TracedReadTools
    telemetry: list[TurnTelemetry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    async def execute(self, request: SpecialistRequest, tools: Any) -> SpecialistResponse:
        """Run one turn with the traced tools instead of the raw scoped tools."""
        del tools
        try:
            response, usage = await self.executor.execute(request, self.tools, digest=self.digest)
        except (ValidationError, json.JSONDecodeError) as error:
            self.errors.append(describe_error(error))
            raise RetryableSpecialistError("Specialist output failed its contract") from error
        except RetryableSpecialistError as error:
            self.errors.append(str(error))
            raise
        except TimeoutError:
            self.errors.append("TimeoutError: the turn exceeded its host deadline")
            raise
        self.telemetry.append(usage)
        return response


def _claim_json(claim: Claim) -> dict[str, Any]:
    """A claim as the trace and the next specialist see it."""
    return claim.model_dump(mode="json", exclude_none=True)


def _instruction(task: str, handoff: Mapping[str, Any]) -> str:
    """A bounded instruction: the role's task plus the structured handoff it receives."""
    text = task + "\n\nHANDOFF_JSON:\n" + json.dumps(handoff, separators=(",", ":"), sort_keys=True)
    if len(text) > MAX_INSTRUCTION_CHARS:
        raise ValueError("Specialist handoff exceeds its bounded size")
    return text


def parse_handoff(instruction: str) -> dict[str, Any]:
    """Read the structured handoff back out of an instruction."""
    _, _, payload = instruction.partition("HANDOFF_JSON:\n")
    return json.loads(payload) if payload else {}


TASKS: Mapping[SpecialistRole, str] = {
    "tactical_analyst": (
        "Analyse the match around the focus moment using your read tools. Propose up to "
        "four claims: measured_stat claims with a registered MetricAssertion for any "
        "number, event_fact claims with a registered fact query where one applies, and "
        "tactical_inference claims for interpretation. Cite only events you have read."
    ),
    "narrative_composer": (
        "Write the broadcast story as claims, one sentence each, from the tactical "
        "claims. Every number in a sentence must equal its assertion; name the player or "
        "team the assertion is about. Put the headline in content. If verifier_feedback "
        "is present, fix or drop every failed claim, using your tools to recompute."
    ),
    "editorial_reviewer": (
        "Review the drafted claims. Keep claims a registered query can check and "
        "interpretations that are clearly marked as such; drop any claim that needs data "
        "the match log does not hold. Return the kept claims and a short note on each drop "
        "in content."
    ),
    "audience_adapter": (
        "Adapt the verified claims for each language (en, es, fr) and persona (analyst, "
        "casual_fan, broadcast_caption). Return content as a JSON array of nine objects "
        "with language, persona, text and claim_ids. Add no new facts, numbers or names."
    ),
}


async def _turn(
    state: WorkflowState,
    role: SpecialistRole,
    executor: WorkflowExecutor,
    *,
    handoff: Mapping[str, Any],
    events: tuple[MatchEvent, ...],
    evidence: EvidenceRecord,
    verification: Mapping[str, VerificationResult],
    digest: str,
    clock: Callable[[], int | None],
    steps: list[dict[str, Any]],
) -> tuple[WorkflowState, SpecialistResponse | None]:
    """Run one role within its host budget and append it to the trace."""
    scoped = ScopedReadTools(
        role=role,
        events=events,
        evidence_records=(evidence,),
        verification_results=tuple(verification.values()),
    )
    traced = TracedReadTools(scoped, verification)
    adapter = _BoundAdapter(executor, digest, traced)
    # A live turn makes several model round trips (one per tool call), so a provider
    # may ask for a longer per-turn deadline than the default; the host still owns it.
    timeout_ms = getattr(executor, "turn_timeout_ms", None)
    policy = RolePolicy(role=role, timeout_ms=timeout_ms) if timeout_ms else None
    started = clock()
    result = await execute_bounded_specialist(
        state,
        instruction=_instruction(TASKS[role], handoff),
        executor=adapter,
        tools=scoped,
        policy=policy,
    )
    finished = clock()
    tokens = [usage.total_tokens for usage in adapter.telemetry if usage.total_tokens is not None]
    steps.append(
        {
            "type": "specialist",
            "role": role,
            "attempts": sum(attempt.role == role for attempt in result.state.attempts)
            - sum(attempt.role == role for attempt in state.attempts),
            "failures": list(result.failure_kinds),
            "errors": list(adapter.errors),
            "outcome": "proposed" if result.response is not None else result.state.status,
            "handoff_keys": sorted(handoff),
            "tool_calls": [
                {"tool": call.tool, "args": call.args, "result": call.result}
                for call in traced.calls
            ],
            "claims": [_claim_json(claim) for claim in result.response.proposed_claims]
            if result.response is not None
            else [],
            "content": result.response.content if result.response is not None else "",
            "tokens": sum(tokens) if tokens else None,
            "duration_ms": None if started is None or finished is None else finished - started,
        }
    )
    return result.state, result.response


def _gate_passes(results: list[VerificationResult]) -> bool:
    """Pass only when every claim is verified or a marked inference, and one is verified."""
    statuses = {result.status for result in results}
    return (
        bool(results)
        and statuses <= {"verified", "supported_inference"}
        and ("verified" in statuses)
    )


def _variants(content: str, verified_ids: set[str]) -> list[dict[str, Any]]:
    """Validate the adapter's nine variants: every pair once, verified claims only."""
    rows = json.loads(content)
    if not isinstance(rows, list):
        raise ValueError("Audience variants must be a JSON array")
    seen = set()
    variants = []
    for row in rows:
        pair = (row.get("language"), row.get("persona"))
        claim_ids = row.get("claim_ids")
        text = row.get("text")
        if pair[0] not in LANGUAGES or pair[1] not in PERSONAS or pair in seen:
            raise ValueError("Audience variants must cover each language and persona once")
        if not isinstance(text, str) or not text.strip() or len(text) > 400:
            raise ValueError("Audience variant text is missing or too long")
        if not isinstance(claim_ids, list) or not claim_ids or not set(claim_ids) <= verified_ids:
            raise ValueError("Audience variants may cite verified claims only")
        seen.add(pair)
        variants.append(
            {
                "language": pair[0],
                "persona": pair[1],
                "text": text,
                "claim_ids": claim_ids,
                "language_review": "NOT_RUN",
                "publishable": False,
            }
        )
    if len(seen) != len(LANGUAGES) * len(PERSONAS):
        raise ValueError("Audience variants must cover all nine language and persona pairs")
    return variants


async def run_agent_workflow(
    executor: WorkflowExecutor,
    *,
    events: tuple[MatchEvent, ...],
    evidence: EvidenceRecord,
    names: Mapping[str, str],
    digest: Mapping[str, Any],
    focus: Mapping[str, Any],
    clock: Callable[[], int | None] | None = None,
) -> dict[str, Any]:
    """Run tactical analysis, composition, review, verification and adaptation once.

    ``focus`` names the moment the story is about. ``clock`` returns milliseconds; the
    rehearsal passes one that returns None so its trace is byte-for-byte reproducible.
    """
    tick = clock if clock is not None else (lambda: time.monotonic_ns() // 1_000_000)
    digest_text = digest_json(digest)
    state = start_workflow(
        f"agent-run-{focus['moment_id']}",
        evidence.match_id,
        evidence.replay_id,
        evidence.revision,
        str(focus["moment_id"]),
    )
    steps: list[dict[str, Any]] = []
    common = {
        "events": events,
        "evidence": evidence,
        "digest": digest_text,
        "clock": tick,
        "steps": steps,
    }
    variants: list[dict[str, Any]] = []
    verified: list[Claim] = []

    state, tactical = await _turn(
        state,
        "tactical_analyst",
        executor,
        handoff={"focus": dict(focus)},
        verification={},
        **common,  # type: ignore[arg-type]
    )
    feedback: list[dict[str, Any]] = []
    previous: list[dict[str, Any]] = []
    verification: dict[str, VerificationResult] = {}
    rounds = 0
    while tactical is not None and state.status == "running":
        handoff: dict[str, Any] = {
            "focus": dict(focus),
            "tactical_claims": [_claim_json(c) for c in tactical.proposed_claims],
        }
        if feedback:
            handoff["previous_claims"] = previous
            handoff["verifier_feedback"] = feedback
        state, draft = await _turn(
            state,
            "narrative_composer",
            executor,
            handoff=handoff,
            verification=verification,
            **common,  # type: ignore[arg-type]
        )
        if draft is None or state.status != "running":
            break
        state, review = await _turn(
            state,
            "editorial_reviewer",
            executor,
            handoff={"draft_claims": [_claim_json(c) for c in draft.proposed_claims]},
            verification=verification,
            **common,  # type: ignore[arg-type]
        )
        if review is None or state.status != "awaiting_verification":
            break
        rounds += 1
        results = [
            verify_claim(claim, evidence, events, names=names) for claim in review.proposed_claims
        ]
        verification = {result.claim_id: result for result in results}
        passed = _gate_passes(results)
        steps.append(
            {
                "type": "verification",
                "round": rounds,
                "passed": passed,
                "results": [
                    {"text": claim.text, **_verdict_row(result)}
                    for claim, result in zip(review.proposed_claims, results, strict=True)
                ],
            }
        )
        failed = [r for r in results if r.status not in ("verified", "supported_inference")]
        state = apply_verification_gate(
            state,
            passed=passed,
            reason="All claims verified"
            if passed
            else f"{len(failed)} claim(s) failed verification",
        )
        if passed:
            verified = [
                c
                for c, r in zip(review.proposed_claims, results, strict=True)
                if r.status == "verified"
            ]
            kept = list(review.proposed_claims)
            state, adapted = await _turn(
                state,
                "audience_adapter",
                executor,
                handoff={"verified_claims": [_claim_json(c) for c in kept]},
                verification=verification,
                **common,  # type: ignore[arg-type]
            )
            if adapted is not None:
                try:
                    variants = _variants(adapted.content, {c.claim_id for c in kept})
                except (ValueError, AttributeError, json.JSONDecodeError) as error:
                    steps.append(
                        {
                            "type": "rejected_output",
                            "role": "audience_adapter",
                            "reason": str(error),
                        }
                    )
            break
        feedback = [_verdict_row(result) for result in failed]
        previous = [_claim_json(c) for c in review.proposed_claims]

    specialist_steps = [s for s in steps if s["type"] == "specialist"]
    tokens = [s["tokens"] for s in specialist_steps if s["tokens"] is not None]
    return {
        "schema": TRACE_SCHEMA,
        "provider": {"kind": executor.kind, "label": executor.label},
        "match_id": evidence.match_id,
        "focus": dict(focus),
        "digest_chars": len(digest_text),
        "digest_event_count": digest["event_count"],
        "status": "completed" if variants else state.status,
        "terminal_reason": state.terminal_reason,
        "steps": steps,
        "verified_claims": [_claim_json(c) for c in verified],
        "variants": variants,
        "totals": {
            "specialist_turns": len(specialist_steps),
            "tool_calls": sum(len(s["tool_calls"]) for s in specialist_steps),
            "verification_rounds": rounds,
            "tokens": sum(tokens) if tokens else None,
        },
        "approval": "human producer only",
        "published": False,
    }
