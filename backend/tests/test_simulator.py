"""Independent Phase 1A tests for deterministic synthetic match generation."""

from collections import Counter

import pytest
from matchdesk.domain.simulator import (
    NORMAL_SCENARIOS,
    generate_scenario,
    scenario_bytes,
)


@pytest.mark.parametrize("name", NORMAL_SCENARIOS)
def test_normal_scenarios_are_byte_reproducible(name: str) -> None:
    """The same named scenario and seed must produce identical serialized bytes."""
    first = generate_scenario(name, 104729)  # type: ignore[arg-type]
    second = generate_scenario(name, 104729)  # type: ignore[arg-type]
    assert scenario_bytes(first) == scenario_bytes(second)


@pytest.mark.parametrize("name", NORMAL_SCENARIOS)
def test_different_seeds_change_normal_scenario_bytes(name: str) -> None:
    """A seed change must affect generated content without changing scenario rules."""
    first = generate_scenario(name, 104729)  # type: ignore[arg-type]
    second = generate_scenario(name, 104730)  # type: ignore[arg-type]
    assert scenario_bytes(first) != scenario_bytes(second)


@pytest.mark.parametrize("name", NORMAL_SCENARIOS)
def test_normal_streams_have_contiguous_unique_identity(name: str) -> None:
    """Normal scenarios must not contain duplicate IDs, sequence gaps or resets."""
    scenario = generate_scenario(name, 17)  # type: ignore[arg-type]
    assert [event.sequence for event in scenario.events] == list(range(len(scenario.events)))
    assert len({event.event_id for event in scenario.events}) == len(scenario.events)
    assert all(event.match_id == scenario.match_id for event in scenario.events)
    assert scenario.events[0].type == "period_start"
    assert scenario.events[-1].type == "period_end"


@pytest.mark.parametrize("name", NORMAL_SCENARIOS)
def test_goal_markers_reference_one_earlier_goal_shot(name: str) -> None:
    """Each goal marker must bind exactly once to a preceding goal-valued shot."""
    scenario = generate_scenario(name, 31)  # type: ignore[arg-type]
    events_by_id = {event.event_id: event for event in scenario.events}
    links: list[str] = []
    for event in scenario.events:
        if event.type != "goal":
            continue
        assert event.linked_event_id is not None
        shot = events_by_id[event.linked_event_id]
        assert shot.type == "shot"
        assert shot.outcome == "goal"
        assert shot.sequence < event.sequence
        assert shot.team_id == event.team_id
        links.append(event.linked_event_id)
    assert len(links) == len(set(links))


def test_late_winner_contains_a_winning_goal_after_88_minutes() -> None:
    """The late-winner fixture must expose its named deterministic fact."""
    scenario = generate_scenario("late_winner", 5)
    late_goals = [
        event
        for event in scenario.events
        if event.type == "goal" and event.period == 2 and event.match_clock_ms >= 5_280_000
    ]
    assert len(late_goals) == 1
    assert late_goals[0].team_id == "home"


def test_momentum_swing_has_two_quick_home_goals_after_away_lead() -> None:
    """The momentum fixture must contain an away lead then two nearby home goals."""
    scenario = generate_scenario("momentum_swing", 5)
    goals = [event for event in scenario.events if event.type == "goal"]
    assert [event.team_id for event in goals] == ["away", "home", "home"]
    assert goals[2].match_clock_ms - goals[1].match_clock_ms <= 300_000


def test_pressing_spell_has_four_attacking_half_regains_in_one_minute() -> None:
    """The pressing fixture must provide a measurable defensive-action cluster."""
    scenario = generate_scenario("pressing_spell", 5)
    actions = [
        event
        for event in scenario.events
        if event.type in {"tackle", "interception", "recovery"}
    ]
    assert len(actions) == 4
    assert all(event.team_id == "home" for event in actions)
    assert all(event.location is not None and event.location.x >= 50 for event in actions)
    assert actions[-1].match_clock_ms - actions[0].match_clock_ms < 60_000


def test_counter_attack_goal_stays_in_one_possession_and_under_15_seconds() -> None:
    """The counter fixture must bind recovery and goal to one fast possession."""
    scenario = generate_scenario("counter_attack_goal", 5)
    recovery = next(event for event in scenario.events if event.type == "recovery")
    goal = next(event for event in scenario.events if event.type == "goal")
    counter_events = [
        event
        for event in scenario.events
        if event.possession_id == recovery.possession_id and event.team_id == "home"
    ]
    assert {event.type for event in counter_events} >= {"recovery", "pass", "carry", "shot", "goal"}
    assert goal.match_clock_ms - recovery.match_clock_ms < 15_000


def test_fault_stream_contains_declared_stream_level_faults() -> None:
    """The fault scenario must stay structurally valid while exposing ingestion defects."""
    scenario = generate_scenario("fault_stream", 5)
    assert scenario.injected_faults == (
        "duplicate_event",
        "out_of_order_sequence",
        "sequence_gap",
        "replay_reset_signal",
    )
    ids = [event.event_id for event in scenario.events]
    sequences = [event.sequence for event in scenario.events]
    assert Counter(ids).most_common(1)[0][1] == 2
    assert any(left > right for left, right in zip(sequences, sequences[1:], strict=False))
    assert set(range(max(sequences) + 1)) - set(sequences)
    assert sequences[-1] == 0


@pytest.mark.parametrize("seed", [-1, True, 1.5, "1"])
def test_invalid_seed_is_rejected(seed: object) -> None:
    """Seeds must be real nonnegative integers rather than coerced scalar values."""
    with pytest.raises(ValueError):
        generate_scenario("late_winner", seed)  # type: ignore[arg-type]
