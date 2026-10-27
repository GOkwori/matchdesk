"""Build the frontend demo export from the canonical match using registered formulas.

The export is a read-only summary for the synthetic judge demo. Statistics come
from the registered metric formulas or from plain event counts over the same
validated log; nothing is estimated, modelled or approved here.
"""

from __future__ import annotations

import hashlib
from collections import Counter

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_claims import DISPLAY_NAMES, claim_export
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import MatchEvent, MatchWindow, Subject, round_half_up
from matchdesk.domain.moments import detect_moments

EXPORT_SCHEMA = "matchdesk-demo-export/1"
REPLAY_END_MS = canonical.clock_ms(67, 12)
KEY_EVENT_NUMBERS = (561, 688, 790, 841, 1359, 1366, 1402, 1421)
FEED_LENGTH = 15

TEAMS = {
    canonical.HOME: {"name": "Northbridge FC", "short": "Northbridge", "code": "NBR"},
    canonical.AWAY: {"name": "Riverside United", "short": "Riverside", "code": "RIV"},
}


def _windows(from_ms: int, to_ms: int) -> list[MatchWindow]:
    """Split a clock range into period-respecting metric windows."""
    windows = []
    if from_ms < canonical.SECOND_HALF_MS:
        windows.append(
            MatchWindow(period=1, from_ms=from_ms, to_ms=min(to_ms, canonical.SECOND_HALF_MS))
        )
    if to_ms > canonical.SECOND_HALF_MS:
        windows.append(
            MatchWindow(period=2, from_ms=max(from_ms, canonical.SECOND_HALF_MS), to_ms=to_ms)
        )
    return windows


def attributable_ms(events: tuple[MatchEvent, ...], window: MatchWindow) -> dict[str, int]:
    """Return per-team owned time using the possession_time.v1 interval rule.

    The registered formula returns a share only; this exposes the numerator and
    denominator for the evidence panel. Tests assert both agree exactly.
    """
    period_events = [event for event in events if event.period == window.period]
    owned: dict[str, int] = {}
    for current, following in zip(period_events, period_events[1:], strict=False):
        if current.team_id is None:
            continue
        start = max(current.match_clock_ms, window.from_ms)
        end = min(following.match_clock_ms, window.to_ms)
        if end > start:
            owned[current.team_id] = owned.get(current.team_id, 0) + (end - start)
    return owned


def _metric_sum(
    metric_id: str, events: tuple[MatchEvent, ...], team: str, from_ms: int, to_ms: int
) -> float:
    """Sum a count metric over the period windows of a clock range."""
    subject = Subject(team_id=team)
    return sum(
        compute_metric(metric_id, events, subject, window) for window in _windows(from_ms, to_ms)
    )


def _possession(events: tuple[MatchEvent, ...], from_ms: int, to_ms: int) -> dict[str, float | int]:
    """Combine per-period possession_time.v1 shares into one whole-range share."""
    home_ms = 0
    total_ms = 0
    for window in _windows(from_ms, to_ms):
        owned = attributable_ms(events, window)
        window_total = sum(owned.values())
        share = compute_metric(
            "possession_time.v1", events, Subject(team_id=canonical.HOME), window
        )
        home_ms += round(share * window_total)
        total_ms += window_total
    return {
        "home_ms": home_ms,
        "away_ms": total_ms - home_ms,
        "total_ms": total_ms,
        "home_share": round(home_ms / total_ms, 4) if total_ms else 0.0,
    }


def _counts(events: tuple[MatchEvent, ...]) -> dict[str, dict[str, int]]:
    """Return plain event counts per team for statistics without a registered formula."""
    counts: dict[str, Counter[str]] = {canonical.HOME: Counter(), canonical.AWAY: Counter()}
    for event in events:
        if event.team_id is None or event.match_clock_ms >= REPLAY_END_MS:
            continue
        team = counts[event.team_id]
        if event.type == "shot" and event.outcome in ("goal", "saved"):
            team["on_target"] += 1
        if "corner" in event.tags:
            team["corners"] += 1
        if event.type == "foul":
            team["fouls"] += 1
        if event.type == "card" and event.outcome == "yellow":
            team["yellow_cards"] += 1
        if event.type == "card" and event.outcome in ("red", "second_yellow"):
            team["red_cards"] += 1
    return {
        team: {
            key: counter[key]
            for key in ("on_target", "corners", "fouls", "yellow_cards", "red_cards")
        }
        for team, counter in counts.items()
    }


def _quality(events: tuple[MatchEvent, ...], team: str) -> dict[str, float | int]:
    """Whole-match passing and defending figures for one team, from the registered metrics."""
    window = MatchWindow(from_ms=0, to_ms=REPLAY_END_MS)
    subject = Subject(team_id=team)

    def value(metric: str) -> float:
        """One registered metric for the team over the replay."""
        return compute_metric(metric, events, subject, window)

    return {
        "pass_accuracy": float(round_half_up(value("pass_accuracy.v1"), 3)),
        "pass_distance": float(round_half_up(value("pass_distance.v1"), 1)),
        "progressive_passes": int(value("progressive_passes.v1")),
        "pass_difficulty": float(round_half_up(value("pass_difficulty.v1"), 1)),
        "ball_speed": float(round_half_up(value("ball_speed.v1"), 1)),
        "pressured_passes": int(value("pressured_passes.v1")),
        "tackles": int(value("tackles.v1")),
        "interceptions": int(value("interceptions.v1")),
        "recoveries": int(value("recoveries.v1")),
    }


def _event_summary(event: MatchEvent) -> dict[str, object]:
    """Return the small, display-safe subset of one event."""
    summary: dict[str, object] = {
        "id": event.event_id,
        "clock_ms": event.match_clock_ms,
        "period": event.period,
        "type": event.type,
        "team": event.team_id,
        "player": event.player_id,
        "outcome": event.outcome,
        "tags": list(event.tags),
    }
    if event.location is not None:
        summary["x"] = round(event.location.x, 1)
        summary["y"] = round(event.location.y, 1)
    if event.xg is not None:
        summary["xg"] = event.xg
    return summary


def evidence_digest(events: tuple[MatchEvent, ...]) -> str:
    """Return one SHA-256 over the ordered per-event content digests."""
    material = "\n".join(content_digest(event) for event in events).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def build_demo_export(events: tuple[MatchEvent, ...] | None = None) -> dict[str, object]:
    """Build the deterministic export consumed by apps/web/src/studio/data.ts."""
    log = events if events is not None else canonical.generate_canonical_match()
    by_id = {event.event_id: event for event in log}
    statistics: dict[str, dict[str, float | int]] = {}
    counts = _counts(log)
    possession = _possession(log, 0, REPLAY_END_MS)
    for team in (canonical.HOME, canonical.AWAY):
        statistics[team] = {
            "goals": int(_metric_sum("goals.v1", log, team, 0, REPLAY_END_MS)),
            "shots": int(_metric_sum("shots.v1", log, team, 0, REPLAY_END_MS)),
            "final_third_entries": int(
                _metric_sum("final_third_entries.v1", log, team, 0, REPLAY_END_MS)
            ),
            **counts[team],
            **_quality(log, team),
        }
    series = []
    for start in range(0, REPLAY_END_MS, 300_000):
        end = min(start + 300_000, REPLAY_END_MS)
        series.append(
            {
                "from_minute": start // 60_000,
                "to_minute": end // 60_000,
                "home_share": _possession(log, start, end)["home_share"],
            }
        )
    moments = detect_moments(log)
    last = log[-1]
    return {
        "schema": EXPORT_SCHEMA,
        "generator": "matchdesk.domain.canonical_match.generate_canonical_match",
        "seed": canonical.CANONICAL_SEED,
        "synthetic": True,
        "match_id": canonical.MATCH_ID,
        "replay_end_ms": REPLAY_END_MS,
        "event_count": len(log),
        "last_event": {"id": last.event_id, "clock_ms": last.match_clock_ms},
        "evidence_digest": evidence_digest(log),
        "teams": TEAMS,
        "players": canonical.PLAYER_NAMES,
        "squads": {team: list(canonical.squad(team)) for team in (canonical.HOME, canonical.AWAY)},
        "statistics": statistics,
        "possession": possession,
        "possession_series": series,
        "key_events": [
            _event_summary(by_id[canonical.event_id(number)]) for number in KEY_EVENT_NUMBERS
        ],
        "shots": [_event_summary(event) for event in log if event.type == "shot"],
        "feed": [_event_summary(event) for event in log[-FEED_LENGTH:]],
        "claims": claim_export(log),
        "display_names": DISPLAY_NAMES,
        "detected_moments": {
            "total": len(moments),
            "by_kind": dict(sorted(Counter(moment.kind for moment in moments).items())),
            "goals": [
                list(moment.evidence_event_ids) for moment in moments if moment.kind == "goal"
            ],
        },
    }
