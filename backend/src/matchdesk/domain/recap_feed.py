"""Automated match recaps, written only from verified claims.

Two recaps are built from the event log: one at half-time, over the first half, and one at
the replay point, over the match so far. Each states the score, who scored and when, the share
of the ball, shots, passing, synthetic expected goals and the tackles leader, plus the
match's milestones (the opening goal, an equaliser, a brace, each side's 5th, 10th and 15th
shot). Every figure is a structured claim the verifier checks against the log; the headline
and body in each persona and language are composed from the verified values, so the words
cannot claim more than the checks.

The feed is deterministic. Nothing here publishes anything: a producer still decides.
"""

from __future__ import annotations

from typing import Any

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_claims import DISPLAY_NAMES, REPLAY_END_MS
from matchdesk.domain.metrics import compute_metric
from matchdesk.domain.models import (
    Claim,
    EventFact,
    MatchEvent,
    MatchWindow,
    Subject,
    round_half_up,
)
from matchdesk.domain.overlay_feed import LANGUAGES, PERSONAS, _Builder, _clock, _minute
from matchdesk.domain.story_feed import _context, build_story_feed

RECAP_SCHEMA = "matchdesk-recap-feed/1"
# The first half's window: every first-half event, up to the second after the half-time whistle.
HALF_TIME_END_MS = canonical.SECOND_HALF_MS + 1000
SHOT_MILESTONES = (5, 10, 15)
_SIDES = (canonical.HOME, canonical.AWAY)
_TEAM = {canonical.HOME: "NBR", canonical.AWAY: "RIV"}


def _name(identity: str) -> str:
    """Display name for a team or player."""
    return DISPLAY_NAMES.get(identity, identity)


def _other(side: str) -> str:
    """The opposing side."""
    return next(other for other in _SIDES if other != side)


def _upto(ms: int) -> tuple[MatchWindow, str]:
    """Kick-off to the next whole second after an event, and that clock as stated."""
    end = (ms // 1000 + 1) * 1000
    return MatchWindow(from_ms=0, to_ms=end), _clock(end)


_MOMENT = {
    "opener": {"en": "Opening goal", "es": "Primer gol", "fr": "Premier but"},
    "equaliser": {"en": "Equaliser", "es": "Empate", "fr": "Égalisation"},
    "lead_restored": {
        "en": "Lead restored",
        "es": "Vuelve a ponerse por delante",
        "fr": "Avantage repris",
    },
    "lead_taken": {"en": "Goes in front", "es": "Se pone por delante", "fr": "Passe devant"},
    "pulls_back": {"en": "One pulled back", "es": "Recorta distancias", "fr": "Réduit l'écart"},
    "extends": {"en": "Lead extended", "es": "Amplía la ventaja", "fr": "Écart creusé"},
}


def _milestones(builder: _Builder, end_ms: int) -> list[dict[str, Any]]:
    """Every goal by what it did to the score, braces, and each side's 5th, 10th and 15th shot."""
    log = builder.log
    out: list[dict[str, Any]] = []
    score = {side: 0 for side in _SIDES}
    led = {side: False for side in _SIDES}
    tally: dict[str, int] = {}
    for goal in (e for e in log if e.type == "goal" and e.match_clock_ms < end_ms):
        assert goal.team_id is not None and goal.player_id is not None
        team, scorer = goal.team_id, goal.player_id
        before = dict(score)
        score[team] += 1
        context = _context(team, before, score, led[team])
        for side in _SIDES:
            led[side] = led[side] or score[side] > score[_other(side)]
        fact = builder.check(
            Claim(
                claim_id=f"RC-{goal.event_id}-SCORER",
                text=f"{_name(scorer)} scored for {_name(team)} at {_clock(goal.match_clock_ms)}.",
                kind="event_fact",
                fact=EventFact(query="goal_scorer.v1", event_id=goal.event_id, player_id=scorer),
                evidence_event_ids=(goal.event_id,),
            )
        )
        out.append(
            {
                "t_ms": goal.match_clock_ms,
                "kind": "goal",
                "team": team,
                "event_id": goal.event_id,
                "label": {
                    lang: f"{_MOMENT[context][lang]} · {_name(scorer)}" for lang in LANGUAGES
                },
                "claim_ids": [fact["claim_id"]],
            }
        )
        tally[scorer] = tally.get(scorer, 0) + 1
        if tally[scorer] == 2:
            window, stated = _upto(goal.match_clock_ms)
            _, brace = builder.metric(
                f"RC-{goal.event_id}-BRACE",
                "goals.v1",
                Subject(player_id=scorer),
                window,
                f"{_name(scorer)} scored {{v}} goal{{s}} up to {stated}.",
            )
            out.append(
                {
                    "t_ms": goal.match_clock_ms,
                    "kind": "brace",
                    "team": team,
                    "event_id": goal.event_id,
                    "label": {
                        "en": f"{_name(scorer)}'s brace",
                        "es": f"Doblete de {_name(scorer)}",
                        "fr": f"Doublé de {_name(scorer)}",
                    },
                    "claim_ids": [brace["claim_id"]],
                }
            )
    for side in _SIDES:
        shots = [
            e for e in log if e.type == "shot" and e.team_id == side and e.match_clock_ms < end_ms
        ]
        for count in SHOT_MILESTONES:
            if len(shots) < count:
                break
            shot = shots[count - 1]
            window, stated = _upto(shot.match_clock_ms)
            _, line = builder.metric(
                f"RC-{_TEAM[side]}-SHOT-{count:02d}",
                "shots.v1",
                Subject(team_id=side),
                window,
                f"{_name(side)} had {{v}} shot{{s}} up to {stated}.",
            )
            out.append(
                {
                    "t_ms": shot.match_clock_ms,
                    "kind": "shots",
                    "team": side,
                    "event_id": shot.event_id,
                    "label": {
                        "en": f"{_name(side)}'s {count}th shot",
                        "es": f"{count}.º tiro del {_name(side)}",
                        "fr": f"{count}e tir de {_name(side)}",
                    },
                    "claim_ids": [line["claim_id"]],
                }
            )
    out.sort(key=lambda m: (m["t_ms"], m["kind"] != "goal", m["team"]))
    return out


def _recap(
    builder: _Builder, key: str, end_ms: int, half: bool, slugs: dict[str, str]
) -> dict[str, Any]:
    """One recap: verified figures, milestones and text in every persona and language."""
    log = builder.log
    window = (
        MatchWindow(period=1, from_ms=0, to_ms=end_ms)
        if half
        else MatchWindow(from_ms=0, to_ms=end_ms)
    )
    phrase = "in the first half" if half else f"up to {_clock(end_ms)}"
    prefix = f"RC-{key.upper()}"

    def per_team(
        name: str, metric: str, text: str, **kwargs: Any
    ) -> tuple[dict[str, float], list[dict[str, Any]]]:
        """One claim per side for a metric over this recap's window."""
        values: dict[str, float] = {}
        lines = []
        for side in _SIDES:
            value, line = builder.metric(
                f"{prefix}-{name}-{_TEAM[side]}",
                metric,
                Subject(team_id=side),
                window,
                text.format(team=_name(side), phrase=phrase).replace("{{", "{").replace("}}", "}"),
                **kwargs,
            )
            values[side] = value
            lines.append(line)
        return values, lines

    goals, goal_lines = per_team("GOALS", "goals.v1", "{team} scored {{v}} goal{{s}} {phrase}.")
    shots, shot_lines = per_team("SHOTS", "shots.v1", "{team} had {{v}} shot{{s}} {phrase}.")
    passing, pass_lines = per_team(
        "PASS",
        "pass_accuracy.v1",
        "{team} completed {{v}}% of their passes {phrase}.",
        unit="ratio",
        decimals=2,
    )
    xg, xg_lines = per_team(
        "XG",
        "synthetic_xg.v1",
        "{team} had {{v}} expected goals {phrase}.",
        unit="synthetic_xg",
        decimals=1,
    )
    share, possession = builder.metric(
        f"{prefix}-POSS",
        "possession_time.v1",
        Subject(team_id=canonical.HOME),
        window,
        f"Northbridge had {{v}}% possession {phrase}.",
        unit="ratio",
        decimals=2,
    )
    players = sorted({e.player_id for e in log if e.player_id})
    leader = min(
        players,
        key=lambda p: (-compute_metric("tackles.v1", log, Subject(player_id=p), window), _name(p)),
    )
    tackles_value, tackles = builder.metric(
        f"{prefix}-TACKLES",
        "tackles.v1",
        Subject(player_id=leader),
        window,
        f"{_name(leader)} made {{v}} tackle{{s}} {phrase}.",
    )
    leader_team = next(e.team_id for e in log if e.player_id == leader) or ""
    scorers = [
        e
        for e in log
        if e.type == "goal" and e.match_clock_ms < end_ms and (not half or e.period == 1)
    ]
    scorer_lines = [
        builder.check(
            Claim(
                claim_id=f"RC-{goal.event_id}-SCORER",
                text=f"{_name(goal.player_id or '')} scored for {_name(goal.team_id or '')} at {_clock(goal.match_clock_ms)}.",
                kind="event_fact",
                fact=EventFact(
                    query="goal_scorer.v1", event_id=goal.event_id, player_id=goal.player_id
                ),
                evidence_event_ids=(goal.event_id,),
            )
        )
        for goal in scorers
    ]
    milestones = [
        m for m in _milestones(builder, end_ms) if not half or _period(log, m["event_id"]) == 1
    ]

    h, a = int(goals[canonical.HOME]), int(goals[canonical.AWAY])
    sh, sa = int(shots[canonical.HOME]), int(shots[canonical.AWAY])
    ph = int(round_half_up(share * 100, 0))
    pa = 100 - ph
    acc = {side: str(round_half_up(passing[side] * 100, 0)) for side in _SIDES}
    xgs = {side: str(round_half_up(xg[side], 1)) for side in _SIDES}
    tk = int(tackles_value)
    who = _name(leader)
    goals_list = ", ".join(
        f"{_name(g.player_id or '')} {_clock(g.match_clock_ms)}" for g in scorers
    )
    goals_caption = ", ".join(
        f"{_name(g.player_id or '')} {_minute(g.match_clock_ms)}′" for g in scorers
    )
    when = {
        "en": "Half-time" if half else f"At {_clock(end_ms)}",
        "es": "Descanso" if half else f"En el {_clock(end_ms)}",
        "fr": "Mi-temps" if half else f"À {_clock(end_ms)}",
    }
    tag = "HT" if half else _clock(end_ms)
    shown_ms = canonical.SECOND_HALF_MS if half else end_ms
    none = {"en": "no goals yet", "es": "sin goles todavía", "fr": "pas encore de but"}
    text: dict[str, dict[str, dict[str, str]]] = {persona: {} for persona in PERSONAS}
    for lang in LANGUAGES:
        scored = goals_list or none[lang]
        # Spanish and French write decimals with a comma.
        x = {side: xgs[side] if lang == "en" else xgs[side].replace(".", ",") for side in _SIDES}
        fan_body = {
            "en": (
                f"{when['en']}: Northbridge {h}–{a} Riverside. Goals: {scored}. "
                f"Northbridge had {ph}% of the ball and {sh} shots to Riverside's {sa}; "
                f"expected goals {x['nbr']}–{x['riv']}. {who} led the tackles with {tk}."
            ),
            "es": (
                f"{when['es']}: Northbridge {h}–{a} Riverside. Goles: {scored}. "
                f"El Northbridge tuvo el {ph} % del balón y {sh} tiros por {sa} del Riverside; "
                f"goles esperados {x['nbr']}–{x['riv']}. {who} lidera las entradas con {tk}."
            ),
            "fr": (
                f"{when['fr']} : Northbridge {h}–{a} Riverside. Buts : {scored}. "
                f"Northbridge a eu {ph} % du ballon et {sh} tirs contre {sa} pour Riverside ; "
                f"buts attendus {x['nbr']}–{x['riv']}. {who} mène aux tacles avec {tk}."
            ),
        }[lang]
        text["fan"][lang] = {
            "headline": f"{when[lang]} · Northbridge {h}–{a} Riverside",
            "body": fan_body,
        }
        pct = "%" if lang == "en" else "\u00a0%"
        labels = {
            "en": ("Poss", "Shots", "Passing", "xG", "Tackles"),
            "es": ("Posesión", "Tiros", "Pases", "xG", "Entradas"),
            "fr": ("Possession", "Tirs", "Passes", "xG", "Tacles"),
        }[lang]
        text["analyst"][lang] = {
            "headline": f"{tag} · NBR {h}–{a} RIV",
            "body": (
                f"{labels[0]} {ph}–{pa} · {labels[1]} {sh}–{sa} · {labels[2]} {acc['nbr']}{pct}–{acc['riv']}{pct} · "
                f"{labels[3]} {x['nbr']}–{x['riv']} · {labels[4]}: {who} ({_name(leader_team)}) {tk}"
                + (f" · {scored}" if goals_list else "")
            ),
        }
        text["caption"][lang] = {
            "headline": f"{tag} · NBR {h}–{a} RIV",
            "body": goals_caption or none[lang],
        }
    checks = [
        (
            {"en": f"Score, {h}–{a}", "es": f"Marcador, {h}–{a}", "fr": f"Score, {h}–{a}"},
            goal_lines,
        ),
        (
            {
                "en": "Goal scorers and times",
                "es": "Goleadores y minutos",
                "fr": "Buteurs et minutes",
            },
            scorer_lines,
        ),
        (
            {
                "en": f"Possession, {ph}–{pa}",
                "es": f"Posesión, {ph}–{pa}",
                "fr": f"Possession, {ph}–{pa}",
            },
            [possession],
        ),
        (
            {"en": f"Shots, {sh}–{sa}", "es": f"Tiros, {sh}–{sa}", "fr": f"Tirs, {sh}–{sa}"},
            shot_lines,
        ),
        (
            {"en": "Pass completion", "es": "Acierto en el pase", "fr": "Réussite des passes"},
            pass_lines,
        ),
        (
            {
                "en": "Expected goals (synthetic model)",
                "es": "Goles esperados (modelo sintético)",
                "fr": "Buts attendus (modèle synthétique)",
            },
            xg_lines,
        ),
        (
            {
                "en": f"Tackles leader, {who}",
                "es": f"Líder en entradas, {who}",
                "fr": f"Meilleur tacleur, {who}",
            },
            [tackles],
        ),
    ]
    return {
        "id": key,
        "t_ms": shown_ms,
        "clock": _clock(shown_ms),
        "window": window.model_dump(mode="json", exclude_none=True),
        "half": half,
        "title": {
            "en": "Half-time recap" if half else f"Recap at {_clock(end_ms)}",
            "es": "Resumen al descanso" if half else f"Resumen en el {_clock(end_ms)}",
            "fr": "Résumé à la mi-temps" if half else f"Résumé à {_clock(end_ms)}",
        },
        "score": {canonical.HOME: h, canonical.AWAY: a},
        "goals": [
            {
                "event_id": g.event_id,
                "t_ms": g.match_clock_ms,
                "clock": _clock(g.match_clock_ms),
                "team": g.team_id,
                "scorer": g.player_id,
                "story": slugs.get(g.event_id),
            }
            for g in scorers
        ],
        "figures": {
            "possession": {canonical.HOME: ph, canonical.AWAY: pa},
            "shots": {canonical.HOME: sh, canonical.AWAY: sa},
            "pass_accuracy": {side: int(acc[side]) for side in _SIDES},
            "synthetic_xg": {side: float(xgs[side]) for side in _SIDES},
            "tackles_leader": {"player": leader, "team": leader_team, "tackles": tk},
        },
        "milestones": milestones,
        "checks": [
            {"label": label, "claim_ids": [line["claim_id"] for line in lines]}
            for label, lines in checks
            if lines
        ],
        "unchecked": [
            {
                "en": "Why the score changed: tactics and individual errors",
                "es": "Por qué cambió el marcador: táctica y errores individuales",
                "fr": "Pourquoi le score a changé : tactique et erreurs individuelles",
            },
            {
                "en": "Cards and substitutions (logged, no registered check yet)",
                "es": "Tarjetas y cambios (registrados, sin comprobación todavía)",
                "fr": "Cartons et remplacements (enregistrés, pas encore de vérification)",
            },
        ],
        "text": text,
    }


def _period(log: tuple[MatchEvent, ...], event_id: str) -> int:
    """The period an event belongs to."""
    return next(e.period for e in log if e.event_id == event_id)


def build_recap_feed(log: tuple[MatchEvent, ...] | None = None) -> dict[str, Any]:
    """The half-time recap and the recap at the replay point, with the claims behind them."""
    events = log if log is not None else canonical.generate_canonical_match()
    builder = _Builder(events)
    slugs = {story["event_id"]: story["slug"] for story in build_story_feed(events)["stories"]}
    recaps = [
        _recap(builder, "half-time", HALF_TIME_END_MS, True, slugs),
        _recap(builder, "latest", REPLAY_END_MS, False, slugs),
    ]
    return {
        "schema": RECAP_SCHEMA,
        "match_id": canonical.MATCH_ID,
        "synthetic": True,
        "replay_end_ms": REPLAY_END_MS,
        "personas": list(PERSONAS),
        "languages": list(LANGUAGES),
        "teams": {side: _name(side) for side in _SIDES},
        "note": (
            "Automated recaps at half-time and at the replay point. Every figure comes from a "
            "claim the verifier checked against the event log; the wording around the figures "
            "is a template, and what the log cannot show is listed as not checked. Spanish and "
            "French are AI-assisted templates awaiting native review. Nothing here is "
            "published: a producer decides."
        ),
        "recaps": recaps,
        "claims": [builder.claims[key] for key in sorted(builder.claims)],
    }
