from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal


def _protocol():
    return importlib.import_module("experiment_runner.cicytex.training_protocol")


def _daily_sensor(sensor_id: str, base: float, days: int = 100) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sensor_id": [sensor_id] * days,
            "timestamp": pd.date_range("2023-01-01", periods=days, freq="D"),
            "soil_moisture": [base + day / 1000 for day in range(days)],
        }
    )


def test_training_protocol_preserves_the_legacy_public_contract():
    protocol = _protocol()
    legacy = importlib.import_module("experiment_runner.cicytex.experiment")

    assert legacy.FEATURES is protocol.FEATURES
    assert legacy.FAMILY_PARAMS is protocol.FAMILY_PARAMS
    assert legacy.TemporalSplit is protocol.TemporalSplit
    assert legacy.build_features is protocol.build_features
    assert legacy.temporal_split is protocol.temporal_split
    assert legacy._part is protocol.select_partition


@pytest.mark.parametrize("horizon", [1, 2, 3])
def test_build_features_is_exact_per_sensor_and_does_not_mutate_input(horizon: int):
    protocol = _protocol()
    original = pd.concat(
        [_daily_sensor("CP1_S2", 0.8, 12), _daily_sensor("CP1_S1", 0.1, 12)],
        ignore_index=True,
    )
    before = original.copy(deep=True)

    actual = protocol.build_features(original, horizon)

    assert_frame_equal(original, before)
    assert actual["sensor_id"].drop_duplicates().tolist() == ["CP1_S1", "CP1_S2"]
    second_sensor = actual.loc[actual["sensor_id"] == "CP1_S2"].reset_index(drop=True)
    assert pd.isna(second_sensor.loc[0, "lag1"])
    assert pd.isna(second_sensor.loc[0, "roll_mean_3"])
    assert second_sensor.loc[3, "lag3"] == pytest.approx(0.8)
    assert second_sensor.loc[6, "roll_mean_7"] == pytest.approx(0.803)
    assert second_sensor.loc[0, "future_soil_moisture"] == pytest.approx(0.8 + horizon / 1000)
    assert second_sensor.loc[0, "target_timestamp"] == pd.Timestamp("2023-01-01") + pd.to_timedelta(
        horizon, unit="D"
    )


def test_temporal_split_uses_the_existing_50_65_80_100_boundaries():
    protocol = _protocol()
    dates = pd.Series(pd.date_range("2023-01-01", periods=100, freq="D"))

    split = protocol.temporal_split(dates)

    assert split == protocol.TemporalSplit(
        train_end=pd.Timestamp("2023-02-19"),
        calibration_end=pd.Timestamp("2023-03-06"),
        validation_end=pd.Timestamp("2023-03-21"),
        evaluation_end=pd.Timestamp("2023-04-10"),
    )


def test_temporal_split_rejects_less_than_sixty_unique_dates():
    protocol = _protocol()

    with pytest.raises(
        ValueError, match="Se requieren al menos 60 fechas para cuatro particiones temporales"
    ):
        protocol.temporal_split(pd.Series(pd.date_range("2023-01-01", periods=59, freq="D")))


def test_select_partition_is_exhaustive_non_overlapping_and_returns_copies():
    protocol = _protocol()
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    frame = pd.DataFrame({"target_timestamp": dates, "value": range(100)})
    split = protocol.temporal_split(frame["target_timestamp"])

    parts = {
        name: protocol.select_partition(frame, split, name)
        for name in ("train", "calibration", "validation", "evaluation")
    }

    assert {name: len(part) for name, part in parts.items()} == {
        "train": 50,
        "calibration": 15,
        "validation": 15,
        "evaluation": 20,
    }
    assert set().union(*(set(part.index) for part in parts.values())) == set(frame.index)
    assert sum(len(part) for part in parts.values()) == len(frame)
    parts["train"].loc[0, "value"] = -1
    assert frame.loc[0, "value"] == 0


def test_select_partition_rejects_unknown_partition():
    protocol = _protocol()
    frame = pd.DataFrame({"target_timestamp": pd.date_range("2023-01-01", periods=60)})
    split = protocol.temporal_split(frame["target_timestamp"])

    with pytest.raises(ValueError, match="unknown"):
        protocol.select_partition(frame, split, "unknown")


def test_cicytex_runners_depend_on_training_protocol_not_on_each_other():
    root = Path(__file__).parents[1] / "src" / "experiment_runner" / "cicytex"
    causal_tree = ast.parse((root / "causal_ensemble.py").read_text(encoding="utf-8"))
    experiment_tree = ast.parse((root / "experiment.py").read_text(encoding="utf-8"))

    causal_imports = {
        node.module for node in ast.walk(causal_tree) if isinstance(node, ast.ImportFrom)
    }
    experiment_imports = {
        node.module for node in ast.walk(experiment_tree) if isinstance(node, ast.ImportFrom)
    }

    assert "experiment_runner.cicytex.experiment" not in causal_imports
    assert "experiment_runner.cicytex.training_protocol" in causal_imports
    assert "experiment_runner.cicytex.training_protocol" in experiment_imports
