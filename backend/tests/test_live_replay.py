"""The live replay: ordered through the ingestor and reducer, cues verified on arrival."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from matchdesk.api.app import create_app
from matchdesk.api.live_routes import create_live_router, live_router_from_env
from matchdesk.domain.live_replay import live_replay


async def _no_sleep(seconds: float) -> None:
    """Skip pacing in tests."""


def _frames(speed: int = 60, from_ms: int = 0, **kw: Any) -> list[tuple[str, dict[str, Any]]]:
    """Run the replay to the end and parse every frame."""

    async def collect() -> list[str]:
        """Every frame, in order."""
        return [
            frame
            async for frame in live_replay(
                speed,
                from_ms,
                sleep=kw.get("sleep", _no_sleep),
                elapsed=kw.get("elapsed", lambda: 0.0),
            )
        ]

    out = []
    for frame in asyncio.run(collect()):
        head, data = frame.strip().split("\n", 1)
        out.append((head.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def test_every_event_arrives_once_in_order_and_the_reducer_keeps_score() -> None:
    """1,421 events in sequence; the final score is the reducer's 2–1."""
    frames = _frames()
    assert frames[0][0] == "hello" and frames[0][1]["synthetic"] is True
    events = [data for kind, data in frames if kind == "event"]
    assert len(events) == 1421
    assert [e["seq"] for e in events] == sorted(e["seq"] for e in events)
    assert events[-1]["score"] == {"nbr": 2, "riv": 1}
    assert frames[-1] == ("end", {"reason": "replay_point", "events_received": 1421})


def test_cues_are_verified_only_on_events_that_have_arrived() -> None:
    """Every numeric cue passes, checked after its window closed and before later events."""
    frames = _frames()
    received = 0
    cues = []
    for kind, data in frames:
        if kind == "event":
            received += 1
        if kind == "cue":
            assert data["events_received"] == received
            assert data["checked_at_ms"] >= data["t_ms"]
            cues.append(data)
    assert len(cues) == 13
    assert {c["status"] for c in cues} == {"verified", "logged"}
    goal = next(c for c in cues if c["cue_id"] == "Q-008")
    assert goal["checked_at_ms"] == 3_498_000
    assert [r["status"] for r in goal["claims"]] == ["verified"] * 3


def test_starting_mid_match_fast_forwards_without_replaying_old_cues() -> None:
    """From 41:40 the score is already 1–1 and only later cues are sent."""
    frames = _frames(from_ms=2_500_000)
    assert frames[0][1]["score"] == {"nbr": 1, "riv": 1}
    cue_ids = [data["cue_id"] for kind, data in frames if kind == "cue"]
    assert cue_ids[0] == "Q-006" and "Q-004" not in cue_ids


def test_pacing_follows_the_speed_and_never_stalls() -> None:
    """Waits are match time over speed, capped at three seconds."""
    waits: list[float] = []

    async def record(seconds: float) -> None:
        """Keep the wait instead of sleeping."""
        waits.append(seconds)

    _frames(speed=1, sleep=record)
    assert max(waits) <= 3.0 and min(waits) > 0
    total = sum(_waits_at(10))
    assert 200 < total < 420  # about 67 minutes at 10x, with long gaps capped


def _waits_at(speed: int) -> list[float]:
    """The waits a whole replay asks for at one speed."""
    waits: list[float] = []

    async def record(seconds: float) -> None:
        """Keep the wait instead of sleeping."""
        waits.append(seconds)

    _frames(speed=speed, sleep=record)
    return waits


def test_a_stream_stops_at_its_time_limit_with_a_resume_point() -> None:
    """Long listens end cleanly and say where to pick up."""
    ticks = iter(range(10_000))
    frames = _frames(speed=1, elapsed=lambda: next(ticks) * 10.0)
    kind, data = frames[-1]
    assert kind == "end" and data["reason"] == "time_limit" and data["resume_from_ms"] > 0


def test_bad_arguments_are_refused() -> None:
    """Only the listed speeds and points inside the replay."""
    with pytest.raises(ValueError):
        _frames(speed=7)
    with pytest.raises(ValueError):
        _frames(from_ms=5_000_000)


def test_the_route_streams_and_caps_listeners(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off by default; when on it streams server-sent events and refuses extra listeners."""
    monkeypatch.delenv("MATCHDESK_LIVE_REPLAY_ENABLED", raising=False)
    assert live_router_from_env() is None
    monkeypatch.setenv("MATCHDESK_LIVE_REPLAY_ENABLED", "true")
    assert live_router_from_env() is not None
    import matchdesk.domain.live_replay as module

    monkeypatch.setattr(module, "MAX_GAP_SECONDS", 0.0)
    client = TestClient(create_app(assistant_router=create_live_router()))
    with client.stream("GET", "/api/live/stream?speed=60&from_ms=4000000") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache, no-transform"
        body = "".join(response.iter_text())
    assert body.startswith("event: hello") and body.rstrip().endswith('"events_received":1421}')
    assert client.get("/api/live/stream?speed=7").status_code == 422
    assert client.get("/api/live/stream?from_ms=-1").status_code == 422
    full = TestClient(create_app(assistant_router=create_live_router(limit=0)))
    assert full.get("/api/live/stream").status_code == 429
