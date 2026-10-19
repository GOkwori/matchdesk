"""Opt-in workforce producer create/edit/decision API; no publication routes.

Every privileged transition requires a verified delegated workforce actor, fresh
server-owned session entitlements and a separate, action-specific host decision.
This router is never mounted by the default application. It deliberately does
not provision keys, assert real Entra MFA, or publish any broadcast material.
"""

from __future__ import annotations

import json
from typing import Literal, Protocol, TypeVar, cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from matchdesk.api.producer_reverification_routes import (
    _headers,
    _invalid_constant,
    _request_shape,
    _response,
    _unique_pairs,
)
from matchdesk.domain.broadcast_outputs import BroadcastEnvelope
from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    ProducerCase,
    ProducerCaseStore,
    _validate_case,
    apply_producer_command,
    inspect_producer_case,
)
from matchdesk.domain.producer_execution_grants import ProducerGrantAttempt
from matchdesk.domain.producer_identity import (
    EntitlementResolver,
    ProducerIdentityPolicy,
    TrustedKeyResolver,
    verify_producer_access_token,
)

CommandAction = Literal["create", "edit", "approve", "reject"]
_T = TypeVar("_T", bound=BaseModel)


class CreateProducerRequest(BaseModel):
    """Confirm the exact host-owned source binding; never accept case payloads."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    binding: ApprovalBinding


class ProducerDecisionRequest(BaseModel):
    """Require a fresh generation and exact evidence/content before any mutation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    binding: ApprovalBinding
    expected_generation: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=256)


class ProducerEditRequest(ProducerDecisionRequest):
    """Submit only a typed next-version draft; the host validates its provenance."""

    revised_output: BroadcastEnvelope


class ProducerSourceResolver(Protocol):
    """Trusted host source for an unapproved case, never arbitrary request JSON."""

    def resolve(
        self,
        *,
        actor: HostVerifiedActor,
        session_id: str,
        output_id: str,
    ) -> ProducerCase | None:
        """Return a source-validated, unapproved initial case or deny access."""


class ProducerMutationStore(ProducerCaseStore, Protocol):
    """Atomic create/CAS adapter with an append-only review audit."""

    def create(self, case: ProducerCase) -> bool:
        """Persist one initial generation and its first audit entry atomically."""


class ProducerGrantMutationStore(ProducerMutationStore, Protocol):
    """A store that always consumes an exact grant inside its case/audit transaction."""

    def create_with_execution_grant(
        self, case: ProducerCase, *, grant: ProducerGrantAttempt
    ) -> bool:
        """Create case and audit atomically with the execution grant."""

    def replace_with_execution_grant(
        self, case: ProducerCase, *, expected_generation: int, grant: ProducerGrantAttempt
    ) -> bool:
        """CAS one case and append audit inside its grant-consumption transaction."""


class ProducerTransactionalGrantSelector(Protocol):
    """Host-owned lookup of an already authorised, opaque, exact-action grant.

    The selector must validate human step-up and revocation against independent
    server-side policy. Never construct its grant from request-supplied UUIDs,
    role headers, cookies, prompts or unverified MFA assertions.
    """

    def select(
        self,
        *,
        actor: HostVerifiedActor,
        action: CommandAction,
        session_id: str,
        output_id: str,
        binding: ApprovalBinding,
        expected_generation: int,
    ) -> ProducerGrantAttempt | None:
        """Return the host-held grant reference for this exact action or deny."""


class ProducerCommandGrantResolver(Protocol):
    """Fresh independently checked, exact-action authorization by trusted host.

    A production resolver must prove step-up and actor/resource authorization
    without using request-controlled role, MFA, approval or tenant claims.
    Returning anything other than the literal boolean True denies the action.
    """

    def authorize(
        self,
        *,
        actor: HostVerifiedActor,
        action: CommandAction,
        session_id: str,
        output_id: str,
        binding: ApprovalBinding,
        expected_generation: int,
    ) -> bool:
        """Allow only an independently authorized action on an exact case version."""


async def _body(request: Request, kind: type[_T]) -> _T | None:
    """Reject ambiguous JSON, unknown fields, and non-normalized review reasons."""
    try:
        data = json.loads(
            await request.body(),
            object_pairs_hook=_unique_pairs,
            parse_constant=_invalid_constant,
        )
        parsed = kind.model_validate(data)
        if isinstance(parsed, ProducerDecisionRequest) and (
            not parsed.reason.strip() or parsed.reason != parsed.reason.strip()
        ):
            return None
        return parsed
    except (TypeError, ValueError, UnicodeError):
        return None


def _actor(
    token: str,
    *,
    policy: ProducerIdentityPolicy,
    keys: TrustedKeyResolver,
    entitlements: EntitlementResolver,
    session_id: str,
) -> HostVerifiedActor | JSONResponse:
    """Resolve a fresh scoped workforce actor; an access token alone is never a grant."""
    try:
        actor = verify_producer_access_token(
            token, policy=policy, keys=keys, entitlements=entitlements
        )
        # Re-enforce the exact policy at the HTTP boundary, independently of
        # the token verifier and host-specific grant resolver. A non-producer
        # principal must never reach the source or durable mutation adapters.
        if (
            type(actor) is not HostVerifiedActor
            or actor.tenant_id != policy.tenant_id
            or actor.issuer != policy.issuer
            or "producer" not in actor.roles
            or session_id not in actor.permitted_sessions
        ):
            return _response("Producer command denied", 403)
        return actor
    except (PermissionError, LookupError, TypeError, ValueError):
        return _response("Producer command denied", 403)
    except Exception:
        return _response("Producer command unavailable", 503)


def _result(case: ProducerCase, *, action: CommandAction, status: int) -> JSONResponse:
    """Return a minimal state receipt, never the audit actors, source events or tokens."""
    return JSONResponse(
        {
            "session_id": case.output.session_id,
            "output_id": case.output.output_id,
            "generation": case.generation,
            "item_version": case.output.binding.item_version,
            "review_status": case.review.status,
            "action": action,
            "mode": "opt_in_development_only",
            "publication_enabled": False,
        },
        status_code=status,
        headers=_headers(),
    )


def _build_producer_command_router(
    *,
    policy: ProducerIdentityPolicy,
    keys: TrustedKeyResolver,
    entitlements: EntitlementResolver,
    grants: ProducerCommandGrantResolver | None,
    transactional_grants: ProducerTransactionalGrantSelector | None,
    source: ProducerSourceResolver,
    store: ProducerMutationStore,
) -> APIRouter:
    """Build either the offline legacy route or the strictly grant-backed candidate."""
    # Exactly one host authority path exists per router instance. In grant-backed
    # mode there is NO fallback to a boolean approval or unguarded case write.
    if (grants is None) == (transactional_grants is None):
        raise ValueError("Select exactly one trusted producer grant authority")
    requirements = [
        (keys, "resolve"),
        (entitlements, "resolve"),
        (source, "resolve"),
        (store, "load"),
    ]
    if transactional_grants is None:
        requirements.extend(
            ((grants, "authorize"), (store, "create"), (store, "replace_if_generation"))
        )
    else:
        requirements.extend(
            (
                (transactional_grants, "select"),
                (store, "create_with_execution_grant"),
                (store, "replace_with_execution_grant"),
            )
        )
    if type(policy) is not ProducerIdentityPolicy or any(
        not callable(getattr(dependency, method, None)) for dependency, method in requirements
    ):
        raise ValueError("Producer commands require explicitly trusted host dependencies")
    policy.__post_init__()
    locked_store = cast(ProducerGrantMutationStore, store)

    router = APIRouter(prefix="/api/workforce/producer", tags=["workforce-producer"])

    def host_authorization(
        *,
        actor: HostVerifiedActor,
        action: CommandAction,
        session_id: str,
        output_id: str,
        binding: ApprovalBinding,
        expected_generation: int,
    ) -> ProducerGrantAttempt | bool | JSONResponse:
        """Fail closed unless the exact host-selected grant or legacy DEV decision exists."""
        try:
            if transactional_grants is not None:
                selected = transactional_grants.select(
                    actor=actor,
                    action=action,
                    session_id=session_id,
                    output_id=output_id,
                    binding=binding,
                    expected_generation=expected_generation,
                )
                # Recheck the returned grant against the *verified* actor and
                # current case. A defective selector cannot retarget a grant.
                if (
                    type(selected) is not ProducerGrantAttempt
                    or selected.actor != actor
                    or selected.action != action
                    or selected.session_id != session_id
                    or selected.output_id != output_id
                    or selected.binding != binding
                    or selected.expected_generation != expected_generation
                ):
                    return _response("Producer command denied", 403)
                return selected
            if (
                grants is None
                or grants.authorize(
                    actor=actor,
                    action=action,
                    session_id=session_id,
                    output_id=output_id,
                    binding=binding,
                    expected_generation=expected_generation,
                )
                is not True
            ):
                return _response("Producer command denied", 403)
            return True
        except (PermissionError, LookupError, TypeError, ValueError):
            return _response("Producer command denied", 403)
        except Exception:
            return _response("Producer command unavailable", 503)

    @router.post("/sessions/{session_id}/cases/{output_id}/create")
    async def create(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Create exactly one initially unapproved record from host-owned evidence."""
        token = _request_shape(request, session_id, output_id)
        if token is None:
            return _response("Producer command denied", 401)
        actor = _actor(
            token,
            policy=policy,
            keys=keys,
            entitlements=entitlements,
            session_id=session_id,
        )
        if isinstance(actor, JSONResponse):
            return actor
        command = await _body(request, CreateProducerRequest)
        if command is None:
            return _response("Invalid producer create request", 400)
        try:
            case = source.resolve(actor=actor, session_id=session_id, output_id=output_id)
            if case is None:
                return _response("Producer command denied", 403)
            _validate_case(case)
            if (
                case.tenant_id != actor.tenant_id
                or case.output.session_id != session_id
                or case.output.output_id != output_id
                or case.generation != 1
                or case.review.status != "pending_verification"
                or case.review.audit[0].actor_id != actor.subject
                or case.output.binding != command.binding
            ):
                return _response("Producer source or binding changed", 409)
        except (PermissionError, LookupError):
            return _response("Producer command denied", 403)
        except ValueError:
            return _response("Producer source or binding changed", 409)
        except Exception:
            return _response("Producer command unavailable", 503)
        permission = host_authorization(
            actor=actor,
            action="create",
            session_id=session_id,
            output_id=output_id,
            binding=case.output.binding,
            expected_generation=0,
        )
        if isinstance(permission, JSONResponse):
            return permission
        try:
            saved = (
                locked_store.create_with_execution_grant(case, grant=permission)
                if type(permission) is ProducerGrantAttempt
                else store.create(case)
            )
        except (PermissionError, ValueError):
            return _response("Producer command denied", 403)
        except Exception:
            return _response("Producer command unavailable", 503)
        if saved is not True:
            return _response("Producer case exists; reload instead of replaying", 409)
        return _result(case, action="create", status=201)

    async def mutate(
        session_id: str,
        output_id: str,
        request: Request,
        *,
        action: Literal["edit", "approve", "reject"],
    ) -> JSONResponse:
        """Authorize, validate, audit and CAS exactly one current-version transition."""
        token = _request_shape(request, session_id, output_id)
        if token is None:
            return _response("Producer command denied", 401)
        actor = _actor(
            token,
            policy=policy,
            keys=keys,
            entitlements=entitlements,
            session_id=session_id,
        )
        if isinstance(actor, JSONResponse):
            return actor
        command = await _body(
            request, ProducerEditRequest if action == "edit" else ProducerDecisionRequest
        )
        if command is None:
            return _response("Invalid producer command request", 400)
        try:
            case = inspect_producer_case(
                store, actor=actor, session_id=session_id, output_id=output_id
            )
        except (PermissionError, LookupError):
            return _response("Producer command denied", 403)
        except Exception:
            return _response("Producer command unavailable", 503)
        if case.generation != command.expected_generation or case.output.binding != command.binding:
            return _response("Producer case changed; reload before acting", 409)
        permission = host_authorization(
            actor=actor,
            action=action,
            session_id=session_id,
            output_id=output_id,
            binding=case.output.binding,
            expected_generation=case.generation,
        )
        if isinstance(permission, JSONResponse):
            return permission
        try:
            revised = apply_producer_command(
                case,
                actor=actor,
                expected_generation=command.expected_generation,
                command=action,
                reason=command.reason,
                revised_output=(
                    command.revised_output if isinstance(command, ProducerEditRequest) else None
                ),
            )
        except (RuntimeError, ValueError):
            return _response("Producer version or decision rejected", 409)
        except Exception:
            return _response("Producer command unavailable", 503)
        try:
            saved = (
                locked_store.replace_with_execution_grant(
                    revised, expected_generation=command.expected_generation, grant=permission
                )
                if type(permission) is ProducerGrantAttempt
                else store.replace_if_generation(
                    revised, expected_generation=command.expected_generation
                )
            )
        except Exception:
            return _response("Producer command unavailable", 503)
        if saved is not True:
            return _response("Producer case changed; reload before acting", 409)
        return _result(revised, action=action, status=200)

    @router.post("/sessions/{session_id}/cases/{output_id}/edit")
    async def edit(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Change a draft; clear any previous approval until fresh reverification."""
        return await mutate(session_id, output_id, request, action="edit")

    @router.post("/sessions/{session_id}/cases/{output_id}/approve")
    async def approve(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Record a host-authorized human decision; never enable publication."""
        return await mutate(session_id, output_id, request, action="approve")

    @router.post("/sessions/{session_id}/cases/{output_id}/reject")
    async def reject(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Reject an exact-version draft with append-only evidence and no publication."""
        return await mutate(session_id, output_id, request, action="reject")

    return router


def create_producer_command_router(
    *,
    policy: ProducerIdentityPolicy,
    keys: TrustedKeyResolver,
    entitlements: EntitlementResolver,
    grants: ProducerCommandGrantResolver,
    source: ProducerSourceResolver,
    store: ProducerMutationStore,
) -> APIRouter:
    """Maintain the default-disabled, boolean-grant offline compatibility router.

    This compatibility route is NOT approved for operational producer mutation:
    its separate boolean host decision cannot prevent an in-flight revocation.
    """
    return _build_producer_command_router(
        policy=policy,
        keys=keys,
        entitlements=entitlements,
        grants=grants,
        transactional_grants=None,
        source=source,
        store=store,
    )


def create_grant_backed_producer_command_router(
    *,
    policy: ProducerIdentityPolicy,
    keys: TrustedKeyResolver,
    entitlements: EntitlementResolver,
    grants: ProducerTransactionalGrantSelector,
    source: ProducerSourceResolver,
    store: ProducerGrantMutationStore,
) -> APIRouter:
    """Build an opt-in, grant-backed DEV candidate without legacy store fallback.

    Real workforce sign-in, MFA step-up, host issuance and manual operator
    acceptance remain unqualified. Do not mount in the shipped default app.
    """
    return _build_producer_command_router(
        policy=policy,
        keys=keys,
        entitlements=entitlements,
        grants=None,
        transactional_grants=grants,
        source=source,
        store=store,
    )
