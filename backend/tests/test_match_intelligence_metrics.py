"""Pass quality, ball speed and defending metrics, checked against hand calculations.

The pitch is 105 m x 68 m: one x unit is 1.05 m and one y unit is 0.68 m.
"""

import math

import pytest
from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.metrics import compute_metric, pass_difficulty
from matchdesk.domain.models import Location, MatchEvent, MatchWindow, Subject

WINDOW = MatchWindow(period=1, from_ms=0, to_ms=60_000)
HOME = Subject(team_id="home")


def _event(number: int, clock_ms: int, kind: str, **fields: object) -> MatchEvent:
    """A first-half event for the home team unless the fields say otherwise."""
    payload: dict[str, object] = {
        "event_id": f"e-{number}",
        "match_id": "m-1",
        "sequence": number,
        "period": 1,
        "match_clock_ms": clock_ms,
        "type": kind,
        "team_id": "home",
        "player_id": "home-7",
        "possession_id": 1,
    }
    payload.update(fields)
    return MatchEvent.model_validate(payload)


def _recovery(number: int, clock_ms: int, player: str, tags: tuple[str, ...]) -> MatchEvent:
    """An away-team ball recovery, tagged with how it was won."""
    return _event(
        number,
        clock_ms,
        "recovery",
        team_id="away",
        player_id=player,
        possession_id=2,
        location=Location(x=30.0, y=40.0),
        outcome="complete",
        tags=tags,
    )


def _fixture() -> tuple[MatchEvent, ...]:
    """Two passes, a recovery of each kind and a closing event for pass timing."""
    return (
        # 20 x units forward = 21 m; ends 25%+ closer to goal: progressive.
        _event(
            1,
            10_000,
            "pass",
            location=Location(x=50.0, y=50.0),
            end_location=Location(x=70.0, y=50.0),
            outcome="complete",
        ),
        # A 3-4-5 triangle in metres: 3 m forward, 4 m across, 5 m long, under pressure.
        _event(
            2,
            12_000,
            "pass",
            location=Location(x=40.0, y=10.0),
            end_location=Location(x=40.0 + 300.0 / 105.0, y=10.0 + 400.0 / 68.0),
            outcome="complete",
            under_pressure=True,
        ),
        _recovery(3, 13_000, "away-4", ("tackle",)),
        _recovery(4, 14_000, "away-5", ("interception",)),
        _recovery(5, 15_000, "away-6", ()),
    )


def test_pass_distance_is_the_mean_length_in_metres() -> None:
    """21 m and 5 m average to 13 m."""
    assert compute_metric("pass_distance.v1", _fixture(), HOME, WINDOW) == pytest.approx(13.0)


def test_only_long_forward_passes_that_close_on_goal_are_progressive() -> None:
    """The 21 m forward pass counts; the 3 m one does not."""
    assert compute_metric("progressive_passes.v1", _fixture(), HOME, WINDOW) == 1.0


def test_ball_speed_is_timed_to_the_next_event() -> None:
    """21 m in 2 s is 37.8 km/h; 5 m in 1 s is 18 km/h; the mean is 27.9 km/h."""
    assert compute_metric("ball_speed.v1", _fixture(), HOME, WINDOW) == pytest.approx(27.9)


def test_pass_difficulty_weighs_length_ambition_target_and_pressure() -> None:
    """Each component is checked on its own pass, then the mean."""
    first, second = _fixture()[:2]
    # 21 m of 40 m length, 21 m of 30 m ambition, no final-sixth target, no pressure.
    assert pass_difficulty(first) == pytest.approx(100 * (0.45 * 21 / 40 + 0.30 * 21 / 30))
    # 5 m long, 3 m forward, under pressure.
    assert pass_difficulty(second) == pytest.approx(100 * (0.45 * 5 / 40 + 0.30 * 3 / 30 + 0.10))
    mean = (pass_difficulty(first) + pass_difficulty(second)) / 2
    assert compute_metric("pass_difficulty.v1", _fixture(), HOME, WINDOW) == pytest.approx(mean)


def test_pressure_and_recovery_kinds_are_counted_separately() -> None:
    """One pass under pressure; one tackle, one interception, three recoveries in all."""
    events = _fixture()
    away = Subject(team_id="away")
    assert compute_metric("pressured_passes.v1", events, HOME, WINDOW) == 1.0
    assert compute_metric("tackles.v1", events, away, WINDOW) == 1.0
    assert compute_metric("interceptions.v1", events, away, WINDOW) == 1.0
    assert compute_metric("recoveries.v1", events, away, WINDOW) == 3.0


def test_empty_windows_measure_zero_rather_than_guessing() -> None:
    """No passes in the window means no length, speed or difficulty to report."""
    late = MatchWindow(period=1, from_ms=50_000, to_ms=60_000)
    for metric in ("pass_distance.v1", "ball_speed.v1", "pass_difficulty.v1"):
        assert compute_metric(metric, _fixture(), HOME, late) == 0.0


def test_canonical_log_gains_squads_and_defending_detail_without_moving_events() -> None:
    """Every player has a name; key events keep their identities, clocks and tags."""
    log = canonical.generate_canonical_match()
    assert len(log) == canonical.LAST_EVENT_NUMBER
    players = {event.player_id for event in log if event.player_id}
    assert players <= set(canonical.PLAYER_NAMES)
    by_id = {event.event_id: event for event in log}
    assert by_id["E-1366"].type == "goal" and by_id["E-1366"].match_clock_ms == 3_497_000
    assert by_id["E-1365"].tags == ("header",) and by_id["E-1359"].tags == ("corner",)
    assert any(event.under_pressure for event in log)
    kinds = {tag for event in log if event.type == "recovery" for tag in event.tags}
    assert kinds == {"tackle", "interception"}
    assert len(canonical.squad("nbr")) == 16 and canonical.squad("riv")[0]["position"] == "GK"
    assert math.isclose(sum(s["starter"] is True for s in canonical.squad("riv")), 11)
