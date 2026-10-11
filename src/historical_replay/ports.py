from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from historical_replay.catalog import ReplayCatalog


class ReplayCatalogSource(Protocol):
    """Source boundary for a site-specific historical replay catalog."""

    def load_catalog(self) -> ReplayCatalog: ...
