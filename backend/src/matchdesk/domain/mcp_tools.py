"""Read-only match tools for other agents: statistics, events, checks, overlays, stories, recaps.

These are the tools MatchDesk's MCP endpoint offers, so a broadcaster's own agent can ask what
happened, compute a registered statistic, and have a sentence checked by the same verifier the
studio uses before it goes anywhere near a screen. Everything reads the synthetic match up to
the replay point; nothing writes, publishes or calls a model.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pydantic import ValidationError

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_claims import DISPLAY_NAMES, REPLAY_END_MS, evidence_record
from matchdesk.domain.metrics import METRIC_DEFINITIONS, compute_metric
from matchdesk.domain.models import Claim, MatchEvent, MatchWindow, MetricAssertion, Subject
from matchdesk.domain.overlay_feed import LANGUAGES, PERSONAS, build_overlay_feed
from matchdesk.domain.recap_feed import build_recap_feed
from matchdesk.domain.story_feed import build_story_feed
from matchdesk.domain.verification import verify_claim

MAX_EVENTS = 200
_MINUTE = 60_000
_LAST_MINUTE = REPLAY_END_MS // _MINUTE + 1
_TEAMS = (canonical.HOME, canonical.AWAY)


class ToolError(ValueError):
    """A tool was asked for something it cannot answer; the message says what to change."""


@lru_cache(maxsize=1)
def _log() -> tuple[MatchEvent, ...]:
    """The synthetic match up to the replay point."""
    return tuple(
        e for e in canonical.generate_canonical_match() if e.match_clock_ms < REPLAY_END_MS
    )


@lru_cache(maxsize=1)
def _overlays() -> dict[str, Any]:
    """The overlay feed, built once."""
    return build_overlay_feed()


@lru_cache(maxsize=1)
def _stories() -> dict[str, Any]:
    """The story feed, built once."""
    return build_story_feed()


@lru_cache(maxsize=1)
def _recaps() -> dict[str, Any]:
    """The recap feed, built once."""
    return build_recap_feed()


def _choice(args: Mapping[str, Any], key: str, options: tuple[str, ...], default: str) -> str:
    """A value from a fixed list, or the default."""
    value = args.get(key, default)
    if value not in options:
        raise ToolError(f"{key} must be one of {', '.join(options)}")
    return str(value)


def _minute(args: Mapping[str, Any], key: str, default: int) -> int:
    """A whole minute inside the replay."""
    value = args.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= _LAST_MINUTE:
        raise ToolError(f"{key} must be a whole minute from 0 to {_LAST_MINUTE}")
    return value


def _window(args: Mapping[str, Any]) -> MatchWindow:
    """The requested window, clipped to the replay point; a period limits it to one half."""
    start = _minute(args, "from_minute", 0) * _MINUTE
    end = min(_minute(args, "to_minute", _LAST_MINUTE) * _MINUTE, REPLAY_END_MS)
    period = args.get("period")
    if period not in (None, 1, 2):
        raise ToolError("period must be 1 or 2")
    if period == 2:
        start = max(start, canonical.SECOND_HALF_MS)
    if end <= start:
        raise ToolError("to_minute must be after from_minute, and inside the replay")
    return MatchWindow(period=period, from_ms=start, to_ms=end)


def _subject(args: Mapping[str, Any]) -> Subject:
    """A team (nbr, riv) or a player id such as nbr-09."""
    team, player = args.get("team"), args.get("player")
    if team is not None and team not in _TEAMS:
        raise ToolError("team must be nbr (Northbridge) or riv (Riverside)")
    players = {str(m["player_id"]) for team in _TEAMS for m in canonical.squad(team)}
    if player is not None and player not in players:
        raise ToolError("player must be a player id such as nbr-09; list_players gives them all")
    if team is None and player is None:
        raise ToolError("give a team or a player")
    return Subject(team_id=team, player_id=player)


def _clock(ms: int) -> str:
    """mm:ss."""
    return f"{ms // 60_000:02d}:{ms // 1000 % 60:02d}"


def list_metrics(args: Mapping[str, Any]) -> dict[str, Any]:
    """The eighteen registered statistics: id, unit and definition."""
    del args
    return {
        "metrics": [
            {"metric": d.metric_id, "unit": d.unit, "definition": d.description}
            for d in METRIC_DEFINITIONS.values()
        ],
        "note": "Every figure MatchDesk states is one of these, recomputed from the event log.",
    }


def list_players(args: Mapping[str, Any]) -> dict[str, Any]:
    """Both squads: player id, name, shirt, position, club and whether they started."""
    del args
    return {
        "teams": {team: DISPLAY_NAMES[team] for team in _TEAMS},
        "players": [
            {
                "player": str(member["player_id"]),
                "name": str(member["name"]),
                "team": team,
                "shirt": member["shirt"],
                "position": member["position"],
                "starter": member["starter"],
            }
            for team in _TEAMS
            for member in canonical.squad(team)
        ],
    }


def compute(args: Mapping[str, Any]) -> dict[str, Any]:
    """One registered statistic for a team or player over a window of the match."""
    metric = args.get("metric")
    if metric not in METRIC_DEFINITIONS:
        raise ToolError("metric must be a registered metric id; list_metrics gives them all")
    window = _window(args)
    subject = _subject(args)
    value = compute_metric(str(metric), _log(), subject, window)
    return {
        "metric": metric,
        "unit": METRIC_DEFINITIONS[str(metric)].unit,
        "value": value,
        "subject": subject.model_dump(exclude_none=True, exclude={"schema_version"}),
        "window": {
            **window.model_dump(exclude_none=True, exclude={"schema_version"}),
            "from": _clock(window.from_ms),
            "to": _clock(window.to_ms),
        },
        "synthetic": True,
    }


def _result(claim: Claim) -> dict[str, Any]:
    """Run the verifier over the whole log to the replay point."""
    log = _log()
    result = verify_claim(claim, evidence_record(log), log, names=DISPLAY_NAMES)
    return {
        "claim_id": result.claim_id,
        "status": result.status,
        "verified": result.status == "verified",
        "reason": result.reason,
        "query_id": result.query_id,
        "expected": result.expected,
        "observed": result.observed,
    }


def check_sentence(args: Mapping[str, Any]) -> dict[str, Any]:
    """Check a sentence that states one registered statistic, as the studio checks its own."""
    text = args.get("sentence")
    if not isinstance(text, str) or not 3 <= len(text) <= 300:
        raise ToolError("sentence must be text of 3 to 300 characters")
    metric = args.get("metric")
    if metric not in METRIC_DEFINITIONS:
        raise ToolError("metric must be a registered metric id; list_metrics gives them all")
    value = args.get("value")
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ToolError("value must be the number the sentence states (a ratio as 0.58 for 58%)")
    window = _window(args)
    subject = _subject(args)
    definition = METRIC_DEFINITIONS[str(metric)]
    decimals = args.get("decimals")
    if decimals is None and definition.unit == "ratio":
        decimals = 2
    counted = {"goals.v1": "goal", "shots.v1": "shot"}.get(str(metric))
    cited = [
        e.event_id
        for e in _log()
        if (counted is None or e.type == counted)
        and (window.period is None or e.period == window.period)
        and window.from_ms <= e.match_clock_ms < window.to_ms
        and (subject.team_id is None or counted is None or e.team_id == subject.team_id)
        and (subject.player_id is None or counted is None or e.player_id == subject.player_id)
    ]
    try:
        claim = Claim(
            claim_id="MCP-CHECK",
            text=text,
            kind="measured_stat",
            assertion=MetricAssertion(
                metric=str(metric),
                subject=subject,
                window=window,
                value=float(value),
                unit=definition.unit,  # type: ignore[arg-type]
                decimals=decimals,
            ),
            evidence_event_ids=tuple(cited[:50] if counted else cited[:1]) or ("E-0001",),
        )
    except ValidationError as error:
        raise ToolError(f"the claim is malformed: {error.errors()[0]['msg']}") from error
    return {**_result(claim), "claim": claim.model_dump(mode="json", exclude_none=True)}


def verify(args: Mapping[str, Any]) -> dict[str, Any]:
    """Verify a full MatchDesk claim contract (measured statistic or registered event fact)."""
    try:
        claim = Claim.model_validate(args.get("claim"))
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise ToolError(f"the claim is malformed at {where}: {first['msg']}") from error
    return _result(claim)


def get_events(args: Mapping[str, Any]) -> dict[str, Any]:
    """Logged events in a window, optionally for one team, player or event type."""
    window = _window(args)
    limit = args.get("limit", 50)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_EVENTS:
        raise ToolError(f"limit must be from 1 to {MAX_EVENTS}")
    kind = args.get("type")
    team, player = args.get("team"), args.get("player")
    matched = [
        e
        for e in _log()
        if (window.period is None or e.period == window.period)
        and window.from_ms <= e.match_clock_ms < window.to_ms
        and (kind is None or e.type == kind)
        and (team is None or e.team_id == team)
        and (player is None or e.player_id == player)
    ]
    return {
        "count": len(matched),
        "returned": min(len(matched), limit),
        "events": [
            {
                "event_id": e.event_id,
                "clock": _clock(e.match_clock_ms),
                "period": e.period,
                "type": e.type,
                "team": e.team_id,
                "player": e.player_id,
                "player_name": DISPLAY_NAMES.get(e.player_id or "", None),
                "outcome": e.outcome,
                "under_pressure": e.under_pressure,
                "xg": e.xg,
                "tags": list(e.tags),
                "location": e.location.model_dump() if e.location else None,
                "end_location": e.end_location.model_dump() if e.end_location else None,
            }
            for e in matched[:limit]
        ],
        "synthetic": True,
    }


def _status(claim_ids: list[str], claims: dict[str, dict[str, Any]]) -> str:
    """verified when every claim behind something is; logged when nothing is behind it."""
    if not claim_ids:
        return "logged"
    return "verified" if all(claims[i]["status"] == "verified" for i in claim_ids) else "failed"


def get_overlays(args: Mapping[str, Any]) -> dict[str, Any]:
    """Timed overlay cues in a window, in one persona and language, with their verification."""
    persona = _choice(args, "persona", PERSONAS, "fan")
    language = _choice(args, "language", LANGUAGES, "en")
    window = _window(args)
    feed = _overlays()
    claims = {c["claim_id"]: c for c in feed["claims"]}
    return {
        "schema": feed["schema"],
        "cues": [
            {
                "cue_id": cue["cue_id"],
                "clock": cue["clock"],
                "t_ms": cue["t_ms"],
                "duration_ms": cue["duration_ms"],
                "kind": cue["kind"],
                "team": cue["team"],
                "players": cue["players"],
                "text": cue["text"][persona][language],
                "status": cue["status"],
                "claims": [
                    {"claim_id": i, "text": claims[i]["text"], "status": claims[i]["status"]}
                    for i in cue["claim_ids"]
                ],
            }
            for cue in feed["cues"]
            if window.from_ms <= cue["t_ms"] < window.to_ms
        ],
        "note": "Cards and substitutions are logged events with no registered check yet.",
    }


def get_recap(args: Mapping[str, Any]) -> dict[str, Any]:
    """The half-time recap or the recap at the replay point, every figure verified."""
    which = _choice(args, "at", ("half-time", "latest"), "latest")
    persona = _choice(args, "persona", PERSONAS, "fan")
    language = _choice(args, "language", LANGUAGES, "en")
    feed = _recaps()
    claims = {c["claim_id"]: c for c in feed["claims"]}
    recap = next(r for r in feed["recaps"] if r["id"] == which)
    return {
        "recap": which,
        "title": recap["title"][language],
        "headline": recap["text"][persona][language]["headline"],
        "body": recap["text"][persona][language]["body"],
        "score": recap["score"],
        "figures": recap["figures"],
        "milestones": [
            {
                "clock": _clock(m["t_ms"]),
                "label": m["label"][language],
                "status": _status(m["claim_ids"], claims),
            }
            for m in recap["milestones"]
        ],
        "checks": [
            {
                "label": c["label"][language],
                "status": _status(c["claim_ids"], claims),
                "claims": [claims[i]["text"] for i in c["claim_ids"]],
            }
            for c in recap["checks"]
        ],
        "not_checked": [row[language] for row in recap["unchecked"]],
    }


def get_story(args: Mapping[str, Any]) -> dict[str, Any]:
    """The fan story for one goal (or the list of goals when none is named)."""
    persona = _choice(args, "persona", PERSONAS, "fan")
    language = _choice(args, "language", LANGUAGES, "en")
    feed = _stories()
    stories = feed["stories"]
    slug = args.get("story")
    if slug is None:
        return {
            "stories": [
                {
                    "story": s["slug"],
                    "clock": s["clock"],
                    "headline": s["text"][persona][language]["headline"],
                }
                for s in stories
            ]
        }
    story = next((s for s in stories if s["slug"] == slug or s["event_id"] == slug), None)
    if story is None:
        raise ToolError(
            "story must be a story slug or goal event id; call get_story without one to list them"
        )
    claims = {c["claim_id"]: c for c in feed["claims"]}
    return {
        "story": story["slug"],
        "clock": story["clock"],
        "headline": story["text"][persona][language]["headline"],
        "body": story["text"][persona][language]["body"],
        "checks": [
            {"label": c["label"][language], "status": _status(c["claim_ids"], claims)}
            for c in story["checks"]
        ],
        "not_checked": [row[language] for row in story["unchecked"]],
    }


@dataclass(frozen=True)
class Tool:
    """One tool: its name, what it does, its input schema and its handler."""

    name: str
    title: str
    description: str
    schema: dict[str, Any]
    handler: Callable[[Mapping[str, Any]], dict[str, Any]]


_WINDOW_PROPS: dict[str, Any] = {
    "from_minute": {
        "type": "integer",
        "minimum": 0,
        "maximum": _LAST_MINUTE,
        "description": "Start minute (default 0).",
    },
    "to_minute": {
        "type": "integer",
        "minimum": 1,
        "maximum": _LAST_MINUTE,
        "description": f"End minute, exclusive (default: the replay point, {_clock(REPLAY_END_MS)}).",
    },
    "period": {
        "type": "integer",
        "enum": [1, 2],
        "description": "Limit to the first or second half.",
    },
}
_SUBJECT_PROPS: dict[str, Any] = {
    "team": {
        "type": "string",
        "enum": list(_TEAMS),
        "description": "nbr = Northbridge, riv = Riverside.",
    },
    "player": {"type": "string", "description": "A player id such as nbr-09 (see list_players)."},
}
_STYLE_PROPS: dict[str, Any] = {
    "persona": {
        "type": "string",
        "enum": list(PERSONAS),
        "description": "analyst, fan or caption (default fan).",
    },
    "language": {
        "type": "string",
        "enum": list(LANGUAGES),
        "description": "en, es or fr (default en).",
    },
}
_METRIC_PROP = {
    "type": "string",
    "enum": list(METRIC_DEFINITIONS),
    "description": "A registered metric id.",
}


def _object(props: dict[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    """A closed JSON Schema object."""
    return {
        "type": "object",
        "properties": props,
        "required": list(required),
        "additionalProperties": False,
    }


TOOLS: tuple[Tool, ...] = (
    Tool(
        "list_metrics",
        "Registered statistics",
        "List the eighteen registered statistics MatchDesk computes from the event log (including synthetic tracking: shot speed, top speed, distance covered, sprints), with units and definitions.",
        _object({}),
        list_metrics,
    ),
    Tool(
        "list_players",
        "Teams and players",
        "List the two clubs and every player id, name and club in the synthetic match.",
        _object({}),
        list_players,
    ),
    Tool(
        "compute_metric",
        "Compute a statistic",
        "Compute one registered statistic for a team or player over a window of the match, recomputed from the event log.",
        _object({"metric": _METRIC_PROP, **_SUBJECT_PROPS, **_WINDOW_PROPS}, ("metric",)),
        compute,
    ),
    Tool(
        "check_sentence",
        "Check a sentence",
        "Check a sentence that states one registered statistic before it is shown: the number is recomputed at the stated precision, and the sentence must name the subject, the statistic and any time window it states. Returns verified or the reason it was sent back. Example: sentence 'Northbridge have had 58% possession.', metric possession_time.v1, team nbr, value 0.58.",
        _object(
            {
                "sentence": {"type": "string", "minLength": 3, "maxLength": 300},
                "metric": _METRIC_PROP,
                "value": {
                    "type": "number",
                    "description": "The number stated; a percentage as a ratio (58% is 0.58).",
                },
                "decimals": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 6,
                    "description": "Precision stated (ratios default to 2, i.e. whole percent).",
                },
                **_SUBJECT_PROPS,
                **_WINDOW_PROPS,
            },
            ("sentence", "metric", "value"),
        ),
        check_sentence,
    ),
    Tool(
        "verify_claim",
        "Verify a claim contract",
        "Verify a full MatchDesk claim contract (kind measured_stat with an assertion, or event_fact with a registered fact query such as goal_scorer.v1 or sequence_gap.v1) with the deterministic verifier.",
        _object(
            {
                "claim": {
                    "type": "object",
                    "description": "A Claim as in matchdesk.domain.models.Claim.",
                }
            },
            ("claim",),
        ),
        verify,
    ),
    Tool(
        "get_events",
        "Read events",
        "Read logged events in a window, optionally for one team, player or event type (pass, shot, goal, recovery, card, substitution...).",
        _object(
            {
                **_WINDOW_PROPS,
                **_SUBJECT_PROPS,
                "type": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_EVENTS},
            }
        ),
        get_events,
    ),
    Tool(
        "get_overlays",
        "Overlay cues",
        "Timed, machine-readable overlay cues in a window, in one persona and language, each with the claims behind it and whether they verified.",
        _object({**_WINDOW_PROPS, **_STYLE_PROPS}),
        get_overlays,
    ),
    Tool(
        "get_recap",
        "Match recap",
        "The automated half-time recap or the recap at the replay point, in one persona and language, with every figure's check.",
        _object({"at": {"type": "string", "enum": ["half-time", "latest"]}, **_STYLE_PROPS}),
        get_recap,
    ),
    Tool(
        "get_story",
        "Fan story",
        "The verified fan story for a goal (by slug or goal event id), or the list of goal stories when none is named.",
        _object({"story": {"type": "string"}, **_STYLE_PROPS}),
        get_story,
    ),
)
TOOLS_BY_NAME: dict[str, Tool] = {tool.name: tool for tool in TOOLS}
