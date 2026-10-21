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
import os
from pathlib import Path
from typing import Any

from matchdesk.domain.agent_demo import record_agent_run
from matchdesk.domain.agent_rehearsal import RehearsalExecutor
from matchdesk.domain.agent_workflow import WorkflowExecutor, describe_error
from matchdesk.domain.foundry_runtime import FoundryWorkflowExecutor

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "apps/web/src/studio/generated/agent-trace.json"


def _annotation(level: str, title: str, lines: list[str]) -> None:
    """Print one GitHub Actions annotation, readable through the checks API."""
    body = "%0A".join(line.replace("%", "%25").replace("\n", " ") for line in lines)
    print(f"::{level} title={title}::{body}")


def report(trace: dict[str, Any]) -> None:
    """Summarise a run as annotations: status, each turn and any provider errors.

    Annotations survive where logs and artifacts may not be reachable, and carry
    only what the trace carries: no endpoint, deployment name or credential.
    """
    totals = trace["totals"]
    lines = [
        f"status {trace['status']}; terminal reason {trace.get('terminal_reason')}",
        f"{totals['specialist_turns']} turns, {totals['tool_calls']} tool calls, "
        f"{totals['verification_rounds']} verification rounds, tokens {totals['tokens']}",
    ]
    for step in trace["steps"]:
        if step["type"] == "specialist":
            lines.append(
                f"{step['role']}: {step['outcome']}, attempts {step['attempts']}, "
                f"tools {len(step['tool_calls'])}, claims {len(step['claims'])}, "
                f"failures {step['failures']}"
            )
            lines.extend(f"  error: {error}" for error in step.get("errors", []))
        elif step["type"] == "verification":
            verdicts = [row.get("status") for row in step.get("results", [])]
            lines.append(f"verification round {step.get('round')}: {verdicts}")
            for row in step.get("results", []):
                if row.get("status") not in ("verified", "supported_inference"):
                    lines.append(
                        f"  {row.get('claim_id')} {row.get('status')}: {row.get('reason')} "
                        f"(expected {row.get('expected')}, observed {row.get('observed')}) "
                        f"text: {str(row.get('text', ''))[:160]}"
                    )
        else:
            lines.append(f"{step['type']}: {step.get('reason', '')}")
    level = "notice" if trace["status"] == "completed" else "error"
    _annotation(level, "Agent run summary", lines)


def main() -> int:
    """Run the workflow once and write the trace."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("rehearsal", "foundry"), default="rehearsal")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    executor: WorkflowExecutor
    if args.provider == "foundry":
        executor = FoundryWorkflowExecutor()
        try:
            trace = asyncio.run(record_agent_run(executor))
        except Exception as error:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                _annotation("error", "Agent run crashed", [describe_error(error)])
            raise
        trace["recorded_on"] = dt.date.today().isoformat()
    else:
        trace = asyncio.run(record_agent_run(RehearsalExecutor(), clock=lambda: None))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(trace, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if os.environ.get("GITHUB_ACTIONS") == "true":
        report(trace)
    totals = trace["totals"]
    print(
        f"{trace['provider']['kind']}: {trace['status']}, {totals['specialist_turns']} turns, "
        f"{totals['tool_calls']} tool calls, {totals['verification_rounds']} verification "
        f"rounds, tokens {totals['tokens']}"
    )
    return 0 if trace["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
