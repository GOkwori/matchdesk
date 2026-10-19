"""DEV-only transaction-scoped, single-use producer grant consumption.

This is not an Entra/MFA adapter. A trusted host must verify a real workforce
actor and step-up and retrieve the opaque grant ID from protected server state.
Only the committed database grant row conveys execution authority. The UPDATE
locks that row until the enclosing case/audit transaction commits, serializing
concurrent revocation and writes without a separate check/write gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.producer_commands import HostVerifiedActor, ProducerCase

GrantAction = Literal["create", "edit", "reverify", "approve", "reject"]
_AUDIT_ACTION = {
    "edit": "revision_opened",
    "reverify": "reverified",
    "approve": "approved",
    "reject": "rejected",
}
_CONSUME = """
UPDATE matchdesk_producer_execution_grants
SET consumed_at = clock_timestamp()
WHERE grant_id = %s::uuid AND tenant_id = %s AND actor_subject = %s
  AND actor_issuer = %s AND action = %s AND session_id = %s
  AND output_id = %s AND expected_generation = %s AND binding_digest = %s
  AND revoked_at IS NULL AND consumed_at IS NULL
  AND expires_at > clock_timestamp()
RETURNING grant_id
"""


class GrantCursor(Protocol):
    """Cursor from the same open PostgreSQL transaction as the eventual write."""

    def execute(self, sql: str, parameters: tuple[object, ...]) -> object:
        """Execute one bound SQL statement."""

    def fetchone(self) -> tuple[object, ...] | None:
        """Return the consumed row, if any."""


@dataclass(frozen=True, slots=True)
class ProducerGrantAttempt:
    """Server-selected grant handle, never a self-authenticating credential.

    A browser request or model output must not choose or construct grant IDs.
    """

    grant_id: UUID
    actor: HostVerifiedActor
    action: GrantAction
    session_id: str
    output_id: str
    binding: ApprovalBinding
    expected_generation: int

    def __post_init__(self) -> None:
        """Reject malformed principals, generations and missing session grants."""
        if (
            type(self.grant_id) is not UUID
            or self.grant_id.int == 0
            or type(self.actor) is not HostVerifiedActor
            or type(self.binding) is not ApprovalBinding
            or self.action not in ("create", "edit", "reverify", "approve", "reject")
            or type(self.session_id) is not str
            or type(self.output_id) is not str
            or not self.session_id
            or not self.output_id
            or type(self.expected_generation) is not int
            or self.expected_generation < 0
            or (self.action == "create") != (self.expected_generation == 0)
            or "producer" not in self.actor.roles
            or self.session_id not in self.actor.permitted_sessions
        ):
            raise PermissionError("Invalid producer grant attempt")


def consume_execution_grant(
    cursor: GrantCursor,
    *,
    attempt: ProducerGrantAttempt,
    case: ProducerCase,
    creating: bool,
) -> bool:
    """Consume the exact live grant on the same transaction as case and audit.

    UPDATE obtains a row lock. When revocation commits first, its changed row
    makes this UPDATE return no row. When consumption locks first, revocation
    waits for the complete case/audit commit. Never separate the transactions.
    """
    if type(attempt) is not ProducerGrantAttempt:
        raise PermissionError("Producer execution requires a server-held grant reference")
    if (
        case.tenant_id != attempt.actor.tenant_id
        or case.output.session_id != attempt.session_id
        or case.output.output_id != attempt.output_id
        or case.review.audit[-1].actor_id != attempt.actor.subject
    ):
        raise PermissionError("Producer grant scope does not match this case")
    if creating:
        if (
            attempt.action != "create"
            or case.generation != 1
            or case.review.audit[-1].action != "review_started"
            or case.output.binding != attempt.binding
        ):
            raise PermissionError("Creation grant does not match the initial case")
    elif (
        attempt.action == "create"
        or len(case.review.audit) < 2
        or case.generation != attempt.expected_generation + 1
        or case.review.audit[-1].action != _AUDIT_ACTION.get(attempt.action)
        or case.review.audit[-2].binding != attempt.binding
    ):
        raise PermissionError("Execution grant does not match the reviewed transition")

    cursor.execute(
        _CONSUME,
        (
            str(attempt.grant_id),
            attempt.actor.tenant_id,
            attempt.actor.subject,
            attempt.actor.issuer,
            attempt.action,
            attempt.session_id,
            attempt.output_id,
            attempt.expected_generation,
            content_digest(attempt.binding),
        ),
    )
    row = cursor.fetchone()
    return type(row) is tuple and len(row) == 1 and str(row[0]) == str(attempt.grant_id)
