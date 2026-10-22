"""Deterministic claim verification for MatchDesk Phase 2B.

Verification recomputes registered measurements and checks evidence identity. It never
treats structurally valid prose as factual truth and grants no publication authority.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Mapping

from matchdesk.domain.claim_text import TEXT_QUERY_ID, text_binding_problem
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.metrics import METRIC_DEFINITIONS, compute_metric
from matchdesk.domain.models import (
    Claim,
    EventFact,
    EvidenceRecord,
    MatchEvent,
    VerificationResult,
    round_half_up,
)

# Count metrics whose cited evidence must be events the formula actually counts.
_COUNTED_TYPES: Mapping[str, str] = {"goals.v1": "goal", "shots.v1": "shot"}


def _query_id(metric_id: str) -> str:
    """Convert a versioned metric identifier into the strict verification query ID."""
    return f"metric-{metric_id.replace('.', '-')}"


def _validate_evidence(
    claim: Claim,
    evidence: EvidenceRecord,
    events: tuple[MatchEvent, ...],
) -> str | None:
    """Return a blocking reason when claim evidence cannot be bound to accepted events."""
    if not events:
        return "No accepted events are available for verification"
    if any(event.match_id != evidence.match_id for event in events):
        return "Verification input contains events outside the evidence match"
    event_ids = {event.event_id for event in events}
    evidence_ids = set(evidence.event_ids)
    missing_from_record = set(claim.evidence_event_ids) - evidence_ids
    if missing_from_record:
        return "Claim cites events that are not bound by the evidence record"
    missing_events = set(claim.evidence_event_ids) - event_ids
    if missing_events:
        return "Claim cites events that are not present in accepted event input"
    return None


def _comparison_passes(
    comparator: str,
    expected: float,
    observed: float,
    decimals: int | None = None,
) -> bool:
    """Evaluate the declared metric comparator.

    Without a stated precision, ``eq`` is exact (to float noise). With one, the recomputed
    value is rounded half up to the claim's precision first: "58%" is true of 57.96% and
    false of 58.6%. Nothing is rounded for ``gte`` or ``lte``.
    """
    if comparator == "eq" and decimals is not None:
        return round_half_up(observed, decimals) == round_half_up(expected, decimals)
    if comparator == "eq":
        return math.isclose(observed, expected, rel_tol=1e-9, abs_tol=1e-9)
    if comparator == "gte":
        return observed >= expected
    if comparator == "lte":
        return observed <= expected
    raise ValueError(f"unsupported comparator: {comparator}")


def _fact_result(
    claim: Claim,
    fact: EventFact,
    evidence: EvidenceRecord,
    events: tuple[MatchEvent, ...],
) -> tuple[str, str, str, float | None, float | None]:
    """Run one registered event-fact query.

    Returns (status, query_id, reason, expected, observed). A wrong gap carries the
    stated and recorded seconds, so a writer sent back for revision learns the
    recorded value rather than guessing again.
    """
    query_id = "event-" + fact.query.replace(".", "-").replace("_", "-")
    if any(event_id not in claim.evidence_event_ids for event_id in fact.referenced_event_ids()):
        return "blocked", query_id, "Event fact reads events the claim does not cite", None, None
    by_id = {event.event_id: event for event in events}
    target = by_id[fact.event_id]
    if target.match_clock_ms >= evidence.window.to_ms:
        return "blocked", query_id, "Event fact reads events after the evidence window", None, None
    if fact.query == "goal_scorer.v1":
        if target.type == "goal" and target.player_id == fact.player_id:
            return (
                "verified",
                query_id,
                "The cited goal event records the stated scorer",
                None,
                None,
            )
        return (
            "needs_revision",
            query_id,
            "The cited event is not a goal by the stated player",
            None,
            None,
        )
    assert fact.from_event_id is not None and fact.gap_seconds is not None
    earlier = by_id[fact.from_event_id]
    if earlier.sequence >= target.sequence:
        return (
            "needs_revision",
            query_id,
            "The cited events are not in the stated order",
            None,
            None,
        )
    if fact.from_tag is not None and fact.from_tag not in earlier.tags:
        return (
            "needs_revision",
            query_id,
            f"The earlier event is not tagged {fact.from_tag}",
            None,
            None,
        )
    gap = round_half_up((target.match_clock_ms - earlier.match_clock_ms) / 1000, 0)
    if gap != Decimal(fact.gap_seconds):
        return (
            "needs_revision",
            query_id,
            "The recorded gap differs from the stated seconds",
            float(fact.gap_seconds),
            float(gap),
        )
    return "verified", query_id, "The recorded events and gap match the stated sequence", None, None


def verify_claim(
    claim: Claim,
    evidence: EvidenceRecord,
    events: tuple[MatchEvent, ...],
    *,
    names: Mapping[str, str] | None = None,
) -> VerificationResult:
    """Verify one claim against deterministic evidence and registered queries.

    ``names`` maps player and team identities to the display names the prose uses. With
    it, a sentence must name its subject and state its value; without it, a sentence may
    still never state a quantity that contradicts its own assertion.
    """
    evidence_digest = content_digest(evidence)
    blocking_reason = _validate_evidence(claim, evidence, events)
    if blocking_reason is not None:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="blocked",
            query_id="evidence-binding-v1",
            reason=blocking_reason,
            evidence_digest=evidence_digest,
        )
    if claim.assertion is not None and claim.assertion.window.to_ms > evidence.window.to_ms:
        # A claim cannot speak about time the evidence does not cover, such as the full
        # 90 minutes at a 67:12 replay point.
        return VerificationResult(
            claim_id=claim.claim_id,
            status="blocked",
            query_id="evidence-window-v1",
            reason="Claim window extends past the evidence window",
            evidence_digest=evidence_digest,
        )

    if claim.kind == "tactical_inference":
        return VerificationResult(
            claim_id=claim.claim_id,
            status="supported_inference",
            query_id="evidence-support-v1",
            reason="All cited evidence events exist; tactical meaning remains an inference",
            evidence_digest=evidence_digest,
        )

    if claim.kind == "event_fact" and claim.fact is not None:
        status, query_id, reason, expected, observed = _fact_result(
            claim, claim.fact, evidence, events
        )
        if status == "verified":
            problem = text_binding_problem(claim, names, events)
            if problem is not None:
                status, query_id, reason = "needs_revision", TEXT_QUERY_ID, problem
        return VerificationResult(
            claim_id=claim.claim_id,
            status=status,  # type: ignore[arg-type]
            query_id=query_id,
            reason=reason,
            expected=expected,
            observed=observed,
            evidence_digest=evidence_digest,
        )

    if claim.kind == "event_fact":
        return VerificationResult(
            claim_id=claim.claim_id,
            status="needs_revision",
            query_id="event-fact-semantic-v1",
            reason=(
                "Event-fact prose has no registered semantic assertion; evidence existence "
                "alone cannot verify the text"
            ),
            evidence_digest=evidence_digest,
        )

    assertion = claim.assertion
    if assertion is None:
        raise ValueError("Measured claim is missing its required metric assertion")

    definition = METRIC_DEFINITIONS.get(assertion.metric)
    if definition is None:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="blocked",
            query_id="metric-registry-v1",
            reason=f"Metric is not registered: {assertion.metric}",
            evidence_digest=evidence_digest,
        )
    if assertion.unit != definition.unit:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="blocked",
            query_id=_query_id(assertion.metric),
            reason=(
                f"Claim unit {assertion.unit} does not match registered metric unit "
                f"{definition.unit}"
            ),
            evidence_digest=evidence_digest,
        )

    try:
        observed = compute_metric(
            assertion.metric,
            events,
            assertion.subject,
            assertion.window,
        )
    except ValueError as error:
        return VerificationResult(
            claim_id=claim.claim_id,
            status="blocked",
            query_id=_query_id(assertion.metric),
            reason=f"Metric recomputation failed: {error}",
            expected=assertion.value,
            evidence_digest=evidence_digest,
        )

    passed = _comparison_passes(assertion.comparator, assertion.value, observed, assertion.decimals)
    query_id = _query_id(assertion.metric)
    reason = (
        "Registered metric recomputation satisfies the claim comparator"
        if passed
        else "Registered metric recomputation does not satisfy the claim comparator"
    )
    if passed:
        counted_type = _COUNTED_TYPES.get(assertion.metric)
        if counted_type is not None and not _cites_counted_events(claim, events, counted_type):
            passed, reason = False, "Claim cites events the registered metric does not count"
    if passed:
        problem = text_binding_problem(claim, names, events)
        if problem is not None:
            passed, query_id, reason = False, TEXT_QUERY_ID, problem
    return VerificationResult(
        claim_id=claim.claim_id,
        status="verified" if passed else "needs_revision",
        query_id=query_id,
        reason=reason,
        expected=assertion.value,
        observed=observed,
        evidence_digest=evidence_digest,
    )


def _cites_counted_events(claim: Claim, events: tuple[MatchEvent, ...], counted_type: str) -> bool:
    """Every cited event must be one the count metric counts for this subject and window."""
    assertion = claim.assertion
    assert assertion is not None
    window, subject = assertion.window, assertion.subject
    counted = {
        event.event_id
        for event in events
        if event.type == counted_type
        and (window.period is None or event.period == window.period)
        and window.from_ms <= event.match_clock_ms < window.to_ms
        and (subject.team_id is None or event.team_id == subject.team_id)
        and (subject.player_id is None or event.player_id == subject.player_id)
    }
    return all(event_id in counted for event_id in claim.evidence_event_ids)
