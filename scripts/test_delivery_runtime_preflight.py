"""Offline, hermetic tests for local-only executor activation preflight."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from delivery_runtime_preflight import verify_local_activation


class PreflightTests(unittest.TestCase):
    """Reject unsafe hosts and verify exact local-only process arguments."""

    def setUp(self):
        """Create paths and a deterministic fake unprivileged host."""
        self.tmp = tempfile.TemporaryDirectory()
        self.source = Path(self.tmp.name) / "repo"
        self.source.mkdir()
        (self.source / ".git").mkdir()
        self.sha = "a" * 40
        self.image = "matchdesk-agent@sha256:" + "b" * 64
        self.commands = []

    def tearDown(self):
        """Release the isolated test paths."""
        self.tmp.cleanup()

    def command(self, cmd, **kwargs):
        """Return stubbed, read-only git and rootless Docker metadata."""
        self.commands.append((cmd, kwargs))
        if cmd[0] == "git":
            value = self.sha if cmd[-1] == "HEAD" else ""
        elif cmd[-1] == "{{json .SecurityOptions}}":
            value = json.dumps(["name=rootless", "name=seccomp"])
        else:
            value = json.dumps([self.image])
        return subprocess.CompletedProcess(cmd, 0, value, "")

    def preflight(self, **overrides):
        """Call preflight without consulting a live Git or Docker daemon."""
        args = dict(
            source=self.source,
            source_sha=self.sha,
            image=self.image,
            database=Path(self.tmp.name) / "state.sqlite3",
            evidence=Path(self.tmp.name) / "evidence",
            environment={"HOME": self.tmp.name},
            effective_uid=1001,
            runner=self.command,
        )
        args.update(overrides)
        return verify_local_activation(**args)

    def test_pinned_rootless_host_passes_without_executing(self):
        """Read-only metadata queries cannot create a cloud coding session."""
        result = self.preflight()
        self.assertEqual(result["mode"], "LOCAL_OFFLINE_PREFLIGHT_ONLY")
        self.assertEqual(result["persistent_service"], "NOT_STARTED")
        self.assertEqual(len(self.commands), 4)
        self.assertTrue(all(command[1]["timeout"] == 20 for command in self.commands))

    def test_root_and_cloud_tokens_fail_before_subprocess(self):
        """Privilege and credential conflicts must not contact Docker."""
        for extra in (
            {"effective_uid": 0},
            {"environment": {"OPENAI_API_KEY": "secret"}},
            {"environment": {"DOCKER_HOST": "tcp://example:2375"}},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.preflight(**extra)
        self.assertEqual(self.commands, [])

    def test_repository_local_state_denied(self):
        """SQLite and patch evidence cannot be written inside source control."""
        with self.assertRaises(ValueError):
            self.preflight(database=self.source / "private" / "state.sqlite3")
        self.assertEqual(self.commands, [])

    def test_non_rootless_daemon_denied(self):
        """A Docker daemon with elevated privileges cannot execute workers."""
        def rootful(cmd, **kwargs):
            """Simulate a Docker daemon without rootless protections."""
            result = self.command(cmd, **kwargs)
            if cmd[:2] == ["docker", "info"]:
                return subprocess.CompletedProcess(cmd, 0, '["name=seccomp"]', "")
            return result

        with self.assertRaises(ValueError):
            self.preflight(runner=rootful)

    def test_worker_entrypoint_enforces_preflight(self):
        """Execution mode must validate host controls before constructing Docker."""
        from unittest.mock import patch

        from delivery_worker_loop import main

        with tempfile.TemporaryDirectory() as directory:
            manifest_file = Path(directory) / "manifest.json"
            from test_delivery_supervisor import manifest

            manifest_file.write_text(json.dumps(manifest()), encoding="utf-8")
            args = [
                "delivery_worker_loop.py",
                "--manifest",
                str(manifest_file),
                "--execute-offline",
                "--source",
                str(self.source),
                "--source-sha",
                self.sha,
                "--image",
                self.image,
                "--evidence-dir",
                str(Path(directory) / "evidence"),
                "--db",
                str(Path(directory) / "state.sqlite3"),
            ]
            with (
                patch("sys.argv", args),
                patch("delivery_worker_loop.verify_local_activation", side_effect=ValueError("denied")) as check,
                patch("delivery_worker_loop.OfflineDockerWorker") as docker,
            ):
                with self.assertRaisesRegex(ValueError, "denied"):
                    main()
                check.assert_called_once()
                docker.assert_not_called()

    def test_incorrect_digest_denied(self):
        """A local image tag is not proof of an installed approved digest."""
        def wrong_image(cmd, **kwargs):
            """Return empty locally installed digest metadata."""
            result = self.command(cmd, **kwargs)
            if cmd[:3] == ["docker", "image", "inspect"]:
                return subprocess.CompletedProcess(cmd, 0, "[]", "")
            return result

        with self.assertRaises(ValueError):
            self.preflight(runner=wrong_image)


if __name__ == "__main__":
    unittest.main()
