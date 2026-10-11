"""Contract tests for the site-neutral ensemble demonstration engine."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from experiment_runner.ensemble_demo_training import run_ensemble_demo_training
from experiment_runner.pergamino_ensemble_demo_runner import PERGAMINO_DEMO_PLAN


class _SerializableArtifact:
    """Minimal fitted-object stand-in accepted by the production bundle writer."""

    def __init__(self, n_features: int):
        self.n_features_in_ = n_features


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
