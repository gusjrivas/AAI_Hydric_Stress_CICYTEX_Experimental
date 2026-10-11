"""Contract tests for the site-neutral ensemble demonstration engine."""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
from datetime import date

import numpy as np
import pandas as pd
import pytest

from experiment_runner import ensemble_demo_training as ensemble_training
from experiment_runner import melchor_romero_historical_demo_runner as melchor_runner
from experiment_runner import pergamino_ensemble_demo_runner as pergamino_runner
from experiment_runner.ensemble_demo_training import run_ensemble_demo_training
from experiment_runner.pergamino_ensemble_demo_runner import PERGAMINO_DEMO_PLAN


class _SerializableArtifact:
    """Minimal fitted-object stand-in accepted by the production bundle writer."""

    def __init__(self, n_features: int):
        self.n_features_in_ = n_features


def test_family_spec_is_deeply_immutable_and_returns_defensive_parameter_copies():
    source = {
        "C": 1.0,
        "solver": "lbfgs",
        "max_iter": 2000,
        "enabled": True,
        "optional": None,
    }
    spec = ensemble_training.EnsembleFamilySpec.from_mapping("logistic_regression", source)

    source["C"] = 99.0
    returned = spec.parameters()
    returned["solver"] = "changed"

    assert spec.family == "logistic_regression"
    assert spec.parameters() == {
        "C": 1.0,
        "solver": "lbfgs",
        "max_iter": 2000,
        "enabled": True,
        "optional": None,
    }
    with pytest.raises(TypeError):
        spec.parameter_items[0] = ("C", 2.0)
    with pytest.raises(FrozenInstanceError):
        spec.family = "changed"
    with pytest.raises(ValueError, match="duplicates"):
        ensemble_training.EnsembleFamilySpec("duplicate", (("C", 1.0), ("C", 2.0)))


@pytest.mark.parametrize(
    ("family", "parameters"),
    [
        ("", {"C": 1.0}),
        ("logistic_regression", {"C": float("nan")}),
        ("logistic_regression", {"nested": {"C": 1.0}}),
    ],
)
def test_family_spec_rejects_invalid_scientific_configuration(family, parameters):
    with pytest.raises((TypeError, ValueError)):
        ensemble_training.EnsembleFamilySpec.from_mapping(family, parameters)


@pytest.mark.parametrize(
    ("runner", "plan_name"),
    [
        (pergamino_runner, "PERGAMINO_DEMO_PLAN"),
        (melchor_runner, "MELCHOR_ROMERO_DEMO_PLAN"),
    ],
)
def test_plan_is_authoritative_when_public_family_params_are_mutated(
    runner, plan_name, monkeypatch
):
    public_snapshot = copy.deepcopy(runner.FAMILY_PARAMS)
    plan = getattr(runner, plan_name)

    assert plan.family_params_dict() == public_snapshot
    assert plan.family_names == tuple(public_snapshot)
    monkeypatch.setitem(runner.FAMILY_PARAMS["logistic_regression"], "C", 999.0)

    assert plan.params_for("logistic_regression")["C"] == 1.0
    if runner is pergamino_runner:
        manifest = runner._new_run_manifest(
            sensor_id="sensor",
            horizons=(1,),
            dataset_sha256="a" * 64,
            input_hashes={},
        )
    else:
        manifest = runner._new_run_manifest(
            sensor_id="sensor",
            horizons=(1,),
            dataset_sha256="a" * 64,
            dataset_name=runner.DATASET_NAME,
        )
    assert manifest["effective_config"]["family_params"] == public_snapshot

    captured = {}

    def fake_fit_estimator(family, parameters, X_train, y_train):
        captured.update(family=family, parameters=parameters)
        return _SerializableArtifact(X_train.shape[1])

    class FakeCalibrator:
        def __init__(self, estimator, *, method):
            self.estimator = estimator
            self.method = method

        def fit(self, X_calib, y_calib):
            return self

    monkeypatch.setattr(runner, "fit_estimator", fake_fit_estimator)
    monkeypatch.setattr(runner, "CalibratedClassifierCV", FakeCalibrator)
    X = np.zeros((2, 1))
    y = np.array([0, 1])
    runner.fit_and_calibrate("logistic_regression", X, y, X, y)

    assert captured == {
        "family": "logistic_regression",
        "parameters": public_snapshot["logistic_regression"],
    }
    assert captured["parameters"] is not runner.FAMILY_PARAMS["logistic_regression"]


def _daily_frame() -> pd.DataFrame:
    dates = pd.date_range(date(2019, 1, 1), date(2023, 12, 31), freq="D")
    day = np.arange(len(dates), dtype=float)
    return pd.DataFrame(
        {
            "timestamp": dates,
            "soil_moisture": 0.45 + 0.2 * np.sin(day / 31),
            "relative_humidity": 60 + 10 * np.cos(day / 17),
            "solar_radiation": 20 + 5 * np.sin(day / 11),
        }
    )


def test_shared_engine_preserves_family_order_and_returns_manifest_ready_results(tmp_path):
    fit_calls: list[tuple[str, int, int]] = []
    completed = []

    def fit_component(family, X_train, y_train, X_calib, y_calib):
        fit_calls.append((family, len(X_train), len(X_calib)))
        assert len(X_train) == len(y_train)
        assert len(X_calib) == len(y_calib)
        return _SerializableArtifact(X_train.shape[1]), _SerializableArtifact(X_train.shape[1])

    result = run_ensemble_demo_training(
        _daily_frame(),
        dataset_sha256="a" * 64,
        output_dir=tmp_path,
        sensor_id="site-neutral-sensor",
        horizons=(1,),
        plan=PERGAMINO_DEMO_PLAN,
        resolve_threshold=lambda frame: 0.23,
        fit_component=fit_component,
        on_horizon_completed=completed.append,
    )

    assert result.threshold == 0.23
    assert tuple(family for family, _, _ in fit_calls) == PERGAMINO_DEMO_PLAN.family_names
    assert len(completed) == 1
    assert result.horizon_results == tuple(completed)

    horizon_result = result.horizon_results[0]
    assert horizon_result.horizon == 1
    assert horizon_result.train_rows_used > 0
    assert horizon_result.calibration_rows_used > 0
    assert tuple(horizon_result.written) == PERGAMINO_DEMO_PLAN.family_names
    assert result.written == {1: horizon_result.written}

    report = horizon_result.manifest_report()
    assert report["train_rows_used"] == horizon_result.train_rows_used
    assert report["calibration_rows_used"] == horizon_result.calibration_rows_used
    assert tuple(report["components"]) == PERGAMINO_DEMO_PLAN.family_names
    for family, component_dir in horizon_result.written.items():
        assert component_dir == tmp_path / "site-neutral-sensor" / "horizon_1" / "ensemble" / family
        assert set(report["components"][family]) == {
            "model.joblib",
            "calibrator.joblib",
            "contract.json",
        }
        assert (component_dir / "bundle.json").exists()
    assert (tmp_path / "site-neutral-sensor" / "horizon_1" / "ensemble_manifest.json").exists()
