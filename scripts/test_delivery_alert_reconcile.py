"""Offline test cases for safe GitHub alert reconciliation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delivery_alert_reconcile import identify_comment, reconcile
from delivery_alerts import format_alert_body
from delivery_supervisor import Supervisor
from test_delivery_supervisor import manifest


class ReconciliationTests(unittest.TestCase):
    """Unknown, forged and duplicate sends remain quarantined."""

    def setUp(self):
        """Start with a durable uncertain claimed send."""
        self.tmp = tempfile.TemporaryDirectory()
        self.supervisor = Supervisor(Path(self.tmp.name) / "state.sqlite3", manifest(), clock=1000)
        self.supervisor.request_input("review", "Confirm approved screenshot")
        self.alert = self.supervisor.pending_alerts()[0]
        self.supervisor.claim_alert_send(self.alert["fingerprint"])

    def tearDown(self):
        """Close the SQLite database before cleaning up."""
        self.supervisor.close()
        self.tmp.cleanup()

    def test_rejects_untrusted_author_or_body(self):
        """An arbitrary GitHub user cannot forge a delivery receipt."""
        body = format_alert_body(
            self.alert["issue"], self.alert["fingerprint"], self.alert["detail"]
        )
        comments = [{"id": 7, "body": body, "user": {"login": "attacker"}}]
        self.assertIsNone(
            identify_comment(
                comments,
                issue=self.alert["issue"],
                fingerprint=self.alert["fingerprint"],
                detail=self.alert["detail"],
                actor="approved-bot",
            )
        )

    def test_multiple_matches_fail_closed(self):
        """Duplicate remote posts must never be silently marked successful."""
        body = format_alert_body(
            self.alert["issue"], self.alert["fingerprint"], self.alert["detail"]
        )
        comments = [
            {"id": n, "body": body, "user": {"login": "approved-bot"}} for n in (7, 8)
        ]
        with self.assertRaises(ValueError):
            identify_comment(
                comments,
                issue=self.alert["issue"],
                fingerprint=self.alert["fingerprint"],
                detail=self.alert["detail"],
                actor="approved-bot",
            )

    def test_only_verified_exact_comment_reconciles(self):
        """A confirmed issue-bound reply clears an uncertain local send."""
        body = format_alert_body(
            self.alert["issue"], self.alert["fingerprint"], self.alert["detail"]
        )
        with patch(
            "delivery_alert_reconcile.read_comments",
            return_value=[{"id": 919, "body": body, "user": {"login": "approved-bot"}}],
        ):
            result = reconcile(self.supervisor, "offline-token", "approved-bot")
        self.assertEqual(result["confirmed"], 1)
        self.assertEqual(result["quarantined"], [])
        self.assertEqual(self.supervisor.status()["pending_owner_alerts"], 0)

    def test_absent_comment_never_retries_or_clears(self):
        """No remote match means a human must resolve the uncertain delivery."""
        with patch("delivery_alert_reconcile.read_comments", return_value=[]):
            result = reconcile(self.supervisor, "offline-token", "approved-bot")
        self.assertEqual(result["confirmed"], 0)
        self.assertEqual(len(result["quarantined"]), 1)


if __name__ == "__main__":
    unittest.main()
