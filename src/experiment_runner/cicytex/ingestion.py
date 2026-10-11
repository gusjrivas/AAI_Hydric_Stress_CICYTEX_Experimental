from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from experiment_runner.cicytex.dataset_contract import (
    CICYTEX_NORMALIZED_V1,
    CicytexDatasetContract,
)

SENSORS = CICYTEX_NORMALIZED_V1.sensor_ids


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class CsvCicytexDatasetSource:
    """CSV adapter for the versioned normalized CICYTEX dataset contract."""

    directory: Path
    contract: CicytexDatasetContract = CICYTEX_NORMALIZED_V1

    def __post_init__(self) -> None:
        object.__setattr__(self, "directory", Path(self.directory))

    def load(self) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        timestamp = self.contract.timestamp_column
        moisture = self.contract.moisture_column
        sensor_column = self.contract.sensor_id_column
        for sensor in self.contract.sensor_ids:
            path = self.directory / self.contract.file_name_for(sensor)
            if not path.is_file():
                raise FileNotFoundError(f"Falta la serie declarada: {path}")
            frame = pd.read_csv(path)
            frame[timestamp] = pd.to_datetime(frame[timestamp], errors="raise")
            frame[moisture] = pd.to_numeric(frame[moisture], errors="coerce")
            if set(frame[sensor_column].dropna().unique()) != {sensor}:
                raise ValueError(f"Identidad de sonda inconsistente en {path.name}")
            frames.append(frame)
        data = pd.concat(frames, ignore_index=True).sort_values([sensor_column, timestamp])
        if data.duplicated([sensor_column, timestamp]).any():
            raise ValueError("Hay fechas duplicadas dentro de una sonda")
        lower, upper = self.contract.moisture_bounds
        if not data[moisture].dropna().between(lower, upper).all():
            raise ValueError("Humedad volumétrica fuera de [0, 1] m3/m3")
        if not self.contract.allow_missing_moisture and data[moisture].isna().any():
            raise ValueError("Humedad volumétrica faltante no permitida")
        return data.reset_index(drop=True)


def load_normalized_cicytex(directory: Path) -> pd.DataFrame:
    """Carga derivados CICYTEX preservando la fachada DataFrame histórica."""
    return CsvCicytexDatasetSource(directory).load()


def quality_summary(data: pd.DataFrame) -> dict:
    counts = data.groupby("sensor_id", observed=True).size()
    observed = data["soil_moisture"].notna()
    return {
        "rows": int(len(data)),
        "sensors": int(data["sensor_id"].nunique()),
        "start": data["timestamp"].min().date().isoformat(),
        "end": data["timestamp"].max().date().isoformat(),
        "missing_soil_moisture": int((~observed).sum()),
        "duplicate_sensor_dates": int(data.duplicated(["sensor_id", "timestamp"]).sum()),
        "rows_per_sensor_min": int(counts.min()),
        "rows_per_sensor_max": int(counts.max()),
        "partial_days": int(data.get("is_partial_day_soil_moisture", False).fillna(False).sum()),
    }
