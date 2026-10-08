"""Shared synthetic contract input and isolated in-process HTTP clients."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from matchdesk.api.app import create_app


@pytest.fixture
def event_data() -> dict[str, object]:
    """Return a new synthetic pass for every test to prevent mutation coupling."""
    return {
        "event_id": "m001-e0001",
        "match_id": "m001",
        "sequence": 1,
        "period": 1,
        "match_clock_ms": 1000,
        "type": "pass",
        "team_id": "demo-a",
        "player_id": "a-08",
        "possession_id": 1,
        "location": {"x": 50.0, "y": 30.0},
        "end_location": {"x": 65.0, "y": 35.0},
        "outcome": "complete",
        "tags": ["contract_fixture"],
        "synthetic": True,
    }


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Start and close a fresh ASGI application for each API test."""
    with TestClient(create_app()) as test_client:
        yield test_client
