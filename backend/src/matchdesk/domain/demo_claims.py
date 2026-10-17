"""The four demo claims in draft D-031, as real contracts checked by the real verifier.

The studio shows these verdicts. They come from ``verify_claim`` over the canonical
event log, not from frontend logic, so the screen and the backend cannot disagree.
"""

from __future__ import annotations

from typing import Any

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.models import (
    Claim,
    EvidenceRecord,
    MatchEvent,
    MatchWindow,
    MetricAssertion,
    Subject,
)
from matchdesk.domain.verification import verify_claim

REPLAY_END_MS = canonical.clock_ms(67, 12)
SCORER = "nbr-09"
FORGED_POSSESSION = 0.59


def replay_window(to_ms: int = REPLAY_END_MS) -> MatchWindow:
    """The whole match from kick-off to a replay point, across both periods."""
    return MatchWindow(from_ms=0, to_ms=to_ms)


def evidence_record(events: tuple[MatchEvent, ...]) -> EvidenceRecord:
    """One evidence record binding the whole replayed log for draft D-031."""
    return EvidenceRecord(
        evidence_id="EV-D031",
        match_id=canonical.MATCH_ID,
        replay_id="replay-nbr-riv-canonical",
        revision=1,
        window=replay_window(),
        event_ids=tuple(event.event_id for event in events),
        engine_version="matchdesk-canonical-1",
        source_digest="0" * 64,
    )


def possession_claim(value: float = 0.58) -> Claim:
    """CL-0214: a whole-percent possession share, verified at its stated precision."""
    return Claim(
        claim_id="CL-0214",
        text=f"Northbridge have had {round(value * 100)}% possession.",
        kind="measured_stat",
        assertion=MetricAssertion(
            metric="possession_time.v1",
            subject=Subject(team_id=canonical.HOME),
            window=replay_window(),
            comparator="eq",
            value=value,
            unit="ratio",
            decimals=2,
        ),
        # Possession is measured over every interval; cite the log's boundary events.
        evidence_event_ids=("E-0001", "E-0841", "E-0842", "E-1421"),
    )


def claims(to_ms: int = REPLAY_END_MS) -> tuple[Claim, ...]:
    """CL-0213 to CL-0216 as drafted in D-031, measured up to a replay point."""
    return (
        Claim(
            claim_id="CL-0213",
            text="Okafor scored both Northbridge goals.",
            kind="measured_stat",
            assertion=MetricAssertion(
                metric="goals.v1",
                subject=Subject(team_id=canonical.HOME, player_id=SCORER),
                window=replay_window(to_ms),
                comparator="eq",
                value=2,
                unit="count",
            ),
            evidence_event_ids=("E-0688", "E-1366"),
        ),
        possession_claim(),
        Claim(
            claim_id="CL-0215",
            text="Riverside's best spell came between 30 and 45 minutes.",
            kind="tactical_inference",
            evidence_event_ids=("E-0788", "E-0789", "E-0790"),
        ),
        Claim(
            claim_id="CL-0216",
            text="It is Okafor's first brace of the season.",
            kind="event_fact",
            evidence_event_ids=("E-0688", "E-1366"),
        ),
    )


def _result(claim: Claim, evidence: EvidenceRecord, events: tuple[MatchEvent, ...]) -> Any:
    """Run the real verifier and keep the fields the screen and the parity test compare."""
    result = verify_claim(claim, evidence, events)
    return {
        "status": result.status,
        "query_id": result.query_id,
        "reason": result.reason,
        "expected": result.expected,
        "observed": result.observed,
    }


def claim_export(events: tuple[MatchEvent, ...]) -> list[dict[str, Any]]:
    """Each claim, its contract, the verifier's result and when that result changes.

    ``timeline`` lists replay clocks at which a count claim's status changes, so the
    replay slider shows the verifier's answer at any point without re-running it.
    """
    evidence = evidence_record(events)
    exported = []
    for claim in claims():
        timeline = []
        assertion = claim.assertion
        if assertion is not None and assertion.unit == "count":
            metric_type = {"goals.v1": "goal", "shots.v1": "shot"}[assertion.metric]
            changes = sorted({e.match_clock_ms + 1 for e in events if e.type == metric_type})
            previous = None
            for to_ms in [1, *changes]:
                if to_ms > REPLAY_END_MS:
                    break
                claim_at = next(c for c in claims(to_ms) if c.claim_id == claim.claim_id)
                status = verify_claim(claim_at, evidence, events).status
                if status != previous:
                    timeline.append({"from_ms": to_ms - 1, "status": status})
                    previous = status
        exported.append(
            {
                "claim": claim.model_dump(mode="json", exclude_none=True),
                "result": _result(claim, evidence, events),
                "timeline": timeline,
            }
        )
    forged = _result(possession_claim(FORGED_POSSESSION), evidence, events)
    exported.append(
        {
            "claim": possession_claim(FORGED_POSSESSION).model_dump(mode="json", exclude_none=True),
            "result": forged,
            "timeline": [],
            "forged": True,
        }
    )
    return exported
