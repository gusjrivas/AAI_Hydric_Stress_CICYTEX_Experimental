from __future__ import annotations

import hashlib
import importlib
import re
from dataclasses import FrozenInstanceError
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


def test_normalized_v1_contract_is_deeply_immutable_and_scientifically_explicit():
    contract_module = importlib.import_module(
        "experiment_runner.cicytex.dataset_contract"
    )
    contract = contract_module.CICYTEX_NORMALIZED_V1

    assert contract.version == "cicytex-normalized-v1"
    assert contract.sensor_ids == SENSORS
    assert contract.required_columns == ("timestamp", "soil_moisture", "sensor_id")
    assert contract.timestamp_column == "timestamp"
    assert contract.moisture_column == "soil_moisture"
    assert contract.sensor_id_column == "sensor_id"
    assert contract.filename_template == "cicytex__{sensor_id}.csv"
    assert contract.moisture_unit == "m3/m3"
    assert contract.moisture_bounds == (0.0, 1.0)
    assert contract.allow_missing_moisture is True
    assert contract.file_name_for(SENSORS[0]) == "cicytex__CP1_S1.csv"

    with pytest.raises(FrozenInstanceError):
        contract.version = "changed"
    with pytest.raises(TypeError):
        contract.sensor_ids[0] = "changed"


@pytest.mark.parametrize(
    "overrides",
    [
        {"version": ""},
        {"sensor_ids": ("CP1_S1", "CP1_S1")},
        {"required_columns": ("timestamp", "soil_moisture")},
        {"filename_template": "cicytex.csv"},
        {"moisture_unit": ""},
        {"moisture_bounds": (1.0, 0.0)},
        {"moisture_bounds": (0.0, float("inf"))},
    ],
)
def test_dataset_contract_rejects_invalid_scientific_configuration(overrides: dict):
    contract_module = importlib.import_module(
        "experiment_runner.cicytex.dataset_contract"
    )
    baseline = contract_module.CICYTEX_NORMALIZED_V1
    values = {
        "version": baseline.version,
        "sensor_ids": baseline.sensor_ids,
        "required_columns": baseline.required_columns,
        "timestamp_column": baseline.timestamp_column,
        "moisture_column": baseline.moisture_column,
        "sensor_id_column": baseline.sensor_id_column,
        "filename_template": baseline.filename_template,
        "moisture_unit": baseline.moisture_unit,
        "moisture_bounds": baseline.moisture_bounds,
        "allow_missing_moisture": baseline.allow_missing_moisture,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        contract_module.CicytexDatasetContract(**values)


def test_csv_source_implements_port_and_matches_legacy_frame(tmp_path: Path):
    _write_normalized_fixture(tmp_path)
    contract_module = importlib.import_module(
        "experiment_runner.cicytex.dataset_contract"
    )
    ingestion_module = importlib.import_module("experiment_runner.cicytex.ingestion")

    source = ingestion_module.CsvCicytexDatasetSource(tmp_path)
    result = source.load()

    assert isinstance(source, contract_module.CicytexDatasetSource)
    assert source.contract is contract_module.CICYTEX_NORMALIZED_V1
    assert_frame_equal(
        result,
        load_normalized_cicytex(tmp_path),
        check_dtype=True,
        check_exact=True,
        check_like=False,
    )


def test_legacy_loader_delegates_to_csv_source(monkeypatch, tmp_path: Path):
    ingestion_module = importlib.import_module("experiment_runner.cicytex.ingestion")
    expected = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01")],
            "soil_moisture": [0.2],
            "sensor_id": ["CP1_S1"],
        }
    )
    observed: dict[str, object] = {}

    def fake_load(source):
        observed["directory"] = source.directory
        observed["contract"] = source.contract
        return expected

    monkeypatch.setattr(ingestion_module.CsvCicytexDatasetSource, "load", fake_load)

    result = ingestion_module.load_normalized_cicytex(tmp_path)

    assert result is expected
    assert observed == {
        "directory": tmp_path,
        "contract": importlib.import_module(
            "experiment_runner.cicytex.dataset_contract"
        ).CICYTEX_NORMALIZED_V1,
    }
