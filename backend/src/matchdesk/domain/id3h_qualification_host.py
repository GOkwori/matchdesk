"""CI-only approval qualification boundary without migration execution authority.

Real identity verification, evidence discovery, key provisioning and clocks MUST
be established by a future trusted execution host. This module only exercises
that separation against disposable test dependencies and returns a non-execution
receipt. It does not mount a route, publish credentials or execute migrations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from matchdesk.domain.id3h_approval_reservations import DisposableApprovalReservationStore
from matchdesk.domain.id3h_release_approval import (
    ENVIRONMENT,
    ObservedReleaseFacts,
    ReleaseDenied,
    reserve_disposable_release_approval,
)


class TrustedCIHostSource(Protocol):
    """Provide independently authenticated/observed state, never caller claims.

    This contract is NOT an authenticator. A future host must independently
    authenticate the workload, pin keys and observe the actual target database.
    """

    def verified_actor(self) -> str:
        """Return the identity proven at the protected workload boundary."""
        ...

    def observe_release(self) -> ObservedReleaseFacts:
        """Observe exact target, source and evidence through trusted channels."""
        ...

    def approval_key(self) -> Ed25519PublicKey:
        """Return a pinned key from a trusted store, never a signed token."""
        ...

    def utcnow(self) -> datetime:
        """Return the trusted host's timezone-aware wall clock."""
        ...


@dataclass(frozen=True, slots=True)
class QualificationReceipt:
    """Offline evidence only; explicitly grants no authority to migrate."""

    approval_id: str
    environment: Literal["disposable-ci"] = "disposable-ci"
    execution_authorized: Literal[False] = False


class DisposableApprovalQualificationHost:
    """Exercise trusted dependency ordering without an execution capability."""

    def __init__(
        self, *, source: TrustedCIHostSource, reservations: DisposableApprovalReservationStore
    ) -> None:
        """Require host-side inputs and a real durable disposable reservation store."""
        if type(reservations) is not DisposableApprovalReservationStore:
            raise ValueError("An approved disposable CI reservation store is required")
        self._source = source
        self._reservations = reservations

    def qualify(self, signed_envelope: str) -> QualificationReceipt:
        """Deny untrusted/changed host facts and reserve only a CI grant once.

        Both the observed actor and target are checked again after reservation,
        so changing authorization state fails closed; consumed grants stay used.
        This method has no migration or provider activation functionality.
        """
        try:
            actor = self._source.verified_actor()
            observed = self._source.observe_release()
            if (
                type(actor) is not str
                or not actor
                or type(observed) is not ObservedReleaseFacts
                or observed.operator_id != actor
                or observed.environment != ENVIRONMENT
            ):
                raise ReleaseDenied("ID3H qualification approval denied")
            approval_id = reserve_disposable_release_approval(
                signed_envelope,
                observed=observed,
                trusted_public_key=self._source.approval_key(),
                reservation_store=self._reservations,
                now=self._source.utcnow(),
            )
            # Failure after the durable consume denies safely; it NEVER
            # restores the consumed approval for another attempt.
            if self._source.verified_actor() != actor or self._source.observe_release() != observed:
                raise ReleaseDenied("ID3H qualification approval denied")
            return QualificationReceipt(approval_id=approval_id)
        except Exception:
            # Fail closed on all host/dependency outages and never leak evidence.
            raise ReleaseDenied("ID3H qualification approval denied") from None
