"""The detector finds what the renderer drew, and never needs the log to do it."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend/src"), str(ROOT), str(Path(__file__).resolve().parent)]

import detect  # noqa: E402
import render  # noqa: E402
import run_lab  # noqa: E402
from matchdesk.domain import canonical_match as canonical  # noqa: E402

LOG = tuple(e for e in canonical.generate_canonical_match() if e.match_clock_ms < 4_032_000)
TRUTH = render.build_truth(LOG)


def _window(start: float, end: float) -> tuple[list, list]:
    """Detections and true touches in a stretch of the match."""
    found = detect.detect(render.frames(TRUTH, start, end), render.TEAM_RGB)
    truth = [t for t in TRUTH.touches if start + 0.5 <= t.t < end - 0.5]
    return found, truth


def test_the_detector_module_does_not_read_the_log() -> None:
    """Pixels only: no import of the match, the log or the renderer."""
    source = Path(detect.__file__).read_text(encoding="utf-8")
    assert "matchdesk" not in source and "render" not in source.replace("rendered", "")


def test_touches_types_and_speeds_in_the_minute_of_the_header() -> None:
    """The corner and Okafor's header: touches found, the header read as a shot at its speed."""
    found, truth = _window(57 * 60 + 40, 58 * 60 + 40)
    pairs = run_lab._match(found, truth)
    logged = [i for i, t in enumerate(truth) if t.event_id]
    assert sum(1 for i in logged if i in pairs) / len(logged) >= 0.95
    assert len(pairs) / len(found) >= 0.95
    header = next(i for i, t in enumerate(truth) if t.event_id == "E-1365")
    shot = found[pairs[header]]
    assert shot.kind == "shot" and abs(shot.speed_ms * 3.6 - 49.4) < 3.0
    for i, j in pairs.items():
        if truth[i].team:
            assert found[j].team == truth[i].team


def test_a_still_ball_and_pixel_noise_make_no_touches() -> None:
    """Noise alone is not an event."""
    still = render.Truth(
        touches=[], segments=[render.Segment(0, 10, (50.0, 30.0), (50.0, 30.0))], rings=[], cuts=[]
    )
    assert detect.detect(render.frames(still, 0.0, 10.0), render.TEAM_RGB) == []
