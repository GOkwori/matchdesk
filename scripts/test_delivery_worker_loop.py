"""Offline loop tests establish no implicit executor or acceptance authority."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from delivery_worker_loop import execute_cycle, run_cycle
from delivery_agent_loop import WorkerResult
from test_delivery_supervisor import manifest


class WorkerLoopTests(unittest.TestCase):
    """Cover absence of executor, durable block and worker validation."""

    def test_dry_run_never_leases(self):
        """Read-only mode never claims that a coding process has started."""
        with tempfile.TemporaryDirectory() as directory:
            result = run_cycle(Path(directory) / "state.sqlite3", manifest(), "worker")
            self.assertEqual(result["mode"], "DRY_RUN_NO_EXECUTOR")
            self.assertFalse(result["state"]["complete"])
            self.assertEqual(result["state"]["tasks"][0]["status"], "QUEUED")

    def test_reservation_blocks_when_no_executor(self):
        """Missing coding adapter leaves no active lease and records one alert."""
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.sqlite3"
            result = run_cycle(db, manifest(), "worker", dry_run=False)
            self.assertEqual(result["mode"], "EXECUTOR_NOT_CONFIGURED")
            self.assertEqual(result["state"]["tasks"][0]["status"], "BLOCKED")
            self.assertEqual(result["state"]["pending_owner_alerts"], 1)
            second = run_cycle(db, manifest(), "worker", dry_run=False)
            self.assertIsNone(second["task"])

    def test_unsafe_worker_rejected(self):
        """Worker identifiers must not contain path or shell metacharacters."""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                run_cycle(Path(directory) / "state.sqlite3", manifest(), "../worker")


    def test_parallel_proposals_are_durable_but_not_accepted(self):
        """Independent lanes generate review receipts without certification."""
        class Stub:
            """Return test-only patch proposals without any subprocess."""

            def execute(self, task_id, identity):
                """Return a deterministic digest bound to its lane."""
                return WorkerResult("REVIEW_REQUIRED", "a" * 64, f"/tmp/{identity}")

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.sqlite3"
            result = execute_cycle(db, manifest(), Stub(), clock=1000)
            first = next(item for item in result["tasks"] if item["id"] == "producer")
            self.assertEqual(first["status"], "REVIEW_REQUIRED")
            self.assertIn('"authority": "PATCH_REVIEW_ONLY"', first["receipt"])
            self.assertFalse(result["complete"])
            second = execute_cycle(db, manifest(), Stub(), clock=1001)
            self.assertEqual(
                next(item for item in second["tasks"] if item["id"] == "producer")["attempts"],
                1,
            )

    def test_worker_exception_blocks_and_escalates_once(self):
        """A failing worker cannot strand an active reservation."""
        class Broken:
            """Test adapter that fails without returning a result."""

            def execute(self, task_id, identity):
                """Simulate a broken offline worker."""
                raise RuntimeError("simulated failure")

        with tempfile.TemporaryDirectory() as directory:
            result = execute_cycle(Path(directory) / "state.sqlite3", manifest(), Broken(), clock=1000)
            self.assertEqual(result["tasks"][0]["status"], "BLOCKED")
            self.assertEqual(result["pending_owner_alerts"], 1)


if __name__ == "__main__":
    unittest.main()
