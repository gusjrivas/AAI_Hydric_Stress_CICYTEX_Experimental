from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from experiment_runner.cicytex.ingestion import (
    SENSORS,
    load_normalized_cicytex,
    quality_summary,
)


def _write_normalized_fixture(directory: Path) -> dict[Path, str]:
    input_hashes: dict[Path, str] = {}
    for sensor_index, sensor in enumerate(SENSORS):
        moisture = (
            "not-observed"
            if sensor_index == 0
            else float(f"{0.2 + sensor_index / 1000:.3f}")
        )
        frame = pd.DataFrame(
            [
                ["2023-01-02", moisture, sensor, False, 20],
                ["2023-01-01", 0.1 + sensor_index / 1000, sensor, True, 20],
            ],
            columns=[
                "timestamp",
                "soil_moisture",
                "sensor_id",
                "is_partial_day_soil_moisture",
                "depth_cm",
            ],
        )
        path = directory / f"cicytex__{sensor}.csv"
        frame.to_csv(path, index=False)
        input_hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return input_hashes


def test_legacy_loader_preserves_exact_frame_contract_and_input_bytes(tmp_path: Path):
    input_hashes = _write_normalized_fixture(tmp_path)

    result = load_normalized_cicytex(tmp_path)

    expected_rows: list[dict[str, object]] = []
    for sensor_index, sensor in enumerate(SENSORS):
        expected_rows.extend(
            [
                {
                    "timestamp": pd.Timestamp("2023-01-01"),
                    "soil_moisture": float(f"{0.1 + sensor_index / 1000:.3f}"),
                    "sensor_id": sensor,
                    "is_partial_day_soil_moisture": True,
                    "depth_cm": 20,
                },
                {
                    "timestamp": pd.Timestamp("2023-01-02"),
                    "soil_moisture": (
                        None
                        if sensor_index == 0
                        else float(f"{0.2 + sensor_index / 1000:.3f}")
                    ),
                    "sensor_id": sensor,
                    "is_partial_day_soil_moisture": False,
                    "depth_cm": 20,
                },
            ]
        )
    expected = pd.DataFrame(expected_rows, columns=result.columns)
    expected["soil_moisture"] = pd.to_numeric(expected["soil_moisture"], errors="coerce")

    assert_frame_equal(result, expected, check_dtype=True, check_exact=True, check_like=False)
    assert isinstance(result.index, pd.RangeIndex)
    assert quality_summary(result) == {
        "rows": 42,
        "sensors": 21,
        "start": "2023-01-01",
        "end": "2023-01-02",
        "missing_soil_moisture": 1,
        "duplicate_sensor_dates": 0,
        "rows_per_sensor_min": 2,
        "rows_per_sensor_max": 2,
        "partial_days": 21,
    }
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_hashes
    } == input_hashes


def test_legacy_loader_ignores_unexpected_csv_files(tmp_path: Path):
    _write_normalized_fixture(tmp_path)
    (tmp_path / "cicytex__unexpected.csv").write_text("invalid", encoding="utf-8")

    result = load_normalized_cicytex(tmp_path)

    assert tuple(result["sensor_id"].drop_duplicates()) == SENSORS


def test_legacy_loader_reports_the_exact_missing_sensor_path(tmp_path: Path):
    _write_normalized_fixture(tmp_path)
    missing_path = tmp_path / f"cicytex__{SENSORS[-1]}.csv"
    missing_path.unlink()

    with pytest.raises(
        FileNotFoundError,
        match=re.escape(f"Falta la serie declarada: {missing_path}"),
    ):
        load_normalized_cicytex(tmp_path)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda frame: frame.assign(sensor_id="OTHER"),
            "Identidad de sonda inconsistente",
        ),
        (
            lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True),
            "Hay fechas duplicadas dentro de una sonda",
        ),
        (
            lambda frame: frame.assign(soil_moisture=1.1),
            r"Humedad volumétrica fuera de \[0, 1\] m3/m3",
        ),
    ],
)
def test_legacy_loader_preserves_validation_failures(tmp_path: Path, mutate, message: str):
    _write_normalized_fixture(tmp_path)
    path = tmp_path / f"cicytex__{SENSORS[0]}.csv"
    frame = pd.read_csv(path)
    mutate(frame).to_csv(path, index=False)

    with pytest.raises(ValueError, match=message):
        load_normalized_cicytex(tmp_path)
