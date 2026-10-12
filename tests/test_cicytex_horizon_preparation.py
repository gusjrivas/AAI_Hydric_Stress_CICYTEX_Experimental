from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal


def _protocol():
    return importlib.import_module("experiment_runner.cicytex.training_protocol")


def _multi_sensor_frame(days: int = 120) -> pd.DataFrame:
    rows = []
    for sensor, base in (("CP1_S1", 0.18), ("CP1_S2", 0.42)):
        for day, timestamp in enumerate(pd.date_range("2023-01-01", periods=days, freq="D")):
            rows.append(
                {
                    "sensor_id": sensor,
                    "timestamp": timestamp,
                    "soil_moisture": base + ((day % 17) - 8) / 1000,
                }
            )
    return pd.DataFrame(rows)


def _legacy_preparation(data: pd.DataFrame, horizon: int):
    protocol = _protocol()
    featured = protocol.build_features(data, horizon).dropna(
        subset=[*protocol.FEATURES, "future_soil_moisture"]
    )
    split = protocol.temporal_split(featured["target_timestamp"])
    parts = {
        name: protocol.select_partition(featured, split, name)
        for name in ("train", "calibration", "validation", "evaluation")
    }
    threshold = float(parts["train"]["future_soil_moisture"].quantile(0.20))
    return split, threshold, parts


@pytest.mark.parametrize("horizon", [1, 2, 3])
def test_prepare_horizon_is_exact_composition_of_public_protocol(horizon: int):
    protocol = _protocol()
    prepare_horizon = getattr(protocol, "prepare_horizon")
    data = _multi_sensor_frame()
    expected_split, expected_threshold, expected_parts = _legacy_preparation(data, horizon)

    actual = prepare_horizon(data, horizon)

    assert actual.horizon_days == horizon
    assert actual.split == expected_split
    assert actual.threshold_train_p20 == expected_threshold
    for name, expected in expected_parts.items():
        assert_frame_equal(
            getattr(actual, name),
            expected,
            check_exact=True,
            check_dtype=True,
            check_like=False,
        )


def test_prepare_horizon_uses_training_only_for_threshold():
    protocol = _protocol()
    prepare_horizon = getattr(protocol, "prepare_horizon")
    baseline = _multi_sensor_frame()
    changed_evaluation = baseline.copy(deep=True)
    late = changed_evaluation["timestamp"] >= changed_evaluation[
        "timestamp"
    ].max() - pd.to_timedelta(9, unit="D")
    changed_evaluation.loc[late, "soil_moisture"] = 0.99

    original = prepare_horizon(baseline, 3)
    mutated = prepare_horizon(changed_evaluation, 3)

    assert original.split == mutated.split
    assert_frame_equal(original.train, mutated.train, check_exact=True)
    assert original.threshold_train_p20 == mutated.threshold_train_p20


def test_prepare_horizon_does_not_mutate_input_and_returns_isolated_copies():
    protocol = _protocol()
    prepare_horizon = getattr(protocol, "prepare_horizon")
    data = _multi_sensor_frame()
    before = data.copy(deep=True)

    prepared = prepare_horizon(data, 2)
    calibration_before = prepared.calibration.copy(deep=True)
    prepared.train.iloc[0, prepared.train.columns.get_loc("soil_moisture")] = -1.0

    assert_frame_equal(data, before, check_exact=True)
    assert_frame_equal(prepared.calibration, calibration_before, check_exact=True)


def test_prepare_horizon_keeps_runner_specific_labels_outside_protocol():
    protocol = _protocol()
    prepared = getattr(protocol, "prepare_horizon")(_multi_sensor_frame(), 1)

    for frame in (
        prepared.train,
        prepared.calibration,
        prepared.validation,
        prepared.evaluation,
    ):
        assert "stress_proxy" not in frame.columns
        assert "observed_label" not in frame.columns


def test_prepare_horizon_preserves_boundaries_and_row_accounting():
    protocol = _protocol()
    prepared = getattr(protocol, "prepare_horizon")(_multi_sensor_frame(), 3)
    parts = {
        name: getattr(prepared, name)
        for name in ("train", "calibration", "validation", "evaluation")
    }

    indexes = [set(frame.index) for frame in parts.values()]
    assert sum(len(index) for index in indexes) == len(set().union(*indexes))
    assert parts["train"]["target_timestamp"].max() <= prepared.split.train_end
    assert parts["calibration"]["target_timestamp"].min() > prepared.split.train_end
    assert parts["calibration"]["target_timestamp"].max() <= prepared.split.calibration_end
    assert parts["validation"]["target_timestamp"].min() > prepared.split.calibration_end
    assert parts["validation"]["target_timestamp"].max() <= prepared.split.validation_end
    assert parts["evaluation"]["target_timestamp"].min() > prepared.split.validation_end
    assert parts["evaluation"]["target_timestamp"].max() <= prepared.split.evaluation_end


def test_runners_delegate_all_horizons_to_shared_preparation():
    root = Path(__file__).parents[1] / "src" / "experiment_runner" / "cicytex"
    for filename in ("experiment.py", "causal_ensemble.py"):
        tree = ast.parse((root / filename).read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "experiment_runner.cicytex.training_protocol"
            for alias in node.names
        }
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert "prepare_horizon" in imported
        assert "prepare_horizon" in called
        assert not {"build_features", "temporal_split", "select_partition"} & called

    causal_tree = ast.parse((root / "causal_ensemble.py").read_text(encoding="utf-8"))
    causal_modules = {
        node.module for node in ast.walk(causal_tree) if isinstance(node, ast.ImportFrom)
    }
    assert "experiment_runner.cicytex.experiment" not in causal_modules
