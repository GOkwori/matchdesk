"""Disposable judge-session isolation and fail-closed reset regressions."""

import pytest
from matchdesk.domain.judge_sessions import LocalJudgeSessions


def test_sessions_are_isolated_and_reset_revokes_old_token() -> None:
    """Reset one run without authorizing or changing another judge."""
    service = LocalJudgeSessions()
    first, second = service.create(), service.create()
    assert first.session_id != second.session_id
    assert first.token != second.token
    with pytest.raises(PermissionError):
        service.get(first.session_id, second.token)
    next_first = service.reset(first.session_id, first.token)
    assert next_first.generation == 2
    assert next_first.token != first.token
    with pytest.raises(PermissionError):
        service.get(first.session_id, first.token)
    assert service.get(second.session_id, second.token) == second
    service.close(second.session_id, second.token)
    with pytest.raises(PermissionError):
        service.get(second.session_id, second.token)


def test_expiry_and_capacity_fail_closed() -> None:
    """Expired tokens cannot be revived and capacity is bounded."""
    now = [100.0]
    service = LocalJudgeSessions(clock=lambda: now[0])
    original = service.create()
    for _ in range(7):
        service.create()
    with pytest.raises(RuntimeError, match="capacity"):
        service.create()
    now[0] += 901.0
    with pytest.raises(PermissionError):
        service.get(original.session_id, original.token)
    replacement = service.create()
    assert replacement.session_id != original.session_id


def test_invalid_token_cannot_reset_or_close() -> None:
    """A guessed handle alone must not grant destructive session operations."""
    service = LocalJudgeSessions()
    session = service.create()
    for action in (service.reset, service.close):
        with pytest.raises(PermissionError):
            action(session.session_id, "wrong-token")
    assert service.get(session.session_id, session.token) == session


@pytest.mark.parametrize("bad", ["", "x" * 129, None, 17, True])
def test_malformed_session_credentials_fail_closed(bad: object) -> None:
    """Malformed handles never reach token comparison or leak state."""
    service = LocalJudgeSessions()
    session = service.create()
    with pytest.raises(PermissionError, match="unavailable"):
        service.get(bad, session.token)  # type: ignore[arg-type]
    with pytest.raises(PermissionError, match="unavailable"):
        service.get(session.session_id, bad)  # type: ignore[arg-type]
    assert service.get(session.session_id, session.token) == session


def test_secret_is_absent_from_default_representation() -> None:
    """Diagnostic representations must not expose bearer secrets."""
    session = LocalJudgeSessions().create()
    assert session.token not in repr(session)
    assert "token=" not in repr(session)
