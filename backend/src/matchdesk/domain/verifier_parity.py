"""Compact event-log export and the parity fixture for the TypeScript verifier port.

The fixture is a list of claims run through the real ``verify_claim``. The browser port
must return the same status, query, reason, expected and observed value for every case,
so the screen can never drift from the backend. ``evidence_digest`` is excluded because
the port does not hash records.
"""

from __future__ import annotations

from typing import Any, Literal

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_claims import claims, evidence_record, possession_claim, replay_window
from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import (
    Claim,
    EvidenceRecord,
    MatchEvent,
    MatchWindow,
    MetricAssertion,
    Subject,
)
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.verification import verify_claim

PARITY_SCHEMA = "matchdesk-verifier-parity/1"
EVENT_LOG_SCHEMA = "matchdesk-event-log/1"


def compact_events(events: tuple[MatchEvent, ...]) -> dict[str, Any]:
    """Column-oriented events with only the fields the registered metrics and binding read."""
    return {
        "schema": EVENT_LOG_SCHEMA,
        "match_ids": [event.match_id for event in events],
        "id": [event.event_id for event in events],
        "seq": [event.sequence for event in events],
        "period": [event.period for event in events],
        "ms": [event.match_clock_ms for event in events],
        "type": [event.type for event in events],
        "team": [event.team_id for event in events],
        "player": [event.player_id for event in events],
        "outcome": [event.outcome for event in events],
        "xg": [event.xg for event in events],
        "x": [event.location.x if event.location else None for event in events],
        "end_x": [event.end_location.x if event.end_location else None for event in events],
    }


def _assertion(
    metric: str,
    subject: Subject,
    value: float,
    unit: Literal["count", "ratio", "synthetic_xg"],
    *,
    window: MatchWindow | None = None,
    comparator: Literal["eq", "gte", "lte"] = "eq",
    decimals: int | None = None,
) -> MetricAssertion:
    """Build a metric assertion over the replay window unless another is given."""
    return MetricAssertion(
        metric=metric,
        subject=subject,
        window=window or replay_window(),
        comparator=comparator,
        value=value,
        unit=unit,
        decimals=decimals,
    )


def _measured(
    claim_id: str, assertion: MetricAssertion, cites: tuple[str, ...] = ("E-0001",)
) -> Claim:
    """Wrap an assertion in a measured claim citing one canonical event by default."""
    return Claim(
        claim_id=claim_id,
        text="Parity case.",
        kind="measured_stat",
        assertion=assertion,
        evidence_event_ids=cites,
    )


def parity_fixture() -> dict[str, Any]:
    """Every verifier branch, on the canonical log and a small simulator scenario."""
    log = canonical.generate_canonical_match()
    scenario = generate_scenario("counter_attack_goal", 7).events
    evidence = evidence_record(log)
    home = Subject(team_id=canonical.HOME)
    away = Subject(team_id=canonical.AWAY)
    first_half = MatchWindow(period=1, from_ms=0, to_ms=canonical.SECOND_HALF_MS)
    second_half = MatchWindow(period=2, from_ms=canonical.SECOND_HALF_MS, to_ms=4_032_000)

    def observed(metric: str, subject: Subject, window: MatchWindow) -> float:
        """Recompute a metric on the canonical log to build an exactly-true claim."""
        return compute_metric(metric, log, subject, window)

    pass_acc = observed("pass_accuracy.v1", home, first_half)
    xg = observed("synthetic_xg.v1", away, replay_window())
    entries = observed("final_third_entries.v1", home, second_half)
    possession_h2 = observed("possession_time.v1", away, second_half)

    cases: list[tuple[str, Claim, str, EvidenceRecord]] = [
        *[(f"demo {c.claim_id}", c, "canonical", evidence) for c in claims()],
        *[(f"demo {c.claim_id} at 50:00", c, "canonical", evidence) for c in claims(3_000_000)],
        ("forged possession 59%", possession_claim(0.59), "canonical", evidence),
        (
            "possession exact eq without precision",
            _measured("P-01", _assertion("possession_time.v1", home, 0.58, "ratio")),
            "canonical",
            evidence,
        ),
        (
            "away possession at three decimals",
            _measured(
                "P-02",
                _assertion("possession_time.v1", away, round(1 - 0.5796, 3), "ratio", decimals=3),
            ),
            "canonical",
            evidence,
        ),
        (
            "possession second half observed",
            _measured(
                "P-03",
                _assertion("possession_time.v1", away, possession_h2, "ratio", window=second_half),
            ),
            "canonical",
            evidence,
        ),
        (
            "possession needs a team-only subject",
            _measured(
                "P-04",
                _assertion(
                    "possession_time.v1",
                    Subject(team_id=canonical.HOME, player_id="nbr-09"),
                    0.5,
                    "ratio",
                ),
            ),
            "canonical",
            evidence,
        ),
        (
            "shots gte",
            _measured("P-05", _assertion("shots.v1", home, 10, "count", comparator="gte")),
            "canonical",
            evidence,
        ),
        (
            "shots lte fails",
            _measured("P-06", _assertion("shots.v1", home, 10, "count", comparator="lte")),
            "canonical",
            evidence,
        ),
        (
            "away shots first half",
            _measured(
                "P-07",
                _assertion(
                    "shots.v1",
                    away,
                    observed("shots.v1", away, first_half),
                    "count",
                    window=first_half,
                ),
            ),
            "canonical",
            evidence,
        ),
        (
            "pass accuracy exact",
            _measured(
                "P-08", _assertion("pass_accuracy.v1", home, pass_acc, "ratio", window=first_half)
            ),
            "canonical",
            evidence,
        ),
        (
            "pass accuracy at two decimals",
            _measured(
                "P-09",
                _assertion(
                    "pass_accuracy.v1",
                    home,
                    float(round(pass_acc, 2)),
                    "ratio",
                    window=first_half,
                    decimals=2,
                ),
            ),
            "canonical",
            evidence,
        ),
        (
            "synthetic xg sum",
            _measured("P-10", _assertion("synthetic_xg.v1", away, xg, "synthetic_xg")),
            "canonical",
            evidence,
        ),
        (
            "final third entries",
            _measured(
                "P-11",
                _assertion("final_third_entries.v1", home, entries, "count", window=second_half),
            ),
            "canonical",
            evidence,
        ),
        (
            "unit mismatch",
            _measured("P-12", _assertion("shots.v1", home, 1, "ratio")),
            "canonical",
            evidence,
        ),
        (
            "unregistered metric",
            _measured("P-13", _assertion("dribbles.v1", home, 1, "count")),
            "canonical",
            evidence,
        ),
        (
            "claim cites an event the record does not bind",
            _measured("P-14", _assertion("shots.v1", home, 1, "count"), ("E-9999",)),
            "canonical",
            evidence,
        ),
        ("events from another match", possession_claim(), "scenario", evidence),
        ("no accepted events", possession_claim(), "empty", evidence),
    ]
    scenario_evidence = EvidenceRecord(
        evidence_id="EV-SCENARIO",
        match_id=scenario[0].match_id,
        replay_id="replay-scenario",
        revision=1,
        window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
        event_ids=tuple(event.event_id for event in scenario) + ("E-GHOST",),
        engine_version="engine-v1",
        source_digest="a" * 64,
    )
    cases.append(
        (
            "record binds an event missing from the log",
            _measured(
                "P-15",
                _assertion(
                    "shots.v1",
                    Subject(team_id="home"),
                    1,
                    "count",
                    window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
                ),
                ("E-GHOST",),
            ),
            "scenario",
            scenario_evidence,
        )
    )
    cases.append(
        (
            "scenario home goal by player",
            _measured(
                "P-16",
                _assertion(
                    "goals.v1",
                    Subject(team_id="home", player_id="home-10"),
                    1,
                    "count",
                    window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
                ),
                (scenario[-2].event_id,),
            ),
            "scenario",
            scenario_evidence,
        )
    )

    sources = {"canonical": log, "scenario": scenario, "empty": ()}
    exported = []
    records: dict[str, Any] = {}
    for name, claim, source, record in cases:
        records[record.evidence_id] = record.model_dump(mode="json", exclude_none=True)
        result = verify_claim(claim, record, sources[source])
        exported.append(
            {
                "name": name,
                "events": source,
                "claim": claim.model_dump(mode="json", exclude_none=True),
                "evidence": record.evidence_id,
                "expected": {
                    "status": result.status,
                    "query_id": result.query_id,
                    "reason": result.reason,
                    "expected": result.expected,
                    "observed": result.observed,
                },
            }
        )
    return {
        "schema": PARITY_SCHEMA,
        "scenario_events": compact_events(scenario),
        "evidence": records,
        "cases": exported,
    }
