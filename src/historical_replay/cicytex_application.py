"""Framework-free orchestration for the CICYTEX causal replay."""

from __future__ import annotations

from datetime import date

import pandas as pd

from historical_replay.catalog import GetReplayCatalog
from historical_replay.cicytex_feedback import (
    CicytexFeedbackConflict,
    CicytexFeedbackService,
    CicytexFeedbackUnavailable,
)
from historical_replay.sessions import (
    ReplaySession,
    ReplaySessionNotFound,
    ReplaySessionService,
)

METHOD_ORDER = (
    "logistic_regression",
    "random_forest",
    "hist_gradient_boosting_classifier",
    "ensemble",
    "persistence",
)


class CicytexApplicationError(RuntimeError):
    """Base application error with no transport semantics."""


class CicytexCatalogUnavailable(CicytexApplicationError):
    pass


class CicytexSelectionUnavailable(CicytexApplicationError):
    pass


class CicytexEmissionNotFound(CicytexApplicationError):
    pass


class CicytexSessionNotFound(CicytexApplicationError):
    pass


class CicytexInvalidFeedbackState(CicytexApplicationError):
    pass


class CicytexFeedbackAlreadyExists(CicytexApplicationError):
    pass


class CicytexFeedbackNotRevealed(CicytexApplicationError):
    pass


class CicytexCatalogApplication:
    def __init__(self, query: GetReplayCatalog) -> None:
        self._query = query

    def catalog(self) -> dict:
        try:
            return self._query.execute().to_dict()
        except (OSError, ValueError):
            raise CicytexCatalogUnavailable from None


class CicytexReplayApplication:
    def __init__(
        self,
        frames: tuple[pd.DataFrame, pd.DataFrame],
        sessions: ReplaySessionService,
        feedback: CicytexFeedbackService,
    ) -> None:
        self._frames = frames
        self._sessions = sessions
        self._feedback = feedback

    def create_session(self, *, sensor_id: str, emission_date: date, horizon_days: int) -> dict:
        predictions, _ = self._frames
        valid = predictions.loc[
            (predictions["sensor_id"] == sensor_id)
            & (predictions["emission_date"].dt.date == emission_date)
            & (predictions["horizon_days"] == horizon_days)
        ]
        if valid.empty:
            raise CicytexSelectionUnavailable
        session = self._sessions.create(
            sensor_id=sensor_id,
            emission_date=emission_date,
            horizon_days=horizon_days,
        )
        return self._render(session)

    def get_session(self, session_id: str) -> dict:
        try:
            return self._render(self._sessions.get(session_id))
        except ReplaySessionNotFound:
            raise CicytexSessionNotFound from None

    def advance_session(self, session_id: str) -> dict:
        try:
            return self._render(self._sessions.advance(session_id))
        except ReplaySessionNotFound:
            raise CicytexSessionNotFound from None

    def reset_session(self, session_id: str) -> dict:
        try:
            return self._render(self._sessions.reset(session_id))
        except ReplaySessionNotFound:
            raise CicytexSessionNotFound from None

    def _render(self, session: ReplaySession) -> dict:
        predictions, observations = self._frames
        sensor_predictions = predictions.loc[predictions["sensor_id"] == session.sensor_id].copy()
        selected = sensor_predictions.loc[
            (sensor_predictions["emission_date"].dt.date == session.emission_date)
            & (sensor_predictions["horizon_days"] == session.horizon_days)
        ]
        if selected.empty:
            raise CicytexEmissionNotFound
        reveal = pd.Timestamp(session.revealed_through)
        known = observations.loc[
            (observations["sensor_id"] == session.sensor_id) & (observations["timestamp"] <= reveal)
        ].sort_values("timestamp")
        predictions_view = []
        for _, row in selected.sort_values(
            "method",
            key=lambda column: column.map(
                {method: index for index, method in enumerate(METHOD_ORDER)}
            ),
        ).iterrows():
            target_revealed = pd.Timestamp(row["target_timestamp"]) <= reveal
            alert = str(row["alert"]).lower() in {"true", "1"}
            observed_label = int(row["observed_label"])
            predictions_view.append(
                {
                    "method": row["method"],
                    "score": float(row["score"]),
                    "alert": alert,
                    "target_date": _iso(row["target_timestamp"]),
                    "observed_soil_moisture": (
                        float(row["observed_soil_moisture"]) if target_revealed else None
                    ),
                    "observed_label": observed_label if target_revealed else None,
                    "outcome": (
                        (
                            ("VP" if observed_label else "FP")
                            if alert
                            else ("FN" if observed_label else "VN")
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
        stored = self._feedback.visible_for(session)
        return {
            "session_id": session.session_id,
            "sensor_id": session.sensor_id,
            "emission_date": session.emission_date.isoformat(),
            "horizon_days": session.horizon_days,
            "revealed_through": session.revealed_through.isoformat(),
            "threshold": float(selected.iloc[0]["event_threshold"]),
            "proxy_notice": (
                "P20 estimado solo con entrenamiento; no es estres fisiologico observado."
            ),
            "predictions": predictions_view,
            "readings": [
                {"date": _iso(row.timestamp), "soil_moisture": float(row.soil_moisture)}
                for row in known.itertuples()
            ],
            "metrics": metrics,
            "feedback": stored.to_public_dict() if stored is not None else None,
            "can_advance": session.can_advance,
        }


class CicytexFeedbackApplication:
    def __init__(
        self,
        sessions: ReplaySessionService,
        feedback: CicytexFeedbackService,
    ) -> None:
        self._sessions = sessions
        self._feedback = feedback

    def create_feedback(
        self,
        session_id: str,
        *,
        estado_validacion: str,
        etiqueta_corregida: int | None,
        observacion: str | None,
    ) -> dict:
        if estado_validacion not in {"confirmada", "rechazada"}:
            raise CicytexInvalidFeedbackState
        try:
            self._sessions.with_session(session_id, lambda _session: True)
        except ReplaySessionNotFound:
            raise CicytexSessionNotFound from None
        try:
            return self._feedback.register(
                session_id,
                estado_validacion=estado_validacion,
                etiqueta_corregida=etiqueta_corregida,
                observacion=observacion,
            ).to_public_dict()
        except CicytexFeedbackConflict:
            raise CicytexFeedbackAlreadyExists from None
        except CicytexFeedbackUnavailable:
            raise CicytexFeedbackNotRevealed from None


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
    observed = rows["observed_label"].astype(int)
    predicted = rows["alert"].astype(str).str.lower().isin(["true", "1"]).astype(int)
    tp = int(((observed == 1) & (predicted == 1)).sum())
    tn = int(((observed == 0) & (predicted == 0)).sum())
    fp = int(((observed == 0) & (predicted == 1)).sum())
    fn = int(((observed == 1) & (predicted == 0)).sum())
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
