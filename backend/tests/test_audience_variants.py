"""Phase 3D tests for audience language/persona variant qualification."""

import pytest
from matchdesk.domain.audience_variants import qualify_audience_variant
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
