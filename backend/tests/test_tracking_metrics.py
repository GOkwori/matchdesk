"""Synthetic tracking: shot speed, player speed and distance, and the metrics that read them."""

from __future__ import annotations

import pytest
from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.metrics import METRIC_DEFINITIONS, SPRINT_KMH, compute_metric
from matchdesk.domain.models import MatchEvent, MatchWindow, Subject

LOG = canonical.generate_canonical_match()
WHOLE = MatchWindow(from_ms=0, to_ms=4_032_000)


def _strip(event: MatchEvent) -> dict[str, object]:
    """An event without its tracking fields."""
    return event.model_dump(exclude={"shot_speed_kmh", "player_speed_kmh", "distance_m"})


def test_tracking_is_added_without_moving_any_event() -> None:
    """Same ids, clocks, locations, outcomes and tags; only the three tracking fields are new."""
    assert len(LOG) == 1421
    assert canonical.generate_canonical_match() == LOG
    shots = [e for e in LOG if e.type == "shot"]
    assert shots and all(e.shot_speed_kmh is not None for e in shots)
    assert all(e.shot_speed_kmh is None for e in LOG if e.type != "shot")
    for event in LOG:
        if event.player_id is None or event.type in ("card", "substitution", "goal"):
            assert event.player_speed_kmh is None and event.distance_m is None
        else:
            assert event.player_speed_kmh is not None and event.distance_m is not None


def test_physical_values_are_football_realistic() -> None:
    """Headers slower than strikes, top speeds under 36 km/h, 7-8.5 km for the busiest at 67′."""
    header = next(e for e in LOG if e.type == "shot" and "header" in e.tags)
    assert header.shot_speed_kmh is not None and header.shot_speed_kmh < 65
    assert all(
        e.shot_speed_kmh is not None and 60 <= e.shot_speed_kmh <= 125
        for e in LOG
        if e.type == "shot" and "header" not in e.tags
    )
    assert max(e.player_speed_kmh or 0 for e in LOG) <= 35.4
    players = {e.player_id for e in LOG if e.player_id}
    km = sorted(
        compute_metric("distance_covered.v1", LOG, Subject(player_id=p), WHOLE) for p in players
    )
    assert 7.0 <= km[-1] <= 8.5


@pytest.mark.parametrize(
    ("metric", "unit"),
    [
        ("shot_speed.v1", "km_per_hour"),
        ("top_speed.v1", "km_per_hour"),
        ("distance_covered.v1", "kilometres"),
        ("sprints.v1", "count"),
    ],
)
def test_the_tracking_metrics_are_registered(metric: str, unit: str) -> None:
    """Four new metrics, eighteen in all."""
    assert METRIC_DEFINITIONS[metric].unit == unit
    assert len(METRIC_DEFINITIONS) == 18


def test_each_formula_reads_its_field() -> None:
    """Mean shot speed, top speed, kilometres and sprints, recomputed by hand."""
    okafor = Subject(player_id="nbr-09")
    mine = [e for e in LOG if e.player_id == "nbr-09" and e.match_clock_ms < WHOLE.to_ms]
    shots = [e.shot_speed_kmh for e in mine if e.type == "shot" and e.shot_speed_kmh is not None]
    assert compute_metric("shot_speed.v1", LOG, okafor, WHOLE) == pytest.approx(
        sum(shots) / len(shots)
    )
    speeds = [e.player_speed_kmh for e in mine if e.player_speed_kmh is not None]
    assert compute_metric("top_speed.v1", LOG, okafor, WHOLE) == max(speeds)
    metres = sum(e.distance_m for e in mine if e.distance_m is not None)
    assert compute_metric("distance_covered.v1", LOG, okafor, WHOLE) == pytest.approx(metres / 1000)
    assert compute_metric("sprints.v1", LOG, okafor, WHOLE) == sum(s >= SPRINT_KMH for s in speeds)
    nobody = Subject(player_id="nbr-16")
    assert compute_metric("top_speed.v1", LOG, nobody, WHOLE) == 0.0
    assert compute_metric("shot_speed.v1", LOG, Subject(player_id="nbr-01"), WHOLE) == 0.0


def test_only_shots_carry_a_shot_speed_and_markers_carry_nothing() -> None:
    """The contract rejects tracking in the wrong place."""
    shot = next(e for e in LOG if e.type == "shot")
    payload = shot.model_dump()
    pass_event = next(e for e in LOG if e.type == "pass").model_dump()
    with pytest.raises(ValueError, match="Only shot events carry a shot speed"):
        MatchEvent.model_validate({**pass_event, "shot_speed_kmh": 80.0})
    marker = next(e for e in LOG if e.type == "period_end").model_dump()
    with pytest.raises(ValueError, match="Period markers"):
        MatchEvent.model_validate({**marker, "distance_m": 10.0})
    with pytest.raises(ValueError):
        MatchEvent.model_validate({**payload, "player_speed_kmh": 60.0})
    assert _strip(MatchEvent.model_validate(payload)) == _strip(shot)
