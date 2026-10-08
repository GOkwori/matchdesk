"""Phase 1B temporal-ingestion tests using deterministic simulator streams."""

import pytest
from matchdesk.domain.ingestion import ReplayIngestor
from matchdesk.domain.simulator import NORMAL_SCENARIOS, generate_scenario


@pytest.mark.parametrize("name", NORMAL_SCENARIOS)
def test_normal_scenarios_ingest_in_sequence(name: str) -> None:
    """Every normal simulator scenario should be accepted without gaps or duplicates."""
    scenario = generate_scenario(name, 17)  # type: ignore[arg-type]
    ingestor = ReplayIngestor(scenario.match_id)

    decisions = [ingestor.ingest(event) for event in scenario.events]

    assert all(decision.status == "accepted" for decision in decisions)
    snapshot = ingestor.snapshot()
    assert snapshot.revision == 1
    assert snapshot.expected_sequence == len(scenario.events)
    assert snapshot.buffered_sequences == ()
    assert snapshot.missing_sequences == ()
    assert snapshot.accepted_events == scenario.events


def test_exact_duplicate_is_idempotent() -> None:
    """Re-sending identical event content must not advance accepted replay state."""
    scenario = generate_scenario("counter_attack_goal", 3)
    ingestor = ReplayIngestor(scenario.match_id)

    first = ingestor.ingest(scenario.events[0])
    duplicate = ingestor.ingest(scenario.events[0])

    assert first.status == "accepted"
    assert duplicate.status == "duplicate"
    assert duplicate.accepted_event_ids == ()
    assert ingestor.snapshot().expected_sequence == 1


def test_future_event_buffers_until_gap_closes() -> None:
    """A future sequence waits until missing predecessors arrive, then flushes in order."""
    scenario = generate_scenario("counter_attack_goal", 3)
    ingestor = ReplayIngestor(scenario.match_id)

    ingestor.ingest(scenario.events[0])
    future = ingestor.ingest(scenario.events[2])

    assert future.status == "buffered"
    assert future.missing_sequences == (1,)
    assert ingestor.snapshot().buffered_sequences == (2,)

    closed = ingestor.ingest(scenario.events[1])

    assert closed.status == "accepted"
    assert closed.accepted_event_ids == (
        scenario.events[1].event_id,
        scenario.events[2].event_id,
    )
    assert ingestor.snapshot().expected_sequence == 3
    assert ingestor.snapshot().buffered_sequences == ()


def test_multiple_visible_gaps_are_reported() -> None:
    """Gap reporting should expose all missing sequence numbers up to pending arrivals."""
    scenario = generate_scenario("counter_attack_goal", 3)
    ingestor = ReplayIngestor(scenario.match_id)

    ingestor.ingest(scenario.events[0])
    ingestor.ingest(scenario.events[3])
    decision = ingestor.ingest(scenario.events[5])

    assert decision.status == "buffered"
    assert decision.missing_sequences == (1, 2, 4)


def test_replay_reset_advances_revision_and_discards_stale_pending_events() -> None:
    """A distinct late sequence-zero marker starts a clean replay revision."""
    scenario = generate_scenario("fault_stream", 5)
    ingestor = ReplayIngestor(scenario.match_id)

    decisions = [ingestor.ingest(event) for event in scenario.events]

    assert any(decision.status == "duplicate" for decision in decisions)
    assert any(decision.status == "buffered" for decision in decisions)
    assert decisions[-1].status == "reset"
    assert decisions[-1].revision == 2
    snapshot = ingestor.snapshot()
    assert snapshot.replay_id.endswith("-r2")
    assert snapshot.expected_sequence == 1
    assert snapshot.buffered_sequences == ()
    assert snapshot.missing_sequences == ()
    assert tuple(event.sequence for event in snapshot.accepted_events) == (0,)
    assert snapshot.accepted_events[0].event_id == "fault-replay-reset"


def test_fault_stream_detects_gap_before_reset() -> None:
    """The deliberate missing sequence remains visible until the replay reset arrives."""
    scenario = generate_scenario("fault_stream", 5)
    ingestor = ReplayIngestor(scenario.match_id)

    before_reset = [ingestor.ingest(event) for event in scenario.events[:-1]]

    assert before_reset[-1].missing_sequences == (7,)
    assert ingestor.snapshot().buffered_sequences == (8, 9)


def test_event_id_reuse_with_changed_content_fails_closed() -> None:
    """One event ID cannot silently identify two different immutable event records."""
    scenario = generate_scenario("counter_attack_goal", 3)
    ingestor = ReplayIngestor(scenario.match_id)
    event = scenario.events[0]
    ingestor.ingest(event)

    conflicting = event.model_copy(update={"match_clock_ms": 1})

    with pytest.raises(ValueError, match="event_id was reused"):
        ingestor.ingest(conflicting)


def test_sequence_collision_with_different_event_fails_closed() -> None:
    """Two different pending events cannot claim the same replay sequence."""
    scenario = generate_scenario("counter_attack_goal", 3)
    ingestor = ReplayIngestor(scenario.match_id)
    ingestor.ingest(scenario.events[0])
    pending = scenario.events[2]
    ingestor.ingest(pending)

    collision = pending.model_copy(update={"event_id": "different-event"})

    with pytest.raises(ValueError, match="sequence collision"):
        ingestor.ingest(collision)


def test_stale_unseen_sequence_fails_closed() -> None:
    """A new event cannot claim a sequence that is already behind accepted position."""
    scenario = generate_scenario("counter_attack_goal", 3)
    ingestor = ReplayIngestor(scenario.match_id)
    ingestor.ingest(scenario.events[0])
    ingestor.ingest(scenario.events[1])

    stale = scenario.events[1].model_copy(update={"event_id": "stale-sequence"})

    with pytest.raises(ValueError, match="behind"):
        ingestor.ingest(stale)


def test_event_from_different_match_is_rejected() -> None:
    """A replay ingestor must never mix events belonging to different matches."""
    scenario = generate_scenario("counter_attack_goal", 3)
    ingestor = ReplayIngestor("other-match")

    with pytest.raises(ValueError, match="match_id"):
        ingestor.ingest(scenario.events[0])


@pytest.mark.parametrize("match_id", ["", "   "])
def test_blank_match_identifier_is_rejected(match_id: str) -> None:
    """An ingestor must have a meaningful match scope before accepting arrivals."""
    with pytest.raises(ValueError):
        ReplayIngestor(match_id)
