"""Separate, non-frozen demonstration executor for Hito 2 of the ensemble
operational integration (PR #217). Builds a real, 3-family, 3-horizon
`ensemble_agreement_v1` bundle from the real Pergamino raw CSVs -- never a
re-execution of the closed `controlled_daily_v4_external_pergamino`
campaign (`docs/design/ensemble-real-enablement-plan.md`).

Explicitly never imports or calls `controlled_daily_v4.cli`,
`stage_a_runner`/`stage_b_runner`/`stage_c_runner`, `freezing.py`,
`holdout_ledger.py`, or anything under `openspec/scientific-closure/`.
Never writes into `/home/gus/scientific-closure-runtime/`,
`openspec/scientific-closure/`, or `replay_packages/`.

What IS reused, read-only, unmodified:
- `controlled_daily_v4.provenance.validate_pergamino_provenance` and
  `controlled_daily_v4.ingestion.*` -- pure CSV parsing/aggregation/date
  restriction, no selection or training logic.
- `controlled_daily_v4.models.build_estimator`/`fit_estimator` -- the three
  frozen family builders (identical reuse to Hito 1's
  `tests/test_ensemble_bundle_real_families.py`).
- `predictive_modeling.operational_preparation.add_multihorizon_targets`/
  `partition_labeled_horizon` -- genuinely horizon-parameterized (unlike
  `controlled_daily_v4.features` which hardcodes `HORIZON_DAYS=3` as a
  module constant); this is *why* +1/+2 are technically buildable by a
  separate executor even though v4's own frozen pipeline only ever ran +3.
- `predictive_modeling.bundle_export`/`bundle_packaging` -- production
  code, never a test helper.
- `predictive_modeling.operational_run.build_feature_frame` -- the SAME
  generic lag/rolling builder that the unmodified `predict_operational_bundle`
  calls internally at inference time. This module therefore does NOT
  reproduce the real campaign's asymmetric `pergamino_features.v1` contract
  (which lags only `soil_moisture`, keeping RH2M/ALLSKY_SFC_SW_DWN at
  current-value only): `load_operational_bundle`/`predict_operational_bundle`
  apply lags/rolling windows uniformly across every declared
  `feature_columns` entry, and building an asymmetric contract would need
  modifying that already-verified, unmodified code -- not done. This demo's
  feature contract (lags/rolling on all 3 raw variables) is therefore its
  OWN declared contract, deliberately different from and not claiming
  equivalence to `pergamino_features.v1`.

**Exclusion of 2024-2025 -- precise description.** `load_era5_hourly_raw`/
`load_nasa_power_daily_raw` read the full raw CSV unconditionally (2024-2025
rows DO enter a `pandas.DataFrame` transiently, in memory, inside those two
calls -- this module does not control that, and never claimed otherwise
after this correction). What IS guaranteed: `restrict_era5_hourly_to_window`/
`restrict_nasa_power_daily_to_window` drop every 2024-2025 row **before**
`aggregate_era5_daily`, `build_daily_joined_series`, the P20 threshold, any
feature, or any target is computed -- no 2024-2025 *value* ever contributes
to any of those. `test_pergamino_ensemble_demo_runner_ingestion.py` proves
this directly: tampering 2024-2025 rows with arbitrary/extreme values, with
2015-2023 held fixed, produces a byte-identical permitted frame, threshold,
and training/calibration feature matrices.

**Family hyperparameters are declared here, fixed upfront, never tuned
against any partition of this run.** `logistic_regression` reuses the real
campaign's own frozen hyperparameters, as recorded in the git-tracked
`docs/research/controlled-daily-v4-external-pergamino-manifest.yaml`
(`frozen_hyperparameters.params`) -- this is the *hyperparameter choice*,
not the *fitted artifact*: this module always refits, on a training window
disjoint from and narrower than the real campaign's own Stage A range
(2015-2021 here vs. 2015-2022 there), so the resulting model is never
presented as the same artifact. `random_forest` and
`hist_gradient_boosting_classifier` never had a frozen artifact in the real
campaign (only Stage A OOF comparison numbers, which this module does not
read: `evidence/A/metrics.json` is root-owned and access-controlled, and
this module does not escalate privileges to read it) -- their
hyperparameters below are a fixed point within the ranges the real
protocol's own manifest already declares for their grids, chosen without
inspecting any evaluation result, real or synthetic, and never revisited
after seeing any accuracy/calibration number from this run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, FrozenEstimator

from experiment_runner.controlled_daily_v4.config import PRIMARY_DEPTH_COLUMN
from experiment_runner.controlled_daily_v4.ingestion import (
    aggregate_era5_daily,
    build_daily_joined_series,
    load_era5_hourly_raw,
    load_nasa_power_daily_raw,
    replace_missing_sentinel,
    restrict_era5_hourly_to_window,
    restrict_nasa_power_daily_to_window,
)
from experiment_runner.controlled_daily_v4.models import fit_estimator
from experiment_runner.controlled_daily_v4.provenance import (
    compute_sha256,
    validate_pergamino_provenance,
)
from experiment_runner.ensemble_demo_training import (
    EmptyTrainingPartitionError,
    EnsembleDemoPlan,
    HorizonDemoTrainingResult,
    run_ensemble_demo_training,
)
from predictive_modeling.labeling import fit_stress_threshold
from predictive_modeling.operational_contract import (
    OPERATIONAL_CONTRACT_VERSION,
    VariableMetadata,
)
from predictive_modeling.operational_preparation import (
    TARGET_LABEL_COLUMN as TARGET_LABEL_COLUMN,
)
from predictive_modeling.operational_preparation import (
    DateRange,
    TemporalCutPlan,
    validate_utc_calendar,
)
from predictive_modeling.operational_run import build_feature_frame as build_feature_frame
from predictive_modeling.operational_run_artifacts import capture_code_identity, capture_environment

# HorizonContract/ArtifactIdentity validate contract_version against this
# exact constant -- the v2 bundle format has no free-form contract_version,
# so this demo executor reuses it as-is rather than inventing a new one.
CONTRACT_VERSION = OPERATIONAL_CONTRACT_VERSION
EVENT_VARIABLE = "soil_moisture"
EVENT_UNIT = "m3/m3"
EVENT_PERCENTILE = 20.0
RAW_TO_CANONICAL = {"RH2M": "relative_humidity", "ALLSKY_SFC_SW_DWN": "solar_radiation"}
# Renamed to the canonical variable names `producer_emission.py` already
# uses for every sensor (`data_ingestion.history.VARIABLE_UNITS`, a fixed
# global registry `predict_operational_bundle`'s caller passes in and this
# module does not control) -- never the raw Pergamino/NASA POWER column
# names, which that registry does not know.
CURRENT_ONLY_COLUMNS: tuple[str, ...] = ("relative_humidity", "solar_radiation")
# All 3 raw columns get lag/rolling treatment (see module docstring): the
# unmodified predict_operational_bundle applies build_feature_frame's
# lags/windows uniformly across every declared feature_columns entry.
FEATURE_COLUMNS: tuple[str, ...] = (EVENT_VARIABLE, *CURRENT_ONLY_COLUMNS)
LAGS: tuple[int, ...] = (1, 2, 3)
ROLLING_WINDOWS: tuple[int, ...] = (3, 7)
DECISION_THRESHOLD = 0.5

# Ingestion-level exclusion boundary: nothing after this date is ever read
# from either raw CSV. 2024-2025 (the closed holdout) never enters pandas.
INGESTION_START = "2015-01-01"
INGESTION_END = "2023-12-31"

DEMO_TRAIN = DateRange("2015-01-01", "2021-12-31")
DEMO_CALIBRATION = DateRange("2022-01-01", "2022-12-31")
DEMO_EVALUATION = DateRange("2023-01-01", "2023-12-31")
DEMO_ALLOWED_DATA = DateRange(INGESTION_START, INGESTION_END)
# First as_of_date admissible for inference: predict_operational_bundle
# rejects only when max(trained_through, calibrated_through) > as_of_date
# (strict), so calibration's own last day is itself already admissible --
# never the day after it.
FIRST_ADMISSIBLE_DATE = DEMO_CALIBRATION.end.isoformat()

VARIABLES = [
    {"name": "soil_moisture", "unit": "m3/m3"},
    {"name": "relative_humidity", "unit": "%"},
    {"name": "solar_radiation", "unit": "MJ/m2/day"},
]

# Fixed, declared upfront, never tuned against any partition of this run.
# logistic_regression: same hyperparameters as the real campaign's frozen
# winner (docs/research/controlled-daily-v4-external-pergamino-manifest.yaml,
# frozen_hyperparameters.params) -- the choice, not the fitted artifact.
# random_forest / hist_gradient_boosting_classifier: one fixed point inside
# the grids the same manifest declares for Stage A, chosen without reading
# evidence/A/metrics.json (root-owned, not read by this module).
FAMILY_PARAMS: dict[str, dict[str, Any]] = {
    "logistic_regression": {
        "C": 1.0,
        "solver": "lbfgs",
        "max_iter": 2000,
        "weighting": "sample_weight_balanced",
    },
    "random_forest": {
        "n_estimators": 100,
        "max_depth": 8,
        "min_samples_leaf": 5,
        "weighting": "sample_weight_balanced",
        "random_state": 42,
        "n_jobs": 1,
    },
    "hist_gradient_boosting_classifier": {
        "learning_rate": 0.1,
        "max_iter": 100,
        "max_leaf_nodes": 15,
        "l2_regularization": 0.0,
        "weighting": "sample_weight_balanced",
        "random_state": 42,
    },
}


class DemoRunnerError(ValueError):
    """A precondition of this demonstration executor was violated."""


_REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_MANIFEST_FILENAME = "run_manifest.json"


def _write_run_manifest(output_dir: Path, manifest: dict[str, Any]) -> None:
    (output_dir / RUN_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )


def _new_run_manifest(
    *, sensor_id: str, horizons: tuple[int, ...], dataset_sha256: str, input_hashes: dict[str, str]
) -> dict[str, Any]:
    """Execution manifest written alongside the bundles: real code SHA and
    dirty state (`capture_code_identity` -- never invents an identity it
    cannot determine), the effective family configuration, input/permitted-
    frame hashes, environment, partitions, and (filled in incrementally as
    each horizon finishes) row counts used/excluded and output hashes.
    `status` distinguishes `iniciado`/`completado`/`fallido` so a partial
    output is never mistaken for a complete one."""
    return {
        "status": "iniciado",
        "sensor_id": sensor_id,
        "horizons_requested": list(horizons),
        "code_identity": capture_code_identity(_REPO_ROOT),
        "environment": capture_environment(),
        "input_hashes": dict(input_hashes),
        "permitted_frame_sha256": dataset_sha256,
        "effective_config": {
            "family_params": FAMILY_PARAMS,
            "decision_threshold": DECISION_THRESHOLD,
            "event_variable": EVENT_VARIABLE,
            "event_percentile": EVENT_PERCENTILE,
            "feature_columns": list(FEATURE_COLUMNS),
            "lags": list(LAGS),
            "rolling_windows": list(ROLLING_WINDOWS),
            "contract_version": CONTRACT_VERSION,
        },
        "partitions": {
            "train": DEMO_TRAIN.to_dict(),
            "calibration": DEMO_CALIBRATION.to_dict(),
            "evaluation": DEMO_EVALUATION.to_dict(),
            "allowed_data": DEMO_ALLOWED_DATA.to_dict(),
            "first_admissible_inference_date": FIRST_ADMISSIBLE_DATE,
        },
        "horizons": {},
    }


REQUIRED_HOURS_PER_DAY = 24


def _invalidate_incomplete_soil_moisture_days(era5_daily: pd.DataFrame) -> pd.DataFrame:
    """Never accept a silently-incomplete daily average.

    `aggregate_era5_daily` already computes, per day, `n_obs` (row count),
    `n_unique_hours` (distinct hours 0-23) and `n_finite_<column>` (finite
    readings) -- this function is the only place they are read before being
    discarded by the later column selection in `build_daily_frame`. A day
    passes only if all three equal `REQUIRED_HOURS_PER_DAY` for the primary
    depth column: 24 rows, 24 distinct hours (catches a duplicated hour
    silently masking a missing one), and 24 finite values (catches a
    non-finite reading that `groupby(...).mean()` would otherwise skip
    silently via `skipna=True`). A day that fails any of the three gets its
    `soil_moisture_0_to_7cm` set to `NaN` -- never imputed, never dropped
    here (dropping the row would also discard `relative_humidity`/
    `solar_radiation` for a day that may be fine for those). `NaN` here
    propagates downstream exactly like a missing calendar day already does:
    `add_calendar_target` marks the target unobserved when the day used as
    someone's target date has no finite value, and
    `partition_labeled_horizon`/the caller's own `dropna` purge a row whose
    OWN day is incomplete as a feature -- so an incomplete day never
    produces a false "observed" label or a false feature value in either
    direction."""
    finite_column = f"n_finite_{PRIMARY_DEPTH_COLUMN}"
    incomplete = (
        (era5_daily["n_obs"] != REQUIRED_HOURS_PER_DAY)
        | (era5_daily["n_unique_hours"] != REQUIRED_HOURS_PER_DAY)
        | (era5_daily[finite_column] != REQUIRED_HOURS_PER_DAY)
    )
    result = era5_daily.copy()
    result.loc[incomplete, PRIMARY_DEPTH_COLUMN] = np.nan
    return result


def build_daily_frame(era5_csv: Path, nasa_power_csv: Path) -> tuple[pd.DataFrame, str]:
    """Load and join the two raw Pergamino CSVs. Returns `(frame,
    dataset_sha256)` with columns `timestamp, soil_moisture,
    relative_humidity, solar_radiation` (renamed from the raw `RH2M`/
    `ALLSKY_SFC_SW_DWN` -- see `RAW_TO_CANONICAL`).

    Both raw files are read in full (2024-2025 rows do enter a DataFrame
    transiently inside `load_era5_hourly_raw`/`load_nasa_power_daily_raw`),
    then immediately restricted to `[INGESTION_START, INGESTION_END]` --
    before `aggregate_era5_daily`, `build_daily_joined_series`, or any
    later computation. See the module docstring for the precise claim this
    supports and `test_pergamino_ensemble_demo_runner_ingestion.py` for the
    direct, tamper-based proof. Incomplete-coverage days are invalidated
    (`_invalidate_incomplete_soil_moisture_days`) before the final column
    selection discards the coverage counters."""
    start = pd.Timestamp(INGESTION_START).date()
    end = pd.Timestamp(INGESTION_END).date()

    _, era5_raw = load_era5_hourly_raw(era5_csv)
    era5_raw = restrict_era5_hourly_to_window(era5_raw, start, end)
    era5_daily = aggregate_era5_daily(era5_raw)
    era5_daily = _invalidate_incomplete_soil_moisture_days(era5_daily)

    _, nasa_raw = load_nasa_power_daily_raw(nasa_power_csv)
    nasa_raw = restrict_nasa_power_daily_to_window(nasa_raw, start, end)
    nasa_raw = replace_missing_sentinel(nasa_raw)

    joined = build_daily_joined_series(era5_daily, nasa_raw)
    frame = joined.reset_index().rename(
        columns={PRIMARY_DEPTH_COLUMN: EVENT_VARIABLE, **RAW_TO_CANONICAL}
    )
    frame = frame[["date", EVENT_VARIABLE, *CURRENT_ONLY_COLUMNS]].rename(
        columns={"date": "timestamp"}
    )
    frame = validate_utc_calendar(frame)
    dataset_sha256 = hashlib.sha256(frame.to_csv(index=False).encode("utf-8")).hexdigest()
    return frame, dataset_sha256


def resolve_training_threshold(daily_frame: pd.DataFrame) -> float:
    """P20 physical threshold, computed ONLY on rows inside `DEMO_TRAIN` --
    never on calibration/evaluation rows, never on the full ingestion
    window."""
    train_rows = daily_frame.loc[DEMO_TRAIN.contains(daily_frame["timestamp"])]
    if train_rows.empty:
        raise DemoRunnerError("La ventana de entrenamiento no contiene filas.")
    return fit_stress_threshold(train_rows, EVENT_VARIABLE, EVENT_PERCENTILE)


def build_cut_plan() -> TemporalCutPlan:
    return TemporalCutPlan(
        allowed_data=DEMO_ALLOWED_DATA,
        train=DEMO_TRAIN,
        calibration=DEMO_CALIBRATION,
        evaluation=DEMO_EVALUATION,
        inference_as_of=INGESTION_END,
    )


PERGAMINO_DEMO_PLAN = EnsembleDemoPlan(
    horizons=(1, 2, 3),
    contract_version=CONTRACT_VERSION,
    event_variable=EVENT_VARIABLE,
    event_unit=EVENT_UNIT,
    event_comparison="lt",
    feature_columns=FEATURE_COLUMNS,
    lags=LAGS,
    rolling_windows=ROLLING_WINDOWS,
    decision_threshold=DECISION_THRESHOLD,
    variables=tuple(VariableMetadata(item["name"], item["unit"]) for item in VARIABLES),
    temporal_cuts=build_cut_plan(),
    family_names=tuple(FAMILY_PARAMS),
    model_identity_template="{family}_pergamino_demo_h{horizon}",
    calibrator_identity_template="{family}_pergamino_demo_calibrator_h{horizon}",
)


def fit_and_calibrate(
    family: str, X_train: np.ndarray, y_train: np.ndarray, X_calib: np.ndarray, y_calib: np.ndarray
) -> tuple[Any, Any]:
    """Reuses `controlled_daily_v4.models.fit_estimator` (frozen, unmodified)
    and the same `CalibratedClassifierCV(FrozenEstimator(...), "sigmoid")`
    pattern already used by `operational_run.fit_seed` and by Hito 1's
    `tests/test_ensemble_bundle_real_families.py` -- never a new calibration
    method, never a different family builder."""
    params = FAMILY_PARAMS[family]
    model = fit_estimator(family, params, X_train, y_train)
    calibrator = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
    calibrator.fit(X_calib, y_calib)
    return model, calibrator


def run_demo_from_frame(
    daily_frame: pd.DataFrame,
    dataset_sha256: str,
    output_dir: Path,
    *,
    sensor_id: str,
    horizons: tuple[int, ...] = (1, 2, 3),
    input_hashes: dict[str, str] | None = None,
) -> dict[int, dict[str, Path]]:
    """Core pipeline, taking an already-built daily frame (columns
    `timestamp, soil_moisture, relative_humidity, solar_radiation`) and its dataset
    hash directly -- used by `run_demo` for the real Pergamino CSVs, and
    directly by synthetic tests (never through `tests/helpers/
    synthetic_bundles.py`, which this module does not import). Computes the
    training-only threshold, builds multi-horizon targets/partitions, fits +
    calibrates the 3 families per horizon, and exports real bundles +
    ensemble manifests + a `run_manifest.json` under `output_dir` -- a
    fresh, empty tree, never `evidence/A|B|C`, `ledger/`, or any path under
    `openspec/scientific-closure/` or `replay_packages/`.

    The run manifest is written before anything else (`status=iniciado`),
    updated after each horizon completes, and finalized as `completado` or
    `fallido` (with the error re-raised, never swallowed) -- a process
    killed mid-run leaves a manifest that says `iniciado`, never one that
    silently looks the same as a complete run."""
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise DemoRunnerError(f"--output-dir {output_dir} no está vacío.")
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = _new_run_manifest(
        sensor_id=sensor_id,
        horizons=horizons,
        dataset_sha256=dataset_sha256,
        input_hashes=input_hashes or {},
    )
    _write_run_manifest(output_dir, manifest)

    def record_threshold(threshold: float) -> None:
        manifest["physical_threshold"] = threshold

    def record_horizon(result: HorizonDemoTrainingResult) -> None:
        manifest["horizons"][str(result.horizon)] = result.manifest_report()
        _write_run_manifest(output_dir, manifest)

    try:
        try:
            result = run_ensemble_demo_training(
                daily_frame,
                dataset_sha256=dataset_sha256,
                output_dir=output_dir,
                sensor_id=sensor_id,
                horizons=horizons,
                plan=PERGAMINO_DEMO_PLAN,
                resolve_threshold=resolve_training_threshold,
                fit_component=fit_and_calibrate,
                on_threshold_resolved=record_threshold,
                on_horizon_completed=record_horizon,
            )
        except EmptyTrainingPartitionError as error:
            raise DemoRunnerError(str(error)) from error

        manifest["status"] = "completado"
        _write_run_manifest(output_dir, manifest)
    except Exception as error:
        manifest["status"] = "fallido"
        manifest["error"] = f"{type(error).__name__}: {error}"
        _write_run_manifest(output_dir, manifest)
        raise

    return result.written


def run_demo(
    era5_csv: Path,
    nasa_power_csv: Path,
    output_dir: Path,
    *,
    sensor_id: str,
    horizons: tuple[int, ...] = (1, 2, 3),
    provenance_mode: str = "scientific",
) -> dict[int, dict[str, Path]]:
    """Validate provenance (never trains), ingest the real Pergamino CSVs
    (see `build_daily_frame` for the precise 2024-2025 exclusion claim),
    then delegate to `run_demo_from_frame`."""
    report = validate_pergamino_provenance(era5_csv, nasa_power_csv, mode=provenance_mode)
    if not report.ok:
        raise DemoRunnerError(f"Validación de provenance falló: {report.issues}")

    input_hashes = {
        "era5_csv": compute_sha256(era5_csv),
        "nasa_power_csv": compute_sha256(nasa_power_csv),
    }
    daily_frame, dataset_sha256 = build_daily_frame(era5_csv, nasa_power_csv)
    return run_demo_from_frame(
        daily_frame,
        dataset_sha256,
        output_dir,
        sensor_id=sensor_id,
        horizons=horizons,
        input_hashes=input_hashes,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pergamino-ensemble-demo",
        description=(
            "Ejecutor de demostración, separado de controlled_daily_v4/ (frozen): "
            "ajusta y calibra las 3 familias para +1/+2/+3 sobre 2015-2023, nunca "
            "reejecuta A/B/C ni toca 2024-2025."
        ),
    )
    parser.add_argument("--era5-csv", type=Path, required=True)
    parser.add_argument("--nasa-power-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sensor-id", default="pergamino-ensemble-demo")
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=[1, 2, 3],
        choices=[1, 2, 3],
    )
    parser.add_argument(
        "--input-mode",
        default="scientific",
        choices=["scientific", "synthetic"],
        help=(
            "'scientific' (default): exige identidad real de los CSV contra el "
            "manifiesto versionado. 'synthetic': exclusivo de pruebas."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        written = run_demo(
            args.era5_csv,
            args.nasa_power_csv,
            args.output_dir,
            sensor_id=args.sensor_id,
            horizons=tuple(sorted(set(args.horizons))),
            provenance_mode=args.input_mode,
        )
    except DemoRunnerError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for horizon, families in sorted(written.items()):
        print(f"horizonte +{horizon}: {sorted(families)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
