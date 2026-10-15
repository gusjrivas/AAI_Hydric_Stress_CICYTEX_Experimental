"""Test-only synchronized repository for replay-session unit tests."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TypeVar

from historical_replay.sessions import ReplaySession, ReplaySessionConflict

T = TypeVar("T")


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, ReplaySession] = {}
        self._lock = Lock()

    def add(self, session: ReplaySession) -> None:
        with self._lock:
            if session.session_id in self._sessions:
                raise ReplaySessionConflict(session.session_id)
            self._sessions[session.session_id] = session

    def get(self, session_id: str) -> ReplaySession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def update(
        self,
        session_id: str,
        transition: Callable[[ReplaySession], ReplaySession],
    ) -> ReplaySession | None:
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                return None
            updated = transition(current)
            if type(updated) is not ReplaySession or updated.session_id != session_id:
                raise ValueError("session transition must preserve its exact identity")
            self._sessions[session_id] = updated
            return updated

    def with_session(
        self,
        session_id: str,
        operation: Callable[[ReplaySession], T],
    ) -> T | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            return operation(session)
