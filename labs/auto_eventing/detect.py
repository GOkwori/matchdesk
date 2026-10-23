"""Auto-eventing: find touches, passes, carries and shots in top-down video, from pixels only.

The detector never sees the event log. Per frame it finds the ball (the brightest compact
blob) and the colour of any ring round it (the team touching it). Over frames it tracks
the ball in metres, fills short gaps where the ball was hidden, and marks a touch wherever
the ball starts to move or changes course or speed sharply. Each stretch between touches
becomes an event: a shot when it is fast and ends at a goal line, a carry when it is slow,
otherwise a pass, completed when the next touch is by the same team. Lengths and speeds are
measured from the track.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np

FPS = 25
PX_PER_M = 6
MARGIN = 3.0
PITCH_W = 105.0
POSTS = (30.34, 37.66)
STILL = 0.03  # metres per frame: below this the ball is at rest
WINDOW = 4  # frames either side used to measure the ball's velocity
MIN_CHANGE = 0.12  # metres per frame (3 m/s): a smaller change in velocity is pixel noise
MIN_LENGTH = 0.6  # metres: a shorter movement is the ball settling, not an event
SHOT_SPEED = 13.0  # metres per second: faster than this, towards a goal line, is a shot
CARRY_SPEED = 8.0  # slower than this is a player running with the ball
PASS_SPEED = 12.0  # a ringed ball slower than this is still being run with
GOAL_MOUTH = (PITCH_W, 34.0)


@dataclass
class Observation:
    """One frame: the ball in metres (or None) and the team colour seen round it."""

    t: float
    ball: tuple[float, float] | None
    ring: str | None


@dataclass
class DetectedEvent:
    """An event read from the video."""

    t: float
    at: tuple[float, float]
    team: str | None
    kind: str  # pass, carry, shot
    length_m: float
    speed_ms: float
    completed: bool | None = None
    end: tuple[float, float] | None = None


@dataclass
class Detector:
    """Reads frames one at a time and keeps the track."""

    team_colours: dict[str, tuple[int, int, int]]
    track: list[Observation] = field(default_factory=list)

    def observe(self, t: float, frame: np.ndarray) -> None:
        """Find the ball and any team ring in one frame."""
        bright = (frame[:, :, 0] > 238) & (frame[:, :, 1] > 238) & (frame[:, :, 2] > 215)
        ys, xs = np.nonzero(bright)
        ball = None
        ring = None
        if 4 <= len(xs) <= 60:
            cx, cy = float(xs.mean()), float(ys.mean())
            ball = (cx / PX_PER_M - MARGIN, cy / PX_PER_M - MARGIN)
            ring = self._ring(frame, int(round(cx)), int(round(cy)))
        self.track.append(Observation(t, ball, ring))

    def _ring(self, frame: np.ndarray, cx: int, cy: int) -> str | None:
        """The team whose colour fills the annulus round the ball, if either does."""
        y0, y1, x0, x1 = max(cy - 8, 0), cy + 9, max(cx - 8, 0), cx + 9
        patch = frame[y0:y1, x0:x1].reshape(-1, 3).astype(np.int16)
        best, best_count = None, 0
        for team, rgb in self.team_colours.items():
            near = np.abs(patch - np.array(rgb, dtype=np.int16)).max(axis=1) < 28
            count = int(near.sum())
            if count > best_count:
                best, best_count = team, count
        return best if best_count >= 12 else None

    def positions(self) -> np.ndarray:
        """The track as an array of (x, y), with hidden frames filled when the gap is short."""
        pts = np.array([o.ball if o.ball else (np.nan, np.nan) for o in self.track], dtype=float)
        missing = np.isnan(pts[:, 0])
        k = 0
        while k < len(pts):
            if not missing[k]:
                k += 1
                continue
            j = k
            while j < len(pts) and missing[j]:
                j += 1
            if 0 < k and j < len(pts) and j - k <= 3:
                for m in range(k, j):
                    f = (m - k + 1) / (j - k + 1)
                    pts[m] = pts[k - 1] + (pts[j] - pts[k - 1]) * f
            k = j
        return pts

    def events(self) -> list[DetectedEvent]:
        """Touches, then the event between each touch and the next.

        The ball's centre moves in whole pixels, so frame-to-frame velocity is noisy. A touch
        is found where the average velocity over the next few frames differs most from the
        average over the previous few: a kick from rest, a pass received and played on, a
        change of direction.
        """
        pts = self.positions()
        times = [o.t for o in self.track]
        n = len(pts)
        w = WINDOW
        change = np.zeros(n)
        cut = np.zeros(n, dtype=bool)
        step = np.hypot(*np.diff(pts, axis=0).T)
        cut[1:] = step > 4.0  # a jump of more than 100 m/s is a cut in the picture, not a kick
        for k in range(w, n - w):
            back = (pts[k] - pts[k - w]) / w
            fwd = (pts[k + w] - pts[k]) / w
            if np.isnan(back).any() or np.isnan(fwd).any() or cut[k - w + 1 : k + w + 1].any():
                continue
            change[k] = float(np.hypot(*(fwd - back)))
        touches = [
            k
            for k in range(w, n - w)
            if change[k] >= MIN_CHANGE
            and change[k] == change[k - w : k + w + 1].max()
            and np.hypot(*(pts[k + w] - pts[k])) / w >= STILL
        ]
        out: list[DetectedEvent] = []
        for i, k in enumerate(touches):
            stop = touches[i + 1] if i + 1 < len(touches) else n - 1
            seg = pts[k : stop + 1]
            ok = ~np.isnan(seg[:, 0])
            if ok.sum() < 2:
                continue
            seg = seg[ok]
            moves = np.hypot(*np.diff(seg, axis=0).T)
            moving = np.nonzero(moves >= STILL)[0]
            if not len(moving):
                continue
            # The first unbroken run of movement is the kick; anything after it belongs to the
            # next touch, even when that touch was found a frame or two late.
            first = int(moving[0])
            last = first
            while last + 1 < len(moves) and moves[last + 1] >= STILL:
                last += 1
            start, end = seg[0], seg[last + 1]
            length = float(np.hypot(*(end - start)))
            if length < MIN_LENGTH:
                continue
            duration = (last + 1 - first) / FPS
            v = length / duration if duration > 0 else 0.0
            team = self._team_near(k)
            # A player running with the ball keeps their ring round it; a kicked ball leaves it.
            frames_seen = self.track[k + first : k + last + 2]
            ringed = sum(1 for o in frames_seen if o.ring) / max(len(frames_seen), 1)
            if v >= SHOT_SPEED and _towards_goal(start, end):
                kind = "shot"
            elif v < CARRY_SPEED or (ringed >= 0.6 and v < PASS_SPEED):
                kind = "carry"
            else:
                kind = "pass"
            out.append(
                DetectedEvent(
                    times[k],
                    (float(start[0]), float(start[1])),
                    team,
                    kind,
                    length,
                    v,
                    end=(float(end[0]), float(end[1])),
                )
            )
        for a, b in zip(out, out[1:], strict=False):
            if a.kind == "pass":
                a.completed = a.team is not None and a.team == b.team
        return out

    def _team_near(self, k: int) -> str | None:
        """The ring colour seen most in the few frames after a touch."""
        seen = [o.ring for o in self.track[k : k + 6] if o.ring]
        return max(set(seen), key=seen.count) if seen else None


def _towards_goal(start: np.ndarray, end: np.ndarray) -> bool:
    """A strike that reaches a goal line, or heads at a goal mouth from within 35 m and is stopped."""
    if end[0] <= 0.8 or end[0] >= PITCH_W - 0.8:
        return True
    goal_x = PITCH_W if end[0] > start[0] else 0.0
    to_goal = np.array([goal_x, 34.0]) - start
    if float(np.hypot(*to_goal)) > 35.0:
        return False
    travel = end - start
    cos = float(np.dot(travel, to_goal) / (np.hypot(*travel) * np.hypot(*to_goal) + 1e-9))
    return cos >= math.cos(math.radians(20))


def detect(
    frames: Iterable[tuple[float, np.ndarray]], team_colours: dict[str, tuple[int, int, int]]
) -> list[DetectedEvent]:
    """Run the detector over a stream of frames."""
    detector = Detector(team_colours)
    for t, frame in frames:
        detector.observe(t, frame)
    return detector.events()
