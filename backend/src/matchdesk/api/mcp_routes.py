"""POST /api/mcp: MatchDesk's read-only tools over the Model Context Protocol.

A small, stateless MCP server on the Streamable HTTP transport: each JSON-RPC request is one
POST answered with one JSON response, and notifications are acknowledged with 202. There is
no server-initiated stream, no session state and nothing to write. It lets another agent (a
broadcaster's graphics assistant, an IDE agent, a Foundry agent) compute registered
statistics, read events, overlays, stories and recaps, and have its own sentences checked by
MatchDesk's verifier before anything is shown.

Mounted only when the host switches it on (MATCHDESK_MCP_ENABLED=true).
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from matchdesk.api.telemetry import tracer
from matchdesk.domain.mcp_tools import TOOLS, TOOLS_BY_NAME, ToolError

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "matchdesk", "title": "MatchDesk match tools", "version": "1.0.0"}
INSTRUCTIONS = (
    "Read-only tools over one synthetic football match (Northbridge FC v Riverside United, "
    "replayed to 67:12). Use compute_metric for figures, get_events for what happened, and "
    "check_sentence before showing any sentence that states a statistic: it is the same "
    "deterministic verifier MatchDesk uses for its own overlays and stories. Nothing is real, "
    "live or published."
)
_ENV_ENABLED = "MATCHDESK_MCP_ENABLED"
_PARSE_ERROR, _INVALID_REQUEST, _NO_METHOD, _INVALID_PARAMS = -32700, -32600, -32601, -32602


def _error(request_id: Any, code: int, message: str) -> JSONResponse:
    """A JSON-RPC error response."""
    return JSONResponse(
        {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    )


def _reply(request_id: Any, result: dict[str, Any]) -> JSONResponse:
    """A JSON-RPC result response."""
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _call(params: dict[str, Any]) -> dict[str, Any]:
    """Run one tool; argument problems come back as a tool error the model can read and fix."""
    tool = TOOLS_BY_NAME[params["name"]]
    arguments = params.get("arguments") or {}
    with tracer.start_as_current_span("matchdesk.mcp.call") as span:
        span.set_attribute("matchdesk.mcp.tool", tool.name)
        try:
            if not isinstance(arguments, dict):
                raise ToolError("arguments must be an object")
            unknown = set(arguments) - set(tool.schema["properties"])
            if unknown:
                raise ToolError(f"unknown arguments: {', '.join(sorted(unknown))}")
            result = tool.handler(arguments)
        except ToolError as error:
            span.set_attribute("matchdesk.mcp.status", "tool_error")
            return {"content": [{"type": "text", "text": str(error)}], "isError": True}
        span.set_attribute("matchdesk.mcp.status", "ok")
    return {
        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
        "structuredContent": result,
        "isError": False,
    }


def create_mcp_router() -> APIRouter:
    """The MCP endpoint."""
    router = APIRouter()

    @router.post("/api/mcp", response_model=None)
    async def mcp(request: Request) -> Response:
        """Answer one JSON-RPC message."""
        try:
            message = json.loads(await request.body())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _error(None, _PARSE_ERROR, "Parse error")
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _error(None, _INVALID_REQUEST, "Send one JSON-RPC 2.0 message per request")
        method = message.get("method")
        if "id" not in message:
            # Notifications (initialized, cancelled) need no answer.
            return Response(status_code=202)
        request_id = message["id"]
        params = message.get("params") or {}
        if not isinstance(method, str) or not isinstance(params, dict):
            return _error(request_id, _INVALID_REQUEST, "Invalid request")
        if method == "initialize":
            asked = params.get("protocolVersion")
            version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            return _reply(
                request_id,
                {
                    "protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO,
                    "instructions": INSTRUCTIONS,
                },
            )
        if method == "ping":
            return _reply(request_id, {})
        if method == "tools/list":
            return _reply(
                request_id,
                {
                    "tools": [
                        {
                            "name": tool.name,
                            "title": tool.title,
                            "description": tool.description,
                            "inputSchema": tool.schema,
                            "annotations": {"readOnlyHint": True, "openWorldHint": False},
                        }
                        for tool in TOOLS
                    ]
                },
            )
        if method == "tools/call":
            if params.get("name") not in TOOLS_BY_NAME:
                return _error(request_id, _INVALID_PARAMS, f"Unknown tool: {params.get('name')}")
            return _reply(request_id, _call(params))
        return _error(request_id, _NO_METHOD, f"Method not found: {method}")

    @router.get("/api/mcp", response_model=None)
    async def no_stream() -> Response:
        """This server never starts a stream of its own."""
        return Response(status_code=405, headers={"Allow": "POST"})

    return router


def mcp_router_from_env() -> APIRouter | None:
    """The router when the host switched the MCP endpoint on; otherwise nothing is mounted."""
    enabled = os.environ.get(_ENV_ENABLED, "").strip().lower() == "true"
    return create_mcp_router() if enabled else None
