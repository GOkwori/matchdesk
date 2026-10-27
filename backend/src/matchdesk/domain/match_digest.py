"""A compact, deterministic digest of a match for specialist agents.

A live specialist receives at most 16,000 characters of context, so the 1,421-event
canonical log cannot be sent whole. The digest carries what a specialist needs to
start (score, key events, detected moments, registered metric values) and the agent
fetches anything else through its role-scoped read tools. Every number in it comes
from a registered formula or a plain count over accepted events.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import MatchEvent, MatchWindow, Subject
from matchdesk.domain.moments import detect_moments

DIGEST_SCHEMA = "matchdesk-match-digest/1"
MAX_DIGEST_CHARS = 8_000
_KEY_TYPES = frozenset({"goal", "card", "substitution"})
_SET_PIECE_LOOKBACK_MS = 30_000


def clock_text(ms: int) -> str:
    """Display clock, mm:ss, as the studio shows it."""
    seconds = ms // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _key_events(events: tuple[MatchEvent, ...], names: Mapping[str, str]) -> list[dict[str, Any]]:
    """Goals, cards and substitutions, plus any tagged set piece shortly before a goal."""
    goal_ms = [event.match_clock_ms for event in events if event.type == "goal"]
    selected = []
    for event in events:
        set_piece_before_goal = bool(event.tags) and any(
            0 < ms - event.match_clock_ms <= _SET_PIECE_LOOKBACK_MS for ms in goal_ms
        )
        if event.type not in _KEY_TYPES and not set_piece_before_goal:
            continue
        row: dict[str, Any] = {
            "event_id": event.event_id,
            "clock": clock_text(event.match_clock_ms),
            "type": event.type,
            "team_id": event.team_id,
            "player_id": event.player_id,
        }
        if event.player_id is not None and event.player_id in names:
            row["player"] = names[event.player_id]
        if event.outcome is not None:
            row["outcome"] = event.outcome
        if event.tags:
            row["tags"] = list(event.tags)
        selected.append(row)
    return selected


def build_match_digest(
    events: tuple[MatchEvent, ...],
    names: Mapping[str, str],
    *,
    to_ms: int,
) -> dict[str, Any]:
    """Return the digest of accepted events up to a replay point."""
    played = tuple(event for event in events if event.match_clock_ms < to_ms)
    if not played:
        raise ValueError("A digest needs at least one accepted event before the replay point")
    teams = sorted({event.team_id for event in played if event.team_id is not None})
    whole = MatchWindow(from_ms=0, to_ms=to_ms)

    def metric(metric_id: str, team: str) -> float:
        """One registered metric for one team over the whole match so far."""
        return compute_metric(metric_id, played, Subject(team_id=team), whole)

    digest = {
        "schema": DIGEST_SCHEMA,
        "match_id": played[0].match_id,
        "replay_clock": clock_text(to_ms),
        "event_count": len(played),
        "teams": {team: names.get(team, team) for team in teams},
        "score": {team: int(metric("goals.v1", team)) for team in teams},
        "metrics_whole_match": {
            team: {
                "goals.v1": int(metric("goals.v1", team)),
                "shots.v1": int(metric("shots.v1", team)),
                "possession_time.v1": round(metric("possession_time.v1", team), 4),
                "pass_accuracy.v1": round(metric("pass_accuracy.v1", team), 4),
                "final_third_entries.v1": int(metric("final_third_entries.v1", team)),
            }
            for team in teams
        },
        "key_events": _key_events(played, names),
        "detected_moments": [
            {
                "moment_id": moment.moment_id,
                "kind": moment.kind,
                "team_id": moment.team_id,
                "clock": clock_text(moment.start_ms),
                "event_ids": list(moment.evidence_event_ids),
            }
            for moment in detect_moments(played)
        ],
        "registered_metrics": [
            "goals.v1",
            "shots.v1",
            "possession_time.v1",
            "pass_accuracy.v1",
            "final_third_entries.v1",
            "synthetic_xg.v1",
        ],
        "registered_event_facts": ["goal_scorer.v1", "sequence_gap.v1"],
    }
    if len(digest_json(digest)) > MAX_DIGEST_CHARS:
        raise ValueError("Match digest exceeds its bounded size")
    return digest


def digest_json(digest: Mapping[str, Any]) -> str:
    """Canonical compact JSON, as sent to a specialist."""
    return json.dumps(digest, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
