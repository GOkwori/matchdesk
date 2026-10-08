"""Phase 1C reducer tests for roster, score, possession and reference truth."""

import pytest
from matchdesk.domain.models import Location, MatchEvent
from matchdesk.domain.reducer import MatchReducer, TeamRoster
from matchdesk.domain.simulator import NORMAL_SCENARIOS, generate_scenario


def _rosters() -> tuple[TeamRoster, TeamRoster]:
    """Return fictional registered players covering all current simulator scenarios."""
    return (
        TeamRoster(
            team_id="home",
            starters=tuple(f"home-{number:02d}" for number in range(1, 12)),
            substitutes=("home-12", "home-13"),
        ),
        TeamRoster(
            team_id="away",
            starters=tuple(f"away-{number:02d}" for number in range(1, 12)),
            substitutes=("away-12", "away-13"),
        ),
    )


@pytest.mark.parametrize("name", NORMAL_SCENARIOS)
def test_normal_scenarios_reduce_without_truth_violations(name: str) -> None:
    """Every normal generated stream must satisfy reducer football invariants."""
    scenario = generate_scenario(name, 23)  # type: ignore[arg-type]
    reducer = MatchReducer(scenario.match_id, _rosters())

    for event in scenario.events:
        reducer.apply(event)

    state = reducer.snapshot()
    assert state.last_sequence == scenario.events[-1].sequence
    assert state.processed_event_ids == frozenset(event.event_id for event in scenario.events)


def test_late_winner_reduces_to_home_two_away_one() -> None:
    """Exactly-once goal markers, not shots, determine the final score."""
    scenario = generate_scenario("late_winner", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())

    for event in scenario.events:
        reducer.apply(event)

    assert reducer.snapshot().scores == {"home": 2, "away": 1}


def test_exact_duplicate_is_an_idempotent_reducer_no_op() -> None:
    """Reapplying identical accepted content cannot increment score twice."""
    scenario = generate_scenario("counter_attack_goal", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())

    for event in scenario.events:
        reducer.apply(event)
    before = reducer.snapshot()

    after = reducer.apply(scenario.events[6])

    assert after == before
    assert after.scores == {"home": 1, "away": 0}


def test_event_id_reuse_with_changed_content_fails_closed() -> None:
    """An immutable event identity cannot silently acquire different reducer content."""
    scenario = generate_scenario("counter_attack_goal", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())
    event = scenario.events[0]
    reducer.apply(event)

    changed = event.model_copy(update={"match_clock_ms": 1})

    with pytest.raises(ValueError, match="event_id"):
        reducer.apply(changed)


def test_out_of_order_sequence_is_rejected() -> None:
    """The reducer must consume the accepted temporal sequence produced by ingestion."""
    scenario = generate_scenario("counter_attack_goal", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())
    reducer.apply(scenario.events[0])
    reducer.apply(scenario.events[2])

    with pytest.raises(ValueError, match="strictly increasing"):
        reducer.apply(scenario.events[1])


def test_unregistered_team_is_rejected() -> None:
    """Football state cannot be updated by a team outside the registered match."""
    scenario = generate_scenario("counter_attack_goal", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())
    reducer.apply(scenario.events[0])
    event = scenario.events[1].model_copy(update={"team_id": "third-team"})

    with pytest.raises(ValueError, match="team is not registered"):
        reducer.apply(event)


def test_inactive_player_is_rejected() -> None:
    """Only currently active registered players can produce ordinary player events."""
    scenario = generate_scenario("counter_attack_goal", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())
    reducer.apply(scenario.events[0])
    event = scenario.events[1].model_copy(update={"player_id": "away-12"})

    with pytest.raises(ValueError, match="not active"):
        reducer.apply(event)


def test_possession_cannot_switch_teams() -> None:
    """One possession identifier must retain one team owner throughout a revision."""
    scenario = generate_scenario("counter_attack_goal", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())
    reducer.apply(scenario.events[0])
    reducer.apply(scenario.events[1])

    conflicting = scenario.events[2].model_copy(
        update={
            "team_id": "away",
            "player_id": "away-06",
            "possession_id": scenario.events[1].possession_id,
        }
    )

    with pytest.raises(ValueError, match="possession_id"):
        reducer.apply(conflicting)


def test_goal_requires_previously_accepted_linked_shot() -> None:
    """A goal cannot score before its referenced shot exists in accepted state."""
    scenario = generate_scenario("counter_attack_goal", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())

    for event in scenario.events[:5]:
        reducer.apply(event)

    goal = scenario.events[6].model_copy(update={"linked_event_id": "missing-shot"})

    with pytest.raises(ValueError, match="has not been accepted"):
        reducer.apply(goal)


def test_goal_reference_must_point_to_goal_valued_shot() -> None:
    """Saved or off-target shots cannot be converted into goals by a goal marker."""
    scenario = generate_scenario("pressing_spell", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())
    for event in scenario.events[:7]:
        reducer.apply(event)

    saved_shot = scenario.events[6]
    fake_goal = MatchEvent.model_validate(
        {
            "event_id": "fake-goal",
            "match_id": scenario.match_id,
            "sequence": 7,
            "period": 1,
            "match_clock_ms": saved_shot.match_clock_ms + 100,
            "type": "goal",
            "team_id": "home",
            "player_id": "home-09",
            "possession_id": saved_shot.possession_id,
            "location": saved_shot.location,
            "outcome": "goal",
            "linked_event_id": saved_shot.event_id,
        }
    )

    with pytest.raises(ValueError, match="goal-valued shot"):
        reducer.apply(fake_goal)


def test_one_shot_cannot_score_twice() -> None:
    """Exactly-once scoring rejects a second goal marker for the same linked shot."""
    scenario = generate_scenario("counter_attack_goal", 7)
    reducer = MatchReducer(scenario.match_id, _rosters())
    for event in scenario.events[:7]:
        reducer.apply(event)

    first_goal = scenario.events[6]
    duplicate_score = first_goal.model_copy(
        update={"event_id": "second-goal-marker", "sequence": 7}
    )

    with pytest.raises(ValueError, match="already produced"):
        reducer.apply(duplicate_score)


def test_substitution_updates_current_roster() -> None:
    """A valid substitution deactivates the outgoing player and activates the substitute."""
    match_id = "substitution-test"
    reducer = MatchReducer(match_id, _rosters())
    start = MatchEvent.model_validate(
        {
            "event_id": "start",
            "match_id": match_id,
            "sequence": 0,
            "period": 1,
            "match_clock_ms": 0,
            "type": "period_start",
        }
    )
    substitution = MatchEvent.model_validate(
        {
            "event_id": "sub",
            "match_id": match_id,
            "sequence": 1,
            "period": 1,
            "match_clock_ms": 1_800_000,
            "type": "substitution",
            "team_id": "home",
            "player_id": "home-09",
            "related_player_id": "home-12",
            "outcome": "complete",
        }
    )
    next_touch = MatchEvent.model_validate(
        {
            "event_id": "touch",
            "match_id": match_id,
            "sequence": 2,
            "period": 1,
            "match_clock_ms": 1_801_000,
            "type": "pass",
            "team_id": "home",
            "player_id": "home-12",
            "possession_id": 60,
            "location": Location(x=50.0, y=50.0),
            "end_location": Location(x=55.0, y=50.0),
            "outcome": "complete",
        }
    )

    reducer.apply(start)
    state = reducer.apply(substitution)
    reducer.apply(next_touch)

    assert "home-09" not in state.active_players["home"]
    assert "home-12" in state.active_players["home"]


def test_substitution_rejects_unregistered_or_already_active_incoming_player() -> None:
    """Substitutions must draw from registered inactive players only."""
    match_id = "bad-substitution-test"
    reducer = MatchReducer(match_id, _rosters())
    start = MatchEvent.model_validate(
        {
            "event_id": "start",
            "match_id": match_id,
            "sequence": 0,
            "period": 1,
            "match_clock_ms": 0,
            "type": "period_start",
        }
    )
    reducer.apply(start)

    def substitution(event_id: str, incoming: str) -> MatchEvent:
        return MatchEvent.model_validate(
            {
                "event_id": event_id,
                "match_id": match_id,
                "sequence": 1,
                "period": 1,
                "match_clock_ms": 1_800_000,
                "type": "substitution",
                "team_id": "home",
                "player_id": "home-09",
                "related_player_id": incoming,
                "outcome": "complete",
            }
        )

    with pytest.raises(ValueError, match="not registered"):
        reducer.apply(substitution("bad-sub-1", "home-99"))

    with pytest.raises(ValueError, match="already active"):
        reducer.apply(substitution("bad-sub-2", "home-10"))


def test_roster_configuration_is_strict() -> None:
    """Reducer configuration rejects empty, duplicate and cross-team player identities."""
    with pytest.raises(ValueError, match="starter"):
        TeamRoster(team_id="home", starters=())
    with pytest.raises(ValueError, match="unique"):
        TeamRoster(team_id="home", starters=("home-01", "home-01"))

    home = TeamRoster(team_id="home", starters=("shared-player",))
    away = TeamRoster(team_id="away", starters=("shared-player",))
    with pytest.raises(ValueError, match="both teams"):
        MatchReducer("match", (home, away))
