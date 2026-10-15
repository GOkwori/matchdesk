#!/usr/bin/env python3
"""Offline, opt-in sandbox adapter producing untrusted review-only patches.

There is no default agent binary, model account or background daemon. An operator
must independently approve and install the pinned worker image and local host.
The adapter never grants GitHub write, network, deployment or release authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

IMAGE = re.compile(r"[a-z0-9][a-z0-9_.:/-]*@sha256:[0-9a-f]{64}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
PATCH_PATH = re.compile(r"[A-Za-z0-9_./-]+\Z")
DIFF_HEADER = re.compile(r"diff --git a/([A-Za-z0-9_./-]+) b/([A-Za-z0-9_./-]+)\Z")
WORKER = re.compile(r"agent-[0-9a-f]{32}\Z")
ALLOWLIST = {
    "producer": ("backend/src/matchdesk/", "backend/tests/"),
    "audience": ("backend/src/matchdesk/", "backend/tests/"),
    "assurance": ("backend/tests/", "docs/evidence/"),
    "demo": ("apps/web/", "docs/competition/", "e2e/"),
}


@dataclass(frozen=True)
class WorkerResult:
    """Outcome returned by a sandbox, never independent qualification evidence."""

    state: str
    digest: str | None = None
    evidence_dir: str | None = None


def _safe_path(lane: str, value: str) -> bool:
    """Constrain a proposed file to a simple lane-scoped repository path."""
    return (
        lane in ALLOWLIST
        and PATCH_PATH.fullmatch(value) is not None
        and not value.startswith((".", "/"))
        and all(part not in ("", ".", "..") for part in value.split("/"))
        and any(value.startswith(prefix) for prefix in ALLOWLIST[lane])
        and not any(part in (".env", ".git", ".github", "__pycache__") for part in value.split("/"))
    )


def validate_patch(lane: str, patch: bytes) -> tuple[str, tuple[str, ...]]:
    """Deny binary, escape, symlink, deletion and cross-lane patch proposals."""
    if lane not in ALLOWLIST or not 0 < len(patch) <= 1_000_000 or b"\x00" in patch:
        raise ValueError("Empty, oversized or binary worker patch")
    try:
        source = patch.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Worker patch must be valid UTF-8") from exc
    files: list[str] = []
    active: str | None = None
    had_hunk = False
    for line in source.splitlines():
        if line.startswith("diff --git "):
            matched = DIFF_HEADER.fullmatch(line)
            if matched is None or matched[1] != matched[2] or not _safe_path(lane, matched[1]):
                raise ValueError("Unauthorized patch target or ambiguous rename")
            if active is not None and not had_hunk:
                raise ValueError("Patch file has no textual change")
            active = matched[1]
            files.append(active)
            had_hunk = False
        elif line.startswith(("GIT binary patch", "Binary files ", "rename ", "copy ")):
            raise ValueError("Binary, rename or copy operations are forbidden")
        elif line.startswith(("old mode ", "deleted file mode ", "new file mode 120000")):
            raise ValueError("Mode, deletion and symlink changes are forbidden")
        elif line.startswith("new file mode ") and line != "new file mode 100644":
            raise ValueError("Only regular new files are allowed")
        elif line.startswith(("--- ", "+++ ")):
            if active is None:
                raise ValueError("Path metadata without a file header")
            candidate = line[4:]
            expected = ("a/" if line.startswith("--- ") else "b/") + active
            if candidate != expected and not (line.startswith("--- ") and candidate == "/dev/null"):
                raise ValueError("Patch metadata changes an unauthorized path")
        elif line.startswith("@@ "):
            if active is None:
                raise ValueError("Hunk without file metadata")
            had_hunk = True
    if active is None or not had_hunk or len(files) > 40 or len(files) != len(set(files)):
        raise ValueError("Patch has missing or duplicate file hunks")
    return hashlib.sha256(patch).hexdigest(), tuple(files)


class OfflineDockerWorker:
    """Run an approved pinned image in an isolated, no-network Docker sandbox.

    Only proposed patch files leave the sandbox. A separate human/CI review is
    always required before integrating output into any protected branch.
    """

    def __init__(
        self,
        source: Path,
        source_sha: str,
        image: str,
        evidence_root: Path,
        *,
        timeout: int = 900,
    ) -> None:
        """Require immutable inputs and reject evidence inside the repository."""
        if IMAGE.fullmatch(image) is None or SHA.fullmatch(source_sha) is None:
            raise ValueError("Source and worker image must have immutable digests")
        if not 30 <= timeout <= 900 or not hasattr(os, "getuid"):
            raise ValueError("Worker requires Linux and a bounded execution budget")
        self.source = source.resolve(strict=True)
        self.evidence_root = evidence_root.resolve()
        if self.evidence_root == self.source or self.source in self.evidence_root.parents:
            raise ValueError("Evidence must be outside the source tree")
        if any("," in str(path) or "\n" in str(path) for path in (self.source, self.evidence_root)):
            raise ValueError("Unsupported Docker mount path")
        self.source_sha = source_sha
        self.image = image
        self.timeout = timeout

    def _snapshot(self, directory: Path) -> None:
        """Export exactly the pinned git tree and reject links or unsafe archives."""
        actual = subprocess.run(
            ["git", "-C", str(self.source), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout.strip()
        if actual != self.source_sha:
            raise ValueError("Local checkout SHA differs from approved work order")
        archive = directory.parent / "source.tar"
        with archive.open("wb") as stream:
            subprocess.run(
                ["git", "-C", str(self.source), "archive", "--format=tar", self.source_sha],
                stdout=stream,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=60,
            )
        with tarfile.open(archive) as content:
            total = 0
            for entry in content:
                path = PurePosixPath(entry.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not (entry.isfile() or entry.isdir())
                ):
                    raise ValueError("Unsafe tracked source archive")
                total += entry.size
                if total > 200_000_000:
                    raise ValueError("Source archive exceeds sandbox limit")
            content.extractall(directory, filter="data")

    def _command(self, source: Path, output: Path, name: str) -> list[str]:
        """Build a command with no network, privileges, credentials or source writes."""
        return [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--name",
            name,
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges=true",
            "--pids-limit=64",
            "--memory=768m",
            "--cpus=1",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=32m",
            "--mount",
            f"type=bind,src={source},dst=/source,readonly",
            "--mount",
            f"type=bind,src={output},dst=/out",
            "--workdir",
            "/source",
            self.image,
            "/usr/local/bin/matchdesk-agent",
            "--work-order",
            "/out/work-order.json",
        ]

    def execute(self, lane: str, worker_id: str) -> WorkerResult:
        """Run one offline worker and retain only a valid, untrusted patch proposal."""
        if lane not in ALLOWLIST or WORKER.fullmatch(worker_id) is None:
            return WorkerResult("BLOCKED")
        container_name = f"matchdesk-{worker_id}"
        try:
            self.evidence_root.mkdir(parents=True, exist_ok=True)
            evidence = self.evidence_root / worker_id
            evidence.mkdir(mode=0o700)
            with tempfile.TemporaryDirectory(prefix="matchdesk-work-") as root:
                workspace = Path(root) / "source"
                workspace.mkdir()
                self._snapshot(workspace)
                order = {
                    "repository": "GOkwori/matchdesk",
                    "source_sha": self.source_sha,
                    "lane": lane,
                    "allowed_paths": ALLOWLIST[lane],
                    "authority": "PROPOSE_PATCH_ONLY_NO_MERGE",
                }
                (evidence / "work-order.json").write_text(
                    json.dumps(order, sort_keys=True) + "\n", encoding="utf-8"
                )
                try:
                    result = subprocess.run(
                        self._command(workspace, evidence, container_name),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=self.timeout,
                        check=False,
                        env={"PATH": os.defpath},
                    )
                except subprocess.TimeoutExpired:
                    return WorkerResult("BLOCKED")
                finally:
                    # A timed-out Docker client may leave a container running.
                    subprocess.run(
                        ["docker", "rm", "-f", container_name],
                        capture_output=True,
                        timeout=20,
                        check=False,
                        env={"PATH": os.defpath},
                    )
                if result.returncode != 0:
                    return WorkerResult("BLOCKED")
                patch_path = evidence / "changes.patch"
                if not patch_path.is_file() or patch_path.is_symlink():
                    return WorkerResult("BLOCKED")
                digest, files = validate_patch(lane, patch_path.read_bytes())
                verified = subprocess.run(
                    ["git", "apply", "--check", str(patch_path)],
                    cwd=workspace,
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
                if verified.returncode != 0:
                    return WorkerResult("BLOCKED")
                (evidence / "receipt.json").write_text(
                    json.dumps(
                        {
                            "state": "REVIEW_REQUIRED",
                            "source_sha": self.source_sha,
                            "lane": lane,
                            "patch_sha256": digest,
                            "paths": files,
                        },
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return WorkerResult("REVIEW_REQUIRED", digest, str(evidence))
        except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError):
            return WorkerResult("BLOCKED")
