"""Registered deterministic football metrics for MatchDesk Phase 1D.

Each public metric has a stable versioned identifier. The formulas operate only on
accepted immutable MatchEvent records and never infer missing football facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from matchdesk.domain.models import MatchEvent, MatchWindow, Subject

_FINAL_THIRD_X = 200.0 / 3.0


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
        if event.period == window.period and window.from_ms <= event.match_clock_ms < window.to_ms
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
    return sum(event.xg or 0.0 for event in shots)


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

    Consecutive accepted events define observed time intervals. Each interval is
    attributed to the team on the earlier event, clipped to the half-open query
    window. Period markers and other teamless events contribute no owned time.
    The denominator is total attributable observed time across teams. A window with
    no attributable interval returns zero rather than inventing possession.
    """
    if subject.team_id is None or subject.player_id is not None:
        raise ValueError("possession_time.v1 requires a team-only subject")

    if not events:
        return 0.0
    _events_in_window(events, window)

    period_events = tuple(event for event in events if event.period == window.period)
    owned_ms: dict[str, int] = {}
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

_FORMULAS: Mapping[str, MetricFormula] = {
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
