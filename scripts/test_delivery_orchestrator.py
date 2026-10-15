"""Regression tests for the read-only MatchDesk delivery controller."""

from __future__ import annotations

import copy
import unittest

from scripts.delivery_orchestrator import (
    build_plan,
    exact_head_checks,
    markdown_summary,
    task_state,
    validate_manifest,
)

SHA = "a" * 40
GATES = ["Foundation CI", "Foundation integration", "Source security", "Dependency audit"]
JOBS = ["runtime-browser", "native-images"]


def manifest_fixture() -> dict:
    """Make a small valid manifest while preserving the real repository identity."""
    return {
        "schema_version": 1,
        "repository": "GOkwori/matchdesk",
        "development_branch": "development",
        "production_branch": "main",
        "deadline": "2026-10-26",
        "epic_issue": 60,
        "max_parallel": 4,
        "required_workflows": GATES,
        "required_integration_checks": JOBS,
        "tasks": [
            {
                "id": "producer",
                "issue": 61,
                "phase": "P3",
                "kind": "engineering",
                "depends_on": [],
                "acceptance": "Scoped fail-closed producer commands",
            },
            {
                "id": "assets",
                "issue": 65,
                "phase": "Review",
                "kind": "human",
                "depends_on": [],
                "acceptance": "Exact originals",
            },
        ],
    }


def passing_runs() -> list[dict]:
    """Produce fixtures matching exact-head workflow identity."""
    return [
        {
            "name": name,
            "head_sha": SHA,
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
        }
        for name in GATES
    ]


def passing_checks() -> list[dict]:
    """Produce fixtures matching actual integration check names."""
    return [{"name": name, "status": "completed", "conclusion": "success"} for name in JOBS]


class ManifestValidationTests(unittest.TestCase):
    """Guard manifest authority and dependency consistency."""

    def test_valid_manifest(self) -> None:
        """Accept a bounded two-lane fixture."""
        self.assertEqual(validate_manifest(manifest_fixture())["epic_issue"], 60)

    def test_reject_other_repository(self) -> None:
        """Do not allow redirection to an arbitrary repository."""
        data = manifest_fixture()
        data["repository"] = "attacker/repo"
        with self.assertRaises(ValueError):
            validate_manifest(data)

    def test_reject_duplicate_issue(self) -> None:
        """An issue cannot be silently assigned to multiple executor lanes."""
        data = manifest_fixture()
        data["tasks"][1]["issue"] = 61
        with self.assertRaises(ValueError):
            validate_manifest(data)

    def test_reject_cycle(self) -> None:
        """Mutually blocked work is not a valid executable DAG."""
        data = manifest_fixture()
        data["tasks"][0]["depends_on"] = ["assets"]
        data["tasks"][1]["depends_on"] = ["producer"]
        with self.assertRaises(ValueError):
            validate_manifest(data)

    def test_reject_unknown_dependency(self) -> None:
        """References must map to declared work items."""
        data = manifest_fixture()
        data["tasks"][0]["depends_on"] = ["not-present"]
        with self.assertRaises(ValueError):
            validate_manifest(data)

    def test_reject_more_than_four_engineering_lanes(self) -> None:
        """Hard-cap the parallel execution budget."""
        data = manifest_fixture()
        for number in range(3, 7):
            data["tasks"].append(
                {
                    "id": f"lane-{number}",
                    "issue": number + 100,
                    "phase": "P4",
                    "kind": "engineering",
                    "depends_on": [],
                    "acceptance": "Verified",
                }
            )
        with self.assertRaises(ValueError):
            validate_manifest(data)

    def test_reject_missing_mandatory_gates(self) -> None:
        """A missing gate group must fail validation rather than appear green."""
        data = manifest_fixture()
        data["required_workflows"] = []
        with self.assertRaises(ValueError):
            validate_manifest(data)


class ReadinessTests(unittest.TestCase):
    """Distinguish read-only planning from actual code execution and acceptance."""

    def test_open_engineering_task_is_ready_not_running(self) -> None:
        """An open issue is a queue entry, never an active coding agent."""
        state = task_state(manifest_fixture()["tasks"][0], {"number": 61, "state": "open"})
        self.assertEqual(state, "READY_FOR_EXECUTOR")

    def test_human_task_never_auto_passes(self) -> None:
        """A human-only task requires true owner input."""
        state = task_state(manifest_fixture()["tasks"][1], {"number": 65, "state": "open"})
        self.assertEqual(state, "OWNER_INPUT_REQUIRED")

    def test_closed_issue_is_not_qualified(self) -> None:
        """GitHub issue closure is not exact-SHA evidence."""
        state = task_state(manifest_fixture()["tasks"][0], {"number": 61, "state": "closed"})
        self.assertEqual(state, "CLOSED_AWAITING_EVIDENCE_REVIEW")

    def test_blocked_label_has_priority(self) -> None:
        """Risk holds always override readiness."""
        state = task_state(
            manifest_fixture()["tasks"][0],
            {"number": 61, "state": "open", "labels": [{"name": "delivery/hold"}]},
        )
        self.assertEqual(state, "BLOCKED")

    def test_unknown_issue_fails_closed(self) -> None:
        """No network snapshot must never be reported as READY."""
        self.assertEqual(task_state(manifest_fixture()["tasks"][0], None), "UNVERIFIED")

    def test_issue_number_mismatch_raises(self) -> None:
        """Responses cannot be confused across numbered issues."""
        with self.assertRaises(ValueError):
            task_state(manifest_fixture()["tasks"][0], {"number": 62, "state": "open"})

    def test_unverified_dependency_waits(self) -> None:
        """A closed parent issue alone cannot release its dependent task."""
        data = manifest_fixture()
        data["tasks"][0]["depends_on"] = ["assets"]
        plan = build_plan(
            data,
            {61: {"number": 61, "state": "open"}, 65: {"number": 65, "state": "closed"}},
            None,
            [],
            [],
        )
        self.assertEqual(plan["tasks"][0]["status"], "WAITING_FOR_DEPENDENCY_VERIFICATION")

    def test_offline_report_is_explicitly_unverified(self) -> None:
        """A dry-run cannot certify GitHub or the build."""
        plan = build_plan(manifest_fixture(), {}, None, [], [])
        self.assertEqual(plan["exact_head_ci"]["status"], "UNVERIFIED")
        self.assertTrue(all(task["status"] == "UNVERIFIED" for task in plan["tasks"]))
        self.assertIn("not RUNNING", markdown_summary(plan))

    def test_invalid_lane_fails(self) -> None:
        """Restrict lane selection to registered task IDs."""
        with self.assertRaises(ValueError):
            build_plan(manifest_fixture(), {}, None, [], [], "other")


class ExactHeadQualificationTests(unittest.TestCase):
    """Check authoritative identity and all six measured workflow/job gates."""

    def test_all_workflows_and_jobs_green(self) -> None:
        """Only the exact SHA with every group passing may pass."""
        status = exact_head_checks(SHA, passing_runs(), passing_checks(), GATES, JOBS)
        self.assertEqual(status["status"], "PASS")
        self.assertEqual(len(status["checks"]), 6)

    def test_historical_pass_does_not_transfer(self) -> None:
        """A green run at another SHA must not be reused."""
        runs = passing_runs()
        runs[0]["head_sha"] = "b" * 40
        status = exact_head_checks(SHA, runs, passing_checks(), GATES, JOBS)
        self.assertEqual(status["status"], "PENDING_OR_MISSING")
        self.assertEqual(status["checks"]["Foundation CI"], "MISSING")

    def test_newest_failure_supersedes_old_success(self) -> None:
        """Do not cherry-pick a successful historical run after a failed rerun."""
        runs = passing_runs()
        bad = copy.deepcopy(runs[0])
        bad.update({"updated_at": "2026-10-15T20:00:00Z", "conclusion": "failure"})
        runs[0]["updated_at"] = "2026-10-15T10:00:00Z"
        status = exact_head_checks(SHA, runs + [bad], passing_checks(), GATES, JOBS)
        self.assertEqual(status["status"], "FAIL")

    def test_failed_native_images_blocks_green(self) -> None:
        """Passing workflow labels cannot excuse a failed native-image job."""
        checks = passing_checks()
        checks[-1]["conclusion"] = "failure"
        status = exact_head_checks(SHA, passing_runs(), checks, GATES, JOBS)
        self.assertEqual(status["status"], "FAIL")

    def test_pending_integration_does_not_pass(self) -> None:
        """A running integration workflow remains pending."""
        runs = passing_runs()
        runs[1].update({"status": "in_progress", "conclusion": None})
        status = exact_head_checks(SHA, runs, passing_checks(), GATES, JOBS)
        self.assertEqual(status["status"], "PENDING_OR_MISSING")

    def test_invalid_sha_rejected(self) -> None:
        """Reject ambiguous or non-commit source IDs."""
        with self.assertRaises(ValueError):
            exact_head_checks("latest", passing_runs(), passing_checks(), GATES, JOBS)


if __name__ == "__main__":
    unittest.main()
