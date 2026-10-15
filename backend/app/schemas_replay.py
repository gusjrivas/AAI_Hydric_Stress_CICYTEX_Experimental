"""Modelos Pydantic de request/response de la API de solo lectura de
reproducción histórica (spec `historical-replay`, Paso 3). Campos
explícitamente permitidos: nunca se serializa `LoadedReplayPackage`, el
`DataFrame` completo, los artefactos crudos ni el manifiesto completo.
`y_proba` se omite deliberadamente de toda respuesta (no se expone como
probabilidad de riesgo ni como confianza calibrada en esta primera API de
demostración).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class ReplayDisclaimers(BaseModel):
    reproduccion_retrospectiva: bool = True
    proxy_estadistico_relativo: bool = True
    utilidad_agronomica_demostrada: bool = False


class ReplayEvidenceCard(BaseModel):
    """Ficha expandible de trazabilidad (Paso 4 §4) — campos explícitos
    tomados de evidencia ya verificada (manifiesto del paquete), nunca el
    manifiesto completo.

    `split_date` (corte de partición train/test) y `training_max_date`
    (última fecha realmente usada para entrenar, de
    `effective_configuration.json::training_dates`) se exponen por separado
    a propósito (Paso 4.1 §3): en este candidato no coinciden, y presentar
    solo `split_date` induciría a leerla como si fuera la última fecha de
    entrenamiento.
    """

    package_id: str
    dataset_name: str
    commit_sha: str
    split_date: date
    training_max_date: date
    day_convention: str
    issuance_assumption: str


class ReplayLabelRule(BaseModel):
    """Regla de la clase proxy, tal como está declarada en
    `manifest.label_rule` (Paso 4.1 §3) — nunca inventada ni invertida."""

    variable: str
    unidad: str
    operador: Literal["less_than"]
    umbral: float
    percentil: float | None = None


class ReplayCandidateInfo(BaseModel):
    experiment_id: str
    run_id: str
    config_name: str
    seed: int
    horizon_days: int
    periodo_inicio: date
    periodo_fin: date
    disclaimers: ReplayDisclaimers
    limitaciones: list[str]
    evidencia: ReplayEvidenceCard
    regla_etiqueta: ReplayLabelRule


class MedicionOriginal(BaseModel):
    estado: str
    valor: float | None = None


class ReplayPredictionResponse(BaseModel):
    timestamp_origen: date
    target_timestamp: date
    experiment_id: str
    run_id: str
    config_name: str
    seed: int
    horizon_days: int
    disclaimers: ReplayDisclaimers
    y_pred: int | None = None
    target_observed: bool | None = None
    y_true: float | None = None
    coincide: bool | None = None
    medicion_original: MedicionOriginal | None = None


class ReplayHistoryRow(BaseModel):
    fecha: date
    soil_moisture: float | None = None
    estado: Literal["medida", "imputada", "no_determinado", "sin_dato_en_fuente"]
    causa: str | None = None
    valor_imputado: float | None = None


class ReplayHistoryResponse(BaseModel):
    simulated_date: date
    rows: list[ReplayHistoryRow]


class ReplayOriginSummary(BaseModel):
    """Metadatos mínimos de un origen disponible — nunca observaciones ni
    resultados futuros (spec `historical-replay`, Paso 4 §2)."""

    timestamp_origen: date


class ReplayOriginsResponse(BaseModel):
    origins: list[ReplayOriginSummary]


class ReplayFeedbackRequest(BaseModel):
    simulated_date: date
    estado_validacion: Literal["confirmada", "rechazada"]
    etiqueta_corregida: Literal[0, 1] | None = None
    observacion: str | None = None


class ReplayFeedbackEntry(BaseModel):
    timestamp_origen: date
    estado_validacion: Literal["confirmada", "rechazada"]
    etiqueta_corregida: int | None = None
    observacion: str | None = None
    registered_at: datetime
    simulated_at: date


class ReplayFeedbackListResponse(BaseModel):
    timestamp_origen: date
    feedback: list[ReplayFeedbackEntry]
