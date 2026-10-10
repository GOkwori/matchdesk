"""Audience-variant qualification for MatchDesk Phase 3D.

Audience adaptation may change wording, language and persona, but it must not change
the underlying match scope, replay/version identity, evidence set, claim set or output
kind. This module validates that invariant and requires every adapted claim to pass the
existing deterministic verification boundary before a producer can review the variant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from matchdesk.domain.broadcast_outputs import BroadcastEnvelope, OutputPayload, OverlayPayload
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import ApprovalBinding, VerificationResult


@dataclass(frozen=True)
class AudienceVariantQualification:
    """Immutable record that one audience variant passed deterministic rechecking."""

    source_output_id: str
    variant_output_id: str
    language: str
    persona: str
    claim_ids: tuple[str, ...]
    verification_statuses: tuple[str, ...]
    variant_content_digest: str
    evidence_digest: str


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
    if isinstance(source.payload, OverlayPayload):
        # A translated label may change, but its source metric and numerical claim may not.
        assert isinstance(variant.payload, OverlayPayload)
        source_metrics = {metric.claim_id: metric.assertion for metric in source.payload.metrics}
        variant_metrics = {metric.claim_id: metric.assertion for metric in variant.payload.metrics}
        if (
            len(source_metrics) != len(source.payload.metrics)
            or len(variant_metrics) != len(variant.payload.metrics)
            or source_metrics != variant_metrics
        ):
            raise ValueError("Audience overlay must preserve each exact numerical assertion")

    source_binding = source.binding
    variant_binding = variant.binding
    if (
        source_binding.item_id != variant_binding.item_id
        or source_binding.item_version != variant_binding.item_version
        or source_binding.replay_id != variant_binding.replay_id
        or source_binding.evidence_digest != variant_binding.evidence_digest
    ):
        raise ValueError(
            "Audience variant must preserve item, version, replay and evidence identity"
        )

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
        variant_content_digest=variant_binding.content_digest,
        evidence_digest=variant_binding.evidence_digest,
    )


@dataclass(frozen=True)
class AudienceLanguageReview:
    """Host-supplied editorial acceptance bound to one exact localized draft.

    This is an audit record, not actor authentication or permission to publish.
    A trusted host must establish the reviewer before calling this function.
    """

    source_output_id: str
    variant_output_id: str
    reviewer_actor_id: str
    variant_content_digest: str
    evidence_digest: str
    language: str
    persona: str


def build_audience_variant(
    source: BroadcastEnvelope,
    *,
    output_id: str,
    payload: OutputPayload,
    language: Literal["en", "es", "fr"],
    persona: Literal["analyst", "casual_fan", "broadcast_caption"],
) -> BroadcastEnvelope:
    """Bind model- or editor-proposed copy to a fresh locale/persona content identity.

    The new draft inherits evidence, claim and replay scope, never the approval itself.
    Neither variant construction nor Pydantic validation proves semantic equivalence.
    """
    if payload.kind != source.payload.kind:
        raise ValueError("Audience draft must retain the source output kind")

    current = source.binding
    binding = ApprovalBinding(
        item_id=current.item_id,
        item_version=current.item_version,
        replay_id=current.replay_id,
        content_digest=content_digest(payload),
        evidence_digest=current.evidence_digest,
        language=language,
        persona=persona,
    )
    return BroadcastEnvelope(
        output_id=output_id,
        session_id=source.session_id,
        match_id=source.match_id,
        binding=binding,
        windows=source.windows,
        evidence_ids=source.evidence_ids,
        claim_ids=source.claim_ids,
        payload=payload,
    )


def record_audience_language_review(
    variant: BroadcastEnvelope,
    qualification: AudienceVariantQualification,
    *,
    reviewer_actor_id: str,
    meaning_preserved: bool,
    language_quality_accepted: bool,
) -> AudienceLanguageReview:
    """Require explicit editorial language/meaning acceptance for exact reviewed copy.

    Deterministic claim checks cannot evaluate whether translated prose changes meaning.
    The trusted host must independently authenticate the reviewer and persist this
    version-bound decision; no publishing authority is returned from this function.
    """
    if (
        qualification.variant_output_id != variant.output_id
        or qualification.variant_content_digest != variant.binding.content_digest
        or qualification.evidence_digest != variant.binding.evidence_digest
        or qualification.language != variant.binding.language
        or qualification.persona != variant.binding.persona
        or qualification.claim_ids != variant.claim_ids
    ):
        raise ValueError("Audience language review must bind the exact qualified variant")
    actor_id = reviewer_actor_id.strip()
    if not actor_id:
        raise ValueError("Audience language reviewer actor_id cannot be blank")
    if type(meaning_preserved) is not bool or type(language_quality_accepted) is not bool:
        raise ValueError("Language review decisions must be explicit booleans")
    if not meaning_preserved or not language_quality_accepted:
        raise ValueError("Audience language review requires meaning and quality acceptance")
    return AudienceLanguageReview(
        source_output_id=qualification.source_output_id,
        variant_output_id=variant.output_id,
        reviewer_actor_id=actor_id,
        variant_content_digest=variant.binding.content_digest,
        evidence_digest=variant.binding.evidence_digest,
        language=variant.binding.language,
        persona=variant.binding.persona,
    )
