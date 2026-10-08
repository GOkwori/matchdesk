"""Phase 1E tests for deterministic football moment detection."""

import pytest
from matchdesk.domain.models import Location, MatchEvent
from matchdesk.domain.moments import detect_moments
from matchdesk.domain.simulator import generate_scenario


def _shot(
    event_id: str,
    sequence: int,
    clock_ms: int,
    *,
    xg: float,
    outcome: str = "saved",
    team_id: str = "home",
    possession_id: int = 1,
) -> MatchEvent:
    """Build one explicit shot for detector threshold tests."""
    return MatchEvent.model_validate(
        {
            "event_id": event_id,
            "match_id": "moment-match",
            "sequence": sequence,
            "period": 1,
            "match_clock_ms": clock_ms,
            "type": "shot",
            "team_id": team_id,
            "player_id": f"{team_id}-09",
            "possession_id": possession_id,
            "location": Location(x=88.0, y=50.0),
            "outcome": outcome,
            "xg": xg,
        }
    )


def _goal(
    event_id: str,
    sequence: int,
    clock_ms: int,
    *,
    shot_id: str,
    team_id: str = "home",
    possession_id: int = 1,
    period: int = 1,
) -> MatchEvent:
    """Build one accepted goal marker linked to an explicit shot identity."""
    return MatchEvent.model_validate(
        {
            "event_id": event_id,
            "match_id": "moment-match",
            "sequence": sequence,
            "period": period,
            "match_clock_ms": clock_ms,
            "type": "goal",
            "team_id": team_id,
            "player_id": f"{team_id}-09",
            "possession_id": possession_id,
            "location": Location(x=88.0, y=50.0),
            "outcome": "goal",
            "linked_event_id": shot_id,
        }
    )


def test_counter_attack_scenario_detects_goal_big_chance_and_counter() -> None:
    """The seeded counter scenario must expose its three deterministic moment types."""
    scenario = generate_scenario("counter_attack_goal", 7)

    moments = detect_moments(scenario.events)
    kinds = [moment.kind for moment in moments]

    assert kinds.count("goal") == 1
    assert kinds.count("big_chance") == 1
    assert kinds.count("counter_attack_goal") == 1

    counter = next(moment for moment in moments if moment.kind == "counter_attack_goal")
    assert counter.team_id == "home"
    assert counter.end_ms - counter.start_ms == 12_400
    assert counter.evidence_event_ids == (
        "ca-recovery-home",
        "ca-pass-home",
        "ca-carry-home",
        "ca-shot-home",
        "ca-goal-home",
    )


def test_pressing_scenario_detects_four_regains_followed_by_shot() -> None:
    """The seeded pressing spell must bind four attacking-half regains to its shot."""
    scenario = generate_scenario("pressing_spell", 11)

    moments = detect_moments(scenario.events)
    pressing = [moment for moment in moments if moment.kind == "pressing_spell"]

    assert len(pressing) == 1
    assert pressing[0].team_id == "home"
    assert pressing[0].evidence_event_ids == (
        "ps-action-1",
        "ps-action-2",
        "ps-action-3",
        "ps-action-4",
        "ps-shot-home",
    )


def test_momentum_swing_scenario_detects_two_home_goals_inside_five_minutes() -> None:
    """Two second-half home goals four minutes apart produce one momentum swing."""
    scenario = generate_scenario("momentum_swing", 19)

    moments = detect_moments(scenario.events)
    swings = [moment for moment in moments if moment.kind == "momentum_swing"]

    assert len(swings) == 1
    assert swings[0].team_id == "home"
    assert swings[0].end_ms - swings[0].start_ms == 240_000
    assert swings[0].evidence_event_ids == ("ms-goal-home-1", "ms-goal-home-2")


def test_late_winner_exposes_each_goal_marker_as_a_goal_moment() -> None:
    """Goal detection follows accepted goal markers rather than shot outcomes."""
    scenario = generate_scenario("late_winner", 3)

    goals = [moment for moment in detect_moments(scenario.events) if moment.kind == "goal"]

    assert [moment.evidence_event_ids for moment in goals] == [
        ("lw-goal-home-1",),
        ("lw-goal-away-1",),
        ("lw-goal-home-winner",),
    ]


def test_big_chance_threshold_is_inclusive_and_versioned_by_formula() -> None:
    """Synthetic xG 0.35 qualifies while a shot immediately below the threshold does not."""
    events = (
        _shot("shot-below", 0, 1_000, xg=0.349),
        _shot("shot-threshold", 1, 2_000, xg=0.35),
    )

    big_chances = [moment for moment in detect_moments(events) if moment.kind == "big_chance"]

    assert len(big_chances) == 1
    assert big_chances[0].evidence_event_ids == ("shot-threshold",)


def test_goal_and_big_chance_are_distinct_moments() -> None:
    """A goal-valued big-chance shot and its goal marker retain separate semantics."""
    events = (
        _shot("shot-goal", 0, 1_000, xg=0.6, outcome="goal"),
        _goal("goal", 1, 1_400, shot_id="shot-goal"),
    )

    moments = detect_moments(events)

    assert {(moment.kind, moment.evidence_event_ids) for moment in moments} == {
        ("big_chance", ("shot-goal",)),
        ("goal", ("goal",)),
    }


def test_momentum_swing_requires_same_team_same_period_and_five_minute_window() -> None:
    """Opponent, cross-period and slow goal pairs must not be labelled momentum swings."""
    same_team_slow = (
        _shot("shot-1", 0, 1_000, xg=0.2, outcome="goal"),
        _goal("goal-1", 1, 1_400, shot_id="shot-1"),
        _shot("shot-2", 2, 302_000, xg=0.2, outcome="goal"),
        _goal("goal-2", 3, 302_000, shot_id="shot-2"),
    )
    assert not any(moment.kind == "momentum_swing" for moment in detect_moments(same_team_slow))

    opponent_second = (
        same_team_slow[0],
        same_team_slow[1],
        _shot("away-shot", 2, 2_000, xg=0.2, outcome="goal", team_id="away"),
        _goal("away-goal", 3, 2_400, shot_id="away-shot", team_id="away"),
    )
    assert not any(moment.kind == "momentum_swing" for moment in detect_moments(opponent_second))


def test_pressing_spell_requires_all_four_successful_attacking_half_regains() -> None:
    """Removing one regain from the seeded spell prevents a pressing classification."""
    scenario = generate_scenario("pressing_spell", 11)
    reduced = tuple(event for event in scenario.events if event.event_id != "ps-action-2")

    assert not any(moment.kind == "pressing_spell" for moment in detect_moments(reduced))


def test_counter_attack_requires_same_possession_and_fifteen_second_limit() -> None:
    """A slow or detached goal cannot inherit counter-attack status from a recovery."""
    scenario = generate_scenario("counter_attack_goal", 7)

    slow = tuple(
        event.model_copy(update={"match_clock_ms": 2_056_000})
        if event.event_id == "ca-goal-home"
        else event
        for event in scenario.events
    )
    assert not any(moment.kind == "counter_attack_goal" for moment in detect_moments(slow))

    detached = tuple(
        event.model_copy(update={"possession_id": 999})
        if event.event_id == "ca-goal-home"
        else event
        for event in scenario.events
    )
    assert not any(moment.kind == "counter_attack_goal" for moment in detect_moments(detached))


def test_empty_input_produces_no_moments() -> None:
    """No events means no inferred moments."""
    assert detect_moments(()) == ()


def test_mixed_matches_and_unordered_input_fail_closed() -> None:
    """Moment detection only accepts one trusted ordered replay."""
    scenario = generate_scenario("counter_attack_goal", 7)
    foreign = scenario.events[-1].model_copy(update={"match_id": "other-match"})

    with pytest.raises(ValueError, match="mix match identities"):
        detect_moments((*scenario.events[:-1], foreign))

    unordered = (scenario.events[1], scenario.events[0], *scenario.events[2:])
    with pytest.raises(ValueError, match="strictly increasing"):
        detect_moments(unordered)


def test_output_order_is_stable_by_end_time_then_kind() -> None:
    """Coincident detector outputs have deterministic ordering for evidence hashing."""
    events = (
        _shot("shot-goal", 0, 1_000, xg=0.6, outcome="goal"),
        _goal("goal", 1, 1_000, shot_id="shot-goal"),
    )

    moments = detect_moments(events)

    assert [moment.kind for moment in moments] == ["big_chance", "goal"]
