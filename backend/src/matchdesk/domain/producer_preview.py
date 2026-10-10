"""Read-only source-bound producer inspection for a deterministic synthetic preview.

The preview is derived afresh from seeded football events. It is not a stored
producer session: no actor is authenticated and it exposes no review mutations,
approval, publisher identity or delivery side effect.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field

from matchdesk.domain.broadcast_outputs import (
    BroadcastEnvelope,
    ClaimLinkedText,
    CommentaryPayload,
)
from matchdesk.domain.hashing import canonical_bytes, content_digest
from matchdesk.domain.models import (
    ApprovalBinding,
    Claim,
    Contract,
    EvidenceRecord,
    MatchEvent,
    MatchWindow,
    MetricAssertion,
    Subject,
    VerificationResult,
    immutable_array,
)
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.verification import verify_claim


class ProducerDeskPreview(Contract):
    """Strict read-only projection; the response has no review-command capability."""

    mode: Literal["synthetic_read_only"] = "synthetic_read_only"
    scenario: Literal["late_winner"] = "late_winner"
    seed: Literal[7] = 7
    output: BroadcastEnvelope
    claim: Claim
    evidence: EvidenceRecord
    verification: VerificationResult
    events: Annotated[
        tuple[MatchEvent, ...],
        Field(min_length=1, max_length=128),
        BeforeValidator(immutable_array),
    ]
    review_status: Literal["pending_verification"] = "pending_verification"
    authenticated: Literal[False] = False
    publication_enabled: Literal[False] = False


def build_producer_desk_preview() -> ProducerDeskPreview:
    """Recompute a real measured claim from fixed synthetic events for inspection.

    The one-goal assertion is independently asserted by tests. Domain verification
    checks the registered metric; its verdict must not automatically change a
    producer-review state or authorize publication.
    """
    scenario = generate_scenario("late_winner", 7)
    events = scenario.events
    window = MatchWindow(period=1, from_ms=0, to_ms=2_700_000)
    first_half = tuple(
        event for event in events
        if event.period == 1 and window.from_ms <= event.match_clock_ms < window.to_ms
    )
    home_goal_events = tuple(
        event.event_id for event in first_half
        if event.type == "goal" and event.team_id == "home"
    )
    if len(home_goal_events) != 1:
        raise AssertionError("The locked producer preview fixture must have one home goal")

    source_digest = hashlib.sha256(
        b"\n".join(canonical_bytes(event) for event in events)
    ).hexdigest()
    evidence = EvidenceRecord(
        evidence_id="demo-home-first-half",
        match_id=scenario.match_id,
        replay_id="demo-late-winner-v1",
        revision=1,
        window=window,
        event_ids=tuple(event.event_id for event in first_half),
        engine_version="engine-v1",
        source_digest=source_digest,
    )
    claim = Claim(
        claim_id="demo-home-first-half-goals",
        text="The home team recorded one goal in the first half.",
        kind="measured_stat",
        evidence_event_ids=home_goal_events,
        assertion=MetricAssertion(
            metric="goals.v1",
            subject=Subject(team_id="home"),
            window=window,
            comparator="eq",
            value=1.0,
            unit="count",
        ),
    )
    verification = verify_claim(claim, evidence, events)
    if verification.status != "verified":
        raise AssertionError("Producer preview must fail closed on a failed metric check")

    payload = CommentaryPayload(lines=(ClaimLinkedText(claim_id=claim.claim_id, text=claim.text),))
    binding = ApprovalBinding(
        item_id="demo-first-half-story",
        item_version=1,
        replay_id=evidence.replay_id,
        content_digest=content_digest(payload),
        evidence_digest=content_digest(evidence),
        language="en",
        persona="analyst",
    )
    output = BroadcastEnvelope(
        output_id="demo-story-output",
        session_id="demo-preview-only",
        match_id=scenario.match_id,
        binding=binding,
        windows=(window,),
        evidence_ids=(evidence.evidence_id,),
        claim_ids=(claim.claim_id,),
        payload=payload,
    )
    return ProducerDeskPreview(
        output=output,
        claim=claim,
        evidence=evidence,
        verification=verification,
        events=first_half,
    )
