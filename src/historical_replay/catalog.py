from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from historical_replay.ports import ReplayCatalogSource


@dataclass(frozen=True)
class ReplayCatalog:
    sensors: tuple[str, ...]
    emission_dates: tuple[str, ...]
    emission_dates_by_horizon: Mapping[int, tuple[str, ...]]
    horizons: tuple[int, ...]
    first_legitimate_emission: str
    last_observation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "sensors": list(self.sensors),
            "emission_dates": list(self.emission_dates),
            "emission_dates_by_horizon": {
                str(horizon): list(dates)
                for horizon, dates in self.emission_dates_by_horizon.items()
            },
            "horizons": list(self.horizons),
            "first_legitimate_emission": self.first_legitimate_emission,
            "last_observation": self.last_observation,
        }


class GetReplayCatalog:
    def __init__(self, source: ReplayCatalogSource) -> None:
        self._source = source

    def execute(self) -> ReplayCatalog:
        return self._source.load_catalog()
