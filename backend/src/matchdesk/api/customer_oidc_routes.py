"""Opt-in, fail-closed customer OIDC start and browser callback HTTP boundary.

This router is never mounted by the shipped MatchDesk application. A reviewed
host must inject the durable single-use state store, trusted broker policy,
code exchanger, issuer-bound signing keys, registered accounts, and sessions.
No social provider tokens, roles, or authorization codes enter response bodies.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from matchdesk.domain.browser_session_security import CustomerBrowserPolicy
from matchdesk.domain.customer_identity import CustomerAccountDirectory, CustomerSigningKeys
from matchdesk.domain.customer_oidc_completion import (
    CustomerCodeExchanger,
    CustomerSessionWriter,
    complete_customer_oidc_sign_in,
)
from matchdesk.domain.oidc_login import (
    CustomerOidcPolicy,
    OidcLoginAttemptStore,
    begin_customer_oidc_login,
    clear_oidc_login_cookie,
    finish_customer_oidc_login,
)

_BINDING_COOKIE = "__Host-matchdesk_oidc"


def _security_headers() -> dict[str, str]:
    """Forbid caches, URL-referrer disclosure, framing, and content sniffing."""
    return {
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "X-Frame-Options": "DENY",
        "Vary": "Cookie, Origin, Sec-Fetch-Site",
    }


def _browser(request: Request, *, origin: str, callback: bool) -> None:
    """Require the exact HTTPS host; distinguish top-level broker navigation.

    The callback permits cross-site *navigation*, not cross-site XHR. PKCE,
    state, issuer and an independent HttpOnly browser cookie defend login CSRF.
    The start endpoint instead requires an exact same-origin POST Origin.
    """
    headers = request.headers
    hosts = headers.getlist("host")
    origins = headers.getlist("origin")
    sites = headers.getlist("sec-fetch-site")
    modes = headers.getlist("sec-fetch-mode")
    destinations = headers.getlist("sec-fetch-dest")
    forwarding = any(
        name.lower() == "forwarded" or name.lower().startswith(("x-forwarded-", "x-original-"))
        for name in headers
    )
    if (
        forwarding
        or request.url.scheme != "https"
        or len(hosts) != 1
        or f"https://{hosts[0]}" != origin
        or len(origins) > 1
        or len(sites) > 1
        or len(modes) > 1
        or len(destinations) > 1
    ):
        raise PermissionError("Customer OIDC browser origin denied")
    if callback:
        if (
            origins
            or (sites and sites[0] not in {"same-origin", "same-site", "cross-site", "none"})
            or (modes and modes[0] != "navigate")
            or (destinations and destinations[0] != "document")
        ):
            raise PermissionError("Customer OIDC callback navigation denied")
    elif origins != [origin] or (sites and sites[0] != "same-origin"):
        raise PermissionError("Customer OIDC initiation denied")


def _callback_query(request: Request) -> tuple[str, str, str | None, str | None]:
    """Reject duplicated, unfamiliar or mixed success/error callback parameters."""
    if len(request.scope.get("query_string", b"")) > 8192:
        raise PermissionError("Customer OIDC callback query too long")
    pairs = list(request.query_params.multi_items())
    fields = [key for key, _ in pairs]
    if len(fields) != len(set(fields)):
        raise PermissionError("Duplicate OIDC callback parameter")
    values = dict(pairs)
    if set(values) not in ({"state", "iss", "code"}, {"state", "iss", "error"}):
        raise PermissionError("Unexpected OIDC callback parameter")
    return values["state"], values["iss"], values.get("code"), values.get("error")


def _binding_cookie(request: Request) -> str:
    """Reject missing, duplicate or malformed host-only browser-binding cookies."""
    cookies = request.headers.getlist("cookie")
    if len(cookies) != 1 or len(cookies[0]) > 4096:
        raise PermissionError("OIDC browser binding unavailable")
    matches: list[str] = []
    for segment in cookies[0].split(";"):
        name, equals, value = segment.strip().partition("=")
        if name == _BINDING_COOKIE:
            if not equals:
                raise PermissionError("OIDC browser binding unavailable")
            matches.append(value)
    if (
        len(matches) != 1
        or len(matches[0]) != 43
        or any(not ch.isascii() or not (ch.isalnum() or ch in "-_") for ch in matches[0])
    ):
        raise PermissionError("OIDC browser binding unavailable")
    return matches[0]


def _denied(status_code: int) -> Response:
    """Return a generic, no-store failure and always clear temporary login state."""
    message = "Customer sign-in denied" if status_code == 401 else "Customer sign-in unavailable"
    response = JSONResponse(
        {"detail": message}, status_code=status_code, headers=_security_headers()
    )
    response.headers.append("set-cookie", clear_oidc_login_cookie())
    return response


def create_customer_oidc_router(
    *,
    policy: CustomerOidcPolicy,
    browser: CustomerBrowserPolicy,
    attempts: OidcLoginAttemptStore,
    exchanger: CustomerCodeExchanger,
    keys: CustomerSigningKeys,
    directory: CustomerAccountDirectory,
    sessions: CustomerSessionWriter,
) -> APIRouter:
    """Create isolated OIDC endpoints only with explicit host-trusted dependencies.

    The factory itself activates no service. The default app intentionally has
    no OIDC routes and does not import or construct a live code exchanger.
    """
    if not isinstance(policy, CustomerOidcPolicy) or not isinstance(browser, CustomerBrowserPolicy):
        raise ValueError("OIDC HTTP requires a reviewed broker and browser policy")
    policy.__post_init__()
    browser.__post_init__()
    if policy.public_origin != browser.public_origin:
        raise ValueError("OIDC HTTP origin and cookie scope must agree")
    dependencies = (
        (attempts, ("create", "consume")),
        (exchanger, ("redeem",)),
        (keys, ("resolve",)),
        (directory, ("lookup",)),
        (sessions, ("create", "load", "revoke")),
    )
    if any(not callable(getattr(obj, name, None)) for obj, names in dependencies for name in names):
        raise ValueError("OIDC HTTP requires trusted stores and token verification")

    router = APIRouter(prefix="/api/customer/oidc", tags=["customer-oidc"])

    @router.post("/start")
    def start(request: Request) -> Response:
        """Reserve one PKCE state under a same-origin POST and redirect to the broker."""
        try:
            _browser(request, origin=browser.public_origin, callback=False)
            if request.url.query:
                raise PermissionError("OIDC start takes no query input")
            initiated = begin_customer_oidc_login(policy=policy, store=attempts)
        except PermissionError:
            return _denied(401)
        except Exception:
            return _denied(503)
        response = RedirectResponse(
            url=initiated.authorization_url, status_code=303, headers=_security_headers()
        )
        response.headers.append("set-cookie", initiated.set_cookie)
        return response

    @router.get("/callback")
    def callback(request: Request) -> Response:
        """Consume one browser-bound callback before any token or session creation.

        The fixed post-login redirect is independent of user/provider input.
        A gateway must redact authorization-code query strings in access logs.
        """
        try:
            _browser(request, origin=browser.public_origin, callback=True)
            state, issuer, code, error = _callback_query(request)
            binding = _binding_cookie(request)
            pending = finish_customer_oidc_login(
                policy=policy,
                store=attempts,
                state=state,
                browser_binding=binding,
                issuer=issuer,
                code=code,
                error=error,
            )
            result = complete_customer_oidc_sign_in(
                pending=pending,
                policy=policy,
                browser=browser,
                exchanger=exchanger,
                keys=keys,
                directory=directory,
                sessions=sessions,
            )
        except PermissionError:
            return _denied(401)
        except Exception:
            return _denied(503)
        response = RedirectResponse(url="/", status_code=303, headers=_security_headers())
        response.headers.append("set-cookie", clear_oidc_login_cookie())
        response.headers.append("set-cookie", result.set_cookie)
        return response

    return router
