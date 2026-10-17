"""Offline security and restart-contract checks for inert systemd unit output."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from render_delivery_host_service import main, render_unit, safe_absolute_path

PIN = "4aca395793b03b9ffab108df0db2d45834922f26"
SOURCE = "/srv/matchdesk-checkout"
STATE = "/var/lib/matchdesk-control"


class RenderControlHostServiceTests(unittest.TestCase):
    """Ensure rendered host service cannot silently activate coding or spend."""

    def render(self, **overrides):
        """Create only an in-memory unit with safe test defaults."""
        options = dict(source=SOURCE, source_sha=PIN, state_dir=STATE)
        options.update(overrides)
        return render_unit(**options)

    def test_pinned_control_only_restart_contract(self):
        """Require source pin, offline restrictions and a finite restart loop."""
        unit = self.render()
        self.assertIn(f"--source-sha {PIN}", unit)
        self.assertIn("ExecStartPre=/usr/bin/python3", unit)
        self.assertIn("--run --cycles 1440 --interval 30", unit)
        self.assertIn("Restart=always", unit)
        self.assertIn("StartLimitBurst=3", unit)
        self.assertIn("ReadWritePaths=/var/lib/matchdesk-control", unit)
        self.assertIn("NoNewPrivileges=yes", unit)
        self.assertIn("RestrictAddressFamilies=AF_UNIX", unit)
        self.assertNotIn("delivery_worker_loop.py", unit)
        self.assertNotIn("docker run", unit)
        self.assertNotIn("systemctl", unit)

    def test_paths_fail_closed_for_injection_and_traversal(self):
        """Never interpolate shell, unit specifier or parent path syntax."""
        for path in (
            "relative/path",
            "/",
            "/srv//checkout",
            "/srv/./checkout",
            "/srv/../checkout",
            "/srv/checkout space",
            "/srv/checkout;echo",
            "/srv/%n",
            "/srv/$(touch-pwned)",
            "/srv/checkout\nExecStart=unsafe",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_absolute_path(path)

    def test_rejects_state_inside_source(self):
        """Durable state cannot be placed in or at the source tree."""
        for state in (SOURCE, SOURCE + "/private"):
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.render(state_dir=state)

    def test_rejects_invalid_pin_and_unbounded_cycles(self):
        """Prevent implicit branch tracking or unrestricted process lifetimes."""
        for pin in ("development", "a" * 39, "A" * 40):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                self.render(source_sha=pin)
        for cycle in (0, 1441):
            with self.assertRaises(ValueError):
                self.render(cycles=cycle)
        for interval in (0, 3601):
            with self.assertRaises(ValueError):
                self.render(interval=interval)

    def test_wsl_scoped_home_runtime_mounts(self):
        """Expose only the reviewed interpreter, checkout and external state."""
        source = "/home/georgie/matchdesk-control-test.PDw9Is/source"
        python = (
            "/home/georgie/.local/share/matchdesk/python/"
            "cpython-3.12.15-linux-x86_64-gnu/bin/python3.12"
        )
        state = "/home/georgie/matchdesk-control-test.PDw9Is/service-state"
        unit = self.render(
            source=source,
            python_path=python,
            state_dir=state,
            wsl_home_paths=True,
        )
        self.assertIn("ProtectHome=tmpfs", unit)
        self.assertIn(f"BindReadOnlyPaths={source}", unit)
        self.assertIn(
            "BindReadOnlyPaths=/home/georgie/.local/share/matchdesk/"
            "python/cpython-3.12.15-linux-x86_64-gnu",
            unit,
        )
        self.assertIn(f"BindPaths={state}", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("RestrictAddressFamilies=AF_UNIX", unit)
        self.assertNotIn("BindPaths=/home/georgie\n", unit)
        self.assertIn(" -E -s -B ", unit)

    def test_wsl_profile_does_not_weaken_default(self):
        """Default remains ProtectHome=yes and rejects paths beneath home."""
        unit = self.render()
        self.assertIn("ProtectHome=yes", unit)
        self.assertNotIn("BindPaths=", unit)
        with self.assertRaises(ValueError):
            self.render(source="/home/georgie/source")

    def test_wsl_rejects_cross_user_and_broad_mounts(self):
        """Reject paths crossing home ownership or overlapping write scopes."""
        source = "/home/georgie/project/source"
        python = "/home/georgie/python/cpython-3.12.15/bin/python3.12"
        valid_state = "/home/georgie/project-state"
        changes = (
            {"source": "/home"},
            {"source": "/home/georgie"},
            {"source": "/home/another/source"},
            {"state_dir": "/home/another/state"},
            {"state_dir": "/home/georgie"},
            {"state_dir": "/home/georgie/python"},
            {"state_dir": "/home/georgie/python/cpython-3.12.15/cache"},
            {"python_path": "/home/another/python/bin/python3.12"},
            {"python_path": "/home/georgie/bin/python3.12"},
            {"python_path": "/home/georgie/project/source/bin/python3.12"},
        )
        for change in changes:
            options = {
                "source": source,
                "python_path": python,
                "state_dir": valid_state,
                "wsl_home_paths": True,
            }
            options.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.render(**options)

    def test_cli_outputs_unit_without_installing(self):
        """The operator gets text to review, not an installed/started service."""
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "--source",
                        SOURCE,
                        "--source-sha",
                        PIN,
                        "--state-dir",
                        STATE,
                        "--cycles",
                        "2",
                        "--interval",
                        "5",
                    ]
                ),
                0,
            )
        self.assertIn("--run --cycles 2 --interval 5", output.getvalue())
        self.assertIn("WantedBy=default.target", output.getvalue())


if __name__ == "__main__":
    unittest.main()
