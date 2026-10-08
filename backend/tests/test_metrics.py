"""Independent expected-value tests for the registered Phase 1D football metrics."""

import pytest
from matchdesk.domain.metrics import METRIC_DEFINITIONS, compute_metric
from matchdesk.domain.models import Location, MatchEvent, MatchWindow, Subject


def _event(
    event_id: str,
    sequence: int,
    clock_ms: int,
    event_type: str,
    *,
    team_id: str | None = None,
    player_id: str | None = None,
    possession_id: int | None = None,
    x: float | None = None,
    end_x: float | None = None,
    outcome: str | None = None,
    xg: float | None = None,
    linked_event_id: str | None = None,
) -> MatchEvent:
    """Build one explicit event for hand-calculated metric expectations."""
    payload: dict[str, object] = {
        "event_id": event_id,
        "match_id": "metric-match",
        "sequence": sequence,
        "period": 1,
        "match_clock_ms": clock_ms,
        "type": event_type,
    }
    if team_id is not None:
        payload["team_id"] = team_id
    if player_id is not None:
        payload["player_id"] = player_id
    if possession_id is not None:
        payload["possession_id"] = possession_id
    if x is not None:
        payload["location"] = Location(x=x, y=50.0)
    if end_x is not None:
        payload["end_location"] = Location(x=end_x, y=50.0)
    if outcome is not None:
        payload["outcome"] = outcome
    if xg is not None:
        payload["xg"] = xg
    if linked_event_id is not None:
        payload["linked_event_id"] = linked_event_id
    return MatchEvent.model_validate(payload)


def _fixture_events() -> tuple[MatchEvent, ...]:
    """Return a sparse accepted replay whose metric values can be calculated by hand."""
    return (
        _event("start", 0, 0, "period_start"),
        _event(
            "home-pass-1",
            1,
            1_000,
            "pass",
            team_id="home",
            player_id="home-08",
            possession_id=1,
            x=50.0,
            end_x=70.0,
            outcome="complete",
        ),
        _event(
            "home-pass-2",
            2,
            5_000,
            "pass",
            team_id="home",
            player_id="home-10",
            possession_id=1,
            x=70.0,
            end_x=80.0,
            outcome="incomplete",
        ),
        _event(
            "home-shot-1",
            3,
            10_000,
            "shot",
            team_id="home",
            player_id="home-09",
            possession_id=1,
            x=88.0,
            outcome="saved",
            xg=0.2,
        ),
        _event(
            "away-pass-1",
            4,
            15_000,
            "pass",
            team_id="away",
            player_id="away-08",
            possession_id=2,
            x=40.0,
            end_x=60.0,
            outcome="complete",
        ),
        _event(
            "away-carry-1",
            5,
            25_000,
            "carry",
            team_id="away",
            player_id="away-10",
            possession_id=2,
            x=60.0,
            end_x=70.0,
            outcome="complete",
        ),
        _event(
            "away-shot-1",
            6,
            30_000,
            "shot",
            team_id="away",
            player_id="away-09",
            possession_id=2,
            x=90.0,
            outcome="goal",
            xg=0.4,
        ),
        _event(
            "away-goal-1",
            7,
            30_100,
            "goal",
            team_id="away",
            player_id="away-09",
            possession_id=2,
            x=90.0,
            outcome="goal",
            linked_event_id="away-shot-1",
        ),
        _event(
            "home-pass-3",
            8,
            40_000,
            "pass",
            team_id="home",
            player_id="home-08",
            possession_id=3,
            x=60.0,
            end_x=80.0,
            outcome="complete",
        ),
        _event(
            "home-shot-2",
            9,
            50_000,
            "shot",
            team_id="home",
            player_id="home-09",
            possession_id=3,
            x=91.0,
            outcome="goal",
            xg=0.5,
        ),
        _event(
            "home-goal-1",
            10,
            50_100,
            "goal",
            team_id="home",
            player_id="home-09",
            possession_id=3,
            x=91.0,
            outcome="goal",
            linked_event_id="home-shot-2",
        ),
        _event("end", 11, 60_000, "period_end"),
    )


def _whole_window() -> MatchWindow:
    """Return the full hand-calculated first-minute fixture window."""
    return MatchWindow(period=1, from_ms=0, to_ms=60_000)


def test_registry_contains_only_the_six_phase_1d_formula_ids() -> None:
    """The public registry is explicit so formulas cannot be selected by fuzzy names."""
    assert set(METRIC_DEFINITIONS) == {
        "shots.v1",
        "goals.v1",
        "pass_accuracy.v1",
        "synthetic_xg.v1",
        "final_third_entries.v1",
        "possession_time.v1",
    }


def test_team_count_and_sum_metrics_match_hand_calculated_values() -> None:
    """Shots, goals and synthetic xG use distinct event semantics."""
    events = _fixture_events()
    window = _whole_window()
    home = Subject(team_id="home")

    assert compute_metric("shots.v1", events, home, window) == 2.0
    assert compute_metric("goals.v1", events, home, window) == 1.0
    assert compute_metric("synthetic_xg.v1", events, home, window) == pytest.approx(0.7)


def test_pass_accuracy_is_completed_over_attempted_and_supports_player_scope() -> None:
    """Two of three home passes complete while home-08 completes both of his attempts."""
    events = _fixture_events()
    window = _whole_window()

    assert compute_metric(
        "pass_accuracy.v1", events, Subject(team_id="home"), window
    ) == pytest.approx(2.0 / 3.0)
    assert (
        compute_metric(
            "pass_accuracy.v1",
            events,
            Subject(team_id="home", player_id="home-08"),
            window,
        )
        == 1.0
    )


def test_pass_accuracy_returns_zero_for_a_zero_denominator() -> None:
    """A subject with no attempts yields zero rather than NaN, infinity or invented data."""
    assert (
        compute_metric(
            "pass_accuracy.v1",
            _fixture_events(),
            Subject(player_id="unused-player"),
            _whole_window(),
        )
        == 0.0
    )


def test_final_third_entries_require_completed_boundary_crossings() -> None:
    """Starting inside the final third does not count; crossing into it does."""
    events = _fixture_events()
    window = _whole_window()

    assert compute_metric("final_third_entries.v1", events, Subject(team_id="home"), window) == 2.0
    assert compute_metric("final_third_entries.v1", events, Subject(team_id="away"), window) == 1.0


def test_possession_time_uses_only_observed_attributable_intervals() -> None:
    """The fixture attributes 34 seconds to home and 25 seconds to away."""
    events = _fixture_events()
    window = _whole_window()

    assert compute_metric(
        "possession_time.v1", events, Subject(team_id="home"), window
    ) == pytest.approx(34.0 / 59.0)
    assert compute_metric(
        "possession_time.v1", events, Subject(team_id="away"), window
    ) == pytest.approx(25.0 / 59.0)


def test_possession_time_clips_intervals_to_the_query_window() -> None:
    """A partial window keeps the ownership established by the preceding event."""
    events = _fixture_events()
    window = MatchWindow(period=1, from_ms=12_000, to_ms=20_000)

    assert compute_metric(
        "possession_time.v1", events, Subject(team_id="home"), window
    ) == pytest.approx(3.0 / 8.0)
    assert compute_metric(
        "possession_time.v1", events, Subject(team_id="away"), window
    ) == pytest.approx(5.0 / 8.0)


def test_possession_time_requires_a_team_only_subject() -> None:
    """Player possession is not defined by this team-share formula."""
    events = _fixture_events()
    window = _whole_window()

    with pytest.raises(ValueError, match="team-only"):
        compute_metric("possession_time.v1", events, Subject(player_id="home-08"), window)
    with pytest.raises(ValueError, match="team-only"):
        compute_metric(
            "possession_time.v1",
            events,
            Subject(team_id="home", player_id="home-08"),
            window,
        )


def test_window_is_half_open_at_the_upper_bound() -> None:
    """An event exactly at to_ms belongs to the following window, not the current one."""
    events = _fixture_events()
    first_thirty_seconds = MatchWindow(period=1, from_ms=0, to_ms=30_000)

    assert compute_metric("shots.v1", events, Subject(team_id="away"), first_thirty_seconds) == 0.0


def test_unregistered_metric_and_untrusted_event_order_fail_closed() -> None:
    """Unknown formulas and unordered replay input cannot produce numerical evidence."""
    events = _fixture_events()
    window = _whole_window()

    with pytest.raises(ValueError, match="unregistered metric"):
        compute_metric("shots.v2", events, Subject(team_id="home"), window)

    unordered = (events[1], events[0], *events[2:])
    with pytest.raises(ValueError, match="strictly increasing"):
        compute_metric("shots.v1", unordered, Subject(team_id="home"), window)


def test_metric_input_cannot_mix_match_identities() -> None:
    """One metric result must never aggregate events from separate matches."""
    events = _fixture_events()
    foreign = events[-1].model_copy(update={"match_id": "other-match"})
    mixed = (*events[:-1], foreign)

    with pytest.raises(ValueError, match="mix match identities"):
        compute_metric("goals.v1", mixed, Subject(team_id="home"), _whole_window())
