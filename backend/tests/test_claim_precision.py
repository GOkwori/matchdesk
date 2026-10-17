"""Tests for whole-match windows and precision-aware equality in claim verification."""

from decimal import Decimal

import pytest
from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import (
    Claim,
    EvidenceRecord,
    MatchWindow,
    MetricAssertion,
    Subject,
    round_half_up,
)
from matchdesk.domain.verification import verify_claim
from pydantic import ValidationError

EVENTS = canonical.generate_canonical_match()
WHOLE = MatchWindow(from_ms=0, to_ms=4_032_000)
HOME = Subject(team_id=canonical.HOME)


def _evidence() -> EvidenceRecord:
    """Bind every canonical event so binding never masks the comparator under test."""
    return EvidenceRecord(
        evidence_id="ev-whole",
        match_id=canonical.MATCH_ID,
        replay_id="replay-canonical",
        revision=1,
        window=WHOLE,
        event_ids=tuple(event.event_id for event in EVENTS),
        engine_version="engine-v1",
        source_digest="b" * 64,
    )


def _possession_claim(value: float, decimals: int | None) -> Claim:
    """CL-0214-style possession claim at a chosen value and stated precision."""
    return Claim(
        claim_id="CL-test",
        text=f"Northbridge have had {value:.0%} possession.",
        kind="measured_stat",
        assertion=MetricAssertion(
            metric="possession_time.v1",
            subject=HOME,
            window=WHOLE,
            value=value,
            unit="ratio",
            decimals=decimals,
        ),
        evidence_event_ids=("E-0001", "E-1421"),
    )


def test_whole_match_window_sums_both_periods() -> None:
    """A window without a period equals the two halves combined, never a cross-break interval."""
    whole = compute_metric("possession_time.v1", EVENTS, HOME, WHOLE)
    assert whole == pytest.approx(2_334_479 / 4_028_000)
    first = MatchWindow(period=1, from_ms=0, to_ms=4_032_000)
    second = MatchWindow(period=2, from_ms=2_700_000, to_ms=4_032_000)
    goals = sum(compute_metric("goals.v1", EVENTS, HOME, w) for w in (first, second))
    assert compute_metric("goals.v1", EVENTS, HOME, WHOLE) == goals == 2.0


def test_rounded_claim_verifies_when_the_recomputed_value_rounds_to_it() -> None:
    """57.96% is "58%" at whole-percent precision, so the stated claim is verified."""
    result = verify_claim(_possession_claim(0.58, 2), _evidence(), EVENTS)
    assert result.status == "verified"
    assert result.expected == 0.58
    assert result.observed == pytest.approx(0.5796, abs=1e-4)


def test_forged_rounded_claim_is_rejected() -> None:
    """A forged 59% does not round from 57.96%, so it needs revision."""
    assert verify_claim(_possession_claim(0.59, 2), _evidence(), EVENTS).status == "needs_revision"


def test_exact_equality_is_unchanged_without_a_precision() -> None:
    """Without decimals, eq stays exact: 0.58 is not 0.5796."""
    assert (
        verify_claim(_possession_claim(0.58, None), _evidence(), EVENTS).status == "needs_revision"
    )


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [(0.575, 2, "0.58"), (0.585, 2, "0.59"), (0.5749, 2, "0.57"), (2.5, 0, "3"), (0.0, 1, "0.0")],
)
def test_round_half_up_uses_the_shortest_decimal_form(
    value: float, decimals: int, expected: str
) -> None:
    """Rounding goes half up on the printed decimal, not the binary float (0.575 -> 0.58)."""
    assert round_half_up(value, decimals) == Decimal(expected)


def test_precision_is_only_for_eq_and_must_match_the_value() -> None:
    """A precision cannot loosen gte/lte, nor be finer than the value it describes."""
    with pytest.raises(ValidationError, match="only to the eq comparator"):
        MetricAssertion(
            metric="shots.v1",
            subject=HOME,
            window=WHOLE,
            comparator="gte",
            value=3,
            unit="count",
            decimals=0,
        )
    with pytest.raises(ValidationError, match="more decimal places"):
        MetricAssertion(
            metric="possession_time.v1",
            subject=HOME,
            window=WHOLE,
            value=0.585,
            unit="ratio",
            decimals=2,
        )


def test_period_two_windows_still_cannot_start_in_the_first_half() -> None:
    """The existing period rule is unchanged for windows that name a period."""
    with pytest.raises(ValidationError, match="second-half window"):
        MatchWindow(period=2, from_ms=0, to_ms=10)
