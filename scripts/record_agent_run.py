"""Record one run of the four-specialist workflow on the canonical match.

Usage:
    python -m scripts.record_agent_run --provider rehearsal
    python -m scripts.record_agent_run --provider foundry --out artifacts/agent-run/agent-trace.json

The rehearsal makes no model calls. The foundry provider makes live, billable calls:
one Agent Framework agent per specialist turn (about six turns, each with at most
twelve read-tool calls and 1,200 output tokens). It requires
MATCHDESK_FOUNDRY_ENABLED=true, FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL, and an
explicit owner decision to spend. The output contains no secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
from pathlib import Path

from matchdesk.domain.agent_demo import record_agent_run
from matchdesk.domain.agent_rehearsal import RehearsalExecutor
from matchdesk.domain.agent_workflow import WorkflowExecutor
from matchdesk.domain.foundry_runtime import FoundryWorkflowExecutor

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "apps/web/src/studio/generated/agent-trace.json"


def main() -> int:
    """Run the workflow once and write the trace."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("rehearsal", "foundry"), default="rehearsal")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    executor: WorkflowExecutor
    if args.provider == "foundry":
        executor = FoundryWorkflowExecutor()
        trace = asyncio.run(record_agent_run(executor))
        trace["recorded_on"] = dt.date.today().isoformat()
    else:
        trace = asyncio.run(record_agent_run(RehearsalExecutor(), clock=lambda: None))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(trace, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    totals = trace["totals"]
    print(
        f"{trace['provider']['kind']}: {trace['status']}, {totals['specialist_turns']} turns, "
        f"{totals['tool_calls']} tool calls, {totals['verification_rounds']} verification "
        f"rounds, tokens {totals['tokens']}"
    )
    return 0 if trace["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
