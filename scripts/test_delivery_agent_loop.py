"""Fail-closed validation of proposed offline worker patches."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delivery_agent_loop import OfflineDockerWorker, validate_patch


class AgentLoopTests(unittest.TestCase):
    """Reject arbitrary files, credentials and unconfigured sandbox execution."""

    def test_scoped_patch_passes_as_proposal_only(self):
        """A valid textual patch produces a digest, not an applied change."""
        content = (
            b"diff --git a/backend/tests/test_example.py b/backend/tests/test_example.py\n"
            b"--- a/backend/tests/test_example.py\n"
            b"+++ b/backend/tests/test_example.py\n"
            b"@@ -1 +1 @@\n-old\n+new\n"
        )
        digest, paths = validate_patch("producer", content)
        self.assertEqual(len(digest), 64)
        self.assertEqual(paths, ("backend/tests/test_example.py",))

    def test_protected_workflow_patch_rejected(self):
        """An agent cannot change authentication or security workflows."""
        content = (
            b"diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml\n"
            b"--- a/.github/workflows/ci.yml\n"
            b"+++ b/.github/workflows/ci.yml\n"
            b"@@ -1 +1 @@\n-a\n+b\n"
        )
        with self.assertRaises(ValueError):
            validate_patch("producer", content)

    def test_traversal_and_metadata_spoofing_rejected(self):
        """Path escapes and disguised metadata cannot cross lane boundaries."""
        fragments = [
            b"diff --git a/backend/tests/../../.github/x b/backend/tests/../../.github/x\n",
            b"diff --git a/backend/tests/a.py b/backend/tests/b.py\n",
            b"diff --git a/backend/tests/a.py b/backend/tests/a.py\n+++ b/.github/x\n",
            b"diff --git a/backend/tests/a.py b/backend/tests/a.py\nnew file mode 120000\n",
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment), self.assertRaises(ValueError):
                validate_patch("producer", fragment + b"@@ -1 +1 @@\n-x\n+y\n")

    def test_unapproved_image_rejected_before_docker(self):
        """An executor must be pinned to an immutable image digest."""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                OfflineDockerWorker(
                    Path(directory), "a" * 40, "untrusted:latest",
                    Path(directory).parent / "evidence",
                )

    def test_invalid_worker_never_invokes_container(self):
        """Invalid worker authority is denied before any process execution."""
        with tempfile.TemporaryDirectory() as directory:
            worker = OfflineDockerWorker(
                Path(directory), "a" * 40,
                "agent@sha256:" + "b" * 64,
                Path(directory).parent / "not-under-repo",
            )
            with patch("delivery_agent_loop.subprocess.run") as execute:
                self.assertEqual(worker.execute("producer", "../invalid").state, "BLOCKED")
                execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
