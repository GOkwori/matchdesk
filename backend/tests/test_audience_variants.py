"""Phase 3D tests for audience language/persona variant qualification."""

import pytest
from matchdesk.domain.audience_variants import (
    build_audience_variant,
    qualify_audience_variant,
    record_audience_language_review,
)
from matchdesk.domain.broadcast_outputs import (
    BroadcastEnvelope,
    CommentaryPayload,
)
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import (
    ApprovalBinding,
    VerificationResult,
)


def _envelope(
    output_id: str,
    *,
    language: str,
    persona: str,
    first_text: str,
    second_text: str,
) -> BroadcastEnvelope:
    """Create one claim-equivalent commentary variant with exact content identity."""
    payload = CommentaryPayload.model_validate(
        {
            "kind": "commentary",
            "lines": [
                {"claim_id": "claim-1", "text": first_text},
                {"claim_id": "claim-2", "text": second_text},
            ],
        }
    )
    return BroadcastEnvelope(
        output_id=output_id,
        session_id="session-1",
        match_id="match-1",
        binding=ApprovalBinding(
            item_id="story-1",
            item_version=3,
            replay_id="replay-1",
            content_digest=content_digest(payload),
            evidence_digest="a" * 64,
            language=language,
            persona=persona,
        ),
        windows=({"period": 1, "from_ms": 0, "to_ms": 2_700_000},),
        evidence_ids=("evidence-1",),
        claim_ids=("claim-1", "claim-2"),
        payload=payload,
    )


def _results(
    *,
    first_status: str = "verified",
    second_status: str = "supported_inference",
    evidence_digest: str = "a" * 64,
) -> tuple[VerificationResult, ...]:
    """Create complete verification coverage for both preserved audience claims."""
    return (
        VerificationResult(
            claim_id="claim-1",
            status=first_status,
            query_id="query-1",
            reason="Deterministic event or metric check passed",
            evidence_digest=evidence_digest,
        ),
        VerificationResult(
            claim_id="claim-2",
            status=second_status,
            query_id="query-2",
            reason="Evidence-bound tactical inference supported",
            evidence_digest=evidence_digest,
        ),
    )


@pytest.mark.parametrize("language", ["en", "es", "fr"])
@pytest.mark.parametrize("persona", ["analyst", "casual_fan", "broadcast_caption"])
def test_all_required_language_persona_variants_can_requalify(
    language: str,
    persona: str,
) -> None:
    """R7's three languages and three personas preserve evidence and claim identity."""
    source = _envelope(
        "output-source",
        language="en",
        persona="analyst",
        first_text="Seven shots were recorded in the first half.",
        second_text="The left side looked more dangerous after the restart.",
    )
    variant = _envelope(
        f"output-{language}-{persona}",
        language=language,
        persona=persona,
        first_text=f"{language}:{persona}: verified first claim",
        second_text=f"{language}:{persona}: supported second claim",
    )

    qualification = qualify_audience_variant(source, variant, _results())

    assert qualification.language == language
    assert qualification.persona == persona
    assert qualification.claim_ids == ("claim-1", "claim-2")
    assert qualification.verification_statuses == ("verified", "supported_inference")


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("session_id", "session-2", "same session and match"),
        ("match_id", "match-2", "same session and match"),
        (
            "windows",
            ({"period": 1, "from_ms": 1_000, "to_ms": 2_700_000},),
            "preserve the source match windows",
        ),
        ("evidence_ids", ("evidence-2",), "preserve the exact evidence set"),
        ("claim_ids", ("claim-1",), "preserve the exact claim set"),
    ],
)
def test_variant_scope_drift_is_rejected(field: str, value: object, match: str) -> None:
    """Audience wording cannot silently move to a different match/evidence/claim scope."""
    source = _envelope(
        "source",
        language="en",
        persona="analyst",
        first_text="Claim one.",
        second_text="Claim two.",
    )
    variant = _envelope(
        "variant",
        language="es",
        persona="casual_fan",
        first_text="Uno.",
        second_text="Dos.",
    ).model_copy(update={field: value})

    with pytest.raises(ValueError, match=match):
        qualify_audience_variant(source, variant, _results())


def test_item_version_replay_or_evidence_identity_drift_is_rejected() -> None:
    """A translated variant cannot escape the exact reviewed item generation."""
    source = _envelope(
        "source",
        language="en",
        persona="analyst",
        first_text="Claim one.",
        second_text="Claim two.",
    )
    variant = _envelope(
        "variant",
        language="fr",
        persona="broadcast_caption",
        first_text="Un.",
        second_text="Deux.",
    )
    changed_binding = variant.binding.model_copy(update={"item_version": 4})
    variant = variant.model_copy(update={"binding": changed_binding})

    with pytest.raises(ValueError, match="preserve item, version, replay and evidence"):
        qualify_audience_variant(source, variant, _results())


@pytest.mark.parametrize(
    "results,match",
    [
        (
            _results(first_status="needs_revision"),
            "did not pass verification",
        ),
        (
            _results(second_status="blocked"),
            "did not pass verification",
        ),
        (
            _results(evidence_digest="b" * 64),
            "bind the variant evidence digest",
        ),
    ],
)
def test_unqualified_or_wrong_evidence_claims_are_rejected(
    results: tuple[VerificationResult, ...],
    match: str,
) -> None:
    """Audience variants must pass the same deterministic evidence boundary again."""
    source = _envelope(
        "source",
        language="en",
        persona="analyst",
        first_text="Claim one.",
        second_text="Claim two.",
    )
    variant = _envelope(
        "variant",
        language="es",
        persona="casual_fan",
        first_text="Uno.",
        second_text="Dos.",
    )

    with pytest.raises(ValueError, match=match):
        qualify_audience_variant(source, variant, results)


def test_missing_or_duplicate_claim_verification_is_rejected() -> None:
    """Every preserved claim must have exactly one verification result."""
    source = _envelope(
        "source",
        language="en",
        persona="analyst",
        first_text="Claim one.",
        second_text="Claim two.",
    )
    variant = _envelope(
        "variant",
        language="fr",
        persona="broadcast_caption",
        first_text="Un.",
        second_text="Deux.",
    )
    one = (_results()[0],)
    duplicate = (_results()[0], _results()[0])

    with pytest.raises(ValueError, match="every claim exactly once"):
        qualify_audience_variant(source, variant, one)
    with pytest.raises(ValueError, match="every claim exactly once"):
        qualify_audience_variant(source, variant, duplicate)


def test_build_variant_preserves_scope_without_inheriting_approval() -> None:
    """Locale adaptation creates a new exact digest, not a publish authorization."""
    source = _envelope(
        "source",
        language="en",
        persona="analyst",
        first_text="Two attempts were made.",
        second_text="The pressure increased.",
    )
    proposed = CommentaryPayload.model_validate(
        {
            "lines": [
                {"claim_id": "claim-1", "text": "Se realizaron dos intentos."},
                {"claim_id": "claim-2", "text": "Aumento la presion."},
            ]
        }
    )
    variant = build_audience_variant(
        source,
        output_id="es-variant",
        payload=proposed,
        language="es",
        persona="casual_fan",
    )
    assert variant.claim_ids == source.claim_ids
    assert variant.evidence_ids == source.evidence_ids
    assert variant.binding.content_digest == content_digest(proposed)
    assert variant.binding.content_digest != source.binding.content_digest
    assert not hasattr(variant, "publication_authorized")


def test_language_review_requires_verification_and_exact_content() -> None:
    """Review must be tied to evidence-checked current localized content."""
    source = _envelope(
        "source",
        language="en",
        persona="analyst",
        first_text="Claim one.",
        second_text="Claim two.",
    )
    variant = _envelope(
        "variant",
        language="fr",
        persona="broadcast_caption",
        first_text="Un.",
        second_text="Deux.",
    )
    qualification = qualify_audience_variant(source, variant, _results())
    review = record_audience_language_review(
        variant,
        qualification,
        reviewer_actor_id="editor-1",
        meaning_preserved=True,
        language_quality_accepted=True,
    )
    assert review.variant_content_digest == variant.binding.content_digest
    assert review.reviewer_actor_id == "editor-1"

    changed = variant.model_copy(
        update={"binding": variant.binding.model_copy(update={"content_digest": "b" * 64})}
    )
    with pytest.raises(ValueError, match="exact qualified variant"):
        record_audience_language_review(
            changed,
            qualification,
            reviewer_actor_id="editor-1",
            meaning_preserved=True,
            language_quality_accepted=True,
        )


@pytest.mark.parametrize("meaning,quality", [(False, True), (True, False), (False, False)])
def test_language_review_rejects_unaccepted_semantics(meaning: bool, quality: bool) -> None:
    """Language quality and meaning are separate fail-closed editorial requirements."""
    source = _envelope(
        "source",
        language="en",
        persona="analyst",
        first_text="Claim one.",
        second_text="Claim two.",
    )
    variant = _envelope(
        "variant",
        language="es",
        persona="casual_fan",
        first_text="Uno.",
        second_text="Dos.",
    )
    qualification = qualify_audience_variant(source, variant, _results())
    with pytest.raises(ValueError, match="meaning and quality acceptance"):
        record_audience_language_review(
            variant,
            qualification,
            reviewer_actor_id="editor-1",
            meaning_preserved=meaning,
            language_quality_accepted=quality,
        )

def test_qualification_rejects_stale_variant_content_digest() -> None:
    """Even an immutable model can be copied without Pydantic revalidation."""
    source = _envelope(
        "source",
        language="en",
        persona="analyst",
        first_text="Two shots.",
        second_text="Pressure increased.",
    )
    variant = _envelope(
        "variant",
        language="es",
        persona="casual_fan",
        first_text="Dos tiros.",
        second_text="Aumento la presion.",
    )
    altered = variant.model_copy(
        update={"binding": variant.binding.model_copy(update={"content_digest": "c" * 64})}
    )
    with pytest.raises(ValueError, match="intact source and variant digests"):
        qualify_audience_variant(source, altered, _results())


def test_language_review_rejects_modified_payload_without_digest_update() -> None:
    """Language acceptance must not be reused after content changes."""
    source = _envelope(
        "source",
        language="en",
        persona="analyst",
        first_text="Two shots.",
        second_text="Pressure increased.",
    )
    variant = _envelope(
        "variant",
        language="fr",
        persona="broadcast_caption",
        first_text="Deux tirs.",
        second_text="La pression augmente.",
    )
    qualified = qualify_audience_variant(source, variant, _results())
    payload = CommentaryPayload.model_validate(
        {
            "lines": [
                {"claim_id": "claim-1", "text": "Trois tirs."},
                {"claim_id": "claim-2", "text": "La pression augmente."},
            ]
        }
    )
    altered = variant.model_copy(update={"payload": payload})
    with pytest.raises(ValueError, match="intact reviewed content"):
        record_audience_language_review(
            altered,
            qualified,
            reviewer_actor_id="editor-1",
            meaning_preserved=True,
            language_quality_accepted=True,
        )
