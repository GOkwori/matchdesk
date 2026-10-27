"""Run the four-specialist workflow live on Microsoft Foundry, one run at a time.

POST /api/agents/run starts a run on the 58′ goal; GET /api/agents/run reports it, step by
step while it runs and in full when it ends. Mounted only when the host switches it on
(MATCHDESK_LIVE_AGENTS_ENABLED=true). Each run makes billable model calls, so runs are
spaced out and capped per day. Agents may only propose: the verifier decides what is true,
and nothing is published.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, cast

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from matchdesk.api.telemetry import tracer
from matchdesk.domain.agent_demo import record_agent_run, trace_view
from matchdesk.domain.agent_workflow import WorkflowExecutor, describe_error

_ENV_ENABLED = "MATCHDESK_LIVE_AGENTS_ENABLED"
COOLDOWN_SECONDS = 300.0
PER_DAY = 12
RUN_TIMEOUT_SECONDS = 360.0

Runner = Callable[[WorkflowExecutor, list[dict[str, Any]]], Awaitable[dict[str, Any]]]


async def _default_runner(
    executor: WorkflowExecutor, progress: list[dict[str, Any]]
) -> dict[str, Any]:
    """One run of the recorded workflow, with the shared progress list."""
    return await record_agent_run(executor, progress=progress)


@dataclass
class LiveRuns:
    """At most one run at a time, spaced by a cooldown and capped per day."""

    executor_factory: Callable[[], WorkflowExecutor]
    runner: Runner = _default_runner
    cooldown: float = COOLDOWN_SECONDS
    per_day: int = PER_DAY
    timeout: float = RUN_TIMEOUT_SECONDS
    now: Callable[[], float] = time.monotonic
    run_id: str | None = None
    status: str = "idle"
    started_at: str | None = None
    started: float | None = None
    finished: float | None = None
    progress: list[dict[str, Any]] = field(default_factory=list)
    trace: dict[str, Any] | None = None
    error: str | None = None
    _starts: deque[float] = field(default_factory=deque)
    _task: asyncio.Task[None] | None = None

    def wait_seconds(self) -> float:
        """How long until a new run may start; zero when one may start now."""
        moment = self.now()
        while self._starts and moment - self._starts[0] >= 86_400:
            self._starts.popleft()
        if len(self._starts) >= self.per_day:
            return 86_400 - (moment - self._starts[0])
        if self._starts and moment - self._starts[-1] < self.cooldown:
            return self.cooldown - (moment - self._starts[-1])
        return 0.0

    def start(self) -> None:
        """Begin a run in the background."""
        moment = self.now()
        self._starts.append(moment)
        self.run_id = f"live-{int(time.time())}"
        self.status = "running"
        self.started = moment
        self.finished = None
        self.started_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        self.progress = []
        self.trace = None
        self.error = None
        self._task = asyncio.get_running_loop().create_task(self._run())

    async def _run(self) -> None:
        """Run to the end or the time limit; keep the outcome, never raise."""
        with tracer.start_as_current_span("matchdesk.agents.live_run") as span:
            await self._run_once()
            span.set_attribute("matchdesk.run.status", self.status)
            span.set_attribute("matchdesk.run.steps", len(self.progress))
            if self.trace is not None:
                totals = self.trace.get("totals", {})
                for key in ("specialist_turns", "tool_calls", "verification_rounds", "tokens"):
                    if isinstance(totals.get(key), int):
                        span.set_attribute(f"matchdesk.run.{key}", totals[key])

    async def _run_once(self) -> None:
        """The run itself."""
        try:
            trace = await asyncio.wait_for(
                self.runner(self.executor_factory(), self.progress), timeout=self.timeout
            )
            trace["recorded_on"] = (self.started_at or "")[:10]
            trace["live_run_id"] = self.run_id
            self.trace = trace
            self.status = "completed" if trace.get("status") == "completed" else "stopped"
        except TimeoutError:
            self.status, self.error = (
                "failed",
                "The run took longer than six minutes and was stopped",
            )
        except Exception as error:  # noqa: BLE001 - a provider fault is reported, not raised
            self.status, self.error = "failed", describe_error(error)
        finally:
            # A finished run reports how long it took, not how long ago it started.
            self.finished = self.now()

    def report(self) -> dict[str, Any]:
        """What the studio shows: the run's state, its steps so far, and the trace when done."""
        steps = trace_view({"steps": list(self.progress)})["steps"]
        end = self.finished if self.finished is not None else self.now()
        elapsed = None if self.started is None else int((end - self.started) * 1000)
        return {
            "run_id": self.run_id,
            "status": self.status,
            "started_at": self.started_at,
            "elapsed_ms": elapsed,
            "steps": steps,
            "trace": trace_view(self.trace) if self.trace is not None else None,
            "error": self.error,
            "next_run_in_s": int(self.wait_seconds()) if self.status != "running" else None,
        }


def create_agent_router(runs: LiveRuns) -> APIRouter:
    """Start and watch live runs."""
    router = APIRouter()

    @router.post("/api/agents/run", status_code=202)
    async def start() -> JSONResponse:
        """Start a live run if none is going and the spacing allows it."""
        if runs.status == "running":
            return JSONResponse(
                status_code=409, content={"detail": "A run is already going", "run_id": runs.run_id}
            )
        wait = runs.wait_seconds()
        if wait > 0:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Live runs are spaced out to bound cost",
                    "retry_after_s": int(wait) + 1,
                },
            )
        runs.start()
        return JSONResponse(status_code=202, content={"run_id": runs.run_id})

    @router.get("/api/agents/run")
    async def watch() -> JSONResponse:
        """The current or last run."""
        return JSONResponse(content=runs.report(), headers={"Cache-Control": "no-store"})

    return router


def agent_router_from_env() -> APIRouter | None:
    """The router when the host switched live runs on; otherwise nothing is mounted."""
    if os.environ.get(_ENV_ENABLED, "").strip().lower() != "true":
        return None
    from matchdesk.domain.foundry_runtime import FoundryWorkflowExecutor

    return create_agent_router(
        LiveRuns(executor_factory=lambda: cast(WorkflowExecutor, FoundryWorkflowExecutor()))
    )
