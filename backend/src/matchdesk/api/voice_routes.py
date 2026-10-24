"""GET /api/voice/{kind}/{item}: a verified story, recap or overlay read aloud by Azure AI Speech.

Mounted only when the host switches it on (MATCHDESK_VOICE_ENABLED=true) and names the Speech
resource (SPEECH_RESOURCE_ID, the Foundry account's resource ID). The API's managed identity
signs in with Microsoft Entra ID; there are no keys. Only items from the verified feeds can be
voiced, each clip is cached in memory once made, and new clips are capped per hour and per day,
so cost stays at pennies. The studio falls back to the device's own voice when this is absent.
"""

from __future__ import annotations

import asyncio
import os
import time
import urllib.error
import urllib.request
from collections import OrderedDict, deque
from collections.abc import Callable
from importlib import import_module
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from matchdesk.api.telemetry import tracer
from matchdesk.domain.voice import ssml, voice_text

_ENV_ENABLED = "MATCHDESK_VOICE_ENABLED"
OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
CACHE_CLIPS = 256
NEW_PER_HOUR = 60
NEW_PER_DAY = 400
TIMEOUT_SECONDS = 15
SCOPE = "https://cognitiveservices.azure.com/.default"

Synthesize = Callable[[str], bytes]


class VoiceUnavailable(Exception):
    """Speech could not make the clip (sign-in, network, quota or a refusal)."""


class _Budget:
    """New clips allowed in a rolling hour and day; cached clips are free."""

    def __init__(self, per_hour: int, per_day: int) -> None:
        """No clips made yet."""
        self.per_hour, self.per_day = per_hour, per_day
        self.made: deque[float] = deque()

    def take(self, now: float) -> bool:
        """Spend one new clip if the budget allows."""
        while self.made and now - self.made[0] > 86_400:
            self.made.popleft()
        last_hour = sum(1 for t in self.made if now - t <= 3_600)
        if len(self.made) >= self.per_day or last_hour >= self.per_hour:
            return False
        self.made.append(now)
        return True


def azure_synthesizer(resource_id: str, endpoint: str) -> Synthesize:
    """Synthesis through Azure AI Speech, signed in as the host's managed identity.

    The Foundry account's custom domain serves text to speech; Entra tokens are passed as
    ``aad#<resource id>#<token>``. Both documented paths are tried once, and the one that
    answers is kept.
    """
    identity = import_module("azure.identity")
    credential = identity.DefaultAzureCredential(exclude_interactive_browser_credential=True)
    paths = ["/tts/cognitiveservices/v1", "/cognitiveservices/v1"]

    def synthesize(markup: str) -> bytes:
        """POST the markup and return the MP3 bytes."""
        token = credential.get_token(SCOPE).token
        last: Exception | None = None
        for path in list(paths):
            request = urllib.request.Request(
                endpoint.rstrip("/") + path,
                data=markup.encode("utf-8"),
                method="POST",
                headers={
                    "Authorization": f"Bearer aad#{resource_id}#{token}",
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
                    "User-Agent": "matchdesk-voice",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
                    audio: bytes = response.read()
                if paths[0] != path:
                    paths.remove(path)
                    paths.insert(0, path)
                return audio
            except urllib.error.HTTPError as error:
                last = error
                if error.code != 404:
                    break
            except OSError as error:
                last = error
                break
        raise VoiceUnavailable(type(last).__name__ if last else "no answer")

    return synthesize


def create_voice_router(
    synthesize: Synthesize,
    *,
    per_hour: int = NEW_PER_HOUR,
    per_day: int = NEW_PER_DAY,
    clock: Callable[[], float] = time.monotonic,
) -> APIRouter:
    """The voice routes, with their own clip cache and budget."""
    router = APIRouter()
    cache: OrderedDict[str, bytes] = OrderedDict()
    budget = _Budget(per_hour, per_day)
    lock = asyncio.Lock()

    @router.get("/api/voice/status")
    async def status() -> dict[str, Any]:
        """Whether voiced clips are available, for the studio to choose its voice."""
        return {"enabled": True, "provider": "Azure AI Speech", "cached": len(cache)}

    @router.get("/api/voice/{kind}/{item}", response_model=None)
    async def voice(
        kind: str,
        item: str,
        persona: str = Query(default="fan"),
        lang: str = Query(default="en"),
    ) -> Response:
        """One verified item read aloud, as MP3."""
        text = voice_text(kind, item, persona, lang)
        if text is None:
            return JSONResponse(
                status_code=404, content={"detail": "Nothing to read for that item"}
            )
        markup = ssml(text, lang)
        headers = {"Cache-Control": "public, max-age=86400", "X-Voice": "Azure AI Speech"}
        if markup in cache:
            cache.move_to_end(markup)
            return Response(cache[markup], media_type="audio/mpeg", headers=headers)
        async with lock:
            if markup not in cache:
                if not budget.take(clock()):
                    return JSONResponse(
                        status_code=429, content={"detail": "The voice is resting; try again later"}
                    )
                with tracer.start_as_current_span("matchdesk.voice.synthesize") as span:
                    span.set_attribute("matchdesk.voice.kind", kind)
                    span.set_attribute("matchdesk.voice.lang", lang)
                    span.set_attribute("matchdesk.voice.characters", len(text))
                    try:
                        audio = await asyncio.to_thread(synthesize, markup)
                    except VoiceUnavailable as error:
                        span.set_attribute("matchdesk.voice.error", str(error))
                        return JSONResponse(
                            status_code=503, content={"detail": "The voice is unavailable"}
                        )
                cache[markup] = audio
                while len(cache) > CACHE_CLIPS:
                    cache.popitem(last=False)
        return Response(cache[markup], media_type="audio/mpeg", headers=headers)

    return router


def voice_router_from_env() -> APIRouter | None:
    """The router when the host switches voice on and names the Speech resource, else None."""
    if os.environ.get(_ENV_ENABLED, "").lower() != "true":
        return None
    resource_id = os.environ.get("SPEECH_RESOURCE_ID", "").strip()
    project = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not resource_id or not project:
        return None
    account = project.removeprefix("https://").split(".", 1)[0]
    endpoint = f"https://{account}.cognitiveservices.azure.com"
    return create_voice_router(azure_synthesizer(resource_id, endpoint))
