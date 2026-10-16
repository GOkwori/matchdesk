"""Bounded in-memory judge sessions for disposable synthetic-only local demonstrations.

This is not identity authentication or production session storage. A trusted,
loopback-only host adapter must guard creation and possession of session tokens.
No global singleton, network access, persistence, review or publication occurs.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

_MAX_SESSIONS = 8
_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class JudgeSession:
    """One synthetic judge run identified by a secret handle, not a user identity."""

    session_id: str
    token: str = field(repr=False)
    generation: int
    expires_at: float


class LocalJudgeSessions:
    """Isolate and expire disposable demonstration sessions with atomic resets."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        """Use a monotonic host clock; keep all state within this instance."""
        self._clock = clock
        self._lock = threading.RLock()
        self._sessions: dict[str, JudgeSession] = {}

    def _prune(self, now: float) -> None:
        """Drop expired secrets before admitting new sessions."""
        for key, session in tuple(self._sessions.items()):
            if now >= session.expires_at:
                del self._sessions[key]

    def create(self) -> JudgeSession:
        """Create a fresh bounded session; never reuse a previous token."""
        with self._lock:
            now = self._clock()
            self._prune(now)
            if len(self._sessions) >= _MAX_SESSIONS:
                raise RuntimeError("Judge session capacity reached")
            session = JudgeSession(
                session_id=secrets.token_urlsafe(24),
                token=secrets.token_urlsafe(32),
                generation=1,
                expires_at=now + _TTL_SECONDS,
            )
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str, token: str) -> JudgeSession:
        """Permit only possession of the exact current unexpired secret."""
        # Host adapters must never turn malformed/oversized inputs into a
        # leaking exception or an unbounded bearer-token comparison.
        if (
            type(session_id) is not str
            or type(token) is not str
            or not 1 <= len(session_id) <= 128
            or not 1 <= len(token) <= 128
        ):
            raise PermissionError("Judge session unavailable")
        with self._lock:
            self._prune(self._clock())
            session = self._sessions.get(session_id)
            if session is None or not token or not secrets.compare_digest(session.token, token):
                raise PermissionError("Judge session unavailable")
            return session

    def reset(self, session_id: str, token: str) -> JudgeSession:
        """Atomically revoke the old token and reset this judge run only."""
        with self._lock:
            current = self.get(session_id, token)
            updated = JudgeSession(
                session_id=current.session_id,
                token=secrets.token_urlsafe(32),
                generation=current.generation + 1,
                expires_at=self._clock() + _TTL_SECONDS,
            )
            self._sessions[session_id] = updated
            return updated

    def close(self, session_id: str, token: str) -> None:
        """Revoke an exact judge run without disturbing other sessions."""
        with self._lock:
            self.get(session_id, token)
            del self._sessions[session_id]
