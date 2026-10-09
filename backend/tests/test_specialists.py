"""Phase 2C tests for specialist interfaces and scoped read-only tools."""

from dataclasses import FrozenInstanceError

import pytest
from matchdesk.domain.models import (
    Claim,
    EvidenceRecord,
    MatchWindow,
    Subject,
    VerificationResult,
)
from matchdesk.domain.orchestration import (
    apply_verification_gate,
    record_specialist_attempt,
    start_workflow,
)
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.specialists import (
    ROLE_READ_TOOLS,
    ScopedReadTools,
    SpecialistRequest,
    SpecialistResponse,
    execute_specialist,
)


def _events():
    """Return deterministic accepted events for specialist read-tool tests."""
    return generate_scenario("counter_attack_goal", 7).events


def _evidence(events):
    """Bind the deterministic event fixture to one immutable evidence record."""
    return EvidenceRecord(
        evidence_id="evidence-1",
        match_id=events[0].match_id,
        replay_id="replay-1",
        revision=1,
        window=MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
        event_ids=tuple(event.event_id for event in events),
        engine_version="engine-v1",
        source_digest="a" * 64,
    )


def _workflow_for(role: str):
    """Advance a workflow deterministically to the requested specialist role."""
    state = start_workflow("wf-1", "match-1", "replay-1", 1, "moment-1")
    if role == "tactical_analyst":
        return state
    state = record_specialist_attempt(
        state,
        "tactical_analyst",
        100,
        "success",
        "analysis complete",
    )
    if role == "narrative_composer":
        return state
    state = record_specialist_attempt(
        state,
        "narrative_composer",
        100,
        "success",
        "draft complete",
    )
    if role == "editorial_reviewer":
        return state
    state = record_specialist_attempt(
        state,
        "editorial_reviewer",
        100,
        "success",
        "review complete",
    )
    state = apply_verification_gate(state, passed=True, reason="verified")
    return state


def test_role_tool_matrix_is_explicit_and_audience_adapter_is_most_restricted() -> None:
    """Permissions are host-owned and audience adaptation cannot inspect raw events."""
    assert ROLE_READ_TOOLS["tactical_analyst"] == {
        "event_by_id",
        "events_in_window",
        "metric",
    }
    assert "event_by_id" not in ROLE_READ_TOOLS["audience_adapter"]
    assert "metric" not in ROLE_READ_TOOLS["audience_adapter"]
    assert ROLE_READ_TOOLS["audience_adapter"] == {
        "evidence_record",
        "verification_result",
    }


def test_tactical_tools_can_read_events_windows_and_registered_metrics() -> None:
    """The tactical specialist gets deterministic football reads but no evidence mutation."""
    events = _events()
    tools = ScopedReadTools(role="tactical_analyst", events=events)

    shot = tools.event_by_id("ca-shot-home")
    assert shot is not None
    window = MatchWindow(period=1, from_ms=0, to_ms=2_100_000)
    assert shot in tools.events_in_window(window)
    assert tools.metric("shots.v1", Subject(team_id="home"), window) == 1.0

    with pytest.raises(PermissionError, match="evidence_record"):
        tools.evidence_record("evidence-1")


def test_narrative_and_editorial_roles_can_read_evidence_and_verification() -> None:
    """Narrative and editorial specialists can inspect deterministic checker output."""
    events = _events()
    evidence = _evidence(events)
    verification = VerificationResult(
        claim_id="claim-1",
        status="verified",
        query_id="metric-shots-v1",
        reason="verified",
        expected=1.0,
        observed=1.0,
        evidence_digest="b" * 64,
    )

    for role in ("narrative_composer", "editorial_reviewer"):
        tools = ScopedReadTools(
            role=role,
            events=events,
            evidence_records=(evidence,),
            verification_results=(verification,),
        )
        assert tools.evidence_record("evidence-1") == evidence
        assert tools.verification_result("claim-1") == verification


def test_audience_adapter_cannot_read_raw_events_or_metrics() -> None:
    """Audience adaptation receives verified artefact reads, not raw deterministic truth."""
    events = _events()
    evidence = _evidence(events)
    verification = VerificationResult(
        claim_id="claim-1",
        status="supported_inference",
        query_id="evidence-support-v1",
        reason="supported",
        evidence_digest="b" * 64,
    )
    tools = ScopedReadTools(
        role="audience_adapter",
        events=events,
        evidence_records=(evidence,),
        verification_results=(verification,),
    )

    assert tools.evidence_record("evidence-1") == evidence
    assert tools.verification_result("claim-1") == verification

    with pytest.raises(PermissionError, match="event_by_id"):
        tools.event_by_id(events[0].event_id)
    with pytest.raises(PermissionError, match="metric"):
        tools.metric(
            "shots.v1",
            Subject(team_id="home"),
            MatchWindow(period=1, from_ms=0, to_ms=2_100_000),
        )


def test_specialist_request_requires_current_running_role() -> None:
    """The host cannot issue a request for a role out of orchestration order."""
    workflow = _workflow_for("tactical_analyst")

    with pytest.raises(ValueError, match="current running workflow role"):
        SpecialistRequest(
            workflow=workflow,
            role="narrative_composer",
            instruction="draft",
        )

    with pytest.raises(ValueError, match="cannot be blank"):
        SpecialistRequest(
            workflow=workflow,
            role="tactical_analyst",
            instruction="   ",
        )


def test_specialist_response_is_frozen_and_has_no_approval_fields() -> None:
    """Specialist output is a proposal rather than an authority-bearing record."""
    response = SpecialistResponse(
        role="tactical_analyst",
        content="Observed transition pressure.",
    )

    with pytest.raises(FrozenInstanceError):
        response.content = "mutated"

    assert not hasattr(response, "approved")
    assert not hasattr(response, "publish")


def test_response_requires_meaningful_output() -> None:
    """An executor cannot claim success while returning an empty proposal."""
    with pytest.raises(ValueError, match="claims or content"):
        SpecialistResponse(role="tactical_analyst")


def test_host_rejects_executor_role_spoofing() -> None:
    """A runtime cannot return output under another specialist's role identity."""

    class WrongRoleExecutor:
        """Return deliberately mislabelled output for host-boundary testing."""

        def execute(self, request, tools):
            """Ignore the request role and return a mismatched response role."""
            return SpecialistResponse(
                role="narrative_composer",
                content="wrong role",
            )

    request = SpecialistRequest(
        workflow=_workflow_for("tactical_analyst"),
        role="tactical_analyst",
        instruction="analyse",
    )

    with pytest.raises(ValueError, match="response role"):
        execute_specialist(WrongRoleExecutor(), request, events=_events())


def test_executor_receives_only_scoped_read_tools() -> None:
    """The host injects read scope and the executor cannot request broader raw access."""

    class TacticalExecutor:
        """Exercise only the host-provided tactical read scope."""

        def execute(self, request, tools):
            """Read one permitted event and return a non-authoritative proposal."""
            assert request.role == "tactical_analyst"
            assert tools.allowed_tools == ROLE_READ_TOOLS["tactical_analyst"]
            event = tools.event_by_id("ca-shot-home")
            assert event is not None
            return SpecialistResponse(
                role=request.role,
                content=f"Observed {event.type}.",
            )

    request = SpecialistRequest(
        workflow=_workflow_for("tactical_analyst"),
        role="tactical_analyst",
        instruction="analyse",
    )

    response = execute_specialist(TacticalExecutor(), request, events=_events())

    assert response.content == "Observed shot."


def test_specialist_can_propose_existing_claim_contract_without_mutating_it() -> None:
    """P2-03 reuses Claim rather than inventing an unverified parallel fact schema."""
    claim = Claim(
        claim_id="claim-1",
        text="The transition created a dangerous chance.",
        kind="tactical_inference",
        evidence_event_ids=("ca-recovery-home", "ca-shot-home"),
    )

    response = SpecialistResponse(
        role="narrative_composer",
        proposed_claims=(claim,),
    )

    assert response.proposed_claims == (claim,)


def test_scoped_tools_reject_mixed_match_event_inputs() -> None:
    """A specialist tool snapshot cannot silently combine deterministic truth sources."""
    events = _events()
    foreign = events[-1].model_copy(update={"match_id": "other-match"})

    with pytest.raises(ValueError, match="mix event match identities"):
        ScopedReadTools(
            role="tactical_analyst",
            events=(*events[:-1], foreign),
        )


def test_read_tools_return_none_for_unknown_ids_without_inventing_data() -> None:
    """Missing reads remain explicit instead of fabricating records."""
    tools = ScopedReadTools(role="tactical_analyst", events=_events())

    assert tools.event_by_id("missing-event") is None
