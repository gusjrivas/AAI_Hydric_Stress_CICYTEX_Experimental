"""Site-neutral contracts for ensemble demonstration training.

This module describes a frozen training plan. It deliberately does not read
datasets, train models, write manifests, or know any site-specific module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from predictive_modeling.operational_contract import VariableMetadata
from predictive_modeling.operational_preparation import SUPPORTED_HORIZONS, TemporalCutPlan


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
