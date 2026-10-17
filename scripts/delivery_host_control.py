#!/usr/bin/env python3
"""Opt-in local MatchDesk control-service preflight; coding is always disabled.

The default CLI only checks a pinned checkout and local storage. --run
permits bounded, restart-manager-friendly control-only cycles: recover
expired reservations and report the durable queue. It never launches Docker,
contacts GitHub, sends notifications, runs a model, or certifies a task.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SHA = re.compile(r"[0-9a-f]{40}\Z")
BLOCKED_CREDENTIALS = (
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "MATCHDESK_ALERT_GITHUB_TOKEN",
    "ANTHROPIC_API_KEY",
    "AZURE_CLIENT_SECRET",
    "AWS_ACCESS_KEY_ID",
)


def verify_control_host(
    source: Path,
    source_sha: str,
    database: Path,
    lock: Path,
    *,
    environment: dict[str, str] | None = None,
    effective_uid: int | None = None,
    runner=subprocess.run,
) -> dict[str, str]:
    """Deny privileged, mutable or mismatched local-only control service inputs.

    This is a readiness observation only. It does not create a SQLite database,
    lock file, systemd service or approved coding executor.
    """
    uid = os.geteuid() if effective_uid is None else effective_uid
    if sys.platform != "linux" or type(uid) is not int or uid <= 0:
        raise ValueError("Dedicated non-root Linux user required")
    if SHA.fullmatch(source_sha) is None:
        raise ValueError("Exact 40-character lowercase source SHA required")

    env = dict(os.environ if environment is None else environment)
    if any(env.get(name) for name in BLOCKED_CREDENTIALS):
        raise ValueError("Control service must not inherit cloud or GitHub credentials")

    checkout = source.resolve(strict=True)
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise ValueError("Existing Git checkout required")
    if not (checkout / "scripts" / "delivery_worker_loop.py").is_file():
        raise ValueError("Committed delivery scripts are missing")
    manifest = checkout / "docs" / "engineering" / "delivery-workstreams.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise ValueError("Expected a regular committed delivery manifest")

    if not database.is_absolute() or not lock.is_absolute():
        raise ValueError("State and lock paths must be absolute")
    if database.is_symlink() or lock.is_symlink():
        raise ValueError("State and lock files must never be symlinks")
    state_dir = database.parent.resolve(strict=True)
    if lock.parent.resolve(strict=True) != state_dir:
        raise ValueError("SQLite and exclusive lock must share one private directory")
    if state_dir == checkout or checkout in state_dir.parents:
        raise ValueError("Durable state cannot be inside the source checkout")
    if database.resolve() == lock.resolve():
        raise ValueError("SQLite and lock cannot refer to the same file")
    state_info = state_dir.stat()
    if (
        not stat.S_ISDIR(state_info.st_mode)
        or state_info.st_uid != uid
        or stat.S_IMODE(state_info.st_mode) & 0o077
    ):
        raise ValueError("State directory must be owned by the worker with mode 0700")
    for path in (database, lock):
        if path.exists():
            info = path.stat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != uid
                or stat.S_IMODE(info.st_mode) & 0o077
            ):
                raise ValueError("Existing state and lock files must be private regular files")

    child_env = {
        "PATH": os.defpath,
        "HOME": env.get("HOME", str(Path.home())),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }

    def checked(command: list[str]) -> str:
        """Use only bounded, local, read-only Git commands."""
        try:
            result = runner(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
                env=child_env,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("Could not verify immutable source checkout") from exc
        return result.stdout.strip()

    if checked(["git", "-C", str(checkout), "rev-parse", "HEAD"]) != source_sha:
        raise ValueError("Local source differs from the pinned approved SHA")
    if checked(["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("Tracked source has uncommitted changes")
    return {
        "mode": "LOCAL_CONTROL_PREFLIGHT_ONLY",
        "source_sha": source_sha,
        "coding_executor": "NOT_ACTIVATED",
        "github_write": "DISABLED",
        "notification_delivery": "DISABLED",
        "persistent_service": "NOT_STARTED_BY_PREFLIGHT",
    }


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    """Prevent a second control process from concurrently operating the ledger."""
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise ValueError("Lock file must be a private regular file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another local control supervisor holds the lock") from exc
        yield
    finally:
        os.close(fd)


def main() -> int:
    """Check readiness, or explicitly run control-only cycles under one lock."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--run", action="store_true", help="Opt-in: control-only, no executor")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()

    if not 1 <= args.cycles <= 1440 or not 1 <= args.interval <= 3600:
        parser.error("Cycles and intervals require fixed finite limits")
    if not args.run and args.cycles != 1:
        parser.error("Multiple cycles require explicit --run")

    os.umask(0o077)
    ready = verify_control_host(args.source, args.source_sha, args.db, args.lock)
    if not args.run:
        print(json.dumps(ready, sort_keys=True))
        return 0

    # No coding adapter is imported or available in this executable. The
    # manifest and SQLite coordinator are loaded only after the SHA preflight.
    from delivery_supervisor import Supervisor

    manifest_path = (
        args.source.resolve(strict=True)
        / "docs"
        / "engineering"
        / "delivery-workstreams.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with exclusive_lock(args.lock):
        for cycle in range(args.cycles):
            # Stop on any branch drift, permission change, or credentials.
            verify_control_host(args.source, args.source_sha, args.db, args.lock)
            coordinator = Supervisor(args.db, manifest)
            try:
                recovered = coordinator.recover()
                state = coordinator.status()
            finally:
                coordinator.close()
            print(
                json.dumps(
                    {
                        "mode": "LOCAL_CONTROL_ONLY_NO_CODING_EXECUTOR",
                        "cycle": cycle + 1,
                        "recovered_expired_leases": recovered,
                        "state": state,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if cycle + 1 < args.cycles:
                time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
