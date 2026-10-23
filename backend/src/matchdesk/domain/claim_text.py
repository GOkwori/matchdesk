"""Bind a claim's sentence to its structured assertion.

The verifier recomputes the structured assertion. Without this module the sentence
beside it was never read, so "Okafor scored a hat-trick" with an assertion of two
goals came back verified. Two rules close that gap:

- Always: every quantity the sentence states must equal the asserted value.
- With a display-name registry: the sentence must also name its subject and state the
  asserted value, so the words a reader sees are the words that were checked.

With a display-name registry the sentence is reader-facing, and these rules also apply:

- It may not negate itself ("Okafor did not score 2 goals"): negative claims are not checked.
- A measured claim must name its own statistic and no other ("Okafor took 2 shots" is not a
  goals claim).
- It may name only the subject's own team.
- Any time it states must be its assertion's window; a window that is not "from kick-off"
  (a half, or a start after kick-off) must be stated.
- An event fact's clock times and minutes must be those of the events it cites, and it may
  not add details the event log does not record (a penalty, a header, a free kick) unless
  the cited events carry that tag (a goal also carries the tags of the shot it was scored
  from: the scorer's goal-bound shot logged immediately before it).

Extraction is deliberately small and fails closed: ambiguous prose ("one of the two
goals") is sent back for revision rather than guessed at. The TypeScript port in
apps/web/src/studio/verifier.ts must reproduce it exactly; the parity fixture enforces it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from matchdesk.domain.models import Claim, MatchEvent, MatchWindow, round_half_up

_NUMBER_WORDS: Mapping[str, int] = {
    "zero": 0,
    "one": 1,
    "once": 1,
    "two": 2,
    "twice": 2,
    "both": 2,
    "brace": 2,
    "double": 2,
    "three": 3,
    "thrice": 3,
    "hat-trick": 3,
    "hat trick": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
# ASCII-explicit boundaries and digits: Python's \b and \d are Unicode-aware and
# JavaScript's are not, so explicit classes keep the browser port exact.
_B = r"(?<![A-Za-z0-9_])"
_E = r"(?![A-Za-z0-9_])"
# Order matters: longer phrases before the words they contain.
_WORD_PATTERN = re.compile(
    _B
    + "("
    + "|".join(re.escape(word) for word in sorted(_NUMBER_WORDS, key=len, reverse=True))
    + ")"
    + _E
)
_CLOCK = re.compile(r"[0-9]{1,3}:[0-9]{2}")
_SCORELINE = re.compile(_B + r"[0-9]+\s*[-\u2013\u2014]\s*[0-9]+" + _E)
_MINUTE = re.compile(_B + r"[0-9]+\s*(?:'|\u2032|\u2019|(?:st|nd|rd|th|mins?|minutes?)" + _E + ")")
_PERCENT = re.compile(_B + r"([0-9]+(?:\.[0-9]+)?)\s*(?:%|per\s?cent" + _E + ")")
_DIGITS = re.compile(_B + r"[0-9]+(?:\.[0-9]+)?" + _E)
# Identifiers such as E-1366, nbr-09 or CL-0214 name a record; they state no quantity.
_IDENTIFIER = re.compile(_B + r"[a-z]+-[0-9]+" + _E)

TEXT_QUERY_ID = "claim-text-binding-v1"


@dataclass(frozen=True)
class StatedQuantities:
    """The counts and percentages a sentence states, in order of appearance."""

    counts: tuple[Decimal, ...]
    percents: tuple[Decimal, ...]


def stated_quantities(text: str) -> StatedQuantities:
    """Extract stated counts and percentages, ignoring clocks, scorelines, minutes and IDs."""
    lowered = text.lower().replace("’", "'")
    lowered = _IDENTIFIER.sub(" ", lowered)
    lowered = _CLOCK.sub(" ", lowered)
    lowered = _SCORELINE.sub(" ", lowered)
    percents = tuple(Decimal(match) for match in _PERCENT.findall(lowered))
    lowered = _PERCENT.sub(" ", lowered)
    lowered = _MINUTE.sub(" ", lowered)
    counts = [Decimal(match) for match in _DIGITS.findall(lowered)]
    counts.extend(Decimal(_NUMBER_WORDS[word]) for word in _WORD_PATTERN.findall(lowered))
    return StatedQuantities(counts=tuple(counts), percents=percents)


def _names_subject(text: str, name: str) -> bool:
    """Whole-word, case-insensitive match of a registered display name."""
    return re.search(_B + re.escape(name.lower()) + _E, text.lower()) is not None


def _expected_quantity(claim: Claim) -> tuple[str, Decimal] | None:
    """The quantity the sentence must state, as ("count" | "percent", value), if any."""
    if claim.assertion is not None:
        assertion = claim.assertion
        if assertion.unit == "count":
            return "count", Decimal(repr(assertion.value))
        if assertion.unit == "ratio":
            places = 6 if assertion.decimals is None else max(assertion.decimals - 2, 0)
            return "percent", round_half_up(assertion.value * 100, places)
        if assertion.unit == "synthetic_xg":
            return "count", round_half_up(
                assertion.value, 2 if assertion.decimals is None else assertion.decimals
            )
        if assertion.unit in _MEASURE_UNITS:
            return "count", round_half_up(
                assertion.value, 1 if assertion.decimals is None else assertion.decimals
            )
        return None
    if claim.fact is not None and claim.fact.gap_seconds is not None:
        return "count", Decimal(claim.fact.gap_seconds)
    return None


def _subject_id(claim: Claim) -> str | None:
    """The identity the sentence must name: a player before a team."""
    if claim.assertion is not None:
        subject = claim.assertion.subject
        return subject.player_id or subject.team_id
    if claim.fact is not None:
        return claim.fact.player_id
    return None


# Units stated as a plain number at one decimal place unless the assertion says otherwise.
_MEASURE_UNITS = frozenset({"metres", "km_per_hour", "rating", "per_minute", "kilometres"})

_NEGATION = re.compile(
    _B + r"(?:not|no|never|none|neither|nor|without|failed to|fails to|[a-z]+n't|cannot)" + _E
)
# The words that name each registered statistic. Longer phrases are matched first and
# masked, so "expected goals" is an xG phrase and never a goals word.
_METRIC_WORDS: tuple[tuple[str, str], ...] = (
    ("synthetic_xg.v1", r"expected goals|xg"),
    ("final_third_entries.v1", r"final[- ]third"),
    ("possession_time.v1", r"possession|of the ball"),
    ("pass_difficulty.v1", r"pass(?:ing)? difficulty|difficulty(?: rating)?"),
    ("pass_distance.v1", r"pass(?:es|ing)? (?:length|distance)|metres|meters"),
    ("progressive_passes.v1", r"progressive pass(?:es)?"),
    ("pressured_passes.v1", r"pass(?:es)? under pressure|pressured pass(?:es)?"),
    # Synthetic tracking. Each names its own measure, so "km/h" alone stays a ball-speed word.
    # The unit is part of the phrase, so it is masked with it.
    ("shot_speed.v1", r"shot speed(?: of| was)? [0-9.]+ km/h|shot speed"),
    ("top_speed.v1", r"top speed(?: of| was)? [0-9.]+ km/h|top speed"),
    ("distance_covered.v1", r"(?:covered|ran) [0-9.]+ (?:km|kilometres)|distance covered"),
    ("sprints.v1", r"sprints?"),
    ("ball_speed.v1", r"ball speed|km/h|speed"),
    ("tackles.v1", r"tackles?|tackled"),
    ("interceptions.v1", r"interceptions?|intercepted"),
    ("recoveries.v1", r"ball recover(?:y|ies)|recover(?:y|ies|ed)|won the ball back"),
    ("pass_accuracy.v1", r"pass(?:es|ing)?"),
    ("shots.v1", r"shots?|attempts?|efforts?"),
    ("goals.v1", r"goals?|scor(?:ed|es|ing)|brace|hat[- ]trick|netted|scoresheet"),
)
# Details of a goal or set piece the event log records only as tags, if at all.
_DETAILS: tuple[tuple[str, str], ...] = (
    ("penalty", r"penalt(?:y|ies)|spot[- ]kick"),
    ("header", r"headers?|headed|heads? (?:in|home)"),
    ("free_kick", r"free[- ]kicks?"),
    ("corner", r"corners?"),
    ("throw_in", r"throw[- ]ins?"),
    ("own_goal", r"own[- ]goals?"),
    ("volley", r"volley(?:ed|s)?"),
    ("left_foot", r"left[- ]foot(?:ed)?|left foot"),
    ("right_foot", r"right[- ]foot(?:ed)?|right foot"),
    ("outside_box", r"outside the (?:box|area)|from (?:distance|range)|long[- ]range"),
    ("inside_box", r"inside the (?:box|area)|tap[- ]ins?"),
    ("counter", r"counter[- ]attack"),
)
_MINUTE_MARK = r"([0-9]{1,3})(?:'|\u2032|\u2019)"
_WINDOW_FIRST = re.compile(
    _B + r"(?:first|1st|opening)[- ]half" + _E + r"|before (?:half[- ]?time|the break)"
)
_WINDOW_SECOND = re.compile(
    _B + r"(?:second|2nd)[- ]half" + _E + r"|after (?:half[- ]?time|the break)"
)
_WINDOW_BETWEEN = re.compile(
    _B
    + r"between ([0-9]{1,3})(?:'|\u2032|\u2019| minutes?)? and ([0-9]{1,3})(?:'|\u2032|\u2019| minutes?)?"
)
_WINDOW_FROM = re.compile(_B + r"(?:since|after|from) " + _MINUTE_MARK)
_WINDOW_TO = re.compile(_B + r"(?:before|by|until|up to) " + _MINUTE_MARK)
_WINDOW_TO_CLOCK = re.compile(_B + r"(?:before|by|until|up to) ([0-9]{1,3}):([0-9]{2})")
_WINDOW_LAST = re.compile(_B + r"(?:last|final) ([0-9]{1,3}) minutes?" + _E)
_FACT_MINUTE = re.compile(_B + r"([0-9]{1,3})(?:'|\u2032|\u2019|(?:st|nd|rd|th) minute)")
_MINUTE_MS = 60_000
_CARD_WORDS = re.compile(_B + r"(?:cards?|booked|booking|cautioned|sent off|dismissed)" + _E)
_RED_WORDS = re.compile(_B + r"(?:red|sent off|dismissed|second yellow)" + _E)
_YELLOW_WORDS = re.compile(_B + r"(?:yellow|booked|booking|cautioned)" + _E)
_SUB_WORDS = re.compile(
    _B + r"(?:replaced|replaces|substitut(?:ed|es|ion)|comes on|came on|on for|off for)" + _E
)
_GOAL_WORDS = re.compile(
    _B
    + r"(?:goals?|scor(?:ed|es|ing)|netted|(?:headed|nodded|fired|slotted|tapped|poked|"
    + r"swept|curled|volleyed|turned) (?:in|home))"
    + _E
)


def _lower(text: str) -> str:
    """Lower-case, normalise apostrophes and drop record identifiers."""
    return _IDENTIFIER.sub(" ", text.lower().replace("\u2019", "'"))


def _metrics_named(lowered: str) -> list[str]:
    """The registered statistics a sentence names, in registry order."""
    found = []
    for metric, words in _METRIC_WORDS:
        pattern = re.compile(_B + r"(?:" + words + r")" + _E)
        if pattern.search(lowered):
            found.append(metric)
            lowered = pattern.sub(" ", lowered)
    return found


def _window_problem(lowered: str, window: MatchWindow) -> str | None:
    """Every time the sentence states must be the assertion's; an implicit window is from kick-off."""
    stated = False
    differs = "Claim text states a time window that differs from its assertion"
    if _WINDOW_FIRST.search(lowered):
        stated = True
        if window.period != 1:
            return differs
    if _WINDOW_SECOND.search(lowered):
        stated = True
        if window.period != 2:
            return differs
    between = _WINDOW_BETWEEN.search(lowered)
    if between:
        stated = True
        if (window.from_ms, window.to_ms) != (
            int(between[1]) * _MINUTE_MS,
            int(between[2]) * _MINUTE_MS,
        ):
            return differs
    else:
        start = _WINDOW_FROM.search(lowered)
        if start:
            stated = True
            if window.from_ms != int(start[1]) * _MINUTE_MS:
                return differs
        end = _WINDOW_TO.search(lowered)
        if end:
            stated = True
            if window.to_ms != int(end[1]) * _MINUTE_MS:
                return differs
        clock = _WINDOW_TO_CLOCK.search(lowered)
        if clock:
            stated = True
            if window.to_ms != (int(clock[1]) * 60 + int(clock[2])) * 1000:
                return differs
    last = _WINDOW_LAST.search(lowered)
    if last:
        stated = True
        if window.to_ms - window.from_ms != int(last[1]) * _MINUTE_MS:
            return differs
    if not stated and (window.period is not None or window.from_ms != 0):
        return "Claim text does not state its time window"
    return None


def _clock_text(ms: int) -> str:
    """The mm:ss a reader sees for a match clock."""
    seconds = ms // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _team_of(player_id: str, events: Sequence[MatchEvent]) -> str | None:
    """A player's team, read from the events they appear in."""
    for event in events:
        if event.player_id == player_id:
            return event.team_id
    return None


def _team_problem(
    lowered: str, team: str | None, names: Mapping[str, str], teams: Sequence[str]
) -> str | None:
    """The sentence may name only its subject's own team."""
    for team_id in teams:
        name = names.get(team_id)
        if name and team_id != team and _names_subject(lowered, name):
            return "Claim text names a team the claim is not about"
    return None


def _scoring_shot(goal: MatchEvent, events: Sequence[MatchEvent]) -> MatchEvent | None:
    """The shot a goal was scored from: the scorer's goal-bound shot logged just before it."""
    for event in events:
        if (
            event.sequence == goal.sequence - 1
            and event.type == "shot"
            and event.outcome == "goal"
            and event.player_id == goal.player_id
        ):
            return event
    return None


def _fact_problem(
    claim: Claim,
    lowered: str,
    events: Sequence[MatchEvent],
    names: Mapping[str, str] | None = None,
) -> str | None:
    """Clock times, minutes and details in an event fact must be those of its cited events."""
    fact = claim.fact
    if fact is None:
        return None
    by_id = {event.event_id: event for event in events}
    cited = [by_id[i] for i in (fact.from_event_id, fact.event_id) if i is not None and i in by_id]
    if not cited:
        return None
    clocks = {_clock_text(event.match_clock_ms) for event in cited}
    for found in _CLOCK.findall(lowered):
        if found.zfill(5) not in clocks:
            return "Claim text states a time that differs from its cited events"
    minutes = set()
    for event in cited:
        minutes.update({event.match_clock_ms // _MINUTE_MS, event.match_clock_ms // _MINUTE_MS + 1})
    for found in _FACT_MINUTE.findall(_CLOCK.sub(" ", lowered)):
        if int(found) not in minutes:
            return "Claim text states a time that differs from its cited events"
    tags = {tag for event in cited for tag in event.tags}
    for event in cited:
        shot = _scoring_shot(event, events) if event.type == "goal" else None
        if shot is not None:
            tags.update(shot.tags)
    for detail, words in _DETAILS:
        if re.search(_B + r"(?:" + words + r")" + _E, lowered) and detail not in tags:
            if not (detail == "corner" and fact.from_tag == "corner"):
                return "Claim text states a detail the event log does not record"
    if fact.query == "goal_scorer.v1" and not _GOAL_WORDS.search(lowered):
        return "Claim text does not say this was a goal"
    target = by_id.get(fact.event_id)
    if fact.query == "card.v1" and target is not None:
        if not _CARD_WORDS.search(lowered):
            return "Claim text does not say this was a card"
        says_red = _RED_WORDS.search(lowered) is not None
        says_yellow = _YELLOW_WORDS.search(lowered) is not None
        # A yellow must read as a yellow; a red or second yellow must read as a sending-off.
        if target.outcome == "yellow" and (says_red or not says_yellow):
            return "Claim text states a card colour the event log does not record"
        if target.outcome == "red" and (says_yellow or not says_red):
            return "Claim text states a card colour the event log does not record"
        if target.outcome == "second_yellow" and not says_red:
            return "Claim text states a card colour the event log does not record"
    if fact.query == "substitution.v1" and target is not None:
        if not _SUB_WORDS.search(lowered):
            return "Claim text does not say this was a substitution"
        incoming = names.get(target.related_player_id or "") if names else None
        if incoming is None or not _names_subject(lowered, incoming):
            return "Claim text does not name the incoming player"
    return None


def text_binding_problem(
    claim: Claim,
    names: Mapping[str, str] | None = None,
    events: Sequence[MatchEvent] = (),
) -> str | None:
    """Return why the sentence does not match its structured claim, or None if it does.

    With ``names`` the reader-facing rules in the module docstring also apply; ``events``
    are the accepted events, used for teams, clock times and tags.
    """
    expected = _expected_quantity(claim)
    if expected is not None:
        kind, value = expected
        stated = stated_quantities(claim.text)
        found = stated.counts if kind == "count" else stated.percents
        if any(quantity != value for quantity in found):
            return "Claim text states a quantity that differs from its assertion"
        if names is not None and value not in found:
            return "Claim text does not state the asserted value"
    if names is not None:
        subject = _subject_id(claim)
        if subject is not None:
            name = names.get(subject)
            if name is None:
                return "Claim subject has no registered display name"
            if not _names_subject(claim.text, name):
                return "Claim text does not name the asserted subject"
    if names is None:
        return None
    lowered = _lower(claim.text)
    teams = sorted({event.team_id for event in events if event.team_id is not None})
    if _NEGATION.search(lowered):
        return "Claim text negates its statement; negative claims are not checked"
    if claim.assertion is not None:
        assertion = claim.assertion
        named = _metrics_named(lowered)
        if assertion.metric not in named:
            return "Claim text does not name the asserted statistic"
        if len(named) > 1:
            return "Claim text names a statistic other than the asserted one"
        asserted = assertion.subject
        team = asserted.team_id or (
            _team_of(asserted.player_id, events) if asserted.player_id else None
        )
        problem = _team_problem(lowered, team, names, teams) or _window_problem(
            lowered, assertion.window
        )
        if problem is not None:
            return problem
        for _detail, words in _DETAILS:
            if re.search(_B + r"(?:" + words + r")" + _E, lowered):
                return "Claim text states a detail the registered metric does not measure"
        return None
    if claim.fact is not None:
        by_id = {event.event_id: event for event in events}
        target = by_id.get(claim.fact.event_id)
        problem = _team_problem(lowered, target.team_id if target else None, names, teams)
        return problem or _fact_problem(claim, lowered, events, names)
    return None
