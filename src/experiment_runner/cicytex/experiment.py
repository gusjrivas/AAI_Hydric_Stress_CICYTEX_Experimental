from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, FrozenEstimator
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)

from experiment_runner.cicytex.ingestion import (
    CicytexDatasetProvenance,
    assert_cicytex_provenance_slot,
    quality_summary,
    write_cicytex_dataset_provenance,
)
from experiment_runner.cicytex.training_protocol import (
    FAMILY_PARAMS,
    FEATURES,
    prepare_horizon,
    select_partition,
)
from experiment_runner.cicytex.training_protocol import (
    TemporalSplit as _TemporalSplit,
)
from experiment_runner.cicytex.training_protocol import (
    build_features as _build_features,
)
from experiment_runner.cicytex.training_protocol import (
    temporal_split as _temporal_split,
)
from experiment_runner.controlled_daily_v4.models import fit_estimator

# Backward-compatible private alias retained while callers migrate to the shared seam.
TemporalSplit = _TemporalSplit
build_features = _build_features
temporal_split = _temporal_split
_part = select_partition


def _safe_metrics(y: pd.Series, probability: np.ndarray) -> dict[str, Any]:
    prediction = (probability >= 0.5).astype(int)
    positives = int((y == 1).sum())
    predicted_positives = int((prediction == 1).sum())
    two_classes = y.nunique() == 2
    matrix = confusion_matrix(y, prediction, labels=[0, 1])
    return {
        "n": int(len(y)),
        "positive_rate": float(y.mean()),
        "mcc": float(matthews_corrcoef(y, prediction)) if two_classes else None,
        "precision": float(precision_score(y, prediction)) if predicted_positives else None,
        "recall": float(recall_score(y, prediction)) if positives else None,
        "f1": float(f1_score(y, prediction)) if positives and predicted_positives else None,
        "roc_auc": float(roc_auc_score(y, probability)) if two_classes else None,
        "pr_auc": float(average_precision_score(y, probability)) if positives else None,
        "brier": float(brier_score_loss(y, probability)),
        "confusion_matrix": matrix.tolist(),
    }


def _finite_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        k: float(v)
        for k, v in metrics.items()
        if isinstance(v, (int, float)) and v is not None and math.isfinite(float(v))
    }


def _git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def run_experiment(
    data: pd.DataFrame,
    output_dir: Path,
    dataset_sha256: str,
    zip_sha256: str,
    tracking_uri: str | None = None,
    *,
    dataset_provenance: CicytexDatasetProvenance | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    provenance_payload = None
    if dataset_provenance is not None:
        assert_cicytex_provenance_slot(
            output_dir,
            dataset_provenance,
            dataset_sha256=dataset_sha256,
            zip_sha256=zip_sha256,
            data=data,
        )
        provenance_payload = dataset_provenance.to_dict()
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("cicytex-external-validation")
    summary: dict[str, Any] = {"dataset": quality_summary(data), "horizons": {}}
    if provenance_payload is not None:
        summary["dataset_provenance"] = provenance_payload
        summary["normalized_dataset_sha256"] = dataset_provenance.snapshot.dataset_sha256
    environment = subprocess.check_output(
        [subprocess.sys.executable, "-m", "pip", "freeze"], text=True
    )
    (output_dir / "dependencies.txt").write_text(environment, encoding="utf-8")
    with mlflow.start_run(run_name="cicytex-parent") as parent:
        parent_params = {
            "dataset_sha256": dataset_sha256,
            "zip_sha256": zip_sha256,
            "git_commit": _git_commit(),
            "seed": 42,
            "proxy_percentile": 20,
            "features": ",".join(FEATURES),
        }
        if dataset_provenance is not None:
            parent_params["normalized_dataset_sha256"] = dataset_provenance.snapshot.dataset_sha256
        mlflow.log_params(parent_params)
        for horizon in (1, 2, 3):
            prepared = prepare_horizon(data, horizon)
            split = prepared.split
            threshold = prepared.threshold_train_p20
            parts = {
                name: getattr(prepared, name)
                for name in ("train", "calibration", "validation", "evaluation")
            }
            for part in parts.values():
                part["stress_proxy"] = (part["future_soil_moisture"] < threshold).astype(int)
            for name, part in parts.items():
                if part.empty or part["stress_proxy"].nunique() < 2:
                    raise ValueError(f"Horizonte +{horizon}: partición {name} sin ambas clases")
            candidates = {}
            for family, params in FAMILY_PARAMS.items():
                model = fit_estimator(
                    family, params, parts["train"][list(FEATURES)], parts["train"]["stress_proxy"]
                )
                calibrated = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
                calibrated.fit(
                    parts["calibration"][list(FEATURES)], parts["calibration"]["stress_proxy"]
                )
                probability = calibrated.predict_proba(parts["validation"][list(FEATURES)])[:, 1]
                candidates[family] = (
                    matthews_corrcoef(parts["validation"]["stress_proxy"], probability >= 0.5),
                    calibrated,
                )
            selected_family, (_, selected) = max(
                candidates.items(),
                key=lambda item: (item[1][0], -list(FAMILY_PARAMS).index(item[0])),
            )
            evaluation = parts["evaluation"]
            probability = selected.predict_proba(evaluation[list(FEATURES)])[:, 1]
            metrics = _safe_metrics(evaluation["stress_proxy"], probability)
            persistence = evaluation["soil_moisture"].to_numpy()
            observed = evaluation["future_soil_moisture"].to_numpy()
            metrics["persistence_mae"] = float(mean_absolute_error(observed, persistence))
            metrics["persistence_rmse"] = float(mean_squared_error(observed, persistence) ** 0.5)
            horizon_dir = output_dir / f"horizon_{horizon}d"
            horizon_dir.mkdir(exist_ok=True)
            predictions = evaluation[
                [
                    "sensor_id",
                    "timestamp",
                    "target_timestamp",
                    "soil_moisture",
                    "future_soil_moisture",
                    "stress_proxy",
                ]
            ].copy()
            predictions["probability"] = probability
            predictions["prediction"] = (probability >= 0.5).astype(int)
            predictions.to_csv(horizon_dir / "predictions.csv", index=False)
            joblib.dump(selected, horizon_dir / "model.joblib")
            matrix = np.asarray(metrics["confusion_matrix"])
            figure, axis = plt.subplots(figsize=(4, 3))
            image = axis.imshow(matrix, cmap="Blues")
            for row in range(2):
                for column in range(2):
                    axis.text(column, row, str(matrix[row, column]), ha="center", va="center")
            axis.set(
                xticks=[0, 1],
                yticks=[0, 1],
                xlabel="Predicción",
                ylabel="Observado",
                title=f"CICYTEX +{horizon} día(s)",
            )
            figure.colorbar(image, ax=axis)
            figure.tight_layout()
            figure.savefig(horizon_dir / "confusion_matrix.png", dpi=160)
            plt.close(figure)
            record = {
                "horizon_days": horizon,
                "threshold_train_p20": threshold,
                "selected_family": selected_family,
                "split": {k: str(v.date()) for k, v in split.__dict__.items()},
                "partition_rows": {k: len(v) for k, v in parts.items()},
                "metrics": metrics,
            }
            (horizon_dir / "result.json").write_text(
                json.dumps(record, indent=2, allow_nan=False), encoding="utf-8"
            )
            with mlflow.start_run(run_name=f"horizon-{horizon}d", nested=True) as child:
                mlflow.log_params(
                    {
                        "horizon_days": horizon,
                        "selected_family": selected_family,
                        "threshold_train_p20": threshold,
                        **{f"split_{k}": str(v.date()) for k, v in split.__dict__.items()},
                    }
                )
                mlflow.log_metrics(_finite_metrics(metrics))
                mlflow.log_artifacts(str(horizon_dir), artifact_path=f"horizon_{horizon}d")
                record["mlflow_run_id"] = child.info.run_id
            summary["horizons"][str(horizon)] = record
        summary["mlflow_parent_run_id"] = parent.info.run_id
        provenance_path = None
        if dataset_provenance is not None:
            provenance_path = write_cicytex_dataset_provenance(
                output_dir,
                dataset_provenance,
                dataset_sha256=dataset_sha256,
                zip_sha256=zip_sha256,
                data=data,
            )
        summary_path = output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
        mlflow.log_artifact(str(summary_path))
        mlflow.log_artifact(str(output_dir / "dependencies.txt"))
        if provenance_path is not None:
            mlflow.log_artifact(str(provenance_path))
    return summary
