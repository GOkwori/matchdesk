"""Offline durable supervisor tests, including crash and authorization cases."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from delivery_supervisor import Supervisor


def manifest():
    """Create a small, bounded queue without external credentials."""
    return {
        "schema_version": 1,
        "repository": "GOkwori/matchdesk",
        "development_branch": "development",
        "production_branch": "main",
        "max_parallel": 4,
        "deadline": "2026-10-26",
        "epic_issue": 60,
        "required_workflows": ["Foundation CI"],
        "required_integration_checks": ["runtime-browser"],
        "tasks": [
            {
                "id": "producer",
                "issue": 61,
                "kind": "engineering",
                "phase": "P3",
                "depends_on": [],
                "acceptance": "Tested",
            },
            {
                "id": "demo",
                "issue": 64,
                "kind": "engineering",
                "phase": "P5",
                "depends_on": ["producer"],
                "acceptance": "Tested",
            },
            {
                "id": "review",
                "issue": 65,
                "kind": "human",
                "phase": "Owner",
                "depends_on": [],
                "acceptance": "Human approval",
            },
        ],
    }


class SupervisorTests(unittest.TestCase):
    """Prove restart, lease expiry, evidence hold and no write escalation."""

    def setUp(self):
        """Give each test an isolated on-disk durable journal."""
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.s = Supervisor(self.path, manifest(), clock=1000)

    def tearDown(self):
        """Release locks and temporary state."""
        self.s.close()
        self.temp.cleanup()

    def test_queue_does_not_claim_completion(self):
        """The presence of a task does not mean execution or approval."""
        report = self.s.status()
        self.assertFalse(report["complete"])
        self.assertEqual(report["tasks"][-1]["status"], "WAITING_INPUT")
        self.assertIn("NO_CODING_EXECUTOR", report["execution_mode"])

    def test_restarts_preserve_reservations_and_recover_after_expiry(self):
        """A crashed worker's task survives restart and lease timeout."""
        self.assertEqual(self.s.claim("worker-1", lease_seconds=60), "producer")
        self.s.close()
        self.s = Supervisor(self.path, manifest(), clock=1040)
        self.assertEqual(self.s.recover(), 0)
        self.assertIsNone(self.s.claim("worker-2"))
        self.s.close()
        self.s = Supervisor(self.path, manifest(), clock=1060)
        self.assertEqual(self.s.recover(), 1)
        self.assertEqual(self.s.claim("worker-2"), "producer")

    def test_dependency_does_not_consume_slot(self):
        """A dependent lane cannot run merely because its predecessor is leased."""
        self.assertEqual(self.s.claim("worker-1"), "producer")
        self.assertIsNone(self.s.claim("worker-2"))

    def test_worker_cannot_certify(self):
        """Returning a worker result is never equivalent to verified acceptance."""
        self.assertEqual(self.s.claim("worker-1"), "producer")
        with self.assertRaises(ValueError):
            self.s.release("producer", "worker-1", "VERIFIED")
        self.s.release("producer", "worker-1", "REVIEW_REQUIRED")
        self.assertNotEqual(self.s.status()["tasks"][0]["status"], "VERIFIED")

    def test_wrong_worker_cannot_release(self):
        """A worker cannot change another worker's reservation."""
        self.s.claim("worker-1")
        with self.assertRaises(PermissionError):
            self.s.release("producer", "worker-2", "QUEUED")

    def test_expired_worker_cannot_release(self):
        """An expired worker must not override its newer successor."""
        self.s.claim("worker-1", lease_seconds=30)
        self.s.now = 1030
        with self.assertRaises(PermissionError):
            self.s.release("producer", "worker-1", "QUEUED")

    def test_attempt_ceiling_prevents_unbounded_retry(self):
        """No task may spin indefinitely on repeated failures."""
        for _ in range(3):
            self.assertEqual(self.s.claim("worker-1"), "producer")
            self.s.release("producer", "worker-1", "QUEUED")
        self.assertIsNone(self.s.claim("worker-1"))

    def test_owner_escalations_deduplicate(self):
        """Identical owner needs cannot flood the outbox."""
        self.assertTrue(self.s.request_input("review", "Provide original PNGs"))
        self.assertFalse(self.s.request_input("review", "Provide original PNGs"))
        self.assertEqual(self.s.status()["pending_owner_alerts"], 1)

    def test_manifest_drift_fails_closed(self):
        """Persisted work cannot be silently redirected to another issue."""
        self.s.close()
        changed = manifest()
        changed["tasks"][0]["issue"] = 900
        with self.assertRaises(ValueError):
            Supervisor(self.path, changed, clock=1000)
        self.s = Supervisor(self.path, manifest(), clock=1000)


if __name__ == "__main__":
    unittest.main()
