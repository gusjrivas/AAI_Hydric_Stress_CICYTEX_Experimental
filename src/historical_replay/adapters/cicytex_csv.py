from __future__ import annotations

from pathlib import Path

import pandas as pd

from historical_replay.catalog import ReplayCatalog


class CsvReplayCatalogSource:
    """Read the archived CICYTEX replay package without exposing pandas upstream."""

    def __init__(
        self,
        root: Path,
        *,
        first_legitimate_emission: str = "2023-07-06",
        last_observation: str = "2023-07-25",
        horizons: tuple[int, ...] = (1, 2, 3),
    ) -> None:
        self._root = Path(root)
        self._first_legitimate_emission = first_legitimate_emission
        self._last_observation = last_observation
        self._horizons = horizons

    def load_catalog(self) -> ReplayCatalog:
        predictions = pd.read_csv(
            self._root / "predictions.csv",
            parse_dates=["emission_date", "target_timestamp"],
        )
        # The existing endpoint treats both files as one package. Reading observations here
        # preserves its fail-closed behavior even though the catalog uses prediction rows only.
        pd.read_csv(self._root / "observations.csv", parse_dates=["timestamp"])

        emission_dates = tuple(
            sorted(
                {pd.Timestamp(value).date().isoformat() for value in predictions["emission_date"]}
            )
        )
        emission_dates_by_horizon = {
            int(horizon): tuple(
                sorted({pd.Timestamp(value).date().isoformat() for value in rows["emission_date"]})
            )
            for horizon, rows in predictions.groupby("horizon_days")
        }
        return ReplayCatalog(
            sensors=tuple(sorted(predictions["sensor_id"].unique().tolist())),
            emission_dates=emission_dates,
            emission_dates_by_horizon=emission_dates_by_horizon,
            horizons=self._horizons,
            first_legitimate_emission=self._first_legitimate_emission,
            last_observation=self._last_observation,
        )
