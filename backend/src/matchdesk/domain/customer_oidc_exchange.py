"""Pinned, bounded OIDC authorization-code redemption for the customer BFF.

The caller supplies a consumed PKCE transaction and a host-held confidential
client credential. This module talks only to the reviewed External ID broker,
never follows redirects, never trusts upstream provider tokens, and returns
only the ID token for the separate signature/nonce verifier.

This is an opt-in adapter. The shipped API does not mount customer login.
"""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass, field
from http.client import HTTPSConnection
from typing import Protocol
from urllib.parse import urlencode, urlsplit

from matchdesk.domain.oidc_login import CustomerOidcPolicy, PendingOidcExchange

_MAX_BODY = 32768
_TIMEOUT_SECONDS = 5.0
_FIELDS = frozenset(
    {"grant_type", "client_id", "client_secret", "code", "code_verifier", "redirect_uri"}
)


@dataclass(frozen=True)
class OidcTokenPost:
    """One non-retryable request with secrets deliberately excluded from repr."""

    endpoint: str
    form: tuple[tuple[str, str], ...] = field(repr=False)
    timeout_seconds: float = _TIMEOUT_SECONDS
    max_response_bytes: int = _MAX_BODY


@dataclass(frozen=True)
class OidcTokenResponse:
    """Transport result; body may contain credentials and is not repr-safe."""

    status_code: int
    content_type: str
    body: bytes = field(repr=False)
    location: str | None = None
    redirected: bool = False


class OidcTokenTransport(Protocol):
    """Send one HTTPS form request without redirect, proxy or automatic retry."""

    def post(self, request: OidcTokenPost) -> OidcTokenResponse:
        """Return the capped response, never log the request or response body."""


def _valid_random(value: object) -> bool:
    """Accept only 256-bit unpadded base64url state-derived PKCE values."""
    return (
        isinstance(value, str)
        and len(value) == 43
        and all(ch.isascii() and (ch.isalnum() or ch in "-_") for ch in value)
    )


def _validated_endpoint(endpoint: str) -> str:
    """Refuse arbitrary hosts, ports, URLs and redirects before opening a socket."""
    try:
        parsed = urlsplit(endpoint)
        host = parsed.hostname
    except (ValueError, TypeError, AttributeError) as exc:
        raise PermissionError("OIDC token endpoint denied") from exc
    parts = parsed.path.split("/")
    if (
        parsed.scheme != "https"
        or not isinstance(host, str)
        or host.count(".") != 2
        or not host.endswith(".ciamlogin.com")
        or host.split(".")[0] == ""
        or not host.split(".")[0].replace("-", "").isalnum()
        or parsed.netloc != host
        or parsed.query
        or parsed.fragment
        or len(parts) != 5
        or parts[0] != ""
        or not parts[1]
        or parts[2:] != ["oauth2", "v2.0", "token"]
    ):
        raise PermissionError("OIDC token endpoint denied")
    return host


def _valid_pending(pending: PendingOidcExchange, policy: CustomerOidcPolicy) -> None:
    """Fail before network I/O if any code-exchange value escapes host trust."""
    if not isinstance(pending, PendingOidcExchange):
        raise PermissionError("OIDC code exchange requires a consumed transaction")
    if (
        pending.issuer != policy.broker.issuer
        or pending.client_id != policy.client_id
        or pending.token_endpoint != policy.token_endpoint
        or pending.redirect_uri != policy.redirect_uri
        or not _valid_random(pending.code_verifier)
        or not _valid_random(pending.nonce)
        or not isinstance(pending.authorization_code, str)
        or not 1 <= len(pending.authorization_code) <= 2048
        or any(not "!" <= ch <= "~" for ch in pending.authorization_code)
    ):
        raise PermissionError("OIDC code exchange is not host-bound")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys instead of accepting ambiguous token contents."""
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON token-response key")
        result[name] = value
    return result


def _invalid_constant(value: str) -> object:
    """Reject NaN and Infinity even if JSON parser extensions permit them."""
    raise ValueError("Nonstandard JSON constant")


def _decode_id_token(response: OidcTokenResponse) -> str:
    """Extract only the broker ID token; another verifier establishes identity."""
    if (
        not isinstance(response, OidcTokenResponse)
        or type(response.status_code) is not int
        or response.status_code != 200
        or response.redirected
        or response.location is not None
        or not isinstance(response.content_type, str)
        or response.content_type.split(";", 1)[0].strip().lower() != "application/json"
        or type(response.body) is not bytes
        or not 1 <= len(response.body) <= _MAX_BODY
    ):
        raise PermissionError("OIDC token response denied")
    try:
        document = json.loads(
            response.body.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise PermissionError("OIDC token response denied") from exc
    if not isinstance(document, dict):
        raise PermissionError("OIDC token response denied")
    token = document.get("id_token")
    if (
        not isinstance(token, str)
        or not 1 <= len(token) <= 16384
        or token.count(".") != 2
        or any(ch.isspace() or not ch.isascii() for ch in token)
    ):
        raise PermissionError("OIDC ID token unavailable")
    # Ignore access_token, refresh_token, roles, email and upstream provider
    # metadata. None of them can authenticate a MatchDesk customer.
    return token


class HttpsOidcTokenTransport:
    """Direct verified-TLS transport; no proxies, redirects or implicit retries."""

    def post(self, request: OidcTokenPost) -> OidcTokenResponse:
        """POST once, cap bytes during reading and redact all transport failures."""
        if not isinstance(request, OidcTokenPost):
            raise PermissionError("OIDC token request denied")
        host = _validated_endpoint(request.endpoint)
        names = [key for key, _ in request.form]
        if (
            len(names) != len(_FIELDS)
            or set(names) != _FIELDS
            or type(request.timeout_seconds) is not float
            or not 1.0 <= request.timeout_seconds <= 10.0
            or request.max_response_bytes != _MAX_BODY
        ):
            raise PermissionError("OIDC token request denied")
        connection: HTTPSConnection | None = None
        try:
            # The system trust store verifies the pinned host's certificate and
            # SNI; http.client does not consult proxy environment variables.
            connection = HTTPSConnection(
                host, timeout=request.timeout_seconds, context=ssl.create_default_context()
            )
            connection.request(
                "POST",
                urlsplit(request.endpoint).path,
                body=urlencode(request.form),
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cache-Control": "no-store",
                    "Connection": "close",
                },
            )
            reply = connection.getresponse()
            headers = reply.getheaders()
            content_types = [value for name, value in headers if name.lower() == "content-type"]
            encodings = [value for name, value in headers if name.lower() == "content-encoding"]
            if (
                reply.status != 200
                or len(content_types) != 1
                or content_types[0].split(";", 1)[0].strip().lower() != "application/json"
                or len(encodings) > 1
                or any(value.strip().lower() != "identity" for value in encodings)
                or any(name.lower() == "location" for name, _ in headers)
            ):
                raise PermissionError("OIDC broker did not return a direct JSON success")
            body = reply.read(request.max_response_bytes + 1)
            if len(body) > request.max_response_bytes:
                raise PermissionError("OIDC broker response is oversized")
            return OidcTokenResponse(
                status_code=reply.status,
                content_type=content_types[0],
                body=body,
            )
        except Exception:
            # Network errors, TLS diagnostics, client secrets and token bodies
            # cannot escape through errors visible to an HTTP caller.
            raise PermissionError("OIDC token transport denied") from None
        finally:
            if connection is not None:
                connection.close()


class BrokerCodeExchanger:
    """Confidential BFF token exchanger with a pinned, separately reviewed host."""

    def __init__(
        self,
        *,
        policy: CustomerOidcPolicy,
        client_secret: str,
        transport: OidcTokenTransport,
    ) -> None:
        """Require an injected secret, exact broker policy and explicit transport."""
        if not isinstance(policy, CustomerOidcPolicy):
            raise ValueError("Customer broker policy must be host configured")
        policy.__post_init__()
        _validated_endpoint(policy.token_endpoint)
        if (
            not isinstance(client_secret, str)
            or not 24 <= len(client_secret) <= 4096
            or any(not "!" <= char <= "~" for char in client_secret)
            or not callable(getattr(transport, "post", None))
        ):
            raise ValueError("OIDC exchange requires a protected confidential client")
        self._policy = policy
        self._secret = client_secret
        self._transport = transport

    def redeem(self, *, pending: PendingOidcExchange) -> str:
        """Redeem once with PKCE; return only an unverified broker ID token."""
        _valid_pending(pending, self._policy)
        form = (
            ("grant_type", "authorization_code"),
            ("client_id", self._policy.client_id),
            ("redirect_uri", self._policy.redirect_uri),
            ("code", pending.authorization_code),
            ("code_verifier", pending.code_verifier),
            ("client_secret", self._secret),
        )
        request = OidcTokenPost(endpoint=self._policy.token_endpoint, form=form)
        try:
            result = self._transport.post(request)
            return _decode_id_token(result)
        except Exception:
            # Never retry a possibly redeemed code: a replay must require a
            # new state, browser binding and authorisation request.
            raise PermissionError("OIDC code redemption denied") from None
