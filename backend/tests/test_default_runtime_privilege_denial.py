"""Prevent implicit privilege activation on the shipping MatchDesk API.

These tests use the real default FastAPI application, not mocked auth/router
dependencies. They qualify absence of live authority, NOT genuine workforce
authentication, delegated MFA, or a secure publisher.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from matchdesk.api.app import app as shipped_app
from matchdesk.api.app import create_app

_CASE = "/api/workforce/producer/sessions/demo-preview-only/cases/demo-story-output"
_PROTECTED_PREFIXES = ("/api/workforce/", "/api/customer/", "/api/judge/")
_SECRET_MARKER = "FAKE_OFFLINE_CAPABILITY_DO_NOT_REFLECT"

# Include every known producer action, plus both opt-in customer routes and
# the separate local judge host. A published synthetic preview is deliberately
# excluded: it grants no actor identity, review or publication authority.
_DENIED_OPERATIONS = (
    ("GET", _CASE),
    ("POST", _CASE + "/create"),
    ("POST", _CASE + "/edit"),
    ("POST", _CASE + "/reverify"),
    ("POST", _CASE + "/approve"),
    ("POST", _CASE + "/reject"),
    ("POST", _CASE + "/publish"),
    ("POST", "/api/customer/oidc/start"),
    ("GET", "/api/customer/session"),
    ("POST", "/api/customer/session"),
    ("POST", "/api/judge/sessions"),
)


@pytest.mark.parametrize("application", [shipped_app, create_app()], ids=["exported", "fresh"])
def test_default_application_has_no_opt_in_privileged_routes(application: FastAPI) -> None:
    """Reject accidental mount even when the route map is manually inspected."""
    actual_paths = {getattr(route, "path", "") for route in application.routes}
    documented_paths = set(application.openapi()["paths"])
    for paths in (actual_paths, documented_paths):
        assert not any(path.startswith(prefix) for path in paths for prefix in _PROTECTED_PREFIXES)

    # The synthetic preview is intentionally public, but has no action method.
    assert "/api/producer/preview" in documented_paths
    assert set(application.openapi()["paths"]["/api/producer/preview"]) == {"get"}


@pytest.mark.parametrize("method,path", _DENIED_OPERATIONS)
@pytest.mark.parametrize(
    "headers",
    (
        {},
        {"Authorization": "Bearer " + _SECRET_MARKER},
        {
            "Authorization": "Bearer " + _SECRET_MARKER,
            "Cookie": "__Host-matchdesk_customer=forged",
            "X-MatchDesk-Actor": "self-asserted-admin",
            "X-Forwarded-For": "127.0.0.1",
            "Origin": "https://untrusted.example",
        },
    ),
    ids=["anonymous", "forged-bearer", "spoofed-metadata"],
)
def test_direct_http_call_cannot_activate_unmounted_authority(
    method: str, path: str, headers: dict[str, str]
) -> None:
    """Direct calls, impersonation headers and forged cookies all remain 404."""
    with TestClient(shipped_app) as client:
        response = client.request(
            method, path, headers=headers, **({"json": {}} if method == "POST" else {})
        )
    assert response.status_code == 404
    assert _SECRET_MARKER not in response.text
    assert "set-cookie" not in response.headers


def test_local_judge_opt_in_cannot_change_shipped_python_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """The separate Next.js judge opt-in cannot silently expose Python routes."""
    monkeypatch.setenv("MATCHDESK_LOCAL_JUDGE_ENABLED", "1")
    with TestClient(create_app()) as client:
        for method, path in (
            ("POST", "/api/judge/sessions"),
            ("POST", _CASE + "/approve"),
            ("GET", _CASE),
        ):
            result = client.request(method, path, json={} if method == "POST" else None)
            assert result.status_code == 404
        # Foundation health is not a readiness or publication certificate.
        assert client.get("/api/ready").status_code == 503
