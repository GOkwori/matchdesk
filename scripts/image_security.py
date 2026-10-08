"""Collect and gate Trivy reports for the exact images used by runtime tests.

Collection deliberately retains all severities and unfixed findings. A successful
scanner process is not a passing security gate: identity, inventory, freshness and
findings are checked independently, with no vulnerability exceptions in this version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCANNER_VERSION = "0.75.0"
SERVICES = {"api", "web", "postgres"}
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def read_object(path: Path) -> dict:
    """Reject absent, linked, oversized or non-object evidence instead of defaulting clean."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 50_000_000:
        raise ValueError(f"Invalid evidence file: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an evidence object: {path.name}")
    return value


def file_hash(path: Path) -> str:
    """Hash retained bytes, including large database files, without loading them at once."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def timestamp(value: str) -> datetime:
    """Require an explicit timezone so database freshness is independent of runner locale."""
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Evidence timestamp must include a timezone")
    return result


def assess_report(report: dict, image_id: str, service: str) -> dict:
    """Validate identity and real package coverage before counting every reported finding."""
    if service not in SERVICES or not DIGEST.fullmatch(image_id):
        raise ValueError("Unexpected service or image identity")
    if report.get("SchemaVersion") != 2 or report.get("ArtifactType") != "container_image":
        raise ValueError("Expected a version-2 container-image report")
    if report.get("Trivy", {}).get("Version") != SCANNER_VERSION:
        raise ValueError("Unexpected scanner version")
    metadata = report.get("Metadata", {})
    if metadata.get("ImageID") != image_id:
        raise ValueError("Scanned image differs from runtime-tested image")
    operating_system = metadata.get("OS", {})
    os_family = operating_system.get("Family")
    if os_family not in {"debian", "alpine"} or not operating_system.get("Name"):
        raise ValueError("Expected an identified Debian or Alpine runtime, not an unknown OS")
    if operating_system.get("EOSL", False) is not False:
        raise ValueError("End-of-life runtime cannot pass the image gate")
    results = report.get("Results")
    if not isinstance(results, list) or not results:
        raise ValueError("Missing package results")
    inventory: dict[str, set[str]] = {"os-pkgs": set(), "lang-pkgs": set()}
    findings = []
    for result in results:
        if not isinstance(result, dict) or result.get("Class") not in inventory:
            raise ValueError("Unexpected result class in vulnerability-only report")
        packages = result.get("Packages")
        if not isinstance(packages, list) or not packages:
            raise ValueError("Missing package inventory; zero findings alone is insufficient")
        for package in packages:
            if (
                not isinstance(package, dict)
                or not package.get("Name")
                or not package.get("Version")
            ):
                raise ValueError("Incomplete package identity")
            inventory[result["Class"]].add(package["Name"].lower().replace("_", "-"))
        vulnerabilities = result.get("Vulnerabilities", [])
        if not isinstance(vulnerabilities, list):
            raise ValueError("Malformed vulnerability collection")
        if result.get("ExperimentalModifiedFindings"):
            raise ValueError("Modified or suppressed findings require a separate review")
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict) or not vulnerability.get("VulnerabilityID"):
                raise ValueError("Incomplete vulnerability identity")
            findings.append(
                {
                    "target": result["Target"],
                    "class": result["Class"],
                    "id": vulnerability["VulnerabilityID"],
                    "package": vulnerability.get("PkgName"),
                    "installed": vulnerability.get("InstalledVersion"),
                    "fixed": vulnerability.get("FixedVersion", ""),
                    "severity": vulnerability.get("Severity", "UNKNOWN"),
                    "status": vulnerability.get("Status", "unknown"),
                }
            )
    os_markers = {
        "debian": {"dpkg", "libc6"},
        "alpine": {"apk-tools", "musl"},
    }
    if not os_markers[os_family].issubset(inventory["os-pkgs"]):
        raise ValueError("Expected OS packages were not inventoried")
    required = {"api": {"fastapi", "starlette", "anyio"}, "web": {"next", "react"}}
    if service in required and not required[service].issubset(inventory["lang-pkgs"]):
        raise ValueError("Runtime application packages were not inventoried")
    if service == "postgres":
        postgres_marker = "postgresql-16" if os_family == "debian" else ".postgresql-rundeps"
        if postgres_marker not in inventory["os-pkgs"]:
            raise ValueError("PostgreSQL runtime package set was not inventoried")
    return {
        "service": service,
        "image_id": image_id,
        "status": "FAIL" if findings else "PASS",
        "os_packages": len(inventory["os-pkgs"]),
        "language_packages": len(inventory["lang-pkgs"]),
        "finding_count": len(findings),
        "findings": findings,
    }


def evaluate_bundle(root: Path, source: str, run_id: str, now: datetime) -> dict:
    """Fail closed for stale, partial, altered or source-mismatched scan collections."""
    manifest = read_object(root / "manifest.json")
    if manifest["source_commit"] != source or manifest["run_id"] != run_id:
        raise ValueError("Scan collection belongs to another source or workflow")
    if manifest["scanner_version"] != SCANNER_VERSION:
        raise ValueError("Scanner does not match the reviewed version")
    for name, digest in manifest["files"].items():
        if name not in {
            "runtime-checks.json",
            "db-metadata.json",
            "api.json",
            "web.json",
            "postgres.json",
        }:
            raise ValueError("Unapproved evidence filename")
        if file_hash(root / name) != digest:
            raise ValueError("Retained evidence bytes changed")
    if set(manifest["files"]) != {
        "runtime-checks.json",
        "db-metadata.json",
        "api.json",
        "web.json",
        "postgres.json",
    }:
        raise ValueError("Incomplete image evidence collection")
    database = read_object(root / "db-metadata.json")
    if database.get("Version") != 2:
        raise ValueError("Unsupported vulnerability database schema")
    age = now - timestamp(database["UpdatedAt"])
    if age < -timedelta(minutes=5) or age > timedelta(hours=48):
        raise ValueError("Vulnerability database timestamp is stale or in the future")
    download_age = now - timestamp(database["DownloadedAt"])
    if download_age < -timedelta(minutes=5) or download_age > timedelta(hours=2):
        raise ValueError("Vulnerability database was not freshly downloaded for this run")
    # Trivy's NextUpdate is the publisher's intended refresh schedule. The upstream
    # database can legitimately be served after that time. A successful current-run
    # download plus a bounded UpdatedAt age is the security control; overdue publisher
    # metadata is retained as an explicit warning rather than misreported as a clean refresh.
    database_current = timestamp(database["NextUpdate"]) >= now
    if not re.fullmatch(r"[0-9a-f]{64}", manifest["database_sha256"]):
        raise ValueError("Missing vulnerability database byte identity")
    runtime = read_object(root / "runtime-checks.json")
    if runtime.get("source_commit") != source or runtime.get("status") != "PASS":
        raise ValueError("No passing runtime checks for the proposed source")
    images = {item["service"]: item["image_id"] for item in runtime["containers"]}
    if set(images) != SERVICES or len(runtime["containers"]) != len(SERVICES):
        raise ValueError("Missing or duplicate runtime image")
    if set(manifest["scans"]) != SERVICES:
        raise ValueError("Not every runtime image was scanned")
    assessments = []
    for service in sorted(SERVICES):
        scan = manifest["scans"][service]
        if type(scan.get("exit_code")) is not int or scan["exit_code"] != 0:
            raise ValueError("A scanner failed; partial output cannot pass")
        if scan["image_id"] != images[service]:
            raise ValueError("Scan identity differs from the tested runtime")
        assessments.append(
            assess_report(read_object(root / f"{service}.json"), images[service], service)
        )
    return {
        "source_commit": source,
        "run_id": run_id,
        "checked_at": now.isoformat(),
        "policy": "all-reported-vulnerabilities-block; no exclusions; unfixed included",
        "database_status": "CURRENT" if database_current else "UPSTREAM_REFRESH_OVERDUE",
        "status": "PASS" if all(item["status"] == "PASS" for item in assessments) else "FAIL",
        "images": assessments,
    }


def collect(root: Path, scanner: str, cache: Path) -> None:
    """Scan the running, tested images without exporting container secrets or changing them."""
    root.mkdir(parents=True, exist_ok=True)
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    project = os.environ["COMPOSE_PROJECT_NAME"]
    if not re.fullmatch(r"matchdesk-it-[0-9]+-[0-9]+", project):
        raise ValueError("Only the isolated integration project may be inspected")
    runtime_path = Path("artifacts/integration/runtime-checks.json")
    runtime = read_object(runtime_path)
    if runtime["source_commit"] != source or runtime["project"] != project:
        raise ValueError("Runtime evidence does not match the current checkout/project")
    shutil.copyfile(runtime_path, root / "runtime-checks.json")
    shutil.copyfile(cache / "db/metadata.json", root / "db-metadata.json")
    manifest = {
        "source_commit": source,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "scanner_version": SCANNER_VERSION,
        "database_sha256": file_hash(cache / "db/trivy.db"),
        "scans": {},
        "files": {},
    }
    config = root / "scanner.yaml"
    config.write_text("{}\n", encoding="utf-8")
    # Collection uses a fixed scanner/config/database and no repository-level ignore file.
    # Registry fallback is disabled: a missing local image must not scan a substitute.
    for item in runtime["containers"]:
        service, image_id = item["service"], item["image_id"]
        if (
            service not in SERVICES
            or not DIGEST.fullmatch(image_id)
            or not re.fullmatch(r"[0-9a-f]{64}", item["id"])
        ):
            raise ValueError("Unexpected runtime identity")
        actual = subprocess.check_output(
            [
                "docker",
                "inspect",
                "--format",
                "{{.Image}}",
                item["id"],
            ],
            text=True,
        ).strip()
        if actual != image_id:
            raise ValueError("Runtime image changed after integration checks")
        command = [
            scanner,
            "--config",
            str(config),
            "--cache-dir",
            str(cache),
            "image",
            "--image-src",
            "docker",
            "--scanners",
            "vuln",
            "--pkg-types",
            "os,library",
            "--format",
            "json",
            "--list-all-pkgs",
            "--ignorefile",
            "/dev/null",
            "--ignore-unfixed=false",
            "--severity",
            "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL",
            "--skip-db-update",
            "--exit-code",
            "0",
            "--exit-on-eol",
            "2",
            "--timeout",
            "5m",
            "--output",
            str(root / f"{service}.json"),
            image_id,
        ]
        started = datetime.now(timezone.utc).isoformat()
        # A vulnerability result is preserved for the independent gate; process errors
        # remain explicit. The collector has no cloud credentials or write token.
        with (root / f"{service}.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=330)
        manifest["scans"][service] = {
            "image_id": image_id,
            "exit_code": result.returncode,
            "command": command,
            "started_at": started,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    for path in sorted(root.glob("*.json")):
        if path.name != "manifest.json":
            manifest["files"][path.name] = file_hash(path)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    """Collect image evidence or enforce the independent gate, returning nonzero on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("collect", "gate"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--scanner")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--source")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.mode == "collect":
        if not args.scanner or not args.cache:
            parser.error("collect requires --scanner and --cache")
        collect(args.directory, args.scanner, args.cache)
        return 0
    if not args.source or not args.run_id:
        parser.error("gate requires --source and --run-id")
    try:
        verdict = evaluate_bundle(
            args.directory, args.source, args.run_id, datetime.now(timezone.utc)
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        verdict = {"status": "FAIL", "reason": str(error), "source_commit": args.source}
    args.directory.mkdir(parents=True, exist_ok=True)
    (args.directory / "verdict.json").write_text(
        json.dumps(verdict, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
