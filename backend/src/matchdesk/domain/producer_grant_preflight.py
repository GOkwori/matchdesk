"""Offline, default-unused preflight for a human-confirmed producer grant intent.

This module cannot issue an action grant, consume a confirmation, write SQL,
mount an API, or establish a human interaction by itself. A future trusted
issuer must independently provision the signing key and JSONB hash resolver,
then atomically consume the signed confirmation and issue a one-use grant in
the same PostgreSQL transaction. No caller can use this result as write access.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import TypeAdapter

from matchdesk.domain.postgres_producer_store import _audit_digest, _case_json
from matchdesk.domain.producer_commands import (
    ProducerCase,
    _authorize,
    _recompute_claims,
    _validate_case,
)
from matchdesk.domain.producer_identity import (
    EntitlementResolver,
    ProducerIdentityPolicy,
    TrustedKeyResolver,
    verify_producer_access_token,
)

GrantAction = Literal["create", "edit", "reverify", "approve", "reject"]
_APPROVAL_ISSUER = "matchdesk-trusted-producer-confirmation-v1"
_APPROVAL_AUDIENCE = "matchdesk-producer-grant-issuer"
_APPROVAL_METHOD = "custom-dialog-execution"
_DENIED = "Producer grant preflight denied"
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")
_CONFIRMATION_ID = re.compile(r"[a-f0-9]{32}\Z")
_SIGNATURE = re.compile(r"[A-Za-z0-9_-]{86}\Z")
_CASE = TypeAdapter(ProducerCase)
_ACTION_AUDIT = {
    "create": "review_started",
    "edit": "revision_opened",
    "reverify": "reverified",
    "approve": "approved",
    "reject": "rejected",
}
_CLAIMS = frozenset(
    {
        "version",
        "issuer",
        "audience",
        "confirmation_id",
        "confirmation_method",
        "actor_id",
        "token_issuer",
        "tenant_id",
        "session_id",
        "output_id",
        "action",
        "expected_generation",
        "authorized_case_sha256",
        "authorized_audit_digest",
        "issued_at",
        "not_before",
        "expires_at",
    }
)


class GrantPreflightDenied(PermissionError):
    """Generic non-disclosing preflight denial; never an execution receipt."""


class CaseDigestResolver(Protocol):
    """Trusted host-owned PostgreSQL JSONB SHA-256 resolver.

    The implementation must compute the same normalized JSONB hash that
    migration 006 compares: encode(sha256(convert_to(%s::jsonb::text,
    'UTF8')), 'hex'). A Python raw JSON hash is NOT interchangeable.
    """

    def digest_case_jsonb(self, case_json: str) -> str:
        """Return exactly 64 lowercase hex characters for a validated case."""


@dataclass(frozen=True, slots=True)
class ProducerGrantPreflight:
    """Inert verified intent; NOT a capability, grant, confirmation receipt or MFA proof.

    No credentials, signing material, bearer token or random executable grant
    identifier are returned. The trusted issuer must recheck current entitlements,
    human confirmation, and durable nonce consumption at actual execution time.
    """

    confirmation_id: str
    actor_id: str
    token_issuer: str
    tenant_id: str
    session_id: str
    output_id: str
    action: GrantAction
    expected_generation: int
    authorized_case_sha256: str
    authorized_audit_digest: str
    confirmation_expires_at: int


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Refuse ambiguous JSON keys instead of accepting the last signed value."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate signed confirmation field")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> None:
    """Reject JSON NaN and Infinity, which have no canonical signing meaning."""
    raise ValueError("Invalid confirmation constant")


def _signed_bytes(claims: dict[str, object]) -> bytes:
    """Create deterministic bytes for a pinned Ed25519 verification key."""
    return json.dumps(claims, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def qualify_producer_grant_preflight(
    *,
    access_token: str,
    policy: ProducerIdentityPolicy,
    keys: TrustedKeyResolver,
    entitlements: EntitlementResolver,
    case: ProducerCase,
    action: GrantAction,
    expected_generation: int,
    signed_confirmation: str,
    confirmation_public_key: Ed25519PublicKey,
    case_hash: CaseDigestResolver,
    now: datetime,
) -> ProducerGrantPreflight:
    """Check signed step-up identity, exact case and signed human-confirmation scope.

    This is strictly a stateless prerequisite, not issuance. Do not accept these
    dependencies from request JSON, headers, a model, or an agent output.
    Successful output grants NO database mutation or publication authority.
    """
    try:
        if (
            type(policy) is not ProducerIdentityPolicy
            or policy.required_auth_context is None
            or policy.max_token_age_seconds > 300
            or not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
            or not isinstance(confirmation_public_key, Ed25519PublicKey)
            or not callable(getattr(case_hash, "digest_case_jsonb", None))
            or action not in _ACTION_AUDIT
            or type(expected_generation) is not int
            or expected_generation < 0
            or (expected_generation == 0) != (action == "create")
        ):
            raise ValueError("Preflight requires an explicitly configured trusted host")
        policy.__post_init__()
        actor = verify_producer_access_token(
            access_token,
            policy=policy,
            keys=keys,
            entitlements=entitlements,
            now=now,
        )
        # Rebuild dataclass nested objects through strict Pydantic conversion:
        # frozen dataclasses alone cannot prevent forged nested attributes.
        case = _CASE.validate_json(_CASE.dump_json(case))
        _authorize(actor, case.tenant_id, case.output.session_id)
        _validate_case(case)
        if (
            case.generation != expected_generation + 1
            or case.review.audit[-1].actor_id != actor.subject
            or case.review.audit[-1].action != _ACTION_AUDIT[action]
            or len(actor.subject) > 256
            or len(actor.issuer) > 512
        ):
            raise ValueError("Producer grant scope is inconsistent")
        if action in ("approve", "reverify"):
            _recompute_claims(case)

        case_digest = case_hash.digest_case_jsonb(_case_json(case))
        audit_digest = _audit_digest(case.review.audit)
        if type(case_digest) is not str or _HEX64.fullmatch(case_digest) is None:
            raise ValueError("Invalid trusted case digest")
        if type(signed_confirmation) is not str:
            raise ValueError("Expected a signed human confirmation")
        if len(signed_confirmation.encode("utf-8")) > 8192:
            raise ValueError("Oversized human confirmation")

        envelope = json.loads(
            signed_confirmation,
            object_pairs_hook=_unique_pairs,
            parse_constant=_invalid_constant,
        )
        if type(envelope) is not dict or set(envelope) != {"claims", "signature"}:
            raise ValueError("Invalid confirmation envelope")
        claims = envelope["claims"]
        encoded = envelope["signature"]
        if type(claims) is not dict or set(claims) != _CLAIMS:
            raise ValueError("Unexpected confirmation claims")
        if type(encoded) is not str or _SIGNATURE.fullmatch(encoded) is None:
            raise ValueError("Invalid confirmation signature")
        if type(claims["version"]) is not int or claims["version"] != 1:
            raise ValueError("Unexpected confirmation version")

        exact = {
            "issuer": _APPROVAL_ISSUER,
            "audience": _APPROVAL_AUDIENCE,
            "confirmation_method": _APPROVAL_METHOD,
            "actor_id": actor.subject,
            "token_issuer": actor.issuer,
            "tenant_id": case.tenant_id,
            "session_id": case.output.session_id,
            "output_id": case.output.output_id,
            "action": action,
            "authorized_case_sha256": case_digest,
            "authorized_audit_digest": audit_digest,
        }
        if any(
            type(claims[key]) is not str or claims[key] != value for key, value in exact.items()
        ):
            raise ValueError("Confirmation is not bound to exact producer facts")
        if (
            type(claims["expected_generation"]) is not int
            or claims["expected_generation"] != expected_generation
            or type(claims["confirmation_id"]) is not str
            or _CONFIRMATION_ID.fullmatch(claims["confirmation_id"]) is None
        ):
            raise ValueError("Invalid or stale confirmation scope")
        issued = claims["issued_at"]
        not_before = claims["not_before"]
        expires = claims["expires_at"]
        timestamp = int(now.astimezone(timezone.utc).timestamp())
        if (
            any(type(value) is not int for value in (issued, not_before, expires))
            or not (0 < issued <= not_before < expires)
            or expires - issued > 120
            or issued > timestamp
            or not_before > timestamp
            or timestamp >= expires
        ):
            raise ValueError("Confirmation expired or not currently effective")
        signature = base64.b64decode(encoded + "==", altchars=b"-_", validate=True)
        if len(signature) != 64:
            raise ValueError("Invalid Ed25519 confirmation signature")
        confirmation_public_key.verify(signature, _signed_bytes(claims))
        return ProducerGrantPreflight(
            confirmation_id=claims["confirmation_id"],
            actor_id=actor.subject,
            token_issuer=actor.issuer,
            tenant_id=case.tenant_id,
            session_id=case.output.session_id,
            output_id=case.output.output_id,
            action=action,
            expected_generation=expected_generation,
            authorized_case_sha256=case_digest,
            authorized_audit_digest=audit_digest,
            confirmation_expires_at=expires,
        )
    except Exception:
        # No confirmation, identity, SQL details or signing diagnostics escape.
        # Even a failing/unavailable trusted dependency cannot yield an intent.
        raise GrantPreflightDenied(_DENIED) from None
