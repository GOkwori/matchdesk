"""Expose foundation health and structural validation without publishing authority.

There is deliberately no mocked match feed or production-ready health assertion.
The workbench validates contracts; it cannot establish that supplied events exist.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from matchdesk.api.assistant_routes import assistant_router_from_env
from matchdesk.api.limits import BodyLimitMiddleware
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import MatchEvent
from matchdesk.domain.producer_preview import ProducerDeskPreview, build_producer_desk_preview


class HealthResponse(BaseModel):
    """Liveness describes this process only, never the availability of the product."""

    service: Literal["matchdesk"] = "matchdesk"
    status: Literal["alive"] = "alive"
    phase: Literal["foundation"] = "foundation"
    model_mode: Literal["not_connected"] = "not_connected"


class ValidationResponse(BaseModel):
    """Structural acceptance and content identity, explicitly distinct from evidence."""

    event_id: str
    structurally_valid: Literal[True] = True
    evidence_verified: Literal[False] = False
    content_digest: str


def create_app(
    *,
    customer_session_router: APIRouter | None = None,
    customer_oidc_router: APIRouter | None = None,
    producer_read_router: APIRouter | None = None,
    producer_reverification_router: APIRouter | None = None,
    producer_command_router: APIRouter | None = None,
    producer_atomic_router: APIRouter | None = None,
    assistant_router: APIRouter | None = None,
) -> FastAPI:
    """Construct an isolated app; atomic producer routes never coexist with legacy writes."""
    if producer_atomic_router is not None and (
        producer_command_router is not None or producer_reverification_router is not None
    ):
        raise ValueError("Atomic producer router cannot coexist with legacy mutation routers")
    app = FastAPI(
        title="MatchDesk foundation API",
        version="0.0.1",
        description="Local contract workbench. Match ingestion and publishing are not implemented.",
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(BodyLimitMiddleware)
    # Only a trusted host may explicitly mount a separately qualified router.
    # The default application exposes no authenticated session routes.
    if customer_session_router is not None:
        app.include_router(customer_session_router)
    # OIDC is opt-in and cannot be activated by the default exported app.
    if customer_oidc_router is not None:
        app.include_router(customer_oidc_router)
    # Producer inspection requires an explicit host-injected workforce router.
    if producer_read_router is not None:
        app.include_router(producer_read_router)
    # Privileged producer reverification remains absent unless the host opts in.
    if producer_reverification_router is not None:
        app.include_router(producer_reverification_router)
    # Privileged commands are invisible unless the host injects trusted dependencies.
    # The exported application remains a deny-by-default foundation workbench.
    if producer_command_router is not None:
        app.include_router(producer_command_router)
    # Signed-confirmation producer commands are an explicitly injected,
    # default-unmounted candidate. Refuse any concurrent legacy write router.
    if producer_atomic_router is not None:
        app.include_router(producer_atomic_router)
    # The Ask MatchDesk planner only reads questions into plans; it is mounted when the
    # host switches it on (MATCHDESK_ASSISTANT_FOUNDRY_ENABLED=true).
    if assistant_router is not None:
        app.include_router(assistant_router)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Return validation locations without echoing possibly private submitted values."""
        del request
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(error["loc"]), "type": error["type"], "msg": error["msg"]}
                    for error in exc.errors()
                ]
            },
        )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Confirm that the foundation process can answer requests."""
        return HealthResponse()

    @app.get("/api/ready", status_code=503)
    def ready() -> JSONResponse:
        """Fail closed until persistence, model integration and product gates exist."""
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "phase": "foundation",
                "checks": {
                    "persistence": "not_implemented",
                    "models": "not_connected",
                    "publication": "not_implemented",
                },
            },
        )

    @app.get("/api/producer/preview", response_model=ProducerDeskPreview)
    def producer_preview() -> ProducerDeskPreview:
        """Inspect real seeded evidence without creating an authenticated review."""
        return build_producer_desk_preview()

    @app.get("/api/contracts/event")
    def event_schema() -> dict[str, object]:
        """Expose the exact accepted JSON schema for local integration development."""
        return MatchEvent.model_json_schema()

    @app.post("/api/contracts/event/validate", response_model=ValidationResponse)
    def validate_event(event: MatchEvent) -> ValidationResponse:
        """Validate shape without persisting, calculating statistics or trusting a claim."""
        return ValidationResponse(event_id=event.event_id, content_digest=content_digest(event))

    return app


app = create_app()
# Customer and producer routers stay unmounted. The Ask MatchDesk planner, which only reads
# questions into plans, is added when the host switches it on.
_assistant_router = assistant_router_from_env()
if _assistant_router is not None:
    app.include_router(_assistant_router)
