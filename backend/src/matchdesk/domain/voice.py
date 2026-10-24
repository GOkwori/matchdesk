"""The texts the studio may read aloud, and the speech markup for each.

Only verified, published-by-design texts can be voiced: a fan story or recap in a persona and
language, or a timed overlay cue. The caller names the item; it never sends text, so the
voice endpoint cannot be used to speak arbitrary words.
"""

from __future__ import annotations

import re
from functools import cache
from typing import Any, Literal
from xml.sax.saxutils import escape

from matchdesk.domain.overlay_feed import LANGUAGES, PERSONAS, build_overlay_feed
from matchdesk.domain.recap_feed import build_recap_feed
from matchdesk.domain.story_feed import build_story_feed

Kind = Literal["story", "recap", "cue"]
KINDS: tuple[Kind, ...] = ("story", "recap", "cue")

# Azure AI Speech neural voices, one per language the studio speaks.
VOICES: dict[str, tuple[str, str]] = {
    "en": ("en-GB", "en-GB-RyanNeural"),
    "es": ("es-ES", "es-ES-AlvaroNeural"),
    "fr": ("fr-FR", "fr-FR-HenriNeural"),
}


@cache
def _feeds() -> dict[str, Any]:
    """The three feeds, built once per process."""
    return {
        "story": build_story_feed(),
        "recap": build_recap_feed(),
        "cue": build_overlay_feed(),
    }


def voice_text(kind: str, item: str, persona: str, lang: str) -> str | None:
    """The sentence(s) to read for one item, or None if there is no such item."""
    if kind not in KINDS or persona not in PERSONAS or lang not in LANGUAGES:
        return None
    feeds = _feeds()
    if kind == "story":
        story = next(
            (s for s in feeds["story"]["stories"] if item in (s["slug"], s["event_id"])), None
        )
        if story is None:
            return None
        text = story["text"][persona][lang]
        # The headline's minute mark is for the screen; the body says when it happened.
        headline = re.sub(r"^[0-9]+′ · ", "", text["headline"])
        return f"{headline}. {text['body']}"
    if kind == "recap":
        recap = next((r for r in feeds["recap"]["recaps"] if r["id"] == item), None)
        if recap is None:
            return None
        text = recap["text"][persona][lang]
        # The fan recap's body opens with the score; other styles need their headline.
        return str(text["body"]) if persona == "fan" else f"{text['headline']}. {text['body']}"
    cue = next((c for c in feeds["cue"]["cues"] if c["cue_id"] == item), None)
    if cue is None or cue["status"] != "verified":
        return None
    return str(cue["text"][persona][lang])


def ssml(text: str, lang: str) -> str:
    """Speech markup for one text in its language's voice, read at a steady pace."""
    locale, voice = VOICES[lang]
    # Separators the screen uses read better as pauses; minute marks as minutes.
    spoken = text.replace(" · ", ". ").replace("′", "")
    return (
        f"<speak version='1.0' xml:lang='{locale}'>"
        f"<voice name='{voice}'><prosody rate='-4%'>{escape(spoken)}</prosody></voice>"
        "</speak>"
    )
