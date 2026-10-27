"""Offline tests for local, non-executing control-service readiness."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from delivery_host_control import exclusive_lock, verify_control_host


class HostControlTests(unittest.TestCase):
    """Reject source drift, unsafe state and duplicate instances."""

    def setUp(self):
        """Build a disposable test-only checkout and locked-down state directory."""
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.source = root / "checkout"
        (self.source / ".git").mkdir(parents=True)
        (self.source / "scripts").mkdir()
        (self.source / "scripts" / "delivery_worker_loop.py").write_text("# fixture\n")
        (self.source / "docs" / "engineering").mkdir(parents=True)
        (self.source / "docs" / "engineering" / "delivery-workstreams.json").write_text("{}")
        self.state_dir = root / "private"
        self.state_dir.mkdir(mode=0o700)
        self.db = self.state_dir / "state.sqlite3"
        self.lock = self.state_dir / "control.lock"
        self.sha = "a" * 40
        self.calls = []

    def tearDown(self):
        """Remove only this test's scratch files."""
        self.temp.cleanup()

    def git(self, command, **kwargs):
        """Stub local Git without network or write operations."""
        self.calls.append((command, kwargs))
        value = self.sha if command[-1] == "HEAD" else ""
        return subprocess.CompletedProcess(command, 0, value, "")

    def verify(self, **kwargs):
        """Use the calling unprivileged UID and a deterministic local Git stub."""
        inputs = dict(
            source=self.source,
            source_sha=self.sha,
            database=self.db,
            lock=self.lock,
            environment={},
            effective_uid=os.geteuid(),
            runner=self.git,
        )
        inputs.update(kwargs)
        return verify_control_host(**inputs)

    @unittest.skipIf(os.geteuid() == 0, "Requires non-root CI user")
    def test_readiness_only_no_executor(self):
        """Preflight never invokes a coding adapter or touches the network."""
        report = self.verify()
        self.assertEqual(report["mode"], "LOCAL_CONTROL_PREFLIGHT_ONLY")
        self.assertEqual(report["coding_executor"], "NOT_ACTIVATED")
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(c[1]["timeout"] == 15 for c in self.calls))
        self.assertTrue(all(c[1]["env"]["GIT_OPTIONAL_LOCKS"] == "0" for c in self.calls))
        self.assertTrue(all(c[1]["env"]["GIT_CONFIG_GLOBAL"] == "/dev/null" for c in self.calls))

    def test_rejects_root_and_credential_inheritance(self):
        """Root and any model/GitHub credential fail before subprocess."""
        with self.assertRaises(ValueError):
            self.verify(effective_uid=0)
        with self.assertRaises(ValueError):
            self.verify(environment={"MATCHDESK_ALERT_GITHUB_TOKEN": "unsafe"})
        self.assertEqual(self.calls, [])

    @unittest.skipIf(os.geteuid() == 0, "Requires non-root CI user")
    def test_rejects_insecure_storage(self):
        """Reject group-readable files, repository-local state and symbolic links."""
        self.state_dir.chmod(0o755)
        with self.assertRaises(ValueError):
            self.verify()
        self.state_dir.chmod(0o700)
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(ValueError, "inside the source checkout"):
            self.verify(database=self.source / "private" / "state.sqlite3")
        with self.assertRaisesRegex(ValueError, "already exist"):
            self.verify(database=Path(self.temp.name) / "missing" / "state.sqlite3")
        self.lock.symlink_to(self.source / ".git")
        with self.assertRaises(ValueError):
            self.verify()
        self.assertEqual(self.calls, [])

    @unittest.skipIf(os.geteuid() == 0, "Requires non-root CI user")
    def test_exact_source_drift_rejected(self):
        """Reject any mismatch between approved commit and checked-out HEAD."""

        def mismatch(command, **kwargs):
            """Simulate a checkout at the wrong commit."""
            self.git(command, **kwargs)
            return subprocess.CompletedProcess(command, 0, "b" * 40, "")

        with self.assertRaises(ValueError):
            self.verify(runner=mismatch)

    @unittest.skipIf(os.geteuid() == 0, "Requires non-root CI user")
    def test_lock_prevents_concurrent_processes(self):
        """A second lock acquisition fails instead of running two coordinators."""
        with exclusive_lock(self.lock):
            with self.assertRaises(RuntimeError):
                with exclusive_lock(self.lock):
                    pass
        with exclusive_lock(self.lock):
            pass


if __name__ == "__main__":
    unittest.main()
