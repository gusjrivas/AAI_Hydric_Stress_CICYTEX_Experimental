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
from historical_replay.adapters.sqlite_feedback import SQLiteReplayFeedbackStore
from historical_replay.adapters.sqlite_sessions import (
    SQLiteCicytexFeedbackRepository,
    SQLiteSessionRepository,
)
from historical_replay.catalog import GetReplayCatalog
from historical_replay.cicytex_application import (
    CicytexCatalogApplication,
    CicytexFeedbackApplication,
    CicytexReplayApplication,
)
from historical_replay.cicytex_feedback import (
    CicytexFeedbackRepositoryError,
    CicytexFeedbackService,
)
from historical_replay.feedback import HistoricalReplayFeedbackRepository
from historical_replay.package_loader import LoadedReplayPackage, load_package
from historical_replay.replay_application import (
    HistoricalReplayApplication,
    HistoricalReplayFeedbackApplication,
)
from historical_replay.sessions import ReplaySessionService
from human_feedback.adapters.disabled import DisabledDecisionPolicyEngine
from human_feedback.adapters.laya_http import LayaDecisionPolicyEngine
from human_feedback.decision_policy import TriageFeedback
from human_feedback.historical_review_store import HistoricalReviewStore
from human_feedback.operational_repository import OperationalRepository

from .config import (
    CicytexLegacyFeedbackConfigurationError,
    get_cicytex_legacy_feedback_json,
    get_cicytex_replay_session_database,
    get_dataset_data_dir,
    get_historical_replay_feedback_database,
    get_historical_replay_feedback_dir,
    get_historical_replay_package_dir,
    is_historical_replay_enabled,
    is_producer_v2_enabled,
)


def _get_cicytex_legacy_feedback_json() -> Path | None:
    try:
        return get_cicytex_legacy_feedback_json()
    except CicytexLegacyFeedbackConfigurationError:
        raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None


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


def get_cicytex_replay_frames() -> tuple:
    import pandas as pd

    configured = os.getenv("CICYTEX_REPLAY_DIR")
    root = (
        Path(configured)
        if configured
        else Path(__file__).resolve().parents[2] / "results" / "cicytex" / "causal_replay"
    )
    try:
        return (
            pd.read_csv(
                root / "predictions.csv", parse_dates=["emission_date", "target_timestamp"]
            ),
            pd.read_csv(root / "observations.csv", parse_dates=["timestamp"]),
        )
    except (OSError, ValueError) as error:
        raise HTTPException(503, "El paquete causal CICYTEX no esta preparado") from error


@lru_cache(maxsize=1)
def get_cicytex_replay_sessions() -> ReplaySessionService:
    """Process-scoped session use case, replaceable through FastAPI overrides."""

    database = get_cicytex_replay_session_database()
    SQLiteCicytexFeedbackRepository(
        database,
        legacy_feedback_path=_get_cicytex_legacy_feedback_json(),
    )
    return ReplaySessionService(
        SQLiteSessionRepository(database),
        id_factory=lambda: uuid4().hex,
        last_observation=date(2023, 7, 25),
    )


def get_cicytex_replay_feedback() -> CicytexFeedbackService:
    return CicytexFeedbackService(
        SQLiteCicytexFeedbackRepository(
            get_cicytex_replay_session_database(),
            legacy_feedback_path=_get_cicytex_legacy_feedback_json(),
        )
    )


def get_cicytex_catalog_application(
    query: GetReplayCatalog = Depends(get_cicytex_replay_catalog),
) -> CicytexCatalogApplication:
    return CicytexCatalogApplication(query)


def get_cicytex_replay_application(
    sessions: ReplaySessionService = Depends(get_cicytex_replay_sessions),
    frames: tuple = Depends(get_cicytex_replay_frames),
    feedback: CicytexFeedbackService = Depends(get_cicytex_replay_feedback),
) -> CicytexReplayApplication:
    return CicytexReplayApplication(frames, sessions, feedback)


def get_cicytex_feedback_application(
    sessions: ReplaySessionService = Depends(get_cicytex_replay_sessions),
    feedback: CicytexFeedbackService = Depends(get_cicytex_replay_feedback),
) -> CicytexFeedbackApplication:
    return CicytexFeedbackApplication(sessions, feedback)


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
    database: Path = Depends(get_historical_replay_feedback_database),
) -> HistoricalReplayFeedbackRepository:
    """Almacenamiento de feedback de demostración (RH-07), aislado por
    `package_id` — nunca el mismo archivo entre paquetes distintos."""
    legacy = get_historical_replay_feedback_dir() / f"{package.manifest['package_id']}.jsonl"
    return SQLiteReplayFeedbackStore(
        database,
        package_id=package.manifest["package_id"],
        legacy_jsonl_path=legacy if legacy.is_file() else None,
    )


def get_historical_replay_application(
    package: LoadedReplayPackage = Depends(get_historical_replay_package),
) -> HistoricalReplayApplication:
    return HistoricalReplayApplication(package)


def get_historical_replay_feedback_application(
    package: LoadedReplayPackage = Depends(get_historical_replay_package),
    store: HistoricalReplayFeedbackRepository = Depends(get_historical_replay_feedback_store),
) -> HistoricalReplayFeedbackApplication:
    return HistoricalReplayFeedbackApplication(package, store)
