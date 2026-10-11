"""Causal CICYTEX replay preparation.

Fits the three already-authorised classifier families once per horizon, freezes
them after validation ends, and archives emissions that can be replayed without
performing inference in the UI.  The event is a training-only P20 soil-moisture
proxy; it is not an observed physiological-stress label.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import joblib
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
    precision_score,
    recall_score,
    roc_auc_score,
)

from experiment_runner.cicytex.experiment import (
    FAMILY_PARAMS,
    FEATURES,
    _part,
    build_features,
    temporal_split,
)
from experiment_runner.controlled_daily_v4.models import fit_estimator

METHODS = (*FAMILY_PARAMS.keys(), "ensemble", "persistence")
DECISION_THRESHOLD = 0.5
SEED = 42


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metrics(rows: pd.DataFrame) -> dict[str, Any]:
    y = rows["observed_label"].astype(int).to_numpy()
    score = rows["score"].astype(float).to_numpy()
    predicted = rows["alert"].astype(int).to_numpy()
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    two_classes = len(np.unique(y)) == 2
    positives = int(y.sum())
    predicted_positives = int(predicted.sum())
    return {
        "n": int(len(rows)),
        "negative": int(len(rows) - positives),
        "positive": positives,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "mcc": float(matthews_corrcoef(y, predicted)) if two_classes else None,
        "precision": float(precision_score(y, predicted)) if predicted_positives else None,
        "recall": float(recall_score(y, predicted)) if positives else None,
        "f1": float(f1_score(y, predicted)) if positives and predicted_positives else None,
        "roc_auc": float(roc_auc_score(y, score)) if two_classes else None,
        "pr_auc": float(average_precision_score(y, score)) if positives else None,
        "brier": float(brier_score_loss(y, score)),
    }


def _episode_metrics(rows: pd.DataFrame) -> dict[str, Any]:
    """Evaluate starts of low-moisture episodes independently per probe."""
    onsets = 0
    anticipated = 0
    lead_days: list[int] = []
    false_alerts = 0
    for _sensor, group in rows.sort_values("target_timestamp").groupby("sensor_id"):
        daily = group.drop_duplicates("target_timestamp").copy()
        daily["previous"] = daily["observed_label"].shift(1)
        starts = daily.loc[(daily["observed_label"] == 1) & (daily["previous"] == 0)]
        onsets += len(starts)
        for _, onset in starts.iterrows():
            candidates = group.loc[
                (group["alert"] == 1)
                & (group["target_timestamp"] == onset["target_timestamp"])
                & (group["emission_date"] < onset["target_timestamp"])
            ]
            if not candidates.empty:
                anticipated += 1
                lead_days.append(
                    int((onset["target_timestamp"] - candidates["emission_date"].min()).days)
                )
        false_alerts += int(((daily["alert"] == 1) & (daily["observed_label"] == 0)).sum())
    return {
        "episode_onsets": int(onsets),
        "anticipated_onsets": int(anticipated),
        "missed_onsets": int(onsets - anticipated),
        "false_alert_days": int(false_alerts),
        "mean_lead_days": float(np.mean(lead_days)) if lead_days else None,
    }


def _finite(values: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in values.items()
        if isinstance(value, (int, float)) and value is not None and math.isfinite(float(value))
    }


def run_causal_ensemble(
    data: pd.DataFrame,
    output_dir: Path,
    *,
    dataset_sha256: str,
    zip_sha256: str,
    tracking_uri: str | None = None,
) -> dict[str, Any]:
    """Train once, archive every legitimate evaluation-period emission."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir = output_dir / "models"
    model_dir.mkdir(exist_ok=True)
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("cicytex-causal-ensemble-replay")
    git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    all_predictions: list[pd.DataFrame] = []
    report: dict[str, Any] = {
        "dataset_sha256": dataset_sha256,
        "zip_sha256": zip_sha256,
        "git_commit": git_commit,
        "seed": SEED,
        "proxy": "soil_moisture below training-only P20; not physiological stress",
        "ensemble_policy": "equal-weight arithmetic mean; threshold 0.5",
        "horizons": {},
    }
    observations = data[["sensor_id", "timestamp", "soil_moisture"]].copy()
    observations.to_csv(output_dir / "observations.csv", index=False)
    with mlflow.start_run(run_name="cicytex-causal-ensemble-parent") as parent:
        report["mlflow_parent_run_id"] = parent.info.run_id
        mlflow.log_params(
            {
                "dataset_sha256": dataset_sha256,
                "zip_sha256": zip_sha256,
                "git_commit": git_commit,
                "seed": SEED,
                "proxy_percentile": 20,
                "ensemble_weights": "1/3,1/3,1/3",
                "decision_threshold": DECISION_THRESHOLD,
            }
        )
        for horizon in (1, 2, 3):
            featured = build_features(data, horizon).dropna(
                subset=[*FEATURES, "future_soil_moisture"]
            )
            split = temporal_split(featured["target_timestamp"])
            train = _part(featured, split, "train")
            calibration = _part(featured, split, "calibration")
            validation = _part(featured, split, "validation")
            evaluation = _part(featured, split, "evaluation")
            threshold = float(train["future_soil_moisture"].quantile(0.20))
            for frame in (train, calibration, validation, evaluation):
                frame["observed_label"] = (frame["future_soil_moisture"] < threshold).astype(int)
                if frame.empty or frame["observed_label"].nunique() < 2:
                    raise ValueError(f"Horizonte +{horizon}: particion no evaluable")

            component_scores: dict[str, np.ndarray] = {}
            component_runs: dict[str, str] = {}
            for family, params in FAMILY_PARAMS.items():
                model = fit_estimator(
                    family, params, train[list(FEATURES)], train["observed_label"]
                )
                calibrator = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
                calibrator.fit(calibration[list(FEATURES)], calibration["observed_label"])
                score = calibrator.predict_proba(evaluation[list(FEATURES)])[:, 1]
                component_scores[family] = score
                artifact = model_dir / f"{family}__h{horizon}.joblib"
                joblib.dump(calibrator, artifact)
                with mlflow.start_run(run_name=f"{family}-h{horizon}", nested=True) as child:
                    component_runs[family] = child.info.run_id
                    mlflow.log_params(
                        {
                            "family": family,
                            "horizon_days": horizon,
                            "trained_through": split.train_end.date().isoformat(),
                            "calibrated_through": split.calibration_end.date().isoformat(),
                            "selected_through": split.validation_end.date().isoformat(),
                            "threshold_train_p20": threshold,
                            **params,
                        }
                    )
                    mlflow.log_artifact(str(artifact), artifact_path="model")

            base = evaluation[
                [
                    "sensor_id",
                    "timestamp",
                    "target_timestamp",
                    "soil_moisture",
                    "future_soil_moisture",
                    "observed_label",
                ]
            ].copy()
            base = base.rename(
                columns={
                    "timestamp": "emission_date",
                    "future_soil_moisture": "observed_soil_moisture",
                }
            )
            legitimate = base["emission_date"] > split.validation_end
            base = base.loc[legitimate].reset_index(drop=True)
            base["event_threshold"] = threshold
            for family, scores in component_scores.items():
                part = base.copy()
                part["method"] = family
                part["score"] = scores[legitimate.to_numpy()]
                part["alert"] = part["score"] >= DECISION_THRESHOLD
                all_predictions.append(part)
            ensemble_score = np.mean(
                np.column_stack(
                    [values[legitimate.to_numpy()] for values in component_scores.values()]
                ),
                axis=1,
            )
            ensemble = base.copy()
            ensemble["method"] = "ensemble"
            ensemble["score"] = ensemble_score
            ensemble["alert"] = ensemble_score >= DECISION_THRESHOLD
            ensemble["majority_alert"] = (
                np.column_stack(
                    [
                        values[legitimate.to_numpy()] >= DECISION_THRESHOLD
                        for values in component_scores.values()
                    ]
                ).sum(axis=1)
                >= 2
            )
            ensemble["vote_fraction"] = np.column_stack(
                [
                    values[legitimate.to_numpy()] >= DECISION_THRESHOLD
                    for values in component_scores.values()
                ]
            ).mean(axis=1)
            all_predictions.append(ensemble)
            persistence = base.copy()
            persistence["method"] = "persistence"
            persistence["score"] = (persistence["soil_moisture"] < threshold).astype(float)
            persistence["alert"] = persistence["score"].astype(bool)
            all_predictions.append(persistence)

            report["horizons"][str(horizon)] = {
                "threshold_train_p20": threshold,
                "split": {key: value.date().isoformat() for key, value in split.__dict__.items()},
                "first_legitimate_emission": (split.validation_end + pd.Timedelta(days=1))
                .date()
                .isoformat(),
                "partition_rows": {
                    "train": len(train),
                    "calibration": len(calibration),
                    "validation": len(validation),
                    "evaluation": len(base),
                },
                "component_mlflow_runs": component_runs,
            }

        predictions = pd.concat(all_predictions, ignore_index=True)
        predictions["horizon_days"] = (
            predictions["target_timestamp"] - predictions["emission_date"]
        ).dt.days
        predictions = predictions.sort_values(
            ["sensor_id", "emission_date", "horizon_days", "method"]
        ).reset_index(drop=True)
        predictions.to_csv(output_dir / "predictions.csv", index=False)

        metric_rows = []
        for (horizon, method), rows in predictions.groupby(["horizon_days", "method"]):
            values = _metrics(rows)
            episodes = _episode_metrics(rows)
            metric_rows.append({"horizon_days": horizon, "method": method, **values, **episodes})
        for horizon, rows in predictions.loc[predictions["method"] == "ensemble"].groupby(
            "horizon_days"
        ):
            majority = rows.copy()
            majority["score"] = majority["vote_fraction"]
            majority["alert"] = majority["majority_alert"]
            values = _metrics(majority)
            episodes = _episode_metrics(majority)
            metric_rows.append(
                {"horizon_days": horizon, "method": "majority_vote_secondary", **values, **episodes}
            )
        metrics = pd.DataFrame(metric_rows).sort_values(["horizon_days", "method"])
        metrics.to_csv(output_dir / "metrics.csv", index=False)
        report["metrics"] = metric_rows
        report["prediction_rows"] = int(len(predictions))
        report["prediction_sha256"] = _sha256(output_dir / "predictions.csv")
        (output_dir / "summary.json").write_text(
            json.dumps(report, indent=2, allow_nan=False, default=str), encoding="utf-8"
        )
        mlflow.log_artifacts(str(output_dir), artifact_path="causal_replay")
        for row in metric_rows:
            prefix = f"h{row['horizon_days']}_{row['method']}"
            mlflow.log_metrics(
                {
                    f"{prefix}_{key}": value
                    for key, value in _finite(row).items()
                    if key != "horizon_days"
                }
            )
    return report
