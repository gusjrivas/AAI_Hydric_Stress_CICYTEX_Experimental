"""HTTP adapter for archived CICYTEX causal replay use cases."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from historical_replay.cicytex_application import (
    CicytexCatalogApplication,
    CicytexCatalogUnavailable,
    CicytexEmissionNotFound,
    CicytexFeedbackAlreadyExists,
    CicytexFeedbackApplication,
    CicytexFeedbackNotRevealed,
    CicytexInvalidFeedbackState,
    CicytexReplayApplication,
    CicytexSelectionUnavailable,
    CicytexSessionNotFound,
)

from ..dependencies import (
    get_cicytex_catalog_application,
    get_cicytex_feedback_application,
    get_cicytex_replay_application,
    get_cicytex_replay_provenance,
)
from ..schemas_cicytex_replay import (
    CicytexCatalogResponse,
    CicytexFeedbackResponse,
    CicytexProvenanceResponse,
    CicytexSessionResponse,
)

router = APIRouter(prefix="/api/v2/cicytex/replay", tags=["cicytex-replay"])


class SessionRequest(BaseModel):
    sensor_id: str
    emission_date: date
    horizon_days: int = Field(default=1, ge=1, le=3)


class FeedbackRequest(BaseModel):
    estado_validacion: Literal["confirmada", "rechazada"]
    etiqueta_corregida: int | None = Field(default=None, ge=0, le=1)
    observacion: str | None = Field(default=None, max_length=1000)


@router.get(
    "/catalog",
    response_model=CicytexCatalogResponse,
    response_model_exclude_unset=True,
)
def catalog(
    application: CicytexCatalogApplication = Depends(get_cicytex_catalog_application),
) -> dict:
    try:
        return application.catalog()
    except CicytexCatalogUnavailable as error:
        raise HTTPException(503, "El paquete causal CICYTEX no esta preparado") from error


@router.get("/provenance", response_model=CicytexProvenanceResponse)
def provenance(
    application=Depends(get_cicytex_replay_provenance),
) -> dict:
    try:
        return application.provenance()
    except CicytexCatalogUnavailable as error:
        raise HTTPException(503, "El paquete causal CICYTEX no esta preparado") from error


@router.post("/sessions", response_model=CicytexSessionResponse, status_code=201)
def create_session(
    request: SessionRequest,
    application: CicytexReplayApplication = Depends(get_cicytex_replay_application),
) -> dict:
    try:
        return application.create_session(
            sensor_id=request.sensor_id,
            emission_date=request.emission_date,
            horizon_days=request.horizon_days,
        )
    except CicytexSelectionUnavailable:
        raise HTTPException(422, "Seleccion fuera del paquete causal") from None
    except CicytexEmissionNotFound:
        raise HTTPException(404, "No existe esa emision CICYTEX") from None


@router.get("/sessions/{session_id}", response_model=CicytexSessionResponse)
def get_session(
    session_id: str,
    application: CicytexReplayApplication = Depends(get_cicytex_replay_application),
) -> dict:
    try:
        return application.get_session(session_id)
    except CicytexSessionNotFound:
        raise HTTPException(404, "Sesion inexistente") from None
    except CicytexEmissionNotFound:
        raise HTTPException(404, "No existe esa emision CICYTEX") from None


@router.post("/sessions/{session_id}/advance", response_model=CicytexSessionResponse)
def advance(
    session_id: str,
    application: CicytexReplayApplication = Depends(get_cicytex_replay_application),
) -> dict:
    try:
        return application.advance_session(session_id)
    except CicytexSessionNotFound:
        raise HTTPException(404, "Sesion inexistente") from None
    except CicytexEmissionNotFound:
        raise HTTPException(404, "No existe esa emision CICYTEX") from None


@router.post("/sessions/{session_id}/reset", response_model=CicytexSessionResponse)
def reset(
    session_id: str,
    application: CicytexReplayApplication = Depends(get_cicytex_replay_application),
) -> dict:
    try:
        return application.reset_session(session_id)
    except CicytexSessionNotFound:
        raise HTTPException(404, "Sesion inexistente") from None
    except CicytexEmissionNotFound:
        raise HTTPException(404, "No existe esa emision CICYTEX") from None


@router.post(
    "/sessions/{session_id}/feedback",
    response_model=CicytexFeedbackResponse,
    status_code=201,
)
def create_feedback(
    session_id: str,
    request: FeedbackRequest,
    application: CicytexFeedbackApplication = Depends(get_cicytex_feedback_application),
) -> dict:
    try:
        return application.create_feedback(
            session_id,
            estado_validacion=request.estado_validacion,
            etiqueta_corregida=request.etiqueta_corregida,
            observacion=request.observacion,
        )
    except CicytexInvalidFeedbackState:
        raise HTTPException(422, "estado_validacion invalido") from None
    except CicytexSessionNotFound:
        raise HTTPException(404, "Sesion inexistente") from None
    except CicytexFeedbackAlreadyExists:
        raise HTTPException(409, "Ya existe feedback para esta prediccion") from None
    except CicytexFeedbackNotRevealed:
        raise HTTPException(409, "La observacion todavia no fue revelada") from None
