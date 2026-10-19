"""Opt-in producer reverification HTTP boundary for offline development qualification.

No producer command endpoint is mounted by the default MatchDesk application.
This module exposes ONLY evidence reverification, not approval, rejection, edit,
publication or a production identity-provider integration. Every request needs a
verified workforce bearer, fresh server-owned session grants and an independent
host-owned step-up authorization for the exact case version being changed.
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from matchdesk.domain.models import ApprovalBinding
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    ProducerCaseStore,
    apply_producer_command,
    inspect_producer_case,
)
from matchdesk.domain.producer_identity import (
    EntitlementResolver,
    ProducerIdentityPolicy,
    TrustedKeyResolver,
    verify_producer_access_token,
)

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class ReverificationRequest(BaseModel):
    """One exact-generation request; no client identity or authority fields."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    expected_generation: int = Field(ge=1)
    binding: ApprovalBinding
    reason: str = Field(min_length=1, max_length=256)


class ReverificationGrantResolver(Protocol):
    """External host authority for step-up and exact-resource command permission.

    A trusted implementation must verify a current workforce MFA/step-up grant,
    actor identity, session membership, intended action and resource binding.
    It must use server-controlled evidence, never headers or JSON authorization
    claims. There is deliberately no production implementation in this module.
    """

    def authorize(
        self,
        *,
        actor: HostVerifiedActor,
        session_id: str,
        output_id: str,
        binding: ApprovalBinding,
        expected_generation: int,
    ) -> bool:
        """Return exactly True only when this actor may reverify this version."""


def _headers() -> dict[str, str]:
    """Prevent caching or accidental browser disclosure of producer outcomes."""
    return {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "X-Frame-Options": "DENY",
        "Vary": "Authorization",
    }


def _response(detail: str, status: int) -> JSONResponse:
    """Hide internal authorization, SQL and verification failure details."""
    return JSONResponse({"detail": detail}, status_code=status, headers=_headers())


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys rather than accepting ambiguous client intent."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Ambiguous JSON object")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    """Disallow non-standard NaN and Infinity numeric literals."""
    raise ValueError("Invalid JSON constant")


def _request_shape(request: Request, session_id: str, output_id: str) -> str | None:
    """Require a single delegated bearer and server-to-server JSON transport."""
    authorization = request.headers.getlist("authorization")
    content_type = request.headers.getlist("content-type")
    if (
        len(authorization) != 1
        or len(content_type) != 1
        or content_type[0].lower() != "application/json"
        or request.url.query
        or request.headers.getlist("cookie")
        or request.headers.getlist("origin")
        or request.headers.getlist("referer")
        or any(
            name.lower() == "forwarded" or name.lower().startswith(("x-forwarded-", "x-original-"))
            for name in request.headers
        )
        or _IDENTIFIER.fullmatch(session_id) is None
        or _IDENTIFIER.fullmatch(output_id) is None
    ):
        return None
    scheme, separator, token = authorization[0].partition(" ")
    if (
        scheme.lower() != "bearer"
        or separator != " "
        or not token
        or token.strip() != token
        or " " in token
    ):
        return None
    return token


def create_producer_reverification_router(
    *,
    policy: ProducerIdentityPolicy,
    keys: TrustedKeyResolver,
    entitlements: EntitlementResolver,
    grants: ReverificationGrantResolver,
    store: ProducerCaseStore,
) -> APIRouter:
    """Create an explicit host-injected, default-disabled DEV command router.

    The trusted host must separately qualify the durable store's transaction/
    audit guarantees and genuinely human step-up authorization before activation.
    A synthetic test verifier does not confer operational production readiness.
    """
    requirements = (
        (keys, "resolve"),
        (entitlements, "resolve"),
        (grants, "authorize"),
        (store, "load"),
        (store, "replace_if_generation"),
    )
    if type(policy) is not ProducerIdentityPolicy or any(
        not callable(getattr(dependency, method, None)) for dependency, method in requirements
    ):
        raise ValueError("Producer reverification requires verified host-owned dependencies")
    policy.__post_init__()
    router = APIRouter(prefix="/api/workforce/producer", tags=["workforce-producer"])

    @router.post("/sessions/{session_id}/cases/{output_id}/reverify")
    async def reverify(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Reverify evidence with exact CAS; no human approval or delivery side effect."""
        token = _request_shape(request, session_id, output_id)
        if token is None:
            return _response("Producer reverification denied", 401)

        try:
            actor = verify_producer_access_token(
                token, policy=policy, keys=keys, entitlements=entitlements
            )
        except (PermissionError, ValueError, LookupError, TypeError):
            return _response("Producer reverification denied", 403)
        except Exception:
            return _response("Producer reverification unavailable", 503)

        # Independently recheck configured workforce trust if the token-verifier
        # integration is defective. Deny before reading cases or requesting grants.
        if (
            type(actor) is not HostVerifiedActor
            or actor.tenant_id != policy.tenant_id
            or actor.issuer != policy.issuer
            or "producer" not in actor.roles
            or session_id not in actor.permitted_sessions
        ):
            return _response("Producer reverification denied", 403)
        try:
            payload = json.loads(
                await request.body(),
                object_pairs_hook=_unique_pairs,
                parse_constant=_invalid_constant,
            )
            command = ReverificationRequest.model_validate(payload)
            if not command.reason.strip() or command.reason != command.reason.strip():
                raise ValueError("Invalid producer reason")
        except (ValueError, TypeError, ValidationError):
            return _response("Invalid reverification request", 400)

        try:
            case = inspect_producer_case(
                store, actor=actor, session_id=session_id, output_id=output_id
            )
        except (PermissionError, LookupError):
            return _response("Producer reverification denied", 403)
        except Exception:
            return _response("Producer reverification unavailable", 503)

        # The caller's complete immutable binding and generation must match a
        # validated stored snapshot, preventing action on unseen newer content.
        if case.generation != command.expected_generation or case.output.binding != command.binding:
            return _response("Producer case changed; reload before reverification", 409)

        try:
            allowed = grants.authorize(
                actor=actor,
                session_id=session_id,
                output_id=output_id,
                binding=case.output.binding,
                expected_generation=case.generation,
            )
        except (PermissionError, LookupError, ValueError):
            return _response("Producer reverification denied", 403)
        except Exception:
            return _response("Producer reverification unavailable", 503)
        if allowed is not True:
            return _response("Producer reverification denied", 403)

        try:
            revised = apply_producer_command(
                case,
                actor=actor,
                expected_generation=command.expected_generation,
                command="reverify",
                reason=command.reason,
            )
        except (ValueError, RuntimeError):
            return _response("Producer case cannot be reverified; reload", 409)
        except Exception:
            return _response("Producer reverification unavailable", 503)
        try:
            saved = store.replace_if_generation(
                revised, expected_generation=command.expected_generation
            )
        except Exception:
            return _response("Producer reverification unavailable", 503)
        if saved is not True:
            return _response("Producer case changed; reload before reverification", 409)

        return JSONResponse(
            {
                "output_id": revised.output.output_id,
                "session_id": revised.output.session_id,
                "generation": revised.generation,
                "review_status": revised.review.status,
                "item_version": revised.output.binding.item_version,
                "mode": "host_authorized_reverification",
                "approval_enabled": False,
                "publication_enabled": False,
            },
            headers=_headers(),
        )

    return router
