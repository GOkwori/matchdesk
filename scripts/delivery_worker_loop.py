#!/usr/bin/env python3
"""Bounded offline delivery loop; never runs coding models or writes to GitHub."""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from delivery_agent_loop import OfflineDockerWorker, WorkerResult
from delivery_orchestrator import DEFAULT_MANIFEST
from delivery_supervisor import Supervisor

WORKER_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")


def run_cycle(db: Path, manifest: dict, worker: str, *, dry_run: bool = True) -> dict:
    """Recover expired reservations and fail closed if no executor is installed."""
    if not WORKER_ID.fullmatch(worker):
        raise ValueError("Invalid worker identity")
    supervisor = Supervisor(db, manifest)
    try:
        recovered = supervisor.recover()
        if dry_run:
            return {
                "mode": "DRY_RUN_NO_EXECUTOR",
                "recovered": recovered,
                "state": supervisor.status(),
            }
        claimed = supervisor.claim(worker)
        if claimed is None:
            return {
                "mode": "RESERVATION_ONLY",
                "task": None,
                "recovered": recovered,
                "state": supervisor.status(),
            }
        # No coding adapter is authorised; do not leave a misleading live lease.
        supervisor.release(claimed, worker, "BLOCKED")
        supervisor.request_input(
            claimed,
            "Coding executor not configured. Supply approved sandbox, credentials and cost ceiling.",
        )
        return {
            "mode": "EXECUTOR_NOT_CONFIGURED",
            "task": claimed,
            "recovered": recovered,
            "state": supervisor.status(),
        }
    finally:
        supervisor.close()


def execute_cycle(
    db: Path, manifest: dict, executor: OfflineDockerWorker, *, clock: int | None = None
) -> dict:
    """Lease and dispatch up to four independent workstreams; retain review receipts.

    The coordinator owns SQLite on its calling thread; worker threads only run
    isolated adapters. A proposal is never an accepted or merged change.
    """
    supervisor = Supervisor(db, manifest, clock=clock)
    try:
        supervisor.recover()
        jobs: list[tuple[str, str, object]] = []
        available = supervisor.manifest["max_parallel"] - sum(
            item["status"] == "LEASED" for item in supervisor.status()["tasks"]
        )
        with ThreadPoolExecutor(max_workers=supervisor.manifest["max_parallel"]) as pool:
            for _ in range(available):
                identity = "agent-" + uuid.uuid4().hex
                task_id = supervisor.claim(identity, lease_seconds=1200)
                if task_id is None:
                    break
                jobs.append((task_id, identity, pool.submit(executor.execute, task_id, identity)))
            for task_id, identity, pending in jobs:
                try:
                    outcome = pending.result()
                    if not isinstance(outcome, WorkerResult):
                        raise ValueError("Unexpected worker response")
                    state = outcome.state
                    if state not in ("REVIEW_REQUIRED", "BLOCKED", "QUEUED"):
                        raise ValueError("Unexpected worker state")
                    receipt = None
                    if state == "REVIEW_REQUIRED":
                        if not outcome.digest or not outcome.evidence_dir:
                            raise ValueError("Missing patch evidence")
                        receipt = json.dumps(
                            {
                                "authority": "PATCH_REVIEW_ONLY",
                                "task_id": task_id,
                                "patch_sha256": outcome.digest,
                                "evidence_dir": outcome.evidence_dir,
                            },
                            sort_keys=True,
                        )
                except Exception:
                    state, receipt = "BLOCKED", None
                supervisor.now = int(time.time()) if clock is None else clock
                supervisor.release(task_id, identity, state, receipt=receipt)
                if state == "BLOCKED":
                    supervisor.request_input(
                        task_id,
                        "Offline executor blocked; inspect local evidence and sandbox configuration.",
                    )
                current = next(
                    item for item in supervisor.status()["tasks"] if item["id"] == task_id
                )
                if state == "QUEUED" and current["attempts"] >= 3:
                    supervisor.request_input(
                        task_id, "Execution retry limit reached; investigate before resuming."
                    )
        return supervisor.status()
    finally:
        supervisor.close()


def main() -> int:
    """Run a bounded offline polling session, without agent or deployment authority."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--db", type=Path, default=Path("artifacts/delivery/state.sqlite3"))
    parser.add_argument("--worker", default="local-supervisor")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--reserve", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.cycles <= 1440 or not 1 <= args.interval <= 3600:
        parser.error("Cycle and interval budgets must be bounded")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    for cycle in range(args.cycles):
        outcome = run_cycle(args.db, manifest, args.worker, dry_run=not args.reserve)
        print(json.dumps(outcome, sort_keys=True), flush=True)
        if cycle + 1 < args.cycles:
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
