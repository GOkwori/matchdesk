"""Phase 2D tests for the gated Agent Framework / Foundry runtime adapter."""

import asyncio
import json

import pytest

from matchdesk.domain.foundry_runtime import (
    AgentFrameworkFoundryExecutor,
    FoundryRuntimeConfig,
    FoundryRuntimeUnavailable,
    RuntimeProposal,
    build_specialist_prompt,
)
from matchdesk.domain.models import (
    Claim,
    EvidenceRecord,
    MatchWindow,
    VerificationResult,
)
from matchdesk.domain.orchestration import (
    apply_verification_gate,
    record_specialist_attempt,
    start_workflow,
)
from matchdesk.domain.simulator import generate_scenario
from matchdesk.domain.specialists import ScopedReadTools, SpecialistRequest


def _events():
    """Return deterministic accepted events for live-runtime adapter tests."""
    return generate_scenario("counter_attack_goal", 7).events


def _evidence(events):
    """Bind all deterministic fixture events to one evidence record."""
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
    """Advance one workflow to the requested specialist role."""
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
    return apply_verification_gate(state, passed=True, reason="verified")


def _request(role: str, instruction: str = "Do the bounded specialist task.") -> SpecialistRequest:
    """Create one valid role-bound specialist request."""
    return SpecialistRequest(
        workflow=_workflow_for(role),
        role=role,
        instruction=instruction,
    )


def test_runtime_config_is_fail_closed_when_disabled() -> None:
    """Live execution cannot activate without an explicit true enable flag."""
    config = FoundryRuntimeConfig.from_env(
        {
            "MATCHDESK_FOUNDRY_ENABLED": "false",
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/p",
            "FOUNDRY_MODEL": "model-1",
        }
    )

    with pytest.raises(FoundryRuntimeUnavailable, match="disabled"):
        config.validate_activation()


def test_runtime_config_requires_endpoint_and_model() -> None:
    """Explicit activation still fails closed when endpoint or model is absent."""
    config = FoundryRuntimeConfig.from_env({"MATCHDESK_FOUNDRY_ENABLED": "true"})

    with pytest.raises(FoundryRuntimeUnavailable, match="FOUNDRY_PROJECT_ENDPOINT"):
        config.validate_activation()

    config = FoundryRuntimeConfig.from_env(
        {
            "MATCHDESK_FOUNDRY_ENABLED": "true",
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/p",
        }
    )
    with pytest.raises(FoundryRuntimeUnavailable, match="FOUNDRY_MODEL"):
        config.validate_activation()


def test_runtime_config_bounds_output_tokens() -> None:
    """P2-04 model output budget cannot exceed the locked adapter ceiling."""
    config = FoundryRuntimeConfig(
        enabled=True,
        project_endpoint="https://example.services.ai.azure.com/api/projects/p",
        model="model-1",
        max_output_tokens=1_201,
    )

    with pytest.raises(FoundryRuntimeUnavailable, match="between 1 and 1200"):
        config.validate_activation()


def test_prompt_contains_only_role_scoped_snapshot() -> None:
    """Audience adaptation receives verification/evidence but never raw events."""
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
    tools = ScopedReadTools(
        role="audience_adapter",
        events=events,
        evidence_records=(evidence,),
        verification_results=(verification,),
    )

    prompt = build_specialist_prompt(
        _request("audience_adapter"),
        tools,
    )

    assert "audience clarity" in prompt
    assert '"evidence_records"' in prompt
    assert '"verification_results"' in prompt
    assert '"events"' not in prompt


def test_prompt_rejects_unbounded_instruction() -> None:
    """Live requests cannot expand token spend through an unbounded instruction."""
    tools = ScopedReadTools(role="tactical_analyst", events=_events())

    with pytest.raises(ValueError, match="instruction exceeds"):
        build_specialist_prompt(
            _request("tactical_analyst", "x" * 4_001),
            tools,
        )


def test_prompt_context_is_valid_json_payload() -> None:
    """The host-produced snapshot is deterministic JSON rather than free-form hidden state."""
    tools = ScopedReadTools(role="tactical_analyst", events=_events())
    prompt = build_specialist_prompt(_request("tactical_analyst"), tools)

    context = prompt.split("HOST-SCOPED CONTEXT:\n", 1)[1].split(
        "\n\nReturn only",
        1,
    )[0]
    parsed = json.loads(context)

    assert parsed["workflow"]["role"] == "tactical_analyst"
    assert parsed["read_scope"]["allowed_tools"] == [
        "event_by_id",
        "events_in_window",
        "metric",
    ]
    assert parsed["read_scope"]["events"]


def test_live_executor_uses_structured_output_and_locked_run_options() -> None:
    """The Agent Framework call receives response schema, output cap and store=False."""
    class FakeAgent:
        """Capture one bounded Agent.run invocation."""

        def __init__(self) -> None:
            self.prompt = ""
            self.kwargs = {}

        async def run(self, prompt, **kwargs):
            """Return one structured proposal while recording bounded run options."""
            self.prompt = prompt
            self.kwargs = kwargs
            return RuntimeProposal(content="Bounded live proposal.")

    class FakeFactory:
        """Return the fake agent without importing any optional live dependency."""

        def __init__(self) -> None:
            self.agent = FakeAgent()
            self.role = None
            self.config = None

        def create(self, *, role, config):
            """Capture role/config and return the fake agent."""
            self.role = role
            self.config = config
            return self.agent

    factory = FakeFactory()
    config = FoundryRuntimeConfig(
        enabled=True,
        project_endpoint="https://example.services.ai.azure.com/api/projects/p",
        model="model-1",
        max_output_tokens=600,
    )
    executor = AgentFrameworkFoundryExecutor(config=config, factory=factory)

    response = asyncio.run(
        executor.execute(
            _request("tactical_analyst"),
            ScopedReadTools(role="tactical_analyst", events=_events()),
        )
    )

    assert response.role == "tactical_analyst"
    assert response.content == "Bounded live proposal."
    assert factory.role == "tactical_analyst"
    assert factory.config == config
    assert factory.agent.kwargs["response_format"] is RuntimeProposal
    assert factory.agent.kwargs["max_tokens"] == 600
    assert factory.agent.kwargs["store"] is False


def test_live_executor_preserves_existing_claim_contract() -> None:
    """Structured model output reuses Claim and cannot invent an authority-bearing schema."""
    claim = Claim(
        claim_id="claim-1",
        text="The recovery created a dangerous transition.",
        kind="tactical_inference",
        evidence_event_ids=("ca-recovery-home", "ca-shot-home"),
    )

    class FakeAgent:
        """Return a structured proposal containing one existing Claim record."""

        async def run(self, prompt, **kwargs):
            """Return the deterministic fake structured proposal."""
            return RuntimeProposal(proposed_claims=(claim,))

    class FakeFactory:
        """Provide the fake structured-output agent."""

        def create(self, *, role, config):
            """Return the fake agent for the requested role."""
            return FakeAgent()

    response = asyncio.run(
        AgentFrameworkFoundryExecutor(
            config=FoundryRuntimeConfig(
                enabled=True,
                project_endpoint="https://example.services.ai.azure.com/api/projects/p",
                model="model-1",
            ),
            factory=FakeFactory(),
        ).execute(
            _request("narrative_composer"),
            ScopedReadTools(
                role="narrative_composer",
                events=_events(),
                evidence_records=(_evidence(_events()),),
            ),
        )
    )

    assert response.proposed_claims == (claim,)
    assert not hasattr(response, "approved")
    assert not hasattr(response, "publish")


def test_executor_does_not_touch_factory_when_activation_is_disabled() -> None:
    """Disabled live runtime fails before any client or credential object is created."""
    class ExplodingFactory:
        """Fail if construction is attempted despite disabled activation."""

        def create(self, *, role, config):
            """Signal incorrect factory use."""
            raise AssertionError("factory must not be touched")

    executor = AgentFrameworkFoundryExecutor(
        config=FoundryRuntimeConfig(
            enabled=False,
            project_endpoint=None,
            model=None,
        ),
        factory=ExplodingFactory(),
    )

    with pytest.raises(FoundryRuntimeUnavailable, match="disabled"):
        asyncio.run(
            executor.execute(
                _request("tactical_analyst"),
                ScopedReadTools(role="tactical_analyst", events=_events()),
            )
        )


def test_scoped_snapshot_remains_role_restricted() -> None:
    """Foundry serialization cannot bypass the P2-03 read permission matrix."""
    events = _events()
    evidence = _evidence(events)
    verification = VerificationResult(
        claim_id="claim-1",
        status="supported_inference",
        query_id="evidence-support-v1",
        reason="supported",
        evidence_digest="b" * 64,
    )

    tactical = ScopedReadTools(role="tactical_analyst", events=events).snapshot()
    audience = ScopedReadTools(
        role="audience_adapter",
        events=events,
        evidence_records=(evidence,),
        verification_results=(verification,),
    ).snapshot()

    assert "events" in tactical
    assert "evidence_records" not in tactical
    assert "events" not in audience
    assert "evidence_records" in audience
    assert "verification_results" in audience
