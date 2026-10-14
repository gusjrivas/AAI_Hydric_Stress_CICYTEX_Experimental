"""HTTP adapter for the archived historical replay application."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from historical_replay.replay_application import (
    HistoricalReplayApplication,
    HistoricalReplayFeedbackApplication,
    ReplayFeedbackNotRevealed,
    ReplayInternalConsistencyError,
    ReplayInvalidFeedback,
    ReplayPackageEmpty,
    ReplayPredictionNotEmitted,
    ReplayPredictionNotFound,
    ReplayUnknownFeedbackPrediction,
)

from ..dependencies import (
    get_historical_replay_application,
    get_historical_replay_feedback_application,
    require_historical_replay_enabled,
)
from ..schemas_replay import (
    ReplayCandidateInfo,
    ReplayFeedbackEntry,
    ReplayFeedbackListResponse,
    ReplayFeedbackRequest,
    ReplayHistoryResponse,
    ReplayOriginsResponse,
    ReplayPredictionResponse,
)

router = APIRouter(
    prefix="/replay",
    tags=["historical-replay"],
    dependencies=[Depends(require_historical_replay_enabled)],
)


@router.get("/candidate", response_model=ReplayCandidateInfo)
def get_candidate(
    application: HistoricalReplayApplication = Depends(get_historical_replay_application),
) -> ReplayCandidateInfo:
    try:
        return ReplayCandidateInfo(**application.candidate())
    except ReplayPackageEmpty as error:
        raise HTTPException(status_code=503, detail=error.detail) from error
    except ReplayInternalConsistencyError as error:
        raise HTTPException(status_code=500, detail=error.detail) from error


@router.get("/predictions", response_model=ReplayOriginsResponse)
def list_origins(
    application: HistoricalReplayApplication = Depends(get_historical_replay_application),
) -> ReplayOriginsResponse:
    return ReplayOriginsResponse(**application.origins())


@router.get(
    "/predictions/{timestamp_origen}",
    response_model=ReplayPredictionResponse,
    response_model_exclude_none=True,
)
def get_prediction(
    timestamp_origen: date,
    simulated_date: date = Query(..., description="Fecha del reloj simulado."),
    application: HistoricalReplayApplication = Depends(get_historical_replay_application),
) -> ReplayPredictionResponse:
    try:
        return ReplayPredictionResponse(
            **application.prediction(
                timestamp_origen=timestamp_origen,
                simulated_date=simulated_date,
            )
        )
    except ReplayPredictionNotFound as error:
        raise HTTPException(status_code=404, detail=error.detail) from error
    except ReplayPredictionNotEmitted as error:
        raise HTTPException(status_code=404, detail=error.detail) from error
    except ReplayInternalConsistencyError as error:
        raise HTTPException(status_code=500, detail=error.detail) from error


@router.get("/history", response_model=ReplayHistoryResponse)
def get_history(
    simulated_date: date = Query(..., description="Fecha del reloj simulado."),
    application: HistoricalReplayApplication = Depends(get_historical_replay_application),
) -> ReplayHistoryResponse:
    return ReplayHistoryResponse(**application.history(simulated_date=simulated_date))


@router.post(
    "/predictions/{timestamp_origen}/feedback",
    response_model=ReplayFeedbackEntry,
    status_code=201,
)
def create_feedback(
    timestamp_origen: date,
    body: ReplayFeedbackRequest,
    application: HistoricalReplayFeedbackApplication = Depends(
        get_historical_replay_feedback_application
    ),
) -> ReplayFeedbackEntry:
    try:
        return ReplayFeedbackEntry(
            **application.create_feedback(
                timestamp_origen=timestamp_origen,
                simulated_date=body.simulated_date,
                estado_validacion=body.estado_validacion,
                etiqueta_corregida=body.etiqueta_corregida,
                observacion=body.observacion,
            )
        )
    except ReplayUnknownFeedbackPrediction as error:
        raise HTTPException(status_code=404, detail=error.detail) from error
    except ReplayFeedbackNotRevealed as error:
        raise HTTPException(status_code=409, detail=error.detail) from error
    except ReplayInvalidFeedback as error:
        raise HTTPException(status_code=422, detail=error.detail) from error


@router.get("/predictions/{timestamp_origen}/feedback", response_model=ReplayFeedbackListResponse)
def get_feedback(
    timestamp_origen: date,
    simulated_date: date = Query(..., description="Fecha del reloj simulado."),
    application: HistoricalReplayFeedbackApplication = Depends(
        get_historical_replay_feedback_application
    ),
) -> ReplayFeedbackListResponse:
    return ReplayFeedbackListResponse(
        **application.feedback(
            timestamp_origen=timestamp_origen,
            simulated_date=simulated_date,
        )
    )
