"""Negative-boundary and deterministic HTTP tests for the opt-in local judge."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from matchdesk.api.app import create_app
from matchdesk.api.judge_local_routes import create_judge_local_app
from matchdesk.domain.judge_sessions import LocalJudgeSessions

ORIGIN = "http://127.0.0.1:8000"
HEADERS = {"Origin": ORIGIN, "X-MatchDesk-Judge": "synthetic-local-v1"}


@pytest.fixture
def local_client() -> Iterator[TestClient]:
    """Construct an isolated loopback caller instead of publishing a server."""
    with TestClient(
        create_judge_local_app(),
        base_url=ORIGIN,
        client=("127.0.0.1", 41000),
    ) as client:
        yield client


def _created(client: TestClient) -> dict[str, object]:
    """Request the only allowed synthetic bearer issuance payload."""
    response = client.post(
        "/api/judge/sessions",
        content=b"{}",
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _authorization(token: object) -> dict[str, str]:
    """Keep capabilities in an authorization header, never a query string."""
    return {**HEADERS, "Authorization": f"Bearer {token}"}


def test_default_app_never_mounts_judge_routes() -> None:
    """Deployed foundation creation stays separate from opt-in synthetic work."""
    with TestClient(create_app()) as client:
        assert client.post("/api/judge/sessions", json={}).status_code == 404
        assert "/api/judge/sessions" not in client.get("/openapi.json").json()["paths"]


def test_create_replay_reset_close_and_revoke(local_client: TestClient) -> None:
    """A reset invalidates the old handle; replay remains fixture-deterministic."""
    session = _created(local_client)
    assert session["mode"] == "synthetic_local_read_only"
    assert session["ttl_seconds"] == 900
    session_id = session["session_id"]
    url = f"/api/judge/sessions/{session_id}"
    old_auth = _authorization(session["token"])
    first = local_client.get(f"{url}/replay", headers=old_auth)
    assert first.status_code == 200
    manifest = first.json()["replay"]
    assert manifest["verified_claim"]["status"] == "verified"
    assert manifest["controlled_error"]["status"] == "needs_revision"
    assert manifest["real_publication"] is False
    assert manifest["live_model_executed"] is False
    assert len(manifest["audience_variants"]) == 9
    assert session["token"] not in first.text
    assert first.headers["cache-control"].startswith("no-store")
    assert first.headers["x-frame-options"] == "DENY"

    rotation = local_client.post(
        f"{url}/reset",
        content=b"{}",
        headers={**old_auth, "Content-Type": "application/json"},
    )
    assert rotation.status_code == 200
    replacement = rotation.json()
    assert replacement["generation"] == 2
    assert replacement["token"] != session["token"]
    assert local_client.get(f"{url}/replay", headers=old_auth).status_code == 403
    new_auth = _authorization(replacement["token"])
    second = local_client.get(f"{url}/replay", headers=new_auth)
    assert second.status_code == 200
    assert second.json()["replay"] == manifest
    assert local_client.delete(url, headers=new_auth).status_code == 204
    assert local_client.get(f"{url}/replay", headers=new_auth).status_code == 403


def test_two_sessions_cannot_cross_read_or_reset(local_client: TestClient) -> None:
    """A copied session ID without its own secret has no capability."""
    first, second = _created(local_client), _created(local_client)
    first_url = f"/api/judge/sessions/{first['session_id']}"
    second_auth = _authorization(second["token"])
    assert local_client.get(f"{first_url}/replay", headers=second_auth).status_code == 403
    assert local_client.post(
        f"{first_url}/reset",
        content=b"{}",
        headers={**second_auth, "Content-Type": "application/json"},
    ).status_code == 403


@pytest.mark.parametrize(
    "override",
    [
        {"Origin": "https://attacker.example"},
        {"Origin": "http://localhost:8000"},
        {"Host": "judge.attacker.test"},
        {"Cookie": "session=spoof"},
        {"Forwarded": "for=127.0.0.1"},
        {"X-Forwarded-For": "127.0.0.1"},
        {"Referer": "https://attacker.example"},
        {"X-MatchDesk-Judge": "unknown"},
    ],
)
def test_spoofed_browser_and_proxy_boundaries_are_denied(
    local_client: TestClient, override: dict[str, str]
) -> None:
    """Every untrusted browser/proxy signal is denied before issuance."""
    result = local_client.post(
        "/api/judge/sessions",
        content=b"{}",
        headers={**HEADERS, "Content-Type": "application/json", **override},
    )
    assert result.status_code == 403


def test_remote_peer_cannot_mint_session() -> None:
    """Forged Host and Origin headers do not authorize a non-loopback peer."""
    with TestClient(
        create_judge_local_app(),
        base_url=ORIGIN,
        client=("203.0.113.7", 41000),
    ) as remote:
        response = remote.post(
            "/api/judge/sessions",
            content=b"{}",
            headers={**HEADERS, "Content-Type": "application/json"},
        )
    assert response.status_code == 403


def test_bad_payload_query_and_auth_fail_closed(local_client: TestClient) -> None:
    """Unknown payloads, query strings and malformed credentials never succeed."""
    assert local_client.post(
        "/api/judge/sessions",
        content=b'{"user":"owner"}',
        headers={**HEADERS, "Content-Type": "application/json"},
    ).status_code == 400
    assert local_client.post(
        "/api/judge/sessions?debug=1",
        content=b"{}",
        headers={**HEADERS, "Content-Type": "application/json"},
    ).status_code == 403
    assert local_client.post(
        "/api/judge/sessions",
        content=b"{}",
        headers={**HEADERS, "Content-Type": "application/json", "Authorization": "Bearer x"},
    ).status_code == 403
    session = _created(local_client)
    url = f"/api/judge/sessions/{session['session_id']}/replay"
    assert local_client.get(url, headers=HEADERS).status_code == 403
    assert local_client.get(
        url, headers={**HEADERS, "Authorization": "Bearer invalid"}
    ).status_code == 403
    assert local_client.get(
        f"{url}?token={session['token']}",
        headers=_authorization(session["token"]),
    ).status_code == 403


def test_expiry_and_capacity_are_caught_at_http_boundary() -> None:
    """Quota cannot expand and expired tokens are rejected after time advances."""
    now = [10.0]
    sessions = LocalJudgeSessions(clock=lambda: now[0])
    with TestClient(
        create_judge_local_app(sessions=sessions),
        base_url=ORIGIN,
        client=("127.0.0.1", 41000),
    ) as client:
        created = [_created(client) for _ in range(8)]
        busy = client.post(
            "/api/judge/sessions",
            content=b"{}",
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        assert busy.status_code == 429
        now[0] += 901
        expired = created[0]
        assert client.get(
            f"/api/judge/sessions/{expired['session_id']}/replay",
            headers=_authorization(expired["token"]),
        ).status_code == 403
        assert _created(client)["session_id"] != expired["session_id"]


def test_body_limit_and_no_cors(local_client: TestClient) -> None:
    """Large submissions cannot allocate indefinitely or grant cross-origin access."""
    response = local_client.post(
        "/api/judge/sessions",
        content=b" " * 3000,
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert "access-control-allow-origin" not in response.headers
