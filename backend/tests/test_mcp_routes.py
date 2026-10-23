"""The MCP endpoint: read-only match tools for other agents, checked by the same verifier."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from matchdesk.api.app import create_app
from matchdesk.api.mcp_routes import PROTOCOL_VERSIONS, create_mcp_router, mcp_router_from_env
from matchdesk.domain.mcp_tools import TOOLS

CLIENT = TestClient(create_app(assistant_router=create_mcp_router()))


def _rpc(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send one JSON-RPC request and return the parsed response."""
    response = CLIENT.post(
        "/api/mcp", json={"jsonrpc": "2.0", "id": 7, "method": method, "params": params or {}}
    )
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["jsonrpc"] == "2.0" and body["id"] == 7
    return body


def _call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a tool and return its result."""
    result: dict[str, Any] = _rpc("tools/call", {"name": name, "arguments": arguments})["result"]
    return result


def test_initialize_negotiates_the_protocol_and_says_what_the_tools_are_for() -> None:
    """The client's version when supported, the latest otherwise; tools only, nothing else."""
    result = _rpc("initialize", {"protocolVersion": "2025-03-26"})["result"]
    assert result["protocolVersion"] == "2025-03-26"
    assert result["capabilities"] == {"tools": {"listChanged": False}}
    assert result["serverInfo"]["name"] == "matchdesk"
    assert "synthetic" in result["instructions"]
    later = _rpc("initialize", {"protocolVersion": "2099-01-01"})["result"]
    assert later["protocolVersion"] == PROTOCOL_VERSIONS[0]
    assert _rpc("ping")["result"] == {}


def test_every_tool_is_read_only_with_a_valid_closed_schema() -> None:
    """Nine tools, each annotated read-only, each schema valid JSON Schema."""
    tools = _rpc("tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == [tool.name for tool in TOOLS]
    assert len(tools) == 9
    for tool in tools:
        Draft202012Validator.check_schema(tool["inputSchema"])
        assert tool["inputSchema"]["additionalProperties"] is False
        assert tool["annotations"] == {"readOnlyHint": True, "openWorldHint": False}


def test_check_sentence_verifies_true_sentences_and_sends_back_false_ones() -> None:
    """The studio's verifier: 58% passes, 61% does not, a wrong half does not."""
    good = _call(
        "check_sentence",
        {
            "sentence": "Northbridge have had 58% possession.",
            "metric": "possession_time.v1",
            "team": "nbr",
            "value": 0.58,
        },
    )
    assert good["isError"] is False and good["structuredContent"]["status"] == "verified"
    wrong = _call(
        "check_sentence",
        {
            "sentence": "Northbridge have had 61% possession.",
            "metric": "possession_time.v1",
            "team": "nbr",
            "value": 0.61,
        },
    )
    assert wrong["structuredContent"]["verified"] is False
    half = _call(
        "check_sentence",
        {
            "sentence": "Okafor scored 2 goals in the second half.",
            "metric": "goals.v1",
            "player": "nbr-09",
            "value": 2,
            "period": 2,
        },
    )
    assert half["structuredContent"]["status"] == "needs_revision"
    unnamed = _call(
        "check_sentence",
        {"sentence": "They scored 2 goals.", "metric": "goals.v1", "player": "nbr-09", "value": 2},
    )
    assert unnamed["structuredContent"]["verified"] is False


def test_verify_claim_takes_a_full_contract_including_event_facts() -> None:
    """A registered event fact verifies; a malformed claim is a readable tool error."""
    fact = {
        "claim_id": "X-1",
        "text": "Okafor scored for Northbridge at 58:17.",
        "kind": "event_fact",
        "fact": {"query": "goal_scorer.v1", "event_id": "E-1366", "player_id": "nbr-09"},
        "evidence_event_ids": ["E-1366"],
    }
    assert _call("verify_claim", {"claim": fact})["structuredContent"]["status"] == "verified"
    broken = _call("verify_claim", {"claim": {"claim_id": "X-2"}})
    assert broken["isError"] is True and "Claim contract" in broken["content"][0]["text"]


def test_compute_events_overlays_stories_and_recaps() -> None:
    """Figures, events and the published feeds, bounded to the replay point."""
    shots = _call("compute_metric", {"metric": "shots.v1", "team": "nbr"})["structuredContent"]
    assert shots["value"] == 14 and shots["window"]["to"] == "67:12"
    goals = _call("get_events", {"type": "goal"})["structuredContent"]
    assert [e["clock"] for e in goals["events"]] == ["34:18", "41:03", "58:17"]
    limited = _call("get_events", {"limit": 5})["structuredContent"]
    assert limited["returned"] == 5 and limited["count"] == 1421
    cues = _call("get_overlays", {"from_minute": 58, "to_minute": 59, "language": "fr"})
    assert [c["text"] for c in cues["structuredContent"]["cues"]] == [
        "BUT ! Okafor marque pour Northbridge. 2–1."
    ]
    stories = _call("get_story", {})["structuredContent"]["stories"]
    assert len(stories) == 3
    story = _call("get_story", {"story": "E-1366", "persona": "caption"})["structuredContent"]
    assert story["headline"] == "59′ GOAL · Okafor · NBR 2–1 RIV"
    assert {c["status"] for c in story["checks"]} == {"verified"}
    recap = _call("get_recap", {"at": "half-time"})["structuredContent"]
    assert recap["score"] == {"nbr": 1, "riv": 1}
    assert {c["status"] for c in recap["checks"]} == {"verified"}
    players = _call("list_players", {})["structuredContent"]["players"]
    assert len(players) == 32 and any(
        p["player"] == "nbr-09" and p["name"] == "Okafor" and p["team"] == "nbr" for p in players
    )
    assert len(_call("list_metrics", {})["structuredContent"]["metrics"]) == 14


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("compute_metric", {"metric": "nope"}, "registered metric"),
        ("compute_metric", {"metric": "shots.v1"}, "team or a player"),
        ("compute_metric", {"metric": "shots.v1", "team": "ars"}, "nbr"),
        ("compute_metric", {"metric": "shots.v1", "team": "nbr", "to_minute": 90}, "whole minute"),
        (
            "compute_metric",
            {"metric": "shots.v1", "team": "nbr", "from_minute": 30, "to_minute": 20},
            "after",
        ),
        ("get_events", {"limit": 1000}, "limit"),
        ("get_recap", {"at": "full-time"}, "half-time"),
        ("get_story", {"story": "nope"}, "slug"),
        ("list_metrics", {"extra": 1}, "unknown arguments"),
    ],
)
def test_bad_arguments_come_back_as_tool_errors(
    name: str, arguments: dict[str, Any], message: str
) -> None:
    """The model gets a message it can act on, not a protocol failure."""
    result = _call(name, arguments)
    assert result["isError"] is True and message in result["content"][0]["text"]


def test_protocol_errors_notifications_and_streams() -> None:
    """Unknown methods and tools, bad JSON, notifications and GET are handled per the transport."""
    assert _rpc("resources/list")["error"]["code"] == -32601
    assert _rpc("tools/call", {"name": "delete_everything"})["error"]["code"] == -32602
    bad = CLIENT.post("/api/mcp", content=b"{", headers={"content-type": "application/json"})
    assert bad.json()["error"]["code"] == -32700
    batch = CLIENT.post("/api/mcp", json=[{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
    assert batch.json()["error"]["code"] == -32600
    note = CLIENT.post("/api/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert note.status_code == 202 and note.content == b""
    assert CLIENT.get("/api/mcp").status_code == 405


def test_the_endpoint_is_mounted_only_when_switched_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off by default."""
    monkeypatch.delenv("MATCHDESK_MCP_ENABLED", raising=False)
    assert mcp_router_from_env() is None
    monkeypatch.setenv("MATCHDESK_MCP_ENABLED", "true")
    assert mcp_router_from_env() is not None
    assert CLIENT.post("/api/mcp", json={}).status_code == 200
    assert TestClient(create_app()).post("/api/mcp", json={}).status_code == 404
