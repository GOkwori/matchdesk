"""Fan stories for every goal, written only from verified claims.

Each goal in the log becomes a story: who scored, the score it made, the scorer's tally,
and how the move began (a corner, an interception, or simply the start of the move). Each of
those is a structured claim the verifier checks against the event log; the headline and body
in each persona and language are composed from the verified values, so the words cannot
claim more than the checks. What the log cannot show (defender positions, who made the final
pass) is listed as not checked rather than guessed.

The feed is deterministic. Nothing here publishes anything: a producer still decides.
"""

from __future__ import annotations

from typing import Any

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_claims import DISPLAY_NAMES, REPLAY_END_MS
from matchdesk.domain.models import (
    Claim,
    EventFact,
    MatchEvent,
    MatchWindow,
    Subject,
    round_half_up,
)
from matchdesk.domain.overlay_feed import LANGUAGES, PERSONAS, _Builder, _clock, _minute

STORY_SCHEMA = "matchdesk-story-feed/1"
CORNER_WINDOW_MS = 30_000
_SIDES = (canonical.HOME, canonical.AWAY)
_ORDINAL = {
    "en": {2: "second", 3: "third", 4: "fourth"},
    "es": {2: "segundo", 3: "tercer", 4: "cuarto"},
    "fr": {2: "deuxième", 3: "troisième", 4: "quatrième"},
}


def _name(identity: str) -> str:
    """Display name for a team or player."""
    return DISPLAY_NAMES.get(identity, identity)


def _of_fr(name: str) -> str:
    """French "de" with elision before a vowel: d'Okafor, de Lindqvist."""
    return f"d'{name}" if name[:1].lower() in "aeiouyh" else f"de {name}"


def _slugify(text: str) -> str:
    """Lower-case words joined by hyphens."""
    return "-".join("".join(ch if ch.isalnum() else " " for ch in text.lower()).split())


def _context(team: str, before: dict[str, int], after: dict[str, int], led_before: bool) -> str:
    """What the goal did to the score, from the scoring team's side."""
    other = next(side for side in _SIDES if side != team)
    if sum(before.values()) == 0:
        return "opener"
    if after[team] == after[other]:
        return "equaliser"
    if after[team] < after[other]:
        return "pulls_back"
    if before[team] == before[other]:
        return "lead_restored" if led_before else "lead_taken"
    return "extends"


def _verb(context: str, team: str, lang: str) -> str:
    """The headline verb phrase for a score context."""
    phrases = {
        "opener": {
            "en": f"puts {team} ahead",
            "es": f"adelanta al {team}",
            "fr": f"donne l'avantage à {team}",
        },
        "equaliser": {
            "en": f"equalises for {team}",
            "es": f"empata para el {team}",
            "fr": f"égalise pour {team}",
        },
        "lead_restored": {
            "en": f"restores the {team} lead",
            "es": f"devuelve la ventaja al {team}",
            "fr": f"redonne l'avantage à {team}",
        },
        "lead_taken": {
            "en": f"puts {team} in front",
            "es": f"pone por delante al {team}",
            "fr": f"met {team} devant",
        },
        "pulls_back": {
            "en": f"pulls one back for {team}",
            "es": f"recorta distancias para el {team}",
            "fr": f"réduit l'écart pour {team}",
        },
        "extends": {
            "en": f"extends the {team} lead",
            "es": f"amplía la ventaja del {team}",
            "fr": f"creuse l'écart pour {team}",
        },
    }
    return phrases[context][lang]


def _slug(scorer: str, header: bool, context: str, team: str) -> str:
    """A stable, readable address for the story."""
    verb = {
        "opener": "opens the scoring",
        "equaliser": f"equalises for {team}",
        "lead_restored": f"restores {team} lead",
        "lead_taken": f"puts {team} in front",
        "pulls_back": f"pulls one back for {team}",
        "extends": f"extends {team} lead",
    }[context]
    return _slugify(f"{scorer} {'header ' if header else ''}{verb}")


def _lead_in(log: tuple[MatchEvent, ...], goal: MatchEvent) -> tuple[str, MatchEvent]:
    """How the move began: a corner within 30 s, else the start of the team's unbroken run."""
    index = log.index(goal)
    for event in reversed(log[:index]):
        if goal.match_clock_ms - event.match_clock_ms > CORNER_WINDOW_MS:
            break
        if event.team_id == goal.team_id and "corner" in event.tags:
            return "corner", event
    start = index
    while (
        start > 0
        and log[start - 1].team_id == goal.team_id
        and log[start - 1].period == goal.period
    ):
        start -= 1
    first = log[start]
    return ("interception" if "interception" in first.tags else "move"), first


def _lead_in_words(kind: str, seconds: int) -> dict[str, dict[str, str]]:
    """The lead-in, as a clause, a check label and a diagram label, per language."""
    if kind == "corner":
        return {
            "clause": {
                "en": f"{seconds} seconds after a corner",
                "es": f"{seconds} segundos después de un córner",
                "fr": f"{seconds} secondes après un corner",
            },
            "check": {
                "en": f"Corner, then goal {seconds} s later",
                "es": f"Córner y gol {seconds}\u00a0s después",
                "fr": f"Corner, puis but {seconds}\u00a0s plus tard",
            },
            "start": {"en": "Corner", "es": "Córner", "fr": "Corner"},
        }
    if kind == "interception":
        return {
            "clause": {
                "en": f"{seconds} seconds after an interception",
                "es": f"{seconds} segundos después de una intercepción",
                "fr": f"{seconds} secondes après une interception",
            },
            "check": {
                "en": f"Interception, then goal {seconds} s later",
                "es": f"Intercepción y gol {seconds}\u00a0s después",
                "fr": f"Interception, puis but {seconds}\u00a0s plus tard",
            },
            "start": {"en": "Interception", "es": "Intercepción", "fr": "Interception"},
        }
    return {
        "clause": {
            "en": f"{seconds} seconds after the move began",
            "es": f"{seconds} segundos después de iniciarse la jugada",
            "fr": f"{seconds} secondes après le début de l'action",
        },
        "check": {
            "en": f"Move began, goal {seconds} s later",
            "es": f"Inicio de la jugada y gol {seconds}\u00a0s después",
            "fr": f"Début de l'action, puis but {seconds}\u00a0s plus tard",
        },
        "start": {"en": "Move begins", "es": "Empieza la jugada", "fr": "Début de l'action"},
    }


def _story(
    builder: _Builder,
    goal: MatchEvent,
    before: dict[str, int],
    led_before: bool,
) -> dict[str, Any]:
    """One goal: its verified claims, its build-up and its text in every persona and language."""
    log = builder.log
    assert goal.team_id is not None and goal.player_id is not None
    team_id, scorer_id = goal.team_id, goal.player_id
    team, scorer = _name(team_id), _name(scorer_id)
    clock = _clock(goal.match_clock_ms)
    shot = next(
        (
            event
            for event in reversed(log[: log.index(goal)])
            if event.type == "shot" and event.player_id == scorer_id
        ),
        None,
    )
    header = shot is not None and "header" in shot.tags
    key = goal.event_id

    scored = builder.check(
        Claim(
            claim_id=f"ST-{key}-SCORER",
            text=(
                f"{scorer} headed in for {team} at {clock}."
                if header
                else f"{scorer} scored for {team} at {clock}."
            ),
            kind="event_fact",
            fact=EventFact(query="goal_scorer.v1", event_id=key, player_id=scorer_id),
            evidence_event_ids=(key,),
        )
    )
    upto = MatchWindow(from_ms=0, to_ms=goal.match_clock_ms + 1000)
    upto_clock = _clock(goal.match_clock_ms + 1000)
    after: dict[str, int] = {}
    score_lines = []
    for side in _SIDES:
        value, line = builder.metric(
            f"ST-{key}-{side.upper()}",
            "goals.v1",
            Subject(team_id=side),
            upto,
            f"{_name(side)} scored {{v}} goal{{s}} up to {upto_clock}.",
        )
        after[side] = int(value)
        score_lines.append(line)
    tally_value, tally = builder.metric(
        f"ST-{key}-TALLY",
        "goals.v1",
        Subject(player_id=scorer_id),
        upto,
        f"{scorer} scored {{v}} goal{{s}} up to {upto_clock}.",
    )
    count = int(tally_value)
    kind, start = _lead_in(log, goal)
    seconds = int(round_half_up((goal.match_clock_ms - start.match_clock_ms) / 1000, 0))
    words = _lead_in_words(kind, seconds)
    gap = builder.check(
        Claim(
            claim_id=f"ST-{key}-LEADIN",
            text=f"The goal came {words['clause']['en']}.",
            kind="event_fact",
            fact=EventFact(
                query="sequence_gap.v1",
                event_id=key,
                from_event_id=start.event_id,
                from_tag=None if kind == "move" else kind,
                gap_seconds=seconds,
            ),
            evidence_event_ids=(start.event_id, key),
        )
    )
    context = _context(team_id, before, after, led_before)
    home, away = after[canonical.HOME], after[canonical.AWAY]
    minute = _minute(goal.match_clock_ms)
    how = {
        "en": "heads in" if header else "scores",
        "es": "marca de cabeza" if header else "marca",
        "fr": "marque de la tête" if header else "marque",
    }
    tally_sentence = {
        "en": f" It is {scorer}'s {_ORDINAL['en'][count]} goal of the match." if count > 1 else "",
        "es": f" Es el {_ORDINAL['es'][count]} gol de {scorer} en el partido." if count > 1 else "",
        "fr": f" C'est le {_ORDINAL['fr'][count]} but {_of_fr(scorer)} dans le match."
        if count > 1
        else "",
    }
    score_word = {"en": "It's", "es": "Ahora", "fr": "Score\u00a0:"}
    goal_word = {"en": "GOAL", "es": "GOL", "fr": "BUT"}
    goals_word = {"en": "goals", "es": "goles", "fr": "buts"}
    text: dict[str, dict[str, dict[str, str]]] = {persona: {} for persona in PERSONAS}
    for lang in LANGUAGES:
        clause = words["clause"][lang]
        text["fan"][lang] = {
            "headline": f"{minute}′ · {scorer} {_verb(context, team, lang)}",
            "body": (
                f"{scorer} {how[lang]} at {clock}, {clause}.{tally_sentence[lang]} "
                f"{score_word[lang]} {home}–{away}."
                if lang == "en"
                else (
                    f"{scorer} {how[lang]} en el {clock}, {clause}.{tally_sentence[lang]} "
                    f"{score_word[lang]} {home}–{away}."
                    if lang == "es"
                    else f"{scorer} {how[lang]} à {clock}, {clause}.{tally_sentence[lang]} "
                    f"{score_word[lang]} {home}–{away}."
                )
            ),
        }
        text["analyst"][lang] = {
            "headline": f"{goal_word[lang]} {clock} · {scorer} ({team}) · {home}–{away}",
            "body": (
                f"{goal_word[lang]} {key} · {clock} · {scorer}"
                f"{' · ' + {'en': 'header', 'es': 'cabezazo', 'fr': 'tête'}[lang] if header else ''}"
                f" · {words['check'][lang]} ({start.event_id})"
                f" · {scorer} {goals_word[lang]}: {count} · Northbridge {home}–{away} Riverside"
            ),
        }
        text["caption"][lang] = {
            "headline": f"{minute}′ {goal_word[lang]} · {scorer} · NBR {home}–{away} RIV",
            "body": f"{words['check'][lang]} · {scorer} {goals_word[lang]}: {count}",
        }
    index = log.index(goal)
    buildup = [
        {
            "id": event.event_id,
            "t_ms": event.match_clock_ms,
            "type": event.type,
            "player": event.player_id,
            "outcome": event.outcome,
            "tags": list(event.tags),
            "x": event.location.x if event.location else None,
            "y": event.location.y if event.location else None,
            "end_x": event.end_location.x if event.end_location else None,
            "end_y": event.end_location.y if event.end_location else None,
        }
        for event in log[log.index(start) : index + 1]
        if event.team_id == team_id
    ]
    return {
        "slug": _slug(scorer, header, context, team),
        "event_id": key,
        "t_ms": goal.match_clock_ms,
        "clock": clock,
        "minute": minute,
        "team": team_id,
        "scorer": scorer_id,
        "header": header,
        "context": context,
        "score": {"before": dict(before), "after": dict(after)},
        "scorer_goals": count,
        "lead_in": {"kind": kind, "event_id": start.event_id, "seconds": seconds},
        "buildup": buildup,
        "checks": [
            {
                "claim_ids": [scored["claim_id"]],
                "label": {"en": "Goal scorer", "es": "Autor del gol", "fr": "Buteur"},
            },
            {
                "claim_ids": [line["claim_id"] for line in score_lines],
                "label": {
                    "en": f"Score after the goal, {home}–{away}",
                    "es": f"Marcador tras el gol, {home}–{away}",
                    "fr": f"Score après le but, {home}–{away}",
                },
            },
            {
                "claim_ids": [tally["claim_id"]],
                "label": {
                    "en": f"{scorer}'s goals so far: {count}",
                    "es": f"Goles de {scorer} hasta ahora: {count}",
                    "fr": f"Buts {_of_fr(scorer)} à ce stade\u00a0: {count}",
                },
            },
            {"claim_ids": [gap["claim_id"]], "label": words["check"]},
        ],
        "unchecked": [
            {
                "en": "Who made the final pass",
                "es": "Autor del último pase",
                "fr": "Auteur de la dernière passe",
            },
            {
                "en": "Defender positions",
                "es": "Posición de los defensas",
                "fr": "Position des défenseurs",
            },
        ],
        "diagram": {
            lang: (
                f"① {words['start'][lang]} {_clock(start.match_clock_ms)} · "
                f"② {scorer} {_clock(goal.match_clock_ms)}"
            )
            for lang in LANGUAGES
        },
        "text": text,
    }


def build_story_feed(log: tuple[MatchEvent, ...] | None = None) -> dict[str, Any]:
    """A story for every goal before the replay point, in time order."""
    events = log if log is not None else canonical.generate_canonical_match()
    builder = _Builder(events)
    score = {side: 0 for side in _SIDES}
    led = {side: False for side in _SIDES}
    stories = []
    for goal in (e for e in events if e.type == "goal" and e.match_clock_ms < REPLAY_END_MS):
        assert goal.team_id is not None
        story = _story(builder, goal, dict(score), led[goal.team_id])
        score = dict(story["score"]["after"])
        for side in _SIDES:
            other = next(s for s in _SIDES if s != side)
            led[side] = led[side] or score[side] > score[other]
        stories.append(story)
    slugs = [story["slug"] for story in stories]
    assert len(set(slugs)) == len(slugs), "story slugs must be unique"
    return {
        "schema": STORY_SCHEMA,
        "match_id": canonical.MATCH_ID,
        "synthetic": True,
        "replay_end_ms": REPLAY_END_MS,
        "personas": list(PERSONAS),
        "languages": list(LANGUAGES),
        "note": (
            "One story per goal. Every figure and fact in the text comes from a claim the "
            "verifier checked against the event log; what the log cannot show is listed as not "
            "checked. Spanish and French are AI-assisted templates awaiting native review. "
            "Fans only see a story after a producer approves it."
        ),
        "stories": stories,
        "claims": [builder.claims[key] for key in sorted(builder.claims)],
    }
