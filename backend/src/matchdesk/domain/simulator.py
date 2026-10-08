"""Deterministic synthetic football scenarios for Phase 1A.

The simulator emits existing immutable MatchEvent contracts. Normal scenarios are
stream-valid by construction. The fault scenario keeps every individual event
structurally valid while introducing stream-level defects for later ingestion tests.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Literal

from matchdesk.domain.models import Location, MatchEvent

ScenarioName = Literal[
    "late_winner",
    "momentum_swing",
    "pressing_spell",
    "counter_attack_goal",
    "fault_stream",
]
NormalScenarioName = Literal[
    "late_winner",
    "momentum_swing",
    "pressing_spell",
    "counter_attack_goal",
]
NORMAL_SCENARIOS: tuple[NormalScenarioName, ...] = (
    "late_winner",
    "momentum_swing",
    "pressing_spell",
    "counter_attack_goal",
)


@dataclass(frozen=True)
class SyntheticScenario:
    """Generated scenario plus machine-readable expectations and injected faults."""

    name: ScenarioName
    seed: int
    match_id: str
    events: tuple[MatchEvent, ...]
    expected_facts: tuple[str, ...]
    injected_faults: tuple[str, ...] = ()


def _rng(seed: int, name: str) -> random.Random:
    """Create a stable scenario-specific PRNG without relying on process hash state."""
    material = f"matchdesk-v1:{name}:{seed}".encode("utf-8")
    derived = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    return random.Random(derived)


def _location(generator: random.Random, x: float, y: float, spread: float = 2.0) -> Location:
    """Return a bounded seeded coordinate near an intended tactical location."""
    return Location(
        x=max(0.0, min(100.0, x + generator.uniform(-spread, spread))),
        y=max(0.0, min(100.0, y + generator.uniform(-spread, spread))),
    )


def _event(
    *,
    event_id: str,
    match_id: str,
    sequence: int,
    period: int,
    clock_ms: int,
    event_type: str,
    team_id: str | None = None,
    player_id: str | None = None,
    possession_id: int | None = None,
    location: Location | None = None,
    end_location: Location | None = None,
    outcome: str | None = None,
    under_pressure: bool = False,
    xg: float | None = None,
    linked_event_id: str | None = None,
) -> MatchEvent:
    """Build one existing contract record with explicit, typed scenario fields."""
    return MatchEvent.model_validate(
        {
            "event_id": event_id,
            "match_id": match_id,
            "sequence": sequence,
            "period": period,
            "match_clock_ms": clock_ms,
            "type": event_type,
            "team_id": team_id,
            "player_id": player_id,
            "possession_id": possession_id,
            "location": location,
            "end_location": end_location,
            "outcome": outcome,
            "under_pressure": under_pressure,
            "xg": xg,
            "linked_event_id": linked_event_id,
        }
    )


def _marker(
    event_id: str, match_id: str, sequence: int, period: int, clock_ms: int, kind: str
) -> MatchEvent:
    """Create a period lifecycle marker without player or ball-action fields."""
    return MatchEvent.model_validate(
        {
            "event_id": event_id,
            "match_id": match_id,
            "sequence": sequence,
            "period": period,
            "match_clock_ms": clock_ms,
            "type": kind,
        }
    )


def _kickoff(
    generator: random.Random,
    *,
    event_id: str,
    match_id: str,
    sequence: int,
    period: int,
    clock_ms: int,
    team_id: str,
    player_id: str,
    possession_id: int,
) -> MatchEvent:
    """Create a legal kickoff event close to the centre spot."""
    return _event(
        event_id=event_id,
        match_id=match_id,
        sequence=sequence,
        period=period,
        clock_ms=clock_ms,
        event_type="kickoff",
        team_id=team_id,
        player_id=player_id,
        possession_id=possession_id,
        location=_location(generator, 50.0, 50.0, 0.25),
        outcome="complete",
    )


def _late_winner(seed: int) -> SyntheticScenario:
    """Generate a level match settled by a seeded late second-half goal."""
    generator = _rng(seed, "late_winner")
    match_id = f"late-winner-{seed}"
    events = (
        _marker("lw-p1-start", match_id, 0, 1, 0, "period_start"),
        _kickoff(
            generator,
            event_id="lw-kickoff-1",
            match_id=match_id,
            sequence=1,
            period=1,
            clock_ms=0,
            team_id="home",
            player_id="home-09",
            possession_id=1,
        ),
        _event(
            event_id="lw-shot-home-1",
            match_id=match_id,
            sequence=2,
            period=1,
            clock_ms=1_080_000,
            event_type="shot",
            team_id="home",
            player_id="home-09",
            possession_id=9,
            location=_location(generator, 88.0, 48.0),
            outcome="goal",
            xg=round(generator.uniform(0.28, 0.44), 3),
        ),
        _event(
            event_id="lw-goal-home-1",
            match_id=match_id,
            sequence=3,
            period=1,
            clock_ms=1_080_500,
            event_type="goal",
            team_id="home",
            player_id="home-09",
            possession_id=9,
            location=_location(generator, 88.0, 48.0),
            outcome="goal",
            linked_event_id="lw-shot-home-1",
        ),
        _event(
            event_id="lw-shot-away-1",
            match_id=match_id,
            sequence=4,
            period=1,
            clock_ms=2_220_000,
            event_type="shot",
            team_id="away",
            player_id="away-10",
            possession_id=17,
            location=_location(generator, 86.0, 55.0),
            outcome="goal",
            xg=round(generator.uniform(0.22, 0.38), 3),
        ),
        _event(
            event_id="lw-goal-away-1",
            match_id=match_id,
            sequence=5,
            period=1,
            clock_ms=2_220_500,
            event_type="goal",
            team_id="away",
            player_id="away-10",
            possession_id=17,
            location=_location(generator, 86.0, 55.0),
            outcome="goal",
            linked_event_id="lw-shot-away-1",
        ),
        _marker("lw-p1-end", match_id, 6, 1, 2_820_000, "period_end"),
        _marker("lw-p2-start", match_id, 7, 2, 2_700_000, "period_start"),
        _kickoff(
            generator,
            event_id="lw-kickoff-2",
            match_id=match_id,
            sequence=8,
            period=2,
            clock_ms=2_700_000,
            team_id="away",
            player_id="away-09",
            possession_id=21,
        ),
        _event(
            event_id="lw-pass-home-late",
            match_id=match_id,
            sequence=9,
            period=2,
            clock_ms=5_336_000,
            event_type="pass",
            team_id="home",
            player_id="home-08",
            possession_id=42,
            location=_location(generator, 61.0, 44.0),
            end_location=_location(generator, 82.0, 49.0),
            outcome="complete",
        ),
        _event(
            event_id="lw-shot-home-winner",
            match_id=match_id,
            sequence=10,
            period=2,
            clock_ms=5_344_000,
            event_type="shot",
            team_id="home",
            player_id="home-11",
            possession_id=42,
            location=_location(generator, 89.0, 49.0),
            outcome="goal",
            under_pressure=True,
            xg=round(generator.uniform(0.34, 0.57), 3),
        ),
        _event(
            event_id="lw-goal-home-winner",
            match_id=match_id,
            sequence=11,
            period=2,
            clock_ms=5_344_400,
            event_type="goal",
            team_id="home",
            player_id="home-11",
            possession_id=42,
            location=_location(generator, 89.0, 49.0),
            outcome="goal",
            linked_event_id="lw-shot-home-winner",
        ),
        _marker("lw-p2-end", match_id, 12, 2, 5_580_000, "period_end"),
    )
    return SyntheticScenario(
        name="late_winner",
        seed=seed,
        match_id=match_id,
        events=events,
        expected_facts=("home_wins_2_1", "winning_goal_after_88_minutes"),
    )


def _momentum_swing(seed: int) -> SyntheticScenario:
    """Generate an away lead followed by two quick home goals after half time."""
    generator = _rng(seed, "momentum_swing")
    match_id = f"momentum-swing-{seed}"
    events = [
        _marker("ms-p1-start", match_id, 0, 1, 0, "period_start"),
        _kickoff(
            generator,
            event_id="ms-kickoff-1",
            match_id=match_id,
            sequence=1,
            period=1,
            clock_ms=0,
            team_id="home",
            player_id="home-09",
            possession_id=1,
        ),
        _event(
            event_id="ms-shot-away",
            match_id=match_id,
            sequence=2,
            period=1,
            clock_ms=1_920_000,
            event_type="shot",
            team_id="away",
            player_id="away-07",
            possession_id=12,
            location=_location(generator, 87.0, 42.0),
            outcome="goal",
            xg=round(generator.uniform(0.25, 0.42), 3),
        ),
        _event(
            event_id="ms-goal-away",
            match_id=match_id,
            sequence=3,
            period=1,
            clock_ms=1_920_500,
            event_type="goal",
            team_id="away",
            player_id="away-07",
            possession_id=12,
            location=_location(generator, 87.0, 42.0),
            outcome="goal",
            linked_event_id="ms-shot-away",
        ),
        _marker("ms-p1-end", match_id, 4, 1, 2_820_000, "period_end"),
        _marker("ms-p2-start", match_id, 5, 2, 2_700_000, "period_start"),
    ]
    sequence = 6
    for index, clock_ms in enumerate((3_180_000, 3_420_000), start=1):
        possession = 30 + index
        shot_id = f"ms-shot-home-{index}"
        events.extend(
            [
                _event(
                    event_id=f"ms-recovery-home-{index}",
                    match_id=match_id,
                    sequence=sequence,
                    period=2,
                    clock_ms=clock_ms - 9_000,
                    event_type="recovery",
                    team_id="home",
                    player_id=f"home-0{index + 5}",
                    possession_id=possession,
                    location=_location(generator, 63.0 + index, 48.0),
                    outcome="complete",
                ),
                _event(
                    event_id=shot_id,
                    match_id=match_id,
                    sequence=sequence + 1,
                    period=2,
                    clock_ms=clock_ms,
                    event_type="shot",
                    team_id="home",
                    player_id=f"home-1{index}",
                    possession_id=possession,
                    location=_location(generator, 88.0, 51.0),
                    outcome="goal",
                    xg=round(generator.uniform(0.31, 0.52), 3),
                ),
                _event(
                    event_id=f"ms-goal-home-{index}",
                    match_id=match_id,
                    sequence=sequence + 2,
                    period=2,
                    clock_ms=clock_ms + 400,
                    event_type="goal",
                    team_id="home",
                    player_id=f"home-1{index}",
                    possession_id=possession,
                    location=_location(generator, 88.0, 51.0),
                    outcome="goal",
                    linked_event_id=shot_id,
                ),
            ]
        )
        sequence += 3
    events.append(_marker("ms-p2-end", match_id, sequence, 2, 5_580_000, "period_end"))
    return SyntheticScenario(
        name="momentum_swing",
        seed=seed,
        match_id=match_id,
        events=tuple(events),
        expected_facts=("away_leads_first", "home_scores_twice_within_five_minutes"),
    )


def _pressing_spell(seed: int) -> SyntheticScenario:
    """Generate repeated attacking-half regains followed by a shot."""
    generator = _rng(seed, "pressing_spell")
    match_id = f"pressing-spell-{seed}"
    actions: tuple[tuple[str, str, float], ...] = (
        ("tackle", "won", 61.0),
        ("interception", "complete", 68.0),
        ("recovery", "complete", 72.0),
        ("tackle", "won", 76.0),
    )
    events: list[MatchEvent] = [
        _marker("ps-p1-start", match_id, 0, 1, 0, "period_start"),
        _kickoff(
            generator,
            event_id="ps-kickoff-1",
            match_id=match_id,
            sequence=1,
            period=1,
            clock_ms=0,
            team_id="away",
            player_id="away-09",
            possession_id=1,
        ),
    ]
    sequence = 2
    base_clock = 1_500_000
    for index, (kind, outcome, x) in enumerate(actions, start=1):
        events.append(
            _event(
                event_id=f"ps-action-{index}",
                match_id=match_id,
                sequence=sequence,
                period=1,
                clock_ms=base_clock + index * 11_000,
                event_type=kind,
                team_id="home",
                player_id=f"home-0{index + 3}",
                possession_id=20 + index,
                location=_location(generator, x, 50.0 + index),
                outcome=outcome,
                under_pressure=index % 2 == 0,
            )
        )
        sequence += 1
    events.extend(
        [
            _event(
                event_id="ps-shot-home",
                match_id=match_id,
                sequence=sequence,
                period=1,
                clock_ms=base_clock + 58_000,
                event_type="shot",
                team_id="home",
                player_id="home-09",
                possession_id=24,
                location=_location(generator, 86.0, 52.0),
                outcome="saved",
                xg=round(generator.uniform(0.18, 0.33), 3),
            ),
            _marker("ps-p1-end", match_id, sequence + 1, 1, 2_820_000, "period_end"),
            _marker("ps-p2-start", match_id, sequence + 2, 2, 2_700_000, "period_start"),
            _marker("ps-p2-end", match_id, sequence + 3, 2, 5_580_000, "period_end"),
        ]
    )
    return SyntheticScenario(
        name="pressing_spell",
        seed=seed,
        match_id=match_id,
        events=tuple(events),
        expected_facts=("four_attacking_half_regains_within_one_minute", "spell_ends_in_shot"),
    )


def _counter_attack_goal(seed: int) -> SyntheticScenario:
    """Generate a recovery-to-goal sequence in one possession within fifteen seconds."""
    generator = _rng(seed, "counter_attack_goal")
    match_id = f"counter-attack-{seed}"
    events = (
        _marker("ca-p1-start", match_id, 0, 1, 0, "period_start"),
        _kickoff(
            generator,
            event_id="ca-kickoff-1",
            match_id=match_id,
            sequence=1,
            period=1,
            clock_ms=0,
            team_id="away",
            player_id="away-09",
            possession_id=1,
        ),
        _event(
            event_id="ca-recovery-home",
            match_id=match_id,
            sequence=2,
            period=1,
            clock_ms=2_040_000,
            event_type="recovery",
            team_id="home",
            player_id="home-06",
            possession_id=51,
            location=_location(generator, 28.0, 47.0),
            outcome="complete",
        ),
        _event(
            event_id="ca-pass-home",
            match_id=match_id,
            sequence=3,
            period=1,
            clock_ms=2_044_000,
            event_type="pass",
            team_id="home",
            player_id="home-06",
            possession_id=51,
            location=_location(generator, 35.0, 46.0),
            end_location=_location(generator, 66.0, 51.0),
            outcome="complete",
        ),
        _event(
            event_id="ca-carry-home",
            match_id=match_id,
            sequence=4,
            period=1,
            clock_ms=2_048_500,
            event_type="carry",
            team_id="home",
            player_id="home-10",
            possession_id=51,
            location=_location(generator, 66.0, 51.0),
            end_location=_location(generator, 84.0, 50.0),
            outcome="complete",
            under_pressure=True,
        ),
        _event(
            event_id="ca-shot-home",
            match_id=match_id,
            sequence=5,
            period=1,
            clock_ms=2_052_000,
            event_type="shot",
            team_id="home",
            player_id="home-10",
            possession_id=51,
            location=_location(generator, 88.0, 50.0),
            outcome="goal",
            under_pressure=True,
            xg=round(generator.uniform(0.36, 0.59), 3),
        ),
        _event(
            event_id="ca-goal-home",
            match_id=match_id,
            sequence=6,
            period=1,
            clock_ms=2_052_400,
            event_type="goal",
            team_id="home",
            player_id="home-10",
            possession_id=51,
            location=_location(generator, 88.0, 50.0),
            outcome="goal",
            linked_event_id="ca-shot-home",
        ),
        _marker("ca-p1-end", match_id, 7, 1, 2_820_000, "period_end"),
        _marker("ca-p2-start", match_id, 8, 2, 2_700_000, "period_start"),
        _marker("ca-p2-end", match_id, 9, 2, 5_580_000, "period_end"),
    )
    return SyntheticScenario(
        name="counter_attack_goal",
        seed=seed,
        match_id=match_id,
        events=events,
        expected_facts=("recovery_to_goal_under_15_seconds", "single_possession_counter"),
    )


def _fault_stream(seed: int) -> SyntheticScenario:
    """Derive a structurally valid stream containing four explicit ingestion faults."""
    base = _counter_attack_goal(seed)
    events = list(base.events)
    duplicate = events[3]
    events.insert(4, duplicate)
    events[5], events[6] = events[6], events[5]
    events = [event for event in events if event.sequence != 7]
    reset = _marker(
        "fault-replay-reset",
        base.match_id,
        0,
        1,
        0,
        "period_start",
    )
    events.append(reset)
    return SyntheticScenario(
        name="fault_stream",
        seed=seed,
        match_id=base.match_id,
        events=tuple(events),
        expected_facts=(),
        injected_faults=(
            "duplicate_event",
            "out_of_order_sequence",
            "sequence_gap",
            "replay_reset_signal",
        ),
    )


def generate_scenario(name: ScenarioName, seed: int) -> SyntheticScenario:
    """Generate one deterministic normal or fault scenario for a nonnegative seed."""
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    generators = {
        "late_winner": _late_winner,
        "momentum_swing": _momentum_swing,
        "pressing_spell": _pressing_spell,
        "counter_attack_goal": _counter_attack_goal,
        "fault_stream": _fault_stream,
    }
    return generators[name](seed)


def scenario_bytes(scenario: SyntheticScenario) -> bytes:
    """Encode generated scenario content into stable compact UTF-8 JSON bytes."""
    payload = {
        "name": scenario.name,
        "seed": scenario.seed,
        "match_id": scenario.match_id,
        "expected_facts": list(scenario.expected_facts),
        "injected_faults": list(scenario.injected_faults),
        "events": [event.model_dump(mode="json") for event in scenario.events],
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
