"""Microsoft Agent Framework / Foundry specialist runtime adapter for MatchDesk Phase 2D.

The adapter is activation-gated, bounded and host-controlled. It imports the optional
Agent Framework integration lazily so MatchDesk stays fail-closed when live-runtime
dependencies or credentials are unavailable. P2-03 remains the authority boundary:
the live runtime receives a SpecialistRequest plus read-only ScopedReadTools and returns
only a SpecialistResponse proposal.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Mapping, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from matchdesk.domain.models import Claim
from matchdesk.domain.orchestration import SpecialistRole
from matchdesk.domain.specialists import ScopedReadTools, SpecialistRequest, SpecialistResponse

_ENV_ENABLED = "MATCHDESK_FOUNDRY_ENABLED"
_ENV_ENDPOINT = "FOUNDRY_PROJECT_ENDPOINT"
_ENV_MODEL = "FOUNDRY_MODEL"

_MAX_INSTRUCTION_CHARS = 4_000
_MAX_CONTEXT_CHARS = 16_000
_MAX_OUTPUT_TOKENS = 1_200


class FoundryRuntimeUnavailable(RuntimeError):
    """Raised when the live Foundry runtime is intentionally unavailable."""


@dataclass(frozen=True)
class FoundryRuntimeConfig:
    """Explicit live-runtime configuration with no implicit credential discovery."""

    enabled: bool
    project_endpoint: str | None
    model: str | None
    max_output_tokens: int = _MAX_OUTPUT_TOKENS

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "FoundryRuntimeConfig":
        """Build configuration from explicit environment variables only."""
        source = os.environ if env is None else env
        enabled = source.get(_ENV_ENABLED, "").strip().lower() == "true"
        endpoint = source.get(_ENV_ENDPOINT)
        model = source.get(_ENV_MODEL)
        return cls(
            enabled=enabled,
            project_endpoint=endpoint.strip() if endpoint else None,
            model=model.strip() if model else None,
        )

    def validate_activation(self) -> None:
        """Fail closed unless all live-runtime activation inputs are present."""
        if not self.enabled:
            raise FoundryRuntimeUnavailable("Foundry runtime activation is disabled")
        if not self.project_endpoint:
            raise FoundryRuntimeUnavailable(f"Missing required {_ENV_ENDPOINT}")
        if not self.model:
            raise FoundryRuntimeUnavailable(f"Missing required {_ENV_MODEL}")
        if not 1 <= self.max_output_tokens <= _MAX_OUTPUT_TOKENS:
            raise FoundryRuntimeUnavailable(
                f"max_output_tokens must be between 1 and {_MAX_OUTPUT_TOKENS}"
            )


class RuntimeProposal(BaseModel):
    """Structured, non-authoritative output returned by the live specialist runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(default="", max_length=8_000)
    proposed_claims: tuple[Claim, ...] = ()

    def to_specialist_response(self, role: SpecialistRole) -> SpecialistResponse:
        """Convert structured model output into the P2-03 proposal envelope."""
        return SpecialistResponse(
            role=role,
            proposed_claims=self.proposed_claims,
            content=self.content,
        )


class _AgentLike(Protocol):
    """Minimal Agent Framework surface consumed by this adapter."""

    async def run(self, prompt: str, **kwargs: Any) -> Any:
        """Execute one bounded specialist turn."""


class _AgentFactory(Protocol):
    """Construct one ephemeral in-process agent for a specialist turn."""

    def create(
        self,
        *,
        role: SpecialistRole,
        config: FoundryRuntimeConfig,
    ) -> _AgentLike:
        """Create one role-bound ephemeral agent."""


_ROLE_INSTRUCTIONS: Mapping[SpecialistRole, str] = {
    "tactical_analyst": (
        "Analyse only the supplied deterministic football evidence. "
        "Never invent events, measurements or identities. Propose tactical-inference "
        "claims with explicit evidence_event_ids when appropriate."
    ),
    "narrative_composer": (
        "Draft concise football narrative using only supplied deterministic evidence and "
        "verification records. Do not upgrade inference to fact. Measured-stat claims must "
        "use the existing Claim/MetricAssertion contract."
    ),
    "editorial_reviewer": (
        "Review proposed football copy for unsupported claims, ambiguity and evidence "
        "mismatch. Return only revised non-authoritative content/claims. Do not approve "
        "publication."
    ),
    "audience_adapter": (
        "Adapt only already verified/supported material for audience clarity. Do not access "
        "raw events, introduce new factual claims or grant publication authority."
    ),
}


def _tool_context(request: SpecialistRequest, tools: ScopedReadTools) -> str:
    """Serialize only the host-approved read scope into a bounded model context."""
    payload: dict[str, Any] = {
        "workflow": {
            "workflow_id": request.workflow.workflow_id,
            "match_id": request.workflow.match_id,
            "replay_id": request.workflow.replay_id,
            "revision": request.workflow.revision,
            "moment_id": request.workflow.moment_id,
            "role": request.role,
        },
        "read_scope": tools.snapshot(),
    }

    context = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    if len(context) > _MAX_CONTEXT_CHARS:
        raise ValueError("Live specialist context exceeds bounded size")
    return context


def build_specialist_prompt(
    request: SpecialistRequest,
    tools: ScopedReadTools,
) -> str:
    """Build the bounded role prompt without exposing approval or publication controls."""
    instruction = request.instruction.strip()
    if len(instruction) > _MAX_INSTRUCTION_CHARS:
        raise ValueError("Specialist instruction exceeds bounded size")
    role_instruction = _ROLE_INSTRUCTIONS[request.role]
    context = _tool_context(request, tools)
    return (
        f"ROLE POLICY:\n{role_instruction}\n\n"
        f"USER TASK:\n{instruction}\n\n"
        f"HOST-SCOPED CONTEXT:\n{context}\n\n"
        "Return only the structured RuntimeProposal schema."
    )


class AgentFrameworkFoundryExecutor:
    """Live P2-04 executor using one ephemeral Agent Framework agent per specialist turn."""

    def __init__(
        self,
        *,
        config: FoundryRuntimeConfig | None = None,
        factory: _AgentFactory | None = None,
    ) -> None:
        """Create a fail-closed executor; no network call occurs during construction."""
        self._config = FoundryRuntimeConfig.from_env() if config is None else config
        self._factory = factory

    async def execute(
        self,
        request: SpecialistRequest,
        tools: ScopedReadTools,
    ) -> SpecialistResponse:
        """Run one bounded live specialist turn and return a non-authoritative proposal."""
        self._config.validate_activation()
        factory = self._factory or _load_default_factory()
        agent = factory.create(role=request.role, config=self._config)
        prompt = build_specialist_prompt(request, tools)
        result = await agent.run(
            prompt,
            options={
                "response_format": RuntimeProposal,
                "max_tokens": self._config.max_output_tokens,
                "store": False,
            },
        )
        proposal = _extract_proposal(result)
        return proposal.to_specialist_response(request.role)


def _extract_proposal(result: Any) -> RuntimeProposal:
    """Extract one RuntimeProposal from common Agent Framework response shapes."""
    value = getattr(result, "value", None)
    if isinstance(value, RuntimeProposal):
        return value

    parsed = getattr(result, "parsed", None)
    if isinstance(parsed, RuntimeProposal):
        return parsed

    text = getattr(result, "text", None)
    if isinstance(text, str):
        return RuntimeProposal.model_validate_json(text)

    if isinstance(result, RuntimeProposal):
        return result
    raise ValueError("Foundry runtime did not return the required RuntimeProposal")


class _DefaultAgentFactory:
    """Lazy Microsoft Agent Framework factory used only when live activation is enabled."""

    def create(
        self,
        *,
        role: SpecialistRole,
        config: FoundryRuntimeConfig,
    ) -> _AgentLike:
        """Create one ephemeral Agent backed by FoundryChatClient."""
        try:
            agent_module = import_module("agent_framework")
            foundry_module = import_module("agent_framework.foundry")
            identity_module = import_module("azure.identity")
        except ImportError as error:
            raise FoundryRuntimeUnavailable(
                "Live Foundry dependencies are not installed/pinned in this build"
            ) from error

        agent_type = agent_module.Agent
        client_type = foundry_module.FoundryChatClient
        credential_type = identity_module.AzureCliCredential

        credential = credential_type()
        client = client_type(
            project_endpoint=cast(str, config.project_endpoint),
            model=cast(str, config.model),
            credential=credential,
        )
        return cast(
            _AgentLike,
            agent_type(
                client=client,
                instructions=_ROLE_INSTRUCTIONS[role],
                name=f"matchdesk-{role.replace('_', '-')}",
            ),
        )


def _load_default_factory() -> _AgentFactory:
    """Return the lazy Agent Framework factory without importing optional packages yet."""
    return _DefaultAgentFactory()
