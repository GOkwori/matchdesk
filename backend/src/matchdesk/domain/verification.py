"""Deterministic claim verification for MatchDesk Phase 2B.

Verification recomputes registered measurements and checks evidence identity. It never
treats structurally valid prose as factual truth and grants no publication authority.
"""

from __future__ import annotations

import math

from matchdesk.domain.hashing import content_digest
from matchdesk.domain.metrics import METRIC_DEFINITIONS, compute_metric
from matchdesk.domain.models import Claim, EvidenceRecord, MatchEvent, VerificationResult


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


def _comparison_passes(comparator: str, expected: float, observed: float) -> bool:
    """Evaluate the declared metric comparator without rounding away discrepancies."""
    if comparator == "eq":
        return math.isclose(observed, expected, rel_tol=1e-9, abs_tol=1e-9)
    if comparator == "gte":
        return observed >= expected
    if comparator == "lte":
        return observed <= expected
    raise ValueError(f"unsupported comparator: {comparator}")


def verify_claim(
    claim: Claim,
    evidence: EvidenceRecord,
    events: tuple[MatchEvent, ...],
) -> VerificationResult:
    """Verify one claim against deterministic evidence and registered Phase 1 queries."""
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

    if claim.kind == "tactical_inference":
        return VerificationResult(
            claim_id=claim.claim_id,
            status="supported_inference",
            query_id="evidence-support-v1",
            reason="All cited evidence events exist; tactical meaning remains an inference",
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

    passed = _comparison_passes(assertion.comparator, assertion.value, observed)
    return VerificationResult(
        claim_id=claim.claim_id,
        status="verified" if passed else "needs_revision",
        query_id=_query_id(assertion.metric),
        reason=(
            "Registered metric recomputation satisfies the claim comparator"
            if passed
            else "Registered metric recomputation does not satisfy the claim comparator"
        ),
        expected=assertion.value,
        observed=observed,
        evidence_digest=evidence_digest,
    )
