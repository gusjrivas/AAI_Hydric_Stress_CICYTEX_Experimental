"""Site-neutral contracts for ensemble demonstration training.

This module describes a frozen training plan. It deliberately does not read
datasets, train models, write manifests, or know any site-specific module.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from predictive_modeling.bundle_export import write_component_bundle, write_ensemble_manifest
from predictive_modeling.bundle_packaging import attach_feature_names
from predictive_modeling.operational_contract import VariableMetadata
from predictive_modeling.operational_preparation import (
    SUPPORTED_HORIZONS,
    TARGET_LABEL_COLUMN,
    TemporalCutPlan,
    add_multihorizon_targets,
    partition_labeled_horizon,
)
from predictive_modeling.operational_run import build_feature_frame

FitComponent = Callable[[str, Any, Any, Any, Any], tuple[Any, Any]]
ResolveThreshold = Callable[[pd.DataFrame], float]
ScientificScalar = str | int | float | bool | None


def _non_empty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")


def _non_empty_unique(values: tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{field} must be a non-empty tuple")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{field} must contain non-empty text")
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must not contain duplicates")


@dataclass(frozen=True, slots=True)
class EnsembleFamilySpec:
    """Deeply immutable estimator-family configuration."""

    family: str
    parameter_items: tuple[tuple[str, ScientificScalar], ...]

    def __post_init__(self) -> None:
        _non_empty(self.family, "family")
        if not isinstance(self.parameter_items, tuple) or not self.parameter_items:
            raise ValueError("parameter_items must be a non-empty tuple")
        keys: list[str] = []
        for item in self.parameter_items:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("parameter_items must contain key-value tuples")
            key, value = item
            _non_empty(key, "parameter key")
            if not isinstance(value, str | int | float | bool) and value is not None:
                raise TypeError("parameter values must be JSON scalar values")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("floating-point parameter values must be finite")
            keys.append(key)
        if len(keys) != len(set(keys)):
            raise ValueError("parameter keys must not contain duplicates")

    @classmethod
    def from_mapping(
        cls, family: str, parameters: Mapping[str, ScientificScalar]
    ) -> EnsembleFamilySpec:
        if not isinstance(parameters, Mapping):
            raise TypeError("parameters must be a mapping")
        return cls(family=family, parameter_items=tuple(parameters.items()))

    def parameters(self) -> dict[str, ScientificScalar]:
        """Return a mutable copy suitable for estimator and JSON boundaries."""
        return dict(self.parameter_items)


@dataclass(frozen=True)
class EnsembleDemoPlan:
    """Immutable scientific configuration consumed by a shared demo engine."""

    horizons: tuple[int, ...]
    contract_version: str
    event_variable: str
    event_unit: str
    event_comparison: str
    feature_columns: tuple[str, ...]
    lags: tuple[int, ...]
    rolling_windows: tuple[int, ...]
    decision_threshold: float
    variables: tuple[VariableMetadata, ...]
    temporal_cuts: TemporalCutPlan
    family_names: tuple[str, ...]
    model_identity_template: str
    calibrator_identity_template: str

    def __post_init__(self) -> None:
        if self.horizons != SUPPORTED_HORIZONS:
            raise ValueError("horizons must be exactly (1, 2, 3)")
        _non_empty(self.contract_version, "contract_version")
        _non_empty(self.event_variable, "event_variable")
        _non_empty(self.event_unit, "event_unit")
        if self.event_comparison != "lt":
            raise ValueError("event_comparison must be lt")
        _non_empty_unique(self.feature_columns, "feature_columns")
        _non_empty_unique(self.family_names, "family_names")
        if (
            not isinstance(self.lags, tuple)
            or not self.lags
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in self.lags
            )
        ):
            raise ValueError("lags must contain positive integers")
        if (
            not isinstance(self.rolling_windows, tuple)
            or not self.rolling_windows
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in self.rolling_windows
            )
        ):
            raise ValueError("rolling_windows must contain positive integers")
        if (
            isinstance(self.decision_threshold, bool)
            or not isinstance(self.decision_threshold, int | float)
            or not math.isfinite(self.decision_threshold)
            or not 0 <= self.decision_threshold <= 1
        ):
            raise ValueError("decision_threshold must be finite and between zero and one")
        if (
            not isinstance(self.variables, tuple)
            or not self.variables
            or not all(isinstance(variable, VariableMetadata) for variable in self.variables)
        ):
            raise ValueError("variables must be a non-empty tuple of VariableMetadata")
        variable_units = {variable.name: variable.unit for variable in self.variables}
        if len(variable_units) != len(self.variables):
            raise ValueError("variables must not contain duplicate names")
        if variable_units.get(self.event_variable) != self.event_unit:
            raise ValueError("event variable and unit must be declared in variables")
        if not isinstance(self.temporal_cuts, TemporalCutPlan):
            raise ValueError("temporal_cuts must be a TemporalCutPlan")
        for field, template in (
            ("model_identity_template", self.model_identity_template),
            ("calibrator_identity_template", self.calibrator_identity_template),
        ):
            _non_empty(template, field)
            try:
                rendered = template.format(family="family", horizon=1)
            except (KeyError, IndexError, ValueError) as error:
                raise ValueError(f"{field} must accept family and horizon") from error
            _non_empty(rendered, field)


class EmptyTrainingPartitionError(RuntimeError):
    """Raised when feature purging leaves train or calibration without rows."""


@dataclass(frozen=True)
class HorizonDemoTrainingResult:
    """Immutable paths and counts produced for one horizon."""

    horizon: int
    written_items: tuple[tuple[str, Path], ...]
    train_rows_used: int
    train_rows_excluded_by_purge: int
    calibration_rows_used: int
    calibration_rows_excluded_by_purge: int
    component_file_items: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]

    @property
    def written(self) -> dict[str, Path]:
        return dict(self.written_items)

    def manifest_report(self) -> dict[str, Any]:
        return {
            "train_rows_used": self.train_rows_used,
            "train_rows_excluded_by_purge": self.train_rows_excluded_by_purge,
            "calibration_rows_used": self.calibration_rows_used,
            "calibration_rows_excluded_by_purge": self.calibration_rows_excluded_by_purge,
            "components": {family: dict(files) for family, files in self.component_file_items},
        }


@dataclass(frozen=True)
class EnsembleDemoTrainingResult:
    """Complete immutable result returned to a site-specific facade."""

    threshold: float
    horizon_results: tuple[HorizonDemoTrainingResult, ...]

    @property
    def written(self) -> dict[int, dict[str, Path]]:
        return {result.horizon: result.written for result in self.horizon_results}


def run_ensemble_demo_training(
    daily_frame: pd.DataFrame,
    *,
    dataset_sha256: str,
    output_dir: Path,
    sensor_id: str,
    horizons: tuple[int, ...],
    plan: EnsembleDemoPlan,
    resolve_threshold: ResolveThreshold,
    fit_component: FitComponent,
    on_threshold_resolved: Callable[[float], None] | None = None,
    on_horizon_completed: Callable[[HorizonDemoTrainingResult], None] | None = None,
) -> EnsembleDemoTrainingResult:
    """Train and export ensemble components without owning site run state."""
    threshold = resolve_threshold(daily_frame)
    if on_threshold_resolved is not None:
        on_threshold_resolved(threshold)
    feature_frame, feature_names_tuple = build_feature_frame(
        daily_frame,
        list(plan.feature_columns),
        lags=list(plan.lags),
        windows=list(plan.rolling_windows),
    )
    feature_names = list(feature_names_tuple)
    labeled_by_horizon = add_multihorizon_targets(
        feature_frame,
        column=plan.event_variable,
        thresholds={horizon: threshold for horizon in plan.horizons},
    )
    event = {
        "variable": plan.event_variable,
        "threshold": threshold,
        "unit": plan.event_unit,
        "comparison": plan.event_comparison,
    }
    variables = [{"name": variable.name, "unit": variable.unit} for variable in plan.variables]

    horizon_results: list[HorizonDemoTrainingResult] = []
    for horizon in horizons:
        prepared = partition_labeled_horizon(
            labeled_by_horizon[horizon],
            cuts=plan.temporal_cuts,
            required_inference_columns=feature_names,
        )
        train_rows = prepared.train.dropna(subset=feature_names)
        calibration_rows = prepared.calibration.dropna(subset=feature_names)
        if train_rows.empty or calibration_rows.empty:
            raise EmptyTrainingPartitionError(
                f"horizonte {horizon}: partición vacía tras la purga."
            )

        X_train = train_rows[feature_names].to_numpy()
        y_train = train_rows[TARGET_LABEL_COLUMN].astype(int).to_numpy()
        X_calibration = calibration_rows[feature_names].to_numpy()
        y_calibration = calibration_rows[TARGET_LABEL_COLUMN].astype(int).to_numpy()
        horizon_dir = Path(output_dir) / sensor_id / f"horizon_{horizon}"
        written_items: list[tuple[str, Path]] = []
        component_file_items: list[tuple[str, tuple[tuple[str, str], ...]]] = []

        for family in plan.family_names:
            model, calibrator = fit_component(
                family, X_train, y_train, X_calibration, y_calibration
            )
            attach_feature_names(model, feature_names)
            attach_feature_names(calibrator, feature_names)
            component_dir = write_component_bundle(
                horizon_dir / "ensemble" / family,
                sensor_id=sensor_id,
                horizon=horizon,
                model=model,
                calibrator=calibrator,
                feature_columns=list(plan.feature_columns),
                feature_names=feature_names,
                lags=list(plan.lags),
                rolling_windows=list(plan.rolling_windows),
                decision_threshold=plan.decision_threshold,
                event=event,
                variables=variables,
                contract_version=plan.contract_version,
                model_identity_label=plan.model_identity_template.format(
                    family=family, horizon=horizon
                ),
                calibrator_identity_label=plan.calibrator_identity_template.format(
                    family=family, horizon=horizon
                ),
                temporal_cuts=plan.temporal_cuts,
                trained_through=plan.temporal_cuts.train.end.isoformat(),
                calibrated_through=plan.temporal_cuts.calibration.end.isoformat(),
                data_snapshot_sha256=dataset_sha256,
            )
            written_items.append((family, component_dir))
            bundle_meta = json.loads((component_dir / "bundle.json").read_text())
            component_file_items.append((family, tuple(dict(bundle_meta["files"]).items())))

        write_ensemble_manifest(
            horizon_dir,
            sensor_id=sensor_id,
            horizon=horizon,
            contract_version=plan.contract_version,
        )
        horizon_result = HorizonDemoTrainingResult(
            horizon=horizon,
            written_items=tuple(written_items),
            train_rows_used=int(len(train_rows)),
            train_rows_excluded_by_purge=int(len(prepared.train) - len(train_rows)),
            calibration_rows_used=int(len(calibration_rows)),
            calibration_rows_excluded_by_purge=int(
                len(prepared.calibration) - len(calibration_rows)
            ),
            component_file_items=tuple(component_file_items),
        )
        horizon_results.append(horizon_result)
        if on_horizon_completed is not None:
            on_horizon_completed(horizon_result)

    return EnsembleDemoTrainingResult(
        threshold=threshold,
        horizon_results=tuple(horizon_results),
    )
