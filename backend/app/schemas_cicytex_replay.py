"""Closed response schemas for the archived CICYTEX replay API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ClosedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CicytexEmissionDatesByHorizon(_ClosedResponse):
    horizon_1: list[date] = Field(default_factory=list, alias="1")
    horizon_2: list[date] = Field(default_factory=list, alias="2")
    horizon_3: list[date] = Field(default_factory=list, alias="3")


class CicytexCatalogResponse(_ClosedResponse):
    sensors: list[str]
    emission_dates: list[date]
    emission_dates_by_horizon: CicytexEmissionDatesByHorizon
    horizons: list[int]
    first_legitimate_emission: date
    last_observation: date


class CicytexPredictionResponse(_ClosedResponse):
    method: str
    score: float
    alert: bool
    target_date: date
    observed_soil_moisture: float | None
    observed_label: int | None
    outcome: Literal["VP", "FP", "FN", "VN"] | None


class CicytexReadingResponse(_ClosedResponse):
    date: date
    soil_moisture: float


class CicytexMetricResponse(_ClosedResponse):
    n: int
    tp: int
    tn: int
    fp: int
    fn: int
    mcc: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    coverage: float


class CicytexMetricsResponse(_ClosedResponse):
    logistic_regression: CicytexMetricResponse | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    random_forest: CicytexMetricResponse | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    hist_gradient_boosting_classifier: CicytexMetricResponse | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    ensemble: CicytexMetricResponse | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    persistence: CicytexMetricResponse | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class CicytexFeedbackResponse(_ClosedResponse):
    estado_validacion: Literal["confirmada", "rechazada"]
    etiqueta_corregida: int | None
    observacion: str | None
    registered_at: str
    simulated_at: date
    scope: str


class CicytexSessionResponse(_ClosedResponse):
    session_id: str
    sensor_id: str
    emission_date: date
    horizon_days: int
    revealed_through: date
    threshold: float
    proxy_notice: str
    predictions: list[CicytexPredictionResponse]
    readings: list[CicytexReadingResponse]
    metrics: CicytexMetricsResponse
    feedback: CicytexFeedbackResponse | None
    can_advance: bool


class CicytexSplitResponse(_ClosedResponse):
    train_end: date
    calibration_end: date
    validation_end: date
    evaluation_end: date


class CicytexPartitionRowsResponse(_ClosedResponse):
    train: int
    calibration: int
    validation: int
    evaluation: int


class CicytexComponentRunsResponse(_ClosedResponse):
    logistic_regression: str
    random_forest: str
    hist_gradient_boosting_classifier: str


class CicytexHorizonProvenanceResponse(_ClosedResponse):
    threshold_train_p20: float
    first_legitimate_emission: date
    split: CicytexSplitResponse
    partition_rows: CicytexPartitionRowsResponse
    component_mlflow_runs: CicytexComponentRunsResponse


class CicytexProvenanceResponse(_ClosedResponse):
    dataset_sha256: str
    git_commit: str
    seed: int
    proxy: str
    ensemble_policy: str
    mlflow_parent_run_id: str
    prediction_sha256: str
    horizons: dict[str, CicytexHorizonProvenanceResponse]
