"""Verify independently stored, host-authenticated producer confirmation records.

A signed confirmation envelope proves its bytes were signed, NOT that a real
human completed an authenticated custom dialog. Before issuing a database
grant, the unmounted bridge must also correlate that envelope with a fresh,
durable, independently read-only host event. This module neither signs
confirmations nor establishes that a future adapter actually authenticates
humans; production activation requires separate operator qualification.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol

from matchdesk.domain.producer_grant_preflight import (
    GrantAction,
    ProducerGrantPreflight,
)

_HEX32 = re.compile(r"[a-f0-9]{32}\Z")
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")
_MAX_EVENT_AGE_SECONDS = 120


@dataclass(frozen=True, slots=True)
class HostConfirmationRecord:
    """Non-authoritative shape for an independently verified host event.

    A record is trustworthy ONLY when returned by a privileged, read-only
    adapter backed by an audited authenticated server-side confirmation event.
    A browser payload, model output, signed JWT or the signing service alone
    must never be used as an implementation of this provider.
    """

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
    signed_envelope_sha256: str
    event_id: str
    event_channel: Literal["workforce_authenticated_custom_dialog"]
    state: Literal["confirmed", "revoked", "cancelled"]
    confirmed_at_seconds: int
    recorded_at_seconds: int


class HostConfirmationRecordReader(Protocol):
    """Read-only, host-injected audited confirmation provenance provider.

    The future backing store MUST enforce authenticated human interaction,
    immutability, independent authorization, tenant isolation and revocation.
    No request or access token may select or construct a returned record.
    """

    def read_verified_confirmation(
        self, *, confirmation_id: str, tenant_id: str
    ) -> HostConfirmationRecord | None:
        """Return one independently verified server event, or None to deny."""


def qualify_host_confirmation_record(
    *,
    reader: HostConfirmationRecordReader,
    preflight: ProducerGrantPreflight,
    signed_confirmation: str,
    now: datetime,
) -> None:
    """Deny missing, stale, revoked or mismatched host confirmation provenance.

    The call occurs AFTER signature verification and BEFORE PostgreSQL grant
    staging. It is a necessary correlation check, not a replacement for actual
    host-owned signing, Entra MFA, one-time nonce consumption or database CAS.
    """
    try:
        if (
            type(preflight) is not ProducerGrantPreflight
            or type(signed_confirmation) is not str
            or not signed_confirmation
            or len(signed_confirmation.encode("utf-8")) > 8192
            or not callable(getattr(reader, "read_verified_confirmation", None))
            or type(now) is not datetime
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError("Missing authenticated host confirmation evidence")
        timestamp = int(now.astimezone(timezone.utc).timestamp())
        proof = reader.read_verified_confirmation(
            confirmation_id=preflight.confirmation_id,
            tenant_id=preflight.tenant_id,
        )
        if type(proof) is not HostConfirmationRecord:
            raise ValueError("No independently verified confirmation record")
        digest = hashlib.sha256(signed_confirmation.encode("utf-8")).hexdigest()
        if (
            proof.confirmation_id != preflight.confirmation_id
            or proof.tenant_id != preflight.tenant_id
            or proof.actor_id != preflight.actor_id
            or proof.token_issuer != preflight.token_issuer
            or proof.session_id != preflight.session_id
            or proof.output_id != preflight.output_id
            or proof.action != preflight.action
            or type(proof.expected_generation) is not int
            or proof.expected_generation != preflight.expected_generation
            or proof.authorized_case_sha256 != preflight.authorized_case_sha256
            or proof.authorized_audit_digest != preflight.authorized_audit_digest
            or type(proof.signed_envelope_sha256) is not str
            or _HEX64.fullmatch(proof.signed_envelope_sha256) is None
            or not hmac.compare_digest(proof.signed_envelope_sha256, digest)
            or type(proof.event_id) is not str
            or _HEX32.fullmatch(proof.event_id) is None
            or proof.event_id == preflight.confirmation_id
            or proof.event_channel != "workforce_authenticated_custom_dialog"
            or proof.state != "confirmed"
            or type(proof.confirmed_at_seconds) is not int
            or type(proof.recorded_at_seconds) is not int
            or not 0 < proof.confirmed_at_seconds <= proof.recorded_at_seconds
            or proof.recorded_at_seconds > timestamp
            or proof.confirmed_at_seconds > timestamp
            or timestamp - proof.confirmed_at_seconds > _MAX_EVENT_AGE_SECONDS
            or timestamp >= preflight.confirmation_expires_at
            or proof.confirmed_at_seconds >= preflight.confirmation_expires_at
        ):
            raise ValueError("Confirmation provenance does not match signed intent")
    except Exception:
        # No actor, token, signature, storage state or event details are exposed.
        raise PermissionError("Producer confirmation provenance denied") from None
