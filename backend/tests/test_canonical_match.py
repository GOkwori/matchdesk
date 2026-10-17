"""Canonical demo match: contract validity, scripted facts and export freshness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_export import (
    REPLAY_END_MS,
    attributable_ms,
    build_demo_export,
    evidence_digest,
)
from matchdesk.domain.ingestion import ReplayIngestor
from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import MatchWindow, Subject
from matchdesk.domain.reducer import MatchReducer

ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / "apps/web/src/studio/generated/nbr-riv.json"


@pytest.fixture(scope="module")
def events():
    """Generate the canonical log once for the module."""
    return canonical.generate_canonical_match()


def test_generation_is_deterministic(events) -> None:
    """The same seed must reproduce byte-identical evidence."""
    assert evidence_digest(events) == evidence_digest(canonical.generate_canonical_match())
    assert evidence_digest(events) != evidence_digest(canonical.generate_canonical_match(seed=5))


def test_identities_and_sequence_are_contiguous(events) -> None:
    """E-0001..E-1421 map one-to-one onto sequences 0..1420."""
    assert len(events) == canonical.LAST_EVENT_NUMBER
    for index, event in enumerate(events):
        assert event.sequence == index
        assert event.event_id == canonical.event_id(index + 1)
        assert event.match_id == canonical.MATCH_ID
        assert event.synthetic is True


def test_stream_passes_ingestion_and_reduction(events) -> None:
    """Every event is accepted in order and the reducer derives a 2-1 score."""
    ingestor = ReplayIngestor(canonical.MATCH_ID)
    reducer = MatchReducer(canonical.MATCH_ID, canonical.rosters())
    for event in events:
        assert ingestor.ingest(event).status == "accepted"
        state = reducer.apply(event)
    assert dict(state.scores) == {canonical.HOME: 2, canonical.AWAY: 1}
    assert "riv-14" in state.active_players[canonical.AWAY]
    assert "riv-07" not in state.active_players[canonical.AWAY]
    assert ingestor.snapshot().missing_sequences == ()


@pytest.mark.parametrize(
    ("number", "clock", "kind", "team", "player"),
    [
        (561, canonical.clock_ms(27, 40), "card", "riv", "riv-06"),
        (688, canonical.clock_ms(34, 18), "goal", "nbr", "nbr-09"),
        (790, canonical.clock_ms(41, 3), "goal", "riv", "riv-11"),
        (841, canonical.SECOND_HALF_MS, "period_end", None, None),
        (1359, canonical.clock_ms(58, 3), "pass", "nbr", "nbr-07"),
        (1366, canonical.clock_ms(58, 17), "goal", "nbr", "nbr-09"),
        (1402, canonical.clock_ms(63, 4), "card", "nbr", "nbr-04"),
        (1421, canonical.clock_ms(67, 8), "substitution", "riv", "riv-07"),
    ],
)
def test_scripted_key_events(events, number, clock, kind, team, player) -> None:
    """Key moments keep the exact identities and clocks used across the product."""
    event = events[number - 1]
    assert (event.match_clock_ms, event.type, event.team_id, event.player_id) == (
        clock,
        kind,
        team,
        player,
    )


def test_corner_header_link(events) -> None:
    """The 58:17 header is linked to its goal-valued shot, 14 seconds after the corner."""
    corner, shot, goal = events[1358], events[1364], events[1365]
    assert "corner" in corner.tags and "header" in shot.tags
    assert goal.linked_event_id == shot.event_id and shot.outcome == "goal"
    assert goal.match_clock_ms - corner.match_clock_ms == 14_000


def test_attributable_time_agrees_with_registered_formula(events) -> None:
    """The exported numerator/denominator reproduce possession_time.v1 exactly."""
    for window in (
        MatchWindow(period=1, from_ms=0, to_ms=canonical.SECOND_HALF_MS),
        MatchWindow(period=2, from_ms=canonical.SECOND_HALF_MS, to_ms=REPLAY_END_MS),
    ):
        owned = attributable_ms(events, window)
        share = compute_metric("possession_time.v1", events, Subject(team_id="nbr"), window)
        assert share == pytest.approx(owned["nbr"] / sum(owned.values()))


def test_export_matches_scripted_totals(events) -> None:
    """The export carries the design-brief totals computed from the log."""
    data = build_demo_export(events)
    stats = data["statistics"]
    assert isinstance(stats, dict)
    for team, expected in {
        "nbr": {
            "goals": 2,
            "shots": 14,
            "on_target": 6,
            "corners": 6,
            "fouls": 8,
            "yellow_cards": 1,
            "red_cards": 0,
        },
        "riv": {
            "goals": 1,
            "shots": 9,
            "on_target": 3,
            "corners": 3,
            "fouls": 11,
            "yellow_cards": 1,
            "red_cards": 0,
        },
    }.items():
        assert {key: stats[team][key] for key in expected} == expected
    possession = data["possession"]
    assert isinstance(possession, dict)
    assert 0.575 <= possession["home_share"] <= 0.585
    assert possession["home_ms"] + possession["away_ms"] == possession["total_ms"]
    assert data["event_count"] == 1421
    assert data["last_event"] == {"id": "E-1421", "clock_ms": canonical.clock_ms(67, 8)}
    moments = data["detected_moments"]
    assert isinstance(moments, dict)
    assert moments["goals"] == [["E-0688"], ["E-0790"], ["E-1366"]]


def test_committed_export_is_current() -> None:
    """The JSON shipped to the frontend must equal a fresh deterministic export."""
    expected = json.dumps(build_demo_export(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert EXPORT.read_text(encoding="utf-8") == expected
