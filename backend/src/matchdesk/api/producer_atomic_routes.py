"""Default-unmounted HTTP boundary for signed, atomic producer decisions.

There is no legacy Boolean/UUID-grant or direct-DML fallback in this router.
The trusted bridge independently revalidates the access token and signed human
confirmation before staging and issuing a PostgreSQL grant. Merely constructing
this factory does not enable live Entra, production access or publication.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from matchdesk.api.producer_command_routes import (
    CreateProducerRequest,
    ProducerDecisionRequest,
    ProducerEditRequest,
    ProducerSourceResolver,
    _body,
)
from matchdesk.api.producer_reverification_routes import (
    ReverificationRequest,
    _headers,
    _request_shape,
    _response,
)
from matchdesk.domain.producer_atomic_grant_bridge import ProducerAtomicGrantBridge
from matchdesk.domain.producer_commands import (
    ProducerCase,
    ProducerCaseReader,
    _validate_case,
    apply_producer_command,
    inspect_producer_case,
)

_Action = Literal["create", "edit", "reverify", "approve", "reject"]


def create_atomic_producer_router(
    *,
    bridge: ProducerAtomicGrantBridge,
    source: ProducerSourceResolver,
    reader: ProducerCaseReader,
) -> APIRouter:
    """Build a separately injected, fail-closed atomic-only producer router.

    The host must provision an independently read-only database principal for
    reader; the bridge uses three different restricted physical workload roles.
    The public app does not mount this router without an explicit host injection.
    """
    if (
        type(bridge) is not ProducerAtomicGrantBridge
        or not callable(getattr(source, "resolve", None))
        or not callable(getattr(reader, "load", None))
        or callable(getattr(reader, "create", None))
        or callable(getattr(reader, "replace_if_generation", None))
        or callable(getattr(reader, "replace_with_execution_grant", None))
    ):
        raise ValueError("Atomic HTTP route requires trusted read-only dependencies")
    router = APIRouter(prefix="/api/workforce/producer", tags=["workforce-producer"])

    async def execute(
        *,
        action: _Action,
        session_id: str,
        output_id: str,
        request: Request,
    ) -> JSONResponse:
        """Validate only case intent at HTTP; authority belongs to the bridge."""
        token = _request_shape(request, session_id, output_id)
        if token is None:
            return _response("Producer command denied", 401)
        try:
            actor = await run_in_threadpool(
                bridge.authenticate, access_token=token, session_id=session_id
            )
        except PermissionError:
            return _response("Producer command denied", 403)
        except Exception:
            return _response("Producer command unavailable", 503)

        kind = (
            CreateProducerRequest
            if action == "create"
            else ReverificationRequest
            if action == "reverify"
            else ProducerEditRequest
            if action == "edit"
            else ProducerDecisionRequest
        )
        command = await _body(request, kind)
        if command is None:
            return _response("Invalid producer command request", 400)

        try:
            if action == "create":
                case = await run_in_threadpool(
                    source.resolve,
                    actor=actor,
                    session_id=session_id,
                    output_id=output_id,
                )
                if (
                    type(case) is not ProducerCase
                    or case.tenant_id != actor.tenant_id
                    or case.output.session_id != session_id
                    or case.output.output_id != output_id
                    or case.generation != 1
                    or case.review.status != "pending_verification"
                    or case.review.audit[0].actor_id != actor.subject
                    or case.output.binding != command.binding
                ):
                    return _response("Producer source or binding changed", 409)
                _validate_case(case)
                expected_generation = 0
                next_case = case
            else:
                case = await run_in_threadpool(
                    inspect_producer_case,
                    reader,
                    actor=actor,
                    session_id=session_id,
                    output_id=output_id,
                )
                if (
                    case.generation != command.expected_generation
                    or case.output.binding != command.binding
                ):
                    return _response("Producer case changed; reload", 409)
                expected_generation = command.expected_generation
                next_case = await run_in_threadpool(
                    apply_producer_command,
                    case,
                    actor=actor,
                    expected_generation=expected_generation,
                    command=action,
                    reason=command.reason,
                    revised_output=(
                        command.revised_output if isinstance(command, ProducerEditRequest) else None
                    ),
                )
        except (PermissionError, LookupError):
            return _response("Producer command denied", 403)
        except (ValueError, RuntimeError):
            return _response("Producer version, source or decision changed", 409)
        except Exception:
            return _response("Producer command unavailable", 503)

        try:
            saved = await run_in_threadpool(
                bridge.execute,
                access_token=token,
                case=next_case,
                action=action,
                expected_generation=expected_generation,
            )
        except PermissionError:
            return _response("Producer command denied", 403)
        except Exception:
            # An ambiguous database outcome must not be converted to 409,
            # success, a retry, or a legacy host approval fallback.
            return _response("Producer command outcome requires reconciliation", 503)
        if saved is not True:
            return _response("Producer command not committed; reload", 409)
        return JSONResponse(
            {
                "session_id": next_case.output.session_id,
                "output_id": next_case.output.output_id,
                "generation": next_case.generation,
                "item_version": next_case.output.binding.item_version,
                "review_status": next_case.review.status,
                "action": action,
                "mode": "signed_atomic_dev_only",
                "publication_enabled": False,
            },
            status_code=201 if action == "create" else 200,
            headers=_headers(),
        )

    @router.post("/sessions/{session_id}/cases/{output_id}/create")
    async def create(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Create a source-bound unapproved case only through a signed atomic grant."""
        return await execute(action="create", session_id=session_id, output_id=output_id, request=request)

    @router.post("/sessions/{session_id}/cases/{output_id}/edit")
    async def edit(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Edit one precise version and invalidate prior decision state."""
        return await execute(action="edit", session_id=session_id, output_id=output_id, request=request)

    @router.post("/sessions/{session_id}/cases/{output_id}/reverify")
    async def reverify(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Reverify evidence without granting publication."""
        return await execute(action="reverify", session_id=session_id, output_id=output_id, request=request)

    @router.post("/sessions/{session_id}/cases/{output_id}/approve")
    async def approve(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Approve only a reverified generation under a signed one-use grant."""
        return await execute(action="approve", session_id=session_id, output_id=output_id, request=request)

    @router.post("/sessions/{session_id}/cases/{output_id}/reject")
    async def reject(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Reject an exact-generation case without publishing anything."""
        return await execute(action="reject", session_id=session_id, output_id=output_id, request=request)

    return router
