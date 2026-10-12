"""Dependencia compartida de FastAPI para validar `sensor_id` en los
cuatro routers de `alerting-ui` (ADR-0008): un único punto de
validación, reusando `data_ingestion.sensor_naming.validate_sensor_id`.
"""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, HTTPException

from data_ingestion.catalog import CatalogRepository
from data_ingestion.sensor_naming import validate_sensor_id
from historical_replay.adapters.cicytex_csv import CsvReplayCatalogSource
from historical_replay.adapters.sqlite_sessions import SQLiteSessionRepository
from historical_replay.catalog import GetReplayCatalog
from historical_replay.feedback import ReplayFeedbackStore
from historical_replay.package_loader import LoadedReplayPackage, load_package
from historical_replay.sessions import ReplaySessionService
from human_feedback.adapters.disabled import DisabledDecisionPolicyEngine
from human_feedback.adapters.laya_http import LayaDecisionPolicyEngine
from human_feedback.decision_policy import TriageFeedback
from human_feedback.historical_review_store import HistoricalReviewStore
from human_feedback.operational_repository import OperationalRepository

from .config import (
    get_cicytex_replay_session_database,
    get_dataset_data_dir,
    get_historical_replay_feedback_dir,
    get_historical_replay_package_dir,
    is_historical_replay_enabled,
    is_producer_v2_enabled,
)


def get_valid_sensor_id(sensor_id: str) -> str:
    try:
        return validate_sensor_id(sensor_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def get_catalog_repository(
    data_dir: Path = Depends(get_dataset_data_dir),
) -> CatalogRepository:
    """Repositorio operacional aislable mediante dependency_overrides."""
    return CatalogRepository(data_dir)


def get_operational_repository(
    sensor_id: str,
    data_dir: Path = Depends(get_dataset_data_dir),
) -> OperationalRepository:
    """Repositorio v2 de emisiones/revisiones del sensor de la ruta,
    aislable mediante dependency_overrides igual que el resto de v2.
    """
    return OperationalRepository(data_dir, sensor_id)


def require_producer_v2_enabled(
    enabled: bool = Depends(is_producer_v2_enabled),
) -> None:
    if not enabled:
        raise HTTPException(status_code=404, detail="Not Found")


def get_producer_bundle_root(data_dir: Path = Depends(get_dataset_data_dir)) -> Path:
    """Administrator-controlled deployment directory; never a client-supplied path."""
    return Path(os.environ.get("PRODUCER_BUNDLE_ROOT", str(data_dir / "operational_bundles")))


def get_historical_review_store(
    sensor_id: str,
    data_dir: Path = Depends(get_dataset_data_dir),
) -> HistoricalReviewStore:
    """Feedback del recorrido historico, aislado de
    `OperationalRepository` (nunca el mismo archivo ni el mismo
    directorio), aislable mediante dependency_overrides igual que el
    resto de v2."""
    return HistoricalReviewStore(data_dir, sensor_id)


def require_historical_replay_enabled(
    enabled: bool = Depends(is_historical_replay_enabled),
) -> None:
    if not enabled:
        raise HTTPException(status_code=404, detail="Not Found")


def get_cicytex_replay_catalog() -> GetReplayCatalog:
    configured = os.getenv("CICYTEX_REPLAY_DIR")
    root = (
        Path(configured)
        if configured
        else Path(__file__).resolve().parents[2] / "results" / "cicytex" / "causal_replay"
    )
    return GetReplayCatalog(CsvReplayCatalogSource(root))


@lru_cache(maxsize=1)
def get_cicytex_replay_sessions() -> ReplaySessionService:
    """Process-scoped session use case, replaceable through FastAPI overrides."""

    return ReplaySessionService(
        SQLiteSessionRepository(get_cicytex_replay_session_database()),
        id_factory=lambda: uuid4().hex,
        last_observation=date(2023, 7, 25),
    )


def get_feedback_triage() -> TriageFeedback:
    url = os.getenv("LAYA_DECISION_URL")
    revision = os.getenv("LAYA_MODEL_REVISION")
    minimum_confidence = float(os.getenv("LAYA_MIN_CONFIDENCE", "0.85"))

    if url is None and revision is None:
        return TriageFeedback(
            DisabledDecisionPolicyEngine(),
            minimum_confidence=minimum_confidence,
        )
    if not url or not revision:
        raise RuntimeError("LAYA_DECISION_URL and LAYA_MODEL_REVISION must be configured together")

    engine = LayaDecisionPolicyEngine(
        url,
        model_revision=revision,
        timeout_seconds=float(os.getenv("LAYA_TIMEOUT_SECONDS", "0.8")),
        api_key=os.getenv("LAYA_API_KEY"),
    )
    return TriageFeedback(engine, minimum_confidence=minimum_confidence)


def get_historical_replay_package(
    package_dir: Path = Depends(get_historical_replay_package_dir),
) -> LoadedReplayPackage:
    """Carga y valida el único paquete autorizado en cada solicitud (spec
    `historical-replay`) — nunca a partir de una ruta, un paquete ni un run
    indicado por el cliente. Recargar en cada solicitud, en vez de cachear,
    revalida integridad y admisión siempre; el costo es despreciable para
    este paquete (unas decenas de KB)."""
    try:
        return load_package(package_dir)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail=f"Paquete de reproducción histórica no disponible o inválido: {error}",
        ) from error


def get_historical_replay_feedback_store(
    package: LoadedReplayPackage = Depends(get_historical_replay_package),
    feedback_dir: Path = Depends(get_historical_replay_feedback_dir),
) -> ReplayFeedbackStore:
    """Almacenamiento de feedback de demostración (RH-07), aislado por
    `package_id` — nunca el mismo archivo entre paquetes distintos."""
    return ReplayFeedbackStore(feedback_dir, package_id=package.manifest["package_id"])
