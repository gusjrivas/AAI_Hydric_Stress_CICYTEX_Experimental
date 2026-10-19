"""Esquemas OpenAPI de catalogo e historial operacional v2."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CatalogText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
SensorId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,64}$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SectorCreate(StrictModel):
    display_name: CatalogText
    crop: CatalogText | None = None


class SectorPatch(StrictModel):
    expected_revision: int = Field(ge=1)
    display_name: CatalogText | None = None
    crop: CatalogText | None = None
    primary_sensor_id: SensorId | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        changed = self.model_fields_set - {"expected_revision"}
        if not changed:
            raise ValueError("Debe indicar al menos un campo para actualizar.")
        if "display_name" in changed and self.display_name is None:
            raise ValueError("display_name no admite null.")
        return self


class SectorResponse(StrictModel):
    sector_id: str
    display_name: str
    crop: str | None
    primary_sensor_id: str | None
    revision: int
    created_at: datetime


class SectorListResponse(StrictModel):
    items: list[SectorResponse]
    next_cursor: str | None


class SensorCreate(StrictModel):
    sensor_id: SensorId
    display_name: CatalogText
    sector_id: str | None = None
    source_kind: Literal["real", "synthetic", "unknown"]


class SensorPatch(StrictModel):
    expected_revision: int = Field(ge=1)
    display_name: CatalogText | None = None
    sector_id: str | None = None
    source_kind: Literal["real", "synthetic", "unknown"] | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        changed = self.model_fields_set - {"expected_revision"}
        if not changed:
            raise ValueError("Debe indicar al menos un campo para actualizar.")
        if "display_name" in changed and self.display_name is None:
            raise ValueError("display_name no admite null.")
        if "source_kind" in changed and self.source_kind is None:
            raise ValueError("source_kind no admite null.")
        return self


class SensorResponse(StrictModel):
    sensor_id: str
    display_name: str
    sector_id: str | None
    source_kind: Literal["real", "synthetic", "unknown"]
    revision: int
    created_at: datetime | None
    registered: bool


class SensorListResponse(StrictModel):
    items: list[SensorResponse]
    next_cursor: str | None


class ReadingWindow(StrictModel):
    start_date: date
    end_date: date
    expected_days: int


class ReadingRow(StrictModel):
    date: date
    soil_moisture: float | None
    relative_humidity: float | None
    solar_radiation: float | None
    temperature: float | None
    precipitation: float | None
    wind_speed: float | None
    et0: float | None
    origin: Literal["real", "synthetic", "external_reanalysis", "unknown"]
    quality_flags: list[str]
    # Variables whose value on this date was completed by causal
    # forward-fill (`data_quality.imputation.interpolate_missing_causal`)
    # rather than present in the source for that day. Distinct from
    # `origin`, which describes the dataset's provenance (real/synthetic/
    # external reanalysis), not the treatment of an individual value: a
    # real dataset can still contain imputed values. Always `[]` for
    # datasets that never impute (the common case).
    imputed_variables: list[str]
    # Variables whose value on this date has an imputation-tracking column
    # in the dataset schema (i.e. this dataset context DOES track
    # imputation) but whose per-row flag for this date is present-but-null:
    # neither confirmed real nor confirmed imputed. Never presented as an
    # independent observation. Always `[]` for datasets that never track
    # imputation at all, and disjoint from `imputed_variables`.
    unverified_variables: list[str]


class VariableCoverage(StrictModel):
    variable: str
    observed_days: int
    missing_days: int
    # Days in the window where this variable had a value only because it
    # was imputed, never counted towards `observed_days`. `0` for datasets
    # that never impute.
    imputed_days: int
    # Days where this variable had a value but its imputation-tracking flag
    # was present-but-null: provenance not verified, never counted towards
    # `observed_days` or `imputed_days`. `0` for datasets that never track
    # imputation for this variable.
    unverified_days: int


class InputRole(StrictModel):
    variable: str
    role: Literal["model_input", "context_only", "unknown"]
    basis: Literal["issued", "configured", "unknown"]
    model_reference: str | None


class ReadingsResponse(StrictModel):
    sensor_id: str
    calendar_timezone: Literal["UTC"]
    server_today: date
    snapshot_id: str | None
    window: ReadingWindow
    status: Literal["ready", "no_readings"]
    rows: list[ReadingRow]
    missing_dates: list[date]
    variable_coverage: list[VariableCoverage]
    units: dict[str, str]
    input_roles: list[InputRole]
    last_reading_date: date | None
    data_age_days: int | None
    provenance: Literal["real", "synthetic", "external_reanalysis", "mixed", "unknown"]


class EventThreshold(StrictModel):
    variable: str
    value: float
    unit: str
    comparison: Literal["lt"]


class ModelReference(StrictModel):
    model_version: str | None
    horizon_days: Literal[1, 2, 3]
    contract_version: str
    trained_through: date | None
    calibration_version: str | None
    assessment_reference: str | None
    calibrated_through: date | None = None


AgreementCategory = Literal[
    "alerta_por_unanimidad",
    "posible_alerta_acuerdo_parcial",
    "sin_alerta_por_mayoria_con_discrepancia",
    "sin_alerta_por_unanimidad",
]


EnsembleFamily = Literal[
    "logistic_regression", "random_forest", "hist_gradient_boosting_classifier"
]
_ENSEMBLE_FAMILIES = ("logistic_regression", "random_forest", "hist_gradient_boosting_classifier")
_ENSEMBLE_AGREEMENT_V1_WEIGHT = 1.0 / 3.0


class EnsembleComponentVote(StrictModel):
    family: EnsembleFamily
    model_reference: ModelReference
    calibrated_through: date
    score: float = Field(ge=0.0, le=1.0)
    decision_threshold: float = Field(ge=0.0, le=1.0)
    alert: bool


class EnsembleDetail(StrictModel):
    policy_version: str
    ensemble_identity_sha256: str
    weights: dict[EnsembleFamily, float]
    components: list[EnsembleComponentVote] = Field(min_length=3, max_length=3)
    combined_probability: float = Field(ge=0.0, le=1.0)
    combined_alert: bool
    positive_votes: int
    agreement_category: AgreementCategory
    calibrated_through: date

    @model_validator(mode="after")
    def validate_coherence(self):
        families = [component.family for component in self.components]
        if sorted(set(families)) != sorted(_ENSEMBLE_FAMILIES) or len(families) != 3:
            raise ValueError("components debe tener exactamente las 3 familias, sin duplicados.")

        if self.policy_version == "ensemble_agreement_v1":
            if set(self.weights) != set(_ENSEMBLE_FAMILIES):
                raise ValueError("weights debe declarar exactamente las 3 familias.")
            if any(
                abs(value - _ENSEMBLE_AGREEMENT_V1_WEIGHT) > 1e-9 for value in self.weights.values()
            ):
                raise ValueError("weights debe ser 1/3 uniforme para ensemble_agreement_v1.")

        expected_votes = sum(1 for component in self.components if component.alert)
        if expected_votes != self.positive_votes:
            raise ValueError("positive_votes no coincide con los votos individuales de components.")
        expected_category = {
            3: "alerta_por_unanimidad",
            2: "posible_alerta_acuerdo_parcial",
            1: "sin_alerta_por_mayoria_con_discrepancia",
            0: "sin_alerta_por_unanimidad",
        }[self.positive_votes]
        if expected_category != self.agreement_category:
            raise ValueError("agreement_category no coincide con positive_votes.")
        expected_probability = sum(component.score for component in self.components) / 3
        if abs(expected_probability - self.combined_probability) > 1e-9:
            raise ValueError("combined_probability no coincide con el promedio de components.")

        thresholds = {component.decision_threshold for component in self.components}
        if len(thresholds) != 1:
            raise ValueError(
                "decision_threshold debe ser igual entre los componentes del ensamble."
            )
        threshold = thresholds.pop()
        for component in self.components:
            if component.alert != (component.score >= threshold):
                raise ValueError(
                    f"alert de {component.family} no coincide con score >= decision_threshold."
                )
        if self.combined_alert != (self.combined_probability >= threshold):
            raise ValueError(
                "combined_alert no coincide con combined_probability >= decision_threshold."
            )
        return self


class LatestReview(StrictModel):
    review_id: str
    request_id: str
    revision: int
    forecast_id: str
    action: Literal["confirm", "reject"]
    observed_label: bool
    comment: str | None
    reviewed_at: datetime


TrainingEligibility = Literal[
    "no_review",
    "waiting_target_maturity",
    "requires_mature_revalidation",
    "compatible_correction",
    "confirmation_only",
    "incompatible_source_model",
    "incompatible_contract",
    "insufficient_data",
    "applied",
]


class ForecastReview(StrictModel):
    status: Literal["pending", "confirmed", "rejected"]
    revision: int
    review_open_at: datetime
    reviewable: bool
    blocked_reason: (
        Literal[
            "review_not_open",
            "target_observation_imputed",
            "target_observation_missing",
            "target_observation_unverified",
        ]
        | None
    )
    latest_review: LatestReview | None
    training_eligibility: TrainingEligibility
    applied_review_references: list[str]


class ForecastResponse(StrictModel):
    forecast_id: str
    sensor_id: str
    batch_id: str
    as_of_date: date
    horizon_days: Literal[1, 2, 3]
    target_date: date
    contract_version: str
    issued_at: datetime
    snapshot_id: str
    alert: bool
    score: float
    score_kind: Literal[
        "raw_model_score", "calibrated_probability", "ensemble_mean_of_calibrated_components"
    ]
    display_probability: float | None
    probability_status: Literal["development_assessed", "not_qualified"]
    probability_reason_code: str | None
    decision_threshold: float
    event_threshold: EventThreshold
    model_reference: ModelReference
    review: ForecastReview
    ensemble: EnsembleDetail | None = None


class ForecastListResponse(StrictModel):
    items: list[ForecastResponse]
    next_cursor: str | None
    pending_total: int
    reviewable_pending_total: int


class ReviewCreate(StrictModel):
    request_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    expected_revision: int = Field(ge=0)
    action: Literal["confirm", "reject"]
    comment: Annotated[str, StringConstraints(max_length=2000)] | None = None


class ErrorBody(StrictModel):
    code: str
    message: str
    details: dict
    request_id: str


class ErrorResponse(StrictModel):
    error: ErrorBody


class EmissionRequest(StrictModel):
    pass


class AvailableForecastSlot(ForecastResponse):
    status: Literal["available"]
    reason_code: None = None


class UnavailableForecastSlot(StrictModel):
    horizon_days: Literal[1, 2, 3]
    target_date: date | None
    status: Literal["unavailable"]
    reason_code: str
    forecast_id: None = None
    alert: None = None
    score: None = None
    score_kind: None = None
    display_probability: None = None
    probability_status: None = None
    probability_reason_code: None = None
    decision_threshold: None = None
    event_threshold: None = None
    model_reference: None = None
    review: None = None


class ForecastBatchResponse(StrictModel):
    batch_id: str | None
    revision: int
    sensor_id: str
    contract_version: str
    as_of_date: date | None
    issued_at: datetime | None
    snapshot_id: str | None
    calendar_timezone: Literal["UTC"]
    server_today: date
    data_age_days: int | None
    provenance: Literal["real", "synthetic", "external_reanalysis", "mixed", "unknown"]
    slots: list[AvailableForecastSlot | UnavailableForecastSlot] = Field(min_length=3, max_length=3)


class CodeIdentity(StrictModel):
    """Identidad de código registrada al entrenar el bundle. `commit`/`dirty`
    son `None` cuando git no estaba disponible (`available=False`)."""

    available: bool
    commit: str | None
    dirty: bool | None


class ProvenanceComponent(StrictModel):
    family: EnsembleFamily
    # None = el bundle no registró `code_identity` ("no registrado").
    code_identity: CodeIdentity | None


class HorizonProvenance(StrictModel):
    horizon_days: Literal[1, 2, 3]
    status: Literal["available", "unavailable"]
    reason_code: str | None
    mode: Literal["single", "ensemble"] | None
    model_reference: ModelReference | None
    ensemble_identity_sha256: str | None
    code_identity: CodeIdentity | None
    components: list[ProvenanceComponent]


class BatchProvenanceResponse(StrictModel):
    """Lista blanca de identidad de una emisión; nunca `input_snapshot`."""

    batch_id: str
    sensor_id: str
    as_of_date: date
    contract_version: str
    snapshot_id: str
    horizons: list[HorizonProvenance] = Field(min_length=3, max_length=3)
    # Datos que el backend no persiste con la emisión (declarados, no inferidos).
    not_persisted: list[Literal["full_config", "mlflow_run", "seed"]]
