"""Offline Phase 3D audience generation contract tests; no live-model expenditure."""

import asyncio
from unittest.mock import patch

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


def test_slow_provider_fails_closed_without_adapted_draft() -> None:
    """A stalled provider cannot produce an implicitly accepted adaptation."""

    class StalledProvider:
        """Offline cooperative coroutine to exercise the real deadline."""

        async def propose(self, prompt: str) -> object:
            """Yield without completing; the deadline must cancel this task."""
            del prompt
            await asyncio.Event().wait()
            return {}

    request = AudienceDraftRequest(
        source=_source(), output_id="variant-timeout", language="en", persona="analyst"
    )
    with patch("matchdesk.domain.audience_generation._PROVIDER_TIMEOUT_SECONDS", 0.01):
        with pytest.raises(ValueError, match="deadline exceeded"):
            asyncio.run(propose_audience_variant(request, StalledProvider()))


def test_provider_failure_propagates_without_an_approved_draft() -> None:
    """A provider exception cannot be interpreted as a usable response."""

    class FailingProvider:
        """Offline failure injection; no external model is contacted."""

        async def propose(self, prompt: str) -> object:
            """Fail after receiving an otherwise valid bounded request."""
            del prompt
            raise RuntimeError("offline provider failed")

    request = AudienceDraftRequest(
        source=_source(), output_id="variant-error", language="fr", persona="casual_fan"
    )
    with pytest.raises(RuntimeError, match="offline provider failed"):
        asyncio.run(propose_audience_variant(request, FailingProvider()))


def test_provider_that_suppresses_cancellation_cannot_return_late_copy() -> None:
    """A late result remains denied even when a provider mishandles cancellation."""

    class CancellationSuppressingProvider:
        """Offline malicious/non-cooperative provider used only for timeout probing."""

        async def propose(self, prompt: str) -> object:
            """Return a superficially valid proposal after swallowing cancellation."""
            del prompt
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return {"kind": "commentary", "lines": [{"claim_id": "claim-1", "text": "Late."}]}
            return {}

    request = AudienceDraftRequest(
        source=_source(), output_id="late-variant", language="en", persona="analyst"
    )
    with patch("matchdesk.domain.audience_generation._PROVIDER_TIMEOUT_SECONDS", 0.01):
        with pytest.raises(ValueError, match="deadline exceeded"):
            asyncio.run(propose_audience_variant(request, CancellationSuppressingProvider()))


def test_model_copy_bypass_cannot_inject_invalid_typed_provider_payload() -> None:
    """Always revalidate a provider-supplied Pydantic instance from actual JSON."""

    valid = CommentaryPayload.model_validate(
        {"lines": [{"claim_id": "claim-1", "text": "Valid source-linked sentence."}]}
    )
    # Pydantic's update helper bypasses min_length; the proposal edge must not.
    invalid = valid.model_copy(update={"lines": ()})
    provider = OfflineProvider(invalid)
    request = AudienceDraftRequest(
        source=_source(), output_id="bad-model", language="fr", persona="analyst"
    )
    with pytest.raises(ValidationError, match="too_short"):
        asyncio.run(propose_audience_variant(request, provider))


def test_large_model_copy_payload_rejected_before_draft_construction() -> None:
    """A forged model instance cannot evade the byte-budget output boundary."""

    valid = CommentaryPayload.model_validate({"lines": [{"claim_id": "claim-1", "text": "Safe."}]})
    forged_line = valid.lines[0].model_copy(update={"text": "X" * 262_145})
    forged = valid.model_copy(update={"lines": (forged_line,)})
    provider = OfflineProvider(forged)
    request = AudienceDraftRequest(
        source=_source(), output_id="oversized-model", language="es", persona="casual_fan"
    )
    with pytest.raises(ValueError, match="bounded response size"):
        asyncio.run(propose_audience_variant(request, provider))


def test_tampered_source_is_denied_before_any_provider_call() -> None:
    """Do not leak structurally inconsistent source drafts to an external adapter."""

    source = _source()
    tampered = source.model_copy(
        update={"binding": source.binding.model_copy(update={"content_digest": "b" * 64})}
    )
    provider = OfflineProvider({"kind": "commentary"})
    request = AudienceDraftRequest(
        source=tampered, output_id="tampered-source", language="en", persona="analyst"
    )
    with pytest.raises(ValidationError, match="digest"):
        asyncio.run(propose_audience_variant(request, provider))
    assert provider.prompts == []
