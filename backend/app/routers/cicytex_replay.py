"""Read-only, session-gated access to archived CICYTEX causal emissions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from threading import Lock
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v2/cicytex/replay", tags=["cicytex-replay"])
METHOD_ORDER = [
    "logistic_regression", "random_forest", "hist_gradient_boosting_classifier",
    "ensemble", "persistence",
]


class SessionRequest(BaseModel):
    sensor_id: str
    emission_date: date
    horizon_days: int = Field(default=1, ge=1, le=3)


@dataclass
class Session:
    sensor_id: str
    start_date: date
    emission_date: date
    horizon_days: int
    revealed_through: date


_sessions: dict[str, Session] = {}
_lock = Lock()


def _root() -> Path:
    configured = os.getenv("CICYTEX_REPLAY_DIR")
    return Path(configured) if configured else Path(__file__).resolve().parents[3] / "results" / "cicytex" / "causal_replay"


def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    root = _root()
    try:
        predictions = pd.read_csv(root / "predictions.csv", parse_dates=["emission_date", "target_timestamp"])
        observations = pd.read_csv(root / "observations.csv", parse_dates=["timestamp"])
    except (OSError, ValueError) as error:
        raise HTTPException(503, "El paquete causal CICYTEX no esta preparado") from error
    return predictions, observations


def _iso(value: object) -> str:
    return pd.Timestamp(value).date().isoformat()


def _metric(rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {"n": 0, "tp": 0, "tn": 0, "fp": 0, "fn": 0, "mcc": None, "precision": None, "recall": None, "f1": None, "coverage": 0.0}
    y = rows["observed_label"].astype(int)
    p = rows["alert"].astype(str).str.lower().isin(["true", "1"]).astype(int)
    tp = int(((y == 1) & (p == 1)).sum()); tn = int(((y == 0) & (p == 0)).sum())
    fp = int(((y == 0) & (p == 1)).sum()); fn = int(((y == 1) & (p == 0)).sum())
    denominator = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "n": int(len(rows)), "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "mcc": (tp * tn - fp * fn) / denominator if denominator else None,
        "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None,
        "coverage": 1.0,
    }


def _render(session_id: str, session: Session) -> dict:
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
        (observations["sensor_id"] == session.sensor_id)
        & (observations["timestamp"] <= reveal)
    ].sort_values("timestamp")
    predictions_view = []
    for _, row in selected.sort_values("method", key=lambda column: column.map({m: i for i, m in enumerate(METHOD_ORDER)})).iterrows():
        target_revealed = pd.Timestamp(row["target_timestamp"]) <= reveal
        predictions_view.append({
            "method": row["method"], "score": float(row["score"]),
            "alert": str(row["alert"]).lower() in {"true", "1"},
            "target_date": _iso(row["target_timestamp"]),
            "observed_soil_moisture": float(row["observed_soil_moisture"]) if target_revealed else None,
            "observed_label": int(row["observed_label"]) if target_revealed else None,
            "outcome": (
                ("VP" if int(row["observed_label"]) else "FP") if str(row["alert"]).lower() in {"true", "1"}
                else ("FN" if int(row["observed_label"]) else "VN")
            ) if target_revealed else None,
        })
    accumulated = sensor_predictions.loc[
        (sensor_predictions["emission_date"].dt.date >= session.start_date)
        & (sensor_predictions["emission_date"] <= reveal)
        & (sensor_predictions["target_timestamp"] <= reveal)
        & (sensor_predictions["horizon_days"] == session.horizon_days)
    ]
    metrics = {method: _metric(rows) for method, rows in accumulated.groupby("method")}
    return {
        "session_id": session_id, "sensor_id": session.sensor_id,
        "emission_date": session.emission_date.isoformat(), "horizon_days": session.horizon_days,
        "revealed_through": session.revealed_through.isoformat(),
        "threshold": float(selected.iloc[0]["event_threshold"]),
        "proxy_notice": "P20 estimado solo con entrenamiento; no es estres fisiologico observado.",
        "predictions": predictions_view,
        "readings": [{"date": _iso(row.timestamp), "soil_moisture": float(row.soil_moisture)} for row in known.itertuples()],
        "metrics": metrics,
        "can_advance": session.revealed_through < date(2023, 7, 25),
    }


@router.get("/catalog")
def catalog() -> dict:
    predictions, _ = _load()
    emissions = sorted({_iso(value) for value in predictions["emission_date"]})
    return {
        "sensors": sorted(predictions["sensor_id"].unique().tolist()),
        "emission_dates": emissions,
        "emission_dates_by_horizon": {
            str(horizon): sorted({_iso(value) for value in rows["emission_date"]})
            for horizon, rows in predictions.groupby("horizon_days")
        },
        "horizons": [1, 2, 3],
        "first_legitimate_emission": "2023-07-06",
        "last_observation": "2023-07-25",
    }


@router.post("/sessions", status_code=201)
def create_session(request: SessionRequest) -> dict:
    predictions, _ = _load()
    valid = predictions.loc[
        (predictions["sensor_id"] == request.sensor_id)
        & (predictions["emission_date"].dt.date == request.emission_date)
        & (predictions["horizon_days"] == request.horizon_days)
    ]
    if valid.empty:
        raise HTTPException(422, "Seleccion fuera del paquete causal")
    session_id = uuid4().hex
    session = Session(request.sensor_id, request.emission_date, request.emission_date, request.horizon_days, request.emission_date)
    with _lock:
        _sessions[session_id] = session
    return _render(session_id, session)


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    with _lock:
        session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "Sesion inexistente")
    return _render(session_id, session)


@router.post("/sessions/{session_id}/advance")
def advance(session_id: str) -> dict:
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "Sesion inexistente")
        session.revealed_through = min(session.revealed_through + timedelta(days=1), date(2023, 7, 25))
    return _render(session_id, session)


@router.post("/sessions/{session_id}/reset")
def reset(session_id: str) -> dict:
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "Sesion inexistente")
        session.revealed_through = session.emission_date
    return _render(session_id, session)
