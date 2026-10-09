"""P2-05 tests for deterministic live-model evaluation."""

from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import Claim, EvidenceRecord, MatchWindow, MetricAssertion, Subject
from matchdesk.domain.runtime_evaluation import evaluate_specialist_response
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.specialists import SpecialistResponse


def _events():
    """Return one deterministic synthetic scenario for evaluation."""
    return generate_scenario("counter_attack_goal", 7).events


def _evidence(events):
    """Bind the complete deterministic fixture to one evidence record."""
    return EvidenceRecord(
        evidence_id="p2e-evidence",
        match_id=events[0].match_id,
        replay_id="p2e-replay",
        revision=1,
        window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
        event_ids=tuple(event.event_id for event in events),
        engine_version="engine-v1",
        source_digest="a" * 64,
    )


def test_evaluation_passes_evidence_bound_tactical_inference() -> None:
    """A supported tactical inference can pass without becoming deterministic fact."""
    events = _events()
    event = next(item for item in events if item.team_id is not None)
    claim = Claim(
        claim_id="claim-supported",
        text="The sequence created a dangerous transition.",
        kind="tactical_inference",
        evidence_event_ids=(event.event_id,),
    )

    evaluation = evaluate_specialist_response(
        SpecialistResponse(role="tactical_analyst", proposed_claims=(claim,)),
        _evidence(events),
        events,
    )

    assert evaluation.status == "pass"
    assert evaluation.verification_results[0].status == "supported_inference"


def test_evaluation_requires_claim_for_model_quality_gate() -> None:
    """Natural text without an evidence-bound claim cannot pass the P2-05 gate."""
    events = _events()
    evaluation = evaluate_specialist_response(
        SpecialistResponse(role="tactical_analyst", content="Plausible but unbound prose."),
        _evidence(events),
        events,
    )

    assert evaluation.status == "needs_revision"
    assert evaluation.verification_results == ()


def test_evaluation_marks_unbound_claim_blocked() -> None:
    """A claim citing an event outside the evidence record is blocked."""
    events = _events()
    cited = next(item for item in events if item.team_id is not None)
    evidence = _evidence(events).model_copy(
        update={"event_ids": tuple(event.event_id for event in events if event != cited)}
    )
    claim = Claim(
        claim_id="claim-unbound",
        text="The cited event supports this interpretation.",
        kind="tactical_inference",
        evidence_event_ids=(cited.event_id,),
    )

    evaluation = evaluate_specialist_response(
        SpecialistResponse(role="tactical_analyst", proposed_claims=(claim,)),
        evidence,
        events,
    )

    assert evaluation.status == "blocked"
    assert evaluation.verification_results[0].status == "blocked"


def test_evaluation_marks_false_measured_claim_for_revision() -> None:
    """A numerically false model claim is recomputed instead of trusted."""
    events = _events()
    event = next(item for item in events if item.team_id is not None)
    subject = Subject(team_id=event.team_id)
    window = MatchWindow(period=1, from_ms=0, to_ms=2_100_000)
    observed = compute_metric("shots.v1", events, subject, window)
    claim = Claim(
        claim_id="claim-false-stat",
        text="The team recorded a different shot total.",
        kind="measured_stat",
        assertion=MetricAssertion(
            metric="shots.v1",
            subject=subject,
            window=window,
            comparator="eq",
            value=observed + 1.0,
            unit="count",
        ),
        evidence_event_ids=(event.event_id,),
    )
    evaluation = evaluate_specialist_response(
        SpecialistResponse(role="tactical_analyst", proposed_claims=(claim,)),
        _evidence(events),
        events,
    )
    assert evaluation.status == "needs_revision"
    assert evaluation.verification_results[0].observed == observed
