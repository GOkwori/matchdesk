"""Deterministic football moment detection for MatchDesk Phase 1E.

Moment detectors consume accepted, sequence-ordered MatchEvent records only. They
use explicit thresholds and event relationships; no language model or hidden state
is allowed to decide whether a moment exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from matchdesk.domain.models import MatchEvent

MomentKind = Literal[
    "goal",
    "big_chance",
    "momentum_swing",
    "pressing_spell",
    "counter_attack_goal",
]

_BIG_CHANCE_XG = 0.35
_MOMENTUM_WINDOW_MS = 5 * 60_000
_PRESSING_WINDOW_MS = 60_000
_PRESSING_SHOT_FOLLOWUP_MS = 30_000
_COUNTER_ATTACK_WINDOW_MS = 15_000
_ATTACKING_HALF_X = 50.0
_REGAIN_TYPES = frozenset({"tackle", "interception", "recovery"})


@dataclass(frozen=True)
class DetectedMoment:
    """One deterministic moment with exact supporting event identities."""

    moment_id: str
    kind: MomentKind
    team_id: str
    period: int
    start_ms: int
    end_ms: int
    evidence_event_ids: tuple[str, ...]


def _validate_input(events: tuple[MatchEvent, ...]) -> None:
    """Reject mixed matches or untrusted event ordering before detection begins."""
    if not events:
        return

    match_id = events[0].match_id
    previous_sequence: int | None = None
    for event in events:
        if event.match_id != match_id:
            raise ValueError("moment input cannot mix match identities")
        if previous_sequence is not None and event.sequence <= previous_sequence:
            raise ValueError("moment input must be in strictly increasing sequence order")
        previous_sequence = event.sequence


def _moment(
    *,
    kind: MomentKind,
    team_id: str,
    period: int,
    start_ms: int,
    end_ms: int,
    evidence: tuple[MatchEvent, ...],
) -> DetectedMoment:
    """Build a stable moment identity from its kind and terminal evidence event."""
    terminal = evidence[-1]
    return DetectedMoment(
        moment_id=f"{kind}-{terminal.event_id}",
        kind=kind,
        team_id=team_id,
        period=period,
        start_ms=start_ms,
        end_ms=end_ms,
        evidence_event_ids=tuple(event.event_id for event in evidence),
    )


def _detect_goals(events: tuple[MatchEvent, ...]) -> list[DetectedMoment]:
    """Detect every accepted goal marker exactly once."""
    moments: list[DetectedMoment] = []
    for event in events:
        if event.type != "goal":
            continue
        assert event.team_id is not None
        moments.append(
            _moment(
                kind="goal",
                team_id=event.team_id,
                period=event.period,
                start_ms=event.match_clock_ms,
                end_ms=event.match_clock_ms,
                evidence=(event,),
            )
        )
    return moments


def _detect_big_chances(events: tuple[MatchEvent, ...]) -> list[DetectedMoment]:
    """Detect shots whose explicit synthetic xG reaches the version-1 threshold."""
    moments: list[DetectedMoment] = []
    for event in events:
        if event.type != "shot" or event.xg is None or event.xg < _BIG_CHANCE_XG:
            continue
        assert event.team_id is not None
        moments.append(
            _moment(
                kind="big_chance",
                team_id=event.team_id,
                period=event.period,
                start_ms=event.match_clock_ms,
                end_ms=event.match_clock_ms,
                evidence=(event,),
            )
        )
    return moments


def _detect_momentum_swings(events: tuple[MatchEvent, ...]) -> list[DetectedMoment]:
    """Detect two goals by one team in the same period within five minutes."""
    goals_by_team: dict[tuple[int, str], list[MatchEvent]] = {}
    moments: list[DetectedMoment] = []

    for event in events:
        if event.type != "goal":
            continue
        assert event.team_id is not None
        key = (event.period, event.team_id)
        prior_goals = goals_by_team.setdefault(key, [])

        # Use the most recent qualifying prior goal so one terminal goal produces
        # at most one momentum-swing moment.
        prior = next(
            (
                candidate
                for candidate in reversed(prior_goals)
                if event.match_clock_ms - candidate.match_clock_ms <= _MOMENTUM_WINDOW_MS
            ),
            None,
        )
        if prior is not None:
            moments.append(
                _moment(
                    kind="momentum_swing",
                    team_id=event.team_id,
                    period=event.period,
                    start_ms=prior.match_clock_ms,
                    end_ms=event.match_clock_ms,
                    evidence=(prior, event),
                )
            )
        prior_goals.append(event)

    return moments


def _is_successful_regain(event: MatchEvent) -> bool:
    """Return whether an event is a successful attacking-half regain."""
    if event.type not in _REGAIN_TYPES or event.location is None:
        return False
    if event.location.x < _ATTACKING_HALF_X:
        return False
    if event.type == "tackle":
        return event.outcome == "won"
    return event.outcome == "complete"


def _detect_pressing_spells(events: tuple[MatchEvent, ...]) -> list[DetectedMoment]:
    """Detect four attacking-half regains in 60 seconds followed by a quick shot."""
    regains: dict[tuple[int, str], list[MatchEvent]] = {}
    moments: list[DetectedMoment] = []
    emitted_terminal_shots: set[str] = set()

    for event in events:
        if _is_successful_regain(event):
            assert event.team_id is not None
            key = (event.period, event.team_id)
            team_regains = regains.setdefault(key, [])
            team_regains.append(event)
            cutoff = event.match_clock_ms - _PRESSING_WINDOW_MS
            regains[key] = [candidate for candidate in team_regains if candidate.match_clock_ms >= cutoff]
            continue

        if event.type != "shot" or event.team_id is None or event.event_id in emitted_terminal_shots:
            continue

        key = (event.period, event.team_id)
        candidates = [
            candidate
            for candidate in regains.get(key, [])
            if 0 <= event.match_clock_ms - candidate.match_clock_ms <= _PRESSING_SHOT_FOLLOWUP_MS
        ]
        if len(candidates) < 4:
            continue

        evidence = tuple(candidates[-4:]) + (event,)
        moments.append(
            _moment(
                kind="pressing_spell",
                team_id=event.team_id,
                period=event.period,
                start_ms=evidence[0].match_clock_ms,
                end_ms=event.match_clock_ms,
                evidence=evidence,
            )
        )
        emitted_terminal_shots.add(event.event_id)

    return moments


def _detect_counter_attack_goals(events: tuple[MatchEvent, ...]) -> list[DetectedMoment]:
    """Detect recovery-to-goal sequences in one possession within fifteen seconds."""
    recoveries: dict[tuple[int, str, int], MatchEvent] = {}
    moments: list[DetectedMoment] = []

    for event in events:
        if (
            event.type == "recovery"
            and event.team_id is not None
            and event.possession_id is not None
            and event.outcome == "complete"
        ):
            recoveries[(event.period, event.team_id, event.possession_id)] = event
            continue

        if event.type != "goal" or event.team_id is None or event.possession_id is None:
            continue

        recovery = recoveries.get((event.period, event.team_id, event.possession_id))
        if recovery is None:
            continue
        elapsed = event.match_clock_ms - recovery.match_clock_ms
        if not 0 <= elapsed <= _COUNTER_ATTACK_WINDOW_MS:
            continue

        possession_events = tuple(
            candidate
            for candidate in events
            if recovery.sequence <= candidate.sequence <= event.sequence
            and candidate.period == event.period
            and candidate.team_id == event.team_id
            and candidate.possession_id == event.possession_id
        )
        moments.append(
            _moment(
                kind="counter_attack_goal",
                team_id=event.team_id,
                period=event.period,
                start_ms=recovery.match_clock_ms,
                end_ms=event.match_clock_ms,
                evidence=possession_events,
            )
        )

    return moments


def detect_moments(events: tuple[MatchEvent, ...]) -> tuple[DetectedMoment, ...]:
    """Return all version-1 moments in stable temporal/type order."""
    _validate_input(events)
    if not events:
        return ()

    moments = (
        _detect_goals(events)
        + _detect_big_chances(events)
        + _detect_momentum_swings(events)
        + _detect_pressing_spells(events)
        + _detect_counter_attack_goals(events)
    )
    return tuple(sorted(moments, key=lambda item: (item.end_ms, item.kind, item.moment_id)))
