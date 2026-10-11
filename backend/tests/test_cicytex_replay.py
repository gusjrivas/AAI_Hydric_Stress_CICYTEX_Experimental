from __future__ import annotations

from pathlib import Path

import pandas as pd
from app.main import app
from fastapi.testclient import TestClient


def _package(root: Path) -> None:
    predictions = []
    for method, score in {
        "logistic_regression": 0.8,
        "random_forest": 0.4,
        "hist_gradient_boosting_classifier": 0.7,
        "ensemble": 0.633333333333,
        "persistence": 0.0,
    }.items():
        predictions.append(
            {
                "sensor_id": "CP1_S1",
                "emission_date": "2023-07-06",
                "target_timestamp": "2023-07-07",
                "soil_moisture": 0.25,
                "observed_soil_moisture": 0.18,
                "observed_label": 1,
                "event_threshold": 0.21,
                "method": method,
                "score": score,
                "alert": score >= 0.5,
                "horizon_days": 1,
            }
        )
    pd.DataFrame(predictions).to_csv(root / "predictions.csv", index=False)
    pd.DataFrame(
        [
            {"sensor_id": "CP1_S1", "timestamp": "2023-07-06", "soil_moisture": 0.25},
            {"sensor_id": "CP1_S1", "timestamp": "2023-07-07", "soil_moisture": 0.18},
        ]
    ).to_csv(root / "observations.csv", index=False)


def test_catalog_contract_is_stable_and_sorted(tmp_path, monkeypatch):
    predictions = pd.DataFrame(
        [
            {
                "sensor_id": sensor_id,
                "emission_date": emission_date,
                "target_timestamp": target_timestamp,
                "soil_moisture": 0.25,
                "observed_soil_moisture": 0.18,
                "observed_label": 1,
                "event_threshold": 0.21,
                "method": "ensemble",
                "score": 0.8,
                "alert": True,
                "horizon_days": horizon_days,
            }
            for sensor_id, emission_date, target_timestamp, horizon_days in (
                ("CP2_S1", "2023-07-07", "2023-07-09", 2),
                ("CP1_S2", "2023-07-06", "2023-07-07", 1),
                ("CP1_S1", "2023-07-07", "2023-07-10", 3),
                ("CP1_S1", "2023-07-06", "2023-07-08", 2),
            )
        ]
    )
    predictions.to_csv(tmp_path / "predictions.csv", index=False)
    pd.DataFrame(
        [{"sensor_id": "CP1_S1", "timestamp": "2023-07-06", "soil_moisture": 0.25}]
    ).to_csv(tmp_path / "observations.csv", index=False)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.get("/api/v2/cicytex/replay/catalog")

    assert response.status_code == 200
    assert response.json() == {
        "sensors": ["CP1_S1", "CP1_S2", "CP2_S1"],
        "emission_dates": ["2023-07-06", "2023-07-07"],
        "emission_dates_by_horizon": {
            "1": ["2023-07-06"],
            "2": ["2023-07-06", "2023-07-07"],
            "3": ["2023-07-07"],
        },
        "horizons": [1, 2, 3],
        "first_legitimate_emission": "2023-07-06",
        "last_observation": "2023-07-25",
    }


def test_catalog_returns_service_unavailable_when_package_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.get("/api/v2/cicytex/replay/catalog")

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "http_error"
    assert error["message"] == "El paquete causal CICYTEX no esta preparado"
    assert error["details"] == {}
    assert error["request_id"]


def test_catalog_returns_service_unavailable_when_package_is_malformed(tmp_path, monkeypatch):
    (tmp_path / "predictions.csv").write_text("not,the,expected,schema\n1,2,3\n", encoding="utf-8")
    (tmp_path / "observations.csv").write_text("timestamp\nnot-a-date\n", encoding="utf-8")
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.get("/api/v2/cicytex/replay/catalog")

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "http_error"
    assert error["message"] == "El paquete causal CICYTEX no esta preparado"
    assert error["details"] == {}
    assert error["request_id"]


def test_future_is_blocked_until_session_clock_advances(tmp_path, monkeypatch):
    _package(tmp_path)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(tmp_path / "feedback"))
    with TestClient(app) as client:
        created = client.post(
            "/api/v2/cicytex/replay/sessions",
            json={
                "sensor_id": "CP1_S1",
                "emission_date": "2023-07-06",
                "horizon_days": 1,
            },
        )
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
        refreshed = client.get(f"/api/v2/cicytex/replay/sessions/{before['session_id']}").json()
        assert refreshed["feedback"]["estado_validacion"] == "confirmada"
        assert refreshed["feedback"]["scope"] == "demostracion; no recalibra ni reentrena"


def test_rejects_non_archived_selection(tmp_path, monkeypatch):
    _package(tmp_path)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(tmp_path / "feedback"))
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/cicytex/replay/sessions",
            json={
                "sensor_id": "CP1_S1",
                "emission_date": "2023-07-05",
                "horizon_days": 1,
            },
        )
    assert response.status_code == 422
