"""Read-only, session-gated access to archived CICYTEX causal emissions."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from historical_replay.catalog import GetReplayCatalog
from historical_replay.sessions import (
    ReplaySession,
    ReplaySessionNotFound,
    ReplaySessionService,
)

from ..dependencies import get_cicytex_replay_catalog, get_cicytex_replay_sessions

router = APIRouter(prefix="/api/v2/cicytex/replay", tags=["cicytex-replay"])
METHOD_ORDER = [
    "logistic_regression",
    "random_forest",
    "hist_gradient_boosting_classifier",
    "ensemble",
    "persistence",
]


class SessionRequest(BaseModel):
    sensor_id: str
    emission_date: date
    horizon_days: int = Field(default=1, ge=1, le=3)


class FeedbackRequest(BaseModel):
    estado_validacion: str
    etiqueta_corregida: int | None = Field(default=None, ge=0, le=1)
    observacion: str | None = Field(default=None, max_length=1000)


_feedback_lock = Lock()


def _root() -> Path:
    configured = os.getenv("CICYTEX_REPLAY_DIR")
    return (
        Path(configured)
        if configured
        else Path(__file__).resolve().parents[3] / "results" / "cicytex" / "causal_replay"
    )


def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    root = _root()
    try:
        predictions = pd.read_csv(
            root / "predictions.csv", parse_dates=["emission_date", "target_timestamp"]
        )
        observations = pd.read_csv(root / "observations.csv", parse_dates=["timestamp"])
    except (OSError, ValueError) as error:
        raise HTTPException(503, "El paquete causal CICYTEX no esta preparado") from error
    return predictions, observations


def _feedback_path() -> Path:
    root = Path(os.getenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(_root() / "feedback")))
    root.mkdir(parents=True, exist_ok=True)
    return root / "feedback.json"


def _feedback_key(session: ReplaySession) -> str:
    return f"{session.sensor_id}|{session.emission_date.isoformat()}|{session.horizon_days}"


def _read_feedback_document() -> dict:
    path = _feedback_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_feedback() -> dict:
    with _feedback_lock:
        return _read_feedback_document()


def _write_feedback_document(document: dict) -> None:
    path = _feedback_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _iso(value: object) -> str:
    return pd.Timestamp(value).date().isoformat()


def _metric(rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {
            "n": 0,
            "tp": 0,
            "tn": 0,
            "fp": 0,
            "fn": 0,
            "mcc": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "coverage": 0.0,
        }
    y = rows["observed_label"].astype(int)
    p = rows["alert"].astype(str).str.lower().isin(["true", "1"]).astype(int)
    tp = int(((y == 1) & (p == 1)).sum())
    tn = int(((y == 0) & (p == 0)).sum())
    fp = int(((y == 0) & (p == 1)).sum())
    fn = int(((y == 1) & (p == 0)).sum())
    denominator = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "n": int(len(rows)),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "mcc": (tp * tn - fp * fn) / denominator if denominator else None,
        "precision": precision,
        "recall": recall,
        "f1": (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else None
        ),
        "coverage": 1.0,
    }


def _render(session: ReplaySession) -> dict:
    predictions, observations = _load()
    sensor_predictions = predictions.loc[predictions["sensor_id"] == session.sensor_id].copy()
    selected = sensor_predictions.loc[
        (sensor_predictions["emission_date"].dt.date == session.emission_date)
        & (sensor_predictions["horizon_days"] == session.horizon_days)
    ]
    if selected.empty:
        raise HTTPException(404, "No existe esa emision CICYTEX")
    reveal = pd.Timestamp(session.revealed_through)
    known = observations.loc[
        (observations["sensor_id"] == session.sensor_id) & (observations["timestamp"] <= reveal)
    ].sort_values("timestamp")
    predictions_view = []
    for _, row in selected.sort_values(
        "method", key=lambda column: column.map({m: i for i, m in enumerate(METHOD_ORDER)})
    ).iterrows():
        target_revealed = pd.Timestamp(row["target_timestamp"]) <= reveal
        predictions_view.append(
            {
                "method": row["method"],
                "score": float(row["score"]),
                "alert": str(row["alert"]).lower() in {"true", "1"},
                "target_date": _iso(row["target_timestamp"]),
                "observed_soil_moisture": (
                    float(row["observed_soil_moisture"]) if target_revealed else None
                ),
                "observed_label": int(row["observed_label"]) if target_revealed else None,
                "outcome": (
                    (
                        ("VP" if int(row["observed_label"]) else "FP")
                        if str(row["alert"]).lower() in {"true", "1"}
                        else ("FN" if int(row["observed_label"]) else "VN")
                    )
                    if target_revealed
                    else None
                ),
            }
        )
    accumulated = sensor_predictions.loc[
        (sensor_predictions["emission_date"].dt.date >= session.start_date)
        & (sensor_predictions["emission_date"] <= reveal)
        & (sensor_predictions["target_timestamp"] <= reveal)
        & (sensor_predictions["horizon_days"] == session.horizon_days)
    ]
    metrics = {method: _metric(rows) for method, rows in accumulated.groupby("method")}
    return {
        "session_id": session.session_id,
        "sensor_id": session.sensor_id,
        "emission_date": session.emission_date.isoformat(),
        "horizon_days": session.horizon_days,
        "revealed_through": session.revealed_through.isoformat(),
        "threshold": float(selected.iloc[0]["event_threshold"]),
        "proxy_notice": "P20 estimado solo con entrenamiento; no es estres fisiologico observado.",
        "predictions": predictions_view,
        "readings": [
            {"date": _iso(row.timestamp), "soil_moisture": float(row.soil_moisture)}
            for row in known.itertuples()
        ],
        "metrics": metrics,
        "feedback": _read_feedback().get(_feedback_key(session)),
        "can_advance": session.revealed_through < date(2023, 7, 25),
    }


@router.get("/catalog")
def catalog(query: GetReplayCatalog = Depends(get_cicytex_replay_catalog)) -> dict:
    try:
        return query.execute().to_dict()
    except (OSError, ValueError) as error:
        raise HTTPException(503, "El paquete causal CICYTEX no esta preparado") from error


@router.post("/sessions", status_code=201)
def create_session(
    request: SessionRequest,
    sessions: ReplaySessionService = Depends(get_cicytex_replay_sessions),
) -> dict:
    predictions, _ = _load()
    valid = predictions.loc[
        (predictions["sensor_id"] == request.sensor_id)
        & (predictions["emission_date"].dt.date == request.emission_date)
        & (predictions["horizon_days"] == request.horizon_days)
    ]
    if valid.empty:
        raise HTTPException(422, "Seleccion fuera del paquete causal")
    session = sessions.create(
        sensor_id=request.sensor_id,
        emission_date=request.emission_date,
        horizon_days=request.horizon_days,
    )
    return _render(session)


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    sessions: ReplaySessionService = Depends(get_cicytex_replay_sessions),
) -> dict:
    try:
        session = sessions.get(session_id)
    except ReplaySessionNotFound:
        raise HTTPException(404, "Sesion inexistente")
    return _render(session)


@router.post("/sessions/{session_id}/advance")
def advance(
    session_id: str,
    sessions: ReplaySessionService = Depends(get_cicytex_replay_sessions),
) -> dict:
    try:
        session = sessions.advance(session_id)
    except ReplaySessionNotFound:
        raise HTTPException(404, "Sesion inexistente")
    return _render(session)


@router.post("/sessions/{session_id}/reset")
def reset(
    session_id: str,
    sessions: ReplaySessionService = Depends(get_cicytex_replay_sessions),
) -> dict:
    try:
        session = sessions.reset(session_id)
    except ReplaySessionNotFound:
        raise HTTPException(404, "Sesion inexistente")
    return _render(session)


@router.post("/sessions/{session_id}/feedback", status_code=201)
def create_feedback(
    session_id: str,
    request: FeedbackRequest,
    sessions: ReplaySessionService = Depends(get_cicytex_replay_sessions),
) -> dict:
    if request.estado_validacion not in {"confirmada", "rechazada"}:
        raise HTTPException(422, "estado_validacion invalido")
    try:
        session = sessions.get(session_id)
    except ReplaySessionNotFound:
        raise HTTPException(404, "Sesion inexistente")
    target = session.emission_date + timedelta(days=session.horizon_days)
    if session.revealed_through < target:
        raise HTTPException(409, "La observacion todavia no fue revelada")
    with _feedback_lock:
        document = _read_feedback_document()
        key = _feedback_key(session)
        if key in document:
            raise HTTPException(409, "Ya existe feedback para esta prediccion")
        entry = {
            "estado_validacion": request.estado_validacion,
            "etiqueta_corregida": request.etiqueta_corregida,
            "observacion": request.observacion.strip() if request.observacion else None,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "simulated_at": session.revealed_through.isoformat(),
            "scope": "demostracion; no recalibra ni reentrena",
        }
        document[key] = entry
        _write_feedback_document(document)
    return entry
