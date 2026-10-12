from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from historical_replay.catalog import ReplayCatalog
    from historical_replay.sessions import ReplaySession

T = TypeVar("T")


class ReplayCatalogSource(Protocol):
    """Source boundary for a site-specific historical replay catalog."""

    def load_catalog(self) -> ReplayCatalog: ...


@runtime_checkable
class SessionRepository(Protocol):
    """Atomic storage boundary for immutable replay sessions."""

    def add(self, session: ReplaySession) -> None: ...

    def get(self, session_id: str) -> ReplaySession | None: ...

    def update(
        self,
        session_id: str,
        transition: Callable[[ReplaySession], ReplaySession],
    ) -> ReplaySession | None: ...

    def with_session(
        self,
        session_id: str,
        operation: Callable[[ReplaySession], T],
    ) -> T | None: ...
