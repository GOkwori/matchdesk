"""Bound incoming request bodies before JSON parsing allocates unbounded memory."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimitMiddleware:
    """Enforce an actual byte limit, including requests without Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int = 65_536) -> None:
        """Configure a positive byte budget for each HTTP request."""
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Read at most the allowed bytes, then replay the bounded body downstream.

        Header-only checks are insufficient: chunked clients can omit the header
        or claim a smaller length. Both the declared and actual size are checked.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        if b"content-length" in headers:
            try:
                length = int(headers[b"content-length"])
                if length < 0:
                    raise ValueError("negative length")
            except ValueError:
                await JSONResponse({"detail": "Invalid content length"}, status_code=400)(
                    scope,
                    receive,
                    send,
                )
                return
            if length > self.max_bytes:
                await JSONResponse({"detail": "Request body too large"}, status_code=413)(
                    scope,
                    receive,
                    send,
                )
                return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await JSONResponse({"detail": "Request body too large"}, status_code=413)(
                    scope,
                    receive,
                    send,
                )
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        sent = False

        async def replay() -> Message:
            """Replay once and then forward disconnects to preserve ASGI semantics."""
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)
