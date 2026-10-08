"""Negative controls for the image gate; these are synthetic reports, not scan evidence."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.image_security import assess_report, evaluate_bundle, file_hash, timestamp

IMAGE = "sha256:" + "a" * 64
NOW = datetime(2026, 10, 8, 10, 30, tzinfo=timezone.utc)


def sample_report(service: str = "api") -> dict:
    """Construct only enough explicitly fictional scanner data to exercise policy code."""
    os_names = ["dpkg", "libc6", "postgresql-16"]
    language_names = ["fastapi", "starlette", "anyio"] if service == "api" else ["next", "react"]
    return {
        "SchemaVersion": 2,
        "ArtifactType": "container_image",
        "Trivy": {"Version": "0.75.0"},
        "Metadata": {"ImageID": IMAGE, "OS": {"Family": "debian", "Name": "12"}},
        "Results": [
            {
                "Target": "synthetic-os-inventory",
                "Class": "os-pkgs",
                "Packages": [{"Name": name, "Version": "test-version"} for name in os_names],
            },
            {
                "Target": "synthetic-application-inventory",
                "Class": "lang-pkgs",
                "Packages": [{"Name": name, "Version": "test-version"} for name in language_names],
            },
        ],
    }


def sample_bundle(root: Path) -> None:
    """Write a closed synthetic evidence set with reproducible identities for negative tests."""
    runtime = {
        "source_commit": "test-source",
        "status": "PASS",
        "containers": [{"service": name, "image_id": IMAGE} for name in ("api", "web", "postgres")],
    }
    database = {
        "Version": 2,
        "UpdatedAt": "2026-10-08T09:00:00Z",
        "NextUpdate": "2026-10-08T15:00:00Z",
    }
    values = {"runtime-checks.json": runtime, "db-metadata.json": database}
    values.update({f"{name}.json": sample_report(name) for name in ("api", "web", "postgres")})
    for name, value in values.items():
        (root / name).write_text(json.dumps(value))
    manifest = {
        "source_commit": "test-source",
        "run_id": "42",
        "scanner_version": "0.75.0",
        "database_sha256": "b" * 64,
        "files": {name: file_hash(root / name) for name in values},
        "scans": {name: {"image_id": IMAGE, "exit_code": 0} for name in ("api", "web", "postgres")},
    }
    (root / "manifest.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize("service", ["api", "web", "postgres"])
def test_real_inventory_is_required_even_for_zero_findings(service: str) -> None:
    """A correctly identified populated report may pass for each required service."""
    result = assess_report(sample_report(service), IMAGE, service)
    assert result["status"] == "PASS"
    assert result["os_packages"] == 3


@pytest.mark.parametrize("severity", ["UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"])
@pytest.mark.parametrize("fixed", ["", "next-version"])
def test_all_findings_block_including_unfixed(severity: str, fixed: str) -> None:
    """Neither low severity nor the absence of a vendor patch silently exempts a finding."""
    report = sample_report()
    report["Results"][0]["Vulnerabilities"] = [
        {
            "VulnerabilityID": "TEST-NOT-A-REAL-ADVISORY",
            "PkgName": "libc6",
            "InstalledVersion": "test-version",
            "FixedVersion": fixed,
            "Severity": severity,
        }
    ]
    result = assess_report(report, IMAGE, "api")
    assert result["status"] == "FAIL"
    assert result["findings"][0]["fixed"] == fixed


@pytest.mark.parametrize(
    "defect", ["empty", "wrong-image", "eol", "no-os", "no-app", "modified", "malformed"]
)
def test_incomplete_or_modified_reports_cannot_appear_clean(defect: str) -> None:
    """Removing evidence or modifying findings must fail before a zero-finding claim."""
    report = sample_report()
    if defect == "empty":
        report["Results"] = []
    elif defect == "wrong-image":
        report["Metadata"]["ImageID"] = "sha256:" + "c" * 64
    elif defect == "eol":
        report["Metadata"]["OS"]["EOSL"] = True
    elif defect == "no-os":
        report["Results"].pop(0)
    elif defect == "no-app":
        report["Results"].pop()
    elif defect == "modified":
        report["Results"][0]["ExperimentalModifiedFindings"] = [{"Status": "ignored"}]
    else:
        report["Results"][0]["Vulnerabilities"] = "not-a-list"
    with pytest.raises(ValueError):
        assess_report(report, IMAGE, "api")


def test_bundle_requires_all_three_images_and_matching_source(tmp_path: Path) -> None:
    """The gate binds a complete collection to the expected source and workflow run."""
    sample_bundle(tmp_path)
    result = evaluate_bundle(tmp_path, "test-source", "42", NOW)
    assert result["status"] == "PASS"
    assert len(result["images"]) == 3
    with pytest.raises(ValueError, match="another source"):
        evaluate_bundle(tmp_path, "different-source", "42", NOW)
    with pytest.raises(ValueError, match="another source"):
        evaluate_bundle(tmp_path, "test-source", "43", NOW)


@pytest.mark.parametrize(
    "defect", ["missing", "tampered", "scanner-error", "boolean-exit", "missing-image"]
)
def test_bundle_rejects_incomplete_or_failed_scans(tmp_path: Path, defect: str) -> None:
    """Partial output, altered bytes and failed scanner execution are not passing scans."""
    sample_bundle(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if defect == "missing":
        (tmp_path / "web.json").unlink()
    elif defect == "tampered":
        (tmp_path / "web.json").write_text("{}")
    elif defect == "scanner-error":
        manifest["scans"]["web"]["exit_code"] = 1
    elif defect == "boolean-exit":
        manifest["scans"]["web"]["exit_code"] = False
    else:
        manifest["scans"].pop("postgres")
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError)):
        evaluate_bundle(tmp_path, "test-source", "42", NOW)


@pytest.mark.parametrize("date", ["2026-10-05T10:00:00Z", "2026-10-10T10:00:00Z"])
def test_database_must_be_fresh_and_not_future_dated(tmp_path: Path, date: str) -> None:
    """A cached or future-dated database cannot establish current security evidence."""
    sample_bundle(tmp_path)
    path = tmp_path / "db-metadata.json"
    database = json.loads(path.read_text())
    database["UpdatedAt"] = date
    path.write_text(json.dumps(database))
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][path.name] = file_hash(path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="stale or in the future"):
        evaluate_bundle(tmp_path, "test-source", "42", NOW)


def test_timezone_and_input_immutability() -> None:
    """Policy evaluation must not mutate reports or interpret naive timestamps as local time."""
    report = sample_report()
    original = copy.deepcopy(report)
    assess_report(report, IMAGE, "api")
    assert report == original
    with pytest.raises(ValueError, match="timezone"):
        timestamp("2026-10-08T10:30:00")


@pytest.mark.parametrize("with_finding", [False, True])
def test_overdue_refresh_blocks_without_hiding_findings(tmp_path: Path, with_finding: bool) -> None:
    """A fresh download of overdue metadata is still blocked and must retain image findings."""
    sample_bundle(tmp_path)
    path = tmp_path / "db-metadata.json"
    database = json.loads(path.read_text())
    database["NextUpdate"] = "2026-10-08T09:30:00Z"
    path.write_text(json.dumps(database))
    if with_finding:
        image_path = tmp_path / "api.json"
        report = json.loads(image_path.read_text())
        report["Results"][0]["Vulnerabilities"] = [
            {"VulnerabilityID": "TEST-RETAINED-FINDING", "Severity": "HIGH"}
        ]
        image_path.write_text(json.dumps(report))
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for name in ("db-metadata.json", "api.json"):
        manifest["files"][name] = file_hash(tmp_path / name)
    manifest_path.write_text(json.dumps(manifest))
    result = evaluate_bundle(tmp_path, "test-source", "42", NOW)
    assert result["status"] == "FAIL"
    assert result["database_status"] == "REFRESH_OVERDUE"
    assert len(result["images"]) == 3
    assert result["images"][0]["finding_count"] == int(with_finding)
