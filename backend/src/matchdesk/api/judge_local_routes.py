"""Opt-in loopback-only synthetic judge API, without production identity authority.

Each request is independently restricted to an exact local host, peer, origin
and intent header. A browser cannot acquire producer or publication authority.
This router is never mounted on the exported foundation API.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from matchdesk.api.limits import BodyLimitMiddleware
from matchdesk.domain.judge_golden_path import build_judge_golden_path
from matchdesk.domain.judge_sessions import JudgeSession, LocalJudgeSessions

_LOCAL_ORIGIN = "http://127.0.0.1:8000"
_INTENT = "synthetic-local-v1"
_SESSION_ID = re.compile(r"[A-Za-z0-9_-]{32}\Z")
_BEARER = re.compile(r"Bearer ([A-Za-z0-9_-]{43})\Z")
_TTL_SECONDS = 15 * 60


def _headers() -> dict[str, str]:
    """Disallow storage, framing, referrer leaks and browser MIME inference."""
    return {
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "X-Frame-Options": "DENY",
        "Vary": "Origin, Authorization, X-MatchDesk-Judge",
    }


def _error(status: int, message: str) -> JSONResponse:
    """Return a generic bounded error that cannot reveal bearer material."""
    return JSONResponse({"detail": message}, status_code=status, headers=_headers())


def _local(request: Request) -> bool:
    """Independently reject remote peers, rebinding and forwarded spoofing."""
    headers = request.headers
    return (
        request.client is not None
        and request.client.host == "127.0.0.1"
        and headers.getlist("host") == ["127.0.0.1:8000"]
        and headers.getlist("origin") == [_LOCAL_ORIGIN]
        and headers.getlist("x-matchdesk-judge") == [_INTENT]
        and not request.url.query
        and not headers.getlist("cookie")
        and not headers.getlist("referer")
        and not any(
            key.lower() == "forwarded" or key.lower().startswith(("x-forwarded-", "x-original-"))
            for key in headers
        )
    )


def _token(request: Request) -> str | None:
    """Require exactly one well-formed bearer without accepting cookie grants."""
    values = request.headers.getlist("authorization")
    if len(values) != 1:
        return None
    found = _BEARER.fullmatch(values[0])
    return found.group(1) if found is not None else None


def _public_session(session: JudgeSession) -> dict[str, Any]:
    """Return an intentional create/reset capability, never in a replay response."""
    return {
        "session_id": session.session_id,
        "token": session.token,
        "generation": session.generation,
        "ttl_seconds": _TTL_SECONDS,
        "mode": "synthetic_local_read_only",
    }


def create_judge_local_app(*, sessions: LocalJudgeSessions | None = None) -> FastAPI:
    """Construct a disposable judge-only process with no published default mount."""
    store = sessions if sessions is not None else LocalJudgeSessions()
    app = FastAPI(
        title="MatchDesk disposable localhost judge",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    # No endpoint may buffer an unbounded or misleadingly sized request body.
    app.add_middleware(BodyLimitMiddleware, max_bytes=2048)

    @app.post("/api/judge/sessions", status_code=201)
    async def create(request: Request) -> JSONResponse:
        """Mint one expiring bearer only for an exact loopback JSON request."""
        if not _local(request) or request.headers.getlist("authorization"):
            return _error(403, "Local judge request denied")
        if (
            request.headers.getlist("content-type") != ["application/json"]
            or await request.body() != b"{}"
        ):
            return _error(400, "Expected an empty JSON object")
        try:
            session = store.create()
        except RuntimeError:
            return _error(429, "Local judge capacity reached")
        return JSONResponse(_public_session(session), status_code=201, headers=_headers())

    def authorized(request: Request, session_id: str) -> JudgeSession | None:
        """Check every read/write independently against the current bearer."""
        if not _local(request) or not _SESSION_ID.fullmatch(session_id):
            return None
        token = _token(request)
        if token is None:
            return None
        try:
            return store.get(session_id, token)
        except PermissionError:
            return None

    @app.get("/api/judge/sessions/{session_id}/replay")
    def replay(session_id: str, request: Request) -> JSONResponse:
        """Return fixture-backed evidence without a privileged producer action."""
        session = authorized(request, session_id)
        if session is None:
            return _error(403, "Local judge session unavailable")
        try:
            manifest = build_judge_golden_path()
        except Exception:
            # Do not return a partial or potentially mislabelled verification.
            return _error(503, "Synthetic replay unavailable")
        return JSONResponse(
            {
                "session_id": session.session_id,
                "generation": session.generation,
                "replay": manifest,
            },
            headers=_headers(),
        )

    @app.post("/api/judge/sessions/{session_id}/reset")
    async def reset(session_id: str, request: Request) -> JSONResponse:
        """Rotate and revoke the old bearer before returning the new one."""
        current = authorized(request, session_id)
        if current is None:
            return _error(403, "Local judge session unavailable")
        if (
            request.headers.getlist("content-type") != ["application/json"]
            or await request.body() != b"{}"
        ):
            return _error(400, "Expected an empty JSON object")
        # The store revalidates under its lock, including concurrent reset races.
        try:
            replacement = store.reset(session_id, _token(request) or "")
        except PermissionError:
            return _error(403, "Local judge session unavailable")
        return JSONResponse(_public_session(replacement), headers=_headers())

    @app.delete("/api/judge/sessions/{session_id}", status_code=204)
    def close(session_id: str, request: Request) -> Response:
        """Revoke exactly one bearer, without touching other judge sessions."""
        current = authorized(request, session_id)
        if current is None:
            return _error(403, "Local judge session unavailable")
        try:
            store.close(session_id, _token(request) or "")
        except PermissionError:
            return _error(403, "Local judge session unavailable")
        return Response(status_code=204, headers=_headers())

    return app
