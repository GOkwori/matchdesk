"""Human-governed producer review and exact-version approval state.

Phase 3 begins by making producer decisions explicit, immutable and bound to the same
ApprovalBinding fields that a later publication gate will compare. This module does not
authenticate actors or publish content; those responsibilities remain outside the pure
domain state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from matchdesk.domain.models import ApprovalBinding

ReviewStatus = Literal[
    "pending_verification",
    "ready_for_decision",
    "approved",
    "rejected",
]
AuditAction = Literal[
    "review_started",
    "reverified",
    "approved",
    "rejected",
    "revision_opened",
]


@dataclass(frozen=True)
class ProducerAuditEntry:
    """Immutable record of one producer-review transition."""

    action: AuditAction
    actor_id: str
    binding: ApprovalBinding
    reason: str


@dataclass(frozen=True)
class ProducerReviewState:
    """Current review state plus immutable transition history."""

    binding: ApprovalBinding
    status: ReviewStatus
    audit: tuple[ProducerAuditEntry, ...]


def _actor(actor_id: str) -> str:
    """Require a non-blank host-established actor identifier."""
    value = actor_id.strip()
    if not value:
        raise ValueError("Producer actor_id cannot be blank")
    return value


def _reason(reason: str) -> str:
    """Require an auditable non-blank transition reason."""
    value = reason.strip()
    if not value:
        raise ValueError("Producer review reason cannot be blank")
    return value


def start_review(
    binding: ApprovalBinding,
    *,
    actor_id: str,
    reason: str = "Producer review opened",
) -> ProducerReviewState:
    """Open review for one exact content/evidence/language/persona binding."""
    entry = ProducerAuditEntry(
        action="review_started",
        actor_id=_actor(actor_id),
        binding=binding,
        reason=_reason(reason),
    )
    return ProducerReviewState(
        binding=binding,
        status="pending_verification",
        audit=(entry,),
    )


def record_reverification(
    state: ProducerReviewState,
    binding: ApprovalBinding,
    *,
    actor_id: str,
    reason: str = "Current version reverified",
) -> ProducerReviewState:
    """Mark the exact current binding ready for a human producer decision."""
    if binding != state.binding:
        raise ValueError("Reverification binding must match the current review version")
    if state.status in ("approved", "rejected"):
        raise ValueError("A terminal producer decision requires a new revision")
    entry = ProducerAuditEntry(
        action="reverified",
        actor_id=_actor(actor_id),
        binding=binding,
        reason=_reason(reason),
    )
    return ProducerReviewState(
        binding=state.binding,
        status="ready_for_decision",
        audit=state.audit + (entry,),
    )


def record_decision(
    state: ProducerReviewState,
    binding: ApprovalBinding,
    *,
    actor_id: str,
    decision: Literal["approve", "reject"],
    reason: str,
) -> ProducerReviewState:
    """Record an exact-binding producer approval or rejection.

    Approval requires prior reverification of the current binding. Rejection may occur
    before or after reverification, but never against a stale version.
    """
    if binding != state.binding:
        raise ValueError("Producer decision binding must match the current review version")
    if state.status in ("approved", "rejected"):
        raise ValueError("Producer decision is already terminal for this version")
    if decision == "approve" and state.status != "ready_for_decision":
        raise ValueError("Approval requires reverification of the current version")

    action: AuditAction = "approved" if decision == "approve" else "rejected"
    entry = ProducerAuditEntry(
        action=action,
        actor_id=_actor(actor_id),
        binding=binding,
        reason=_reason(reason),
    )
    return ProducerReviewState(
        binding=state.binding,
        status="approved" if decision == "approve" else "rejected",
        audit=state.audit + (entry,),
    )


def open_revision(
    state: ProducerReviewState,
    binding: ApprovalBinding,
    *,
    actor_id: str,
    reason: str = "Producer opened a new content revision",
) -> ProducerReviewState:
    """Open a strictly newer version and invalidate any prior approval."""
    current = state.binding
    if binding.item_id != current.item_id:
        raise ValueError("Revision must retain the same item_id")
    if binding.replay_id != current.replay_id:
        raise ValueError("Revision must retain the same replay_id")
    if binding.language != current.language or binding.persona != current.persona:
        raise ValueError("Revision must retain the same language and persona")
    if binding.item_version <= current.item_version:
        raise ValueError("Revision item_version must increase")

    entry = ProducerAuditEntry(
        action="revision_opened",
        actor_id=_actor(actor_id),
        binding=binding,
        reason=_reason(reason),
    )
    return ProducerReviewState(
        binding=binding,
        status="pending_verification",
        audit=state.audit + (entry,),
    )


def approved_binding(state: ProducerReviewState) -> ApprovalBinding | None:
    """Return the exact currently approved binding, otherwise fail closed with None."""
    if state.status != "approved":
        return None
    return state.binding
