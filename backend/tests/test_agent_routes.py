"""Live agent runs: off by default, one at a time, spaced out, progress visible, never raises."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from matchdesk.api.agent_routes import LiveRuns, agent_router_from_env, create_agent_router
from matchdesk.api.app import create_app
from matchdesk.domain.agent_demo import record_agent_run
from matchdesk.domain.agent_rehearsal import RehearsalExecutor
from matchdesk.domain.agent_workflow import WorkflowExecutor
from matchdesk.domain.foundry_runtime import host_credential


class _Clock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        """Start at zero."""
        self.t = 0.0

    def __call__(self) -> float:
        """Now."""
        return self.t


def _runs(runner: Any = None, clock: _Clock | None = None, **kw: Any) -> LiveRuns:
    """Live runs backed by the deterministic rehearsal, no model calls."""

    async def rehearsal(
        executor: WorkflowExecutor, progress: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Run the deterministic rehearsal with the shared progress list."""
        return await record_agent_run(executor, clock=lambda: None, progress=progress)

    return LiveRuns(
        executor_factory=RehearsalExecutor,  # type: ignore[arg-type]
        runner=runner or rehearsal,
        now=clock or _Clock(),
        **kw,
    )


def test_off_unless_switched_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """No variable, no route."""
    monkeypatch.delenv("MATCHDESK_LIVE_AGENTS_ENABLED", raising=False)
    assert agent_router_from_env() is None
    monkeypatch.setenv("MATCHDESK_LIVE_AGENTS_ENABLED", "true")
    assert agent_router_from_env() is not None
    assert TestClient(create_app()).post("/api/agents/run").status_code == 404


def test_a_run_completes_and_reports_the_same_view_as_a_recording() -> None:
    """Start, then read the finished trace, with progress steps and the verifier's rounds."""

    async def scenario() -> dict[str, Any]:
        """Start a run and wait for it."""
        runs = _runs()
        assert runs.wait_seconds() == 0
        runs.start()
        assert runs.report()["status"] == "running"
        assert runs._task is not None
        await runs._task
        return runs.report()

    report = asyncio.run(scenario())
    assert report["status"] == "completed" and report["error"] is None
    trace = report["trace"]
    assert trace["live_run_id"] == report["run_id"] and trace["recorded_on"]
    kinds = [step["type"] for step in trace["steps"]]
    assert "verification" in kinds and kinds[0] == "specialist"
    assert report["steps"] == trace["steps"]
    assert report["next_run_in_s"] == 300


def test_runs_are_spaced_out_and_capped_per_day() -> None:
    """Five minutes between starts and at most the daily cap."""
    clock = _Clock()
    runs = _runs(clock=clock, per_day=2)
    runs._starts.extend([0.0])
    assert 299 < runs.wait_seconds() <= 300
    clock.t = 301
    assert runs.wait_seconds() == 0
    runs._starts.append(301.0)
    clock.t = 700
    assert runs.wait_seconds() > 80_000
    clock.t = 86_401
    assert runs.wait_seconds() == 0


def test_provider_faults_and_timeouts_are_reported_not_raised() -> None:
    """A crashing or slow provider leaves a readable failure."""

    async def crash(executor: WorkflowExecutor, progress: list[dict[str, Any]]) -> dict[str, Any]:
        """A provider that fails."""
        raise RuntimeError("upstream unavailable")

    async def slow(executor: WorkflowExecutor, progress: list[dict[str, Any]]) -> dict[str, Any]:
        """A provider slower than the limit."""
        await asyncio.sleep(5)
        return {}

    async def scenario(runner: Any, timeout: float) -> dict[str, Any]:
        """Start a run and wait for it."""
        runs = _runs(runner=runner, timeout=timeout)
        runs.start()
        assert runs._task is not None
        await runs._task
        return runs.report()

    crashed = asyncio.run(scenario(crash, 10))
    assert crashed["status"] == "failed" and "RuntimeError" in crashed["error"]
    timed_out = asyncio.run(scenario(slow, 0.01))
    assert timed_out["status"] == "failed" and "six minutes" in timed_out["error"]


def test_the_routes_start_refuse_and_report() -> None:
    """202 to start, 409 while running, 429 inside the cooldown, and a no-store report."""
    gate = asyncio.Event()

    async def held(executor: WorkflowExecutor, progress: list[dict[str, Any]]) -> dict[str, Any]:
        """A run that waits until the test lets it finish."""
        await gate.wait()
        return {"status": "completed", "steps": []}

    runs = _runs(runner=held)
    with TestClient(create_app(assistant_router=create_agent_router(runs))) as client:
        first = client.post("/api/agents/run")
        assert first.status_code == 202 and first.json()["run_id"]
        assert client.post("/api/agents/run").status_code == 409
        report = client.get("/api/agents/run")
        assert report.headers["cache-control"] == "no-store"
        assert report.json()["status"] == "running"
        runs.status = "completed"
        refused = client.post("/api/agents/run")
        assert refused.status_code == 429 and refused.json()["retry_after_s"] > 0


def test_the_host_identity_is_the_managed_identity_on_container_apps() -> None:
    """Managed identity where Container Apps runs the API; the signed-in CLI elsewhere."""

    class _Identity:
        """Stand-in for azure.identity."""

        def ManagedIdentityCredential(self, client_id: str) -> tuple[str, str]:  # noqa: N802
            """Record the managed identity."""
            return ("managed", client_id)

        def AzureCliCredential(self) -> str:  # noqa: N802
            """Record the CLI."""
            return "cli"

    identity = _Identity()
    env = {"CONTAINER_APP_NAME": "mdesk-api", "AZURE_CLIENT_ID": "abc"}
    assert host_credential(identity, env) == ("managed", "abc")
    assert host_credential(identity, {"AZURE_CLIENT_ID": "abc"}) == "cli"
    assert host_credential(identity, {"CONTAINER_APP_NAME": "x"}) == "cli"


def test_a_finished_run_reports_its_duration_not_its_age() -> None:
    """Elapsed time stops when the run ends."""
    clock = _Clock()

    async def scenario() -> tuple[int, int]:
        """Start at 0, finish at 120 s, read at 120 s and again an hour later."""
        runs = _runs(clock=clock)
        runs.start()
        clock.t = 120.0
        assert runs._task is not None
        await runs._task
        first = runs.report()["elapsed_ms"]
        clock.t = 3_720.0
        return first, runs.report()["elapsed_ms"]

    first, later = asyncio.run(scenario())
    assert first == later == 120_000
