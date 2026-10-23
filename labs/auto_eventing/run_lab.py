"""Run the auto-eventing lab: render the synthetic match, detect events from the video, score.

    python3 labs/auto_eventing/run_lab.py --clip apps/web/src/studio/generated/auto-eventing

The renderer turns the canonical log into top-down video and keeps the ground truth. The
detector reads only the frames. The scorer matches what the detector found to the truth:
touches (recall against the logged events, precision against every real change of course),
the event type, the team, touch-to-touch length and ball speed, the speed of each shot
against the log's synthetic tracking, and possession read from the video against the
registered possession metric. The result is written for the studio's Auto-eventing lab page.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend/src"), str(ROOT), str(Path(__file__).resolve().parent)]

from detect import DetectedEvent, detect  # noqa: E402
from matchdesk.domain import canonical_match as canonical  # noqa: E402
from matchdesk.domain.demo_claims import REPLAY_END_MS  # noqa: E402
from matchdesk.domain.metrics import compute_metric  # noqa: E402
from matchdesk.domain.models import MatchWindow, Subject  # noqa: E402
from render import FPS, HEIGHT, TEAM_RGB, WIDTH, build_truth, frames  # noqa: E402

OUT = ROOT / "apps/web/src/studio/generated/auto-eventing.json"
CLIP = (57 * 60 + 40, 58 * 60 + 40)  # the corner and Okafor's header
TIME_TOL = 2.5 / FPS
DIST_TOL = 1.5


def _match(found: list[DetectedEvent], truth: list, tol_t: float = TIME_TOL) -> dict[int, int]:
    """Pair each true touch with the nearest unused detection in time and place."""
    pairs: dict[int, int] = {}
    used: set[int] = set()
    j0 = 0
    for i, touch in enumerate(truth):
        while j0 < len(found) and found[j0].t < touch.t - tol_t:
            j0 += 1
        best, best_d = None, None
        for j in range(j0, len(found)):
            if found[j].t > touch.t + tol_t:
                break
            if j in used:
                continue
            d = math.hypot(found[j].at[0] - touch.at[0], found[j].at[1] - touch.at[1])
            if d <= DIST_TOL and (best_d is None or d < best_d):
                best, best_d = j, d
        if best is not None:
            pairs[i] = best
            used.add(best)
    return pairs


def _possession(found: list[DetectedEvent], start: float, end: float) -> float | None:
    """Northbridge's share of time from each touch to the next, by the team seen touching."""
    held = {canonical.HOME: 0.0, canonical.AWAY: 0.0}
    for a, b in zip(found, [*found[1:], None], strict=False):
        nxt = b.t if b else end
        if a.team in held and a.t >= start:
            held[a.team] += max(0.0, min(nxt, end) - a.t)
    total = sum(held.values())
    return held[canonical.HOME] / total if total else None


def run(clip: Path | None) -> dict:
    """Render, detect and score the whole replay; optionally encode the highlight clip."""
    log = tuple(e for e in canonical.generate_canonical_match() if e.match_clock_ms < REPLAY_END_MS)
    truth = build_truth(log)
    end = REPLAY_END_MS / 1000.0
    found = detect(frames(truth, 0.0, end), TEAM_RGB)
    logged = [t for t in truth.touches if t.event_id]
    pairs_all = _match(found, truth.touches)
    pairs_logged = {i: j for i, j in pairs_all.items() if truth.touches[i].event_id}
    matched_found = set(pairs_all.values())
    kinds = {
        "pass": "pass",
        "kickoff": "pass",
        "clearance": "pass",
        "carry": "carry",
        "dribble": "carry",
        "shot": "shot",
    }
    typed = [
        (truth.touches[i], found[j])
        for i, j in pairs_logged.items()
        if truth.touches[i].event_type in kinds
    ]
    type_ok = sum(kinds[t.event_type] == f.kind for t, f in typed)
    teamed = [
        (truth.touches[i], found[j]) for i, j in pairs_logged.items() if truth.touches[i].team
    ]
    team_ok = sum(t.team == f.team for t, f in teamed)
    passes = [(t, f) for t, f in typed if kinds[t.event_type] == "pass" and f.kind == "pass"]
    length_err = [abs(f.length_m - t.length_m) for t, f in passes]
    speed_err = [abs(f.speed_ms - t.speed_ms) * 3.6 for t, f in passes]
    shots = [(t, f) for t, f in typed if t.event_type == "shot"]
    shot_rows = [
        {
            "event_id": t.event_id,
            "clock": f"{int(t.t // 60):02d}:{int(t.t % 60):02d}",
            "tracking_kmh": t.shot_speed_kmh,
            "video_kmh": round(f.speed_ms * 3.6, 1),
            "detected_as": f.kind,
        }
        for t, f in shots
    ]
    log_share = compute_metric(
        "possession_time.v1",
        log,
        Subject(team_id=canonical.HOME),
        MatchWindow(from_ms=0, to_ms=REPLAY_END_MS),
    )
    video_share = _possession(found, 0.0, end)
    timeline = [
        {
            "t": round(f.t, 2),
            "kind": f.kind,
            "team": f.team,
            "length_m": round(f.length_m, 1),
            "kmh": round(f.speed_ms * 3.6, 1),
            "event_id": next(
                (truth.touches[i].event_id for i, j in pairs_all.items() if j == n), None
            ),
        }
        for n, f in enumerate(found)
        if CLIP[0] <= f.t < CLIP[1]
    ]
    result = {
        "schema": "matchdesk-auto-eventing/1",
        "synthetic": True,
        "video": {
            "fps": FPS,
            "width": WIDTH,
            "height": HEIGHT,
            "seconds": round(end),
            "frames": int(end * FPS),
            "clip": {"from_s": CLIP[0], "to_s": CLIP[1]},
        },
        "touches": {
            "logged": len(logged),
            "found": len(found),
            "recall": round(len(pairs_logged) / len(logged), 4),
            "precision": round(len(matched_found) / len(found), 4) if found else None,
            "unlogged_true": len(truth.touches) - len(logged),
        },
        "type_accuracy": round(type_ok / len(typed), 4) if typed else None,
        "team_accuracy": round(team_ok / len(teamed), 4) if teamed else None,
        "passes": {
            "compared": len(passes),
            "length_mae_m": round(mean(length_err), 2) if length_err else None,
            "length_median_m": round(median(length_err), 2) if length_err else None,
            "speed_mae_kmh": round(mean(speed_err), 2) if speed_err else None,
        },
        "shots": {
            "logged": sum(1 for t in logged if t.event_type == "shot"),
            "matched": len(shots),
            "detected_as_shot": sum(1 for _, f in shots if f.kind == "shot"),
            "speed_mae_kmh": round(
                mean(
                    abs(r["video_kmh"] - r["tracking_kmh"]) for r in shot_rows if r["tracking_kmh"]
                ),
                2,
            )
            if shot_rows
            else None,
            "rows": shot_rows,
        },
        "possession": {
            "log": round(log_share, 4),
            "video": round(video_share, 4) if video_share is not None else None,
        },
        "clip_events": timeline,
    }
    if clip is not None:
        encode(truth, clip)
    return result


def encode(truth, out: Path) -> None:
    """The highlight clip as MP4 (H.264), then WebM (VP9) from it, so every browser plays one.

    The frames carry sensor noise, which barely compresses; H.264 at a moderate quality smooths
    it, and the WebM is made from that file so both stay small.
    """
    mp4, webm = out.with_suffix(".mp4"), out.with_suffix(".webm")
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WIDTH}x{HEIGHT}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "30",
        "-preset",
        "slow",
        "-movflags",
        "+faststart",
        str(mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for _, frame in frames(truth, *CLIP):
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    vp9 = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(mp4),
        "-c:v",
        "libvpx-vp9",
        "-b:v",
        "0",
        "-crf",
        "38",
        "-deadline",
        "good",
        "-cpu-used",
        "4",
        "-row-mt",
        "1",
        str(webm),
    ]
    if subprocess.run(vp9, check=False).returncode != 0:
        raise SystemExit("ffmpeg failed")


def main() -> None:
    """Write the results, and the clip when asked."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", type=Path, help="Base path for the clip; writes .webm and .mp4")
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()
    result = run(args.clip)
    OUT.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        k: result[k] for k in ("touches", "type_accuracy", "team_accuracy", "passes", "possession")
    }
    summary["shots"] = {k: v for k, v in result["shots"].items() if k != "rows"}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
