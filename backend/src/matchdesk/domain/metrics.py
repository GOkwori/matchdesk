"""Registered deterministic football metrics for MatchDesk Phase 1D.

Each public metric has a stable versioned identifier. The formulas operate only on
accepted immutable MatchEvent records and never infer missing football facts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from matchdesk.domain.models import MatchEvent, MatchWindow, Subject

_FINAL_THIRD_X = 200.0 / 3.0
# Locations are on a 0-100 pitch. Distances convert against a documented 105 m x 68 m pitch.
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
# A progressive pass moves the ball at least this far towards the opponent's goal, and ends at
# least this much closer to the centre of that goal than it started.
PROGRESSIVE_GAIN_M = 10.0
PROGRESSIVE_CLOSER = 0.25


@dataclass(frozen=True)
class MetricDefinition:
    """Stable registry metadata for one deterministic metric formula."""

    metric_id: str
    unit: str
    description: str


MetricFormula = Callable[[tuple[MatchEvent, ...], Subject, MatchWindow], float]


def _events_in_window(
    events: tuple[MatchEvent, ...],
    window: MatchWindow,
) -> tuple[MatchEvent, ...]:
    """Return events inside the half-open metric window after validating replay order."""
    if not events:
        return ()

    match_id = events[0].match_id
    previous_sequence: int | None = None
    for event in events:
        if event.match_id != match_id:
            raise ValueError("metric input cannot mix match identities")
        if previous_sequence is not None and event.sequence <= previous_sequence:
            raise ValueError("metric input must be in strictly increasing sequence order")
        previous_sequence = event.sequence

    return tuple(
        event
        for event in events
        if (window.period is None or event.period == window.period)
        and window.from_ms <= event.match_clock_ms < window.to_ms
    )


def _matches_subject(event: MatchEvent, subject: Subject) -> bool:
    """Apply every populated subject dimension without guessing missing identity."""
    if subject.team_id is not None and event.team_id != subject.team_id:
        return False
    if subject.player_id is not None and event.player_id != subject.player_id:
        return False
    return True


def _shots(events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow) -> float:
    """Count shot events for the requested subject and half-open match window."""
    selected = _events_in_window(events, window)
    return float(
        sum(event.type == "shot" and _matches_subject(event, subject) for event in selected)
    )


def _goals(events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow) -> float:
    """Count accepted goal markers, never shot outcomes, to preserve exactly-once scoring."""
    selected = _events_in_window(events, window)
    return float(
        sum(event.type == "goal" and _matches_subject(event, subject) for event in selected)
    )


def _pass_accuracy(
    events: tuple[MatchEvent, ...],
    subject: Subject,
    window: MatchWindow,
) -> float:
    """Return completed passes divided by attempted passes, or zero when no pass exists."""
    passes = tuple(
        event
        for event in _events_in_window(events, window)
        if event.type == "pass" and _matches_subject(event, subject)
    )
    if not passes:
        return 0.0
    completed = sum(event.outcome == "complete" for event in passes)
    return completed / len(passes)


def _synthetic_xg(
    events: tuple[MatchEvent, ...],
    subject: Subject,
    window: MatchWindow,
) -> float:
    """Sum the explicit synthetic xG values attached to shot events."""
    shots = (
        event
        for event in _events_in_window(events, window)
        if event.type == "shot" and _matches_subject(event, subject)
    )
    return _plain_sum(event.xg or 0.0 for event in shots)


def _final_third_entries(
    events: tuple[MatchEvent, ...],
    subject: Subject,
    window: MatchWindow,
) -> float:
    """Count completed movements that cross from outside into the attacking final third."""
    eligible = {"pass", "carry", "dribble"}
    selected = _events_in_window(events, window)
    count = 0
    for event in selected:
        if event.type not in eligible or event.outcome != "complete":
            continue
        if not _matches_subject(event, subject):
            continue
        assert event.location is not None
        assert event.end_location is not None
        if event.location.x < _FINAL_THIRD_X <= event.end_location.x:
            count += 1
    return float(count)


def _possession_time(
    events: tuple[MatchEvent, ...],
    subject: Subject,
    window: MatchWindow,
) -> float:
    """Return an event-derived team possession-time share inside the requested window.

    Consecutive accepted events within one period define observed time intervals. Each
    interval is attributed to the team on the earlier event, clipped to the half-open query
    window; a window without a period sums both periods. Period markers and other teamless events contribute no owned time.
    The denominator is total attributable observed time across teams. A window with
    no attributable interval returns zero rather than inventing possession.
    """
    if subject.team_id is None or subject.player_id is not None:
        raise ValueError("possession_time.v1 requires a team-only subject")

    if not events:
        return 0.0
    _events_in_window(events, window)

    # Intervals never span the half-time break: each period is walked on its own, and a
    # whole-match window (period None) sums both periods' clipped intervals.
    periods = (1, 2) if window.period is None else (window.period,)
    owned_ms: dict[str, int] = {}
    for period in periods:
        period_events = tuple(event for event in events if event.period == period)
        for current, following in zip(period_events, period_events[1:], strict=False):
            if current.team_id is None:
                continue
            start_ms = max(current.match_clock_ms, window.from_ms)
            end_ms = min(following.match_clock_ms, window.to_ms)
            if end_ms <= start_ms:
                continue
            owned_ms[current.team_id] = owned_ms.get(current.team_id, 0) + (end_ms - start_ms)

    total_ms = sum(owned_ms.values())
    if total_ms == 0:
        return 0.0
    return owned_ms.get(subject.team_id, 0) / total_ms


def _metres(event: MatchEvent) -> float:
    """Straight-line distance of a movement on the 105 m x 68 m pitch."""
    assert event.location is not None
    assert event.end_location is not None
    dx = (event.end_location.x - event.location.x) * PITCH_LENGTH_M / 100.0
    dy = (event.end_location.y - event.location.y) * PITCH_WIDTH_M / 100.0
    return math.sqrt(dx * dx + dy * dy)


def _forward_metres(event: MatchEvent) -> float:
    """Distance gained towards the opponent's goal, in metres (negative when backwards)."""
    assert event.location is not None
    assert event.end_location is not None
    return (event.end_location.x - event.location.x) * PITCH_LENGTH_M / 100.0


def _passes(
    events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow
) -> tuple[MatchEvent, ...]:
    """The subject's passes with a start and an end location, inside the window."""
    return tuple(
        event
        for event in _events_in_window(events, window)
        if event.type == "pass"
        and event.location is not None
        and event.end_location is not None
        and _matches_subject(event, subject)
    )


def _plain_sum(values: Iterable[float]) -> float:
    """Left-to-right float addition.

    Python 3.12's ``sum`` compensates for rounding and JavaScript's addition does not; the
    browser port must reproduce every bit, so both add the same way.
    """
    total = 0.0
    for value in values:
        total += value
    return total


def _mean(values: list[float]) -> float:
    """Arithmetic mean, or zero when there is nothing to average."""
    return _plain_sum(values) / len(values) if values else 0.0


def _pass_distance(events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow) -> float:
    """Mean length, in metres, of the subject's attempted passes."""
    return _mean([_metres(event) for event in _passes(events, subject, window)])


def _to_goal_metres(x: float, y: float) -> float:
    """Distance, in metres, from a pitch point to the centre of the opponent's goal."""
    dx = (100.0 - x) * PITCH_LENGTH_M / 100.0
    dy = (50.0 - y) * PITCH_WIDTH_M / 100.0
    return math.sqrt(dx * dx + dy * dy)


def _is_progressive(event: MatchEvent) -> bool:
    """A completed pass 10 m or more forward that ends at least 25% closer to goal."""
    assert event.location is not None
    assert event.end_location is not None
    before = _to_goal_metres(event.location.x, event.location.y)
    after = _to_goal_metres(event.end_location.x, event.end_location.y)
    return (
        event.outcome == "complete"
        and _forward_metres(event) >= PROGRESSIVE_GAIN_M
        and after <= (1.0 - PROGRESSIVE_CLOSER) * before
    )


def _progressive_passes(
    events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow
) -> float:
    """Completed passes 10 m or more forward that end at least 25% closer to goal."""
    return float(sum(_is_progressive(event) for event in _passes(events, subject, window)))


def pass_difficulty(event: MatchEvent) -> float:
    """A 0-100 rating of how hard one pass is, from its length, ambition, target and pressure.

    45% length (40 m or more is hardest), 30% forward ambition (30 m or more towards goal),
    15% a target in the final sixth of the pitch, 10% playing it under pressure. It rates the
    attempt, not the outcome, so accuracy and difficulty can be read side by side.
    """
    assert event.end_location is not None
    length = min(_metres(event) / 40.0, 1.0)
    ambition = min(max(_forward_metres(event) / 30.0, 0.0), 1.0)
    target = 1.0 if event.end_location.x >= 500.0 / 6.0 else 0.0
    pressure = 1.0 if event.under_pressure else 0.0
    return 100.0 * (0.45 * length + 0.30 * ambition + 0.15 * target + 0.10 * pressure)


def _pass_difficulty(
    events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow
) -> float:
    """Mean difficulty rating (0-100) of the subject's attempted passes."""
    return _mean([pass_difficulty(event) for event in _passes(events, subject, window)])


def _ball_speed(events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow) -> float:
    """Mean estimated ball speed, in km/h, of the subject's completed passes.

    The log has no tracking data, so each pass's travel time is estimated as the time until
    the next logged event in the same period. The figure is labelled as an estimate wherever
    it is shown.
    """
    _events_in_window(events, window)
    following = {
        current.event_id: after
        for current, after in zip(events, events[1:], strict=False)
        if current.period == after.period
    }
    speeds = []
    for event in _passes(events, subject, window):
        after = following.get(event.event_id)
        if event.outcome != "complete" or after is None:
            continue
        seconds = (after.match_clock_ms - event.match_clock_ms) / 1000.0
        if seconds > 0:
            speeds.append(_metres(event) / seconds * 3.6)
    return _mean(speeds)


def _pressured_passes(
    events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow
) -> float:
    """Passes the subject played under pressure from an opponent."""
    return float(sum(event.under_pressure for event in _passes(events, subject, window)))


def _tagged_recoveries(tag: str) -> MetricFormula:
    """Count the subject's ball recoveries that carry one tag (tackle or interception)."""

    def count(events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow) -> float:
        """Recoveries with the tag for the subject in the window."""
        return float(
            sum(
                event.type == "recovery" and tag in event.tags and _matches_subject(event, subject)
                for event in _events_in_window(events, window)
            )
        )

    return count


def _recoveries(events: tuple[MatchEvent, ...], subject: Subject, window: MatchWindow) -> float:
    """Every ball the subject won back: tackles, interceptions and loose balls."""
    return float(
        sum(
            event.type == "recovery" and _matches_subject(event, subject)
            for event in _events_in_window(events, window)
        )
    )


METRIC_DEFINITIONS: Mapping[str, MetricDefinition] = {
    "shots.v1": MetricDefinition(
        metric_id="shots.v1",
        unit="count",
        description="Shot events for the subject in the half-open match window.",
    ),
    "goals.v1": MetricDefinition(
        metric_id="goals.v1",
        unit="count",
        description="Accepted goal markers for the subject in the half-open match window.",
    ),
    "pass_accuracy.v1": MetricDefinition(
        metric_id="pass_accuracy.v1",
        unit="ratio",
        description="Completed passes divided by attempted passes; zero when no passes exist.",
    ),
    "synthetic_xg.v1": MetricDefinition(
        metric_id="synthetic_xg.v1",
        unit="synthetic_xg",
        description="Sum of explicit synthetic xG values attached to subject shot events.",
    ),
    "final_third_entries.v1": MetricDefinition(
        metric_id="final_third_entries.v1",
        unit="count",
        description="Completed pass/carry/dribble movements crossing into the attacking final third.",
    ),
    "possession_time.v1": MetricDefinition(
        metric_id="possession_time.v1",
        unit="ratio",
        description="Team share of event-derived attributable possession intervals.",
    ),
}

_NEW_DEFINITIONS: Mapping[str, MetricDefinition] = {
    "pass_distance.v1": MetricDefinition(
        metric_id="pass_distance.v1",
        unit="metres",
        description="Mean length of attempted passes on a 105 m x 68 m pitch.",
    ),
    "progressive_passes.v1": MetricDefinition(
        metric_id="progressive_passes.v1",
        unit="count",
        description="Completed passes 10 m or more forward ending at least 25% closer to goal.",
    ),
    "pass_difficulty.v1": MetricDefinition(
        metric_id="pass_difficulty.v1",
        unit="rating",
        description="Mean 0-100 difficulty of attempted passes: length, ambition, target, pressure.",
    ),
    "ball_speed.v1": MetricDefinition(
        metric_id="ball_speed.v1",
        unit="km_per_hour",
        description="Mean estimated speed of completed passes, timed to the next logged event.",
    ),
    "pressured_passes.v1": MetricDefinition(
        metric_id="pressured_passes.v1",
        unit="count",
        description="Passes played under pressure from an opponent.",
    ),
    "tackles.v1": MetricDefinition(
        metric_id="tackles.v1",
        unit="count",
        description="Ball recoveries won by a tackle.",
    ),
    "interceptions.v1": MetricDefinition(
        metric_id="interceptions.v1",
        unit="count",
        description="Ball recoveries won by an interception.",
    ),
    "recoveries.v1": MetricDefinition(
        metric_id="recoveries.v1",
        unit="count",
        description="Every ball recovery: tackles, interceptions and loose balls.",
    ),
}
METRIC_DEFINITIONS = {**METRIC_DEFINITIONS, **_NEW_DEFINITIONS}

_FORMULAS: Mapping[str, MetricFormula] = {
    "pass_distance.v1": _pass_distance,
    "progressive_passes.v1": _progressive_passes,
    "pass_difficulty.v1": _pass_difficulty,
    "ball_speed.v1": _ball_speed,
    "pressured_passes.v1": _pressured_passes,
    "tackles.v1": _tagged_recoveries("tackle"),
    "interceptions.v1": _tagged_recoveries("interception"),
    "recoveries.v1": _recoveries,
    "shots.v1": _shots,
    "goals.v1": _goals,
    "pass_accuracy.v1": _pass_accuracy,
    "synthetic_xg.v1": _synthetic_xg,
    "final_third_entries.v1": _final_third_entries,
    "possession_time.v1": _possession_time,
}


def compute_metric(
    metric_id: str,
    events: tuple[MatchEvent, ...],
    subject: Subject,
    window: MatchWindow,
) -> float:
    """Compute one registered metric or fail closed for an unknown formula identifier."""
    try:
        formula = _FORMULAS[metric_id]
    except KeyError as error:
        raise ValueError(f"unregistered metric: {metric_id}") from error
    return formula(events, subject, window)
