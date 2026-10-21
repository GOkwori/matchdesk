"""A deterministic stand-in for the model, so the whole workflow runs in CI without spend.

The rehearsal is not a script of answers: each role reads the match through the same
traced, role-scoped tools a live model gets, builds real claims from what the tools
return, and hands them on through the same structured handoff. Two things are staged
on purpose and say so in their output: the composer's first draft misstates
possession by two points, and it includes a season-history sentence, so the
verification loop and the editorial review have something real to catch. Nothing here
is presented as model output; the trace labels the provider "rehearsal".
"""

from __future__ import annotations

import json
from typing import Any

from matchdesk.domain.agent_workflow import (
    ProviderKind,
    TracedReadTools,
    TurnTelemetry,
    parse_handoff,
)
from matchdesk.domain.models import Claim, EventFact, MatchWindow, MetricAssertion, Subject
from matchdesk.domain.specialists import SpecialistRequest, SpecialistResponse

_INJECTED_ERROR = 0.02
_SPELL_BLOCKS = ((0.0, 15.0), (15.0, 30.0), (30.0, 45.0), (45.0, 60.0), (60.0, 67.2))


def _seconds(clock: str) -> int:
    """Seconds from an mm:ss display clock."""
    minutes, seconds = clock.split(":")
    return int(minutes) * 60 + int(seconds)


def _whole(to_minute: float) -> MatchWindow:
    """The whole match up to a minute, across both halves."""
    return MatchWindow(from_ms=0, to_ms=round(to_minute * 60_000))


class RehearsalExecutor:
    """Deterministic provider for every specialist role; makes no model calls."""

    kind: ProviderKind = "rehearsal"
    label: str = "Rehearsal: deterministic stand-in for the model, no AI"

    async def execute(
        self, request: SpecialistRequest, tools: TracedReadTools, *, digest: str
    ) -> tuple[SpecialistResponse, TurnTelemetry]:
        """Dispatch to the role's rehearsal behaviour."""
        handoff = parse_handoff(request.instruction)
        facts = json.loads(digest)
        role = request.role
        if role == "tactical_analyst":
            response = self._tactical(tools, facts, handoff)
        elif role == "narrative_composer":
            response = self._composer(tools, facts, handoff)
        elif role == "editorial_reviewer":
            response = self._reviewer(handoff)
        else:
            response = self._adapter(tools, facts, handoff)
        return response, TurnTelemetry()

    def _tactical(
        self, tools: TracedReadTools, facts: dict[str, Any], handoff: dict[str, Any]
    ) -> SpecialistResponse:
        """Find the away side's best spell, the possession share and the goal sequence."""
        focus = handoff["focus"]
        home, away = focus["team_id"], focus["opponent_id"]
        end = _seconds(facts["replay_clock"]) / 60
        shares = [
            tools.metric("possession_time.v1", away, from_minute=a, to_minute=b)
            for a, b in _SPELL_BLOCKS
        ]
        best_from, best_to = _SPELL_BLOCKS[shares.index(max(shares))]
        spell_events = tools.events_in_window(best_from, best_to, types=["goal", "shot"])
        cited_spell = tuple(row["event_id"] for row in spell_events if row["team_id"] == away)
        share = tools.metric("possession_time.v1", home, from_minute=0, to_minute=end)
        first = tools.events_in_window(0, 1)[0]["event_id"]
        goal = tools.event_by_id(focus["event_id"])
        assert goal is not None
        goal_s = _seconds(goal["clock"])
        around = tools.events_in_window(goal_s / 60 - 0.5, goal_s / 60 + 0.05)
        corner = next(row for row in reversed(around) if "corner" in row.get("tags", []))
        gap = goal_s - _seconds(corner["clock"])
        names = facts["teams"]
        pct = round(share * 100)
        claims = (
            Claim(
                claim_id="TA-01",
                text=f"{names[away]}'s best spell came between {best_from:g} and {best_to:g} minutes.",
                kind="tactical_inference",
                evidence_event_ids=cited_spell or (first,),
            ),
            Claim(
                claim_id="TA-02",
                text=f"{names[home]} have had {pct}% possession.",
                kind="measured_stat",
                assertion=MetricAssertion(
                    metric="possession_time.v1",
                    subject=Subject(team_id=home),
                    window=_whole(end),
                    value=round(share, 2),
                    unit="ratio",
                    decimals=2,
                ),
                evidence_event_ids=(first,),
            ),
            Claim(
                claim_id="TA-03",
                text=f"The goal came {gap} seconds after a corner.",
                kind="event_fact",
                fact=EventFact(
                    query="sequence_gap.v1",
                    event_id=goal["event_id"],
                    from_event_id=corner["event_id"],
                    from_tag="corner",
                    gap_seconds=gap,
                ),
                evidence_event_ids=(corner["event_id"], goal["event_id"]),
            ),
        )
        return SpecialistResponse(
            role="tactical_analyst",
            proposed_claims=claims,
            content=f"{names[away]} held {max(shares):.0%} of possession from "
            f"{best_from:g} to {best_to:g} minutes, their highest share of any block.",
        )

    def _composer(
        self, tools: TracedReadTools, facts: dict[str, Any], handoff: dict[str, Any]
    ) -> SpecialistResponse:
        """Draft the story; on revision, recompute each failed number with the tools."""
        if handoff.get("verifier_feedback"):
            return self._revise(tools, handoff)
        focus = handoff["focus"]
        home = focus["team_id"]
        names = facts["teams"]
        tactical = {c["claim_id"]: Claim.model_validate(c) for c in handoff["tactical_claims"]}
        end = _seconds(facts["replay_clock"]) / 60
        scorer = focus["player_id"]
        scorer_name = next(
            row["player"] for row in facts["key_events"] if row["event_id"] == focus["event_id"]
        )
        goals = tools.metric("goals.v1", home, player_id=scorer, to_minute=end)
        goal_ids = tuple(
            row["event_id"]
            for row in facts["key_events"]
            if row["type"] == "goal" and row.get("player_id") == scorer
        )
        possession = tactical["TA-02"]
        assert possession.assertion is not None
        staged = round(possession.assertion.value + _INJECTED_ERROR, 2)
        sequence = tactical["TA-03"]
        assert sequence.fact is not None
        claims = (
            Claim(
                claim_id="NC-01",
                text=f"{scorer_name} scored both {names[home]} goals."
                if goals == 2
                else f"{scorer_name} scored {goals:g} {names[home]} goals.",
                kind="measured_stat",
                assertion=MetricAssertion(
                    metric="goals.v1",
                    subject=Subject(team_id=home, player_id=scorer),
                    window=_whole(end),
                    value=goals,
                    unit="count",
                ),
                evidence_event_ids=goal_ids,
            ),
            possession.model_copy(
                update={
                    "claim_id": "NC-02",
                    "text": f"{names[home]} have had {round(staged * 100)}% possession.",
                    "assertion": possession.assertion.model_copy(update={"value": staged}),
                }
            ),
            sequence.model_copy(
                update={
                    "claim_id": "NC-03",
                    "text": f"{scorer_name}'s header came {sequence.fact.gap_seconds} seconds "
                    "after a corner.",
                }
            ),
            Claim(
                claim_id="NC-04",
                text=f"It is {scorer_name}'s first brace of the season.",
                kind="event_fact",
                evidence_event_ids=goal_ids,
            ),
            tactical["TA-01"].model_copy(update={"claim_id": "NC-05"}),
        )
        return SpecialistResponse(
            role="narrative_composer",
            proposed_claims=claims,
            content=f"Headline: {scorer_name} double restores {names[home]} lead\n"
            "[rehearsal] NC-02 misstates possession by two points and NC-04 needs "
            "season data, on purpose, so review and verification have something to catch.",
        )

    def _revise(self, tools: TracedReadTools, handoff: dict[str, Any]) -> SpecialistResponse:
        """Rewrite each failed measured claim from a fresh metric read; keep the rest."""
        failed = {row["claim_id"] for row in handoff["verifier_feedback"]}
        revised = []
        for raw in handoff["previous_claims"]:
            claim = Claim.model_validate(raw)
            if claim.claim_id in failed and claim.assertion is not None:
                assertion = claim.assertion
                window = assertion.window
                observed = tools.metric(
                    assertion.metric,
                    assertion.subject.team_id or "",
                    player_id=assertion.subject.player_id,
                    from_minute=window.from_ms / 60_000,
                    to_minute=window.to_ms / 60_000,
                )
                value = round(observed, assertion.decimals or 0)
                old = round(assertion.value * 100)
                claim = claim.model_copy(
                    update={
                        "text": claim.text.replace(f"{old}%", f"{round(value * 100)}%"),
                        "assertion": assertion.model_copy(update={"value": value}),
                    }
                )
            elif claim.claim_id in failed:
                continue
            revised.append(claim)
        return SpecialistResponse(
            role="narrative_composer",
            proposed_claims=tuple(revised),
            content="Revised after verification: recomputed every failed number from the log.",
        )

    def _reviewer(self, handoff: dict[str, Any]) -> SpecialistResponse:
        """Drop event facts no registered query can check; keep everything else."""
        kept, dropped = [], []
        for raw in handoff["draft_claims"]:
            claim = Claim.model_validate(raw)
            if claim.kind == "event_fact" and claim.fact is None:
                dropped.append(claim.claim_id)
            else:
                kept.append(claim)
        note = (
            f"Dropped {', '.join(dropped)}: the match log holds no season history to check it."
            if dropped
            else "No claim needs data outside the match log."
        )
        return SpecialistResponse(
            role="editorial_reviewer", proposed_claims=tuple(kept), content=note
        )

    def _adapter(
        self, tools: TracedReadTools, facts: dict[str, Any], handoff: dict[str, Any]
    ) -> SpecialistResponse:
        """Nine templated variants of the verified goal and sequence claims.

        The adapter cannot read events; it confirms each claim's verdict through the one
        tool its scope allows before adapting it.
        """
        claims = [
            Claim.model_validate(raw)
            for raw in handoff["verified_claims"]
            if (tools.verification_result(raw["claim_id"]) or {}).get("status") == "verified"
        ]
        goals = next(c for c in claims if c.assertion and c.assertion.metric == "goals.v1")
        sequence = next(c for c in claims if c.fact and c.fact.query == "sequence_gap.v1")
        assert goals.assertion is not None and sequence.fact is not None
        team = facts["teams"][goals.assertion.subject.team_id or ""]
        name = next(
            row["player"]
            for row in facts["key_events"]
            if row.get("player_id") == goals.assertion.subject.player_id and "player" in row
        )
        gap = sequence.fact.gap_seconds
        count = int(goals.assertion.value)
        both = {"en": "both", "es": "los dos", "fr": "les deux"}
        n = {lang: both[lang] if count == 2 else str(count) for lang in both}
        texts = {
            (
                "en",
                "analyst",
            ): f"{name} has scored {n['en']} {team} goals; his header came {gap} seconds after a corner.",
            (
                "en",
                "casual_fan",
            ): f"{name} again! A header {gap} seconds after a corner puts {team} back in front.",
            ("en", "broadcast_caption"): f"{name} · header {gap}s after a corner",
            (
                "es",
                "analyst",
            ): f"{name} ha marcado {n['es']} goles del {team}; su cabezazo llegó {gap} segundos después de un córner.",
            (
                "es",
                "casual_fan",
            ): f"¡{name} otra vez! Un cabezazo {gap} segundos después de un córner devuelve la ventaja al {team}.",
            ("es", "broadcast_caption"): f"{name} · cabezazo {gap} s tras córner",
            (
                "fr",
                "analyst",
            ): f"{name} a marqué {n['fr']} buts de {team} ; sa tête est arrivée {gap} secondes après un corner.",
            (
                "fr",
                "casual_fan",
            ): f"Encore {name} ! Une tête {gap} secondes après un corner, et {team} repasse devant.",
            ("fr", "broadcast_caption"): f"{name} · tête {gap} s après corner",
        }
        rows = [
            {
                "language": lang,
                "persona": persona,
                "text": text,
                "claim_ids": [goals.claim_id, sequence.claim_id],
            }
            for (lang, persona), text in texts.items()
        ]
        return SpecialistResponse(
            role="audience_adapter", content=json.dumps(rows, ensure_ascii=False)
        )
