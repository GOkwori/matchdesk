#!/usr/bin/env python3
"""Read-only, fail-closed delivery planner for the MatchDesk competition build.

The planner observes GitHub issues and exact development-commit CI. It never
dispatches a coding model, edits an issue, merges a PR, spends money or deploys.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY = "GOkwori/matchdesk"
DEFAULT_MANIFEST = Path("docs/engineering/delivery-workstreams.json")
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")


def validate_manifest(data: dict[str, Any]) -> dict[str, Any]:
    """Reject unexpected repository targets, cycles and malformed task records."""
    if data.get("schema_version") != 1 or data.get("repository") != REPOSITORY:
        raise ValueError("Invalid manifest schema or repository identity")
    if data.get("development_branch") != "development":
        raise ValueError("Only the protected development reference can be inspected")
    if data.get("production_branch") != "main":
        raise ValueError("Unexpected protected production branch")
    if data.get("max_parallel") != 4:
        raise ValueError("Parallel lane limit must remain four")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Manifest must contain tasks")
    ids: set[str] = set()
    issues: set[int] = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Malformed task")
        task_id = task.get("id")
        issue = task.get("issue")
        if not isinstance(task_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", task_id):
            raise ValueError("Unsafe task ID")
        if task_id in ids or type(issue) is not int or issue < 1 or issue in issues:
            raise ValueError("Duplicate or invalid task ID/issue")
        if task.get("kind") not in ("engineering", "human"):
            raise ValueError("Unexpected task kind")
        if not isinstance(task.get("depends_on"), list):
            raise ValueError("Expected dependency list")
        if not isinstance(task.get("acceptance"), str) or not task["acceptance"].strip():
            raise ValueError("Missing acceptance conditions")
        ids.add(task_id)
        issues.add(issue)
    by_id = {item["id"]: item for item in tasks}
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(task_id: str) -> None:
        """Walk dependency edges to reject unknown targets and cycles."""
        if task_id in visiting:
            raise ValueError("Cyclic delivery dependency")
        if task_id in visited:
            return
        visiting.add(task_id)
        for parent in by_id[task_id]["depends_on"]:
            if not isinstance(parent, str) or parent not in by_id:
                raise ValueError("Unknown delivery dependency")
            if parent == task_id:
                raise ValueError("Self dependency")
            visit(parent)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in by_id:
        visit(task_id)
    if sum(item["kind"] == "engineering" for item in tasks) > data["max_parallel"]:
        raise ValueError("Unbounded engineering concurrency")
    for field in ("required_workflows", "required_integration_checks"):
        values = data.get(field)
        if not isinstance(values, list) or not values:
            raise ValueError(f"Missing mandatory gate group: {field}")
        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError("Invalid mandatory gate name")
        if len(values) != len(set(values)):
            raise ValueError("Duplicate mandatory gate")
    return data


def github_get(relative_path: str, token: str) -> dict[str, Any]:
    """Fetch one predetermined repository API path with no write authority."""
    if not token:
        raise ValueError("GITHUB_TOKEN is required for live, authoritative status")
    if not re.fullmatch(r"[A-Za-z0-9_/?=&.%-]+", relative_path):
        raise ValueError("Unsafe GitHub request path")
    req = Request(
        f"https://api.github.com/repos/{REPOSITORY}/{relative_path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "matchdesk-readonly-delivery-orchestrator",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=15) as response:
            body = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub read failed for {relative_path}: {exc}") from exc
    if not isinstance(body, dict):
        raise ValueError("Unexpected GitHub API document")
    return body


def task_state(task: dict[str, Any], issue: dict[str, Any] | None) -> str:
    """Never call a closed issue delivered or a human gate automatically passed."""
    if issue is None:
        return "UNVERIFIED"
    if issue.get("number") != task["issue"]:
        raise ValueError("Issue identity mismatch")
    if issue.get("state") == "closed":
        return "CLOSED_AWAITING_EVIDENCE_REVIEW"
    if issue.get("state") != "open":
        return "UNVERIFIED"
    labels = {label.get("name") for label in issue.get("labels", []) if isinstance(label, dict)}
    if "delivery/blocked" in labels or "delivery/hold" in labels:
        return "BLOCKED"
    if task["kind"] == "human":
        return "OWNER_INPUT_REQUIRED"
    if "delivery/review" in labels:
        return "REVIEW_PENDING"
    if "delivery/active" in labels:
        return "IN_PROGRESS"
    return "READY_FOR_EXECUTOR"


def exact_head_checks(
    sha: str,
    runs: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    required_workflows: list[str],
    required_jobs: list[str],
) -> dict[str, Any]:
    """Require successful workflow groups and integration jobs at one exact SHA."""
    if not HEX_SHA.fullmatch(sha):
        raise ValueError("Invalid development commit identity")
    verdicts: dict[str, str] = {}
    evidence: dict[str, str] = {}
    for name in required_workflows:
        matching = [run for run in runs if run.get("head_sha") == sha and run.get("name") == name]
        matching.sort(
            key=lambda run: (run.get("updated_at") or "", run.get("run_attempt") or 0),
            reverse=True,
        )
        if not matching:
            verdicts[name] = "MISSING"
            continue
        run = matching[0]
        verdicts[name] = (
            "PASS"
            if run.get("status") == "completed" and run.get("conclusion") == "success"
            else "FAIL"
            if run.get("status") == "completed"
            else "PENDING"
        )
        evidence[name] = str(run.get("html_url") or "")
    for name in required_jobs:
        matching = [check for check in checks if check.get("name") == name]
        matching.sort(key=lambda check: check.get("completed_at") or "", reverse=True)
        if not matching:
            verdicts[name] = "MISSING"
        else:
            check = matching[0]
            verdicts[name] = (
                "PASS"
                if check.get("status") == "completed" and check.get("conclusion") == "success"
                else "FAIL"
                if check.get("status") == "completed"
                else "PENDING"
            )
            evidence[name] = str(check.get("html_url") or "")
    if all(value == "PASS" for value in verdicts.values()):
        overall = "PASS"
    elif any(value == "FAIL" for value in verdicts.values()):
        overall = "FAIL"
    else:
        overall = "PENDING_OR_MISSING"
    return {"status": overall, "checks": verdicts, "evidence": evidence}


def build_plan(
    manifest: dict[str, Any],
    issue_snapshots: dict[int, dict[str, Any]],
    sha: str | None,
    runs: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    lane: str | None = None,
) -> dict[str, Any]:
    """Produce a truthful queue without equating readiness with execution."""
    tasks = []
    selected_ids = {task["id"] for task in manifest["tasks"]}
    if lane is not None and lane not in selected_ids:
        raise ValueError("Unknown workstream lane")
    for task in manifest["tasks"]:
        state = task_state(task, issue_snapshots.get(task["issue"]))
        if task["depends_on"]:
            # A closed issue alone cannot clear a dependency: no trustworthy
            # scoped acceptance receipts have been supplied in this release.
            state = "WAITING_FOR_DEPENDENCY_VERIFICATION"
        if lane is not None and task["id"] != lane:
            continue
        tasks.append(
            {
                "id": task["id"],
                "phase": task["phase"],
                "issue": task["issue"],
                "url": f"https://github.com/{REPOSITORY}/issues/{task['issue']}",
                "kind": task["kind"],
                "status": state,
                "depends_on": task["depends_on"],
                "acceptance": task["acceptance"],
            }
        )
    ci = (
        exact_head_checks(
            sha,
            runs,
            checks,
            manifest["required_workflows"],
            manifest["required_integration_checks"],
        )
        if sha is not None
        else {"status": "UNVERIFIED", "checks": {}, "evidence": {}}
    )
    return {
        "repository": REPOSITORY,
        "development_sha": sha,
        "deadline": manifest["deadline"],
        "epic": f"https://github.com/{REPOSITORY}/issues/{manifest['epic_issue']}",
        "execution_mode": "READ_ONLY_PLAN_NO_CODING_EXECUTOR",
        "exact_head_ci": ci,
        "tasks": tasks,
    }


def markdown_summary(plan: dict[str, Any]) -> str:
    """Render an inspectable run summary without claiming a build was executed."""
    lines = [
        "# MatchDesk delivery control",
        "",
        f"Development SHA: {plan['development_sha'] or 'NOT VERIFIED'}",
        f"Exact-head CI: {plan['exact_head_ci']['status']}",
        f"Deadline: {plan['deadline']}",
        f"Coordination issue: {plan['epic']}",
        "",
        "| Lane | Phase | State | Tracker |",
        "| --- | --- | --- | --- |",
    ]
    for task in plan["tasks"]:
        lines.append(f"| {task['id']} | {task['phase']} | {task['status']} | {task['url']} |")
    lines.extend(
        [
            "",
            "This workflow plans and verifies only. READY_FOR_EXECUTOR is not RUNNING.",
            "Closed issues are not certification. No AI worker, merge, publication,",
            "deployment, privileged operation or paid service is started by this job.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run the bounded CLI, preserving failure instead of inventing green states."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--github", action="store_true", help="Require live GitHub reads")
    mode.add_argument("--offline", action="store_true", help="Unverified dry-run only")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--lane", help="Restrict report to one workstream ID")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = validate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
        if args.github:
            token = os.environ.get("GITHUB_TOKEN", "")
            branch = github_get("branches/development", token)
            sha = branch.get("commit", {}).get("sha")
            if not isinstance(sha, str) or not HEX_SHA.fullmatch(sha):
                raise ValueError("GitHub supplied no valid development source SHA")
            issues = {
                task["issue"]: github_get(f"issues/{task['issue']}", token)
                for task in manifest["tasks"]
            }
            runs_data = github_get(f"actions/runs?head_sha={sha}&per_page=100", token)
            checks_data = github_get(f"commits/{sha}/check-runs?per_page=100", token)
            if runs_data.get("total_count", 0) > 100 or checks_data.get("total_count", 0) > 100:
                raise ValueError("Evidence pagination would omit exact-head checks")
            runs = runs_data.get("workflow_runs", [])
            checks = checks_data.get("check_runs", [])
            if not isinstance(runs, list) or not isinstance(checks, list):
                raise ValueError("Malformed GitHub check evidence")
        else:
            sha, issues, runs, checks = None, {}, [], []
        plan = build_plan(manifest, issues, sha, runs, checks, args.lane)
        summary = markdown_summary(plan)
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            (args.output_dir / "plan.json").write_text(
                json.dumps(plan, indent=2) + "\n", encoding="utf-8"
            )
            (args.output_dir / "summary.md").write_text(summary, encoding="utf-8")
        print(summary)
    except (ValueError, OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"Delivery preflight BLOCKED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
