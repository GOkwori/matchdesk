"""Fail-closed activation preflight for an existing, operator-owned local host.

This script only validates an already installed offline Docker runtime. It does
not install Docker, launch a worker, send alerts, request credentials, create
billable resources or grant GitHub permissions.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

from delivery_agent_loop import IMAGE, SHA

RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def _outside_source(source: Path, value: Path) -> bool:
    """Reject repository-local state, including resolved symlink escapes."""
    resolved = value.resolve()
    return resolved != source and source not in resolved.parents


def verify_local_activation(
    *,
    source: Path,
    source_sha: str,
    image: str,
    database: Path,
    evidence: Path,
    runner: RunCommand = subprocess.run,
    environment: dict[str, str] | None = None,
    effective_uid: int | None = None,
) -> dict[str, str]:
    """Verify immutable source, clean checkout and rootless offline Docker.

    A successful result establishes only *local readiness*, never that an
    autonomous coding agent is installed, its output is accepted or a service
    is already running. No network calls, paid services or git writes occur.
    """
    if sys.platform != "linux" or not hasattr(os, "geteuid"):
        raise ValueError("Only a Linux local host may run the offline service")
    uid = os.geteuid() if effective_uid is None else effective_uid
    if type(uid) is not int or uid <= 0:
        raise ValueError("Run as an unprivileged local user, not root")
    if SHA.fullmatch(source_sha) is None or IMAGE.fullmatch(image) is None:
        raise ValueError("Source SHA and Docker image digest must be pinned")

    checkout = source.resolve(strict=True)
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise ValueError("Expected an existing local Git checkout")
    if (
        not _outside_source(checkout, database)
        or not _outside_source(checkout, evidence)
        or database.resolve() == evidence.resolve()
    ):
        raise ValueError("Durable state and patch evidence must be outside Git")
    if database.is_symlink() or evidence.is_symlink():
        raise ValueError("State and evidence paths must not be symlinks")

    env = dict(os.environ if environment is None else environment)
    allowed_socket = f"unix:///run/user/{uid}/docker.sock"
    if env.get("DOCKER_HOST", allowed_socket) != allowed_socket:
        raise ValueError("Only the local rootless Docker socket is permitted")
    if env.get("DOCKER_CONTEXT", "") not in ("", "default", "rootless"):
        raise ValueError("Remote or unknown Docker context not authorised")
    if env.get("DOCKER_TLS_VERIFY") or env.get("DOCKER_CERT_PATH"):
        raise ValueError("Remote Docker TLS configuration not authorised")
    if any(env.get(name) for name in ("OPENAI_API_KEY", "GITHUB_TOKEN", "GH_TOKEN")):
        raise ValueError("Offline worker must not inherit cloud or GitHub credentials")

    # Keep child commands free of tokens and arbitrary environment overrides.
    sanitized = {
        "PATH": os.defpath,
        "HOME": env.get("HOME", str(Path.home())),
        "DOCKER_HOST": allowed_socket,
        "DOCKER_CONTEXT": env.get("DOCKER_CONTEXT", "default"),
    }

    def checked(command: list[str]) -> str:
        """Run bounded local read-only checks and expose no subprocess stderr."""
        try:
            result = runner(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
                env=sanitized,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("Required local runtime preflight failed") from exc
        return result.stdout.strip()

    if checked(["git", "-C", str(checkout), "rev-parse", "HEAD"]) != source_sha:
        raise ValueError("Local checkout does not match the approved source SHA")
    if checked(["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("Local checkout has uncommitted tracked changes")

    try:
        security = json.loads(
            checked(["docker", "info", "--format", "{{json .SecurityOptions}}"])
        )
        image_digests = json.loads(
            checked(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image])
        )
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Could not verify local Docker daemon and image metadata") from exc
    if not isinstance(security, list) or "name=rootless" not in security:
        raise ValueError("Rootless Docker daemon is mandatory")
    if not isinstance(image_digests, list) or image not in image_digests:
        raise ValueError("The exact approved image digest is not installed locally")

    return {
        "mode": "LOCAL_OFFLINE_PREFLIGHT_ONLY",
        "source_sha": source_sha,
        "image": image,
        "docker": "ROOTLESS_LOCAL_DIGEST_VERIFIED",
        "coding_agent": "NOT_VERIFIED",
        "persistent_service": "NOT_STARTED",
    }
