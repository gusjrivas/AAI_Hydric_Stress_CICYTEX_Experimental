"""Pure domain and application service for CICYTEX replay sessions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import TypeVar

from historical_replay.ports import SessionRepository

T = TypeVar("T")
_SESSION_LIMIT = object()


class ReplaySessionNotFound(LookupError):
    """The requested replay session does not exist."""


class ReplaySessionConflict(ValueError):
    """A new replay session conflicts with an existing identity."""


@dataclass(frozen=True, slots=True)
class ReplaySession:
    session_id: str
    sensor_id: str
    start_date: date
    emission_date: date
    horizon_days: int
    revealed_through: date
    last_observation: date

    def __post_init__(self) -> None:
        if type(self.session_id) is not str or not self.session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if type(self.sensor_id) is not str or not self.sensor_id.strip():
            raise ValueError("sensor_id must be a non-empty string")
        if type(self.start_date) is not date or type(self.emission_date) is not date:
            raise ValueError("session dates must be exact dates")
        if type(self.revealed_through) is not date:
            raise ValueError("revealed_through must be an exact date")
        if type(self.last_observation) is not date:
            raise ValueError("last_observation must be an exact date")
        if type(self.horizon_days) is not int or not 1 <= self.horizon_days <= 3:
            raise ValueError("horizon_days must be an integer between 1 and 3")
        if self.start_date != self.emission_date:
            raise ValueError("start_date must equal emission_date")
        if self.revealed_through < self.emission_date:
            raise ValueError("revealed_through cannot precede emission_date")
        if self.last_observation < self.emission_date:
            raise ValueError("last_observation cannot precede emission_date")
        if self.last_observation < self.revealed_through:
            raise ValueError("last_observation cannot precede the session clock")

    @property
    def can_advance(self) -> bool:
        return self.revealed_through < self.last_observation

    def advance(self, last_observation: object = _SESSION_LIMIT) -> ReplaySession:
        limit = self.last_observation
        if last_observation is not _SESSION_LIMIT:
            if type(last_observation) is not date:
                raise ValueError("last_observation must be an exact date")
            if last_observation < self.emission_date or last_observation < self.revealed_through:
                raise ValueError("last_observation cannot precede the session clock")
            limit = last_observation
        return replace(
            self,
            revealed_through=min(
                self.revealed_through + timedelta(days=1),
                limit,
            ),
        )

    def reset(self) -> ReplaySession:
        return replace(self, revealed_through=self.emission_date)


class ReplaySessionService:
    """Own all replay-session commands over an injected repository."""

    def __init__(
        self,
        repository: SessionRepository,
        *,
        id_factory: Callable[[], str],
        last_observation: date,
    ) -> None:
        if not callable(id_factory):
            raise TypeError("id_factory must be callable")
        if type(last_observation) is not date:
            raise ValueError("last_observation must be an exact date")
        self._repository = repository
        self._id_factory = id_factory
        self._last_observation = last_observation

    def create(
        self,
        *,
        sensor_id: str,
        emission_date: date,
        horizon_days: int,
    ) -> ReplaySession:
        if type(emission_date) is not date:
            raise ValueError("emission_date must be an exact date")
        if emission_date > self._last_observation:
            raise ValueError("emission_date cannot follow the last observation")
        session = ReplaySession(
            session_id=self._id_factory(),
            sensor_id=sensor_id,
            start_date=emission_date,
            emission_date=emission_date,
            horizon_days=horizon_days,
            revealed_through=emission_date,
            last_observation=self._last_observation,
        )
        self._repository.add(session)
        return session

    def get(self, session_id: str) -> ReplaySession:
        session = self._repository.get(session_id)
        if session is None:
            raise ReplaySessionNotFound(session_id)
        return session

    def advance(self, session_id: str) -> ReplaySession:
        session = self._repository.update(
            session_id,
            ReplaySession.advance,
        )
        if session is None:
            raise ReplaySessionNotFound(session_id)
        return session

    def with_session(
        self,
        session_id: str,
        operation: Callable[[ReplaySession], T],
    ) -> T:
        result = self._repository.with_session(session_id, operation)
        if result is None:
            raise ReplaySessionNotFound(session_id)
        return result

    def reset(self, session_id: str) -> ReplaySession:
        session = self._repository.update(session_id, ReplaySession.reset)
        if session is None:
            raise ReplaySessionNotFound(session_id)
        return session
