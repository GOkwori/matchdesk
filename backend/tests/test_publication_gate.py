"""Phase 3 tests for exact-binding publication authorization."""

from dataclasses import replace

import pytest
from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.producer_review import (
    ProducerAuditEntry,
    ProducerReviewState,
    open_revision,
    record_decision,
    record_reverification,
    start_review,
)
from matchdesk.domain.publication_gate import authorize_publication


def _binding(
    version: int,
    *,
    content: str = "a",
    evidence: str = "b",
    language: str = "en",
    persona: str = "analyst",
) -> ApprovalBinding:
    """Create one deterministic publication binding."""
    return ApprovalBinding(
        item_id="story-1",
        item_version=version,
        replay_id="replay-1",
        content_digest=content * 64,
        evidence_digest=evidence * 64,
        language=language,
        persona=persona,
    )


def _approved_state() -> ProducerReviewState:
    """Create one legitimately reverified and producer-approved review state."""
    binding = _binding(1)
    state = start_review(binding, actor_id="producer-1")
    state = record_reverification(state, binding, actor_id="producer-1")
    return record_decision(
        state,
        binding,
        actor_id="producer-1",
        decision="approve",
        reason="Evidence and wording approved",
    )


def test_exact_current_approved_binding_is_authorized() -> None:
    """The publication gate returns immutable approval provenance on exact match."""
    state = _approved_state()

    authorization = authorize_publication(
        state,
        state.binding,
        publisher_actor_id="publisher-1",
    )

    assert authorization.binding == state.binding
    assert authorization.producer_actor_id == "producer-1"
    assert authorization.publisher_actor_id == "publisher-1"


@pytest.mark.parametrize("status", ["pending_verification", "ready_for_decision", "rejected"])
def test_unapproved_review_states_cannot_publish(status: str) -> None:
    """Only the terminal approved state can cross the publication boundary."""
    binding = _binding(1)
    state = ProducerReviewState(binding=binding, status=status, audit=())

    with pytest.raises(PermissionError, match="requires producer approval"):
        authorize_publication(state, binding, publisher_actor_id="publisher-1")


def test_new_revision_invalidates_prior_publication_authority() -> None:
    """An edit after approval requires reverification and a fresh producer approval."""
    approved = _approved_state()
    revised = open_revision(
        approved,
        _binding(2, content="c", evidence="d"),
        actor_id="producer-1",
    )

    with pytest.raises(PermissionError, match="requires producer approval"):
        authorize_publication(
            revised,
            revised.binding,
            publisher_actor_id="publisher-1",
        )


@pytest.mark.parametrize(
    "candidate",
    [
        _binding(2),
        _binding(1, content="c"),
        _binding(1, evidence="d"),
        _binding(1, language="fr"),
        _binding(1, persona="casual_fan"),
    ],
)
def test_any_binding_drift_is_blocked(candidate: ApprovalBinding) -> None:
    """Version, content, evidence, language and persona must match the approval."""
    state = _approved_state()

    with pytest.raises(PermissionError, match="approved current version"):
        authorize_publication(
            state,
            candidate,
            publisher_actor_id="publisher-1",
        )


def test_status_only_forgery_without_approval_audit_is_blocked() -> None:
    """An approved status flag alone cannot manufacture publication authority."""
    binding = _binding(1)
    forged = ProducerReviewState(binding=binding, status="approved", audit=())

    with pytest.raises(PermissionError, match="approval audit record"):
        authorize_publication(
            forged,
            binding,
            publisher_actor_id="publisher-1",
        )


def test_latest_audit_entry_must_be_current_approval() -> None:
    """A stale or contradictory terminal audit cannot authorize publication."""
    state = _approved_state()
    forged_entry = ProducerAuditEntry(
        action="revision_opened",
        actor_id="producer-1",
        binding=_binding(2),
        reason="Forged later transition",
    )
    forged = replace(state, audit=state.audit + (forged_entry,))

    with pytest.raises(PermissionError, match="Latest producer audit entry"):
        authorize_publication(
            forged,
            state.binding,
            publisher_actor_id="publisher-1",
        )


def test_blank_publisher_identity_is_rejected() -> None:
    """Publication authorization must retain a host-established publisher actor."""
    state = _approved_state()

    with pytest.raises(ValueError, match="Publisher actor_id"):
        authorize_publication(
            state,
            state.binding,
            publisher_actor_id=" ",
        )
