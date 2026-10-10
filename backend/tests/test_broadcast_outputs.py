"""Phase 3C broadcast contract tests: shape, identity, claim links and scope."""

import json

import pytest
from jsonschema import Draft202012Validator
from matchdesk.domain.broadcast_outputs import (
    BroadcastEnvelope,
    CommentaryPayload,
    ExplainerPayload,
    FullTimeRecapPayload,
    HalfTimeRecapPayload,
    OverlayPayload,
)
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import ApprovalBinding
from pydantic import ValidationError

from scripts.export_contracts import expected_exports


def _statement(
    claim_id: str = "claim-1", text: str = "An evidence-linked moment."
) -> dict[str, str]:
    """Build a draft statement with a claim reference, not a truth assertion."""
    return {"claim_id": claim_id, "text": text}


def _metric() -> dict[str, object]:
    """Build a typed numerical overlay whose formula still needs actual verification."""
    return {
        "label": "Shots",
        "claim_id": "claim-2",
        "assertion": {
            "metric": "shots.v1",
            "subject": {"team_id": "team-a"},
            "window": {"period": 1, "from_ms": 0, "to_ms": 2_700_000},
            "value": 7.0,
            "unit": "count",
        },
    }


def _payload(kind: str) -> dict[str, object]:
    """Provide all five specified broadcast outputs using deterministic fixtures."""
    if kind == "commentary":
        return {"kind": kind, "lines": [_statement()]}
    if kind == "explainer":
        return {
            "kind": kind,
            "headline": _statement(),
            "points": [_statement("claim-2", "An evidence-linked explanation.")],
        }
    if kind == "overlay":
        return {"kind": kind, "headline": _statement(), "metrics": [_metric()]}
    return {
        "kind": kind,
        "headline": _statement(),
        "highlights": [_statement("claim-2", "An evidence-linked highlight.")],
    }


def _windows(kind: str) -> list[dict[str, int]]:
    """Use the match clock's period-specific, half-open window convention."""
    first = {"period": 1, "from_ms": 0, "to_ms": 2_700_000}
    second = {"period": 2, "from_ms": 2_700_000, "to_ms": 5_400_000}
    if kind == "full_time_recap":
        return [first, second]
    return [first]


def _envelope(kind: str = "commentary") -> dict[str, object]:
    """Bind draft content to an exact versioned approval identity, without approving it."""
    payload = _payload(kind)
    model = {
        "commentary": CommentaryPayload,
        "explainer": ExplainerPayload,
        "overlay": OverlayPayload,
        "half_time_recap": HalfTimeRecapPayload,
        "full_time_recap": FullTimeRecapPayload,
    }[kind].model_validate(payload)
    claims = {"claim-1"} if kind == "commentary" else {"claim-1", "claim-2"}
    return {
        "output_id": "output-1",
        "session_id": "judge-1",
        "match_id": "match-1",
        "binding": {
            "item_id": "story-1",
            "item_version": 1,
            "replay_id": "replay-1",
            "content_digest": content_digest(model),
            "evidence_digest": "a" * 64,
            "language": "en",
            "persona": "analyst",
        },
        "windows": _windows(kind),
        "evidence_ids": ["evidence-1"],
        "claim_ids": sorted(claims),
        "payload": payload,
    }


@pytest.mark.parametrize(
    "kind",
    ["commentary", "explainer", "overlay", "half_time_recap", "full_time_recap"],
)
def test_all_broadcast_kinds_have_immutable_json_round_trips(kind: str) -> None:
    """Every defined output shape keeps its identities through JSON transport."""
    envelope = BroadcastEnvelope.model_validate_json(json.dumps(_envelope(kind)))
    assert envelope.payload.kind == kind
    assert isinstance(envelope.binding, ApprovalBinding)
    assert len(envelope.claim_ids) >= 1
    assert BroadcastEnvelope.model_validate_json(envelope.model_dump_json()) == envelope
    assert envelope.binding.content_digest == content_digest(envelope.payload)
    with pytest.raises(ValidationError):
        envelope.output_id = "altered"


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("commentary", 1),
        ("explainer", 1),
        ("overlay", 1),
        ("half_time_recap", 1),
        ("full_time_recap", 2),
    ],
)
def test_broadcast_periods_are_explicit(kind: str, expected: int) -> None:
    """Only a full-time recap may span both half-open match periods."""
    envelope = BroadcastEnvelope.model_validate_json(json.dumps(_envelope(kind)))
    assert len(envelope.windows) == expected
    assert tuple(window.period for window in envelope.windows) == tuple(range(1, expected + 1))


@pytest.mark.parametrize("kind", ["commentary", "explainer", "overlay"])
def test_non_recap_output_cannot_cover_two_periods(kind: str) -> None:
    """Moment-type envelopes must not quietly masquerade as match-wide recaps."""
    draft = _envelope(kind)
    draft["windows"] = _windows("full_time_recap")
    with pytest.raises(ValidationError, match="require one window"):
        BroadcastEnvelope.model_validate_json(json.dumps(draft))


@pytest.mark.parametrize(
    "kind,windows",
    [
        ("half_time_recap", [{"period": 2, "from_ms": 2_700_000, "to_ms": 5_400_000}]),
        ("half_time_recap", [{"period": 1, "from_ms": 1000, "to_ms": 2_700_000}]),
        ("full_time_recap", [{"period": 1, "from_ms": 0, "to_ms": 2_700_000}]),
        (
            "full_time_recap",
            [
                {"period": 2, "from_ms": 2_700_000, "to_ms": 5_400_000},
                {"period": 1, "from_ms": 0, "to_ms": 2_700_000},
            ],
        ),
        (
            "full_time_recap",
            [
                {"period": 1, "from_ms": 0, "to_ms": 2_700_000},
                {"period": 2, "from_ms": 2_700_001, "to_ms": 5_400_000},
            ],
        ),
    ],
)
def test_recap_scope_requires_correct_half_boundaries(
    kind: str, windows: list[dict[str, int]]
) -> None:
    """A recap declares its canonical half coverage rather than borrowing an unrelated window."""
    draft = _envelope(kind)
    draft["windows"] = windows
    with pytest.raises(ValidationError):
        BroadcastEnvelope.model_validate_json(json.dumps(draft))


@pytest.mark.parametrize(
    "patch",
    [
        {"claim_ids": []},
        {"claim_ids": ["claim-1", "claim-1"]},
        {"claim_ids": ["claim-1", "unknown"]},
        {"evidence_ids": []},
        {"evidence_ids": ["evidence-1", "evidence-1"]},
        {"session_id": ""},
        {"match_id": "other/match"},
        {"extra_authorization": True},
    ],
)
def test_missing_duplicate_or_extra_scope_is_rejected(patch: dict[str, object]) -> None:
    """The envelope is closed and retains meaningful, unique claim/evidence references."""
    draft = _envelope()
    draft.update(patch)
    with pytest.raises(ValidationError):
        BroadcastEnvelope.model_validate_json(json.dumps(draft))


def test_content_edit_without_new_approval_digest_is_rejected() -> None:
    """Editing a headline after producer review invalidates the exact binding."""
    draft = _envelope("explainer")
    payload = draft["payload"]
    assert isinstance(payload, dict)
    payload["headline"] = _statement("claim-1", "Edited factual headline")
    with pytest.raises(ValidationError, match="payload digest"):
        BroadcastEnvelope.model_validate_json(json.dumps(draft))


def test_claim_reference_edit_without_envelope_update_is_rejected() -> None:
    """A fabricated claim reference cannot bypass the envelope's declared claim set."""
    draft = _envelope("explainer")
    payload = draft["payload"]
    assert isinstance(payload, dict)
    payload["points"] = [_statement("claim-forged", "Inserted assertion.")]
    # A new content hash alone cannot sidestep mandatory claim-set completeness.
    validated_payload = ExplainerPayload.model_validate(payload)
    binding = draft["binding"]
    assert isinstance(binding, dict)
    binding["content_digest"] = content_digest(validated_payload)
    with pytest.raises(ValidationError, match="claims must exactly match"):
        BroadcastEnvelope.model_validate_json(json.dumps(draft))


@pytest.mark.parametrize("kind", ["commentary", "explainer", "overlay", "half_time_recap"])
def test_blank_or_extraneous_payload_fields_are_rejected(kind: str) -> None:
    """The strict typed payloads reject an unmodelled fact or whitespace-only content."""
    draft = _envelope(kind)
    payload = draft["payload"]
    assert isinstance(payload, dict)
    payload["unverified_claim"] = "goal"
    with pytest.raises(ValidationError):
        BroadcastEnvelope.model_validate_json(json.dumps(draft))
    payload.pop("unverified_claim")
    field = "lines" if kind == "commentary" else "headline"
    if field == "lines":
        payload["lines"] = [_statement(text="   ")]
    else:
        payload["headline"] = _statement(text="   ")
    with pytest.raises(ValidationError):
        BroadcastEnvelope.model_validate_json(json.dumps(draft))


@pytest.mark.parametrize(
    "metric_patch",
    [
        {"label": "   "},
        {"assertion": {"metric": "unregistered.v1"}},
        {"assertion": {"unit": "ratio"}},
        {"assertion": {"comparator": "gte"}},
        {"assertion": {"value": 1.5}},
        {"assertion": {"value": True}},
    ],
)
def test_overlay_requires_registered_precise_metric_values(metric_patch: dict[str, object]) -> None:
    """Overlay JSON cannot introduce unknown metrics, loose comparisons or invalid values."""
    draft = _envelope("overlay")
    payload = draft["payload"]
    assert isinstance(payload, dict)
    metric = _metric()
    for key, value in metric_patch.items():
        if key == "assertion":
            assertion = metric["assertion"]
            assert isinstance(assertion, dict)
            assert isinstance(value, dict)
            assertion.update(value)
        else:
            metric[key] = value
    payload["metrics"] = [metric]
    with pytest.raises(ValidationError):
        BroadcastEnvelope.model_validate_json(json.dumps(draft))


def test_unknown_output_kind_is_rejected() -> None:
    """No unreviewed kind can silently cross the discriminated output boundary."""
    draft = _envelope()
    draft["payload"] = {"kind": "audio", "lines": [_statement()]}
    with pytest.raises(ValidationError, match="union_tag_invalid"):
        BroadcastEnvelope.model_validate_json(json.dumps(draft))


def test_json_schema_is_a_valid_draft_2020_12_contract() -> None:
    """The published output envelope is directly consumable by JSON-schema clients."""
    schema = BroadcastEnvelope.model_json_schema()
    Draft202012Validator.check_schema(schema)
    assert "discriminator" in schema["properties"]["payload"]
    assert "authorization" not in schema["properties"]
    assert "verified" not in schema["properties"]
    Draft202012Validator(schema).validate(
        BroadcastEnvelope.model_validate(_envelope("overlay")).model_dump(mode="json")
    )


def test_content_identity_is_language_scoped_but_does_not_grant_publication() -> None:
    """Changing language is a new binding; a valid envelope is not an approval."""
    draft = _envelope()
    envelope = BroadcastEnvelope.model_validate_json(json.dumps(draft))
    binding = draft["binding"]
    assert isinstance(binding, dict)
    binding["language"] = "fr"
    alternate = BroadcastEnvelope.model_validate_json(json.dumps(draft))
    assert alternate.binding != envelope.binding
    assert not hasattr(alternate, "publication_authorized")



def test_exported_broadcast_schema_is_registered_and_versioned() -> None:
    """The frozen export manifest must include the entire version-one payload union."""
    exports = expected_exports()
    name = "BroadcastEnvelope.v1.json"
    assert name in exports
    manifest = json.loads(exports["manifest.json"])
    assert name in manifest["files"]
    schema = json.loads(exports[name])
    assert set(schema["properties"]["payload"]["discriminator"]["mapping"]) == {
        "commentary",
        "explainer",
        "overlay",
        "half_time_recap",
        "full_time_recap",
    }


@pytest.mark.parametrize(
    "model,field,maximum",
    [
        ("BroadcastEnvelope", "windows", 2),
        ("BroadcastEnvelope", "evidence_ids", 4096),
        ("BroadcastEnvelope", "claim_ids", 4096),
        ("CommentaryPayload", "lines", 4),
        ("ExplainerPayload", "points", 8),
        ("OverlayPayload", "metrics", 6),
        ("HalfTimeRecapPayload", "highlights", 12),
        ("FullTimeRecapPayload", "highlights", 16),
    ],
)
def test_exported_array_bounds_have_correct_schema_keywords(
    model: str, field: str, maximum: int
) -> None:
    """External JSON Schema validators must get item limits, never string limits."""
    schema = json.loads(expected_exports()["BroadcastEnvelope.v1.json"])
    properties = schema["properties"] if model == "BroadcastEnvelope" else schema["$defs"][model]["properties"]
    array = properties[field]
    assert array["minItems"] == 1
    assert array["maxItems"] == maximum
    assert "minLength" not in array
    assert "maxLength" not in array
