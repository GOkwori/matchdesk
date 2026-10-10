"""Optional customer session HTTP routes; never mounted by the deployed app.

These routes require host-injected durable sessions, exact HTTPS origin and a
server-only CSRF secret. They do not support OIDC login or producer authority.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from matchdesk.domain.browser_session_security import (
    CustomerBrowserPolicy,
    authorize_customer_mutation,
    clear_customer_session_cookie,
    customer_session_cookie,
    issue_customer_csrf,
)
from matchdesk.domain.customer_sessions import (
    CustomerSession,
    CustomerSessionStore,
    resolve_customer_session,
)

_COOKIE = "__Host-matchdesk_customer"


class CustomerLifecycleStore(CustomerSessionStore, Protocol):
    """Trusted persistent session store supporting atomic lifecycle mutations."""

    def rotate(
        self, opaque_session_id: str, *, now: datetime | None = None
    ) -> CustomerSession | None:
        """Rotate a live token atomically, preserving the original expiry."""

    def revoke(self, opaque_session_id: str) -> bool:
        """Persist revocation before clearing the browser cookie."""


def _headers() -> dict[str, str]:
    """Suppress caching, referrer leaks and content sniffing for session data."""
    return {
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Vary": "Cookie, Origin, Sec-Fetch-Site",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "X-Frame-Options": "DENY",
    }


def _browser(request: Request, policy: CustomerBrowserPolicy) -> None:
    """Reject spoofed hosts, insecure transport and cross-site browser requests."""
    # Never treat unqualified client proxy metadata as trusted HTTPS evidence.
    # A reviewed gateway must strip forwarding headers before routing traffic.
    forwarded = any(
        name.lower() == "forwarded"
        or name.lower().startswith(("x-forwarded-", "x-original-"))
        for name in request.headers
    )
    hosts = request.headers.getlist("host")
    fetch_sites = request.headers.getlist("sec-fetch-site")
    if (
        forwarded
        or request.url.scheme != "https"
        or len(hosts) != 1
        or f"https://{hosts[0]}" != policy.public_origin
        or len(fetch_sites) > 1
        or (fetch_sites and fetch_sites[0] != "same-origin")
    ):
        raise HTTPException(status_code=403, detail="Customer browser origin denied")


def _cookie(request: Request) -> str:
    """Reject cookie tossing, multiple Cookie fields and malformed session IDs."""
    headers = request.headers.getlist("cookie")
    if len(headers) != 1 or len(headers[0]) > 4096:
        raise HTTPException(status_code=401, detail="Customer session unavailable")
    found: list[str] = []
    for segment in headers[0].split(";"):
        name, equals, value = segment.strip().partition("=")
        if name == _COOKIE:
            if not equals:
                raise HTTPException(status_code=401, detail="Customer session unavailable")
            found.append(value)
    if (
        len(found) != 1
        or len(found[0]) != 64
        or any(char not in "0123456789abcdef" for char in found[0])
    ):
        raise HTTPException(status_code=401, detail="Customer session unavailable")
    return found[0]


def _active(token: str, store: CustomerLifecycleStore) -> CustomerSession:
    """Only a persisted and unrevoked customer session grants read access."""
    try:
        return resolve_customer_session(token, store=store)
    except (ValueError, TypeError, PermissionError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Customer session unavailable",
            headers=_headers(),
        ) from exc
    except Exception as exc:
        # Host-owned database faults must not reveal connection or token details.
        raise HTTPException(
            status_code=503,
            detail="Customer session service unavailable",
            headers=_headers(),
        ) from exc


def _write(
    request: Request,
    token: str,
    *,
    store: CustomerLifecycleStore,
    policy: CustomerBrowserPolicy,
    secret: bytes,
) -> None:
    """Require one exact Origin and one session-bound CSRF proof before mutation."""
    origins = request.headers.getlist("origin")
    proofs = request.headers.getlist("x-matchdesk-csrf")
    fetch_sites = request.headers.getlist("sec-fetch-site")
    if len(origins) != 1 or len(proofs) != 1 or len(fetch_sites) > 1:
        raise HTTPException(status_code=403, detail="Customer CSRF verification denied")
    try:
        authorize_customer_mutation(
            token,
            store=store,
            policy=policy,
            secret=secret,
            method=request.method,
            request_origin=origins[0],
            csrf_header=proofs[0],
            fetch_site=fetch_sites[0] if fetch_sites else None,
        )
    except (PermissionError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=403,
            detail="Customer CSRF verification denied",
            headers=_headers(),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Customer session service unavailable",
            headers=_headers(),
        ) from exc


def create_customer_session_router(
    *, store: CustomerLifecycleStore, policy: CustomerBrowserPolicy, csrf_secret: bytes
) -> APIRouter:
    """Construct opt-in routes only for a host that supplies reviewed dependencies."""
    if not isinstance(policy, CustomerBrowserPolicy):
        raise ValueError("A reviewed customer browser policy is required")
    policy.__post_init__()
    if not isinstance(csrf_secret, bytes) or len(csrf_secret) < 32:
        raise ValueError("A server-only 256-bit CSRF key is required")
    if any(not callable(getattr(store, name, None)) for name in ("load", "rotate", "revoke")):
        raise ValueError("A trusted customer lifecycle store is required")

    router = APIRouter(prefix="/api/customer/session", tags=["customer-session"])

    @router.get("")
    def status(request: Request) -> JSONResponse:
        """Expose expiry only; never an email, raw token, identity or role."""
        _browser(request, policy)
        record = _active(_cookie(request), store)
        return JSONResponse(
            {"authenticated": True, "expires_at": record.expires_at.isoformat()},
            headers=_headers(),
        )

    @router.get("/csrf")
    def csrf(request: Request) -> JSONResponse:
        """Issue a same-origin CSRF token after the trusted session lookup."""
        _browser(request, policy)
        token = _cookie(request)
        _active(token, store)
        try:
            proof = issue_customer_csrf(token, store=store, policy=policy, secret=csrf_secret)
        except PermissionError as exc:
            raise HTTPException(
                status_code=401, detail="Customer session unavailable", headers=_headers()
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail="Customer session service unavailable", headers=_headers()
            ) from exc
        return JSONResponse({"csrf_token": proof}, headers=_headers())

    @router.post("/renew")
    def renew(request: Request) -> JSONResponse:
        """Atomically revoke old bearer and set a new host-only session cookie."""
        _browser(request, policy)
        token = _cookie(request)
        _write(request, token, store=store, policy=policy, secret=csrf_secret)
        try:
            successor = store.rotate(token)
        except Exception as exc:
            # No success response can be issued after an uncertain database write.
            raise HTTPException(
                status_code=503, detail="Customer renewal unavailable", headers=_headers()
            ) from exc
        if successor is None:
            raise HTTPException(
                status_code=401, detail="Customer renewal denied", headers=_headers()
            )
        if not isinstance(successor, CustomerSession):
            raise HTTPException(
                status_code=503, detail="Customer renewal unavailable", headers=_headers()
            )
        try:
            cookie = customer_session_cookie(successor.session_id, store=store, policy=policy)
            proof = issue_customer_csrf(
                successor.session_id, store=store, policy=policy, secret=csrf_secret
            )
            headers = _headers()
            headers["Set-Cookie"] = cookie
            # Construct the response before leaving the post-commit cleanup guard.
            return JSONResponse({"renewed": True, "csrf_token": proof}, headers=headers)
        except Exception as exc:
            # Rotation already committed: best-effort revoke the successor.
            # Never return its bearer, a Set-Cookie header or an authenticated
            # success when post-commit serialization or revalidation fails.
            try:
                store.revoke(successor.session_id)
            except Exception:
                # A storage outage can prevent cleanup; the bearer was not sent.
                pass
            raise HTTPException(
                status_code=503, detail="Customer renewal unavailable", headers=_headers()
            ) from exc

    @router.post("/logout")
    def logout(request: Request) -> Response:
        """Revoke a live customer session before expiring its cookie."""
        _browser(request, policy)
        token = _cookie(request)
        _write(request, token, store=store, policy=policy, secret=csrf_secret)
        try:
            revoked = store.revoke(token)
        except Exception as exc:
            # Never acknowledge a logout if the revocation commit is unknown.
            raise HTTPException(
                status_code=503, detail="Customer logout unavailable", headers=_headers()
            ) from exc
        if not revoked:
            raise HTTPException(
                status_code=401, detail="Customer logout denied", headers=_headers()
            )
        headers = _headers()
        headers["Set-Cookie"] = clear_customer_session_cookie()
        return Response(status_code=204, headers=headers)

    return router
