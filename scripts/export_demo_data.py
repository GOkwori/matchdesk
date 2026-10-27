"""Write (or check) the frontend files generated from the canonical match.

Usage: python -m scripts.export_demo_data [--check]
--check fails when any committed file differs from a fresh deterministic export.

Files:
- apps/web/src/studio/generated/nbr-riv.json: statistics, moments and the backend's
  verdicts on the D-031 claims.
- apps/web/src/studio/generated/nbr-riv-events.json: the compact event log the browser
  re-verifies against.
- apps/web/tests/verifier-parity.json: claims run through the real verifier, which the
  TypeScript port must reproduce exactly.
- apps/web/src/studio/generated/agent-trace.json: the four-specialist workflow on the
  58:17 goal. The deterministic rehearsal is regenerated here; a live Foundry recording
  (scripts/record_agent_run.py --provider foundry) is never overwritten or compared,
  because a model does not answer twice the same way. Tests re-verify its verdicts.
- apps/web/src/studio/generated/agent-trace-rehearsal.json: the rehearsal, always
  regenerated, so AI insights can show it beside a live recording.
- apps/web/src/studio/generated/verifier-benchmark.json: the "try to fool the verifier"
  results; apps/web/tests/verifier-benchmark-cases.json: every case and the server's
  verdict, which the browser port must reproduce.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.agent_demo import rehearsal_trace, trace_view
from matchdesk.domain.demo_export import build_demo_export
from matchdesk.domain.overlay_feed import build_overlay_feed
from matchdesk.domain.recap_feed import build_recap_feed
from matchdesk.domain.story_feed import build_story_feed
from matchdesk.domain.verifier_benchmark import parity_cases, run_benchmark
from matchdesk.domain.verifier_parity import compact_events, parity_fixture

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "apps/web/src/studio/generated/nbr-riv.json"
EVENTS = ROOT / "apps/web/src/studio/generated/nbr-riv-events.json"
PARITY = ROOT / "apps/web/tests/verifier-parity.json"
TRACE = ROOT / "apps/web/src/studio/generated/agent-trace.json"
REHEARSAL = ROOT / "apps/web/src/studio/generated/agent-trace-rehearsal.json"
OVERLAYS = ROOT / "apps/web/src/studio/generated/nbr-riv-overlays.json"
STORIES = ROOT / "apps/web/src/studio/generated/nbr-riv-stories.json"
RECAPS = ROOT / "apps/web/src/studio/generated/nbr-riv-recaps.json"
BENCHMARK = ROOT / "apps/web/src/studio/generated/verifier-benchmark.json"
BENCHMARK_CASES = ROOT / "apps/web/tests/verifier-benchmark-cases.json"
VIEWS = {
    TRACE: ROOT / "apps/web/src/studio/generated/agent-trace.view.json",
    REHEARSAL: ROOT / "apps/web/src/studio/generated/agent-trace-rehearsal.view.json",
}


def render() -> str:
    """Return the canonical JSON text for the summary export."""
    return json.dumps(build_demo_export(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_events() -> str:
    """Return the compact event log; one line, as it ships to the browser."""
    log = canonical.generate_canonical_match()
    return json.dumps(compact_events(log), separators=(",", ":"), sort_keys=True) + "\n"


def render_parity() -> str:
    """Return the verifier parity fixture."""
    return json.dumps(parity_fixture(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def render_stories() -> str:
    """The fan stories, one per goal, with the claims behind them."""
    return json.dumps(build_story_feed(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def render_recaps() -> str:
    """The half-time recap and the recap at the replay point, with the claims behind them."""
    return json.dumps(build_recap_feed(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def render_overlays() -> str:
    """Return the timed overlay feed, published as a downloadable file."""
    return json.dumps(build_overlay_feed(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def render_benchmark() -> str:
    """The verifier benchmark's results, as the studio shows them."""
    return json.dumps(run_benchmark(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def render_benchmark_cases() -> str:
    """Every benchmark case with the server's verdict, one per line."""
    lines = [
        json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for c in parity_cases()
    ]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def render_trace() -> str:
    """Return the deterministic rehearsal trace."""
    return json.dumps(rehearsal_trace(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def committed_trace_is_live() -> bool:
    """True when the committed trace is a live recording, which must be kept as is."""
    if not TRACE.exists():
        return False
    return bool(json.loads(TRACE.read_text(encoding="utf-8"))["provider"]["kind"] == "foundry")


def outputs() -> dict[Path, str]:
    """Every generated file and its expected text."""
    files = {
        TARGET: render(),
        EVENTS: render_events(),
        PARITY: render_parity(),
        REHEARSAL: render_trace(),
        OVERLAYS: render_overlays(),
        STORIES: render_stories(),
        RECAPS: render_recaps(),
        BENCHMARK: render_benchmark(),
        BENCHMARK_CASES: render_benchmark_cases(),
    }
    # agent-trace.json holds the recorded live run once there is one; until then it is
    # the rehearsal too. AI insights shows both when they differ.
    if not committed_trace_is_live():
        files[TRACE] = render_trace()
    for source, view in VIEWS.items():
        text = files.get(source) or source.read_text(encoding="utf-8")
        files[view] = json.dumps(trace_view(json.loads(text)), sort_keys=True, ensure_ascii=False)
        files[view] += "\n"
    return files


def main() -> int:
    """Write the exports, or compare them with the committed files in --check mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if a committed export is stale")
    args = parser.parse_args()
    stale = 0
    for path, text in outputs().items():
        name = path.relative_to(ROOT)
        if args.check:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != text:
                print(f"STALE: {name} differs from a fresh export")
                stale += 1
            else:
                print(f"OK: {name} is current")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {name}")
    return int(bool(stale))


if __name__ == "__main__":
    raise SystemExit(main())
