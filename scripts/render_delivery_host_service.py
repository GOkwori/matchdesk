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
    wsl_home_paths: bool = False,
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
    if state == checkout or checkout in state.parents or state in checkout.parents:
        raise ValueError("State directory must not overlap the source checkout")
    if not 1 <= cycles <= 1440 or not 1 <= interval <= 3600:
        raise ValueError("Finite cycle count and interval must be within bounds")

    # The default unit keeps /home inaccessible. Explicit WSL mode instead
    # masks all homes with a read-only tmpfs and restores only the minimum
    # reviewed source/interpreter paths (read-only) and state path (writable).
    # Do not replace this with ProtectHome=read-only, which exposes all homes.
    protected = (
        PurePosixPath("/home"),
        PurePosixPath("/root"),
        PurePosixPath("/run/user"),
    )
    paths = (checkout, executable, state)
    mounts: list[str] = []
    if wsl_home_paths:
        if len(checkout.parts) < 4 or checkout.parts[1] != "home":
            raise ValueError("WSL mode requires an explicitly scoped user-home checkout")
        home = PurePosixPath("/home") / checkout.parts[2]
        if any(path == home or home not in path.parents for path in paths):
            raise ValueError("WSL runtime paths must be inside the same user home")
        if executable.parent.name != "bin" or not executable.name.startswith("python3"):
            raise ValueError("WSL Python must use a separately installed bin/python3 runtime")
        # Include the managed interpreter's lib/ tree, but never bind the
        # user's home or a parent of the checkout or writable state.
        python_root = executable.parents[1]
        if python_root == home or home not in python_root.parents:
            raise ValueError("WSL Python root must be narrower than the home directory")
        if any(
            left == right or left in right.parents or right in left.parents
            for left, right in ((checkout, python_root), (state, python_root))
        ):
            raise ValueError("Python, checkout and writable state must not overlap")
        home_policy = "tmpfs"
        mounts = [
            f"BindReadOnlyPaths={checkout}",
            f"BindReadOnlyPaths={python_root}",
            f"BindPaths={state}",
        ]
    else:
        if any(root == path or root in path.parents for path in paths for root in protected):
            raise ValueError("Protected-home paths require explicit --wsl-home-paths")
        home_policy = "yes"

    # Only the previously reviewed, non-coding entrypoint may be invoked.
    script = checkout / "scripts" / "delivery_host_control.py"
    db = state / "state.sqlite3"
    lock = state / "control.lock"
    command = (
        f"{executable} -E -s -B {script} --source {checkout} --source-sha {source_sha} "
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
            f"ProtectHome={home_policy}",
            *mounts,
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
    parser.add_argument(
        "--wsl-home-paths",
        action="store_true",
        help="Explicitly bind only the reviewed WSL runtime and state paths",
    )
    args = parser.parse_args(argv)
    try:
        unit = render_unit(
            source=args.source,
            source_sha=args.source_sha,
            state_dir=args.state_dir,
            python_path=args.python,
            cycles=args.cycles,
            interval=args.interval,
            wsl_home_paths=args.wsl_home_paths,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(unit, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
