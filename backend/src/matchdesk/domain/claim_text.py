"""Bind a claim's sentence to its structured assertion.

The verifier recomputes the structured assertion. Without this module the sentence
beside it was never read, so "Okafor scored a hat-trick" with an assertion of two
goals came back verified. Two rules close that gap:

- Always: every quantity the sentence states must equal the asserted value.
- With a display-name registry: the sentence must also name its subject and state the
  asserted value, so the words a reader sees are the words that were checked.

Extraction is deliberately small and fails closed: ambiguous prose ("one of the two
goals") is sent back for revision rather than guessed at. The TypeScript port in
apps/web/src/studio/verifier.ts must reproduce it exactly; the parity fixture enforces it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from matchdesk.domain.models import Claim, round_half_up

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

TEXT_QUERY_ID = "claim-text-binding-v1"


@dataclass(frozen=True)
class StatedQuantities:
    """The counts and percentages a sentence states, in order of appearance."""

    counts: tuple[Decimal, ...]
    percents: tuple[Decimal, ...]


def stated_quantities(text: str) -> StatedQuantities:
    """Extract stated counts and percentages, ignoring clocks, scorelines and minutes."""
    lowered = text.lower().replace("’", "'")
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


def text_binding_problem(claim: Claim, names: Mapping[str, str] | None = None) -> str | None:
    """Return why the sentence does not match its structured claim, or None if it does."""
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
    return None
