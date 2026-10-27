"""Deterministic, synthetic-only judge golden path; no live model or authority.

The facts and audience qualifications reuse existing domain boundaries rather
than generating success labels or presenting scripted specialists as live agents.
No identity, review decision, network connection, database or publisher runs here.
"""

from __future__ import annotations

from itertools import product

from matchdesk.domain.audience_variants import build_audience_variant, qualify_audience_variant
from matchdesk.domain.broadcast_outputs import ClaimLinkedText, CommentaryPayload
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.moments import detect_moments
from matchdesk.domain.producer_preview import build_producer_desk_preview
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.specialists import ScopedReadTools
from matchdesk.domain.verification import verify_claim

_LANGUAGES = ("en", "es", "fr")
_PERSONAS = ("analyst", "casual_fan", "broadcast_caption")

# Explicitly scripted, unreviewed illustrative wording. This is not evidence
# of translation quality, model use, human acceptance or publication approval.
_SCRIPTED_COPY: dict[tuple[str, str], str] = {
    ("en", "analyst"): "The home side registered one first-half goal.",
    ("en", "casual_fan"): "The home team scored once before half-time.",
    ("en", "broadcast_caption"): "Home: one first-half goal.",
    ("es", "analyst"): "El equipo local marcó un gol en la primera mitad.",
    ("es", "casual_fan"): "El equipo de casa anotó una vez antes del descanso.",
    ("es", "broadcast_caption"): "Local: un gol en la primera mitad.",
    ("fr", "analyst"): "L'équipe à domicile a marqué un but en première période.",
    ("fr", "casual_fan"): "L'équipe à domicile a marqué une fois avant la pause.",
    ("fr", "broadcast_caption"): "Domicile : un but en première période.",
}


def build_judge_golden_path() -> dict[str, object]:
    """Recompute a fixture-backed inspectable path, never an authenticated action.

    Specialist stages are explicitly *scripted proposals*, not Agent Framework
    executions. Audience variants are structurally qualified; no system claims
    that foreign-language wording received fluent review or is publication-ready.
    """
    preview = build_producer_desk_preview()
    scenario = generate_scenario("late_winner", 7)
    if preview.output.match_id != scenario.match_id:
        raise ValueError("Judge fixture and producer replay do not match")
    moments = detect_moments(scenario.events)
    metric_assertion = preview.claim.assertion
    if metric_assertion is None:
        raise ValueError("Judge fixture requires a registered measured claim")
    tools = ScopedReadTools(role="tactical_analyst", events=scenario.events)
    observed = tools.metric(
        metric_assertion.metric, metric_assertion.subject, metric_assertion.window
    )
    verdict = verify_claim(preview.claim, preview.evidence, preview.events)
    if (
        verdict.status != "verified"
        or verdict.observed != observed
        or verdict.evidence_digest != preview.output.binding.evidence_digest
        or preview.output.binding.evidence_digest != content_digest(preview.evidence)
    ):
        raise ValueError("Judge narrative must be bound to the verified source metric")

    # Controlled error: a forged numerical assertion is genuinely recalculated
    # by the verification engine and must be denied, never relabelled as safe.
    false_assertion = metric_assertion.model_copy(update={"value": observed + 1.0})
    false_claim = preview.claim.model_copy(update={"assertion": false_assertion})
    false_verdict = verify_claim(false_claim, preview.evidence, preview.events)
    if false_verdict.status != "needs_revision":
        raise ValueError("Judge test error unexpectedly passed verification")

    variants: list[dict[str, object]] = []
    for language, persona in product(_LANGUAGES, _PERSONAS):
        text = _SCRIPTED_COPY[(language, persona)]
        payload = CommentaryPayload(
            lines=(ClaimLinkedText(claim_id=preview.claim.claim_id, text=text),)
        )
        variant = build_audience_variant(
            preview.output,
            output_id=f"judge-{language}-{persona}",
            payload=payload,
            language=language,  # type: ignore[arg-type]
            persona=persona,  # type: ignore[arg-type]
        )
        qualified = qualify_audience_variant(preview.output, variant, (verdict,))
        variants.append(
            {
                "output_id": variant.output_id,
                "language": language,
                "persona": persona,
                "text": text,
                "claim_ids": list(qualified.claim_ids),
                "evidence_digest": qualified.evidence_digest,
                "content_digest": qualified.variant_content_digest,
                "structural_verification": list(qualified.verification_statuses),
                "semantic_language_review": "NOT_RUN",
                "publishable": False,
            }
        )

    return {
        "schema_version": 1,
        "mode": "synthetic_local_read_only",
        "scenario": scenario.name,
        "seed": scenario.seed,
        "match_id": scenario.match_id,
        "source_events": [
            {
                "event_id": event.event_id,
                "period": event.period,
                "match_clock_ms": event.match_clock_ms,
                "type": event.type,
                "team_id": event.team_id,
            }
            for event in scenario.events
        ],
        "detected_moments": [
            {
                "moment_id": moment.moment_id,
                "kind": moment.kind,
                "event_ids": list(moment.evidence_event_ids),
            }
            for moment in moments
        ],
        "scripted_specialist_proposal": {
            "runtime": "offline_scripted_fixture_not_live_ai",
            "role": "narrative_composer",
            "claim_id": preview.claim.claim_id,
            "text": preview.claim.text,
            "source_event_ids": list(preview.claim.evidence_event_ids),
        },
        "registered_metric": {
            "id": metric_assertion.metric,
            "observed": observed,
            "unit": metric_assertion.unit,
            "window": metric_assertion.window.model_dump(mode="json"),
        },
        "verified_claim": {
            "claim_id": verdict.claim_id,
            "status": verdict.status,
            "observed": verdict.observed,
            "expected": verdict.expected,
            "evidence_digest": verdict.evidence_digest,
            "content_digest": preview.output.binding.content_digest,
        },
        "controlled_error": {
            "expected": false_verdict.expected,
            "observed": false_verdict.observed,
            "status": false_verdict.status,
            "published": False,
        },
        "producer_review": {
            "status": preview.review_status,
            "authenticated": False,
            "approval_enabled": False,
            "publication_enabled": False,
        },
        "audience_variants": variants,
        "human_language_review": "NOT_RUN",
        "manual_wcag_acceptance": "NOT_RUN",
        "live_model_executed": False,
        "live_producer_authority": False,
        "real_publication": False,
    }
