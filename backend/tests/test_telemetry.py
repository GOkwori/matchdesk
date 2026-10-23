"""Telemetry: exported only with a connection string, with counts and never content."""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any

import pytest
from fastapi.testclient import TestClient
from matchdesk.api.app import create_app
from matchdesk.api.assistant_routes import create_assistant_router
from matchdesk.api.live_routes import create_live_router
from matchdesk.api.telemetry import configure_telemetry
from matchdesk.domain.assistant_planner import (
    AssistantPlanner,
    AssistantPlannerConfig,
    PlannedQuestion,
)
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

EXPORTER = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(_provider)


def test_nothing_is_exported_without_a_connection_string() -> None:
    """No variable, no exporter."""
    assert configure_telemetry({}) is False
    assert configure_telemetry({"APPLICATIONINSIGHTS_CONNECTION_STRING": "  "}) is False


def test_a_connection_string_configures_both_exporters_without_sensitive_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Traces and metrics go to Application Insights; prompts and replies do not."""
    seen: dict[str, Any] = {}
    fake = types.ModuleType("agent_framework.observability")

    def configure(**kwargs: Any) -> None:
        """Record what the API asks for."""
        seen.update(kwargs)

    fake.configure_otel_providers = configure  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agent_framework.observability", fake)
    connection = "InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint=https://example.invalid/"
    assert configure_telemetry({"APPLICATIONINSIGHTS_CONNECTION_STRING": connection}) is True
    assert seen["service_name"] == "matchdesk-api" and seen["enable_sensitive_data"] is False
    assert sorted(type(e).__name__ for e in seen["exporters"]) == [
        "AzureMonitorMetricExporter",
        "AzureMonitorTraceExporter",
    ]


def test_a_failing_setup_never_stops_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """A broken exporter is logged and skipped."""
    fake = types.ModuleType("agent_framework.observability")

    def configure(**kwargs: Any) -> None:
        """Record what the API asks for."""
        raise RuntimeError("no network")

    fake.configure_otel_providers = configure  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agent_framework.observability", fake)
    assert (
        configure_telemetry({"APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=x"})
        is False
    )


def test_the_planner_span_carries_the_intent_not_the_question() -> None:
    """One span per question, with its intent and status."""

    class _Agent:
        """A planner agent that always reads the question as the score."""

        async def run(self, prompt: str, **kwargs: Any) -> Any:
            """Return the plan."""
            return types.SimpleNamespace(value=PlannedQuestion(intent="score"))

    class _Factory:
        """Hands out that agent."""

        def create(self, config: AssistantPlannerConfig) -> _Agent:
            """Return the agent."""
            return _Agent()

    planner = AssistantPlanner(
        config=AssistantPlannerConfig(True, "https://example.invalid", "m"),
        factory=_Factory(),  # type: ignore[arg-type]
    )
    EXPORTER.clear()
    client = TestClient(create_app(assistant_router=create_assistant_router(planner)))
    client.post("/api/assistant/plan", json={"question": "How is it going for the home side?"})
    span = next(s for s in EXPORTER.get_finished_spans() if s.name == "matchdesk.assistant.plan")
    assert span.attributes is not None
    assert span.attributes["matchdesk.plan.intent"] == "score"
    assert span.attributes["matchdesk.http.status"] == 200
    assert all("home side" not in str(v) for v in span.attributes.values())


def test_the_stream_span_counts_events_and_verdicts(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stream from 66:40 sends its last events and cues, all counted."""
    import matchdesk.domain.live_replay as module

    monkeypatch.setattr(module, "MAX_GAP_SECONDS", 0.0)
    EXPORTER.clear()
    client = TestClient(create_app(assistant_router=create_live_router()))
    with client.stream("GET", "/api/live/stream?speed=60&from_ms=4000000") as response:
        "".join(response.iter_text())
    span = next(s for s in EXPORTER.get_finished_spans() if s.name == "matchdesk.live.stream")
    assert span.attributes is not None
    assert span.attributes["matchdesk.stream.events"] > 0
    assert span.attributes["matchdesk.stream.verifieds"] == 1
    assert span.attributes["matchdesk.stream.loggeds"] == 1
    assert span.attributes["matchdesk.stream.faileds"] == 0


def test_the_live_run_span_records_totals() -> None:
    """A finished run reports its turns, tool calls and rounds."""
    from matchdesk.api.agent_routes import LiveRuns
    from matchdesk.domain.agent_demo import record_agent_run
    from matchdesk.domain.agent_rehearsal import RehearsalExecutor

    async def rehearsal(executor: Any, progress: list[dict[str, Any]]) -> dict[str, Any]:
        """Run the deterministic rehearsal with the shared progress list."""
        return await record_agent_run(executor, clock=lambda: None, progress=progress)

    async def scenario() -> None:
        """Start a run and wait for it."""
        runs = LiveRuns(executor_factory=RehearsalExecutor, runner=rehearsal)  # type: ignore[arg-type]
        runs.start()
        assert runs._task is not None
        await runs._task

    EXPORTER.clear()
    asyncio.run(scenario())
    span = next(s for s in EXPORTER.get_finished_spans() if s.name == "matchdesk.agents.live_run")
    assert span.attributes is not None
    assert span.attributes["matchdesk.run.status"] == "completed"
    assert span.attributes["matchdesk.run.verification_rounds"] == 2
    assert span.attributes["matchdesk.run.specialist_turns"] >= 4


def test_the_mcp_span_names_the_tool_and_its_outcome() -> None:
    """One span per tool call, with the tool and whether it answered; never the arguments."""
    from matchdesk.api.mcp_routes import create_mcp_router

    client = TestClient(create_app(assistant_router=create_mcp_router()))
    EXPORTER.clear()
    for arguments in ({"metric": "shots.v1", "team": "nbr"}, {"metric": "nope"}):
        client.post(
            "/api/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "compute_metric", "arguments": arguments},
            },
        )
    spans = [s for s in EXPORTER.get_finished_spans() if s.name == "matchdesk.mcp.call"]
    assert [(s.attributes or {}).get("matchdesk.mcp.status") for s in spans] == ["ok", "tool_error"]
    assert all((s.attributes or {}).get("matchdesk.mcp.tool") == "compute_metric" for s in spans)
