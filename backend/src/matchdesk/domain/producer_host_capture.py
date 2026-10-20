"""Inert host-only verification contract for a real producer dialog event.

This does NOT receive HTTP requests, sign approvals, open SQL connections or
assert that an Entra user was actually present. The injected host source must
independently authenticate the operator and atomically consume its challenge.
An unreviewed browser or agent adapter cannot supply this source safely.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol

from matchdesk.domain.producer_confirmation_provenance import HostConfirmationRecord
from matchdesk.domain.producer_grant_preflight import (
    GrantAction,
    ProducerGrantPreflight,
)
from matchdesk.domain.producer_policy_assurance import (
    ProducerPolicyAssuranceProvider,
    qualify_producer_policy_assurance,
)

_ID = re.compile(r"[a-f0-9]{32}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_ACTIONS = frozenset(("create", "edit", "reverify", "approve", "reject"))
_MAX_INTERACTION_AGE_SECONDS = 120


@dataclass(frozen=True, slots=True)
class VerifiedOperatorDialogEvent:
    """Host-resolved one-time operator action, not caller self-attestation.

    Only a trusted server adapter may construct this after verifying a fresh
    authenticated workforce session, server-side dialog challenge, same-origin
    CSRF protection, deliberate user confirmation and independent audit trail.
    The dataclass itself is NOT security evidence outside that trust boundary.
    """

    event_id: str
    challenge_id: str
    confirmation_id: str
    tenant_id: str
    actor_id: str
    token_issuer: str
    session_id: str
    output_id: str
    action: GrantAction
    expected_generation: int
    authorized_case_sha256: str
    authorized_audit_digest: str
    interaction_method: Literal["workforce_authenticated_custom_dialog"]
    confirmed_at_seconds: int
    verified_at_seconds: int


class TrustedOperatorDialogSource(Protocol):
    """Host-owned store that atomically consumes an authenticated challenge.

    A real implementation MUST verify the originating human on the server,
    reject replay, enforce origin/CSRF/session binding and return only an
    independently auditable, single-use result. Never adapt request JSON,
    model output, an arbitrary Boolean, or a decoded JWT claim to this API.
    """

    def consume_verified_dialog_event(
        self, *, confirmation_id: str, tenant_id: str
    ) -> VerifiedOperatorDialogEvent | None:
        """Consume a unique authenticated confirmation event or deny."""


def qualify_host_operator_confirmation(
    *,
    source: TrustedOperatorDialogSource,
    policy_assurance: ProducerPolicyAssuranceProvider,
    preflight: ProducerGrantPreflight,
    signed_envelope: str,
    context_id: str,
    client_ids: frozenset[str],
    now: datetime,
) -> HostConfirmationRecord:
    """Correlate host-only human interaction, current CA and signed intent.

    This is a necessary capture preflight, not a database write, actual
    authentication service, signing capability or executable action grant.
    A future host recorder must recheck authorization and write with an
    isolated, insert-only login after this function returns.
    """
    try:
        if (
            type(preflight) is not ProducerGrantPreflight
            or not callable(getattr(source, "consume_verified_dialog_event", None))
            or type(signed_envelope) is not str
            or not 0 < len(signed_envelope.encode("utf-8")) <= 8192
            or type(now) is not datetime
            or now.tzinfo is None
            or now.utcoffset() is None
            or type(preflight.confirmation_id) is not str
            or _ID.fullmatch(preflight.confirmation_id) is None
            or type(preflight.action) is not str
            or preflight.action not in _ACTIONS
            or type(preflight.expected_generation) is not int
            or preflight.expected_generation < 0
            or type(preflight.authorized_case_sha256) is not str
            or _HASH.fullmatch(preflight.authorized_case_sha256) is None
            or type(preflight.authorized_audit_digest) is not str
            or _HASH.fullmatch(preflight.authorized_audit_digest) is None
            or type(preflight.confirmation_expires_at) is not int
        ):
            raise ValueError("Invalid verified preflight or host source")
        current = int(now.astimezone(timezone.utc).timestamp())
        if current <= 0 or current >= preflight.confirmation_expires_at:
            raise ValueError("Signed intent is no longer current")

        # Claims in a signature-verified preflight remain insufficient: the
        # independent host must also establish current tenant policy coverage.
        qualify_producer_policy_assurance(
            provider=policy_assurance,
            tenant_id=preflight.tenant_id,
            subject=preflight.actor_id,
            session_id=preflight.session_id,
            context_id=context_id,
            client_ids=client_ids,
            now=now,
        )
        event = source.consume_verified_dialog_event(
            confirmation_id=preflight.confirmation_id,
            tenant_id=preflight.tenant_id,
        )
        if (
            type(event) is not VerifiedOperatorDialogEvent
            or type(event.event_id) is not str
            or _ID.fullmatch(event.event_id) is None
            or event.event_id == preflight.confirmation_id
            or type(event.challenge_id) is not str
            or _ID.fullmatch(event.challenge_id) is None
            or event.challenge_id in (event.event_id, event.confirmation_id)
            or event.confirmation_id != preflight.confirmation_id
            or event.tenant_id != preflight.tenant_id
            or event.actor_id != preflight.actor_id
            or event.token_issuer != preflight.token_issuer
            or event.session_id != preflight.session_id
            or event.output_id != preflight.output_id
            or event.action != preflight.action
            or type(event.expected_generation) is not int
            or event.expected_generation != preflight.expected_generation
            or event.authorized_case_sha256 != preflight.authorized_case_sha256
            or event.authorized_audit_digest != preflight.authorized_audit_digest
            or event.interaction_method != "workforce_authenticated_custom_dialog"
            or type(event.confirmed_at_seconds) is not int
            or type(event.verified_at_seconds) is not int
            or not 0 < event.confirmed_at_seconds <= event.verified_at_seconds <= current
            or current - event.confirmed_at_seconds > _MAX_INTERACTION_AGE_SECONDS
            or event.verified_at_seconds - event.confirmed_at_seconds > 60
            or event.confirmed_at_seconds >= preflight.confirmation_expires_at
        ):
            raise ValueError("Untrusted or mismatched operator dialog event")

        # The digest is calculated exclusively from the already verified
        # host-held signed envelope, never a browser-provided hash.
        return HostConfirmationRecord(
            confirmation_id=preflight.confirmation_id,
            tenant_id=preflight.tenant_id,
            actor_id=preflight.actor_id,
            token_issuer=preflight.token_issuer,
            session_id=preflight.session_id,
            output_id=preflight.output_id,
            action=preflight.action,
            expected_generation=preflight.expected_generation,
            authorized_case_sha256=preflight.authorized_case_sha256,
            authorized_audit_digest=preflight.authorized_audit_digest,
            signed_envelope_sha256=hashlib.sha256(
                signed_envelope.encode("utf-8")
            ).hexdigest(),
            event_id=event.event_id,
            event_channel="workforce_authenticated_custom_dialog",
            state="confirmed",
            confirmed_at_seconds=event.confirmed_at_seconds,
            recorded_at_seconds=current,
        )
    except Exception:
        # No user identity, approval signature, CA result or session detail
        # may escape into a public response or model/operator log.
        raise PermissionError("Producer authenticated confirmation denied") from None
