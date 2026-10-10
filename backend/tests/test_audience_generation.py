"""Offline Phase 3D audience generation contract tests; no live-model expenditure."""

import asyncio

import pytest
from matchdesk.domain.audience_generation import (
    AudienceDraftRequest,
    build_audience_prompt,
    propose_audience_variant,
)
from matchdesk.domain.broadcast_outputs import BroadcastEnvelope, CommentaryPayload
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import ApprovalBinding
from pydantic import ValidationError


def _source() -> BroadcastEnvelope:
    """Build a versioned English source with one evidence-bound claim."""
    payload = CommentaryPayload.model_validate(
        {"lines": [{"claim_id": "claim-1", "text": "The team made two attempts."}]}
    )
    return BroadcastEnvelope(
        output_id="source-1",
        session_id="session-1",
        match_id="match-1",
        binding=ApprovalBinding(
            item_id="item-1",
            item_version=1,
            replay_id="replay-1",
            content_digest=content_digest(payload),
            evidence_digest="a" * 64,
            language="en",
            persona="analyst",
        ),
        windows=({"period": 1, "from_ms": 0, "to_ms": 2700000},),
        evidence_ids=("evidence-1",),
        claim_ids=("claim-1",),
        payload=payload,
    )


class OfflineProvider:
    """Deterministic fake that cannot contact a real language model."""

    def __init__(self, answer: object) -> None:
        """Retain one proposed response for an offline qualification."""
        self.answer = answer
        self.prompts: list[str] = []

    async def propose(self, prompt: str) -> object:
        """Capture the policy prompt and return the configured fake output."""
        self.prompts.append(prompt)
        return self.answer


@pytest.mark.parametrize("language", ["en", "es", "fr"])
@pytest.mark.parametrize("persona", ["analyst", "casual_fan", "broadcast_caption"])
def test_offline_provider_emits_unapproved_scoped_draft(language: str, persona: str) -> None:
    """All nine language/persona combinations retain evidence and claim identity."""
    provider = OfflineProvider(
        {"kind": "commentary", "lines": [{"claim_id": "claim-1", "text": "Draft."}]}
    )
    request = AudienceDraftRequest(
        source=_source(), output_id="variant-1", language=language, persona=persona
    )
    output = asyncio.run(propose_audience_variant(request, provider))
    assert output.binding.language == language
    assert output.binding.persona == persona
    assert output.claim_ids == request.source.claim_ids
    assert output.evidence_ids == request.source.evidence_ids
    assert output.binding.content_digest == content_digest(output.payload)
    assert "Do not approve or publish" in provider.prompts[0]
    assert not hasattr(output, "publication_authorized")


def test_untrusted_provider_cannot_add_new_claim() -> None:
    """A plausible-sounding but unsupported claim cannot enter the draft envelope."""
    provider = OfflineProvider(
        {"kind": "commentary", "lines": [{"claim_id": "invented", "text": "Three goals."}]}
    )
    request = AudienceDraftRequest(
        source=_source(), output_id="variant-1", language="fr", persona="casual_fan"
    )
    with pytest.raises(ValidationError, match="claims must exactly match"):
        asyncio.run(propose_audience_variant(request, provider))


def test_untrusted_provider_cannot_switch_output_kind() -> None:
    """An unapproved model cannot substitute an explainer for commentary."""
    provider = OfflineProvider(
        {
            "kind": "explainer",
            "headline": {"claim_id": "claim-1", "text": "Headline"},
            "points": [{"claim_id": "claim-1", "text": "Point"}],
        }
    )
    request = AudienceDraftRequest(
        source=_source(), output_id="variant-1", language="es", persona="analyst"
    )
    with pytest.raises(ValueError, match="preserve the broadcast output kind"):
        asyncio.run(propose_audience_variant(request, provider))


def test_invalid_provider_payload_rejected() -> None:
    """Malformed generation output must not become an accepted broadcast record."""
    provider = OfflineProvider({"kind": "commentary", "lines": []})
    request = AudienceDraftRequest(
        source=_source(), output_id="variant-1", language="en", persona="analyst"
    )
    with pytest.raises(ValidationError):
        asyncio.run(propose_audience_variant(request, provider))


def test_unsupported_locale_is_not_sent_to_provider() -> None:
    """Host input is validated before a possibly costly provider call."""
    provider = OfflineProvider({})
    request = AudienceDraftRequest(
        source=_source(), output_id="variant-1", language="de", persona="analyst"
    )
    with pytest.raises(ValueError, match="Unsupported audience language"):
        asyncio.run(propose_audience_variant(request, provider))
    assert provider.prompts == []


def test_prompt_distinguishes_untrusted_copy_from_policy() -> None:
    """Source content must be bracketed as data and output remains proposal-only."""
    request = AudienceDraftRequest(
        source=_source(), output_id="variant-1", language="fr", persona="broadcast_caption"
    )
    prompt = build_audience_prompt(request)
    assert "SOURCE_JSON:" in prompt
    assert "untrusted data" in prompt
    assert "independent human meaning/language review" in prompt
