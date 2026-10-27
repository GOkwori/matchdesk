"""Phase 1 regression probes: a verified claim means its sentence is true, not only its number.

Each case here was reproduced against the earlier verifier, which returned "verified"
for every wrong sentence below because it never read the claim text.
"""

from decimal import Decimal

import pytest
from matchdesk.domain import canonical_match as canonical
from matchdesk.domain.claim_text import stated_quantities
from matchdesk.domain.demo_claims import DISPLAY_NAMES, evidence_record, replay_window
from matchdesk.domain.models import Claim, EventFact, MatchWindow, MetricAssertion, Subject
from matchdesk.domain.verification import verify_claim

LOG = canonical.generate_canonical_match()
EVIDENCE = evidence_record(LOG)
OKAFOR = Subject(team_id=canonical.HOME, player_id="nbr-09")


def _goals(text: str, *, value: float = 2, cites=("E-0688", "E-1366"), to_ms=None) -> Claim:
    """An Okafor goal-count claim with the given sentence."""
    window = replay_window() if to_ms is None else MatchWindow(from_ms=0, to_ms=to_ms)
    return Claim(
        claim_id="P",
        text=text,
        kind="measured_stat",
        assertion=MetricAssertion(
            metric="goals.v1", subject=OKAFOR, window=window, value=value, unit="count"
        ),
        evidence_event_ids=cites,
    )


def _verify(claim: Claim, names=DISPLAY_NAMES):
    """Verify against the canonical log with the demo's display names."""
    return verify_claim(claim, EVIDENCE, LOG, names=names)


def test_true_sentence_is_verified() -> None:
    """The baseline: the right words with the right number pass."""
    assert _verify(_goals("Okafor scored both Northbridge goals.")).status == "verified"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Okafor scored a hat-trick.", "states a quantity that differs"),
        ("Okafor scored three goals.", "states a quantity that differs"),
        ("Lindqvist scored twice for Riverside.", "does not name the asserted subject"),
        ("Okafor was on the scoresheet.", "does not state the asserted value"),
    ],
)
def test_wrong_sentence_with_a_true_assertion_is_sent_back(text: str, reason: str) -> None:
    """The structured claim is true, the sentence is not: it must not verify."""
    result = _verify(_goals(text))
    assert result.status == "needs_revision"
    assert result.query_id == "claim-text-binding-v1"
    assert reason in result.reason
    # The metric itself was recomputed and agreed; only the words failed.
    assert result.observed == 2.0


def test_contradicting_quantity_fails_even_without_display_names() -> None:
    """A sentence may never state a number its own assertion contradicts."""
    result = verify_claim(_goals("Okafor scored a hat-trick."), EVIDENCE, LOG)
    assert result.status == "needs_revision"
    assert "differs" in result.reason


def test_citing_an_event_the_metric_does_not_count_is_sent_back() -> None:
    """A kick-off cannot be evidence for a goal count."""
    result = _verify(_goals("Okafor scored both goals.", cites=("E-0002",)))
    assert result.status == "needs_revision"
    assert result.reason == "Claim cites events the registered metric does not count"


def test_claim_cannot_speak_past_the_evidence_window() -> None:
    """At 67:12 nobody can verify how the full 90 minutes ended."""
    result = _verify(_goals("Okafor finished with two goals.", to_ms=90 * 60_000))
    assert result.status == "blocked"
    assert result.query_id == "evidence-window-v1"


def test_percentages_are_bound_to_the_asserted_ratio() -> None:
    """A possession claim must state the share it asserts, at its precision."""

    def possession(text: str) -> Claim:
        """A 58% Northbridge possession claim with the given sentence."""
        return Claim(
            claim_id="P",
            text=text,
            kind="measured_stat",
            assertion=MetricAssertion(
                metric="possession_time.v1",
                subject=Subject(team_id=canonical.HOME),
                window=replay_window(),
                value=0.58,
                unit="ratio",
                decimals=2,
            ),
            evidence_event_ids=("E-0001",),
        )

    assert _verify(possession("Northbridge have had 58% possession.")).status == "verified"
    assert _verify(possession("Northbridge have had 60% possession.")).status == "needs_revision"
    assert _verify(possession("Northbridge dominated the ball.")).status == "needs_revision"


def _fact(text: str, fact: EventFact, cites=("E-1359", "E-1366")) -> Claim:
    """An event-fact claim with a registered query."""
    return Claim(claim_id="F", text=text, kind="event_fact", fact=fact, evidence_event_ids=cites)


def test_goal_scorer_fact_is_checked_against_the_goal_event() -> None:
    """A true scorer verifies; a wrong scorer does not."""
    right = EventFact(query="goal_scorer.v1", event_id="E-1366", player_id="nbr-09")
    wrong = EventFact(query="goal_scorer.v1", event_id="E-1366", player_id="nbr-04")
    assert _verify(_fact("Okafor headed in at 58:17.", right, ("E-1366",))).status == "verified"
    assert _verify(_fact("Mensah headed in at 58:17.", wrong, ("E-1366",))).status == (
        "needs_revision"
    )


def test_corner_to_goal_gap_is_recomputed() -> None:
    """The fan story's "goal 14 seconds after the corner" is a computed check."""

    def gap(seconds: int, tag: str = "corner") -> EventFact:
        """The corner-to-goal sequence before Okafor's header."""
        return EventFact(
            query="sequence_gap.v1",
            event_id="E-1366",
            from_event_id="E-1359",
            from_tag=tag,
            gap_seconds=seconds,
        )

    assert _verify(_fact("The goal came 14 seconds after the corner.", gap(14))).status == (
        "verified"
    )
    assert _verify(_fact("The goal came 15 seconds after the corner.", gap(15))).status == (
        "needs_revision"
    )
    assert _verify(_fact("The goal came 14 seconds after it.", gap(14, "free_kick"))).status == (
        "needs_revision"
    )
    uncited = _verify(_fact("The goal came 14 seconds after the corner.", gap(14), ("E-1366",)))
    assert uncited.status == "blocked"


def test_unregistered_event_facts_still_cannot_verify() -> None:
    """Season history is not in the log, so "first brace of the season" stays unverified."""
    claim = Claim(
        claim_id="CL-0216",
        text="It is Okafor's first brace of the season.",
        kind="event_fact",
        evidence_event_ids=("E-0688", "E-1366"),
    )
    assert _verify(claim).query_id == "event-fact-semantic-v1"


@pytest.mark.parametrize(
    ("text", "counts", "percents"),
    [
        ("Okafor scored at 58:17 to make it 2-1.", (), ()),
        ("In the 58th minute, 58' and 34′, Northbridge led.", (), ()),
        ("Northbridge have had 57.5 per cent possession.", (), (Decimal("57.5"),)),
        ("Okafor scored both goals from 3 shots.", (Decimal(3), Decimal(2)), ()),
        ("Okafor's brace", (Decimal(2),), ()),
    ],
)
def test_quantity_extraction_ignores_clocks_minutes_and_scorelines(text, counts, percents) -> None:
    """Only stated quantities are compared; times and scores are not quantities."""
    stated = stated_quantities(text)
    assert stated.counts == counts
    assert stated.percents == percents


def test_record_identifiers_in_a_sentence_are_not_quantities() -> None:
    """E-1366 or nbr-09 name a record; reading them as numbers failed a true live claim."""
    from matchdesk.domain.claim_text import stated_quantities

    stated = stated_quantities("Okafor (nbr-09) scored E-1366, 14 seconds after CL-0214.")
    assert stated.counts == (Decimal(14),)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Okafor took 2 shots.", "Claim text does not name the asserted statistic"),
        ("Okafor scored 2 goals from 2 attempts.", "names a statistic other than the asserted"),
        ("Okafor did not score 2 goals.", "negates its statement"),
        ("Okafor hasn't scored 2 goals.", "negates its statement"),
        ("Okafor scored 2 goals for Riverside.", "names a team the claim is not about"),
        ("Okafor scored 2 goals in the first half.", "time window that differs"),
        ("Okafor scored 2 goals in the 2nd half.", "time window that differs"),
        ("Okafor scored 2 goals before 40'.", "time window that differs"),
        ("Okafor scored 2 goals since 10'.", "time window that differs"),
        ("Okafor scored 2 goals, both penalties.", "detail the registered metric does not measure"),
        ("Okafor scored 2 headers.", "detail the registered metric does not measure"),
    ],
)
def test_reader_facing_sentence_must_say_only_what_was_checked(text: str, reason: str) -> None:
    """Metric word, negation, team, window and detail are all bound to the assertion."""
    result = _verify(_goals(text))
    assert result.status == "needs_revision"
    assert reason in result.reason


@pytest.mark.parametrize(
    "text",
    [
        "Okafor scored 2 goals.",
        "Okafor scored 2 goals up to 67:12.",
        "Okafor has a brace.",
        "Okafor netted twice for Northbridge.",
    ],
)
def test_reader_facing_sentence_that_matches_is_verified(text: str) -> None:
    """Plain phrasings of the asserted statistic over its own window still verify."""
    assert _verify(_goals(text)).status == "verified"


def test_a_stated_window_must_be_the_asserted_one() -> None:
    """A half must be stated when asserted, and a partial window must say where it ends."""
    half = MatchWindow(period=2, from_ms=canonical.SECOND_HALF_MS, to_ms=4_032_000)
    claim = _goals("Okafor scored 1 goal in the second half.", value=1, cites=("E-1366",))
    claim = claim.model_copy(
        update={"assertion": claim.assertion.model_copy(update={"window": half})}
    )
    assert _verify(claim).status == "verified"
    unstated = claim.model_copy(update={"text": "Okafor scored 1 goal."})
    assert "does not state its time window" in _verify(unstated).reason
    early = _goals("Okafor scored 1 goal before 40'.", value=1, cites=("E-0688",), to_ms=2_400_000)
    assert _verify(early).status == "verified"
    assert _verify(early.model_copy(update={"text": "Okafor scored 1 goal."})).status == "verified"


@pytest.mark.parametrize(
    ("text", "event_id", "status"),
    [
        ("Okafor scored at 58:17.", "E-1366", "verified"),
        ("Okafor scored in the 59th minute.", "E-1366", "verified"),
        ("Okafor headed in at 58:17.", "E-1366", "verified"),
        ("Okafor scored at 34:18.", "E-1366", "needs_revision"),
        ("Okafor scored in the 70th minute.", "E-1366", "needs_revision"),
        ("Okafor headed in at 34:18.", "E-0688", "needs_revision"),
        ("Okafor scored a penalty at 58:17.", "E-1366", "needs_revision"),
        ("Okafor was there at 58:17.", "E-1366", "needs_revision"),
        ("Okafor scored for Riverside at 58:17.", "E-1366", "needs_revision"),
    ],
)
def test_event_fact_sentence_is_bound_to_its_event(text: str, event_id: str, status: str) -> None:
    """Clock, minute, recorded detail, goal wording and team must match the cited goal."""
    fact = EventFact(query="goal_scorer.v1", event_id=event_id, player_id="nbr-09")
    assert _verify(_fact(text, fact, (event_id,))).status == status
