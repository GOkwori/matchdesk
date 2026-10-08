"""Protect the supported HTTP client boundary after the patched ASGI upgrade."""

import httpx2
from fastapi.testclient import TestClient


def test_testclient_uses_supported_httpx2() -> None:
    """Fail if TestClient falls back to the deprecated client instead of HTTPX2."""
    # The suite also promotes import-time warnings to errors. Keeping this assertion
    # explicit prevents a future dependency change from silently restoring the old path.
    assert issubclass(TestClient, httpx2.Client)
