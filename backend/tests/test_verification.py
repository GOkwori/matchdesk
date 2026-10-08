"""Phase 2B tests for deterministic claim verification."""

from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import Claim, EvidenceRecord, MatchWindow, MetricAssertion, Subject
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.verification import verify_claim


def _fixture() -> tuple[tuple[object, ...], EvidenceRecord]:
    """Return accepted counter-attack events and one evidence record binding all of them."""
    events = generate_scenario("counter_attack_goal", 7).events
    evidence = EvidenceRecord(
        evidence_id="ev-1",
        match_id=events[0].match_id,
        replay_id="replay-1",
        revision=1,
        window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
        event_ids=tuple(event.event_id for event in events),
        engine_version="engine-v1",
        source_digest="a" * 64,
    )
    return events, evidence


def test_measured_claim_is_verified_by_registered_metric_recomputation() -> None:
    """A correct measured claim is verified from accepted events, not trusted prose."""
    events, evidence = _fixture()
    claim = Claim(
        claim_id="claim-1",
        text="Home took one shot.",
        kind="measured_stat",
        assertion=MetricAssertion(
            metric="shots.v1",
            subject=Subject(team_id="home"),
            window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
            comparator="eq",
            value=1.0,
            unit="count",
        ),
        evidence_event_ids=(events[-2].event_id,),
    )

    result = verify_claim(claim, evidence, events)

    assert result.status == "verified"
    assert result.expected == 1.0
    assert result.observed == 1.0
    assert result.query_id == "metric-shots-v1"
    assert result.evidence_digest == content_digest(evidence)


def test_wrong_measured_value_requires_revision() -> None:
    """A numerically false measured claim cannot pass because its text sounds plausible."""
    events, evidence = _fixture()
    claim = Claim(
        claim_id="claim-2",
        text="Home took two shots.",
        kind="measured_stat",
        assertion=MetricAssertion(
            metric="shots.v1",
            subject=Subject(team_id="home"),
            window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
            comparator="eq",
            value=2.0,
            unit="count",
        ),
        evidence_event_ids=(events[-2].event_id,),
    )

    result = verify_claim(claim, evidence, events)

    assert result.status == "needs_revision"
    assert result.observed == 1.0


def test_tactical_inference_is_supported_not_verified() -> None:
    """Existing evidence can support an inference without converting it into a fact."""
    events, evidence = _fixture()
    claim = Claim(
        claim_id="claim-3",
        text="The recovery triggered a dangerous transition.",
        kind="tactical_inference",
        evidence_event_ids=(events[1].event_id, events[-2].event_id),
    )

    result = verify_claim(claim, evidence, events)

    assert result.status == "supported_inference"
    assert result.expected is None
    assert result.observed is None


def test_event_fact_without_semantic_assertion_requires_revision() -> None:
    """Evidence existence alone never verifies arbitrary event-fact prose."""
    events, evidence = _fixture()
    claim = Claim(
        claim_id="claim-4",
        text="The goalkeeper touched the ball before the goal.",
        kind="event_fact",
        evidence_event_ids=(events[-1].event_id,),
    )

    result = verify_claim(claim, evidence, events)

    assert result.status == "needs_revision"
    assert result.query_id == "event-fact-semantic-v1"


def test_missing_claim_evidence_is_blocked() -> None:
    """A claim cannot verify against an event absent from the evidence record."""
    events, evidence = _fixture()
    claim = Claim(
        claim_id="claim-5",
        text="Unsupported event reference.",
        kind="tactical_inference",
        evidence_event_ids=("missing-event",),
    )

    result = verify_claim(claim, evidence, events)

    assert result.status == "blocked"
    assert "not bound" in result.reason


def test_mixed_match_input_is_blocked() -> None:
    """Verification cannot aggregate accepted events from different matches."""
    events, evidence = _fixture()
    foreign = events[-1].model_copy(update={"match_id": "other-match"})
    mixed = (*events[:-1], foreign)
    claim = Claim(
        claim_id="claim-6",
        text="Inference.",
        kind="tactical_inference",
        evidence_event_ids=(events[1].event_id,),
    )

    result = verify_claim(claim, evidence, mixed)

    assert result.status == "blocked"
    assert "outside the evidence match" in result.reason


def test_metric_unit_mismatch_is_blocked() -> None:
    """A registered metric cannot be relabelled with an incompatible unit."""
    events, evidence = _fixture()
    claim = Claim(
        claim_id="claim-7",
        text="Home took one shot.",
        kind="measured_stat",
        assertion=MetricAssertion(
            metric="shots.v1",
            subject=Subject(team_id="home"),
            window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
            comparator="eq",
            value=1.0,
            unit="ratio",
        ),
        evidence_event_ids=(events[-2].event_id,),
    )

    result = verify_claim(claim, evidence, events)

    assert result.status == "blocked"
    assert "registered metric unit" in result.reason


def test_gte_and_lte_comparators_are_recomputed() -> None:
    """Non-equality comparators use the observed deterministic metric value."""
    events, evidence = _fixture()
    for comparator, value in (("gte", 1.0), ("lte", 1.0)):
        claim = Claim(
            claim_id=f"claim-{comparator}",
            text="Comparator claim.",
            kind="measured_stat",
            assertion=MetricAssertion(
                metric="shots.v1",
                subject=Subject(team_id="home"),
                window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
                comparator=comparator,
                value=value,
                unit="count",
            ),
            evidence_event_ids=(events[-2].event_id,),
        )

        assert verify_claim(claim, evidence, events).status == "verified"


def test_empty_event_input_is_blocked() -> None:
    """No accepted events means no claim verification."""
    _, evidence = _fixture()
    claim = Claim(
        claim_id="claim-empty",
        text="Inference.",
        kind="tactical_inference",
        evidence_event_ids=(evidence.event_ids[0],),
    )

    assert verify_claim(claim, evidence, ()).status == "blocked"
