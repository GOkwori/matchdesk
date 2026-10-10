"""Source-bound human quality assessment for Phase 3D audience variants.

This is an offline acceptance record. The host must authenticate reviewers and
persist evidence independently; a claimed PASS here is not a model evaluation,
proof of translation accuracy or authorization to publish.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from matchdesk.domain.audience_variants import AudienceVariantQualification
from matchdesk.domain.broadcast_outputs import BroadcastEnvelope
from matchdesk.domain.hashing import content_digest

_LANGUAGES = ("en", "es", "fr")
_PERSONAS = ("analyst", "casual_fan", "broadcast_caption")
_REQUIRED_PAIRS = frozenset((language, persona) for language in _LANGUAGES for persona in _PERSONAS)
MatrixStatus = Literal["incomplete", "needs_revision", "reported_pass"]


@dataclass(frozen=True)
class AudienceQualityAssessment:
    """One reviewer-reported result bound to the exact proposed audience content."""

    source_output_id: str
    source_content_digest: str
    variant_output_id: str
    variant_content_digest: str
    evidence_digest: str
    language: str
    persona: str
    reviewer_actor_id: str
    meaning_preserved: bool
    football_terms_accurate: bool
    language_quality_accepted: bool
    persona_fit: bool
    no_new_factual_assertions: bool
    notes: str

    @property
    def reported_pass(self) -> bool:
        """Require all five independently reported acceptance dimensions."""
        return (
            self.meaning_preserved
            and self.football_terms_accurate
            and self.language_quality_accepted
            and self.persona_fit
            and self.no_new_factual_assertions
        )


@dataclass(frozen=True)
class AudienceQualityMatrix:
    """Coverage of the required three-language, three-persona review matrix."""

    status: MatrixStatus
    covered: tuple[tuple[str, str], ...]
    missing: tuple[tuple[str, str], ...]
    needs_revision: tuple[tuple[str, str], ...]


def record_audience_quality_assessment(
    source: BroadcastEnvelope,
    variant: BroadcastEnvelope,
    qualification: AudienceVariantQualification,
    *,
    reviewer_actor_id: str,
    meaning_preserved: bool,
    football_terms_accurate: bool,
    language_quality_accepted: bool,
    persona_fit: bool,
    no_new_factual_assertions: bool,
    notes: str,
) -> AudienceQualityAssessment:
    """Record five explicit judgments against the current qualified variant.

    The judgments are supplied by an independently authenticated human reviewer,
    not inferred from matching claim IDs or a model's own self-evaluation. This
    function checks bindings but cannot establish the reviewer's real identity.
    """
    if source.binding.content_digest != content_digest(source.payload):
        raise ValueError("Quality review requires an intact source content digest")
    if variant.binding.content_digest != content_digest(variant.payload):
        raise ValueError("Quality review requires an intact variant content digest")
    if (
        qualification.source_output_id != source.output_id
        or qualification.variant_output_id != variant.output_id
        or qualification.variant_content_digest != variant.binding.content_digest
        or qualification.evidence_digest != variant.binding.evidence_digest
        or qualification.language != variant.binding.language
        or qualification.persona != variant.binding.persona
        or qualification.claim_ids != variant.claim_ids
    ):
        raise ValueError("Quality review must match the current audience qualification")

    judgments = (
        meaning_preserved,
        football_terms_accurate,
        language_quality_accepted,
        persona_fit,
        no_new_factual_assertions,
    )
    if any(type(value) is not bool for value in judgments):
        raise ValueError("Quality judgments must be explicit booleans")
    actor_id = reviewer_actor_id.strip()
    if not actor_id:
        raise ValueError("Quality reviewer actor_id cannot be blank")
    note_text = notes.strip()
    if not note_text:
        raise ValueError("Quality review requires written reviewer notes")

    return AudienceQualityAssessment(
        source_output_id=source.output_id,
        source_content_digest=source.binding.content_digest,
        variant_output_id=variant.output_id,
        variant_content_digest=variant.binding.content_digest,
        evidence_digest=variant.binding.evidence_digest,
        language=variant.binding.language,
        persona=variant.binding.persona,
        reviewer_actor_id=actor_id,
        meaning_preserved=meaning_preserved,
        football_terms_accurate=football_terms_accurate,
        language_quality_accepted=language_quality_accepted,
        persona_fit=persona_fit,
        no_new_factual_assertions=no_new_factual_assertions,
        notes=note_text,
    )


def summarize_audience_quality(
    assessments: tuple[AudienceQualityAssessment, ...],
) -> AudienceQualityMatrix:
    """Summarize reviewer-reported coverage; never turn reports into authority.

    A complete reported matrix means nine records exist, not that a live Foundry
    model has been evaluated or all translations are independently verified.
    """
    if not assessments:
        return AudienceQualityMatrix(
            status="incomplete",
            covered=(),
            missing=tuple(sorted(_REQUIRED_PAIRS)),
            needs_revision=(),
        )

    first = assessments[0]
    covered: set[tuple[str, str]] = set()
    outputs: set[str] = set()
    failures: set[tuple[str, str]] = set()
    for assessment in assessments:
        pair = (assessment.language, assessment.persona)
        if pair not in _REQUIRED_PAIRS:
            raise ValueError("Quality review contains unsupported language/persona")
        if pair in covered or assessment.variant_output_id in outputs:
            raise ValueError("Quality matrix cannot reuse a locale/persona or variant output")
        if (
            assessment.source_output_id != first.source_output_id
            or assessment.source_content_digest != first.source_content_digest
            or assessment.evidence_digest != first.evidence_digest
        ):
            raise ValueError("Quality matrix must compare one source and evidence generation")
        covered.add(pair)
        outputs.add(assessment.variant_output_id)
        if not assessment.reported_pass:
            failures.add(pair)

    missing = _REQUIRED_PAIRS - covered
    status: MatrixStatus = (
        "needs_revision" if failures else "incomplete" if missing else "reported_pass"
    )
    return AudienceQualityMatrix(
        status=status,
        covered=tuple(sorted(covered)),
        missing=tuple(sorted(missing)),
        needs_revision=tuple(sorted(failures)),
    )
