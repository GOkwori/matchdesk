"""Offline loop tests establish no implicit executor or acceptance authority."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from delivery_worker_loop import run_cycle
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


if __name__ == "__main__":
    unittest.main()
