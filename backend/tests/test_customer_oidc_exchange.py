"""Offline and mocked-TLS regression tests for bounded broker code exchange."""

import json
from dataclasses import replace
from unittest.mock import Mock, patch

import pytest
from matchdesk.domain.customer_identity import CustomerBrokerPolicy
from matchdesk.domain.customer_oidc_exchange import (
    BrokerCodeExchanger,
    HttpsOidcTokenTransport,
    OidcTokenPost,
    OidcTokenResponse,
)
from matchdesk.domain.oidc_login import CustomerOidcPolicy, PendingOidcExchange

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://test.ciamlogin.com/{TENANT}/v2.0"
BASE = f"https://test.ciamlogin.com/{TENANT}"
CLIENT = "test-client"
ORIGIN = "https://matchdesk.example"
CLIENT_SECRET = "synthetic-injected-client-credential-for-offline-tests"


class CapturingTransport:
    """Fake that captures the pinned request without performing any network I/O."""

    def __init__(self, response: OidcTokenResponse) -> None:
        """Store a synthetic response and a call count for one-use tests."""
        self.response = response
        self.requests: list[OidcTokenPost] = []
        self.failure: Exception | None = None

    def post(self, request: OidcTokenPost) -> OidcTokenResponse:
        """Simulate one trusted HTTPS POST without parsing credentials."""
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return self.response


@pytest.fixture
def configured():
    """Use one synthetic reviewed External ID tenant and consumed login transaction."""
    policy = CustomerOidcPolicy(
        broker=CustomerBrokerPolicy(
            issuer=ISSUER,
            tenant_id=TENANT,
            audience="api://customer",
            client_ids=frozenset({CLIENT}),
        ),
        client_id=CLIENT,
        public_origin=ORIGIN,
        authorization_endpoint=f"{BASE}/oauth2/v2.0/authorize",
        token_endpoint=f"{BASE}/oauth2/v2.0/token",
        jwks_uri=f"{BASE}/discovery/v2.0/keys",
    )
    pending = PendingOidcExchange(
        issuer=ISSUER,
        client_id=CLIENT,
        token_endpoint=policy.token_endpoint,
        redirect_uri=policy.redirect_uri,
        authorization_code="single-use-code",
        code_verifier="a" * 43,
        nonce="b" * 43,
    )
    response = OidcTokenResponse(
        status_code=200,
        content_type="application/json; charset=utf-8",
        body=json.dumps(
            {
                "id_token": "header.payload.signature",
                "access_token": "must-not-escape",
                "refresh_token": "must-not-escape",
                "roles": ["producer"],
                "email": "false@example.com",
            }
        ).encode(),
    )
    return policy, pending, CapturingTransport(response)


def test_pinned_code_post_returns_id_token_only(configured) -> None:
    """Never disclose upstream access tokens, roles or the injected client secret."""
    policy, pending, transport = configured
    exchanger = BrokerCodeExchanger(
        policy=policy, client_secret=CLIENT_SECRET, transport=transport
    )
    assert exchanger.redeem(pending=pending) == "header.payload.signature"
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.endpoint == policy.token_endpoint
    assert request.timeout_seconds == 5.0
    assert request.max_response_bytes == 32768
    assert dict(request.form) == {
        "grant_type": "authorization_code",
        "client_id": CLIENT,
        "redirect_uri": policy.redirect_uri,
        "code": pending.authorization_code,
        "code_verifier": pending.code_verifier,
        "client_secret": CLIENT_SECRET,
    }
    for private in (pending.authorization_code, pending.code_verifier, CLIENT_SECRET):
        assert private not in repr(request)
        assert private not in repr(exchanger)
        assert private not in request.endpoint
    assert "refresh_token" not in repr(transport.response)
    assert "must-not-escape" not in repr(transport.response)


@pytest.mark.parametrize(
    "change",
    [
        {"issuer": "https://accounts.google.com"},
        {"client_id": "different-client"},
        {"token_endpoint": "https://attacker.example/token"},
        {"redirect_uri": "https://attacker.example/callback"},
        {"code_verifier": "bad"},
        {"nonce": "bad"},
        {"authorization_code": "code with spaces"},
        {"authorization_code": ""},
        {"authorization_code": "line\nbreak"},
        {"authorization_code": "x" * 2049},
    ],
)
def test_bad_exchange_never_reaches_http_transport(configured, change) -> None:
    """Tampered broker, PKCE, redirect and code are refused before network calls."""
    policy, pending, transport = configured
    exchanger = BrokerCodeExchanger(
        policy=policy, client_secret=CLIENT_SECRET, transport=transport
    )
    with pytest.raises(PermissionError):
        exchanger.redeem(pending=replace(pending, **change))
    assert not transport.requests


@pytest.mark.parametrize(
    "bad",
    ["", "short", "has spaces and 1234567890123456789", "x" * 4097, None],
)
def test_missing_or_invalid_confidential_credential_fails_closed(configured, bad) -> None:
    """A browser or unconfigured host cannot activate anonymous code redemption."""
    policy, _, transport = configured
    with pytest.raises(ValueError):
        BrokerCodeExchanger(policy=policy, client_secret=bad, transport=transport)


@pytest.mark.parametrize(
    "status,content_type,body,location,redirected",
    [
        (302, "application/json", b'{"id_token":"a.b.c"}', None, False),
        (200, "text/html", b'{"id_token":"a.b.c"}', None, False),
        (200, "application/json", b"<html>bad</html>", None, False),
        (200, "application/json", b'{"id_token":"a.b.c","id_token":"x.y.z"}', None, False),
        (200, "application/json", b'{"id_token":null}', None, False),
        (200, "application/json", b'{"id_token":42}', None, False),
        (200, "application/json", b'{"access_token":"a.b.c"}', None, False),
        (200, "application/json", b'{"id_token":"bad"}', None, False),
        (200, "application/json", b'["a.b.c"]', None, False),
        (200, "application/json", b'{"id_token":"a.b.c","score":NaN}', None, False),
        (200, "application/json", b"x" * 32769, None, False),
        (200, "application/json", b'{"id_token":"a.b.c"}', "https://evil.example", False),
        (200, "application/json", b'{"id_token":"a.b.c"}', None, True),
    ],
)
def test_bad_token_response_cannot_leave_exchange(
    configured, status, content_type, body, location, redirected
) -> None:
    """Reject redirects, malformed JSON and token substitution with no token logging."""
    policy, pending, transport = configured
    transport.response = OidcTokenResponse(
        status_code=status,
        content_type=content_type,
        body=body,
        location=location,
        redirected=redirected,
    )
    exchanger = BrokerCodeExchanger(
        policy=policy, client_secret=CLIENT_SECRET, transport=transport
    )
    with pytest.raises(PermissionError, match="code redemption denied") as failure:
        exchanger.redeem(pending=pending)
    assert len(transport.requests) == 1
    assert "a.b.c" not in str(failure.value)


def test_transport_error_is_redacted_and_not_retried(configured) -> None:
    """A network failure does not reveal secrets or replay a spent OIDC code."""
    policy, pending, transport = configured
    transport.failure = RuntimeError("private client credential and network address")
    exchanger = BrokerCodeExchanger(
        policy=policy, client_secret=CLIENT_SECRET, transport=transport
    )
    with pytest.raises(PermissionError, match="code redemption denied") as failure:
        exchanger.redeem(pending=pending)
    assert len(transport.requests) == 1
    assert "private client credential" not in str(failure.value)


def test_concrete_https_transport_uses_verified_tls_no_proxy_and_no_redirect(configured) -> None:
    """Use a single direct HTTPS POST with a bounded read and no redirect handler."""
    policy, pending, transport = configured
    exchanger = BrokerCodeExchanger(
        policy=policy, client_secret=CLIENT_SECRET, transport=transport
    )
    assert exchanger.redeem(pending=pending) == "header.payload.signature"
    request = transport.requests[0]
    reply = Mock()
    reply.status = 200
    reply.getheaders.return_value = [
        ("Content-Type", "application/json"),
        ("Content-Encoding", "identity"),
    ]
    reply.read.return_value = b'{"id_token":"header.payload.signature"}'
    with patch(
        "matchdesk.domain.customer_oidc_exchange.HTTPSConnection"
    ) as connection_factory:
        connection_factory.return_value.getresponse.return_value = reply
        result = HttpsOidcTokenTransport().post(request)
    assert result.body == reply.read.return_value
    assert connection_factory.call_args.args == ("test.ciamlogin.com",)
    assert connection_factory.call_args.kwargs["timeout"] == 5.0
    assert connection_factory.call_args.kwargs["context"].verify_mode.name == "CERT_REQUIRED"
    sent = connection_factory.return_value.request.call_args
    assert sent.args == ("POST", f"/{TENANT}/oauth2/v2.0/token")
    assert "code=single-use-code" in sent.kwargs["body"]
    assert "client_secret=" in sent.kwargs["body"]
    assert sent.kwargs["headers"]["Accept-Encoding"] == "identity"
    reply.read.assert_called_once_with(32769)
    connection_factory.return_value.close.assert_called_once()


@pytest.mark.parametrize(
    "status,headers,body",
    [
        (302, [("Location", "https://evil.example"), ("Content-Type", "application/json")], b""),
        (400, [("Content-Type", "application/json")], b'{"error":"invalid_grant"}'),
        (200, [("Content-Type", "text/plain")], b"bad"),
        (200, [("Content-Type", "application/json")] * 2, b'{"id_token":"a.b.c"}'),
        (200, [("Content-Type", "application/json"), ("Content-Encoding", "gzip")], b"bad"),
        (200, [("Content-Type", "application/json")], b"x" * 32769),
    ],
)
def test_https_transport_rejects_redirects_errors_compression_and_oversize(
    configured, status, headers, body
) -> None:
    """The wire transport neither follows redirects nor downloads unbounded data."""
    policy, pending, captured = configured
    exchanger = BrokerCodeExchanger(
        policy=policy, client_secret=CLIENT_SECRET, transport=captured
    )
    exchanger.redeem(pending=pending)
    request = captured.requests[0]
    reply = Mock(status=status)
    reply.getheaders.return_value = headers
    reply.read.return_value = body
    with patch(
        "matchdesk.domain.customer_oidc_exchange.HTTPSConnection"
    ) as connection_factory:
        connection_factory.return_value.getresponse.return_value = reply
        with pytest.raises(PermissionError, match="transport denied"):
            HttpsOidcTokenTransport().post(request)
        connection_factory.return_value.close.assert_called_once()


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://test.ciamlogin.com/a/oauth2/v2.0/token",
        "https://evil.example/a/oauth2/v2.0/token",
        "https://test.ciamlogin.com:443/a/oauth2/v2.0/token",
        "https://test.ciamlogin.com/a/oauth2/v2.0/token?target=evil",
        "https://test.ciamlogin.com/a/oauth2/v2.0/authorize",
    ],
)
def test_https_transport_rejects_unpinned_endpoint_before_socket(configured, endpoint) -> None:
    """Arbitrary URLs cannot turn the low-level client into an SSRF primitive."""
    policy, pending, captured = configured
    BrokerCodeExchanger(
        policy=policy, client_secret=CLIENT_SECRET, transport=captured
    ).redeem(pending=pending)
    request = replace(captured.requests[0], endpoint=endpoint)
    with patch(
        "matchdesk.domain.customer_oidc_exchange.HTTPSConnection"
    ) as connection_factory:
        with pytest.raises(PermissionError):
            HttpsOidcTokenTransport().post(request)
        connection_factory.assert_not_called()


def test_tls_failure_is_redacted_and_connection_closed(configured) -> None:
    """Certificate, DNS and timeout diagnostics cannot leak from the token adapter."""
    policy, pending, captured = configured
    BrokerCodeExchanger(
        policy=policy, client_secret=CLIENT_SECRET, transport=captured
    ).redeem(pending=pending)
    request = captured.requests[0]
    with patch(
        "matchdesk.domain.customer_oidc_exchange.HTTPSConnection"
    ) as connection_factory:
        connection_factory.return_value.request.side_effect = OSError("private host")
        with pytest.raises(PermissionError, match="transport denied") as failure:
            HttpsOidcTokenTransport().post(request)
        connection_factory.return_value.close.assert_called_once()
    assert "private host" not in str(failure.value)
