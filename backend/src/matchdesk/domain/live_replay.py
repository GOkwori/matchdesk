"""A paced replay of the synthetic match, ingested, reduced and verified as it arrives.

Events leave in sequence at the requested speed. Each one goes through the same ordered,
idempotent ingestor and football-state reducer as any feed, and the running score comes from
the reducer. When an overlay cue's time window has closed, its claims are verified against
only the events that have arrived so far, so a cue is never shown on the strength of events
that have not happened yet. Cards and substitutions have no registered query and are sent as
logged. The half-time recap goes out once the first half has arrived, and the recap at the
replay point at the end, each verified the same way.

The match is synthetic and the replay is a recording played back, not a live feed; the
stream says so in its first message.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import lru_cache
from typing import Any

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_claims import DISPLAY_NAMES, REPLAY_END_MS
from matchdesk.domain.ingestion import ReplayIngestor
from matchdesk.domain.models import Claim, EvidenceRecord, MatchEvent, MatchWindow
from matchdesk.domain.overlay_feed import build_overlay_feed
from matchdesk.domain.recap_feed import build_recap_feed
from matchdesk.domain.reducer import MatchReducer
from matchdesk.domain.verification import verify_claim

SPEEDS = (1, 10, 30, 60)
MAX_GAP_SECONDS = 3.0
MAX_STREAM_SECONDS = 900.0

Sleep = Callable[[float], Awaitable[None]]


@lru_cache(maxsize=1)
def _log() -> tuple[MatchEvent, ...]:
    """The canonical log, up to the replay point."""
    return tuple(
        event
        for event in canonical.generate_canonical_match()
        if event.match_clock_ms < REPLAY_END_MS
    )


def _due(t_ms: int, bound: list[Claim]) -> int:
    """When every claim's window has closed and, for possession, the next event has arrived."""
    windows = [c.assertion.window.to_ms for c in bound if c.assertion is not None]
    due = max([t_ms, *windows])
    if any(c.assertion is not None and c.assertion.metric == "possession_time.v1" for c in bound):
        # Time on the ball runs until the next event, so possession waits for it.
        following = next((e.match_clock_ms for e in _log() if e.match_clock_ms >= due), due)
        due = following + 1
    return due


@lru_cache(maxsize=1)
def _cues() -> tuple[tuple[int, dict[str, Any], tuple[Claim, ...]], ...]:
    """Each overlay cue and recap with the time its claims can first be checked, and the claims."""
    feed = build_overlay_feed()
    recaps = build_recap_feed()
    claims = {
        record["claim_id"]: Claim.model_validate(record["claim"])
        for record in (*feed["claims"], *recaps["claims"])
    }
    out = []
    for recap in recaps["recaps"]:
        ids = [claim_id for check in recap["checks"] for claim_id in check["claim_ids"]]
        ids += [claim_id for m in recap["milestones"] for claim_id in m["claim_ids"]]
        bound = [claims[claim_id] for claim_id in dict.fromkeys(ids)]
        item = {"recap_id": recap["id"], "t_ms": recap["t_ms"]}
        out.append((min(_due(recap["t_ms"], bound), REPLAY_END_MS + 1), item, tuple(bound)))
    for cue in feed["cues"]:
        bound = [claims[claim_id] for claim_id in cue["claim_ids"]]
        out.append((_due(cue["t_ms"], bound), cue, tuple(bound)))
    return tuple(
        sorted(out, key=lambda item: (item[0], item[1].get("cue_id") or item[1]["recap_id"]))
    )


def _event_payload(event: MatchEvent) -> dict[str, Any]:
    """The fields the studio's metrics and pitch read, in the compact form it already uses."""
    return {
        "id": event.event_id,
        "seq": event.sequence,
        "period": event.period,
        "ms": event.match_clock_ms,
        "type": event.type,
        "team": event.team_id,
        "player": event.player_id,
        "outcome": event.outcome,
        "xg": event.xg,
        "x": event.location.x if event.location else None,
        "y": event.location.y if event.location else None,
        "end_x": event.end_location.x if event.end_location else None,
        "end_y": event.end_location.y if event.end_location else None,
        "pressure": 1 if event.under_pressure else 0,
        "tags": list(event.tags),
    }


class _Session:
    """One listener's ingestor, reducer and the cues already sent."""

    def __init__(self) -> None:
        """Start from an empty replay."""
        self.ingestor = ReplayIngestor(canonical.MATCH_ID)
        self.reducer = MatchReducer(canonical.MATCH_ID, canonical.rosters())
        self.accepted: list[MatchEvent] = []
        self.next_cue = 0

    def take(self, event: MatchEvent) -> dict[str, int]:
        """Ingest and reduce one arrival; return the reducer's score."""
        decision = self.ingestor.ingest(event)
        if decision.status != "accepted":  # the canonical log arrives in order, once
            raise RuntimeError(f"replay event {event.event_id} was {decision.status}")
        state = self.reducer.apply(event)
        self.accepted.append(event)
        return {team: int(score) for team, score in state.scores.items()}

    def next_due(self) -> int | None:
        """When the next cue's windows close, if any cue is left."""
        cues = _cues()
        return cues[self.next_cue][0] if self.next_cue < len(cues) else None

    def due_cues(self, now_ms: int) -> list[dict[str, Any]]:
        """Cues whose windows have closed, verified against the events received so far."""
        ready = []
        cues = _cues()
        while self.next_cue < len(cues) and cues[self.next_cue][0] <= now_ms:
            due, cue, claims = cues[self.next_cue]
            self.next_cue += 1
            results = []
            if claims:
                evidence = EvidenceRecord(
                    evidence_id="EV-LIVE",
                    match_id=canonical.MATCH_ID,
                    replay_id=self.ingestor.replay_id,
                    revision=1,
                    window=MatchWindow(from_ms=0, to_ms=now_ms),
                    event_ids=tuple(event.event_id for event in self.accepted),
                    engine_version="matchdesk-live-replay-1",
                    source_digest="0" * 64,
                )
                events = tuple(self.accepted)
                for claim in claims:
                    result = verify_claim(claim, evidence, events, names=DISPLAY_NAMES)
                    results.append(
                        {
                            "claim_id": claim.claim_id,
                            "status": result.status,
                            "reason": result.reason,
                        }
                    )
            verified = bool(results) and all(r["status"] == "verified" for r in results)
            status = "logged" if not claims else "verified" if verified else "failed"
            label = (
                {"recap_id": cue["recap_id"]} if "recap_id" in cue else {"cue_id": cue["cue_id"]}
            )
            ready.append(
                {
                    **label,
                    "t_ms": cue["t_ms"],
                    "checked_at_ms": now_ms,
                    "events_received": len(self.accepted),
                    "status": status,
                    "claims": results,
                }
            )
        return ready


async def _wait(sleep: Sleep, match_ms: int, speed: int) -> None:
    """Pause for a stretch of match time at the replay speed, never long enough to stall."""
    if match_ms > 0:
        await sleep(min(match_ms / 1000 / speed, MAX_GAP_SECONDS))


def _frame(kind: str, data: dict[str, Any]) -> str:
    """One server-sent event."""
    return f"event: {kind}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def live_replay(
    speed: int,
    from_ms: int = 0,
    *,
    sleep: Sleep,
    elapsed: Callable[[], float],
) -> AsyncIterator[str]:
    """Stream the replay from ``from_ms`` at ``speed`` times real time, as server-sent events."""
    if speed not in SPEEDS:
        raise ValueError(f"speed must be one of {SPEEDS}")
    if not 0 <= from_ms < REPLAY_END_MS:
        raise ValueError("from_ms must be inside the replay")
    session = _Session()
    log = _log()
    start = 0
    score: dict[str, int] = {}
    while start < len(log) and log[start].match_clock_ms < from_ms:
        score = session.take(log[start])
        start += 1
    # Cues before the starting point are not replayed.
    session.due_cues(from_ms)
    yield _frame(
        "hello",
        {
            "match_id": canonical.MATCH_ID,
            "synthetic": True,
            "source": "recorded synthetic log, played back",
            "speed": speed,
            "from_ms": from_ms,
            "replay_end_ms": REPLAY_END_MS,
            "events_received": len(session.accepted),
            "score": score or {canonical.HOME: 0, canonical.AWAY: 0},
        },
    )
    previous_ms = from_ms
    for event in log[start:]:
        if elapsed() > MAX_STREAM_SECONDS:
            yield _frame("end", {"reason": "time_limit", "resume_from_ms": previous_ms})
            return
        # A cue goes out the moment its window closes, even in a gap between events.
        due = session.next_due()
        while due is not None and due <= event.match_clock_ms:
            await _wait(sleep, due - previous_ms, speed)
            previous_ms = max(previous_ms, due)
            for cue in session.due_cues(due):
                yield _frame("recap" if "recap_id" in cue else "cue", cue)
            due = session.next_due()
        await _wait(sleep, event.match_clock_ms - previous_ms, speed)
        score = session.take(event)
        previous_ms = event.match_clock_ms
        yield _frame("event", {**_event_payload(event), "score": score})
        for cue in session.due_cues(event.match_clock_ms + 1):
            yield _frame("recap" if "recap_id" in cue else "cue", cue)
    for cue in session.due_cues(REPLAY_END_MS + 1):
        yield _frame("recap" if "recap_id" in cue else "cue", cue)
    yield _frame("end", {"reason": "replay_point", "events_received": len(session.accepted)})
