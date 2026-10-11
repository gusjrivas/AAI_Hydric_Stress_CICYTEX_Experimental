from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

SENSORS = tuple(f"CP{point}_S{probe}" for point in range(1, 8) for probe in range(1, 4))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_normalized_cicytex(directory: Path) -> pd.DataFrame:
    """Carga únicamente derivados CICYTEX y conserva identidad de sonda/fuente."""
    frames: list[pd.DataFrame] = []
    for sensor in SENSORS:
        path = directory / f"cicytex__{sensor}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"Falta la serie declarada: {path}")
        frame = pd.read_csv(path)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
        frame["soil_moisture"] = pd.to_numeric(frame["soil_moisture"], errors="coerce")
        if set(frame["sensor_id"].dropna().unique()) != {sensor}:
            raise ValueError(f"Identidad de sonda inconsistente en {path.name}")
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True).sort_values(["sensor_id", "timestamp"])
    if data.duplicated(["sensor_id", "timestamp"]).any():
        raise ValueError("Hay fechas duplicadas dentro de una sonda")
    if not data["soil_moisture"].dropna().between(0.0, 1.0).all():
        raise ValueError("Humedad volumétrica fuera de [0, 1] m3/m3")
    return data.reset_index(drop=True)


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
