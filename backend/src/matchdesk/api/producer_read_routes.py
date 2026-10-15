"""Optional read-only workforce producer inspection routes, never auto-mounted.

Identity must be verified against pinned workforce issuer/signing keys and
current server-side entitlements on every request. No command/write routes are
registered. Customer cookies or headers cannot supply producer authority.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from matchdesk.domain.producer_commands import ProducerCaseReader, inspect_producer_case
from matchdesk.domain.producer_identity import (
    EntitlementResolver,
    ProducerIdentityPolicy,
    TrustedKeyResolver,
    verify_producer_access_token,
)

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def _headers() -> dict[str, str]:
    """Prevent caching and cross-origin leakage of producer case material."""
    return {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "X-Frame-Options": "DENY",
        "Vary": "Authorization",
    }


def create_producer_read_router(
    *,
    policy: ProducerIdentityPolicy,
    keys: TrustedKeyResolver,
    entitlements: EntitlementResolver,
    reader: ProducerCaseReader,
) -> APIRouter:
    """Build an opt-in inspection router with host-supplied trust dependencies."""
    if type(policy) is not ProducerIdentityPolicy or any(
        not callable(getattr(obj, method, None))
        for obj, method in ((keys, "resolve"), (entitlements, "resolve"), (reader, "load"))
    ):
        raise ValueError("Producer read API requires an exact policy and trusted dependencies")
    policy.__post_init__()
    router = APIRouter(prefix="/api/workforce/producer", tags=["workforce-producer"])

    @router.get("/sessions/{session_id}/cases/{output_id}")
    def inspect(session_id: str, output_id: str, request: Request) -> JSONResponse:
        """Inspect a case only after independently verified actor and session grants."""
        headers = _headers()
        # Reject ambiguous credentials, query overrides, browser session cookies,
        # forwarding spoofing and malformed resource identifiers.
        authorization = request.headers.getlist("authorization")
        if (
            len(authorization) != 1
            or request.url.query
            or request.headers.getlist("cookie")
            or any(
                name.lower() == "forwarded"
                or name.lower().startswith(("x-forwarded-", "x-original-"))
                for name in request.headers
            )
            or not _IDENTIFIER.fullmatch(session_id)
            or not _IDENTIFIER.fullmatch(output_id)
        ):
            return JSONResponse(
                {"detail": "Producer inspection denied"}, status_code=401, headers=headers
            )
        scheme, separator, token = authorization[0].partition(" ")
        if scheme.lower() != "bearer" or separator != " " or not token or token.strip() != token:
            return JSONResponse(
                {"detail": "Producer inspection denied"}, status_code=401, headers=headers
            )
        try:
            actor = verify_producer_access_token(
                token, policy=policy, keys=keys, entitlements=entitlements
            )
            case = inspect_producer_case(
                reader, actor=actor, session_id=session_id, output_id=output_id
            )
        except (PermissionError, LookupError, ValueError, TypeError):
            return JSONResponse(
                {"detail": "Producer inspection denied"}, status_code=403, headers=headers
            )
        except Exception:
            return JSONResponse(
                {"detail": "Producer inspection unavailable"}, status_code=503, headers=headers
            )
        # Deliberately minimal: no stored audit actor identities, source events,
        # tenant identifiers, authorization tokens or approval-command capability.
        return JSONResponse(
            {
                "output_id": case.output.output_id,
                "session_id": case.output.session_id,
                "generation": case.generation,
                "review_status": case.review.status,
                "item_version": case.output.binding.item_version,
                "mode": "authenticated_read_only",
                "publication_enabled": False,
            },
            headers=headers,
        )

    return router
