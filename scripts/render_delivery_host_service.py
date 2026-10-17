#!/usr/bin/env python3
"""Render an inert systemd user service; never install or start it.

The resulting unit only runs the MatchDesk control-only preflight and bounded
recovery/status loop. Rendering does not inspect or change a real host, and
nothing produced here grants a coding executor or notification authority.
"""

from __future__ import annotations

import argparse
import re
from pathlib import PurePosixPath

SHA = re.compile(r"[0-9a-f]{40}\Z")
SAFE_PATH = re.compile(r"/[A-Za-z0-9._/-]+\Z")


def safe_absolute_path(value: str) -> PurePosixPath:
    """Reject unit-field injection, traversal, substitutions and relative paths."""
    if SAFE_PATH.fullmatch(value) is None:
        raise ValueError("Only simple absolute Linux paths are permitted")
    components = value.split("/")[1:]
    if any(component in {"", ".", ".."} for component in components):
        raise ValueError("Paths cannot contain empty, dot or parent components")
    return PurePosixPath(value)


def render_unit(
    *,
    source: str,
    source_sha: str,
    state_dir: str,
    python_path: str = "/usr/bin/python3",
    cycles: int = 1440,
    interval: int = 30,
) -> str:
    """Return a pinned, restart-managed control-only unit without any side effects.

    All variable text is restricted to safe systemd ExecStart field tokens.
    The unit requires external operator provisioning and independent acceptance.
    """
    if SHA.fullmatch(source_sha) is None:
        raise ValueError("Exact lowercase 40-hex source SHA required")
    checkout = safe_absolute_path(source)
    state = safe_absolute_path(state_dir)
    executable = safe_absolute_path(python_path)
    if state == checkout or checkout in state.parents:
        raise ValueError("State directory must be outside the source checkout")
    if not 1 <= cycles <= 1440 or not 1 <= interval <= 3600:
        raise ValueError("Finite cycle count and interval must be within bounds")

    # Only the previously reviewed, non-coding entrypoint may be invoked.
    script = checkout / "scripts" / "delivery_host_control.py"
    db = state / "state.sqlite3"
    lock = state / "control.lock"
    command = (
        f"{executable} {script} --source {checkout} --source-sha {source_sha} "
        f"--db {db} --lock {lock}"
    )
    return "\n".join(
        [
            "# REVIEW ONLY. Operator must independently verify the host and pin.",
            "# Control/recovery/status only: no coding executor or notifications.",
            "[Unit]",
            "Description=MatchDesk local control-only coordinator (NO coding)",
            "StartLimitIntervalSec=300",
            "StartLimitBurst=3",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={checkout}",
            "Environment=PYTHONDONTWRITEBYTECODE=1",
            "Environment=PYTHONNOUSERSITE=1",
            (
                "UnsetEnvironment=OPENAI_API_KEY ANTHROPIC_API_KEY "
                "GITHUB_TOKEN GH_TOKEN MATCHDESK_ALERT_GITHUB_TOKEN "
                "AZURE_CLIENT_SECRET AWS_ACCESS_KEY_ID"
            ),
            f"ExecStartPre={command}",
            f"ExecStart={command} --run --cycles {cycles} --interval {interval}",
            "Restart=always",
            "RestartSec=20s",
            "TimeoutStopSec=30s",
            "UMask=0077",
            "NoNewPrivileges=yes",
            "CapabilityBoundingSet=",
            "PrivateTmp=yes",
            "ProtectSystem=strict",
            "ProtectHome=yes",
            f"ReadWritePaths={state}",
            "RestrictAddressFamilies=AF_UNIX",
            "RestrictSUIDSGID=yes",
            "LockPersonality=yes",
            "MemoryMax=256M",
            "TasksMax=32",
            "StandardOutput=journal",
            "StandardError=journal",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    """Print only a reviewable unit; never call systemctl or write a file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--python", default="/usr/bin/python3")
    parser.add_argument("--cycles", type=int, default=1440)
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        unit = render_unit(
            source=args.source,
            source_sha=args.source_sha,
            state_dir=args.state_dir,
            python_path=args.python,
            cycles=args.cycles,
            interval=args.interval,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(unit, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
