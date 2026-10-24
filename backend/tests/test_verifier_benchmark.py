"""The verifier catches every false sentence in the benchmark and keeps every true one."""

from __future__ import annotations

from functools import cache
from typing import Any

from matchdesk.domain.verifier_benchmark import CATEGORIES, CONTROLS, run_benchmark


@cache
def _result() -> dict[str, Any]:
    """Run the benchmark once for every test."""
    return run_benchmark()


def test_every_false_claim_is_caught_and_no_true_claim_is_rejected() -> None:
    """All 800+ false claims are sent back and no true claim or rewording is."""
    result = _result()
    assert result["false"]["total"] >= 800
    assert result["false"]["caught"] == result["false"]["total"]
    assert result["true"]["total"] >= 250
    assert result["true"]["wrongly_rejected"] == 0
    for category in result["categories"]:
        assert category["missed"] == [], category["id"]


def test_every_kind_of_error_is_exercised() -> None:
    """Each kind of error and each kind of true rewording has cases."""
    ids = {c["id"] for c in _result()["categories"]}
    assert ids == set(CATEGORIES) | set(CONTROLS)


def test_a_substitution_the_wrong_way_round_is_caught() -> None:
    """The benchmark found this gap: swapping who came on and who went off."""
    subs = next(c for c in _result()["categories"] if c["id"] == "wrong_substitute")
    assert subs["total"] >= 2 and subs["correct"] == subs["total"]
