"""A timed, machine-readable overlay feed for broadcast and streaming graphics.

Each cue is something a renderer can put on screen at a match time: a goal lower-third, a
card or substitution strap, a stats card at fixed intervals, a spell of control, or a player
spotlight. Every number in a cue comes from a structured claim that the verifier has checked
against the event log; the cue's text is composed from those verified values in three
languages and three personas, so the words on screen cannot drift from the figures. Cards and
substitutions have no registered event-fact query yet, so they carry the logged event and the
status ``logged`` instead of ``verified``.

The feed is deterministic. Nothing here publishes anything: a producer still decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_claims import DISPLAY_NAMES, REPLAY_END_MS, evidence_record
from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import (
    Claim,
    EventFact,
    MatchEvent,
    MatchWindow,
    MetricAssertion,
    Subject,
    round_half_up,
)
from matchdesk.domain.verification import verify_claim

OVERLAY_SCHEMA = "matchdesk-overlay-feed/1"
PERSONAS = ("analyst", "fan", "caption")
LANGUAGES = ("en", "es", "fr")
STAT_CARD_MS = (900_000, 1_800_000, 2_700_000, 3_600_000)
CUE_MS = 8_000
SPELL = (1_800_000, 2_700_000)
SPOTLIGHT_MS = 3_600_000
_TEAM = {canonical.HOME: "NBR", canonical.AWAY: "RIV"}


def _clock(ms: int) -> str:
    """mm:ss for a match clock."""
    seconds = ms // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _minute(ms: int) -> int:
    """The minute a viewer would say: 58:17 is the 59th minute, written 59′."""
    return ms // 60_000 + 1


@dataclass
class _Builder:
    """Collects claims, verifies them once each, and numbers the cues."""

    log: tuple[MatchEvent, ...]

    def __post_init__(self) -> None:
        """Bind the evidence record once."""
        self.evidence = evidence_record(self.log)
        self.claims: dict[str, dict[str, Any]] = {}
        self.cues: list[dict[str, Any]] = []

    def check(self, claim: Claim) -> dict[str, Any]:
        """Verify one claim with the reader-facing rules and keep the verdict."""
        result = verify_claim(claim, self.evidence, self.log, names=DISPLAY_NAMES)
        record = {
            "claim_id": claim.claim_id,
            "text": claim.text,
            "status": result.status,
            "query_id": result.query_id,
            "reason": result.reason,
            "evidence_event_ids": list(claim.evidence_event_ids),
            "observed": result.observed,
            "claim": claim.model_dump(mode="json", exclude_none=True),
        }
        self.claims[claim.claim_id] = record
        return record

    def metric(
        self,
        claim_id: str,
        metric: str,
        subject: Subject,
        window: MatchWindow,
        text: str,
        unit: str = "count",
        decimals: int | None = None,
        cites: tuple[str, ...] = ("E-0001",),
    ) -> tuple[float, dict[str, Any]]:
        """Compute a metric, state it at its precision, and verify the sentence."""
        raw = compute_metric(metric, self.log, subject, window)
        value = raw if decimals is None else float(round_half_up(raw, decimals))
        if unit == "count":
            cited = tuple(
                event.event_id
                for event in self.log
                if event.type == {"goals.v1": "goal", "shots.v1": "shot"}.get(metric, "")
                and (window.period is None or event.period == window.period)
                and window.from_ms <= event.match_clock_ms < window.to_ms
                and (subject.team_id is None or event.team_id == subject.team_id)
                and (subject.player_id is None or event.player_id == subject.player_id)
            )
            if not cited:
                # A zero cites the window it read: its first event.
                cited = tuple(
                    event.event_id
                    for event in self.log
                    if (window.period is None or event.period == window.period)
                    and window.from_ms <= event.match_clock_ms < window.to_ms
                )[:1]
            cites = cited or cites
        claim = Claim(
            claim_id=claim_id,
            text=text.format(v=_shown(value, unit, decimals), s="" if value == 1 else "s"),
            kind="measured_stat",
            assertion=MetricAssertion(
                metric=metric,
                subject=subject,
                window=window,
                value=value,
                unit=unit,  # type: ignore[arg-type]
                decimals=decimals,
            ),
            evidence_event_ids=cites,
        )
        return value, self.check(claim)

    def cue(
        self,
        t_ms: int,
        kind: str,
        texts: Mapping[str, Mapping[str, str]],
        claims: list[dict[str, Any]],
        team: str | None = None,
        players: tuple[str, ...] = (),
        events: tuple[str, ...] = (),
    ) -> None:
        """Add one cue; its status is verified only if every claim behind it verified."""
        statuses = {claim["status"] for claim in claims}
        status = "logged" if not claims else "verified" if statuses == {"verified"} else "failed"
        self.cues.append(
            {
                "cue_id": f"Q-{len(self.cues) + 1:03d}",
                "t_ms": t_ms,
                "clock": _clock(t_ms),
                "duration_ms": CUE_MS,
                "kind": kind,
                "team": team,
                "players": list(players),
                "event_ids": list(events),
                "status": status,
                "claim_ids": [claim["claim_id"] for claim in claims],
                "text": {persona: dict(texts[persona]) for persona in PERSONAS},
            }
        )


def _shown(value: float, unit: str, decimals: int | None) -> str:
    """How a verified value appears in a sentence: whole counts, percentages, one-place measures."""
    if unit == "ratio":
        return str(round_half_up(value * 100, max((decimals or 2) - 2, 0)))
    if unit == "count":
        return str(int(value))
    return str(round_half_up(value, decimals if decimals is not None else 1))


def _name(identity: str) -> str:
    """Display name for a team or player."""
    return DISPLAY_NAMES.get(identity, identity)


def _goal_cues(builder: _Builder) -> None:
    """A lower-third for every goal, with the scorer and the score it makes, both verified."""
    goals = [event for event in builder.log if event.type == "goal"]
    for event in goals:
        assert event.player_id is not None and event.team_id is not None
        scorer = _name(event.player_id)
        team = _name(event.team_id)
        fact = builder.check(
            Claim(
                claim_id=f"OV-{event.event_id}-SCORER",
                text=f"{scorer} scored for {team} at {_clock(event.match_clock_ms)}.",
                kind="event_fact",
                fact=EventFact(
                    query="goal_scorer.v1", event_id=event.event_id, player_id=event.player_id
                ),
                evidence_event_ids=(event.event_id,),
            )
        )
        # The score once the goal is in: everything up to the next whole second.
        after = MatchWindow(from_ms=0, to_ms=event.match_clock_ms + 1000)
        clock = _clock(event.match_clock_ms + 1000)
        score: dict[str, int] = {}
        lines = [fact]
        for side in (canonical.HOME, canonical.AWAY):
            value, line = builder.metric(
                f"OV-{event.event_id}-{_TEAM[side]}",
                "goals.v1",
                Subject(team_id=side),
                after,
                f"{_name(side)} scored {{v}} goal{{s}} up to {clock}.",
            )
            score[side] = int(value)
            lines.append(line)
        home, away = score[canonical.HOME], score[canonical.AWAY]
        minute = _minute(event.match_clock_ms)
        texts = {
            "analyst": {
                "en": f"GOAL {_clock(event.match_clock_ms)} · {scorer} ({team}) · Northbridge {home}–{away} Riverside",
                "es": f"GOL {_clock(event.match_clock_ms)} · {scorer} ({team}) · Northbridge {home}–{away} Riverside",
                "fr": f"BUT {_clock(event.match_clock_ms)} · {scorer} ({team}) · Northbridge {home}–{away} Riverside",
            },
            "fan": {
                "en": f"GOAL! {scorer} scores for {team}. It's {home}–{away}.",
                "es": f"¡GOL! {scorer} marca para el {team}. {home}–{away}.",
                "fr": f"BUT ! {scorer} marque pour {team}. {home}–{away}.",
            },
            "caption": {
                "en": f"{minute}′ GOAL · {scorer} · NBR {home}–{away} RIV",
                "es": f"{minute}′ GOL · {scorer} · NBR {home}–{away} RIV",
                "fr": f"{minute}′ BUT · {scorer} · NBR {home}–{away} RIV",
            },
        }
        builder.cue(
            event.match_clock_ms,
            "goal",
            texts,
            lines,
            team=event.team_id,
            players=(event.player_id,),
            events=(event.event_id,),
        )


def _logged_cues(builder: _Builder) -> None:
    """Cards and substitutions: logged events, shown as such until a query can check them."""
    for event in builder.log:
        if event.match_clock_ms >= REPLAY_END_MS or event.team_id is None:
            continue
        team = _name(event.team_id)
        minute = _minute(event.match_clock_ms)
        if event.type == "card" and event.player_id:
            player = _name(event.player_id)
            colour = {"en": "Yellow card", "es": "Tarjeta amarilla", "fr": "Carton jaune"}
            if event.outcome in ("red", "second_yellow"):
                colour = {"en": "Red card", "es": "Tarjeta roja", "fr": "Carton rouge"}
            texts = {
                "analyst": {
                    lang: f"{colour[lang]} {_clock(event.match_clock_ms)} · {player} ({team})"
                    for lang in LANGUAGES
                },
                "fan": {lang: f"{colour[lang]}: {player} ({team})" for lang in LANGUAGES},
                "caption": {
                    lang: f"{minute}′ {colour[lang].upper()} · {player}" for lang in LANGUAGES
                },
            }
            builder.cue(
                event.match_clock_ms,
                "card",
                texts,
                [],
                team=event.team_id,
                players=(event.player_id,),
                events=(event.event_id,),
            )
        if event.type == "substitution" and event.player_id and event.related_player_id:
            off, on = _name(event.player_id), _name(event.related_player_id)
            word = {"en": "Substitution", "es": "Cambio", "fr": "Remplacement"}
            arrows = f"{on} ↑ {off} ↓"
            texts = {
                "analyst": {
                    lang: f"{word[lang]} {_clock(event.match_clock_ms)} · {team} · {arrows}"
                    for lang in LANGUAGES
                },
                "fan": {lang: f"{word[lang]} · {team}: {arrows}" for lang in LANGUAGES},
                "caption": {
                    lang: f"{minute}′ {word[lang].upper()} · {arrows}" for lang in LANGUAGES
                },
            }
            builder.cue(
                event.match_clock_ms,
                "substitution",
                texts,
                [],
                team=event.team_id,
                players=(event.player_id, event.related_player_id),
                events=(event.event_id,),
            )


def _stat_cards(builder: _Builder) -> None:
    """Possession and shots from kick-off, every 15 minutes and at the replay point."""
    for t_ms in (*STAT_CARD_MS, REPLAY_END_MS):
        window = MatchWindow(from_ms=0, to_ms=t_ms)
        clock = _clock(t_ms)
        share, possession = builder.metric(
            f"OV-STATS-{t_ms // 60_000:02d}-POSS",
            "possession_time.v1",
            Subject(team_id=canonical.HOME),
            window,
            f"Northbridge have had {{v}}% possession up to {clock}.",
            unit="ratio",
            decimals=2,
        )
        shots: dict[str, int] = {}
        lines = [possession]
        for side in (canonical.HOME, canonical.AWAY):
            value, line = builder.metric(
                f"OV-STATS-{t_ms // 60_000:02d}-SHOTS-{_TEAM[side]}",
                "shots.v1",
                Subject(team_id=side),
                window,
                f"{_name(side)} had {{v}} shot{{s}} up to {clock}.",
            )
            shots[side] = int(value)
            lines.append(line)
        home = int(round_half_up(share * 100, 0))
        away = 100 - home
        nbr, riv = shots[canonical.HOME], shots[canonical.AWAY]
        minute = t_ms // 60_000
        texts = {
            "analyst": {
                "en": f"{minute}′ · Possession NBR {home}% · RIV {away}% · Shots {nbr}–{riv}",
                "es": f"{minute}′ · Posesión NBR {home} % · RIV {away} % · Tiros {nbr}–{riv}",
                "fr": f"{minute}′ · Possession NBR {home} % · RIV {away} % · Tirs {nbr}–{riv}",
            },
            "fan": {
                "en": f"After {minute} minutes: Northbridge {home}% of the ball, shots {nbr}–{riv}",
                "es": f"Tras {minute} minutos: Northbridge {home} % del balón, tiros {nbr}–{riv}",
                "fr": f"Après {minute} minutes : Northbridge {home} % du ballon, tirs {nbr}–{riv}",
            },
            "caption": {
                "en": f"POSS {home}–{away} · SHOTS {nbr}–{riv}",
                "es": f"POSESIÓN {home}–{away} · TIROS {nbr}–{riv}",
                "fr": f"POSSESSION {home}–{away} · TIRS {nbr}–{riv}",
            },
        }
        builder.cue(t_ms, "stats", texts, lines)


def _spell_cue(builder: _Builder) -> None:
    """Riverside's best spell: their share of the ball between 30′ and 45′."""
    start, end = SPELL
    share, line = builder.metric(
        "OV-SPELL-RIV",
        "possession_time.v1",
        Subject(team_id=canonical.AWAY),
        MatchWindow(from_ms=start, to_ms=end),
        "Riverside had {v}% possession between 30′ and 45′.",
        unit="ratio",
        decimals=2,
    )
    pct = int(round_half_up(share * 100, 0))
    texts = {
        "analyst": {
            "en": f"Control shift · Riverside {pct}% possession, 30′–45′",
            "es": f"Cambio de control · Riverside {pct} % de posesión, 30′–45′",
            "fr": f"Bascule · Riverside {pct} % de possession, 30′–45′",
        },
        "fan": {
            "en": f"Riverside had {pct}% of the ball from 30′ to 45′",
            "es": f"Riverside tuvo el {pct} % del balón del 30′ al 45′",
            "fr": f"Riverside a eu {pct} % du ballon de la 30e à la 45e",
        },
        "caption": {
            "en": f"RIV {pct}% POSS · 30′–45′",
            "es": f"RIV {pct} % POSESIÓN · 30′–45′",
            "fr": f"RIV {pct} % POSSESSION · 30′–45′",
        },
    }
    builder.cue(end, "spell", texts, [line], team=canonical.AWAY)


def _spotlight_cue(builder: _Builder) -> None:
    """The tackles leader at the hour, ranked from every player's recomputed count."""
    window = MatchWindow(from_ms=0, to_ms=SPOTLIGHT_MS)
    players = sorted({event.player_id for event in builder.log if event.player_id})
    ranked = sorted(
        players,
        key=lambda player: (
            -compute_metric("tackles.v1", builder.log, Subject(player_id=player), window),
            _name(player),
        ),
    )
    leader = ranked[0]
    value, line = builder.metric(
        "OV-SPOT-TACKLES",
        "tackles.v1",
        Subject(player_id=leader),
        window,
        f"{_name(leader)} made {{v}} tackle{{s}} up to 60:00.",
    )
    count = int(value)
    team_id = next(event.team_id for event in builder.log if event.player_id == leader)
    texts = {
        "analyst": {
            "en": f"Tackles leader at 60′ · {_name(leader)} ({_name(team_id or '')}) · {count}",
            "es": f"Líder en entradas al 60′ · {_name(leader)} ({_name(team_id or '')}) · {count}",
            "fr": f"Meilleur tacleur à la 60e · {_name(leader)} ({_name(team_id or '')}) · {count}",
        },
        "fan": {
            "en": f"{_name(leader)} has made {count} tackles, the most on the pitch",
            "es": f"{_name(leader)} lleva {count} entradas, más que nadie",
            "fr": f"{_name(leader)} compte {count} tacles, le plus haut total du match",
        },
        "caption": {
            "en": f"TACKLES · {_name(leader)} {count}",
            "es": f"ENTRADAS · {_name(leader)} {count}",
            "fr": f"TACLES · {_name(leader)} {count}",
        },
    }
    builder.cue(SPOTLIGHT_MS, "spotlight", texts, [line], team=team_id, players=(leader,))


def build_overlay_feed(log: tuple[MatchEvent, ...] | None = None) -> dict[str, Any]:
    """Every cue to the replay point, in time order, with the claims behind it."""
    events = log if log is not None else canonical.generate_canonical_match()
    builder = _Builder(events)
    _goal_cues(builder)
    _logged_cues(builder)
    _stat_cards(builder)
    _spell_cue(builder)
    _spotlight_cue(builder)
    ordered = sorted(builder.cues, key=lambda cue: (cue["t_ms"], cue["cue_id"]))
    for number, cue in enumerate(ordered, start=1):
        cue["cue_id"] = f"Q-{number:03d}"
    return {
        "schema": OVERLAY_SCHEMA,
        "match_id": canonical.MATCH_ID,
        "synthetic": True,
        "replay_end_ms": REPLAY_END_MS,
        "personas": list(PERSONAS),
        "languages": list(LANGUAGES),
        "teams": {side: _name(side) for side in (canonical.HOME, canonical.AWAY)},
        "note": (
            "Timed cues for on-screen graphics. Numbers come only from claims the verifier "
            "checked against the event log; cards and substitutions are logged events with no "
            "registered query yet. Spanish and French are AI-assisted templates awaiting native "
            "review. Nothing here is published: a producer decides."
        ),
        "cues": ordered,
        "claims": [builder.claims[key] for key in sorted(builder.claims)],
    }
