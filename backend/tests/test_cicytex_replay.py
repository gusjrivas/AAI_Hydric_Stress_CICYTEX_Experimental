from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier

import pandas as pd
import pytest
from app.dependencies import get_cicytex_replay_sessions
from app.main import app
from fastapi.testclient import TestClient

from historical_replay.adapters.in_memory_sessions import InMemorySessionRepository
from historical_replay.sessions import ReplaySessionService


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


@pytest.mark.parametrize("_repeat", range(2))
def test_future_is_blocked_until_session_clock_advances(tmp_path, monkeypatch, _repeat):
    _package(tmp_path)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(tmp_path / "feedback"))
    session_database = tmp_path / "sessions.sqlite3"
    monkeypatch.setenv("CICYTEX_REPLAY_SESSION_DB", str(session_database))
    monkeypatch.delenv("CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON", raising=False)
    app.dependency_overrides.clear()
    get_cicytex_replay_sessions.cache_clear()
    try:
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
            reset = client.post(f"/api/v2/cicytex/replay/sessions/{before['session_id']}/reset")
            assert reset.status_code == 200
            assert reset.json() == before
            assert all(row["observed_soil_moisture"] is None for row in reset.json()["predictions"])
            advanced = client.post(
                f"/api/v2/cicytex/replay/sessions/{before['session_id']}/advance"
            ).json()
            registered = client.post(
                f"/api/v2/cicytex/replay/sessions/{before['session_id']}/feedback",
                json={
                    "estado_validacion": "confirmada",
                    "observacion": "Revisado en defensa",
                },
            )
            assert registered.status_code == 201
            refreshed = client.get(f"/api/v2/cicytex/replay/sessions/{before['session_id']}").json()
            assert refreshed["feedback"]["estado_validacion"] == "confirmada"
            assert refreshed["feedback"]["scope"] == ("demostracion; no recalibra ni reentrena")
    finally:
        get_cicytex_replay_sessions.cache_clear()
        app.dependency_overrides.clear()
    assert session_database.is_file()


def test_unrevealed_prediction_does_not_read_missing_future_outcome(tmp_path, monkeypatch):
    _package(tmp_path)
    predictions_path = tmp_path / "predictions.csv"
    predictions = pd.read_csv(predictions_path)
    predictions["observed_soil_moisture"] = pd.NA
    predictions["observed_label"] = pd.NA
    predictions.to_csv(predictions_path, index=False)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("CICYTEX_REPLAY_SESSION_DB", str(tmp_path / "sessions.sqlite3"))
    monkeypatch.delenv("CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON", raising=False)
    app.dependency_overrides.clear()
    get_cicytex_replay_sessions.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v2/cicytex/replay/sessions",
                json={
                    "sensor_id": "CP1_S1",
                    "emission_date": "2023-07-06",
                    "horizon_days": 1,
                },
            )
    finally:
        get_cicytex_replay_sessions.cache_clear()
        app.dependency_overrides.clear()

    assert response.status_code == 201
    for prediction in response.json()["predictions"]:
        assert prediction["observed_soil_moisture"] is None
        assert prediction["observed_label"] is None
        assert prediction["outcome"] is None


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


def test_session_http_payload_and_status_contract_is_unchanged(tmp_path, monkeypatch):
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
        session_id = created.json()["session_id"]
        assert created.json() == {
            "session_id": session_id,
            "sensor_id": "CP1_S1",
            "emission_date": "2023-07-06",
            "horizon_days": 1,
            "revealed_through": "2023-07-06",
            "threshold": 0.21,
            "proxy_notice": (
                "P20 estimado solo con entrenamiento; no es estres fisiologico observado."
            ),
            "predictions": [
                {
                    "method": method,
                    "score": score,
                    "alert": alert,
                    "target_date": "2023-07-07",
                    "observed_soil_moisture": None,
                    "observed_label": None,
                    "outcome": None,
                }
                for method, score, alert in (
                    ("logistic_regression", 0.8, True),
                    ("random_forest", 0.4, False),
                    ("hist_gradient_boosting_classifier", 0.7, True),
                    ("ensemble", 0.633333333333, True),
                    ("persistence", 0.0, False),
                )
            ],
            "readings": [{"date": "2023-07-06", "soil_moisture": 0.25}],
            "metrics": {},
            "feedback": None,
            "can_advance": True,
        }

        fetched = client.get(f"/api/v2/cicytex/replay/sessions/{session_id}")
        advanced = client.post(f"/api/v2/cicytex/replay/sessions/{session_id}/advance")
        reset = client.post(f"/api/v2/cicytex/replay/sessions/{session_id}/reset")

    assert fetched.status_code == 200
    assert fetched.json() == created.json()
    assert advanced.status_code == 200
    assert advanced.json()["revealed_through"] == "2023-07-07"
    assert reset.status_code == 200
    assert reset.json() == created.json()


def test_missing_session_http_errors_are_unchanged(tmp_path, monkeypatch):
    _package(tmp_path)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))

    with TestClient(app) as client:
        responses = (
            client.get("/api/v2/cicytex/replay/sessions/missing-session"),
            client.post("/api/v2/cicytex/replay/sessions/missing-session/advance"),
            client.post("/api/v2/cicytex/replay/sessions/missing-session/reset"),
        )

    for response in responses:
        assert response.status_code == 404
        error = response.json()["error"]
        assert error["code"] == "resource_not_found"
        assert error["message"] == "Sesion inexistente"
        assert error["details"] == {}
        assert error["request_id"]


def test_feedback_revalidates_the_session_after_a_concurrent_reset(tmp_path, monkeypatch):
    _package(tmp_path)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))
    feedback_dir = tmp_path / "feedback"
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(feedback_dir))

    repository = InMemorySessionRepository()
    sessions = ReplaySessionService(
        repository,
        id_factory=lambda: "coordinated-session",
        last_observation=date(2023, 7, 7),
    )
    sessions.create(
        sensor_id="CP1_S1",
        emission_date=date(2023, 7, 6),
        horizon_days=1,
    )
    sessions.advance("coordinated-session")
    interleaving = Barrier(2, timeout=5)

    class CoordinatedSessions:
        def get(self, session_id):
            raise AssertionError("feedback must use the atomic session operation")

        def with_session(self, session_id, operation):
            interleaving.wait()
            interleaving.wait()
            return sessions.with_session(session_id, operation)

    app.dependency_overrides[get_cicytex_replay_sessions] = CoordinatedSessions
    try:
        with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
            response_future = pool.submit(
                client.post,
                "/api/v2/cicytex/replay/sessions/coordinated-session/feedback",
                json={"estado_validacion": "confirmada"},
            )
            interleaving.wait()
            reset = sessions.reset("coordinated-session")
            assert reset.revealed_through == date(2023, 7, 6)
            interleaving.wait()
            response = response_future.result(timeout=5)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["message"] == ("La observacion todavia no fue revelada")
    assert not (feedback_dir / "feedback.json").exists()


def test_can_advance_uses_the_injected_session_service_observation_limit(tmp_path, monkeypatch):
    _package(tmp_path)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(tmp_path / "feedback"))

    sessions = ReplaySessionService(
        InMemorySessionRepository(),
        id_factory=lambda: "bounded-session",
        last_observation=date(2023, 7, 7),
    )
    sessions.create(
        sensor_id="CP1_S1",
        emission_date=date(2023, 7, 6),
        horizon_days=1,
    )
    sessions.advance("bounded-session")
    app.dependency_overrides[get_cicytex_replay_sessions] = lambda: sessions
    try:
        with TestClient(app) as client:
            response = client.get("/api/v2/cicytex/replay/sessions/bounded-session")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["revealed_through"] == "2023-07-07"
    assert response.json()["can_advance"] is False
