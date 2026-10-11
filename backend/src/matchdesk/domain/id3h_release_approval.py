"""Verify one-time ID3H *disposable-CI* release approvals, not live releases.

This offline policy does not run SQL or establish the operator's identity.
A future, separately approved execution host MUST independently authenticate the
workload, discover target/evidence facts and own the public key and atomic store.
Neither an agent nor an HTTP caller may supply those trusted dependencies.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ISSUER = "matchdesk-trusted-release-authority"
AUDIENCE = "matchdesk-id3h-qualification"
ACTION = "id3h.reconcile-receipt-only"
ENVIRONMENT = "disposable-ci"
DENIAL = "ID3H qualification approval denied"
_MAX_TOKEN_BYTES = 8192
_MAX_GRANT_AGE_SECONDS = 600
_BOUND_FIELDS = frozenset(
    {
        "action",
        "environment",
        "operator_id",
        "tenant_fingerprint",
        "database_fingerprint",
        "source_commit",
        "migration_sha256",
        "historical_evidence_sha256",
        "backup_evidence_sha256",
        "catalog_evidence_sha256",
        "cost_decision_sha256",
        "change_id",
    }
)
_CLAIM_FIELDS = _BOUND_FIELDS | {
    "version",
    "issuer",
    "audience",
    "approval_id",
    "reviewer_id",
    "issued_at",
    "not_before",
    "expires_at",
}
_HEX40 = re.compile(r"[a-f0-9]{40}\Z")
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SIGNATURE = re.compile(r"[A-Za-z0-9_-]{86}\Z")


class ReleaseDenied(PermissionError):
    """Signal a generic deny without disclosing any approval or DB identifiers."""


@dataclass(frozen=True, slots=True)
class ObservedReleaseFacts:
    """Facts a future host must obtain independently at the execution boundary.

    These values are *not* trustworthy if constructed from an API request,
    browser claim, prompt, CI log, self-attested manifest or approval payload.
    """

    action: str
    environment: str
    operator_id: str
    tenant_fingerprint: str
    database_fingerprint: str
    source_commit: str
    migration_sha256: str
    historical_evidence_sha256: str
    backup_evidence_sha256: str
    catalog_evidence_sha256: str
    cost_decision_sha256: str
    change_id: str


class ApprovalReservationStore(Protocol):
    """Externally owned store offering durable, globally atomic single use.

    An implementation MUST persist a successful reservation before returning,
    reject duplicates, and never report success after a transient write error.
    """

    def reserve_once(self, approval_id: str, expires_at: int) -> bool:
        """Consume one verified approval ID atomically, or return False."""
        ...


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Refuse duplicate JSON properties rather than accepting a parser override."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate approval claim")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    """Disallow JSON NaN and Infinity which have no canonical signature meaning."""
    raise ValueError("Invalid JSON constant")


def _canonical(claims: dict[str, object]) -> bytes:
    """Encode the complete validated claims into one deterministic signature body."""
    return json.dumps(claims, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _observed_fields(observed: ObservedReleaseFacts) -> dict[str, str]:
    """Bind each grant claim to a separately observed execution-host fact."""
    return {
        "action": observed.action,
        "environment": observed.environment,
        "operator_id": observed.operator_id,
        "tenant_fingerprint": observed.tenant_fingerprint,
        "database_fingerprint": observed.database_fingerprint,
        "source_commit": observed.source_commit,
        "migration_sha256": observed.migration_sha256,
        "historical_evidence_sha256": observed.historical_evidence_sha256,
        "backup_evidence_sha256": observed.backup_evidence_sha256,
        "catalog_evidence_sha256": observed.catalog_evidence_sha256,
        "cost_decision_sha256": observed.cost_decision_sha256,
        "change_id": observed.change_id,
    }


def reserve_disposable_release_approval(
    envelope_text: str,
    *,
    observed: ObservedReleaseFacts,
    trusted_public_key: Ed25519PublicKey,
    reservation_store: ApprovalReservationStore,
    now: datetime,
) -> str:
    """Verify exact signed scope and consume a one-time CI grant; never run SQL.

    The fixed issuer/audience/action/environment cannot be relaxed through
    grant fields. The caller must be a *trusted* host that separately verifies
    actor identity, source, target, historical migration and backup evidence.
    A real release needs a different reviewed execution boundary and approval.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ReleaseDenied(DENIAL)
    expected = _observed_fields(observed)
    if (
        expected["action"] != ACTION
        or expected["environment"] != ENVIRONMENT
        or not _IDENTIFIER.fullmatch(expected["operator_id"])
        or not _IDENTIFIER.fullmatch(expected["change_id"])
        or not _HEX40.fullmatch(expected["source_commit"])
        or any(
            not _HEX64.fullmatch(expected[field])
            for field in (
                "tenant_fingerprint",
                "database_fingerprint",
                "migration_sha256",
                "historical_evidence_sha256",
                "backup_evidence_sha256",
                "catalog_evidence_sha256",
                "cost_decision_sha256",
            )
        )
    ):
        raise ReleaseDenied(DENIAL)
    if not isinstance(envelope_text, str) or len(envelope_text.encode("utf-8")) > _MAX_TOKEN_BYTES:
        raise ReleaseDenied(DENIAL)

    try:
        envelope: object = json.loads(
            envelope_text,
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
        if not isinstance(envelope, dict) or set(envelope) != {"claims", "signature"}:
            raise ValueError("Invalid approval envelope")
        claims = envelope["claims"]
        signature_text = envelope["signature"]
        if not isinstance(claims, dict) or set(claims) != _CLAIM_FIELDS:
            raise ValueError("Missing or additional claim")
        if not isinstance(signature_text, str) or not _SIGNATURE.fullmatch(signature_text):
            raise ValueError("Invalid signature encoding")
        if type(claims["version"]) is not int or claims["version"] != 1:
            raise ValueError("Unsupported approval version")
        if claims["issuer"] != ISSUER or claims["audience"] != AUDIENCE:
            raise ValueError("Untrusted grant authority")
        for field in _BOUND_FIELDS:
            if type(claims[field]) is not str or claims[field] != expected[field]:
                raise ValueError("Approved scope does not match observed scope")
        approval_id: object = claims["approval_id"]
        reviewer_id: object = claims["reviewer_id"]
        if (
            type(approval_id) is not str
            or not re.fullmatch(r"[a-f0-9]{32}", approval_id)
            or type(reviewer_id) is not str
            or not _IDENTIFIER.fullmatch(reviewer_id)
            or reviewer_id == observed.operator_id
        ):
            raise ValueError("Missing distinct human approval")
        issued, not_before, expires = (
            claims["issued_at"],
            claims["not_before"],
            claims["expires_at"],
        )
        if any(type(value) is not int for value in (issued, not_before, expires)):
            raise ValueError("Invalid grant time")
        current = int(now.astimezone(timezone.utc).timestamp())
        if not (
            0 < issued <= not_before < expires
            and 0 < expires - issued <= _MAX_GRANT_AGE_SECONDS
            and issued <= current
            and not_before <= current < expires
        ):
            raise ValueError("Approval is not currently valid")
        signature = base64.b64decode(signature_text + "==", altchars=b"-_", validate=True)
        if len(signature) != 64:
            raise ValueError("Invalid signature length")
        # Verification uses ONLY the key provisioned out-of-band by a trusted
        # host; no 'kid', header-supplied key URL or network lookup is accepted.
        trusted_public_key.verify(signature, _canonical(claims))
    except (ValueError, TypeError, KeyError, InvalidSignature, OverflowError):
        raise ReleaseDenied(DENIAL) from None

    try:
        # A check-then-write read would permit concurrent replay. The external
        # reservation must be atomic and durable BEFORE a future host acts.
        if not reservation_store.reserve_once(approval_id, expires):
            raise ReleaseDenied(DENIAL)
    except Exception:
        # Treat unavailable, non-atomic, failed and duplicate reservations as
        # denial. A future host must never proceed after ambiguous commits.
        raise ReleaseDenied(DENIAL) from None
    return approval_id
