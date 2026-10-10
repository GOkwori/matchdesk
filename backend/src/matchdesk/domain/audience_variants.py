"""Audience-variant qualification for MatchDesk Phase 3D.

Audience adaptation may change wording, language and persona, but it must not change
the underlying match scope, replay/version identity, evidence set, claim set or output
kind. This module validates that invariant and requires every adapted claim to pass the
existing deterministic verification boundary before a producer can review the variant.
"""

from __future__ import annotations

from dataclasses import dataclass

from matchdesk.domain.broadcast_outputs import BroadcastEnvelope
from matchdesk.domain.models import VerificationResult


@dataclass(frozen=True)
class AudienceVariantQualification:
    """Immutable record that one audience variant passed deterministic rechecking."""

    source_output_id: str
    variant_output_id: str
    language: str
    persona: str
    claim_ids: tuple[str, ...]
    verification_statuses: tuple[str, ...]


def qualify_audience_variant(
    source: BroadcastEnvelope,
    variant: BroadcastEnvelope,
    verification_results: tuple[VerificationResult, ...],
) -> AudienceVariantQualification:
    """Validate one adapted variant without granting producer or publish authority."""
    if source.session_id != variant.session_id or source.match_id != variant.match_id:
        raise ValueError("Audience variant must remain in the same session and match")
    if source.windows != variant.windows:
        raise ValueError("Audience variant must preserve the source match windows")
    if source.evidence_ids != variant.evidence_ids:
        raise ValueError("Audience variant must preserve the exact evidence set")
    if source.claim_ids != variant.claim_ids:
        raise ValueError("Audience variant must preserve the exact claim set")
    if source.payload.kind != variant.payload.kind:
        raise ValueError("Audience variant must preserve the broadcast output kind")

    source_binding = source.binding
    variant_binding = variant.binding
    if (
        source_binding.item_id != variant_binding.item_id
        or source_binding.item_version != variant_binding.item_version
        or source_binding.replay_id != variant_binding.replay_id
        or source_binding.evidence_digest != variant_binding.evidence_digest
    ):
        raise ValueError("Audience variant must preserve item, version, replay and evidence identity")

    by_claim = {result.claim_id: result for result in verification_results}
    if set(by_claim) != set(variant.claim_ids) or len(by_claim) != len(verification_results):
        raise ValueError("Audience variant verification must cover every claim exactly once")

    accepted = {"verified", "supported_inference"}
    ordered_statuses: list[str] = []
    for claim_id in variant.claim_ids:
        result = by_claim[claim_id]
        if result.evidence_digest != variant_binding.evidence_digest:
            raise ValueError("Audience verification must bind the variant evidence digest")
        if result.status not in accepted:
            raise ValueError("Audience variant contains a claim that did not pass verification")
        ordered_statuses.append(result.status)

    return AudienceVariantQualification(
        source_output_id=source.output_id,
        variant_output_id=variant.output_id,
        language=variant_binding.language,
        persona=variant_binding.persona,
        claim_ids=variant.claim_ids,
        verification_statuses=tuple(ordered_statuses),
    )
