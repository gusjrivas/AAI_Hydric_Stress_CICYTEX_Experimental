"""Separate, non-frozen demonstration executor that builds a real,
3-family, 3-horizon `ensemble_agreement_v1` bundle for Melchor Romero, the
site's own second real historical-demonstration site (HU6
`architecture-integration`, generalizing the pattern already established by
`pergamino_ensemble_demo_runner.py` for Pergamino).

Loads the REAL, already-committed dataset `data/melchor_romero_2024_consolidado.parquet`
(`data_ingestion.storage.load_dataset_snapshot`) -- no external CSV, no raw
data outside the repository, unlike Pergamino. This is a genuine, real,
field-adjacent (ESA CCI soil moisture + NASA POWER climate) dataset already
used elsewhere in this repository as the sole evidence base of
`controlled_daily_v3` (`docs/adr/0011-...`, `openspec/specs/architecture-integration/spec.md`).

This module never re-executes, re-selects or re-trains anything from
`controlled_daily_v3`, never touches `replay_packages/base-seed4-1157696b7b-v2`
(the frozen historical-replay package for this same dataset), and never
imports `historical_replay.*`. It fits its own, separately-declared model
family configuration on a disjoint temporal window of the SAME real
dataset, exactly as `pergamino_ensemble_demo_runner.py` does for Pergamino
relative to `controlled_daily_v4_external_pergamino` -- a second,
independent, real historical demonstration site, not a re-run of frozen
scientific evidence.

**Train/calibration/evaluation split.** The 2024 calendar year is the only
real year available for this dataset (366 rows). The split reuses the
cutoff date (`2024-10-19`) already established and verified for this exact
dataset in `openspec/specs/architecture-integration/spec.md` ("Verificado
sobre el dataset real (Melchor Romero 2024, ... corte 2024-10-19)"), rather
than inventing a new one:

- Train: 2024-01-01 to 2024-09-04.
- Calibration: 2024-09-05 to 2024-10-19 (same day the architecture-integration
  pipeline already uses as its train/test cutoff for this dataset).
- Demo/evaluation: 2024-10-20 to 2024-12-31.

**Missing values.** Unlike Pergamino's ingestion (which invalidates any
incomplete day and never imputes), `soil_moisture` in the real, committed
Melchor Romero dataset has genuine missing days (ESA CCI coverage gaps,
disclosed in `data/melchor_romero_2024_consolidado_coverage.csv`). Without
causal imputation the calibration window is left with 0-1 usable rows after
lag/rolling propagation, which cannot support `CalibratedClassifierCV`.
This module therefore reuses `data_quality.imputation.interpolate_missing_causal`
(existing, already-verified, already-approved general-purpose capability,
strictly forward-fill, never `bfill`/linear interpolation) applied
independently per partition, each warm-started only from the immediately
preceding partition's own last (already-imputed) row -- train from nothing,
calibration from train's tail, demo/evaluation from calibration's tail.
Evaluation rows are never used to seed or complete train/calibration, and
train/calibration are never completed using evaluation rows: no partition
ever borrows a value from a later partition, and no partition is imputed
using its own future.

**Labels are built from this prepared (imputed) frame, not retrospectively
recomputed (F01).** `interpolate_missing_causal` records, per variable, a
`<variable>_imputado` boolean column identifying exactly which rows were
completed by forward-fill (never inferred later by comparing values across
days -- it is derived directly from which cells were `NaN` before
imputation). This module trains/labels on the already-imputed frame, same
as before F01: the fix is that `build_daily_frame_from_repo_dataset` no
longer discards those `<variable>_imputado` columns before returning, so
`scripts/prepare_melchor_romero_historical_demo.py` can persist them into
the readings file `data_ingestion.history.query_readings` serves, and the
UI can identify an imputed value explicitly instead of presenting it as an
unqualified real observation. This never changes any label, any trained
model, or any already-served prediction -- it only makes an
already-computed fact (which values were imputed) visible downstream.

**Feature contract (this module's own, declared here, never claiming
equivalence to any frozen protocol contract).** Lag (1, 2, 3) and rolling
mean (3, 7) windows applied uniformly to the three raw variables
(`soil_moisture`, `relative_humidity`, `solar_radiation`) -- identical
contract shape to `pergamino_ensemble_demo_runner.py`'s own declared
contract (chosen for consistency between the two demonstration sites, not
because either equals `pergamino_features.v1` or the 15-variable
`controlled_daily_v3` contract).

**Family hyperparameters** are declared fixed, upfront, in this file, and
never revised after observing any evaluation result of this run, real or
synthetic -- same governance discipline as
`pergamino_ensemble_demo_runner.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, FrozenEstimator

from data_ingestion.storage import DEFAULT_DATA_DIR, load_dataset_snapshot
from data_quality.imputation import interpolate_missing_causal
from experiment_runner.controlled_daily_v4.models import fit_estimator
from experiment_runner.ensemble_demo_training import (
    EmptyTrainingPartitionError,
    EnsembleDemoPlan,
    EnsembleFamilySpec,
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

CONTRACT_VERSION = OPERATIONAL_CONTRACT_VERSION
DATASET_NAME = "melchor_romero_2024_consolidado"
EVENT_VARIABLE = "soil_moisture"
EVENT_UNIT = "m3/m3"
EVENT_PERCENTILE = 20.0
CURRENT_ONLY_COLUMNS: tuple[str, ...] = ("relative_humidity", "solar_radiation")
FEATURE_COLUMNS: tuple[str, ...] = (EVENT_VARIABLE, *CURRENT_ONLY_COLUMNS)
LAGS: tuple[int, ...] = (1, 2, 3)
ROLLING_WINDOWS: tuple[int, ...] = (3, 7)
DECISION_THRESHOLD = 0.5

# Reuses the split date already established and verified for this exact
# dataset (openspec/specs/architecture-integration/spec.md, "corte
# 2024-10-19"), never invented for this module.
DEMO_TRAIN = DateRange("2024-01-01", "2024-09-04")
DEMO_CALIBRATION = DateRange("2024-09-05", "2024-10-19")
DEMO_EVALUATION = DateRange("2024-10-20", "2024-12-31")
DEMO_ALLOWED_DATA = DateRange("2024-01-01", "2024-12-31")
# predict_operational_bundle rejects only when max(trained_through,
# calibrated_through) > as_of_date (strict) -- calibration's own last day is
# itself already admissible, never the day after it.
FIRST_ADMISSIBLE_DATE = DEMO_CALIBRATION.end.isoformat()

VARIABLES = [
    {"name": "soil_moisture", "unit": "m3/m3"},
    {"name": "relative_humidity", "unit": "%"},
    {"name": "solar_radiation", "unit": "MJ/m2/day"},
]

# Fixed, declared upfront, never tuned against any partition of this run.
# One fixed point inside conventional ranges for each family -- chosen
# without reading any evaluation result of this run, real or synthetic.
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
    *, sensor_id: str, horizons: tuple[int, ...], dataset_sha256: str, dataset_name: str
) -> dict[str, Any]:
    return {
        "status": "iniciado",
        "sensor_id": sensor_id,
        "dataset_name": dataset_name,
        "horizons_requested": list(horizons),
        "code_identity": capture_code_identity(_REPO_ROOT),
        "environment": capture_environment(),
        "permitted_frame_sha256": dataset_sha256,
        "effective_config": {
            "family_params": MELCHOR_ROMERO_DEMO_PLAN.family_params_dict(),
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
        "imputation": {
            "method": "interpolate_missing_causal (forward-fill only)",
            "applied_per_partition_with_sequential_warm_start": True,
        },
        "horizons": {},
    }


def _causal_impute_by_partition(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Apply `interpolate_missing_causal` independently to train,
    calibration and evaluation, each warm-started only from the
    immediately preceding partition's own last (already-imputed) row.
    Never lets a partition borrow a value from a later partition; never
    imputes a partition using its own future rows."""
    train_rows = frame.loc[DEMO_TRAIN.contains(frame["timestamp"])].copy()
    calib_rows = frame.loc[DEMO_CALIBRATION.contains(frame["timestamp"])].copy()
    eval_rows = frame.loc[DEMO_EVALUATION.contains(frame["timestamp"])].copy()

    train_imputed = interpolate_missing_causal(train_rows, columns)
    calib_warm = train_imputed.iloc[-1] if not train_imputed.empty else None
    calib_imputed = interpolate_missing_causal(calib_rows, columns, warm_start=calib_warm)
    eval_warm = calib_imputed.iloc[-1] if not calib_imputed.empty else calib_warm
    eval_imputed = interpolate_missing_causal(eval_rows, columns, warm_start=eval_warm)

    return pd.concat([train_imputed, calib_imputed, eval_imputed], ignore_index=True)


def build_daily_frame_from_repo_dataset(
    data_dir: Path = DEFAULT_DATA_DIR,
) -> tuple[pd.DataFrame, str]:
    """Load the real, already-committed `melchor_romero_2024_consolidado`
    dataset and restrict/impute it exactly as this demo's partitions
    require. Returns `(frame, dataset_sha256)` with columns `timestamp,
    soil_moisture, relative_humidity, solar_radiation` plus, for each of
    those three variables, a `<variable>_imputado` boolean column (F01:
    which cells were completed by causal forward-fill, computed directly
    from `interpolate_missing_causal`, never inferred afterwards) --
    deliberately NOT stripped before returning, so callers that persist
    this frame as readings (`scripts/prepare_melchor_romero_historical_demo.py`)
    can preserve per-value imputation provenance alongside the dataset-level
    `origen` they set separately. `dataset_sha256` identifies the raw
    snapshot read (before imputation), matching the convention
    `pergamino_ensemble_demo_runner.py` uses for its own input hash."""
    snapshot = load_dataset_snapshot(DATASET_NAME, data_dir=data_dir)
    df, dataset_sha256 = snapshot.dataframe, snapshot.dataset_sha256
    frame = df[["timestamp", *FEATURE_COLUMNS]].copy()
    frame = frame.loc[DEMO_ALLOWED_DATA.contains(frame["timestamp"])].reset_index(drop=True)
    frame = _causal_impute_by_partition(frame, list(FEATURE_COLUMNS))
    frame = validate_utc_calendar(frame)
    return frame, dataset_sha256


def resolve_training_threshold(daily_frame: pd.DataFrame) -> float:
    """P20 physical threshold, computed ONLY on rows inside `DEMO_TRAIN` --
    never on calibration/evaluation rows, never on the full window."""
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
        inference_as_of=DEMO_EVALUATION.end.isoformat(),
    )


MELCHOR_ROMERO_DEMO_PLAN = EnsembleDemoPlan(
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
    family_specs=tuple(
        EnsembleFamilySpec.from_mapping(family, parameters)
        for family, parameters in FAMILY_PARAMS.items()
    ),
    model_identity_template="{family}_melchor_romero_demo_h{horizon}",
    calibrator_identity_template="{family}_melchor_romero_demo_calibrator_h{horizon}",
)


def fit_and_calibrate(
    family: str, X_train: np.ndarray, y_train: np.ndarray, X_calib: np.ndarray, y_calib: np.ndarray
) -> tuple[Any, Any]:
    """Reuses `controlled_daily_v4.models.fit_estimator` (frozen, unmodified,
    generic across sites/domains) and the same
    `CalibratedClassifierCV(FrozenEstimator(...), "sigmoid")` pattern
    already used for Pergamino -- never a new calibration method, never a
    different family builder."""
    params = MELCHOR_ROMERO_DEMO_PLAN.params_for(family)
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
) -> dict[int, dict[str, Path]]:
    """Core pipeline: given an already-built, already-imputed daily frame
    (columns `timestamp, soil_moisture, relative_humidity,
    solar_radiation`) and its raw dataset hash, computes the training-only
    threshold, builds multi-horizon targets/partitions, fits + calibrates
    the 3 families per horizon, and exports real bundles + ensemble
    manifests + a `run_manifest.json` under `output_dir` -- a fresh, empty
    tree, never `replay_packages/` or any path under
    `openspec/scientific-closure/`.

    The run manifest is written before anything else (`status=iniciado`),
    updated after each horizon completes, and finalized as `completado` or
    `fallido` (error re-raised, never swallowed)."""
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise DemoRunnerError(f"--output-dir {output_dir} no está vacío.")
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = _new_run_manifest(
        sensor_id=sensor_id,
        horizons=horizons,
        dataset_sha256=dataset_sha256,
        dataset_name=DATASET_NAME,
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
                plan=MELCHOR_ROMERO_DEMO_PLAN,
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
    output_dir: Path,
    *,
    sensor_id: str = "melchor-romero-demo",
    horizons: tuple[int, ...] = (1, 2, 3),
    data_dir: Path = DEFAULT_DATA_DIR,
) -> dict[int, dict[str, Path]]:
    """Load the real committed Melchor Romero dataset and delegate to
    `run_demo_from_frame`. No external CSV, no provenance validation
    against an external manifest is needed: `data_ingestion.storage`
    already is this repository's single access contract for datasets
    (ADR-0002), and the dataset's own provenance is recorded in
    `data/dictionaries/*melchor_romero_2024*.json`."""
    daily_frame, dataset_sha256 = build_daily_frame_from_repo_dataset(data_dir=data_dir)
    return run_demo_from_frame(
        daily_frame,
        dataset_sha256,
        output_dir,
        sensor_id=sensor_id,
        horizons=horizons,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="melchor-romero-historical-demo",
        description=(
            "Ejecutor de demostración, separado del protocolo congelado "
            "controlled_daily_v3: ajusta y calibra las 3 familias para "
            "+1/+2/+3 sobre el dataset real ya versionado de Melchor Romero "
            "2024, nunca reejecuta ni reinterpreta la evidencia congelada de "
            "controlled_daily_v3 ni el paquete de historical-replay."
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sensor-id", default="melchor-romero-demo")
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=[1, 2, 3],
        choices=[1, 2, 3],
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        written = run_demo(
            args.output_dir,
            sensor_id=args.sensor_id,
            horizons=tuple(sorted(set(args.horizons))),
            data_dir=args.data_dir,
        )
    except DemoRunnerError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for horizon, families in sorted(written.items()):
        print(f"horizonte +{horizon}: {sorted(families)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
