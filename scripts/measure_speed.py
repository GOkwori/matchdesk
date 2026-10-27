"""Measure how fast the pipeline ingests, reduces and verifies, on this machine.

    python -m scripts.measure_speed

Times three things with the real code and no network: the whole live replay streamed with
no pacing (ingest, reduce and verify every cue and recap on the events received so far);
verifying each cue's claims at the moment its window closes; and verifying every claim the
overlays, recaps and stories show. Prints JSON. Numbers depend on the machine; they are
for scale, not a service-level promise.
"""

from __future__ import annotations

import asyncio
import json
import platform
import statistics
import time

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain import live_replay
from matchdesk.domain.demo_claims import DISPLAY_NAMES, REPLAY_END_MS, evidence_record
from matchdesk.domain.verification import verify_claim
from matchdesk.domain.verifier_benchmark import base_claims


async def _stream() -> tuple[float, int, int]:
    """The whole replay with sleeps removed: seconds, events and verified frames."""

    async def no_sleep(_: float) -> None:
        """Skip the pacing: the replay runs as fast as the code allows."""
        return None

    start = time.perf_counter()
    events = frames = 0
    async for frame in live_replay.live_replay(60, sleep=no_sleep, elapsed=lambda: 0.0):
        events += frame.startswith("event: event")
        frames += frame.startswith("event: cue") or frame.startswith("event: recap")
    return time.perf_counter() - start, events, frames


def _per_cue() -> tuple[list[float], int]:
    """Milliseconds per moment a cue or recap closes, verified on the events received then."""
    session = live_replay._Session()
    timings = []
    checked = 0
    for event in live_replay._log():
        due = session.next_due()
        while due is not None and due <= event.match_clock_ms:
            began = time.perf_counter()
            checked += len(session.due_cues(due))
            timings.append((time.perf_counter() - began) * 1000)
            due = session.next_due()
        session.take(event)
    # The last cues close after the final event, at the replay point.
    while (due := session.next_due()) is not None:
        began = time.perf_counter()
        checked += len(session.due_cues(due))
        timings.append((time.perf_counter() - began) * 1000)
    return timings, checked


def _all_claims(repeats: int = 5) -> float:
    """Milliseconds to verify every claim the demo shows, best of several runs."""
    log = tuple(e for e in canonical.generate_canonical_match() if e.match_clock_ms < REPLAY_END_MS)
    evidence = evidence_record(log)
    claims = base_claims()
    best = float("inf")
    for _ in range(repeats):
        began = time.perf_counter()
        for claim in claims:
            verify_claim(claim, evidence, log, names=DISPLAY_NAMES)
        best = min(best, (time.perf_counter() - began) * 1000)
    return best


def main() -> None:
    """Print the measurements."""
    seconds, events, frames = asyncio.run(_stream())
    cue_ms, checked = _per_cue()
    print(
        json.dumps(
            {
                "machine": f"{platform.machine()} · Python {platform.python_version()}",
                "stream": {
                    "events": events,
                    "verified_frames": frames,
                    "seconds": round(seconds, 2),
                    "events_per_second": round(events / seconds),
                },
                "cue_verification_ms": {
                    "cues_and_recaps": checked,
                    "moments": len(cue_ms),
                    "median": round(statistics.median(cue_ms), 1),
                    "max": round(max(cue_ms), 1),
                },
                "all_claims_ms": {"claims": len(base_claims()), "total": round(_all_claims(), 1)},
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
