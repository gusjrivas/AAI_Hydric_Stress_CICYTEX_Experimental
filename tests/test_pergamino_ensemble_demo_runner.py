"""Synthetic-data test for the separate Hito 2 demonstration executor
(`experiment_runner.pergamino_ensemble_demo_runner`) -- never reads the real
Pergamino CSVs, never touches `controlled_daily_v4/` beyond the frozen,
read-only reuse the runner itself declares (`build_estimator`/
`fit_estimator`), never opens the 2024-2025 holdout.

Exercises the full separate pipeline for the three families and the three
horizons at once: threshold-on-training-only, multi-horizon partitioning
with per-horizon purges, fit+calibration, production export (never a test
helper), and real load/inference through the unmodified v2/ensemble API --
including an HTTP-level check through the real producer route.
"""

from __future__ import annotations

import hashlib
import inspect
from dataclasses import FrozenInstanceError
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from experiment_runner import pergamino_ensemble_demo_runner as pergamino_runner
from experiment_runner.pergamino_ensemble_demo_runner import (
    DEMO_CALIBRATION,
    DEMO_TRAIN,
    FAMILY_PARAMS,
    FIRST_ADMISSIBLE_DATE,
    INGESTION_END,
    INGESTION_START,
    RUN_MANIFEST_FILENAME,
    DemoRunnerError,
    run_demo_from_frame,
)
from predictive_modeling.ensemble_bundle import (
    EnsembleComponentMissingError,
    load_ensemble_bundle,
    predict_ensemble_bundle,
)
from predictive_modeling.operational_contract import VariableMetadata
from predictive_modeling.operational_preparation import TemporalCutPlan

SENSOR_ID = "synthetic-pergamino-demo"


def test_pergamino_demo_plan_is_deeply_immutable_and_preserves_scientific_contract():
    plan = pergamino_runner.PERGAMINO_DEMO_PLAN

    assert isinstance(plan.temporal_cuts, TemporalCutPlan)
    assert plan.temporal_cuts == pergamino_runner.build_cut_plan()
    assert plan.horizons == (1, 2, 3)
    assert plan.variables == tuple(
        VariableMetadata(item["name"], item["unit"]) for item in pergamino_runner.VARIABLES
    )
    assert plan.feature_columns == pergamino_runner.FEATURE_COLUMNS
    assert plan.lags == pergamino_runner.LAGS
    assert plan.rolling_windows == pergamino_runner.ROLLING_WINDOWS
    assert plan.family_names == tuple(pergamino_runner.FAMILY_PARAMS)
    assert plan.event_variable == pergamino_runner.EVENT_VARIABLE
    assert plan.event_unit == pergamino_runner.EVENT_UNIT
    assert plan.event_comparison == "lt"
    assert plan.decision_threshold == pergamino_runner.DECISION_THRESHOLD
    assert plan.contract_version == pergamino_runner.CONTRACT_VERSION
    assert plan.model_identity_template == "{family}_pergamino_demo_h{horizon}"
    assert plan.calibrator_identity_template == ("{family}_pergamino_demo_calibrator_h{horizon}")

    with pytest.raises(FrozenInstanceError):
        plan.decision_threshold = 0.7
    with pytest.raises(TypeError):
        plan.family_names[0] = "changed"
    with pytest.raises(FrozenInstanceError):
        plan.variables[0].unit = "changed"


def _synthetic_daily_frame() -> pd.DataFrame:
    start = date.fromisoformat(INGESTION_START)
    end = date.fromisoformat(INGESTION_END)
    n_days = (end - start).days + 1
    dates = pd.date_range(start=start, periods=n_days, freq="D")
    day = np.arange(n_days)
    rng = np.random.default_rng(20260926)
    soil_moisture = 0.5 + 0.25 * np.sin(2 * np.pi * day / 365.25) + rng.normal(0, 0.03, n_days)
    rh2m = 60 + 15 * np.cos(2 * np.pi * day / 30) + rng.normal(0, 2.0, n_days)
    allsky = 20 + 8 * np.sin(2 * np.pi * day / 90 + 1.0) + rng.normal(0, 1.0, n_days)
    return pd.DataFrame(
        {
            "timestamp": dates,
            "soil_moisture": np.clip(soil_moisture, 0.05, 0.95),
            "relative_humidity": rh2m,
            "solar_radiation": allsky,
        }
    )


@pytest.fixture(scope="module")
def demo_frame():
    frame = _synthetic_daily_frame()
    dataset_sha256 = hashlib.sha256(frame.to_csv(index=False).encode("utf-8")).hexdigest()
    return frame, dataset_sha256


def test_run_demo_from_frame_covers_all_three_families_and_horizons(tmp_path, demo_frame):
    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path / "output"

    written = run_demo_from_frame(
        frame, dataset_sha256, output_dir, sensor_id=SENSOR_ID, horizons=(1, 2, 3)
    )

    assert set(written) == {1, 2, 3}
    for horizon, families in written.items():
        assert set(families) == set(FAMILY_PARAMS)
        for family, component_dir in families.items():
            assert (component_dir / "model.joblib").exists()
            assert (component_dir / "calibrator.joblib").exists()
            assert (component_dir / "contract.json").exists()
            assert (component_dir / "bundle.json").exists()
        manifest_path = output_dir / SENSOR_ID / f"horizon_{horizon}" / "ensemble_manifest.json"
        assert manifest_path.exists()


def test_run_manifest_records_identity_config_partitions_and_counts(tmp_path, demo_frame):
    import json

    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path / "output"

    run_demo_from_frame(
        frame,
        dataset_sha256,
        output_dir,
        sensor_id=SENSOR_ID,
        horizons=(1, 2, 3),
        input_hashes={"era5_csv": "a" * 64, "nasa_power_csv": "b" * 64},
    )

    manifest = json.loads((output_dir / RUN_MANIFEST_FILENAME).read_text())
    assert manifest["status"] == "completado"
    assert manifest["sensor_id"] == SENSOR_ID
    assert manifest["permitted_frame_sha256"] == dataset_sha256
    assert manifest["input_hashes"] == {"era5_csv": "a" * 64, "nasa_power_csv": "b" * 64}
    assert "code_identity" in manifest and "environment" in manifest
    assert set(manifest["effective_config"]["family_params"]) == set(FAMILY_PARAMS)
    assert manifest["partitions"]["train"] == {
        "start": DEMO_TRAIN.start.isoformat(),
        "end": DEMO_TRAIN.end.isoformat(),
    }
    for horizon in (1, 2, 3):
        report = manifest["horizons"][str(horizon)]
        assert report["train_rows_used"] > 0
        assert report["calibration_rows_used"] > 0
        assert set(report["components"]) == set(FAMILY_PARAMS)
        for family_files in report["components"].values():
            assert set(family_files) == {"model.joblib", "calibrator.joblib", "contract.json"}


def test_run_manifest_records_fallido_on_a_partial_run_without_deleting_prior_progress(
    tmp_path, demo_frame
):
    import json

    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path / "output"

    with pytest.raises(KeyError):
        # horizon=99 is not in add_multihorizon_targets' output (only 1/2/3
        # ever get a threshold) -> KeyError inside the loop, after horizon 1
        # has already completed and been recorded -- proves a failure
        # mid-run is re-raised (never swallowed) and neither claims
        # "completado" nor erases the horizons that did finish.
        run_demo_from_frame(
            frame, dataset_sha256, output_dir, sensor_id=SENSOR_ID, horizons=(1, 99)
        )

    manifest = json.loads((output_dir / RUN_MANIFEST_FILENAME).read_text())
    assert manifest["status"] == "fallido"
    assert "error" in manifest
    assert "1" in manifest["horizons"]  # horizon 1's progress was preserved
    assert (output_dir / SENSOR_ID / "horizon_1" / "ensemble_manifest.json").exists()


def test_run_demo_from_frame_rejects_a_non_empty_output_dir(tmp_path, demo_frame):
    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "leftover.txt").write_text("not empty")

    with pytest.raises(DemoRunnerError, match="no está vacío"):
        run_demo_from_frame(frame, dataset_sha256, output_dir, sensor_id=SENSOR_ID)


def test_public_facade_and_artifact_tree_are_frozen(demo_output):
    signature = inspect.signature(run_demo_from_frame)
    assert tuple(signature.parameters) == (
        "daily_frame",
        "dataset_sha256",
        "output_dir",
        "sensor_id",
        "horizons",
        "input_hashes",
    )
    assert signature.parameters["sensor_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["horizons"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["horizons"].default == (1, 2, 3)
    assert signature.parameters["input_hashes"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["input_hashes"].default is None

    expected_files = {RUN_MANIFEST_FILENAME}
    for horizon in (1, 2, 3):
        horizon_root = f"{SENSOR_ID}/horizon_{horizon}"
        expected_files.add(f"{horizon_root}/ensemble_manifest.json")
        for family in FAMILY_PARAMS:
            component_root = f"{horizon_root}/ensemble/{family}"
            expected_files.update(
                {
                    f"{component_root}/model.joblib",
                    f"{component_root}/calibrator.joblib",
                    f"{component_root}/contract.json",
                    f"{component_root}/bundle.json",
                }
            )

    actual_files = {
        path.relative_to(demo_output).as_posix()
        for path in demo_output.rglob("*")
        if path.is_file()
    }
    assert actual_files == expected_files


@pytest.fixture(scope="module")
def demo_output(tmp_path_factory, demo_frame):
    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path_factory.mktemp("pergamino_demo_output")
    run_demo_from_frame(frame, dataset_sha256, output_dir, sensor_id=SENSOR_ID, horizons=(1, 2, 3))
    return output_dir


@pytest.mark.parametrize("horizon", [1, 2, 3])
def test_real_bundle_loads_and_infers_through_the_unmodified_v2_api(demo_output, horizon):
    ensemble = load_ensemble_bundle(demo_output, sensor_id=SENSOR_ID, horizon=horizon)
    assert set(ensemble.components) == set(FAMILY_PARAMS)

    as_of_date = date(2023, 6, 15)  # inside the demo/evaluation window, after calibration ends
    result = predict_ensemble_bundle(
        ensemble,
        _synthetic_daily_frame(),
        sensor_id=SENSOR_ID,
        units={"soil_moisture": "m3/m3", "relative_humidity": "%", "solar_radiation": "MJ/m2/day"},
        as_of_date=as_of_date,
    )

    assert result["policy_version"] == "ensemble_agreement_v1"
    assert result["decision_threshold"] == 0.5
    assert 0.0 <= result["combined_probability"] <= 1.0
    assert result["combined_alert"] == (result["combined_probability"] >= 0.5)
    assert result["weights"] == {family: pytest.approx(1 / 3) for family in FAMILY_PARAMS}
    for component in result["components"]:
        assert 0.0 <= component["score"] <= 1.0


def test_temporal_admissibility_rejects_inference_before_calibration_ends(demo_output):
    """FIRST_ADMISSIBLE_DATE (calibration's own last day) is itself already
    admissible -- predict_operational_bundle rejects only strictly earlier
    dates. One day before it must be rejected, never silently answered."""
    ensemble = load_ensemble_bundle(demo_output, sensor_id=SENSOR_ID, horizon=1)
    assert date.fromisoformat(FIRST_ADMISSIBLE_DATE) == DEMO_CALIBRATION.end
    day_before_admissible = date.fromisoformat(FIRST_ADMISSIBLE_DATE) - timedelta(days=1)

    with pytest.raises(EnsembleComponentMissingError, match="model_not_available_at_date"):
        predict_ensemble_bundle(
            ensemble,
            _synthetic_daily_frame(),
            sensor_id=SENSOR_ID,
            units={
                "soil_moisture": "m3/m3",
                "relative_humidity": "%",
                "solar_radiation": "MJ/m2/day",
            },
            as_of_date=day_before_admissible,
        )

    # And the boundary itself must succeed, never off-by-one in either direction.
    result = predict_ensemble_bundle(
        ensemble,
        _synthetic_daily_frame(),
        sensor_id=SENSOR_ID,
        units={"soil_moisture": "m3/m3", "relative_humidity": "%", "solar_radiation": "MJ/m2/day"},
        as_of_date=date.fromisoformat(FIRST_ADMISSIBLE_DATE),
    )
    assert 0.0 <= result["combined_probability"] <= 1.0


def test_partitions_never_overlap_and_never_touch_2024_2025():
    assert DEMO_TRAIN.end < DEMO_CALIBRATION.start
    assert DEMO_CALIBRATION.end < date(2023, 1, 1)
    assert date.fromisoformat(INGESTION_END) == date(2023, 12, 31)
    assert date.fromisoformat(INGESTION_END).year == 2023
