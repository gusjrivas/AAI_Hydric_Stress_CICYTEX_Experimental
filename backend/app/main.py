"""Punto de entrada de la app FastAPI (spec alerting-ui)."""

from __future__ import annotations

import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from data_ingestion.catalog import CatalogError
from data_ingestion.history import HistoryError
from human_feedback.operational_repository import OperationalRepositoryError

from .routers import (
    cicytex_replay,
    feedback,
    feedback_triage,
    forecast,
    lineage,
    models,
    producer_v2,
    quality,
    recalibration,
    replay,
    sensors,
)

app = FastAPI(title="Alerting UI API")

# Paso 4.1 §4: los orígenes extra (p. ej. el puerto aislado de una sesión de
# demostración) se configuran por variable de entorno — nunca editando esta
# lista a mano para cada sesión.
_extra_cors_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_EXTRA_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", *_extra_cors_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _v2_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                    "request_id": request.state.request_id,
                }
            }
        ),
    )


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(CatalogError)
async def catalog_error_handler(request: Request, error: CatalogError) -> JSONResponse:
    return _v2_error_response(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )


@app.exception_handler(HistoryError)
async def history_error_handler(request: Request, error: HistoryError) -> JSONResponse:
    return _v2_error_response(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )


@app.exception_handler(OperationalRepositoryError)
async def operational_repository_error_handler(
    request: Request, error: OperationalRepositoryError
) -> JSONResponse:
    return _v2_error_response(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, error: RequestValidationError):
    if not request.url.path.startswith("/api/v2/"):
        return await request_validation_exception_handler(request, error)
    return _v2_error_response(
        request,
        status_code=422,
        code="validation_error",
        message="La solicitud no cumple el contrato.",
        details={"errors": error.errors()},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, error: HTTPException):
    if not request.url.path.startswith("/api/v2/"):
        return await http_exception_handler(request, error)
    return _v2_error_response(
        request,
        status_code=error.status_code,
        code="resource_not_found" if error.status_code == 404 else "http_error",
        message=str(error.detail),
        details={},
    )


app.include_router(forecast.router)
app.include_router(feedback.router)
app.include_router(recalibration.router)
app.include_router(sensors.router)
app.include_router(quality.router)
app.include_router(models.router)
app.include_router(lineage.router)
app.include_router(producer_v2.router)
app.include_router(replay.router)
app.include_router(cicytex_replay.router)
app.include_router(feedback_triage.router)
