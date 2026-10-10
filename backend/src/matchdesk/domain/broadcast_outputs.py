"""Versioned draft broadcast output contracts for MatchDesk Phase 3C.

These immutable envelopes separate evidence references and reviewed content identity
from factual verification, authenticated producer approval and delivery side effects.
A valid envelope is a draft data shape, never authority to publish.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from matchdesk.domain.hashing import content_digest
from matchdesk.domain.metrics import METRIC_DEFINITIONS
from matchdesk.domain.models import (
    ApprovalBinding,
    Contract,
    Identifier,
    MatchWindow,
    MetricAssertion,
    immutable_array,
)
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


class BroadcastPayload(Contract):
    """Strict immutable content whose canonical digest can be reviewed by a producer."""


class ClaimLinkedText(BaseModel):
    """An authored passage explicitly associated with an upstream claim ID."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, validate_default=True)

    claim_id: Identifier
    text: Annotated[str, Field(min_length=1, max_length=2000)]

    @model_validator(mode="after")
    def reject_blank_text(self) -> Self:
        """Reject whitespace-only claims even when their length is non-zero."""
        if not self.text.strip():
            raise ValueError("Broadcast statement text cannot be blank")
        return self


class CommentaryPayload(BroadcastPayload):
    """One short, ordered play-by-play or analysis commentary draft."""

    kind: Literal["commentary"] = "commentary"
    lines: Annotated[
        tuple[ClaimLinkedText, ...],
        BeforeValidator(immutable_array),
        Field(min_length=1, max_length=4),
    ]


class ExplainerPayload(BroadcastPayload):
    """A headline and ordered explanatory points bound to claim references."""

    kind: Literal["explainer"] = "explainer"
    headline: ClaimLinkedText
    points: Annotated[
        tuple[ClaimLinkedText, ...],
        BeforeValidator(immutable_array),
        Field(min_length=1, max_length=8),
    ]


class OverlayMetric(BaseModel):
    """An overlay number that must be checked against its referenced metric claim."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, validate_default=True)

    label: Annotated[str, Field(min_length=1, max_length=80)]
    claim_id: Identifier
    assertion: MetricAssertion

    @model_validator(mode="after")
    def require_registered_metric(self) -> Self:
        """Disallow unregistered metrics and incompatible units in visual output."""
        if not self.label.strip():
            raise ValueError("Overlay metric label cannot be blank")
        definition = METRIC_DEFINITIONS.get(self.assertion.metric)
        if definition is None:
            raise ValueError("Overlay metric must use a registered formula")
        if self.assertion.unit != definition.unit:
            raise ValueError("Overlay metric unit must match the registered formula")
        if self.assertion.comparator != "eq":
            raise ValueError("Overlay metric must show an exact value, not a bound")
        return self


class OverlayPayload(BroadcastPayload):
    """Structured overlay JSON with claim-bound numbers, not display-string facts."""

    kind: Literal["overlay"] = "overlay"
    headline: ClaimLinkedText
    metrics: Annotated[
        tuple[OverlayMetric, ...],
        BeforeValidator(immutable_array),
        Field(min_length=1, max_length=6),
    ]


class HalfTimeRecapPayload(BroadcastPayload):
    """A first-half draft with claim-linked headline and ordered highlights."""

    kind: Literal["half_time_recap"] = "half_time_recap"
    headline: ClaimLinkedText
    highlights: Annotated[
        tuple[ClaimLinkedText, ...],
        BeforeValidator(immutable_array),
        Field(min_length=1, max_length=12),
    ]


class FullTimeRecapPayload(BroadcastPayload):
    """A two-period draft with claim-linked headline and ordered highlights."""

    kind: Literal["full_time_recap"] = "full_time_recap"
    headline: ClaimLinkedText
    highlights: Annotated[
        tuple[ClaimLinkedText, ...],
        BeforeValidator(immutable_array),
        Field(min_length=1, max_length=16),
    ]


OutputPayload = Annotated[
    CommentaryPayload
    | ExplainerPayload
    | OverlayPayload
    | HalfTimeRecapPayload
    | FullTimeRecapPayload,
    Field(discriminator="kind"),
]


def _payload_claim_ids(payload: OutputPayload) -> set[str]:
    """Extract claim links without treating the linked text as verified evidence."""
    if isinstance(payload, CommentaryPayload):
        return {line.claim_id for line in payload.lines}
    if isinstance(payload, ExplainerPayload):
        return {payload.headline.claim_id, *(point.claim_id for point in payload.points)}
    if isinstance(payload, OverlayPayload):
        return {payload.headline.claim_id, *(metric.claim_id for metric in payload.metrics)}
    return {payload.headline.claim_id, *(item.claim_id for item in payload.highlights)}


class BroadcastEnvelope(Contract):
    """One session/replay-scoped draft with exact content and evidence references.

    The producer-approved binding must use the canonical digest of the complete
    payload, including the versioned kind. This detects payload drift, but does not
    authenticate a producer, prove claim truth or authorize actual publication.
    """

    output_id: Identifier
    session_id: Identifier
    match_id: Identifier
    binding: ApprovalBinding
    windows: Annotated[
        tuple[MatchWindow, ...],
        BeforeValidator(immutable_array),
        Field(min_length=1, max_length=2),
    ]
    evidence_ids: Annotated[
        tuple[Identifier, ...],
        BeforeValidator(immutable_array),
        Field(min_length=1, max_length=4096),
    ]
    claim_ids: Annotated[
        tuple[Identifier, ...],
        BeforeValidator(immutable_array),
        Field(min_length=1, max_length=4096),
    ]
    payload: OutputPayload

    @model_validator(mode="after")
    def validate_draft_binding(self) -> Self:
        """Enforce content identity, complete claim links and typed period coverage."""
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Broadcast evidence IDs must be unique")
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError("Broadcast claim IDs must be unique")
        if set(self.claim_ids) != _payload_claim_ids(self.payload):
            raise ValueError("Broadcast claims must exactly match the payload references")
        if self.binding.content_digest != content_digest(self.payload):
            raise ValueError("Broadcast payload digest must match the reviewed content binding")

        kind = self.payload.kind
        if kind == "half_time_recap":
            if len(self.windows) != 1 or self.windows[0].period != 1:
                raise ValueError("Half-time recap requires exactly one first-half window")
            if self.windows[0].from_ms != 0:
                raise ValueError("Half-time recap must cover the first half from kick-off")
        elif kind == "full_time_recap":
            if len(self.windows) != 2 or tuple(w.period for w in self.windows) != (1, 2):
                raise ValueError("Full-time recap requires ordered first- and second-half windows")
            if self.windows[0].from_ms != 0 or self.windows[1].from_ms != 2_700_000:
                raise ValueError("Full-time recap windows must begin at each half's start")
        elif len(self.windows) != 1:
            raise ValueError("Moment commentary, explainer and overlay require one window")
        return self
