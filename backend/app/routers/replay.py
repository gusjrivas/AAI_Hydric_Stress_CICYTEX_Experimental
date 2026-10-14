"""Router de solo lectura para la reproducción histórica causal (spec
`historical-replay`, Paso 3). Carga exclusivamente el paquete autorizado
desde una ubicación configurada por el servidor
(`get_historical_replay_package_dir`) — el cliente nunca puede indicar una
ruta, un paquete ni un run. No ejecuta modelos ni recalcula métricas: solo
proyecta evidencia ya archivada según el reloj simulado (`simulated_date`)
que el cliente consulta. Funciona sin MLflow ni red: `load_package` es
puramente local.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from historical_replay.feedback import (
    FeedbackNotYetRevealedError,
    HistoricalReplayFeedbackRepository,
    InvalidFeedbackContentError,
    UnknownPredictionError,
    register_feedback,
    visible_feedback_for,
)
from historical_replay.history_state import classify_history_row
from historical_replay.history_view import filtered_history
from historical_replay.imputation_markers import (
    ImputationSourceDriftError,
    reconstruct_imputation_markers,
)
from historical_replay.observations import (
    CrossSeriesObservationError,
    ObservationConsistencyError,
    link_observation,
)
from historical_replay.package_loader import LoadedReplayPackage
from historical_replay.projection import project

from ..dependencies import (
    get_historical_replay_feedback_store,
    get_historical_replay_package,
    require_historical_replay_enabled,
)
from ..schemas_replay import (
    MedicionOriginal,
    ReplayCandidateInfo,
    ReplayDisclaimers,
    ReplayEvidenceCard,
    ReplayFeedbackEntry,
    ReplayFeedbackListResponse,
    ReplayFeedbackRequest,
    ReplayHistoryResponse,
    ReplayHistoryRow,
    ReplayLabelRule,
    ReplayOriginsResponse,
    ReplayOriginSummary,
    ReplayPredictionResponse,
)

_LABEL_RULE_OPERATORS = {
    "observed_value_at_t_plus_h_less_than_frozen_threshold": "less_than",
}


def _label_rule(manifest: dict) -> ReplayLabelRule:
    """Traduce `manifest.label_rule` a la ficha expuesta por la API —
    verificando primero el operador exacto contra la evidencia documentada
    (Paso 4.1 §3), nunca inventándolo ni invirtiendo las clases."""
    label_rule = manifest["label_rule"]
    rule_id = label_rule["rule"]
    if rule_id not in _LABEL_RULE_OPERATORS:
        raise HTTPException(
            status_code=500,
            detail=f"Regla de etiqueta no reconocida en el manifiesto: {rule_id!r}.",
        )
    return ReplayLabelRule(
        variable=label_rule["label_column"],
        unidad=label_rule["unit"],
        operador=_LABEL_RULE_OPERATORS[rule_id],
        umbral=label_rule["frozen_threshold"],
        percentil=label_rule.get("percentile"),
    )


def _training_max_date(effective_configuration: dict) -> date:
    training_dates = effective_configuration["training_dates"]
    return max(date.fromisoformat(raw[:10]) for raw in training_dates)


_ISSUANCE_TEXT = {
    "after_daily_observations_available": (
        "Se supone que las mediciones diarias ya están disponibles al emitir "
        "el pronóstico de ese día — es un supuesto documentado del protocolo, "
        "no un timestamp de recepción verificado por fila."
    ),
}

router = APIRouter(
    prefix="/replay",
    tags=["historical-replay"],
    dependencies=[Depends(require_historical_replay_enabled)],
)


def _disclaimers() -> ReplayDisclaimers:
    return ReplayDisclaimers()


def _find_record(package: LoadedReplayPackage, timestamp_origen: date):
    for record in package.records:
        if record.identity.timestamp_origen == timestamp_origen:
            return record
    return None


@router.get("/candidate", response_model=ReplayCandidateInfo)
def get_candidate(
    package: LoadedReplayPackage = Depends(get_historical_replay_package),
) -> ReplayCandidateInfo:
    candidate = package.manifest["candidate"]
    origins = [record.identity.timestamp_origen for record in package.records]
    targets = [record.target_timestamp for record in package.records]
    if not origins:
        raise HTTPException(status_code=503, detail="El paquete autorizado no tiene predicciones.")
    temporal = package.manifest["temporal_semantics"]
    issuance = temporal.get("issuance", "")
    return ReplayCandidateInfo(
        experiment_id=candidate["experiment_id"],
        run_id=candidate["run_id_child"],
        config_name=candidate["config_name"],
        seed=candidate["seed"],
        horizon_days=temporal["horizon_days"],
        periodo_inicio=min(origins),
        periodo_fin=max(targets),
        disclaimers=_disclaimers(),
        limitaciones=package.manifest["known_limitations"],
        evidencia=ReplayEvidenceCard(
            package_id=package.manifest["package_id"],
            dataset_name=package.manifest["dataset"]["name"],
            commit_sha=package.manifest["execution_identity"]["commit_sha"],
            split_date=temporal["split_date"],
            training_max_date=_training_max_date(package.effective_configuration),
            day_convention=temporal.get("day_convention", ""),
            issuance_assumption=_ISSUANCE_TEXT.get(issuance, issuance),
        ),
        regla_etiqueta=_label_rule(package.manifest),
    )


@router.get("/predictions", response_model=ReplayOriginsResponse)
def list_origins(
    package: LoadedReplayPackage = Depends(get_historical_replay_package),
) -> ReplayOriginsResponse:
    """Metadatos mínimos de los orígenes realmente disponibles — nunca
    observaciones ni resultados futuros (Paso 4 §2)."""
    origins = sorted({record.identity.timestamp_origen for record in package.records})
    return ReplayOriginsResponse(
        origins=[ReplayOriginSummary(timestamp_origen=origin) for origin in origins]
    )


@router.get(
    "/predictions/{timestamp_origen}",
    response_model=ReplayPredictionResponse,
    response_model_exclude_none=True,
)
def get_prediction(
    timestamp_origen: date,
    simulated_date: date = Query(..., description="Fecha del reloj simulado."),
    package: LoadedReplayPackage = Depends(get_historical_replay_package),
) -> ReplayPredictionResponse:
    record = _find_record(package, timestamp_origen)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No hay ninguna predicción archivada con origen " f"{timestamp_origen.isoformat()}."
            ),
        )

    view = project(record, simulated_date)
    if view is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Esa predicción todavía no fue emitida en la fecha simulada indicada "
                f"({simulated_date.isoformat()} es anterior a su origen)."
            ),
        )

    horizon_days = package.manifest["temporal_semantics"]["horizon_days"]
    payload = {
        "timestamp_origen": record.identity.timestamp_origen,
        "target_timestamp": record.target_timestamp,
        "experiment_id": record.identity.experiment_id,
        "run_id": record.identity.run_id,
        "config_name": record.identity.config_name,
        "seed": record.identity.seed,
        "horizon_days": horizon_days,
        "disclaimers": _disclaimers(),
        "y_pred": view.get("y_pred"),
    }

    if "target_observed" in view:
        payload["target_observed"] = view["target_observed"]
        if view["target_observed"]:
            payload["y_true"] = view["y_true"]
            payload["coincide"] = view["y_pred"] == view["y_true"]

            dataset_name = package.manifest["dataset"]["name"]
            label_column = package.manifest["label_rule"]["label_column"]
            try:
                observation = link_observation(
                    record=record,
                    dataset_name=dataset_name,
                    expected_dataset_name=dataset_name,
                    dataset_df=package.dataset,
                    label_column=label_column,
                    imputation_markers_df=None,
                )
            except (CrossSeriesObservationError, ObservationConsistencyError) as error:
                # Inconsistencia interna del paquete ya cargado y validado
                # (no un dato del cliente): se informa, no se sustituye por
                # un valor estimado.
                raise HTTPException(
                    status_code=500,
                    detail=f"Inconsistencia al vincular la observación: {error}",
                ) from error
            payload["medicion_original"] = MedicionOriginal(
                estado=observation.state, valor=observation.raw_value
            )

    return ReplayPredictionResponse(**payload)


@router.get("/history", response_model=ReplayHistoryResponse)
def get_history(
    simulated_date: date = Query(..., description="Fecha del reloj simulado."),
    package: LoadedReplayPackage = Depends(get_historical_replay_package),
) -> ReplayHistoryResponse:
    label_column = package.manifest["label_rule"]["label_column"]
    history = filtered_history(
        package.dataset, columns=[label_column], simulated_clock=simulated_date
    )

    try:
        markers = reconstruct_imputation_markers(package.dataset, [label_column])
        drift_causa = None
    except ImputationSourceDriftError as error:
        markers = None
        drift_causa = (
            f"ImputationSourceDriftError: {error} No se reconstruyen marcadores "
            "de imputación hasta revisar este cambio."
        )

    rows = []
    for _, row in history.iterrows():
        fecha = row["timestamp"].date()
        raw_value = None if pd.isna(row[label_column]) else float(row[label_column])
        state = classify_history_row(
            raw_value=raw_value,
            target_date=fecha,
            label_column=label_column,
            imputation_markers_df=markers,
            undetermined_causa=drift_causa,
        )
        rows.append(
            ReplayHistoryRow(
                fecha=fecha,
                soil_moisture=raw_value,
                estado=state.estado,
                causa=state.causa,
                valor_imputado=state.valor_imputado,
            )
        )
    return ReplayHistoryResponse(simulated_date=simulated_date, rows=rows)


@router.post(
    "/predictions/{timestamp_origen}/feedback",
    response_model=ReplayFeedbackEntry,
    status_code=201,
)
def create_feedback(
    timestamp_origen: date,
    body: ReplayFeedbackRequest,
    package: LoadedReplayPackage = Depends(get_historical_replay_package),
    store: HistoricalReplayFeedbackRepository = Depends(get_historical_replay_feedback_store),
) -> ReplayFeedbackEntry:
    """Registra feedback de demostración (RH-07). El servidor valida la
    identidad de la predicción referenciada y que su observación ya fue
    revelada en `simulated_date` — nunca confía únicamente en que el
    cliente haya esperado a que la interfaz revelara el resultado."""
    try:
        record = register_feedback(
            package.records,
            store,
            timestamp_origen=timestamp_origen,
            simulated_date=body.simulated_date,
            estado_validacion=body.estado_validacion,
            etiqueta_corregida=body.etiqueta_corregida,
            observacion=body.observacion,
        )
    except UnknownPredictionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except FeedbackNotYetRevealedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except InvalidFeedbackContentError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ReplayFeedbackEntry(
        timestamp_origen=date.fromisoformat(record.timestamp_origen),
        estado_validacion=record.estado_validacion,
        etiqueta_corregida=record.etiqueta_corregida,
        observacion=record.observacion,
        registered_at=record.registered_at,
        simulated_at=date.fromisoformat(record.simulated_at),
    )


@router.get("/predictions/{timestamp_origen}/feedback", response_model=ReplayFeedbackListResponse)
def get_feedback(
    timestamp_origen: date,
    simulated_date: date = Query(..., description="Fecha del reloj simulado."),
    package: LoadedReplayPackage = Depends(get_historical_replay_package),
    store: HistoricalReplayFeedbackRepository = Depends(get_historical_replay_feedback_store),
) -> ReplayFeedbackListResponse:
    """Feedback visible en `simulated_date` — retroceder el reloj vuelve a
    ocultarlo sin borrar el registro persistido."""
    visible = visible_feedback_for(
        package.records,
        store,
        timestamp_origen=timestamp_origen,
        simulated_date=simulated_date,
    )
    return ReplayFeedbackListResponse(
        timestamp_origen=timestamp_origen,
        feedback=[
            ReplayFeedbackEntry(
                timestamp_origen=date.fromisoformat(entry.timestamp_origen),
                estado_validacion=entry.estado_validacion,
                etiqueta_corregida=entry.etiqueta_corregida,
                observacion=entry.observacion,
                registered_at=entry.registered_at,
                simulated_at=date.fromisoformat(entry.simulated_at),
            )
            for entry in visible
        ],
    )
