from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app


def _package(root: Path) -> None:
    predictions = []
    for method, score in {
        "logistic_regression": 0.8,
        "random_forest": 0.4,
        "hist_gradient_boosting_classifier": 0.7,
        "ensemble": 0.633333333333,
        "persistence": 0.0,
    }.items():
        predictions.append({
            "sensor_id": "CP1_S1", "emission_date": "2023-07-06",
            "target_timestamp": "2023-07-07", "soil_moisture": 0.25,
            "observed_soil_moisture": 0.18, "observed_label": 1,
            "event_threshold": 0.21, "method": method, "score": score,
            "alert": score >= 0.5, "horizon_days": 1,
        })
    pd.DataFrame(predictions).to_csv(root / "predictions.csv", index=False)
    pd.DataFrame([
        {"sensor_id": "CP1_S1", "timestamp": "2023-07-06", "soil_moisture": 0.25},
        {"sensor_id": "CP1_S1", "timestamp": "2023-07-07", "soil_moisture": 0.18},
    ]).to_csv(root / "observations.csv", index=False)


def test_future_is_blocked_until_session_clock_advances(tmp_path, monkeypatch):
    _package(tmp_path)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(tmp_path / "feedback"))
    with TestClient(app) as client:
        created = client.post("/api/v2/cicytex/replay/sessions", json={
            "sensor_id": "CP1_S1", "emission_date": "2023-07-06", "horizon_days": 1,
        })
        assert created.status_code == 201
        before = created.json()
        assert before["readings"][-1]["date"] == "2023-07-06"
        assert all(row["observed_soil_moisture"] is None for row in before["predictions"])
        assert before["metrics"] == {}
        blocked = client.post(
            f"/api/v2/cicytex/replay/sessions/{before['session_id']}/feedback",
            json={"estado_validacion": "confirmada"},
        )
        assert blocked.status_code == 409

        advanced = client.post(
            f"/api/v2/cicytex/replay/sessions/{before['session_id']}/advance"
        ).json()
        assert advanced["readings"][-1]["date"] == "2023-07-07"
        assert all(row["observed_soil_moisture"] == 0.18 for row in advanced["predictions"])
        assert advanced["metrics"]["ensemble"]["tp"] == 1
        assert advanced["metrics"]["persistence"]["fn"] == 1
        registered = client.post(
            f"/api/v2/cicytex/replay/sessions/{before['session_id']}/feedback",
            json={"estado_validacion": "confirmada", "observacion": "Revisado en defensa"},
        )
        assert registered.status_code == 201
        refreshed = client.get(
            f"/api/v2/cicytex/replay/sessions/{before['session_id']}"
        ).json()
        assert refreshed["feedback"]["estado_validacion"] == "confirmada"
        assert refreshed["feedback"]["scope"] == "demostracion; no recalibra ni reentrena"


def test_rejects_non_archived_selection(tmp_path, monkeypatch):
    _package(tmp_path)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(tmp_path / "feedback"))
    with TestClient(app) as client:
        response = client.post("/api/v2/cicytex/replay/sessions", json={
            "sensor_id": "CP1_S1", "emission_date": "2023-07-05", "horizon_days": 1,
        })
    assert response.status_code == 422
