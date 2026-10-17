"""Deterministic canonical demo match: Northbridge FC v Riverside United to 67:12.

This module generates the single synthetic event log behind the judge-facing
frontend. Key events are fixed anchors with the exact identities and clocks in
the design brief; every other event is seeded filler shaped so that the
registered metrics reproduce the scripted totals. Nothing here is real football
data, and no output carries approval or publication authority.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

from matchdesk.domain.models import Location, MatchEvent
from matchdesk.domain.reducer import TeamRoster

MATCH_ID = "nbr-riv-canonical"
HOME = "nbr"
AWAY = "riv"
CANONICAL_SEED = 4
LAST_EVENT_NUMBER = 1421
SECOND_HALF_MS = 2_700_000

HOME_STARTERS = tuple(f"nbr-{index:02d}" for index in range(1, 12))
HOME_SUBSTITUTES = tuple(f"nbr-{index:02d}" for index in range(12, 17))
AWAY_STARTERS = tuple(f"riv-{index:02d}" for index in range(1, 12))
AWAY_SUBSTITUTES = tuple(f"riv-{index:02d}" for index in range(12, 17))

# Invented display names for the few players the story mentions.
PLAYER_NAMES: dict[str, str] = {
    "nbr-09": "Okafor",
    "nbr-04": "Mensah",
    "riv-06": "Haddad",
    "riv-11": "Lindqvist",
    "riv-07": "Barros",
    "riv-14": "Kovac",
}

# Scripted Northbridge possession share per five-minute block (0-5', 5-10', ...).
TARGET_HOME_SHARE: tuple[float, ...] = (
    0.55,
    0.61,
    0.58,
    0.64,
    0.60,
    0.57,
    0.43,
    0.40,
    0.47,
    0.58,
    0.62,
    0.65,
    0.60,
    0.63,
)

# Non-anchor statistical events required to reach the scripted whole-match totals.
_EXTRA_SHOT_OUTCOMES: dict[str, tuple[str, ...]] = {
    HOME: ("saved",) * 4 + ("off_target",) * 5 + ("blocked",) * 3,
    AWAY: ("saved",) * 2 + ("off_target",) * 4 + ("blocked",) * 2,
}
_EXTRA_CORNERS: dict[str, int] = {HOME: 5, AWAY: 3}
_EXTRA_FOULS: dict[str, int] = {HOME: 7, AWAY: 10}
_ANCHOR_GUARD_MS = 45_000


def event_id(number: int) -> str:
    """Return the display identity for the n-th event in the log (E-0001...)."""
    return f"E-{number:04d}"


def rosters() -> tuple[TeamRoster, TeamRoster]:
    """Return the registered squads used to validate the canonical stream."""
    return (
        TeamRoster(HOME, HOME_STARTERS, HOME_SUBSTITUTES),
        TeamRoster(AWAY, AWAY_STARTERS, AWAY_SUBSTITUTES),
    )


def clock_ms(minutes: int, seconds: float) -> int:
    """Convert a display clock to milliseconds."""
    return int(round((minutes * 60 + seconds) * 1000))


@dataclass
class _Draft:
    """Mutable event draft; converted to an immutable MatchEvent once complete."""

    number: int
    period: int
    clock: int
    type: str = "pass"
    team: str | None = None
    player: str | None = None
    possession: int | None = None
    location: tuple[float, float] | None = None
    end_location: tuple[float, float] | None = None
    outcome: str | None = None
    xg: float | None = None
    linked: int | None = None
    related_player: str | None = None
    tags: tuple[str, ...] = ()
    anchor: bool = False
    run: int | None = None


@dataclass
class _Run:
    """One filler possession: consecutive drafts owned by one team."""

    team: str
    numbers: list[int] = field(default_factory=list)
    used: bool = False


def _rng(seed: int) -> random.Random:
    """Return a PRNG derived from the seed without process hash randomisation."""
    material = f"matchdesk-canonical-v1:{seed}".encode("utf-8")
    return random.Random(int.from_bytes(hashlib.sha256(material).digest()[:8], "big"))


def _anchors() -> dict[int, _Draft]:
    """Return the scripted key events with their exact identities and clocks."""
    p2 = 2
    drafts = [
        _Draft(1, 1, 0, "period_start"),
        _Draft(2, 1, 0, "kickoff", HOME, "nbr-09", location=(50.0, 50.0), outcome="complete"),
        _Draft(
            560,
            1,
            clock_ms(27, 38),
            "foul",
            AWAY,
            "riv-06",
            location=(52.0, 38.0),
            outcome="committed",
        ),
        _Draft(561, 1, clock_ms(27, 40), "card", AWAY, "riv-06", outcome="yellow"),
        _Draft(
            686,
            1,
            clock_ms(34, 15),
            "pass",
            HOME,
            "nbr-10",
            location=(70.0, 58.0),
            end_location=(84.0, 57.0),
            outcome="complete",
        ),
        _Draft(
            687,
            1,
            clock_ms(34, 17.6),
            "shot",
            HOME,
            "nbr-09",
            location=(84.0, 57.0),
            outcome="goal",
            xg=0.21,
        ),
        _Draft(
            688,
            1,
            clock_ms(34, 18),
            "goal",
            HOME,
            "nbr-09",
            location=(84.0, 57.0),
            outcome="goal",
            linked=687,
        ),
        _Draft(
            689,
            1,
            clock_ms(34, 48),
            "kickoff",
            AWAY,
            "riv-09",
            location=(50.0, 50.0),
            outcome="complete",
        ),
        _Draft(
            788,
            1,
            clock_ms(41, 0),
            "pass",
            AWAY,
            "riv-07",
            location=(95.0, 30.0),
            end_location=(88.0, 44.0),
            outcome="complete",
        ),
        _Draft(
            789,
            1,
            clock_ms(41, 2.6),
            "shot",
            AWAY,
            "riv-11",
            location=(88.0, 44.0),
            outcome="goal",
            xg=0.38,
        ),
        _Draft(
            790,
            1,
            clock_ms(41, 3),
            "goal",
            AWAY,
            "riv-11",
            location=(88.0, 44.0),
            outcome="goal",
            linked=789,
        ),
        _Draft(
            791,
            1,
            clock_ms(41, 33),
            "kickoff",
            HOME,
            "nbr-09",
            location=(50.0, 50.0),
            outcome="complete",
        ),
        _Draft(841, 1, SECOND_HALF_MS, "period_end"),
        _Draft(842, p2, SECOND_HALF_MS, "period_start"),
        _Draft(
            843,
            p2,
            SECOND_HALF_MS,
            "kickoff",
            AWAY,
            "riv-09",
            location=(50.0, 50.0),
            outcome="complete",
        ),
        _Draft(
            1359,
            p2,
            clock_ms(58, 3),
            "pass",
            HOME,
            "nbr-07",
            location=(99.5, 0.5),
            end_location=(93.0, 47.0),
            outcome="incomplete",
            tags=("corner",),
        ),
        _Draft(
            1360,
            p2,
            clock_ms(58, 5),
            "clearance",
            AWAY,
            "riv-05",
            location=(8.0, 50.0),
            outcome="incomplete",
        ),
        _Draft(
            1361,
            p2,
            clock_ms(58, 7),
            "recovery",
            HOME,
            "nbr-08",
            location=(70.0, 22.0),
            outcome="complete",
        ),
        _Draft(
            1362,
            p2,
            clock_ms(58, 9),
            "pass",
            HOME,
            "nbr-08",
            location=(70.0, 22.0),
            end_location=(84.0, 9.0),
            outcome="complete",
        ),
        _Draft(
            1363,
            p2,
            clock_ms(58, 12),
            "carry",
            HOME,
            "nbr-07",
            location=(84.0, 9.0),
            end_location=(92.0, 8.0),
            outcome="complete",
        ),
        _Draft(
            1364,
            p2,
            clock_ms(58, 15),
            "pass",
            HOME,
            "nbr-07",
            location=(92.0, 8.0),
            end_location=(95.0, 47.0),
            outcome="complete",
        ),
        _Draft(
            1365,
            p2,
            clock_ms(58, 16.6),
            "shot",
            HOME,
            "nbr-09",
            location=(95.0, 47.0),
            outcome="goal",
            xg=0.34,
            tags=("header",),
        ),
        _Draft(
            1366,
            p2,
            clock_ms(58, 17),
            "goal",
            HOME,
            "nbr-09",
            location=(95.0, 47.0),
            outcome="goal",
            linked=1365,
        ),
        _Draft(
            1367,
            p2,
            clock_ms(58, 47),
            "kickoff",
            AWAY,
            "riv-09",
            location=(50.0, 50.0),
            outcome="complete",
        ),
        _Draft(
            1401,
            p2,
            clock_ms(63, 2),
            "foul",
            HOME,
            "nbr-04",
            location=(47.0, 62.0),
            outcome="committed",
        ),
        _Draft(1402, p2, clock_ms(63, 4), "card", HOME, "nbr-04", outcome="yellow"),
        _Draft(
            LAST_EVENT_NUMBER,
            p2,
            clock_ms(67, 8),
            "substitution",
            AWAY,
            "riv-07",
            outcome="complete",
            related_player="riv-14",
        ),
    ]
    for draft in drafts:
        draft.anchor = True
    return {draft.number: draft for draft in drafts}


def _target_share(clock: int) -> float:
    """Return the scripted Northbridge share for the five-minute block containing clock."""
    block = min(clock // 300_000, len(TARGET_HOME_SHARE) - 1)
    return TARGET_HOME_SHARE[block]


def _other(team: str) -> str:
    """Return the opposing team identifier."""
    return AWAY if team == HOME else HOME


def _layout(anchors: dict[int, _Draft]) -> list[_Draft]:
    """Place filler drafts evenly in clock between consecutive anchors."""
    ordered = sorted(anchors)
    drafts: list[_Draft] = []
    for left, right in zip(ordered, ordered[1:], strict=False):
        start, end = anchors[left], anchors[right]
        drafts.append(start)
        gap = right - left - 1
        for offset in range(1, gap + 1):
            clock = start.clock + (end.clock - start.clock) * offset // (gap + 1)
            drafts.append(_Draft(left + offset, start.period, clock))
    drafts.append(anchors[ordered[-1]])
    return drafts


def _assign_runs(drafts: list[_Draft], generator: random.Random) -> list[_Run]:
    """Give filler drafts possession runs whose lengths follow the target share."""
    runs: list[_Run] = []
    possession = 0
    team = HOME
    remaining = 0
    keep_team = False
    for draft in drafts:
        if draft.anchor:
            if draft.team is not None and draft.type in ("kickoff", "recovery", "pass", "carry"):
                possession += 1
                draft.possession = possession
                team = draft.team
                remaining = 0
                keep_team = True
            elif draft.type in ("shot", "goal"):
                draft.possession = possession if draft.team == team else None
            continue
        if remaining <= 0:
            if not keep_team:
                team = _other(team)
            keep_team = False
            share = _target_share(draft.clock)
            mean = 16.0 * (share if team == HOME else 1.0 - share)
            remaining = max(2, round(generator.gauss(mean, mean * 0.3)))
            possession += 1
            runs.append(_Run(team))
        run = runs[-1]
        run.numbers.append(draft.number)
        draft.team = team
        draft.possession = possession
        draft.run = len(runs) - 1
        remaining -= 1
    return runs


def _fill_actions(drafts: dict[int, _Draft], runs: list[_Run], generator: random.Random) -> None:
    """Turn each run into recovery, passes/carries and a final lost pass."""
    for run in runs:
        size = len(run.numbers)
        for index, number in enumerate(run.numbers):
            draft = drafts[number]
            progress = (index + 1) / (size + 1)
            x = 18.0 + 60.0 * progress + generator.uniform(-6.0, 6.0)
            y = generator.uniform(8.0, 92.0)
            draft.player = f"{draft.team}-{generator.randint(2, 11):02d}"
            draft.location = (round(x, 1), round(y, 1))
            if index == 0:
                draft.type, draft.outcome, draft.end_location = "recovery", "complete", None
            elif generator.random() < 0.18:
                draft.type, draft.outcome = "carry", "complete"
                draft.end_location = (round(min(99.0, x + 6.0), 1), round(y, 1))
            else:
                last = index == size - 1
                draft.type = "pass"
                draft.outcome = "incomplete" if last else "complete"
                end_x = min(99.0, x + generator.uniform(4.0, 16.0))
                draft.end_location = (round(end_x, 1), round(generator.uniform(8.0, 92.0), 1))


def _near_anchor(clock: int, anchor_clocks: list[int]) -> bool:
    """Return whether a clock is too close to a scripted key event."""
    return any(abs(clock - other) < _ANCHOR_GUARD_MS for other in anchor_clocks)


def _eligible(
    runs: list[_Run], drafts: dict[int, _Draft], team: str, anchor_clocks: list[int]
) -> list[_Run]:
    """Return unused runs of a team that are long enough and away from anchors."""
    return [
        run
        for run in runs
        if run.team == team
        and not run.used
        and len(run.numbers) >= 4
        and not _near_anchor(drafts[run.numbers[0]].clock, anchor_clocks)
        and not _near_anchor(drafts[run.numbers[-1]].clock, anchor_clocks)
    ]


def _place_statistics(
    drafts: dict[int, _Draft], runs: list[_Run], generator: random.Random
) -> None:
    """Convert filler events into the shots, corners and fouls the totals require."""
    anchor_clocks = [draft.clock for draft in drafts.values() if draft.anchor]
    for team in (HOME, AWAY):
        outcomes = list(_EXTRA_SHOT_OUTCOMES[team])
        generator.shuffle(outcomes)
        for run, outcome in zip(
            generator.sample(_eligible(runs, drafts, team, anchor_clocks), len(outcomes)),
            outcomes,
            strict=True,
        ):
            run.used = True
            shot = drafts[run.numbers[-1]]
            shot.type, shot.outcome, shot.end_location = "shot", outcome, None
            shot.location = (
                round(generator.uniform(76.0, 95.0), 1),
                round(generator.uniform(22.0, 78.0), 1),
            )
            shot.xg = round(generator.uniform(0.03, 0.28), 3)
        for run in generator.sample(
            _eligible(runs, drafts, team, anchor_clocks), _EXTRA_CORNERS[team]
        ):
            run.used = True
            corner = drafts[run.numbers[0]]
            corner.type, corner.outcome, corner.tags = "pass", "complete", ("corner",)
            corner.location = (99.5, generator.choice((0.5, 99.5)))
            corner.end_location = (
                round(generator.uniform(88.0, 95.0), 1),
                round(generator.uniform(36.0, 64.0), 1),
            )
        for run in generator.sample(
            _eligible(runs, drafts, _other(team), anchor_clocks), _EXTRA_FOULS[team]
        ):
            run.used = True
            victim = drafts[run.numbers[len(run.numbers) // 2]]
            assert victim.location is not None
            victim.type, victim.outcome, victim.end_location = "foul", "committed", None
            victim.team = team
            victim.player = f"{team}-{generator.randint(2, 11):02d}"
            victim.possession = None
            victim.location = (
                round(100.0 - victim.location[0], 1),
                round(100.0 - victim.location[1], 1),
            )


def _location(point: tuple[float, float]) -> dict[str, float]:
    """Convert a draft coordinate to the contract shape, clamped to the pitch."""
    return {"x": max(0.0, min(100.0, point[0])), "y": max(0.0, min(100.0, point[1]))}


def _to_event(draft: _Draft) -> MatchEvent:
    """Validate one finished draft against the immutable MatchEvent contract."""
    payload: dict[str, object] = {
        "event_id": event_id(draft.number),
        "match_id": MATCH_ID,
        "sequence": draft.number - 1,
        "period": draft.period,
        "match_clock_ms": draft.clock,
        "type": draft.type,
    }
    if draft.type not in ("period_start", "period_end"):
        payload.update(
            {
                "team_id": draft.team,
                "player_id": draft.player,
                "possession_id": draft.possession
                if draft.type not in ("card", "substitution", "foul")
                else None,
                "location": Location.model_validate(_location(draft.location))
                if draft.location
                else None,
                "end_location": Location.model_validate(_location(draft.end_location))
                if draft.end_location
                else None,
                "outcome": draft.outcome,
                "xg": draft.xg,
                "linked_event_id": event_id(draft.linked) if draft.linked else None,
                "related_player_id": draft.related_player,
                "tags": draft.tags,
            }
        )
    return MatchEvent.model_validate(payload)


def generate_canonical_match(seed: int = CANONICAL_SEED) -> tuple[MatchEvent, ...]:
    """Generate the full canonical event log, E-0001 to E-1421, in sequence order."""
    generator = _rng(seed)
    anchors = _anchors()
    ordered = _layout(anchors)
    runs = _assign_runs(ordered, generator)
    by_number = {draft.number: draft for draft in ordered}
    _fill_actions(by_number, runs, generator)
    _place_statistics(by_number, runs, generator)
    return tuple(_to_event(by_number[number]) for number in sorted(by_number))
