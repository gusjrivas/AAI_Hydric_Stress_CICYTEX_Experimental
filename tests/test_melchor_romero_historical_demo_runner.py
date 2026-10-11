"""Test for the separate, non-frozen demonstration executor
`experiment_runner.melchor_romero_historical_demo_runner` -- the second real
historical-demonstration site (HU6 `architecture-integration`), generalizing
the pattern already established by `pergamino_ensemble_demo_runner.py`.

Unlike the Pergamino demo tests, this module exercises the REAL,
already-committed dataset (`data/melchor_romero_2024_consolidado.parquet`) --
no synthetic fixture is needed since the real data is small, fast, and
already versioned in the repository. Never touches
`replay_packages/base-seed4-1157696b7b-v2` (the frozen historical-replay
package for the same dataset) and never imports `historical_replay.*`.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import FrozenInstanceError
from datetime import date, timedelta

import pytest

from experiment_runner import melchor_romero_historical_demo_runner as melchor_runner
from experiment_runner.ensemble_demo_training import (
    EnsembleDemoTrainingResult,
    HorizonDemoTrainingResult,
)
from experiment_runner.melchor_romero_historical_demo_runner import (
    DEMO_CALIBRATION,
    DEMO_TRAIN,
    FAMILY_PARAMS,
    FIRST_ADMISSIBLE_DATE,
    RUN_MANIFEST_FILENAME,
    DemoRunnerError,
    build_daily_frame_from_repo_dataset,
    run_demo_from_frame,
)
from predictive_modeling.ensemble_bundle import (
    EnsembleComponentMissingError,
    load_ensemble_bundle,
    predict_ensemble_bundle,
)
from predictive_modeling.operational_contract import VariableMetadata
from predictive_modeling.operational_preparation import (
    TARGET_LABEL_COLUMN as CANONICAL_TARGET_LABEL,
)
from predictive_modeling.operational_preparation import TemporalCutPlan
from predictive_modeling.operational_run import build_feature_frame as canonical_build_feature_frame

SENSOR_ID = "test-melchor-romero-demo"


def test_melchor_demo_plan_is_deeply_immutable_and_preserves_scientific_contract():
    plan = melchor_runner.MELCHOR_ROMERO_DEMO_PLAN

    assert isinstance(plan.temporal_cuts, TemporalCutPlan)
    assert plan.temporal_cuts == melchor_runner.build_cut_plan()
    assert plan.horizons == (1, 2, 3)
    assert plan.variables == tuple(
        VariableMetadata(item["name"], item["unit"]) for item in melchor_runner.VARIABLES
    )
    assert plan.feature_columns == melchor_runner.FEATURE_COLUMNS
    assert plan.lags == melchor_runner.LAGS
    assert plan.rolling_windows == melchor_runner.ROLLING_WINDOWS
    assert plan.family_names == tuple(melchor_runner.FAMILY_PARAMS)
    assert plan.event_variable == melchor_runner.EVENT_VARIABLE
    assert plan.event_unit == melchor_runner.EVENT_UNIT
    assert plan.event_comparison == "lt"
    assert plan.decision_threshold == melchor_runner.DECISION_THRESHOLD
    assert plan.contract_version == melchor_runner.CONTRACT_VERSION
    assert plan.model_identity_template == "{family}_melchor_romero_demo_h{horizon}"
    assert plan.calibrator_identity_template == (
        "{family}_melchor_romero_demo_calibrator_h{horizon}"
    )

    with pytest.raises(FrozenInstanceError):
        plan.decision_threshold = 0.7
    with pytest.raises(TypeError):
        plan.family_names[0] = "changed"
    with pytest.raises(FrozenInstanceError):
        plan.variables[0].unit = "changed"


@pytest.fixture(scope="module")
def demo_frame():
    return build_daily_frame_from_repo_dataset()


def test_real_dataset_has_no_missing_feature_values_after_causal_imputation(demo_frame):
    frame, _ = demo_frame
    assert frame[["soil_moisture", "relative_humidity", "solar_radiation"]].isna().sum().sum() == 0


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
    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path / "output"

    run_demo_from_frame(frame, dataset_sha256, output_dir, sensor_id=SENSOR_ID, horizons=(1, 2, 3))

    manifest = json.loads((output_dir / RUN_MANIFEST_FILENAME).read_text())
    assert manifest["status"] == "completado"
    assert manifest["sensor_id"] == SENSOR_ID
    assert manifest["dataset_name"] == "melchor_romero_2024_consolidado"
    assert manifest["permitted_frame_sha256"] == dataset_sha256
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
    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path / "output"

    with pytest.raises(KeyError):
        # horizon=99 is not in add_multihorizon_targets' output (only 1/2/3
        # ever get a threshold) -> KeyError inside the loop, after horizon 1
        # has already completed and been recorded.
        run_demo_from_frame(
            frame, dataset_sha256, output_dir, sensor_id=SENSOR_ID, horizons=(1, 99)
        )

    manifest = json.loads((output_dir / RUN_MANIFEST_FILENAME).read_text())
    assert manifest["status"] == "fallido"
    assert manifest["error"] == "KeyError: 99"
    assert manifest["physical_threshold"] > 0
    assert set(manifest["horizons"]) == {"1"}
    assert manifest["horizons"]["1"]["train_rows_used"] > 0
    assert (output_dir / SENSOR_ID / "horizon_1" / "ensemble_manifest.json").exists()
    assert not (output_dir / SENSOR_ID / "horizon_99").exists()


def test_run_demo_from_frame_rejects_a_non_empty_output_dir(tmp_path, demo_frame):
    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "leftover.txt").write_text("not empty")

    with pytest.raises(DemoRunnerError, match="no está vacío"):
        run_demo_from_frame(frame, dataset_sha256, output_dir, sensor_id=SENSOR_ID)


def test_run_demo_from_frame_delegates_to_the_shared_engine(tmp_path, demo_frame, monkeypatch):
    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path / "output"
    captured = {}
    component_dir = output_dir / SENSOR_ID / "horizon_1" / "ensemble" / "family"
    horizon_result = HorizonDemoTrainingResult(
        horizon=1,
        written_items=(("family", component_dir),),
        train_rows_used=10,
        train_rows_excluded_by_purge=2,
        calibration_rows_used=5,
        calibration_rows_excluded_by_purge=1,
        component_file_items=(("family", (("model.joblib", "a" * 64),)),),
    )

    def fake_engine(daily_frame, **kwargs):
        captured["daily_frame"] = daily_frame
        captured.update(kwargs)
        kwargs["on_threshold_resolved"](0.23)
        kwargs["on_horizon_completed"](horizon_result)
        return EnsembleDemoTrainingResult(0.23, (horizon_result,))

    monkeypatch.setattr(melchor_runner, "run_ensemble_demo_training", fake_engine, raising=False)

    written = run_demo_from_frame(
        frame, dataset_sha256, output_dir, sensor_id=SENSOR_ID, horizons=(1,)
    )

    assert captured["daily_frame"] is frame
    assert captured["dataset_sha256"] == dataset_sha256
    assert captured["output_dir"] == output_dir
    assert captured["sensor_id"] == SENSOR_ID
    assert captured["horizons"] == (1,)
    assert captured["plan"] is melchor_runner.MELCHOR_ROMERO_DEMO_PLAN
    assert captured["resolve_threshold"] is melchor_runner.resolve_training_threshold
    assert captured["fit_component"] is melchor_runner.fit_and_calibrate
    assert written == {1: {"family": component_dir}}
    manifest = json.loads((output_dir / RUN_MANIFEST_FILENAME).read_text())
    assert manifest["status"] == "completado"
    assert manifest["physical_threshold"] == 0.23
    assert manifest["horizons"]["1"] == horizon_result.manifest_report()


@pytest.fixture(scope="module")
def demo_output(tmp_path_factory, demo_frame):
    frame, dataset_sha256 = demo_frame
    output_dir = tmp_path_factory.mktemp("melchor_romero_demo_output")
    run_demo_from_frame(frame, dataset_sha256, output_dir, sensor_id=SENSOR_ID, horizons=(1, 2, 3))
    return output_dir


def test_public_facade_reexports_and_artifact_tree_are_frozen(demo_output):
    signature = inspect.signature(run_demo_from_frame)
    assert tuple(signature.parameters) == (
        "daily_frame",
        "dataset_sha256",
        "output_dir",
        "sensor_id",
        "horizons",
    )
    assert signature.parameters["sensor_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["horizons"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["horizons"].default == (1, 2, 3)
    assert melchor_runner.TARGET_LABEL_COLUMN == CANONICAL_TARGET_LABEL
    assert melchor_runner.build_feature_frame is canonical_build_feature_frame

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


@pytest.mark.parametrize("horizon", [1, 2, 3])
def test_real_bundle_loads_and_infers_through_the_unmodified_v2_api(demo_output, horizon):
    ensemble = load_ensemble_bundle(demo_output, sensor_id=SENSOR_ID, horizon=horizon)
    assert set(ensemble.components) == set(FAMILY_PARAMS)

    as_of_date = date(2024, 10, 25)  # inside the demo/evaluation window, after calibration ends
    frame, _ = build_daily_frame_from_repo_dataset()
    result = predict_ensemble_bundle(
        ensemble,
        frame,
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
    dates."""
    ensemble = load_ensemble_bundle(demo_output, sensor_id=SENSOR_ID, horizon=1)
    assert date.fromisoformat(FIRST_ADMISSIBLE_DATE) == DEMO_CALIBRATION.end
    day_before_admissible = date.fromisoformat(FIRST_ADMISSIBLE_DATE) - timedelta(days=1)
    frame, _ = build_daily_frame_from_repo_dataset()

    with pytest.raises(EnsembleComponentMissingError, match="model_not_available_at_date"):
        predict_ensemble_bundle(
            ensemble,
            frame,
            sensor_id=SENSOR_ID,
            units={
                "soil_moisture": "m3/m3",
                "relative_humidity": "%",
                "solar_radiation": "MJ/m2/day",
            },
            as_of_date=day_before_admissible,
        )

    result = predict_ensemble_bundle(
        ensemble,
        frame,
        sensor_id=SENSOR_ID,
        units={"soil_moisture": "m3/m3", "relative_humidity": "%", "solar_radiation": "MJ/m2/day"},
        as_of_date=date.fromisoformat(FIRST_ADMISSIBLE_DATE),
    )
    assert 0.0 <= result["combined_probability"] <= 1.0


def test_partitions_never_overlap_and_stay_within_2024():
    assert DEMO_TRAIN.end < DEMO_CALIBRATION.start
    assert DEMO_CALIBRATION.end < date(2024, 10, 20)
    assert DEMO_TRAIN.start.year == 2024
    # Reuses the split date already established/verified for this exact
    # dataset in openspec/specs/architecture-integration/spec.md.
    assert DEMO_CALIBRATION.end == date(2024, 10, 19)


def test_causal_imputation_never_uses_a_later_partitions_values():
    """A tamper-based non-leakage proof: mutating evaluation-window rows of
    the raw committed dataset must never change the train/calibration
    imputed values or the training-only threshold -- imputation is strictly
    forward, partition by partition."""
    import pandas as pd

    from data_ingestion.storage import load_dataset_snapshot
    from experiment_runner.melchor_romero_historical_demo_runner import (
        DEMO_ALLOWED_DATA,
        FEATURE_COLUMNS,
        _causal_impute_by_partition,
        resolve_training_threshold,
    )

    snapshot = load_dataset_snapshot("melchor_romero_2024_consolidado")
    df = snapshot.dataframe
    base = df[["timestamp", *FEATURE_COLUMNS]].copy()
    base = base.loc[DEMO_ALLOWED_DATA.contains(base["timestamp"])].reset_index(drop=True)

    tampered = base.copy()
    is_evaluation = tampered["timestamp"] >= pd.Timestamp("2024-10-20")
    tampered.loc[is_evaluation, "soil_moisture"] = 999.0

    imputed_base = _causal_impute_by_partition(base, list(FEATURE_COLUMNS))
    imputed_tampered = _causal_impute_by_partition(tampered, list(FEATURE_COLUMNS))

    before_eval = imputed_base["timestamp"] < pd.Timestamp("2024-10-20")
    pd.testing.assert_frame_equal(
        imputed_base.loc[before_eval].reset_index(drop=True),
        imputed_tampered.loc[before_eval].reset_index(drop=True),
    )
    assert resolve_training_threshold(imputed_base) == resolve_training_threshold(imputed_tampered)
