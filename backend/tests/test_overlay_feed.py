"""The timed overlay feed: every figure on screen comes from a claim the verifier passed."""

import json
import re
from pathlib import Path

from matchdesk.domain.overlay_feed import LANGUAGES, OVERLAY_SCHEMA, PERSONAS, build_overlay_feed

FEED = build_overlay_feed()
CLAIMS = {claim["claim_id"]: claim for claim in FEED["claims"]}


def test_cues_are_timed_ordered_and_inside_the_replay() -> None:
    """A renderer can play the cues in order without sorting them itself."""
    times = [cue["t_ms"] for cue in FEED["cues"]]
    assert times == sorted(times)
    assert all(0 <= t <= FEED["replay_end_ms"] for t in times)
    assert [cue["cue_id"] for cue in FEED["cues"]] == [
        f"Q-{n:03d}" for n in range(1, len(times) + 1)
    ]
    assert FEED["schema"] == OVERLAY_SCHEMA and FEED["synthetic"] is True


def test_every_cue_has_every_persona_and_language() -> None:
    """Analyst, fan and caption versions in English, Spanish and French, none empty."""
    for cue in FEED["cues"]:
        for persona in PERSONAS:
            for language in LANGUAGES:
                assert cue["text"][persona][language].strip(), (cue["cue_id"], persona, language)


def test_numeric_cues_are_verified_and_logged_cues_say_so() -> None:
    """Goals, stats, the spell and the spotlight are verified; cards and changes are logged."""
    kinds = {cue["kind"]: cue["status"] for cue in FEED["cues"]}
    assert kinds["goal"] == kinds["stats"] == kinds["spell"] == kinds["spotlight"] == "verified"
    assert kinds["card"] == kinds["substitution"] == "logged"
    for cue in FEED["cues"]:
        statuses = {CLAIMS[claim_id]["status"] for claim_id in cue["claim_ids"]}
        assert statuses <= {"verified"}, cue["cue_id"]
        assert bool(cue["claim_ids"]) == (cue["status"] == "verified")


def test_goal_cues_show_the_verified_scorer_and_score() -> None:
    """The 58th-minute cue names Okafor and the 2-1 its claims verified."""
    goal = next(cue for cue in FEED["cues"] if cue["kind"] == "goal" and cue["clock"] == "58:17")
    assert goal["players"] == ["nbr-09"] and goal["event_ids"] == ["E-1366"]
    assert goal["text"]["caption"]["en"] == "59′ GOAL · Okafor · NBR 2–1 RIV"
    texts = [CLAIMS[claim_id]["text"] for claim_id in goal["claim_ids"]]
    assert texts == [
        "Okafor scored for Northbridge at 58:17.",
        "Northbridge scored 2 goals up to 58:18.",
        "Riverside scored 1 goal up to 58:18.",
    ]


def test_stat_card_numbers_match_their_claims() -> None:
    """The percentage and shot counts on each card are the verified values, not new text."""
    for cue in (c for c in FEED["cues"] if c["kind"] == "stats"):
        possession, home_shots, away_shots = (CLAIMS[i]["text"] for i in cue["claim_ids"])
        share = re.search(r"(\d+)%", possession)
        shots = [re.search(r"had (\d+) shot", text) for text in (home_shots, away_shots)]
        assert share and all(shots)
        caption = cue["text"]["caption"]["en"]
        assert caption.startswith(f"POSS {share[1]}–{100 - int(share[1])}")
        assert caption.endswith(f"SHOTS {shots[0][1]}–{shots[1][1]}")  # type: ignore[index]


def test_the_published_feed_file_is_current() -> None:
    """The downloadable copy in the studio is exactly this feed."""
    path = (
        Path(__file__).resolve().parents[2] / "apps/web/src/studio/generated/nbr-riv-overlays.json"
    )
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(json.dumps(FEED))
