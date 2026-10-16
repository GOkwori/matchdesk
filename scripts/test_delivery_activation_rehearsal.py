"""Hermetic operator rehearsal for the actual four-lane delivery manifest.

All outcomes are synthetic fixtures. This module makes no GitHub request,
runs no coding agent or Docker image, sends no alert, and changes no release
authority. A green test is not evidence of an activated persistent worker.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from delivery_agent_loop import WorkerResult
from delivery_orchestrator import DEFAULT_MANIFEST
from delivery_supervisor import Supervisor
from delivery_worker_loop import execute_cycle


def actual_manifest():
    """Load the committed queue, not a reduced stand-in test manifest."""
    return json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))


class OperatorRehearsalTests(unittest.TestCase):
    """Rehearse bounded concurrency, crashes, review holds and owner alerts."""

    def test_four_engineering_lanes_are_bounded_and_humans_never_leased(self):
        """No fifth engineering lease or human approval can be claimed."""
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.sqlite3"
            supervisor = Supervisor(db, actual_manifest(), clock=1000)
            try:
                claims = [
                    supervisor.claim(f"rehearsal-{i}", lease_seconds=30)
                    for i in range(5)
                ]
                self.assertEqual(
                    claims, ["producer", "audience", "assurance", "demo", None]
                )
                states = {
                    item["id"]: item["status"]
                    for item in supervisor.status()["tasks"]
                }
                self.assertEqual(states["owner-input"], "WAITING_INPUT")
                self.assertEqual(states["accessibility"], "WAITING_INPUT")
                self.assertFalse(supervisor.status()["complete"])
            finally:
                supervisor.close()

    def test_three_crashes_recover_then_block_with_exactly_one_alert(self):
        """A restarted worker cannot exceed the retry ceiling or self-clear."""
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.sqlite3"
            for attempt in range(3):
                started_at = 1000 + 31 * attempt
                supervisor = Supervisor(db, actual_manifest(), clock=started_at)
                try:
                    self.assertEqual(
                        supervisor.claim(f"crashed-{attempt}", lease_seconds=30),
                        "producer",
                    )
                finally:
                    supervisor.close()
                supervisor = Supervisor(db, actual_manifest(), clock=started_at + 30)
                try:
                    self.assertEqual(supervisor.recover(), 1)
                    producer = next(
                        task for task in supervisor.status()["tasks"]
                        if task["id"] == "producer"
                    )
                    self.assertEqual(
                        producer["status"],
                        "BLOCKED" if attempt == 2 else "QUEUED",
                    )
                finally:
                    supervisor.close()
            supervisor = Supervisor(db, actual_manifest(), clock=1093)
            try:
                result = supervisor.status()
                producer = next(
                    task for task in result["tasks"]
                    if task["id"] == "producer"
                )
                self.assertEqual(producer["attempts"], 3)
                self.assertEqual(result["pending_owner_alerts"], 1)
                self.assertFalse(result["complete"])
            finally:
                supervisor.close()

    def test_four_patch_proposals_do_not_certify_or_release_human_holds(self):
        """Only test-only patch proposals emerge, never accepted code."""

        class FakeSandbox:
            """Supply synthetic review receipts without executing a command."""

            def execute(self, task_id, identity):
                """Return a fixture that cannot be treated as verified output."""
                return WorkerResult(
                    "REVIEW_REQUIRED", "a" * 64, f"/test-only/{identity}"
                )

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.sqlite3"
            result = execute_cycle(
                db, actual_manifest(), FakeSandbox(), clock=1000
            )
            review = {
                task["id"] for task in result["tasks"]
                if task["status"] == "REVIEW_REQUIRED"
            }
            self.assertEqual(
                review, {"producer", "audience", "assurance", "demo"}
            )
            self.assertFalse(result["complete"])
            supervisor = Supervisor(db, actual_manifest(), clock=1001)
            try:
                human = {
                    task["id"] for task in supervisor.status()["tasks"]
                    if task["kind"] == "human"
                }
                self.assertEqual(human, {"owner-input", "accessibility"})
                self.assertFalse(supervisor.status()["complete"])
            finally:
                supervisor.close()

    def test_crash_ambiguous_owner_alert_remains_quarantined_after_restart(self):
        """A claimed but unconfirmed notification is not automatically resent."""
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.sqlite3"
            supervisor = Supervisor(db, actual_manifest(), clock=1000)
            try:
                detail = "Operator sign-off required"
                self.assertTrue(supervisor.request_input("owner-input", detail))
                self.assertFalse(supervisor.request_input("owner-input", detail))
                fingerprint = str(
                    supervisor.pending_alerts()[0]["fingerprint"]
                )
                self.assertTrue(supervisor.claim_alert_send(fingerprint))
            finally:
                supervisor.close()
            supervisor = Supervisor(db, actual_manifest(), clock=1001)
            try:
                self.assertFalse(supervisor.claim_alert_send(fingerprint))
                self.assertEqual(len(supervisor.claimed_alerts()), 1)
                self.assertEqual(
                    supervisor.status()["uncertain_owner_alerts"], 1
                )
                self.assertEqual(
                    supervisor.status()["pending_owner_alerts"], 1
                )
            finally:
                supervisor.close()


if __name__ == "__main__":
    unittest.main()
