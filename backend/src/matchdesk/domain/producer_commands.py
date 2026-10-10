"""Fail-closed P3-05 producer command boundary, without HTTP publication.

A verified actor must be supplied by a trusted identity adapter. Nothing in this
module authenticates a bearer token, accepts identity from request JSON, persists an
approval or publishes. A durable adapter must implement atomic compare-and-swap.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Protocol

from matchdesk.domain.broadcast_outputs import BroadcastEnvelope
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import Claim, EvidenceRecord, MatchEvent
from matchdesk.domain.producer_review import (
    ProducerReviewState,
    open_revision,
    record_decision,
    record_reverification,
    start_review,
)
from matchdesk.domain.verification import verify_claim

ProducerCommand = Literal["edit", "reverify", "approve", "reject"]
ProducerRole = Literal["producer", "auditor", "publisher"]


@dataclass(frozen=True)
class HostVerifiedActor:
    """Identity claims accepted only after a trusted external OIDC validation.

    This dataclass is not an authentication mechanism. Never populate it from
    request-supplied headers, roles, cookies or JSON without validating the issuer,
    audience, signature, expiration, tenant and session entitlements at the edge.
    """

    subject: str
    tenant_id: str
    issuer: str
    roles: frozenset[ProducerRole]
    permitted_sessions: frozenset[str]

    def __post_init__(self) -> None:
        """Reject missing principal context instead of defaulting to permissions."""
        if not self.subject.strip() or not self.tenant_id.strip() or not self.issuer.strip():
            raise ValueError("Host-verified identity requires subject, tenant and issuer")
        if not self.roles or not self.roles.issubset({"producer", "auditor", "publisher"}):
            raise ValueError("Producer principal contains invalid or missing roles")
        if not self.permitted_sessions or any(not item.strip() for item in self.permitted_sessions):
            raise ValueError("Producer principal requires explicit session entitlements")


@dataclass(frozen=True)
class ProducerCase:
    """One evidence-backed draft and its immutable local review-state generation."""

    tenant_id: str
    output: BroadcastEnvelope
    claims: tuple[Claim, ...]
    evidence: EvidenceRecord
    accepted_events: tuple[MatchEvent, ...]
    review: ProducerReviewState
    generation: int


class ProducerCaseStore(Protocol):
    """Host-owned storage with atomic compare-and-swap in one DB transaction."""

    def load(self, tenant_id: str, session_id: str, output_id: str) -> ProducerCase | None:
        """Load the current case from a tenant- and session-scoped record."""

    def replace_if_generation(
        self,
        case: ProducerCase,
        *,
        expected_generation: int,
    ) -> bool:
        """Atomically save the case and audit or return False on any race."""


def _authorize(actor: HostVerifiedActor, tenant_id: str, session_id: str) -> None:
    """Require exact tenant, explicit session grant and the producer role."""
    if actor.tenant_id != tenant_id or session_id not in actor.permitted_sessions:
        raise PermissionError("Producer actor is not authorized for the requested session")
    if "producer" not in actor.roles:
        raise PermissionError("Producer mutation requires a producer role")



def _validate_review_history(case: ProducerCase) -> None:
    """Reconstruct every review transition instead of trusting a stored status flag.

    Frozen dataclasses prevent accidental changes, not forged or corrupt storage.
    Replaying the existing state machine verifies the complete version-bound audit,
    the status and the one-audit-entry-per-generation invariant before mutation.
    This does not authenticate the recorded actors or replace a trusted audit store.
    """
    audit = case.review.audit
    if not audit or audit[0].action != "review_started" or case.generation != len(audit):
        raise ValueError("Producer review must have one valid audit entry per generation")

    initial = audit[0]
    reconstructed = start_review(
        initial.binding, actor_id=initial.actor_id, reason=initial.reason
    )
    for entry in audit[1:]:
        if entry.action == "revision_opened":
            reconstructed = open_revision(
                reconstructed, entry.binding, actor_id=entry.actor_id, reason=entry.reason
            )
        elif entry.action == "reverified":
            reconstructed = record_reverification(
                reconstructed, entry.binding, actor_id=entry.actor_id, reason=entry.reason
            )
        elif entry.action in ("approved", "rejected"):
            decision: Literal["approve", "reject"] = (
                "approve" if entry.action == "approved" else "reject"
            )
            reconstructed = record_decision(
                reconstructed,
                entry.binding,
                actor_id=entry.actor_id,
                decision=decision,
                reason=entry.reason,
            )
        else:
            raise ValueError("Producer review contains an unsupported audit transition")

    if reconstructed != case.review:
        raise ValueError("Producer review state does not match its immutable audit history")


def _validate_case(case: ProducerCase) -> None:
    """Recheck the source, claim, content and review bindings at each command boundary."""
    _validate_review_history(case)
    draft = case.output
    evidence = case.evidence
    if (
        draft.binding.content_digest != content_digest(draft.payload)
        or draft.binding.evidence_digest != content_digest(evidence)
        or draft.binding != case.review.binding
    ):
        raise ValueError("Producer case contains stale or inconsistent review bindings")
    if (
        case.generation < 1
        or not case.tenant_id.strip()
        or evidence.match_id != draft.match_id
        or evidence.replay_id != draft.binding.replay_id
        or draft.evidence_ids != (evidence.evidence_id,)
        or evidence.window not in draft.windows
    ):
        raise ValueError("Producer case evidence is outside the bound match and replay")
    ids = tuple(claim.claim_id for claim in case.claims)
    if len(ids) != len(set(ids)) or set(ids) != set(draft.claim_ids):
        raise ValueError("Producer case must contain every source claim exactly once")
    if not case.accepted_events:
        raise ValueError("Producer case requires accepted source events")
    event_ids = {event.event_id for event in case.accepted_events}
    if (
        any(event.match_id != draft.match_id for event in case.accepted_events)
        or not set(evidence.event_ids).issubset(event_ids)
        or any(
            not set(claim.evidence_event_ids).issubset(set(evidence.event_ids))
            for claim in case.claims
        )
    ):
        raise ValueError("Producer case claims and events must belong to the exact evidence")


def _recompute_claims(case: ProducerCase) -> None:
    """Fail closed unless all claimed metrics independently pass source verification.

    Accepted tactical inferences remain labelled as inference; this step does not
    prove that a rewritten natural-language sentence preserves its factual meaning.
    """
    for claim in case.claims:
        result = verify_claim(claim, case.evidence, case.accepted_events)
        if result.evidence_digest != case.output.binding.evidence_digest:
            raise ValueError("Producer verification has drifted from the source evidence")
        if result.status not in ("verified", "supported_inference"):
            raise ValueError("Producer action requires passing deterministic reverification")


def open_producer_case(
    *,
    actor: HostVerifiedActor,
    tenant_id: str,
    output: BroadcastEnvelope,
    claims: tuple[Claim, ...],
    evidence: EvidenceRecord,
    accepted_events: tuple[MatchEvent, ...],
) -> ProducerCase:
    """Prepare an unapproved case from host-owned source records, without persisting."""
    _authorize(actor, tenant_id, output.session_id)
    case = ProducerCase(
        tenant_id=tenant_id,
        output=output,
        claims=claims,
        evidence=evidence,
        accepted_events=accepted_events,
        review=start_review(output.binding, actor_id=actor.subject),
        generation=1,
    )
    _validate_case(case)
    return case


def apply_producer_command(
    case: ProducerCase,
    *,
    actor: HostVerifiedActor,
    expected_generation: int,
    command: ProducerCommand,
    reason: str,
    revised_output: BroadcastEnvelope | None = None,
) -> ProducerCase:
    """Apply one exact-generation transition without granting publication authority."""
    _authorize(actor, case.tenant_id, case.output.session_id)
    if case.generation != expected_generation:
        raise RuntimeError("Producer case generation conflict")
    _validate_case(case)
    current = case.output
    if command == "edit":
        if revised_output is None:
            raise ValueError("Producer edit requires a new validated output")
        # model_copy(update=...) bypasses Pydantic validators: reconstruct the model.
        revised = BroadcastEnvelope.model_validate(revised_output.model_dump(mode="json"))
        if (
            revised.output_id != current.output_id
            or revised.session_id != current.session_id
            or revised.match_id != current.match_id
            or revised.windows != current.windows
            or revised.evidence_ids != current.evidence_ids
            or revised.claim_ids != current.claim_ids
            or revised.payload.kind != current.payload.kind
            or revised.binding.evidence_digest != current.binding.evidence_digest
            or revised.binding.item_version != current.binding.item_version + 1
        ):
            raise ValueError("Producer edit must preserve scope and advance one version")
        review = open_revision(
            case.review,
            revised.binding,
            actor_id=actor.subject,
            reason=reason,
        )
        return replace(case, output=revised, review=review, generation=case.generation + 1)

    if revised_output is not None:
        raise ValueError("Only edit may supply a revised output")
    if command == "reverify":
        _recompute_claims(case)
        review = record_reverification(
            case.review, current.binding, actor_id=actor.subject, reason=reason
        )
    elif command in ("approve", "reject"):
        if command == "approve":
            _recompute_claims(case)
        review = record_decision(
            case.review,
            current.binding,
            actor_id=actor.subject,
            decision="approve" if command == "approve" else "reject",
            reason=reason,
        )
    else:
        raise ValueError("Unsupported producer command")
    return replace(case, review=review, generation=case.generation + 1)


def execute_producer_command(
    store: ProducerCaseStore,
    *,
    actor: HostVerifiedActor,
    tenant_id: str,
    session_id: str,
    output_id: str,
    expected_generation: int,
    command: ProducerCommand,
    reason: str,
    revised_output: BroadcastEnvelope | None = None,
) -> ProducerCase:
    """Load, authorize and atomically save one command; never retry a racing write."""
    _authorize(actor, tenant_id, session_id)
    case = store.load(tenant_id, session_id, output_id)
    if case is None:
        raise LookupError("Producer case does not exist in the authorized session")
    if (
        case.tenant_id != tenant_id
        or case.output.session_id != session_id
        or case.output.output_id != output_id
    ):
        raise PermissionError("Producer store returned an out-of-scope case")
    updated = apply_producer_command(
        case,
        actor=actor,
        expected_generation=expected_generation,
        command=command,
        reason=reason,
        revised_output=revised_output,
    )
    if not store.replace_if_generation(updated, expected_generation=expected_generation):
        raise RuntimeError("Concurrent producer case update; reload before retrying")
    return updated
