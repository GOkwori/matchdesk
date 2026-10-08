"""Strict data contracts for the first MatchDesk boundary.

These models validate shape and local invariants, not the truth of a story.
Roster validity, temporal ingestion, metric computation and publication authority
are separate responsibilities. A validated Claim is never a verified Claim.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def plain_integer(value: object) -> object:
    """Reject bool before Literal matching: Python otherwise considers True equal to 1."""
    if type(value) is not int:
        raise ValueError("An integer is required; booleans and strings are not integers")
    return value


def plain_boolean(value: object) -> object:
    """Require a real JSON boolean instead of accepting the integer 1 as True."""
    if type(value) is not bool:
        raise ValueError("A boolean is required")
    return value


def immutable_array(value: object) -> object:
    """Normalise JSON arrays only; retain strict validation of each immutable element.

    FastAPI parses JSON before Pydantic receives it. Explicit list-to-tuple
    normalisation makes HTTP validation equivalent to model_validate_json.
    """
    if isinstance(value, list):
        return tuple(value)
    return value


Identifier = Annotated[str, Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9_-]+$")]
MetricIdentifier = Annotated[
    str,
    Field(min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_]*\.v[1-9][0-9]*$"),
]
Period = Annotated[Literal[1, 2], BeforeValidator(plain_integer)]
EventIds = Annotated[tuple[Identifier, ...], BeforeValidator(immutable_array)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
FiniteNumber = Annotated[float, Field(allow_inf_nan=False)]
EventType = Literal[
    "kickoff",
    "pass",
    "carry",
    "dribble",
    "shot",
    "save",
    "tackle",
    "interception",
    "recovery",
    "clearance",
    "foul",
    "card",
    "substitution",
    "goal",
    "period_start",
    "period_end",
]
# Centralising valid outcomes prevents a goal from being accepted as an incomplete pass.
OUTCOMES: dict[str, frozenset[str]] = {
    "kickoff": frozenset({"complete"}),
    "pass": frozenset({"complete", "incomplete"}),
    "carry": frozenset({"complete", "incomplete"}),
    "dribble": frozenset({"complete", "incomplete"}),
    "shot": frozenset({"goal", "saved", "blocked", "off_target", "post"}),
    "save": frozenset({"complete"}),
    "tackle": frozenset({"won", "lost"}),
    "interception": frozenset({"complete"}),
    "recovery": frozenset({"complete"}),
    "clearance": frozenset({"complete", "incomplete"}),
    "foul": frozenset({"committed"}),
    "card": frozenset({"yellow", "second_yellow", "red"}),
    "substitution": frozenset({"complete"}),
    "goal": frozenset({"goal"}),
}


class Contract(BaseModel):
    """Reject unknown fields and coercion; immutable records protect evidence hashes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, validate_default=True)
    schema_version: Literal["1.0"] = "1.0"


class Location(Contract):
    """Position on a 0-100 pitch normalised to the event team's attacking direction.

    Coordinates are not metres. Any distance metric must first convert against
    the documented pitch dimensions. Booleans and non-finite values are invalid.
    """

    x: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
    y: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class MatchEvent(Contract):
    """An immutable synthetic event, identified independently of arrival order.

    match_clock_ms is the display clock: period 2 starts at 45:00 regardless of
    first-half stoppage time. Sequence, not this clock alone, defines ordering.
    linked_event_id associates a goal with its shot; existence is checked later
    by ingestion, not by structural validation.
    """

    event_id: Identifier
    match_id: Identifier
    sequence: Annotated[int, Field(ge=0)]
    period: Period
    match_clock_ms: Annotated[int, Field(ge=0)]
    type: EventType
    team_id: Identifier | None = None
    player_id: Identifier | None = None
    possession_id: Annotated[int, Field(ge=0)] | None = None
    location: Location | None = None
    end_location: Location | None = None
    outcome: str | None = Field(default=None, max_length=32)
    under_pressure: bool = False
    xg: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None = None
    linked_event_id: Identifier | None = None
    related_player_id: Identifier | None = None
    tags: EventIds = ()
    synthetic: Annotated[Literal[True], BeforeValidator(plain_boolean)] = True

    @model_validator(mode="after")
    def validate_event_fields(self) -> Self:
        """Enforce type-specific requirements without inferring missing event data."""
        if self.period == 2 and self.match_clock_ms < 2_700_000:
            raise ValueError("The second-half display clock cannot precede 45:00")
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("Event tags must be unique")
        if self.type in ("period_start", "period_end"):
            if any(
                value is not None
                for value in (
                    self.team_id,
                    self.player_id,
                    self.possession_id,
                    self.location,
                    self.end_location,
                    self.outcome,
                    self.xg,
                    self.linked_event_id,
                    self.related_player_id,
                )
            ):
                raise ValueError("Period markers cannot carry player or on-ball fields")
            return self
        if self.team_id is None or self.player_id is None:
            raise ValueError("A player event requires team_id and player_id")
        if self.outcome not in OUTCOMES[self.type]:
            raise ValueError("Outcome is not valid for this event type")
        if self.type not in ("card", "substitution") and self.location is None:
            raise ValueError("An on-ball event requires a location")
        if self.type in ("pass", "carry", "dribble") and self.end_location is None:
            raise ValueError("A movement event requires an end_location")
        if (self.type == "shot") != (self.xg is not None):
            raise ValueError("Exactly shot events require a synthetic xG estimate")
        if self.type == "goal" and self.linked_event_id is None:
            raise ValueError("A goal must reference its shot event")
        if self.type != "goal" and self.linked_event_id is not None:
            raise ValueError("Only goals use linked_event_id in schema 1.0")
        if self.type == "substitution":
            if self.related_player_id is None or self.related_player_id == self.player_id:
                raise ValueError("A substitution requires a distinct incoming player")
        elif self.related_player_id is not None:
            raise ValueError("Only substitutions use related_player_id in schema 1.0")
        return self


class MatchWindow(Contract):
    """A nonempty half-open [from_ms, to_ms) window within one match period."""

    period: Period
    from_ms: Annotated[int, Field(ge=0)]
    to_ms: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        """Reject reversed windows and cross-period ambiguity before querying metrics."""
        if self.to_ms <= self.from_ms:
            raise ValueError("A window must end after it starts")
        if self.period == 2 and self.from_ms < 2_700_000:
            raise ValueError("A second-half window cannot start before 45:00")
        return self


class Subject(Contract):
    """A team, player, or team-qualified player referenced by an assertion."""

    team_id: Identifier | None = None
    player_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_subject(self) -> Self:
        """Require an explicit subject rather than guessing from the current score."""
        if self.team_id is None and self.player_id is None:
            raise ValueError("At least one subject identifier is required")
        return self


class MetricAssertion(Contract):
    """A requested metric comparison; truth is established by a registered query."""

    metric: MetricIdentifier
    subject: Subject
    window: MatchWindow
    comparator: Literal["eq", "gte", "lte"] = "eq"
    value: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    unit: Literal["count", "ratio", "synthetic_xg", "metres", "per_minute"]

    @model_validator(mode="after")
    def validate_units(self) -> Self:
        """Prevent fractional counts and ratios outside the unit interval."""
        if self.unit == "count" and not self.value.is_integer():
            raise ValueError("Count assertions must be integers")
        if self.unit == "ratio" and self.value > 1:
            raise ValueError("Ratios must lie between zero and one")
        return self


class Claim(Contract):
    """A narrative assertion with evidence references, not a verification certificate."""

    claim_id: Identifier
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    kind: Literal["measured_stat", "event_fact", "tactical_inference"]
    assertion: MetricAssertion | None = None
    evidence_event_ids: Annotated[
        tuple[Identifier, ...],
        Field(min_length=1, max_length=4096),
        BeforeValidator(immutable_array),
    ]

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        """Make missing measurement semantics and duplicate evidence explicit errors."""
        if not self.text.strip():
            raise ValueError("Claim text cannot be blank")
        if (self.kind == "measured_stat") != (self.assertion is not None):
            raise ValueError("Exactly measured claims require a metric assertion")
        if len(set(self.evidence_event_ids)) != len(self.evidence_event_ids):
            raise ValueError("Evidence references must be unique")
        return self


class EvidenceRecord(Contract):
    """Versioned query provenance scoped to a single match and replay generation."""

    evidence_id: Identifier
    match_id: Identifier
    replay_id: Identifier
    revision: Annotated[int, Field(ge=1)]
    window: MatchWindow
    event_ids: Annotated[
        tuple[Identifier, ...],
        Field(min_length=1, max_length=4096),
        BeforeValidator(immutable_array),
    ]
    engine_version: Identifier
    source_digest: Digest

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        """Reject duplicate references instead of inflating apparent evidence coverage."""
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError("Evidence references must be unique")
        return self


class VerificationResult(Contract):
    """A checker result with explicit status; this is not permission to publish.

    A future numerical checker must supply expected and observed values. This
    contract also accommodates event checks with an auditable registered query ID.
    """

    claim_id: Identifier
    status: Literal["verified", "supported_inference", "needs_revision", "blocked", "fallback"]
    query_id: Identifier
    reason: Annotated[str, Field(min_length=1, max_length=1000)]
    expected: FiniteNumber | None = None
    observed: FiniteNumber | None = None
    evidence_digest: Digest


class ApprovalBinding(Contract):
    """Exact artefacts that a future producer approval must bind transactionally.

    Hashing this record is not a signature. The service must establish the actor,
    preserve a server-side approval and compare all bindings at publication.
    """

    item_id: Identifier
    item_version: Annotated[int, Field(ge=1)]
    replay_id: Identifier
    content_digest: Digest
    evidence_digest: Digest
    language: Literal["en", "es", "fr"]
    persona: Literal["analyst", "casual_fan", "broadcast_caption"]
