"""Phase 3 tests for exact-version producer review and approval state."""

import pytest

from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.producer_review import (
    approved_binding,
    open_revision,
    record_decision,
    record_reverification,
    start_review,
)


def _binding(version: int, *, content: str = "a", evidence: str = "b") -> ApprovalBinding:
    """Create one deterministic approval binding for producer-review tests."""
    return ApprovalBinding(
        item_id="story-1",
        item_version=version,
        replay_id="replay-1",
        content_digest=content * 64,
        evidence_digest=evidence * 64,
        language="en",
        persona="analyst",
    )


def test_approval_requires_reverification_of_current_binding() -> None:
    """An unverified content version cannot receive producer approval."""
    binding = _binding(1)
    state = start_review(binding, actor_id="producer-1")

    with pytest.raises(ValueError, match="requires reverification"):
        record_decision(
            state,
            binding,
            actor_id="producer-1",
            decision="approve",
            reason="Ready to publish",
        )

    assert approved_binding(state) is None


def test_reverified_current_version_can_be_approved() -> None:
    """A producer can approve only the exact binding that was reverified."""
    binding = _binding(1)
    state = start_review(binding, actor_id="producer-1")
    state = record_reverification(state, binding, actor_id="producer-1")
    state = record_decision(
        state,
        binding,
        actor_id="producer-1",
        decision="approve",
        reason="Evidence checked and wording approved",
    )

    assert state.status == "approved"
    assert approved_binding(state) == binding
    assert [entry.action for entry in state.audit] == [
        "review_started",
        "reverified",
        "approved",
    ]


def test_stale_binding_cannot_be_reverified_or_decided() -> None:
    """A producer action cannot silently bind to a different content version."""
    current = _binding(2, content="c")
    stale = _binding(1)
    state = start_review(current, actor_id="producer-1")

    with pytest.raises(ValueError, match="current review version"):
        record_reverification(state, stale, actor_id="producer-1")

    with pytest.raises(ValueError, match="current review version"):
        record_decision(
            state,
            stale,
            actor_id="producer-1",
            decision="reject",
            reason="Stale version",
        )


def test_new_revision_invalidates_prior_approval_and_preserves_history() -> None:
    """Editing to a newer version removes publishable approval until reverification."""
    first = _binding(1)
    state = start_review(first, actor_id="producer-1")
    state = record_reverification(state, first, actor_id="producer-1")
    state = record_decision(
        state,
        first,
        actor_id="producer-1",
        decision="approve",
        reason="First version approved",
    )

    second = _binding(2, content="c", evidence="d")
    state = open_revision(
        state,
        second,
        actor_id="producer-1",
        reason="Producer edited the story",
    )

    assert state.status == "pending_verification"
    assert approved_binding(state) is None
    assert state.binding == second
    assert [entry.action for entry in state.audit] == [
        "review_started",
        "reverified",
        "approved",
        "revision_opened",
    ]


def test_revision_must_be_strictly_newer_and_keep_variant_scope() -> None:
    """Version chains cannot roll back or cross replay/language/persona boundaries."""
    state = start_review(_binding(2), actor_id="producer-1")

    with pytest.raises(ValueError, match="must increase"):
        open_revision(state, _binding(2), actor_id="producer-1")

    other_language = _binding(3).model_copy(update={"language": "fr"})
    with pytest.raises(ValueError, match="language and persona"):
        open_revision(state, other_language, actor_id="producer-1")


def test_rejection_is_terminal_for_current_version() -> None:
    """A rejected binding requires a new revision before another decision."""
    binding = _binding(1)
    state = start_review(binding, actor_id="producer-1")
    state = record_decision(
        state,
        binding,
        actor_id="producer-1",
        decision="reject",
        reason="Needs a clearer evidence explanation",
    )

    assert state.status == "rejected"
    assert approved_binding(state) is None

    with pytest.raises(ValueError, match="already terminal"):
        record_decision(
            state,
            binding,
            actor_id="producer-1",
            decision="reject",
            reason="Duplicate rejection",
        )


def test_actor_and_reason_are_auditable_non_blank_values() -> None:
    """Blank producer identity or transition reasons are rejected."""
    binding = _binding(1)

    with pytest.raises(ValueError, match="actor_id"):
        start_review(binding, actor_id=" ")

    state = start_review(binding, actor_id="producer-1")
    with pytest.raises(ValueError, match="reason"):
        record_decision(
            state,
            binding,
            actor_id="producer-1",
            decision="reject",
            reason=" ",
        )
