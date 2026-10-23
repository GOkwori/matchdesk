"""GET /api/live/stream: the synthetic replay as server-sent events, verified as it arrives.

Mounted only when the host switches it on (MATCHDESK_LIVE_REPLAY_ENABLED=true). Read-only:
it streams a recording of the synthetic match through the ingestor, reducer and verifier.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse

from matchdesk.domain.demo_claims import REPLAY_END_MS
from matchdesk.domain.live_replay import SPEEDS, live_replay

MAX_LISTENERS = 16
_ENV_ENABLED = "MATCHDESK_LIVE_REPLAY_ENABLED"


class _Listeners:
    """A process-wide cap on open streams."""

    def __init__(self, limit: int) -> None:
        """No listeners yet."""
        self.limit = limit
        self.open = 0

    def try_enter(self) -> bool:
        """Take a place if one is free."""
        if self.open >= self.limit:
            return False
        self.open += 1
        return True

    def leave(self) -> None:
        """Give a place back."""
        self.open = max(0, self.open - 1)


def create_live_router(limit: int = MAX_LISTENERS) -> APIRouter:
    """The stream route, with its own listener cap."""
    router = APIRouter()
    listeners = _Listeners(limit)

    @router.get("/api/live/stream", response_model=None)
    async def stream(
        speed: int = Query(default=30),
        from_ms: int = Query(default=0, ge=0, lt=REPLAY_END_MS),
    ) -> StreamingResponse | JSONResponse:
        """Stream the replay from a point in the match at 1, 10, 30 or 60 times real time."""
        if speed not in SPEEDS:
            return JSONResponse(
                status_code=422, content={"detail": f"speed must be one of {SPEEDS}"}
            )
        if not listeners.try_enter():
            return JSONResponse(
                status_code=429, content={"detail": "Too many live viewers; try again shortly"}
            )
        started = time.monotonic()

        async def frames() -> AsyncIterator[str]:
            try:
                async for frame in live_replay(
                    speed, from_ms, sleep=asyncio.sleep, elapsed=lambda: time.monotonic() - started
                ):
                    yield frame
            finally:
                listeners.leave()

        return StreamingResponse(
            frames(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    return router


def live_router_from_env() -> APIRouter | None:
    """The router when the host switched the live replay on; otherwise nothing is mounted."""
    enabled = os.environ.get(_ENV_ENABLED, "").strip().lower() == "true"
    return create_live_router() if enabled else None
