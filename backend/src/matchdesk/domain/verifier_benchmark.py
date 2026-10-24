"""Try to fool the verifier: a benchmark of false sentences built from the claims the demo shows.

Every claim the overlays, recaps and stories show is verified. This module takes each one
and makes it wrong in one specific way, the way a fluent model gets a sentence wrong: a
number off by a little, the wrong player or team, the wrong half, a different statistic,
evidence that does not support it, a time past the replay point, the wrong scorer, card
colour, substitute or gap. Each false claim must not verify. The untouched claims, and
rewordings of them that a reader would accept, must verify. The result says how many false
claims were caught and how many true ones were wrongly sent back, per kind of error.

The cases are deterministic (no randomness), so the numbers are reproducible, and the
browser port of the verifier is checked against the same cases.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.demo_claims import DISPLAY_NAMES, REPLAY_END_MS, evidence_record
from matchdesk.domain.models import Claim, MatchEvent, round_half_up
from matchdesk.domain.verification import verify_claim

BENCHMARK_SCHEMA = "matchdesk-verifier-benchmark/1"

# The kinds of error, in the order the results list them, with a plain description.
CATEGORIES: dict[str, str] = {
    "wrong_number": "A wrong number, stated consistently in the sentence and its assertion",
    "number_mismatch": "The sentence states a different number from the one it asserts",
    "wrong_subject_named": "The sentence names the wrong player or team",
    "wrong_subject_asserted": "The claim is about a different player than the sentence names",
    "wrong_window": "The sentence states the wrong half, minute range or time",
    "wrong_statistic": "The sentence names a different statistic",
    "unsupported_evidence": "The claim cites events that do not support it, or do not exist",
    "past_replay_point": "The claim speaks about time the evidence does not cover",
    "wrong_scorer": "A goal credited to the wrong player",
    "wrong_card": "A card with the wrong colour, or the wrong player booked",
    "wrong_substitute": "A substitution with the players swapped or wrong",
    "wrong_gap": "A goal's build-up timed wrongly",
    "wrong_clock": "An event placed at the wrong time",
}
CONTROLS: dict[str, str] = {
    "original": "The claim as the demo shows it",
    "window_first": "Reworded with the time phrase first",
    "total_of": "Reworded with 'a total of'",
    "synonyms": "Reworded with number words and synonyms a reader would accept",
}
_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
_SYNONYMS: tuple[tuple[str, str], ...] = (
    (r"% possession", "% of the ball"),
    (r" up to ([0-9]{1,2}:[0-9]{2})", r" by \1"),
    (r"\bscored for\b", "netted for"),
    (r"\bhad ([0-9]+) shots\b", r"took \1 shots"),
    (r"\bmade ([0-9]+) tackles\b", r"won \1 tackles"),
)

_TEAMS = (canonical.HOME, canonical.AWAY)
_PLAYERS = sorted(canonical.PLAYER_NAMES)


@dataclass(frozen=True)
class Case:
    """One benchmark sentence: true (a control) or made wrong in one way."""

    name: str
    category: str
    truthful: bool
    claim: Claim
    note: str = ""


def _shown(value: float, unit: str, decimals: int | None) -> str:
    """How a value appears in a sentence (as the feeds write it)."""
    if unit == "ratio":
        return str(round_half_up(value * 100, max((decimals or 2) - 2, 0)))
    if unit == "count":
        return str(int(value))
    return str(round_half_up(value, decimals if decimals is not None else 1))


def _replace_number(text: str, old: str, new: str) -> str | None:
    """Replace the first standalone occurrence of a stated number, or None if absent."""
    pattern = re.compile(r"(?<![\d.])" + re.escape(old) + r"(?![\d])(?!\.\d)")
    if not pattern.search(text):
        return None
    return pattern.sub(new, text, count=1)


def _with(claim: Claim, **changes: Any) -> Claim:
    """A copy of a claim with fields changed, revalidated."""
    data = claim.model_dump(mode="json", exclude_none=True)
    data.update(changes)
    return Claim.model_validate(data)


def _with_assertion(claim: Claim, text: str | None = None, **changes: Any) -> Claim:
    """A copy with assertion fields changed (and optionally the text)."""
    assert claim.assertion is not None
    assertion = claim.assertion.model_dump(mode="json", exclude_none=True)
    assertion.update(changes)
    return _with(claim, assertion=assertion, **({"text": text} if text is not None else {}))


def _with_fact(claim: Claim, text: str | None = None, **changes: Any) -> Claim:
    """A copy with event-fact fields changed (and optionally the text)."""
    assert claim.fact is not None
    fact = claim.fact.model_dump(mode="json", exclude_none=True)
    fact.update(changes)
    return _with(claim, fact=fact, **({"text": text} if text is not None else {}))


def _deltas(unit: str, decimals: int | None, value: float) -> list[float]:
    """Small and larger errors in a value, at its stated precision."""
    if unit == "count":
        return [d for d in (1.0, -1.0, 2.0) if value + d >= 0]
    if unit == "ratio":
        step = 10 ** -(decimals or 2)
        return [d for d in (step, -step, 5 * step) if 0 <= value + d <= 1]
    step = 10 ** -(decimals if decimals is not None else 1)
    return [d for d in (step, -step, round(value * 0.1, 6) or step) if value + d >= 0]


def _other_player(player_id: str) -> str:
    """A different player on the same team, chosen deterministically."""
    side = player_id.split("-")[0]
    same = [p for p in _PLAYERS if p.startswith(side) and p != player_id]
    return same[len(player_id) % len(same)]


def _named(claim: Claim) -> tuple[str, str] | None:
    """The subject identity and the display name the sentence uses for it."""
    if claim.assertion is not None:
        subject = claim.assertion.subject
        identity = subject.player_id or subject.team_id
    elif claim.fact is not None:
        identity = claim.fact.player_id
    else:
        return None
    if identity is None:
        return None
    name = DISPLAY_NAMES.get(identity, identity)
    return (identity, name) if name in claim.text else None


_STAT_SWAPS: tuple[tuple[str, str], ...] = (
    (r"\bshots\b", "tackles"),
    (r"\bshot\b", "tackle"),
    (r"\bgoals\b", "shots"),
    (r"\bgoal\b", "shot"),
    (r"\btackles\b", "interceptions"),
    (r"\bpossession\b", "pass accuracy"),
    (r"\bexpected goals\b", "shots"),
    (r"\bof their passes\b", "of their shots"),
    (r"\btop speed\b", "shot speed"),
    (r"\bshot speed\b", "top speed"),
    (r"\bcovered\b", "sprinted"),
    (r"\bsprints\b", "tackles"),
    (r"\bsprint\b", "tackle"),
)


def _windows(text: str) -> Iterator[str]:
    """The sentence with its time phrase changed in each way it can be."""
    swaps = (
        (r"in the first half", "in the second half"),
        (r"in the second half", "in the first half"),
    )
    for old, new in swaps:
        if old in text:
            yield text.replace(old, new, 1)
    clock = re.search(r"up to ([0-9]{1,2}):([0-9]{2})", text)
    if clock:
        minute = int(clock.group(1))
        shifted = minute - 5 if minute >= 10 else minute + 5
        yield text.replace(clock.group(0), f"up to {shifted}:{clock.group(2)}", 1)
    between = re.search(r"between ([0-9]{1,3})′ and ([0-9]{1,3})′", text)
    if between:
        start, end = int(between.group(1)), int(between.group(2))
        yield text.replace(between.group(0), f"between {start + 2}′ and {end + 2}′", 1)
    at = re.search(r"at ([0-9]{1,2}):([0-9]{2})", text)
    if at:
        minute = int(at.group(1))
        yield text.replace(at.group(0), f"at {minute - 1}:{at.group(2)}", 1)


def _metric_cases(claim: Claim, log: tuple[MatchEvent, ...]) -> Iterator[Case]:
    """False versions of one metric claim."""
    assert claim.assertion is not None
    a = claim.assertion
    shown = _shown(a.value, a.unit, a.decimals)
    for i, delta in enumerate(_deltas(a.unit, a.decimals, a.value)):
        wrong = round(a.value + delta, 6)
        if a.decimals is not None:
            wrong = float(round_half_up(wrong, a.decimals))
        if wrong == a.value:
            continue
        text = _replace_number(claim.text, shown, _shown(wrong, a.unit, a.decimals))
        if text is None or text == claim.text:
            continue
        yield Case(
            f"{claim.claim_id}/value{i}",
            "wrong_number",
            False,
            _with_assertion(claim, text=text, value=wrong),
        )
        yield Case(f"{claim.claim_id}/text{i}", "number_mismatch", False, _with(claim, text=text))
    named = _named(claim)
    if named:
        identity, name = named
        if identity in _TEAMS:
            other = DISPLAY_NAMES[_TEAMS[1 - _TEAMS.index(identity)]]
        else:
            other = DISPLAY_NAMES[_other_player(identity)]
        yield Case(
            f"{claim.claim_id}/name",
            "wrong_subject_named",
            False,
            _with(claim, text=claim.text.replace(name, other, 1)),
        )
        if a.subject.player_id:
            subject = {"player_id": _other_player(a.subject.player_id)}
            yield Case(
                f"{claim.claim_id}/subject",
                "wrong_subject_asserted",
                False,
                _with_assertion(claim, subject=subject),
                f"The claim is about {DISPLAY_NAMES[subject['player_id']]}",
            )
    for i, text in enumerate(_windows(claim.text)):
        yield Case(f"{claim.claim_id}/window{i}", "wrong_window", False, _with(claim, text=text))
    for old, new in _STAT_SWAPS:
        if re.search(old, claim.text):
            yield Case(
                f"{claim.claim_id}/stat",
                "wrong_statistic",
                False,
                _with(claim, text=re.sub(old, new, claim.text, count=1)),
            )
            break
    yield Case(
        f"{claim.claim_id}/ghost",
        "unsupported_evidence",
        False,
        _with(claim, evidence_event_ids=["E-9999"]),
        "It cites E-9999, which is not in the log",
    )
    if a.metric in ("shots.v1", "goals.v1") and a.value > 0:
        wrong_type = next(e.event_id for e in log if e.type == "pass")
        yield Case(
            f"{claim.claim_id}/cites",
            "unsupported_evidence",
            False,
            _with(claim, evidence_event_ids=[wrong_type]),
            f"It cites {wrong_type}, a pass, as its evidence",
        )
    window = a.window.model_dump(mode="json", exclude_none=True)
    window["to_ms"] = REPLAY_END_MS + 60_000
    yield Case(
        f"{claim.claim_id}/future",
        "past_replay_point",
        False,
        _with_assertion(claim, window=window),
        "Its window runs a minute past the replay point, 67:12",
    )


def _fact_cases(claim: Claim) -> Iterator[Case]:
    """False versions of one event-fact claim."""
    assert claim.fact is not None
    fact = claim.fact
    if fact.query == "goal_scorer.v1" and fact.player_id:
        other = _other_player(fact.player_id)
        text = claim.text.replace(DISPLAY_NAMES[fact.player_id], DISPLAY_NAMES[other], 1)
        yield Case(
            f"{claim.claim_id}/scorer",
            "wrong_scorer",
            False,
            _with_fact(claim, text=text, player_id=other),
        )
        yield Case(f"{claim.claim_id}/scorer-text", "wrong_scorer", False, _with(claim, text=text))
    if fact.query == "card.v1":
        text = claim.text.replace("was shown a yellow card", "was sent off", 1)
        if text == claim.text:
            text = claim.text.replace("was sent off", "was shown a yellow card", 1)
        yield Case(f"{claim.claim_id}/colour", "wrong_card", False, _with(claim, text=text))
        if fact.player_id:
            other = _other_player(fact.player_id)
            yield Case(
                f"{claim.claim_id}/booked",
                "wrong_card",
                False,
                _with_fact(
                    claim,
                    text=claim.text.replace(DISPLAY_NAMES[fact.player_id], DISPLAY_NAMES[other], 1),
                    player_id=other,
                ),
            )
    if fact.query == "substitution.v1":
        match = re.match(r"(.+?) replaced (.+?) for ", claim.text)
        if match:
            on, off = match.group(1), match.group(2)
            yield Case(
                f"{claim.claim_id}/swap",
                "wrong_substitute",
                False,
                _with(
                    claim,
                    text=claim.text.replace(f"{on} replaced {off}", f"{off} replaced {on}", 1),
                ),
            )
            if fact.player_id:
                other = DISPLAY_NAMES[_other_player(fact.player_id)]
                yield Case(
                    f"{claim.claim_id}/off",
                    "wrong_substitute",
                    False,
                    _with(claim, text=claim.text.replace(off, other, 1)),
                )
    if fact.query == "sequence_gap.v1" and fact.gap_seconds is not None:
        for i, delta in enumerate((3, -3, 10)):
            wrong = fact.gap_seconds + delta
            if wrong <= 0:
                continue
            gap_text = _replace_number(claim.text, str(fact.gap_seconds), str(wrong))
            if gap_text:
                yield Case(
                    f"{claim.claim_id}/gap{i}",
                    "wrong_gap",
                    False,
                    _with_fact(claim, text=gap_text, gap_seconds=wrong),
                )
    at = re.search(r"at ([0-9]{1,2}):([0-9]{2})", claim.text)
    if at:
        minute = int(at.group(1))
        yield Case(
            f"{claim.claim_id}/clock",
            "wrong_clock",
            False,
            _with(claim, text=claim.text.replace(at.group(0), f"at {minute - 1}:{at.group(2)}", 1)),
        )
    yield Case(
        f"{claim.claim_id}/ghost",
        "unsupported_evidence",
        False,
        _with(claim, evidence_event_ids=["E-9999"]),
    )


def _controls(claim: Claim) -> Iterator[Case]:
    """True claims: the original, and rewordings a reader would accept."""
    yield Case(f"{claim.claim_id}/original", "original", True, claim)
    if claim.assertion is None:
        return
    match = re.match(
        r"^(.+?) (in the (?:first|second) half|up to [0-9]{1,2}:[0-9]{2}|between [0-9]{1,3}′ and [0-9]{1,3}′)\.$",
        claim.text,
    )
    if match:
        phrase = match.group(2)
        yield Case(
            f"{claim.claim_id}/front",
            "window_first",
            True,
            _with(claim, text=f"{phrase[0].upper()}{phrase[1:]}, {match.group(1)}."),
        )
    total = re.sub(r"\b(had|made|scored) ([0-9]+) ", r"\1 a total of \2 ", claim.text, count=1)
    if total != claim.text:
        yield Case(f"{claim.claim_id}/total", "total_of", True, _with(claim, text=total))
    for i, (old, new) in enumerate(_SYNONYMS):
        text = re.sub(old, new, claim.text, count=1)
        if text != claim.text:
            yield Case(f"{claim.claim_id}/synonym{i}", "synonyms", True, _with(claim, text=text))
    a = claim.assertion
    if a.unit == "count" and int(a.value) < len(_WORDS):
        worded = _replace_number(claim.text, str(int(a.value)), _WORDS[int(a.value)])
        if worded and worded != claim.text:
            yield Case(f"{claim.claim_id}/word", "synonyms", True, _with(claim, text=worded))


def base_claims() -> list[Claim]:
    """Every verified claim the overlays, recaps and stories show, once each."""
    from matchdesk.domain.overlay_feed import build_overlay_feed
    from matchdesk.domain.recap_feed import build_recap_feed
    from matchdesk.domain.story_feed import build_story_feed

    seen: dict[str, Claim] = {}
    for feed in (build_overlay_feed(), build_recap_feed(), build_story_feed()):
        for record in feed["claims"]:
            if record["status"] == "verified" and record["claim_id"] not in seen:
                seen[record["claim_id"]] = Claim.model_validate(record["claim"])
    return [seen[key] for key in sorted(seen)]


def build_cases(log: tuple[MatchEvent, ...]) -> list[Case]:
    """The full benchmark: controls and false claims for every base claim."""
    cases: list[Case] = []
    for claim in base_claims():
        cases.extend(_controls(claim))
        make: Callable[..., Iterator[Case]] = _metric_cases if claim.assertion else _fact_cases
        cases.extend(make(claim, log) if claim.assertion else make(claim))
    return cases


def run_benchmark() -> dict[str, Any]:
    """Verify every case and summarise caught false claims and wrongly rejected true ones."""
    log = tuple(e for e in canonical.generate_canonical_match() if e.match_clock_ms < REPLAY_END_MS)
    evidence = evidence_record(log)
    cases = build_cases(log)
    rows = []
    for case in cases:
        result = verify_claim(case.claim, evidence, log, names=DISPLAY_NAMES)
        rows.append((case, result))
    by: dict[str, dict[str, Any]] = {}
    for case, result in rows:
        entry = by.setdefault(
            case.category, {"total": 0, "correct": 0, "statuses": {}, "missed": []}
        )
        entry["total"] += 1
        ok = (result.status == "verified") == case.truthful
        entry["correct"] += int(ok)
        entry["statuses"][result.status] = entry["statuses"].get(result.status, 0) + 1
        if not ok:
            entry["missed"].append(
                {"case": case.name, "text": case.claim.text, "reason": result.reason}
            )
    false_rows = [(c, r) for c, r in rows if not c.truthful]
    true_rows = [(c, r) for c, r in rows if c.truthful]
    caught = sum(r.status != "verified" for _, r in false_rows)
    rejected = sum(r.status != "verified" for _, r in true_rows)
    originals = {
        c.name.split("/")[0]: c.claim.text for c, _ in true_rows if c.category == "original"
    }
    examples = []
    for index, category in enumerate(CATEGORIES):
        # A different base claim for each kind of error, so the examples show variety.
        pool = [(c, r) for c, r in false_rows if c.category == category]
        sample = pool[(index * 37) % len(pool)] if pool else None
        if sample:
            examples.append(
                {
                    "category": category,
                    "text": sample[0].claim.text,
                    "note": sample[0].note,
                    "original": originals.get(sample[0].name.split("/")[0], ""),
                    "status": sample[1].status,
                    "reason": sample[1].reason,
                }
            )
    return {
        "schema": BENCHMARK_SCHEMA,
        "synthetic": True,
        "base_claims": len({c.name.split("/")[0] for c, _ in rows}),
        "false": {
            "total": len(false_rows),
            "caught": caught,
            "rate": round(caught / len(false_rows), 4) if false_rows else None,
        },
        "true": {
            "total": len(true_rows),
            "wrongly_rejected": rejected,
            "rate": round(rejected / len(true_rows), 4) if true_rows else None,
        },
        "categories": [
            {"id": key, "label": label, "truthful": False, **_public(by.get(key))}
            for key, label in CATEGORIES.items()
            if key in by
        ]
        + [
            {"id": key, "label": label, "truthful": True, **_public(by.get(key))}
            for key, label in CONTROLS.items()
            if key in by
        ],
        "examples": examples,
    }


def _public(entry: dict[str, Any] | None) -> dict[str, Any]:
    """A category's counts and any misses, for the published results."""
    entry = entry or {"total": 0, "correct": 0, "statuses": {}, "missed": []}
    return {
        "total": entry["total"],
        "correct": entry["correct"],
        "statuses": dict(sorted(entry["statuses"].items())),
        "missed": entry["missed"],
    }


def parity_cases() -> list[dict[str, Any]]:
    """Every case with the verdict the server gave, for the browser port to reproduce."""
    log = tuple(e for e in canonical.generate_canonical_match() if e.match_clock_ms < REPLAY_END_MS)
    evidence = evidence_record(log)
    out = []
    for case in build_cases(log):
        result = verify_claim(case.claim, evidence, log, names=DISPLAY_NAMES)
        out.append(
            {
                "name": case.name,
                "claim": case.claim.model_dump(mode="json", exclude_none=True),
                "status": result.status,
                "query_id": result.query_id,
            }
        )
    return out
