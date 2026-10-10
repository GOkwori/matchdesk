"""Offline audience quality review matrix regressions; no reviewer sign-off implied."""

from dataclasses import replace

import pytest
from matchdesk.domain.audience_quality import (
    record_audience_quality_assessment,
    summarize_audience_quality,
)
from matchdesk.domain.audience_variants import (
    build_audience_variant,
    qualify_audience_variant,
)
from matchdesk.domain.broadcast_outputs import BroadcastEnvelope, CommentaryPayload
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import ApprovalBinding, VerificationResult


def _source() -> BroadcastEnvelope:
    """Create one synthetic story for the nine offline review combinations."""
    payload = CommentaryPayload.model_validate(
        {"lines": [{"claim_id": "claim-1", "text": "The team made two attempts."}]}
    )
    return BroadcastEnvelope(
        output_id="source-1",
        session_id="session-1",
        match_id="match-1",
        binding=ApprovalBinding(
            item_id="story-1",
            item_version=1,
            replay_id="replay-1",
            content_digest=content_digest(payload),
            evidence_digest="a" * 64,
            language="en",
            persona="analyst",
        ),
        windows=({"period": 1, "from_ms": 0, "to_ms": 2_700_000},),
        evidence_ids=("evidence-1",),
        claim_ids=("claim-1",),
        payload=payload,
    )


def _assessment(
    language: str = "en",
    persona: str = "analyst",
    *,
    meaning: bool = True,
):
    """Return a mock reviewer record; this does not establish real language quality."""
    source = _source()
    payload = CommentaryPayload.model_validate(
        {"lines": [{"claim_id": "claim-1", "text": "Offline sample text."}]}
    )
    variant = build_audience_variant(
        source,
        output_id=f"variant-{language}-{persona}",
        payload=payload,
        language=language,
        persona=persona,
    )
    verification = (
        VerificationResult(
            claim_id="claim-1",
            status="verified",
            query_id="query-1",
            reason="Offline verification fixture",
            evidence_digest=source.binding.evidence_digest,
        ),
    )
    qualification = qualify_audience_variant(source, variant, verification)
    return record_audience_quality_assessment(
        source,
        variant,
        qualification,
        reviewer_actor_id="offline-fixture",
        meaning_preserved=meaning,
        football_terms_accurate=True,
        language_quality_accepted=True,
        persona_fit=True,
        no_new_factual_assertions=True,
        notes="Synthetic reviewer flags for contract testing, not human verification",
    )


def test_empty_quality_matrix_remains_incomplete() -> None:
    """No fake/absent reviews can be treated as successful qualification."""
    result = summarize_audience_quality(())
    assert result.status == "incomplete"
    assert len(result.missing) == 9


def test_all_nine_reported_pairs_are_structurally_covered() -> None:
    """Three languages by three personas are required for reported matrix coverage."""
    assessments = tuple(
        _assessment(lang, persona)
        for lang in ("en", "es", "fr")
        for persona in ("analyst", "casual_fan", "broadcast_caption")
    )
    report = summarize_audience_quality(assessments)
    assert report.status == "reported_pass"
    assert len(report.covered) == 9
    assert report.missing == ()
    assert report.needs_revision == ()


def test_partial_matrix_never_reports_a_pass() -> None:
    """A missing audience persona or language prevents full reported coverage."""
    report = summarize_audience_quality((_assessment("fr", "analyst"),))
    assert report.status == "incomplete"
    assert len(report.missing) == 8


def test_reported_meaning_failure_requires_revision() -> None:
    """A structural claim-ID match alone cannot overrule a negative human judgment."""
    report = summarize_audience_quality((_assessment("es", "casual_fan", meaning=False),))
    assert report.status == "needs_revision"
    assert report.needs_revision == (("es", "casual_fan"),)


def test_quality_matrix_rejects_duplicate_variant_pair() -> None:
    """A duplicated sample cannot inflate nine-way coverage."""
    assessment = _assessment()
    with pytest.raises(ValueError, match="cannot reuse"):
        summarize_audience_quality((assessment, assessment))


def test_quality_matrix_rejects_mixed_evidence_and_unsupported_language() -> None:
    """One matrix cannot mix evidence generations or silently add a fourth locale."""
    base = _assessment()
    other = _assessment("fr", "broadcast_caption")
    with pytest.raises(ValueError, match="one source and evidence generation"):
        summarize_audience_quality((base, replace(other, evidence_digest="b" * 64)))
    with pytest.raises(ValueError, match="unsupported language/persona"):
        summarize_audience_quality((replace(base, language="de"),))


def test_quality_review_rejects_stale_qualification() -> None:
    """A changed output digest cannot reuse a previous source-bound assessment."""
    source = _source()
    payload = CommentaryPayload.model_validate(
        {"lines": [{"claim_id": "claim-1", "text": "Deux tirs."}]}
    )
    variant = build_audience_variant(
        source,
        output_id="variant-fr",
        payload=payload,
        language="fr",
        persona="casual_fan",
    )
    verification = (
        VerificationResult(
            claim_id="claim-1",
            status="verified",
            query_id="query-1",
            reason="Synthetic fixture",
            evidence_digest="a" * 64,
        ),
    )
    qualified = qualify_audience_variant(source, variant, verification)
    altered = variant.model_copy(
        update={"binding": variant.binding.model_copy(update={"content_digest": "b" * 64})}
    )
    with pytest.raises(ValueError, match="intact variant content digest"):
        record_audience_quality_assessment(
            source,
            altered,
            qualified,
            reviewer_actor_id="offline-fixture",
            meaning_preserved=True,
            football_terms_accurate=True,
            language_quality_accepted=True,
            persona_fit=True,
            no_new_factual_assertions=True,
            notes="Content was modified",
        )


def test_quality_review_requires_explicit_judgments_and_notes() -> None:
    """A reviewer cannot skip judgment fields or submit numeric pseudo-booleans."""
    source = _source()
    payload = CommentaryPayload.model_validate(
        {"lines": [{"claim_id": "claim-1", "text": "Deux tirs."}]}
    )
    variant = build_audience_variant(
        source,
        output_id="variant-fr",
        payload=payload,
        language="fr",
        persona="analyst",
    )
    qualification = qualify_audience_variant(
        source,
        variant,
        (
            VerificationResult(
                claim_id="claim-1",
                status="verified",
                query_id="query-1",
                reason="Fixture",
                evidence_digest="a" * 64,
            ),
        ),
    )
    with pytest.raises(ValueError, match="explicit booleans"):
        record_audience_quality_assessment(
            source,
            variant,
            qualification,
            reviewer_actor_id="offline-fixture",
            meaning_preserved=1,
            football_terms_accurate=True,
            language_quality_accepted=True,
            persona_fit=True,
            no_new_factual_assertions=True,
            notes="Fixture",
        )
    with pytest.raises(ValueError, match="written reviewer notes"):
        record_audience_quality_assessment(
            source,
            variant,
            qualification,
            reviewer_actor_id="offline-fixture",
            meaning_preserved=True,
            football_terms_accurate=True,
            language_quality_accepted=True,
            persona_fit=True,
            no_new_factual_assertions=True,
            notes=" ",
        )
