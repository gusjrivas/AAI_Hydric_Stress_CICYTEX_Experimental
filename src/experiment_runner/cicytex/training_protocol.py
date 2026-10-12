"""Pure, shared feature and temporal-partition protocol for CICYTEX runners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

FEATURES = ("soil_moisture", "lag1", "lag2", "lag3", "roll_mean_3", "roll_mean_7")
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
        "max_depth": None,
        "early_stopping": False,
        "random_state": 42,
    },
}


@dataclass(frozen=True)
class TemporalSplit:
    train_end: pd.Timestamp
    calibration_end: pd.Timestamp
    validation_end: pd.Timestamp
    evaluation_end: pd.Timestamp


@dataclass(frozen=True, slots=True)
class HorizonPreparation:
    """Structurally immutable preparation containing mutable partition copies."""

    horizon_days: int
    split: TemporalSplit
    threshold_train_p20: float
    train: pd.DataFrame
    calibration: pd.DataFrame
    validation: pd.DataFrame
    evaluation: pd.DataFrame


def build_features(data: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Features y targets se construyen por sonda; nunca cruzan identidades."""
    pieces = []
    for sensor, group in data.groupby("sensor_id", sort=True, observed=True):
        frame = group.sort_values("timestamp").copy()
        moisture = frame["soil_moisture"]
        for lag in (1, 2, 3):
            frame[f"lag{lag}"] = moisture.shift(lag)
        for window in (3, 7):
            frame[f"roll_mean_{window}"] = moisture.rolling(window, min_periods=window).mean()
        frame["future_soil_moisture"] = moisture.shift(-horizon)
        frame["target_timestamp"] = frame["timestamp"] + pd.to_timedelta(horizon, unit="D")
        frame["sensor_id"] = sensor
        pieces.append(frame)
    return pd.concat(pieces, ignore_index=True)


def temporal_split(dates: pd.Series) -> TemporalSplit:
    unique = pd.Series(sorted(pd.to_datetime(dates).dropna().unique()))
    if len(unique) < 60:
        raise ValueError("Se requieren al menos 60 fechas para cuatro particiones temporales")

    # 50% fit, 15% calibración, 15% validación, 20% evaluación final.
    def at(fraction: float) -> pd.Timestamp:
        position = min(len(unique) - 1, int(len(unique) * fraction) - 1)
        return pd.Timestamp(unique.iloc[position])

    return TemporalSplit(at(0.50), at(0.65), at(0.80), pd.Timestamp(unique.iloc[-1]))


def select_partition(frame: pd.DataFrame, split: TemporalSplit, name: str) -> pd.DataFrame:
    target = frame["target_timestamp"]
    if name == "train":
        mask = target <= split.train_end
    elif name == "calibration":
        mask = (target > split.train_end) & (target <= split.calibration_end)
    elif name == "validation":
        mask = (target > split.calibration_end) & (target <= split.validation_end)
    elif name == "evaluation":
        mask = (target > split.validation_end) & (target <= split.evaluation_end)
    else:
        raise ValueError(name)
    return frame.loc[mask].copy()


def prepare_horizon(data: pd.DataFrame, horizon_days: int) -> HorizonPreparation:
    """Compose the shared scientific preparation without runner-specific labels."""
    featured = build_features(data, horizon_days).dropna(subset=[*FEATURES, "future_soil_moisture"])
    split = temporal_split(featured["target_timestamp"])
    parts = {
        name: select_partition(featured, split, name)
        for name in ("train", "calibration", "validation", "evaluation")
    }
    threshold = float(parts["train"]["future_soil_moisture"].quantile(0.20))
    return HorizonPreparation(
        horizon_days=horizon_days,
        split=split,
        threshold_train_p20=threshold,
        train=parts["train"],
        calibration=parts["calibration"],
        validation=parts["validation"],
        evaluation=parts["evaluation"],
    )
