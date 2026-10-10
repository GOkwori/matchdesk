"""Read-only producer preview contract and HTTP security regressions."""

from fastapi.testclient import TestClient
from matchdesk.api.app import create_app
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.producer_preview import build_producer_desk_preview


def test_preview_is_deterministic_and_metric_verified() -> None:
    """Only a real registered home-goal metric is shown as verified."""
    first = build_producer_desk_preview()
    again = build_producer_desk_preview()
    assert first == again
    assert first.verification.status == "verified"
    assert first.verification.observed == 1.0
    assert first.claim.assertion is not None
    assert first.claim.assertion.metric == "goals.v1"
    assert first.output.binding.evidence_digest == content_digest(first.evidence)
    assert first.output.binding.content_digest == content_digest(first.output.payload)
    assert first.review_status == "pending_verification"
    assert first.authenticated is False
    assert first.publication_enabled is False


def test_preview_http_exposes_no_review_mutations() -> None:
    """Unauthenticated visitors can inspect synthetic data but cannot approve."""
    client = TestClient(create_app())
    response = client.get("/api/producer/preview")
    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "synthetic_read_only"
    assert result["verification"]["status"] == "verified"
    assert result["authenticated"] is False
    assert result["publication_enabled"] is False
    for action in ("reverify", "approve", "reject", "publish", "edit"):
        assert client.post(f"/api/producer/preview/{action}", json={}).status_code == 404


def test_preview_is_not_an_operational_readiness_claim() -> None:
    """Preview availability must not enable product health or publishing."""
    client = TestClient(create_app())
    assert client.get("/api/ready").status_code == 503
    assert client.get("/api/ready").json()["checks"]["publication"] == "not_implemented"
