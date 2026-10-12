"""Configuración del backend (fachada delgada, ADR-0003). Los nombres
de dataset, feedback log y modelo registrado ya no son globales por
deployment: se derivan por sensor (ADR-0008,
`data_ingestion.sensor_naming`).
"""

from __future__ import annotations

import os
from pathlib import Path

from data_ingestion.storage import DEFAULT_DATA_DIR

HISTORICAL_DATASET_NAME = "melchor_romero_2024_consolidado"

FEATURE_COLUMNS = ["soil_moisture", "solar_radiation", "relative_humidity"]
LABEL_COLUMN = "soil_moisture"
RANDOM_STATE = 42
HORIZON_DAYS = 3
# Identificador de la versión metodológica del pipeline (auditoría de fuga
# temporal + validación cruzada purgada), usado como parte del contrato de
# compatibilidad de `human_feedback.model_registry` — ver
# docs/research/hu8-analisis-resultados.md, sección 11, y la auditoría de
# validación cruzada purgada posterior.
PIPELINE_VERSION = "controlled_daily_v3"


def get_feedback_data_dir() -> Path:
    """Dependencia de FastAPI: directorio donde persisten los registros
    de retroalimentación. Overrideable en tests
    (`app.dependency_overrides`) para no escribir en el `data/` real
    del proyecto.
    """
    return DEFAULT_DATA_DIR


def get_dataset_data_dir() -> Path:
    """Dependencia de FastAPI: directorio donde persisten los datasets
    de sensor. Overrideable en tests (`app.dependency_overrides`) para
    no escribir en el `data/` real del proyecto.
    """
    return DEFAULT_DATA_DIR


def is_producer_v2_enabled() -> bool:
    """Feature flag aditivo; deshabilitarlo no elimina metadatos persistidos."""
    return os.getenv("PRODUCER_V2_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_historical_replay_enabled() -> bool:
    """Feature flag aditivo (spec `historical-replay`): apagado por defecto,
    consistente con `is_producer_v2_enabled`. No expone la API de
    reproducción histórica salvo que se habilite explícitamente."""
    return os.getenv("HISTORICAL_REPLAY_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_historical_replay_feedback_dir() -> Path:
    """Dependencia de FastAPI: directorio exclusivo del feedback de
    demostración (spec `historical-replay`, RH-07) — nunca
    `data/feedback__<sensor_id>.parquet`, nunca dentro de
    `replay_packages/`. Overrideable en tests."""
    configured = os.environ.get("HISTORICAL_REPLAY_FEEDBACK_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "replay_feedback"


def get_historical_replay_package_dir() -> Path:
    """Dependencia de FastAPI: ubicación del único paquete de reproducción
    histórica autorizado (spec `historical-replay`, Paso 3 §3) —
    administrator-controlled deployment directory; el cliente nunca puede
    indicar una ruta, un paquete ni un run. Overrideable en tests mediante
    `app.dependency_overrides`, igual que `get_producer_bundle_root`.
    """
    configured = os.environ.get("HISTORICAL_REPLAY_PACKAGE_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "replay_packages" / "base-seed4-1157696b7b-v2"


def get_cicytex_replay_session_database() -> Path:
    """Return the administrator-controlled durable replay-session store."""

    configured = os.environ.get("CICYTEX_REPLAY_SESSION_DB")
    if configured:
        return Path(configured)
    return DEFAULT_DATA_DIR / "cicytex_replay_sessions.sqlite3"
