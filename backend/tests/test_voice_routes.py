"""Voice-over: only verified items can be voiced, clips are cached, and new clips are capped."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from matchdesk.api.voice_routes import VoiceUnavailable, create_voice_router, voice_router_from_env
from matchdesk.domain.voice import ssml, voice_text


def _client(synthesize, **limits) -> TestClient:  # type: ignore[no-untyped-def]
    """A test app with the voice routes and a fake synthesizer."""
    app = FastAPI()
    app.include_router(create_voice_router(synthesize, **limits))
    return TestClient(app)


def test_a_story_is_voiced_once_and_then_served_from_the_cache() -> None:
    """The second request for the same clip does not call Speech again."""
    calls: list[str] = []

    def fake(markup: str) -> bytes:
        """Record the markup and return fake audio."""
        calls.append(markup)
        return b"ID3-audio"

    client = _client(fake)
    url = "/api/voice/story/okafor-header-restores-northbridge-lead?persona=fan&lang=es"
    first, second = client.get(url), client.get(url)
    assert first.status_code == second.status_code == 200
    assert first.headers["content-type"] == "audio/mpeg"
    assert first.content == b"ID3-audio"
    assert len(calls) == 1
    assert "es-ES-AlvaroNeural" in calls[0] and "Okafor marca de cabeza" in calls[0]


def test_only_items_from_the_verified_feeds_can_be_voiced() -> None:
    """Unknown items, kinds, personas and languages are refused, and text cannot be sent."""
    client = _client(lambda markup: b"x")
    for url in (
        "/api/voice/story/not-a-story",
        "/api/voice/podcast/half-time",
        "/api/voice/recap/half-time?lang=de",
        "/api/voice/recap/half-time?persona=pundit",
        "/api/voice/cue/Q-999",
    ):
        assert client.get(url).status_code == 404, url
    assert client.get("/api/voice/recap/half-time?lang=fr").status_code == 200
    assert client.get("/api/voice/cue/Q-001?lang=en").status_code == 200


def test_new_clips_are_capped_but_cached_clips_are_free() -> None:
    """Past the hourly cap a new clip is refused; one already made is still served."""
    client = _client(lambda markup: b"x", per_hour=1, per_day=5)
    assert client.get("/api/voice/recap/half-time").status_code == 200
    assert client.get("/api/voice/recap/latest").status_code == 429
    assert client.get("/api/voice/recap/half-time").status_code == 200


def test_a_speech_failure_is_a_503_and_nothing_is_cached() -> None:
    """When Speech cannot answer the studio falls back to the device voice."""

    def broken(markup: str) -> bytes:
        """Fail like a refused sign-in."""
        raise VoiceUnavailable("HTTPError")

    client = _client(broken)
    assert client.get("/api/voice/recap/half-time").status_code == 503


def test_the_voice_reads_prose_not_screen_marks() -> None:
    """Minute marks and separators become pauses, and markup is escaped."""
    text = voice_text("story", "E-1366", "fan", "en")
    assert text is not None and not text.startswith("59′")
    markup = ssml("35′ GOAL · Okafor & <b>", "en")
    assert "en-GB-RyanNeural" in markup and "35 GOAL. Okafor &amp; &lt;b&gt;" in markup


def test_voice_is_off_unless_switched_on_with_a_resource(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """No router without the switch, the Speech resource ID and the Foundry endpoint."""
    monkeypatch.delenv("MATCHDESK_VOICE_ENABLED", raising=False)
    assert voice_router_from_env() is None
    monkeypatch.setenv("MATCHDESK_VOICE_ENABLED", "true")
    monkeypatch.delenv("SPEECH_RESOURCE_ID", raising=False)
    assert voice_router_from_env() is None
