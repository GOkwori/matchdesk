"""Protect the approved solo-maintainer policy without claiming GitHub activation.

These assertions inspect the versioned import files. Live rulesets, successful
checks and George's final exact-commit approval still require separate verification.
"""

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CHECKS = {
    "foundation",
    "web",
    "runtime-browser",
    "native-images",
    "dependencies",
    "history-secrets",
    "codeql-python",
    "codeql-javascript-typescript",
}


def load_policy(branch: str) -> dict[str, Any]:
    """Load only an explicitly supported branch's checked-in import configuration."""
    assert branch in {"main", "development"}
    path = ROOT / "docs" / "operations" / "rulesets" / f"{branch}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("branch", ["main", "development"])
def test_rule_scope_and_no_bypass(branch: str) -> None:
    """Prevent widening branch targets or adding an administrator bypass silently."""
    policy = load_policy(branch)
    assert policy["target"] == "branch"
    assert policy["enforcement"] == "active"
    assert policy["bypass_actors"] == []
    assert policy["conditions"] == {
        "ref_name": {"include": [f"refs/heads/{branch}"], "exclude": []},
    }


def test_main_requires_pr_without_an_additional_reviewer() -> None:
    """Remove both independent-review barriers while preserving review resolution."""
    rules = load_policy("main")["rules"]
    reviews = [rule for rule in rules if rule["type"] == "pull_request"]
    assert len(reviews) == 1
    assert reviews[0]["parameters"] == {
        "dismiss_stale_reviews_on_push": True,
        "require_code_owner_review": False,
        "require_last_push_approval": False,
        "required_approving_review_count": 0,
        "required_review_thread_resolution": True,
    }


def test_main_retains_all_exact_required_checks() -> None:
    """A solo review policy must not become a security-check exemption."""
    rules = load_policy("main")["rules"]
    checks = [rule for rule in rules if rule["type"] == "required_status_checks"]
    assert len(checks) == 1
    parameters = checks[0]["parameters"]
    assert parameters["strict_required_status_checks_policy"] is True
    assert parameters["do_not_enforce_on_create"] is False
    expected = [{"context": name, "integration_id": 15368} for name in EXPECTED_CHECKS]
    observed = sorted(parameters["required_status_checks"], key=lambda item: item["context"])
    assert observed == sorted(expected, key=lambda item: item["context"])


def test_main_retains_history_safeguards() -> None:
    """Preserve the reviewed PR, history and check controls without duplicate rules."""
    rules = load_policy("main")["rules"]
    expected = {
        "deletion",
        "non_fast_forward",
        "required_linear_history",
        "pull_request",
        "required_status_checks",
    }
    assert len(rules) == len(expected)
    assert {rule["type"] for rule in rules} == expected


def test_development_preserves_the_two_branch_workflow() -> None:
    """Protect history without requiring a third branch or blocking ordinary development."""
    assert load_policy("development")["rules"] == [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
    ]
