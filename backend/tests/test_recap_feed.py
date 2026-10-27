"""Match recaps: half-time and the replay point, every figure checked by the verifier."""

import re

from matchdesk.domain.overlay_feed import LANGUAGES, PERSONAS
from matchdesk.domain.recap_feed import RECAP_SCHEMA, build_recap_feed

FEED = build_recap_feed()
CLAIMS = {claim["claim_id"]: claim for claim in FEED["claims"]}
RECAPS = {recap["id"]: recap for recap in FEED["recaps"]}


def _cited(recap: dict) -> list[str]:
    """Every claim a recap's checks and milestones rely on."""
    return [i for c in recap["checks"] for i in c["claim_ids"]] + [
        i for m in recap["milestones"] for i in m["claim_ids"]
    ]


def test_two_recaps_with_every_claim_verified() -> None:
    """Half-time and the replay point; nothing unverified behind either."""
    assert FEED["schema"] == RECAP_SCHEMA and FEED["synthetic"] is True
    assert list(RECAPS) == ["half-time", "latest"]
    for recap in FEED["recaps"]:
        for claim_id in _cited(recap):
            assert CLAIMS[claim_id]["status"] == "verified", (claim_id, CLAIMS[claim_id]["reason"])
            assert CLAIMS[claim_id]["claim"]["text"] == CLAIMS[claim_id]["text"]


def test_the_half_time_recap_covers_the_first_half_only() -> None:
    """1–1 at the break, both first-half goals, first-half windows in every claim."""
    half = RECAPS["half-time"]
    assert half["score"] == {"nbr": 1, "riv": 1} and half["clock"] == "45:00"
    assert [g["event_id"] for g in half["goals"]] == ["E-0688", "E-0790"]
    for check in half["checks"]:
        for claim_id in check["claim_ids"]:
            assertion = CLAIMS[claim_id]["claim"].get("assertion")
            if assertion:
                assert assertion["window"]["period"] == 1
                assert "in the first half" in CLAIMS[claim_id]["text"]
    assert all(m["t_ms"] < 2_700_000 for m in half["milestones"])


def test_the_latest_recap_has_the_score_goals_and_milestones() -> None:
    """2–1 at 67:12, three goals linked to their stories, the brace and the 10th shot."""
    latest = RECAPS["latest"]
    assert latest["score"] == {"nbr": 2, "riv": 1} and latest["clock"] == "67:12"
    assert [g["story"] for g in latest["goals"]] == [
        "okafor-opens-the-scoring",
        "lindqvist-equalises-for-riverside",
        "okafor-header-restores-northbridge-lead",
    ]
    labels = [m["label"]["en"] for m in latest["milestones"]]
    assert "Opening goal · Okafor" in labels and "Equaliser · Lindqvist" in labels
    assert "Lead restored · Okafor" in labels and "Okafor's brace" in labels
    assert "Northbridge's 10th shot" in labels
    assert latest["figures"]["shots"] == {"nbr": 14, "riv": 9}
    assert latest["figures"]["possession"] == {"nbr": 58, "riv": 42}


def test_every_persona_and_language_states_only_verified_figures() -> None:
    """Each number in each text is the score, a clock, or a verified figure."""
    for recap in FEED["recaps"]:
        f = recap["figures"]
        allowed = {
            *map(str, recap["score"].values()),
            *map(str, f["possession"].values()),
            *map(str, f["shots"].values()),
            *map(str, f["pass_accuracy"].values()),
            *(str(v) for v in f["synthetic_xg"].values()),
            *(str(v).replace(".", ",") for v in f["synthetic_xg"].values()),
            str(f["tackles_leader"]["tackles"]),
            *(g["clock"] for g in recap["goals"]),
            *(f"{int(g['clock'][:2]) + 1}" for g in recap["goals"]),
            recap["clock"],
        }
        for persona in PERSONAS:
            for lang in LANGUAGES:
                text = recap["text"][persona][lang]
                for number in re.findall(
                    r"\d+(?:[:.,]\d+)?", text["headline"] + " " + text["body"]
                ):
                    assert number in allowed, (recap["id"], persona, lang, number)


def test_spanish_and_french_use_decimal_commas() -> None:
    """Expected goals read 2,5 in Spanish and French, 2.5 in English."""
    latest = RECAPS["latest"]
    assert "2.5" in latest["text"]["fan"]["en"]["body"]
    assert "2,5" in latest["text"]["fan"]["es"]["body"]
    assert "2,5" in latest["text"]["fan"]["fr"]["body"]
