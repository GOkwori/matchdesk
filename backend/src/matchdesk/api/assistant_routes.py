"""POST /api/assistant/plan: an optional Foundry translator for Ask MatchDesk questions.

Mounted only when the host switches the planner on. It returns a query plan, never an
answer; the browser computes and verifies every figure itself.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from matchdesk.domain.assistant_planner import (
    MAX_QUESTION_CHARS,
    AssistantPlanner,
    PlannerBusy,
    QuestionRejected,
)
from matchdesk.domain.foundry_runtime import FoundryRuntimeUnavailable

_log = logging.getLogger("matchdesk.assistant")


class PlanRequest(BaseModel):
    """One question, bounded."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)


def create_assistant_router(planner: AssistantPlanner) -> APIRouter:
    """Expose the planner; failures degrade to the unknown plan, never to a guess."""
    router = APIRouter()

    @router.post("/api/assistant/plan")
    async def plan(request: PlanRequest) -> JSONResponse:
        """Read one question into a plan."""
        try:
            result: dict[str, Any] = await planner.plan(request.question)
        except PlannerBusy:
            return JSONResponse(
                status_code=429,
                content={"detail": "The assistant is busy; try one of the suggested questions"},
            )
        except FoundryRuntimeUnavailable:
            return JSONResponse(
                status_code=503, content={"detail": "The assistant planner is unavailable"}
            )
        except QuestionRejected:
            return JSONResponse(
                status_code=422,
                content={"detail": f"Ask a question of 1 to {MAX_QUESTION_CHARS} characters"},
            )
        except Exception:  # noqa: BLE001 - a model or network fault must never surface as a guess
            _log.warning("assistant planner call failed", exc_info=True)
            return JSONResponse(status_code=200, content={"plan": {"intent": "unknown"}})
        return JSONResponse(status_code=200, content={"plan": result})

    return router


def assistant_router_from_env() -> APIRouter | None:
    """The router when the host switched the planner on; otherwise nothing is mounted."""
    planner = AssistantPlanner()
    return create_assistant_router(planner) if planner.enabled else None
