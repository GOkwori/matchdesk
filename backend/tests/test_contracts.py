"""Boundary, regression and deterministic sample tests; no LLM or database is used."""
import json
import math
import random

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from matchdesk.domain.hashing import canonical_bytes, content_digest
from matchdesk.domain.models import (
    ApprovalBinding, Claim, EvidenceRecord, Location, MatchEvent, MatchWindow,
    MetricAssertion, Subject, VerificationResult,
)
from scripts.export_contracts import check_exports


def event_from(data: dict[str, object]) -> MatchEvent:
    """Exercise the public JSON boundary rather than an internal Python object shape."""
    return MatchEvent.model_validate_json(json.dumps(data))


def measured_claim() -> dict[str, object]:
    """Create a numerical assertion without claiming that its evidence is truthful."""
    return {
        "claim_id": "claim-1", "text": "The team took seven shots.",
        "kind": "measured_stat", "evidence_event_ids": ["event-1"],
        "assertion": {
            "metric": "shots", "subject": {"team_id": "demo-a"},
            "window": {"period": 1, "from_ms": 0, "to_ms": 60_000},
            "value": 7.0, "unit": "count",
        },
    }


def test_valid_pass_round_trips(event_data: dict[str, object]) -> None:
    """Accepted JSON must preserve the same canonical identity after serialisation."""
    event = event_from(event_data)
    assert event_from(event.model_dump(mode="json")) == event
    assert len(content_digest(event)) == 64


@pytest.mark.parametrize("field,value", [
    ("sequence", -1), ("sequence", "1"), ("sequence", True),
    ("period", 3), ("period", True), ("period", "1"),
    ("match_clock_ms", -1), ("synthetic", False), ("synthetic", 1),
    ("synthetic", "true"), ("event_id", "../secret"), ("event_id", ""),
    ("type", "unknown"), ("under_pressure", "false"), ("unexpected", "secret"),
    ("outcome", "goal"), ("xg", 0.2), ("player_id", None), ("team_id", None),
    ("end_location", None), ("location", None),
    ("tags", ["same", "same"]), ("linked_event_id", "other"),
    ("related_player_id", "other"),
])
def test_invalid_event_rejected(event_data: dict[str, object], field: str, value: object) -> None:
    """Invalid data must fail explicitly rather than be coerced or silently ignored."""
    event_data[field] = value
    with pytest.raises(ValidationError):
        event_from(event_data)


@pytest.mark.parametrize("value", [-0.01, 100.01, float("nan"), float("inf"), True, "40"])
def test_invalid_coordinate(value: object) -> None:
    """Coordinates reject out-of-pitch, non-finite and wrong-typed values."""
    with pytest.raises(ValidationError):
        Location.model_validate({"x": value, "y": 50.0})


def test_coordinate_seeded_invariants() -> None:
    """Check 500 reproducible coordinate samples; this is not a Hypothesis suite."""
    generator = random.Random(104729)
    for _ in range(500):
        x, y = generator.uniform(0, 100), generator.uniform(0, 100)
        coordinate = Location(x=x, y=y)
        assert math.isfinite(coordinate.x)
        assert 0 <= coordinate.x <= 100 and 0 <= coordinate.y <= 100
        with pytest.raises(ValidationError):
            Location(x=x + 101, y=y)


def test_record_is_immutable(event_data: dict[str, object]) -> None:
    """A verified identity cannot silently change through assignment to a frozen model."""
    event = event_from(event_data)
    with pytest.raises(ValidationError):
        event.sequence = 9


def test_defaults_and_key_order_do_not_change_hash(event_data: dict[str, object]) -> None:
    """Semantically identical JSON inputs produce the same version-1 content digest."""
    first = event_from(event_data)
    event_data["under_pressure"] = False
    event_data["schema_version"] = "1.0"
    second = event_from(dict(reversed(list(event_data.items()))))
    assert content_digest(first) == content_digest(second)
    assert canonical_bytes(first).startswith(b"{")


def test_changed_event_changes_hash(event_data: dict[str, object]) -> None:
    """A change of time must invalidate a cached event identity."""
    before = content_digest(event_from(event_data))
    event_data["match_clock_ms"] = 2000
    assert content_digest(event_from(event_data)) != before


def test_period_clock_handles_stoppage_time(event_data: dict[str, object]) -> None:
    """First-half stoppage time can exceed the nominal 45-minute restart clock."""
    event_data["match_clock_ms"] = 48 * 60_000
    first = event_from(event_data)
    event_data.update(period=2, match_clock_ms=45 * 60_000, sequence=2)
    second = event_from(event_data)
    assert first.match_clock_ms > second.match_clock_ms
    assert first.sequence < second.sequence
    event_data["match_clock_ms"] = 44 * 60_000
    with pytest.raises(ValidationError):
        event_from(event_data)


@pytest.mark.parametrize("kind", ["period_start", "period_end"])
def test_period_markers_have_no_player(kind: str) -> None:
    """Lifecycle events must not accidentally count as a player's ball action."""
    data = {"event_id": "period-1", "match_id": "match-1", "sequence": 0,
            "period": 1, "match_clock_ms": 0, "type": kind}
    assert event_from(data).player_id is None
    data["player_id"] = "a-08"
    with pytest.raises(ValidationError):
        event_from(data)


def test_shot_and_goal_are_distinct(event_data: dict[str, object]) -> None:
    """A goal marker references its shot; the numerical estimate belongs to the shot."""
    event_data.update(type="shot", outcome="goal", xg=0.31)
    assert event_from(event_data).xg == 0.31
    event_data.update(type="goal", xg=None)
    with pytest.raises(ValidationError):
        event_from(event_data)
    event_data["linked_event_id"] = "shot-1"
    assert event_from(event_data).linked_event_id == "shot-1"
    event_data.update(type="shot", linked_event_id=None)
    with pytest.raises(ValidationError):
        event_from(event_data)


def test_substitution_requires_distinct_incoming_player(event_data: dict[str, object]) -> None:
    """Substitution records must distinguish the outgoing player from the incoming one."""
    event_data.update(type="substitution", related_player_id="a-08")
    with pytest.raises(ValidationError):
        event_from(event_data)
    event_data["related_player_id"] = "a-16"
    assert event_from(event_data).related_player_id == "a-16"


@pytest.mark.parametrize("start,end", [(0, 0), (2, 1), (-1, 10)])
def test_invalid_windows(start: int, end: int) -> None:
    """Empty, reversed or negative time windows cannot reach a metric query."""
    with pytest.raises(ValidationError):
        MatchWindow(period=1, from_ms=start, to_ms=end)


def test_second_half_window_requires_display_clock() -> None:
    """Period-local and display-clock values cannot be silently mixed."""
    with pytest.raises(ValidationError):
        MatchWindow(period=2, from_ms=0, to_ms=1000)
    assert MatchWindow(period=2, from_ms=2_700_000, to_ms=2_701_000).period == 2


def test_subject_must_be_identified() -> None:
    """An unscoped subject is rejected; a player-only subject remains possible."""
    with pytest.raises(ValidationError):
        Subject()
    assert Subject(player_id="a-08").player_id == "a-08"


@pytest.mark.parametrize("unit,value", [("count", 1.5), ("ratio", 1.01), ("ratio", -0.01)])
def test_metric_units(unit: str, value: float) -> None:
    """Metric units constrain values before numerical evidence is queried."""
    data = measured_claim()["assertion"]
    assert isinstance(data, dict)
    data.update(unit=unit, value=value)
    with pytest.raises(ValidationError):
        MetricAssertion.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("patch", [
    {"assertion": None}, {"kind": "event_fact"}, {"evidence_event_ids": []},
    {"evidence_event_ids": ["event-1", "event-1"]}, {"text": "   "},
])
def test_incomplete_claim_rejected(patch: dict[str, object]) -> None:
    """A claim cannot omit its assertion, evidence or meaningful text."""
    data = measured_claim()
    data.update(patch)
    with pytest.raises(ValidationError):
        Claim.model_validate_json(json.dumps(data))


def test_valid_claim_is_not_a_verification() -> None:
    """Structural validity cannot be confused with a query-backed verification result."""
    claim = Claim.model_validate_json(json.dumps(measured_claim()))
    assert claim.kind == "measured_stat"
    assert "verification" not in claim.model_dump()
    assert "verified" not in claim.model_dump()


def test_evidence_uniqueness() -> None:
    """Repeating an event cannot inflate the evidence set."""
    data = {"evidence_id": "ev-1", "match_id": "match-1", "replay_id": "r-1",
            "revision": 1, "window": {"period": 1, "from_ms": 0, "to_ms": 100},
            "event_ids": ["e-1"], "engine_version": "v1", "source_digest": "a" * 64}
    assert EvidenceRecord.model_validate_json(json.dumps(data)).revision == 1
    data["event_ids"] = ["e-1", "e-1"]
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate_json(json.dumps(data))


def test_verification_and_approval_are_distinct() -> None:
    """Checker status is not human approval, and translations have distinct identities."""
    result = VerificationResult(claim_id="c-1", status="blocked", query_id="q-1",
                                reason="The event does not exist", evidence_digest="b" * 64)
    assert "approved" not in result.model_dump()
    data = {"item_id": "i-1", "item_version": 1, "replay_id": "r-1",
            "content_digest": "a" * 64, "evidence_digest": "b" * 64,
            "language": "en", "persona": "analyst"}
    first = ApprovalBinding.model_validate_json(json.dumps(data))
    data["language"] = "es"
    assert content_digest(first) != content_digest(ApprovalBinding.model_validate_json(json.dumps(data)))


def test_json_schema_accepts_fixture(event_data: dict[str, object]) -> None:
    """The exported structural schema and Python boundary agree on a valid event."""
    Draft202012Validator(MatchEvent.model_json_schema()).validate(event_data)


def test_exported_schemas_have_no_drift() -> None:
    """A contract change fails until a versioned baseline change is reviewed explicitly."""
    assert check_exports() == []


def test_evidence_array_schema_keeps_item_constraints() -> None:
    """JSON normalisation must preserve array item limits, not string-length keywords."""
    for model, field in ((Claim, "evidence_event_ids"), (EvidenceRecord, "event_ids")):
        schema = model.model_json_schema()["properties"][field]
        assert schema["minItems"] == 1
        assert schema["maxItems"] == 4096
        assert "minLength" not in schema


def test_window_rejects_boolean_period() -> None:
    """A boolean cannot select period one merely because True equals 1 in Python."""
    with pytest.raises(ValidationError):
        MatchWindow.model_validate_json('{"period":true,"from_ms":0,"to_ms":1000}')
