"""Model-agnostic specialist execution interfaces for MatchDesk Phase 2C.

The host owns role scope and exposes only read-only tools over immutable Phase 1/2
records. Specialist implementations can propose claims/content but cannot mutate
events, evidence, verification results, approvals or publication state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Protocol

from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import (
    Claim,
    EvidenceRecord,
    MatchEvent,
    MatchWindow,
    Subject,
    VerificationResult,
)
from matchdesk.domain.orchestration import SpecialistRole, WorkflowState

ReadToolName = Literal[
    "event_by_id",
    "events_in_window",
    "metric",
    "evidence_record",
    "verification_result",
]

ROLE_READ_TOOLS: Mapping[SpecialistRole, frozenset[ReadToolName]] = {
    "tactical_analyst": frozenset({"event_by_id", "events_in_window", "metric"}),
    "narrative_composer": frozenset(
        {"event_by_id", "events_in_window", "metric", "evidence_record", "verification_result"}
    ),
    "editorial_reviewer": frozenset(
        {"event_by_id", "events_in_window", "metric", "evidence_record", "verification_result"}
    ),
    "audience_adapter": frozenset({"evidence_record", "verification_result"}),
}


@dataclass(frozen=True)
class SpecialistRequest:
    """Immutable execution request bound to one active workflow specialist."""

    workflow: WorkflowState
    role: SpecialistRole
    instruction: str

    def __post_init__(self) -> None:
        """Reject blank prompts and out-of-order role execution."""
        if not self.instruction.strip():
            raise ValueError("Specialist instruction cannot be blank")
        if self.workflow.status != "running" or self.workflow.current_role != self.role:
            raise ValueError("Specialist request must match the current running workflow role")


@dataclass(frozen=True)
class SpecialistResponse:
    """A specialist proposal; it carries no approval or mutation authority."""

    role: SpecialistRole
    proposed_claims: tuple[Claim, ...] = ()
    content: str = ""

    def __post_init__(self) -> None:
        """Require meaningful proposed output without inventing side effects."""
        if not self.proposed_claims and not self.content.strip():
            raise ValueError("Specialist response must contain claims or content")


class SpecialistExecutor(Protocol):
    """Model-agnostic synchronous execution boundary for local specialist runtimes."""

    def execute(
        self,
        request: SpecialistRequest,
        tools: "ScopedReadTools",
    ) -> SpecialistResponse:
        """Return a proposal using only host-provided read tools."""


class AsyncSpecialistExecutor(Protocol):
    """Model-agnostic asynchronous boundary for remote or live specialist runtimes."""

    async def execute(
        self,
        request: SpecialistRequest,
        tools: "ScopedReadTools",
    ) -> SpecialistResponse:
        """Return a proposal using only host-provided read tools."""


class ScopedReadTools:
    """Role-scoped, read-only access to deterministic MatchDesk records."""

    def __init__(
        self,
        *,
        role: SpecialistRole,
        events: tuple[MatchEvent, ...],
        evidence_records: tuple[EvidenceRecord, ...] = (),
        verification_results: tuple[VerificationResult, ...] = (),
    ) -> None:
        """Snapshot immutable inputs and validate one-match event scope."""
        if events:
            match_id = events[0].match_id
            if any(event.match_id != match_id for event in events):
                raise ValueError("Scoped read tools cannot mix event match identities")
        self._role = role
        self._events = tuple(events)
        self._events_by_id = {event.event_id: event for event in events}
        self._evidence = {record.evidence_id: record for record in evidence_records}
        self._verification = {result.claim_id: result for result in verification_results}

    @property
    def allowed_tools(self) -> frozenset[ReadToolName]:
        """Expose the immutable host-enforced tool permission set for this role."""
        return ROLE_READ_TOOLS[self._role]

    def _require(self, tool: ReadToolName) -> None:
        """Fail closed when a specialist attempts a tool outside its role scope."""
        if tool not in self.allowed_tools:
            raise PermissionError(f"{self._role} is not allowed to use {tool}")

    def event_by_id(self, event_id: str) -> MatchEvent | None:
        """Read one accepted immutable event by identity."""
        self._require("event_by_id")
        return self._events_by_id.get(event_id)

    def events_in_window(self, window: MatchWindow) -> tuple[MatchEvent, ...]:
        """Read immutable accepted events in one half-open match window."""
        self._require("events_in_window")
        return tuple(
            event
            for event in self._events
            if event.period == window.period
            and window.from_ms <= event.match_clock_ms < window.to_ms
        )

    def metric(
        self,
        metric_id: str,
        subject: Subject,
        window: MatchWindow,
    ) -> float:
        """Read one registered deterministic metric result."""
        self._require("metric")
        return compute_metric(metric_id, self._events, subject, window)

    def evidence_record(self, evidence_id: str) -> EvidenceRecord | None:
        """Read one immutable evidence record by identity."""
        self._require("evidence_record")
        return self._evidence.get(evidence_id)

    def verification_result(self, claim_id: str) -> VerificationResult | None:
        """Read one deterministic verification result by claim identity."""
        self._require("verification_result")
        return self._verification.get(claim_id)


def execute_specialist(
    executor: SpecialistExecutor,
    request: SpecialistRequest,
    *,
    events: tuple[MatchEvent, ...],
    evidence_records: tuple[EvidenceRecord, ...] = (),
    verification_results: tuple[VerificationResult, ...] = (),
) -> SpecialistResponse:
    """Execute one specialist behind host-owned role and read-tool boundaries."""
    tools = ScopedReadTools(
        role=request.role,
        events=events,
        evidence_records=evidence_records,
        verification_results=verification_results,
    )
    response = executor.execute(request, tools)
    if response.role != request.role:
        raise ValueError("Specialist response role must match the requested role")
    return response


async def execute_specialist_async(
    executor: AsyncSpecialistExecutor,
    request: SpecialistRequest,
    *,
    events: tuple[MatchEvent, ...],
    evidence_records: tuple[EvidenceRecord, ...] = (),
    verification_results: tuple[VerificationResult, ...] = (),
) -> SpecialistResponse:
    """Execute one asynchronous specialist behind the same host-owned read boundary."""
    tools = ScopedReadTools(
        role=request.role,
        events=events,
        evidence_records=evidence_records,
        verification_results=verification_results,
    )
    response = await executor.execute(request, tools)
    if response.role != request.role:
        raise ValueError("Specialist response role must match the requested role")
    return response
