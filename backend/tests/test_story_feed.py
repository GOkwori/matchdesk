"""Fan stories: one per goal, every fact in the text checked by the verifier."""

import json
import re
from pathlib import Path

from matchdesk.domain.overlay_feed import LANGUAGES, PERSONAS
from matchdesk.domain.story_feed import STORY_SCHEMA, build_story_feed

FEED = build_story_feed()
CLAIMS = {claim["claim_id"]: claim for claim in FEED["claims"]}
STORIES = {story["slug"]: story for story in FEED["stories"]}


def test_every_goal_has_one_story_and_the_existing_address_is_kept() -> None:
    """Three goals, three stories, in time order; the published 58′ address still works."""
    assert FEED["schema"] == STORY_SCHEMA and FEED["synthetic"] is True
    assert list(STORIES) == [
        "okafor-opens-the-scoring",
        "lindqvist-equalises-for-riverside",
        "okafor-header-restores-northbridge-lead",
    ]
    assert [story["event_id"] for story in FEED["stories"]] == ["E-0688", "E-0790", "E-1366"]


def test_every_check_behind_a_story_is_verified() -> None:
    """The scorer, the score, the tally and the lead-in all pass the verifier."""
    for story in FEED["stories"]:
        cited = [claim_id for check in story["checks"] for claim_id in check["claim_ids"]]
        assert len(cited) == 5
        for claim_id in cited:
            assert CLAIMS[claim_id]["status"] == "verified", (claim_id, CLAIMS[claim_id]["reason"])
            assert CLAIMS[claim_id]["claim"]["text"] == CLAIMS[claim_id]["text"]


def test_the_score_context_follows_the_running_score() -> None:
    """Opener, equaliser, then the lead restored, as the log has it."""
    contexts = [(story["context"], story["score"]["after"]) for story in FEED["stories"]]
    assert contexts == [
        ("opener", {"nbr": 1, "riv": 0}),
        ("equaliser", {"nbr": 1, "riv": 1}),
        ("lead_restored", {"nbr": 2, "riv": 1}),
    ]


def test_the_58th_minute_story_keeps_its_verified_details() -> None:
    """Header, corner 14 seconds earlier, Okafor's second goal, 2–1."""
    story = STORIES["okafor-header-restores-northbridge-lead"]
    assert story["header"] is True
    assert story["lead_in"] == {"kind": "corner", "event_id": "E-1359", "seconds": 14}
    fan = story["text"]["fan"]["en"]
    assert fan["headline"] == "59′ · Okafor restores the Northbridge lead"
    assert fan["body"] == (
        "Okafor heads in at 58:17, 14 seconds after a corner. "
        "It is Okafor's second goal of the match. It's 2–1."
    )
    assert "d'Okafor" in story["text"]["fan"]["fr"]["body"]


def test_numbers_in_the_text_match_the_verified_claims() -> None:
    """Every score and gap the text states is the value its claim verified."""
    for story in FEED["stories"]:
        home, away = story["score"]["after"]["nbr"], story["score"]["after"]["riv"]
        seconds = story["lead_in"]["seconds"]
        lead_in = CLAIMS[story["checks"][3]["claim_ids"][0]]
        assert f"{seconds} seconds" in lead_in["text"]
        for persona in PERSONAS:
            for language in LANGUAGES:
                text = story["text"][persona][language]
                assert text["headline"].strip() and text["body"].strip()
                scores = re.findall(r"(\d+)–(\d+)", text["headline"] + " " + text["body"])
                assert all((int(h), int(a)) == (home, away) for h, a in scores), (persona, language)


def test_the_build_up_is_the_scoring_team_from_the_lead_in_to_the_goal() -> None:
    """The diagram's events start at the lead-in event and end at the goal."""
    for story in FEED["stories"]:
        ids = [event["id"] for event in story["buildup"]]
        assert ids[0] == story["lead_in"]["event_id"] and ids[-1] == story["event_id"]
        times = [event["t_ms"] for event in story["buildup"]]
        assert times == sorted(times)


def test_the_published_story_file_is_current() -> None:
    """The studio's copy is exactly this feed."""
    path = (
        Path(__file__).resolve().parents[2] / "apps/web/src/studio/generated/nbr-riv-stories.json"
    )
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(json.dumps(FEED))
