"""Render the synthetic match as a top-down video, and keep the truth of what is in it.

The canonical event log has no continuous ball path, so the renderer builds one: at each
on-ball event the ball is at the event's location, and it travels to the next event's
location at a seeded, football-realistic speed (passes and clearances fast, carries slow,
shots at the log's synthetic shot speed towards the goal line), then waits for the next
touch. A ring in the team's colour marks the player touching the ball for a moment after
each touch. Frames carry sensor-like noise and the ball is occasionally hidden, so the
detector has real work to do.

Only the renderer sees the log. It also returns the ground truth the lab scores against:
every point where the ball changes course, whether that point is a logged event, the true
segment lengths and speeds, and the team in possession.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.models import MatchEvent

FPS = 25
PX_PER_M = 6
PITCH_W, PITCH_H = 105.0, 68.0
# A margin round the pitch, so a ball in the net or over the line stays in shot.
MARGIN = 3.0
WIDTH, HEIGHT = int((PITCH_W + 2 * MARGIN) * PX_PER_M), int((PITCH_H + 2 * MARGIN) * PX_PER_M)
BALL = (255, 252, 236)
TEAM_RGB = {canonical.HOME: (255, 122, 61), canonical.AWAY: (224, 69, 58)}
GRASS = (34, 92, 54)
LINES = (150, 190, 160)
ON_BALL = {"kickoff", "pass", "carry", "dribble", "recovery", "clearance", "shot", "foul"}
RING_SECONDS = 0.32
POSTS = (30.34, 37.66)


def absolute(event: MatchEvent, x: float, y: float) -> tuple[float, float]:
    """Metres on a pitch where Northbridge attack to the right; event coordinates are per team."""
    if event.team_id == canonical.AWAY:
        x, y = 100.0 - x, 100.0 - y
    return x / 100.0 * PITCH_W, y / 100.0 * PITCH_H


@dataclass
class Segment:
    """The ball moving in a straight line (or resting, when start equals end)."""

    t0: float
    t1: float
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass
class TrueTouch:
    """A point where the ball starts moving or changes course, as the renderer drew it."""

    t: float
    at: tuple[float, float]
    team: str | None
    event_id: str | None  # None for a movement the log does not record (a save, a rebound)
    event_type: str | None
    length_m: float
    speed_ms: float
    shot_speed_kmh: float | None = None


@dataclass
class Truth:
    """What the video shows, for scoring."""

    touches: list[TrueTouch]
    segments: list[Segment]
    rings: list[tuple[float, float, str]]  # (from, to, team)
    cuts: list[float]


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Metres between two points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def build_truth(log: tuple[MatchEvent, ...], seed: int = 20261023) -> Truth:
    """The ball's path and every touch in it, from the log, deterministically."""
    rng = random.Random(seed)
    events = [e for e in log if e.type in ON_BALL and e.location is not None]
    touches: list[TrueTouch] = []
    segments: list[Segment] = []
    rings: list[tuple[float, float, str]] = []
    cuts: list[float] = []
    for index, event in enumerate(events):
        assert event.location is not None
        t0 = event.match_clock_ms / 1000.0
        here = absolute(event, event.location.x, event.location.y)
        following = events[index + 1] if index + 1 < len(events) else None
        if following is None or following.period != event.period:
            segments.append(Segment(t0, t0 + 2.0, here, here))
            continue
        assert following.location is not None
        t1 = following.match_clock_ms / 1000.0
        there = absolute(following, following.location.x, following.location.y)
        if event.team_id:
            rings.append((t0, t0 + RING_SECONDS, event.team_id))
        if event.type == "shot":
            # Towards the goal line: inside the posts if on target, wide if not; blocked short.
            attacking_right = event.team_id == canonical.HOME
            goal_x = (
                PITCH_W + (1.2 if event.outcome == "goal" else 0.0)
                if attacking_right
                else (-1.2 if event.outcome == "goal" else 0.0)
            )
            if event.outcome in ("goal", "saved"):
                goal_y = rng.uniform(POSTS[0] + 0.6, POSTS[1] - 0.6)
            else:
                goal_y = rng.choice((POSTS[0] - rng.uniform(1, 5), POSTS[1] + rng.uniform(1, 5)))
            target = (goal_x, goal_y)
            if event.outcome == "blocked":
                target = (
                    here[0] + (target[0] - here[0]) * 0.35,
                    here[1] + (target[1] - here[1]) * 0.35,
                )
            speed = (event.shot_speed_kmh or 80.0) / 3.6
            length = _dist(here, target)
            flight = min(length / speed, max(t1 - t0 - 0.2, 0.08))
            segments.append(Segment(t0, t0 + flight, here, target))
            touches.append(
                TrueTouch(
                    t0,
                    here,
                    event.team_id,
                    event.event_id,
                    "shot",
                    length,
                    length / flight,
                    event.shot_speed_kmh,
                )
            )
            if event.outcome == "goal":
                # The ball rests in the net until play restarts from the centre: a cut, not a kick.
                segments.append(Segment(t0 + flight, t1, target, target))
                cuts.append(t1)
                continue
            # A save, block or miss: the ball goes on to the next touch, a movement the log does not record.
            rest = t0 + flight + 0.25
            gap = _dist(target, there)
            move = min(gap / rng.uniform(9, 14), max(t1 - rest, 0.08))
            segments.append(Segment(t0 + flight, rest, target, target))
            if gap > 1.0 and rest < t1:
                segments.append(Segment(rest, rest + move, target, there))
                touches.append(TrueTouch(rest, target, None, None, None, gap, gap / move))
                segments.append(Segment(rest + move, t1, there, there))
            continue
        length = _dist(here, there)
        if length < 1.0:
            segments.append(Segment(t0, t1, here, here))
            continue
        lo, hi = {"carry": (3.5, 6.5), "dribble": (4.0, 7.0), "clearance": (18, 26)}.get(
            event.type, (11, 21)
        )
        speed = rng.uniform(lo, hi)
        duration = max(min(length / speed, t1 - t0), 0.08)
        segments.append(Segment(t0, t0 + duration, here, there))
        if event.type in ("carry", "dribble") and event.team_id:
            # The player runs with the ball, so the ring stays with it.
            rings[-1] = (t0, t0 + duration, event.team_id)
        if t0 + duration < t1:
            segments.append(Segment(t0 + duration, t1, there, there))
        touches.append(
            TrueTouch(
                t0, here, event.team_id, event.event_id, event.type, length, length / duration
            )
        )
    return Truth(touches, segments, rings, cuts)


def ball_at(segments: list[Segment], t: float, cursor: list[int]) -> tuple[float, float] | None:
    """The ball's position at time t; segments are scanned forwards with a shared cursor."""
    i = cursor[0]
    while i < len(segments) and segments[i].t1 <= t:
        i += 1
    cursor[0] = i
    if i >= len(segments) or segments[i].t0 > t:
        return None
    s = segments[i]
    span = s.t1 - s.t0
    f = 0.0 if span <= 0 else (t - s.t0) / span
    return (s.start[0] + (s.end[0] - s.start[0]) * f, s.start[1] + (s.end[1] - s.start[1]) * f)


def _pitch() -> np.ndarray:
    """Grass with markings in a muted colour, so the ball stays the brightest thing on screen."""
    frame = np.empty((HEIGHT, WIDTH, 3), dtype=np.uint8)
    frame[:] = GRASS

    def line(x0: float, y0: float, x1: float, y1: float) -> None:
        """A two-pixel line between two points in metres."""
        steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) * PX_PER_M))
        for k in range(steps + 1):
            f = k / steps
            px = int((x0 + (x1 - x0) * f + MARGIN) * PX_PER_M)
            py = int((y0 + (y1 - y0) * f + MARGIN) * PX_PER_M)
            frame[max(py - 1, 0) : py + 1, max(px - 1, 0) : px + 1] = LINES

    edges = [
        (0.3, 0.3, 104.7, 0.3),
        (0.3, 67.7, 104.7, 67.7),
        (0.3, 0.3, 0.3, 67.7),
        (104.7, 0.3, 104.7, 67.7),
        (52.5, 0.3, 52.5, 67.7),
    ]
    for x, inner in ((0.3, 16.5), (104.7, 88.2)):
        edges += [(x, 13.85, inner, 13.85), (x, 54.15, inner, 54.15), (inner, 13.85, inner, 54.15)]
    for edge in edges:
        line(*edge)
    for k in range(120):
        a = 2 * math.pi * k / 120
        x, y = 52.5 + 9.15 * math.cos(a), 34 + 9.15 * math.sin(a)
        line(x, y, x, y)
    return frame


def frames(
    truth: Truth, start: float, end: float, seed: int = 7
) -> Iterator[tuple[float, np.ndarray]]:
    """Video frames from start to end seconds of match clock: noisy, with the ball sometimes hidden."""
    rng = np.random.default_rng(seed)
    base = _pitch().astype(np.int16)
    noisy = [
        np.clip(base + rng.normal(0, 9, base.shape), 0, 255).astype(np.uint8) for _ in range(24)
    ]
    yy, xx = np.mgrid[-8:9, -8:9]
    r2 = xx * xx + yy * yy
    ball_mask = r2 <= 6
    ring_mask = (r2 >= 22) & (r2 <= 42)
    cursor = [0]
    rings = sorted(truth.rings)
    ring_i = 0
    hide = random.Random(seed)
    n = int((end - start) * FPS)
    for k in range(n):
        t = start + k / FPS
        frame = noisy[k % len(noisy)].copy()
        pos = ball_at(truth.segments, t, cursor)
        while ring_i < len(rings) and rings[ring_i][1] < t:
            ring_i += 1
        if pos is not None:
            px, py = (
                int(round((pos[0] + MARGIN) * PX_PER_M)),
                int(round((pos[1] + MARGIN) * PX_PER_M)),
            )
            team = next((r[2] for r in rings[ring_i : ring_i + 3] if r[0] <= t <= r[1]), None)
            y0, y1, x0, x1 = py - 8, py + 9, px - 8, px + 9
            if 0 <= y0 and y1 <= HEIGHT and 0 <= x0 and x1 <= WIDTH:
                window = frame[y0:y1, x0:x1]
                if team is not None:
                    window[ring_mask] = TEAM_RGB[team]
                # About one frame in fifty the ball is hidden, as by a player or the camera.
                if hide.random() > 0.02:
                    window[ball_mask] = BALL
        yield t, frame
