"""Execute the available foundation checks and retain source-bound, honest results.

An incomplete environment cannot produce a passing Phase 0 gate. Local results are
still useful and are retained alongside explicit unexecuted dependencies and checks.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
            "node_modules", ".next", "artifacts"}


def source_inventory(root: Path) -> dict[str, str]:
    """Hash source/configuration/docs while excluding output and credentials.

    Evidence excludes itself to avoid a self-referential hash. The entire initial
    source manifest is retained so a moved ZIP can be checked without Git metadata.
    """
    inventory: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED for part in path.relative_to(root).parts):
            continue
        name = path.relative_to(root).as_posix()
        if name.startswith("docs/evidence/") or path.name.startswith((".env", ".coverage")):
            continue
        if path.suffix in (".pyc", ".tsbuildinfo"):
            continue
        inventory[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return inventory


def run_check(name: str, command: list[str], folder: Path, environment: dict[str, str]) -> dict[str, object]:
    """Capture a bounded real execution; failures and timeouts remain failures."""
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=120, check=False)
        output = completed.stdout
        status = "PASS" if completed.returncode == 0 else "FAIL"
        code: int | None = completed.returncode
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        output = str(error)
        status = "BLOCKED" if isinstance(error, FileNotFoundError) else "FAIL"
        code = None
    (folder / f"{name}.log").write_text(output, encoding="utf-8")
    return {"name": name, "command": command, "status": status, "exit_code": code,
            "elapsed_seconds": round(time.monotonic() - started, 3), "log": f"{name}.log"}


def package_version(name: str) -> str | None:
    """Record an installed distribution, without implying that the target lock resolved."""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> int:
    """Write a dated run and return nonzero while any required gate is incomplete."""
    started_at = datetime.now(UTC).isoformat()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-phase0-" + uuid4().hex[:6]
    folder = ROOT / "docs/evidence" / run_id
    folder.mkdir(parents=True)
    inventory = source_inventory(ROOT)
    inventory_json = json.dumps(inventory, sort_keys=True, separators=(",", ":"))
    tree_digest = hashlib.sha256(inventory_json.encode()).hexdigest()
    (folder / "source-manifest.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    commit = revision.stdout.strip() if revision.returncode == 0 else None
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "backend/src") + os.pathsep + str(ROOT)
    checks = [
        run_check("contracts", [sys.executable, "-m", "scripts.export_contracts"], folder, environment),
        run_check("comments", [sys.executable, "-m", "scripts.check_comments"], folder, environment),
        run_check("documentation", [sys.executable, "-m", "scripts.check_docs"], folder, environment),
        run_check("pytest", [sys.executable, "-m", "pytest", f"--junitxml={folder / 'junit.xml'}",
                             "--cov=matchdesk", f"--cov-report=json:{folder / 'coverage.json'}",
                             "--cov-report=term-missing"], folder, environment),
        run_check("api-http-smoke", [sys.executable, "-m", "scripts.smoke_api"], folder, environment),
        run_check("typescript-syntax", ["node", "scripts/check_ts_syntax.cjs"], folder, environment),
        run_check("next-config-syntax", ["node", "--check", "apps/web/next.config.mjs"], folder, environment),
    ]
    blockers = [
        "GitHub target repository access/publication and hosted CI not established",
        "Python 3.12 target runtime has not been qualified",
        "Reviewed uv.lock and package-lock.json are absent; registry DNS is unavailable",
        "Ruff and mypy have not run; frontend dependency-aware type checking has not run",
        "Docker/real PostgreSQL topology and actual Next.js/browser tests have not run",
        "Branch protection, secret/dependency/container scans and action-SHA pinning not qualified",
    ]
    # Detect accidental source mutation during collection, including baseline rewrites.
    stable = inventory == source_inventory(ROOT)
    if not stable:
        blockers.append("Source changed during evidence collection")
    status = "FAIL" if any(check["status"] == "FAIL" for check in checks) or not stable else "BLOCKED"
    manifest = {
        "schema_version": "1.0", "run_id": run_id, "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(), "gate_status": status,
        "source_commit": commit, "source_commit_scope": "local_only",
        "source_tree_sha256": tree_digest, "source_stable_during_run": stable,
        "source_manifest_excludes": ["docs/evidence", "credentials", "dependencies", "runtime output"],
        "python": platform.python_version(), "platform": platform.platform(),
        "model_mode": "not_connected", "cloud_resources_created": False,
        "packages": {name: package_version(name) for name in (
            "fastapi", "pydantic", "uvicorn", "pytest", "pytest-cov", "httpx", "jsonschema", "ruff", "mypy",
        )}, "checks": checks, "blockers": blockers,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lines = ["# Phase 0 execution evidence", "", f"Gate: **{status}**. This is not a production release.", "",
             f"Run: `{run_id}`", f"Started: {started_at}", f"Finished: {manifest['finished_at']}",
             f"Local source commit: `{commit}`", f"Source manifest SHA-256: `{tree_digest}`", "",
             f"Runtime: Python {platform.python_version()}; models not connected; no Azure provisioning.", "",
             "| Check | Actual result | Duration (seconds) |", "|---|---|---|"]
    lines.extend(f"| {c['name']} | {c['status']} | {c['elapsed_seconds']} |" for c in checks)
    lines.extend(["", "## Unresolved gates", "", *[f"- {item}" for item in blockers], "",
                  "Coverage applies only to the implemented Python foundation. It does not measure",
                  "whole-product completion, frontend quality or the correctness of future algorithms.", ""])
    (folder / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "docs/evidence/latest.json").write_text(json.dumps({"run_id": run_id, "status": status}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": status, "checks": checks}, indent=2))
    return 1 if status == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
