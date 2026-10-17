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
