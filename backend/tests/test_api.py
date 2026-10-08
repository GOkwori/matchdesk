"""Exercise real ASGI routes and byte limits without external service stubs."""
import asyncio
from collections.abc import Iterator
import pytest
from fastapi.testclient import TestClient
from matchdesk.api.limits import BodyLimitMiddleware


def test_health_is_not_product_readiness(client: TestClient) -> None:
    """The running foundation cannot advertise a functioning production product."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["model_mode"] == "not_connected"
    ready = client.get("/api/ready")
    assert ready.status_code == 503
    assert ready.json()["checks"]["publication"] == "not_implemented"


def test_event_validation_has_no_verification_authority(client: TestClient, event_data: dict[str, object]) -> None:
    """HTTP clients can submit JSON arrays without structural success implying truth."""
    response = client.post("/api/contracts/event/validate", json=event_data)
    assert response.status_code == 200, response.text
    assert response.json()["structurally_valid"] is True
    assert response.json()["evidence_verified"] is False
    assert len(response.json()["content_digest"]) == 64


def test_invalid_inputs_are_not_echoed(client: TestClient, event_data: dict[str, object]) -> None:
    """Validation responses must not copy sensitive values from an unknown field."""
    event_data["private_material"] = "DO_NOT_ECHO_THIS_VALUE"
    response = client.post("/api/contracts/event/validate", json=event_data)
    assert response.status_code == 422
    assert "DO_NOT_ECHO_THIS_VALUE" not in response.text


def test_malformed_json_is_422(client: TestClient) -> None:
    """Malformed JSON produces a controlled validation response, not an internal error."""
    response = client.post("/api/contracts/event/validate", content="{", headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_schema_and_openapi_are_accessible(client: TestClient) -> None:
    """Published contract endpoints match implemented routes, not future product routes."""
    assert client.get("/api/contracts/event").json()["title"] == "MatchEvent"
    spec = client.get("/openapi.json").json()
    assert "/api/contracts/event/validate" in spec["paths"]
    assert "/api/sessions" not in spec["paths"]
    assert client.post("/api/items/fake/actions", json={"action": "publish"}).status_code == 404


@pytest.mark.parametrize("length,expected", [("-1", 400), ("invalid", 400), ("70000", 413)])
def test_declared_body_limits(client: TestClient, length: str, expected: int) -> None:
    """Malformed and oversized declared bodies fail before payload validation."""
    response = client.post("/api/contracts/event/validate", content="{}", headers={"Content-Length": length})
    assert response.status_code == expected


def test_oversized_actual_body(client: TestClient) -> None:
    """An undersized Content-Length cannot bypass the actual-byte limit."""
    response = client.post("/api/contracts/event/validate", content="x" * 70_000, headers={"Content-Length": "2"})
    assert response.status_code == 413


def test_chunked_body_limit(client: TestClient) -> None:
    """Clients without Content-Length are still limited by the accumulated byte count."""
    def chunks() -> Iterator[bytes]:
        """Yield enough individually small chunks to exceed the total budget."""
        for _ in range(10):
            yield b"x" * 10_000
    response = client.post("/api/contracts/event/validate", content=chunks())
    assert response.status_code == 413


def test_limiter_rejects_invalid_configuration() -> None:
    """A configuration error must be visible during construction."""
    async def application(scope, receive, send) -> None:
        """Supply a minimal ASGI endpoint for configuration validation."""
        del scope, receive, send
    with pytest.raises(ValueError):
        BodyLimitMiddleware(application, max_bytes=0)


def test_limiter_passes_non_http_and_disconnects() -> None:
    """Lifespan traffic passes through, whereas a disconnected body is not processed."""
    calls: list[str] = []
    async def application(scope, receive, send) -> None:
        """Record which protocol reached the inner application."""
        del receive, send
        calls.append(scope["type"])
    async def receive() -> dict:
        """Simulate a client that disconnected before sending a body."""
        return {"type": "http.disconnect"}
    async def send(message) -> None:
        """Record an unexpected response to a disconnected client."""
        calls.append(message["type"])
    middleware = BodyLimitMiddleware(application)
    asyncio.run(middleware({"type": "lifespan"}, receive, send))
    asyncio.run(middleware({"type": "http", "headers": []}, receive, send))
    assert calls == ["lifespan"]


def test_limiter_replays_chunks_then_disconnect() -> None:
    """Bounded chunk assembly must preserve downstream disconnect delivery."""
    messages = iter([
        {"type": "http.request", "body": b"a", "more_body": True},
        {"type": "http.request", "body": b"b", "more_body": False},
        {"type": "http.disconnect"},
    ])
    received: list[dict] = []
    async def receive() -> dict:
        """Read the next event of the controlled ASGI request stream."""
        return next(messages)
    async def send(message) -> None:
        """This test consumes a request without writing an HTTP response."""
        del message
    async def application(scope, receive, send) -> None:
        """Observe the single bounded replay followed by the original disconnect."""
        del scope, send
        received.extend([await receive(), await receive()])
    asyncio.run(BodyLimitMiddleware(application)({"type": "http", "headers": []}, receive, send))
    assert received[0]["body"] == b"ab"
    assert received[1]["type"] == "http.disconnect"
