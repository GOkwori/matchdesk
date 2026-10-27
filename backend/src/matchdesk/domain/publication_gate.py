"""Version-bound publication authorization for human-approved producer content.

This pure domain gate does not publish content or authenticate callers. It verifies that
the host is attempting to publish exactly the binding that the producer approved and
returns an immutable authorization record for a later delivery adapter.
"""

from __future__ import annotations

from dataclasses import dataclass

from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.producer_review import ProducerReviewState


@dataclass(frozen=True)
class PublicationAuthorization:
    """Immutable proof that one exact producer-approved binding may be published."""

    binding: ApprovalBinding
    producer_actor_id: str
    publisher_actor_id: str


def _publisher_actor(actor_id: str) -> str:
    """Require a non-blank host-established publisher identity."""
    value = actor_id.strip()
    if not value:
        raise ValueError("Publisher actor_id cannot be blank")
    return value


def authorize_publication(
    state: ProducerReviewState,
    binding: ApprovalBinding,
    *,
    publisher_actor_id: str,
) -> PublicationAuthorization:
    """Authorize publication only for the exact currently approved binding.

    The latest audit entry must itself be the approval for the current binding. This
    prevents a caller from manufacturing a status-only state that bypasses the producer
    decision history.
    """
    if state.status != "approved":
        raise PermissionError("Publication requires producer approval")
    if binding != state.binding:
        raise PermissionError("Publication binding must match the approved current version")
    if not state.audit:
        raise PermissionError("Publication requires an approval audit record")

    approval = state.audit[-1]
    if approval.action != "approved" or approval.binding != state.binding:
        raise PermissionError("Latest producer audit entry must approve the current version")

    return PublicationAuthorization(
        binding=binding,
        producer_actor_id=approval.actor_id,
        publisher_actor_id=_publisher_actor(publisher_actor_id),
    )
