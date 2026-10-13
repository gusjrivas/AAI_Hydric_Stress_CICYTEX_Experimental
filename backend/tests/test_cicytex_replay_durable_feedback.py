from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from app.dependencies import get_cicytex_replay_sessions
from app.main import app
from fastapi.testclient import TestClient


def _package(root: Path) -> None:
    predictions = [
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
        for method, score in (
            ("logistic_regression", 0.8),
            ("random_forest", 0.4),
            ("hist_gradient_boosting_classifier", 0.7),
            ("ensemble", 0.633333333333),
            ("persistence", 0.0),
        )
    ]
    pd.DataFrame(predictions).to_csv(root / "predictions.csv", index=False)
    pd.DataFrame(
        [
            {"sensor_id": "CP1_S1", "timestamp": "2023-07-06", "soil_moisture": 0.25},
            {"sensor_id": "CP1_S1", "timestamp": "2023-07-07", "soil_moisture": 0.18},
        ]
    ).to_csv(root / "observations.csv", index=False)


def _clear_dependencies() -> None:
    get_cicytex_replay_sessions.cache_clear()
    app.dependency_overrides.clear()


@pytest.fixture
def configured(tmp_path, monkeypatch):
    replay = tmp_path / "replay"
    replay.mkdir()
    _package(replay)
    database = tmp_path / "sessions-and-feedback.sqlite3"
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(replay))
    monkeypatch.setenv("CICYTEX_REPLAY_SESSION_DB", str(database))
    monkeypatch.delenv("CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON", raising=False)
    monkeypatch.delenv("CICYTEX_REPLAY_FEEDBACK_DIR", raising=False)
    _clear_dependencies()
    yield database
    _clear_dependencies()


def _create_and_reveal(client: TestClient) -> str:
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
    assert client.post(f"/api/v2/cicytex/replay/sessions/{session_id}/advance").status_code == 200
    return session_id


def test_http_feedback_contract_is_durable_and_duplicate_is_409(configured):
    with TestClient(app) as client:
        session_id = _create_and_reveal(client)
        payload = {
            "estado_validacion": "confirmada",
            "etiqueta_corregida": 1,
            "observacion": "Revisado en defensa",
        }
        created = client.post(
            f"/api/v2/cicytex/replay/sessions/{session_id}/feedback", json=payload
        )
        duplicate = client.post(
            f"/api/v2/cicytex/replay/sessions/{session_id}/feedback", json=payload
        )
    assert created.status_code == 201
    assert created.json() == {
        "estado_validacion": "confirmada",
        "etiqueta_corregida": 1,
        "observacion": "Revisado en defensa",
        "registered_at": created.json()["registered_at"],
        "simulated_at": "2023-07-07",
        "scope": "demostracion; no recalibra ni reentrena",
    }
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message"] == "Ya existe feedback para esta prediccion"
    with sqlite3.connect(configured) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cicytex_replay_feedback").fetchone() == (1,)
    assert not configured.parent.joinpath("replay/feedback/feedback.json").exists()

    _clear_dependencies()
    with TestClient(app) as restarted:
        restored = restarted.get(f"/api/v2/cicytex/replay/sessions/{session_id}")
    assert restored.status_code == 200
    assert restored.json()["feedback"] == created.json()


def test_reset_hides_but_does_not_delete_durable_cicytex_feedback(configured):
    with TestClient(app) as client:
        session_id = _create_and_reveal(client)
        assert (
            client.post(
                f"/api/v2/cicytex/replay/sessions/{session_id}/feedback",
                json={"estado_validacion": "confirmada"},
            ).status_code
            == 201
        )
        reset = client.post(f"/api/v2/cicytex/replay/sessions/{session_id}/reset")
        hidden = client.get(f"/api/v2/cicytex/replay/sessions/{session_id}")
        advanced = client.post(f"/api/v2/cicytex/replay/sessions/{session_id}/advance")

    assert reset.status_code == 200
    assert hidden.json()["feedback"] is None
    assert advanced.json()["feedback"]["estado_validacion"] == "confirmada"
    with sqlite3.connect(configured) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cicytex_replay_feedback").fetchone() == (1,)


def test_repository_failure_is_sanitized_503_for_feedback_read_and_write(configured):
    with TestClient(app) as client:
        session_id = _create_and_reveal(client)
        private_marker = "private-corrupt-feedback-marker"
        with sqlite3.connect(configured) as connection:
            connection.execute(
                "INSERT INTO cicytex_replay_feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "CP1_S1",
                    "2023-07-06",
                    1,
                    "confirmada",
                    1,
                    private_marker,
                    "not-a-timestamp",
                    "2023-07-07",
                    "demostracion; no recalibra ni reentrena",
                ),
            )
        responses = (
            client.get(f"/api/v2/cicytex/replay/sessions/{session_id}"),
            client.post(
                f"/api/v2/cicytex/replay/sessions/{session_id}/feedback",
                json={"estado_validacion": "confirmada"},
            ),
        )

    for response in responses:
        assert response.status_code == 503
        error = response.json()["error"]
        assert error["code"] == "http_error"
        assert error["message"] == "El almacenamiento de feedback CICYTEX no esta disponible"
        assert str(configured) not in response.text
        assert private_marker not in response.text
        assert "cicytex_replay_feedback" not in response.text


def test_invalid_legacy_import_returns_private_503_and_no_partial_rows(tmp_path, monkeypatch):
    replay = tmp_path / "replay"
    replay.mkdir()
    _package(replay)
    database = tmp_path / "private-sessions.sqlite3"
    legacy = tmp_path / "private-feedback.json"
    marker = "private-legacy-marker"
    legacy.write_text('{"broken":"' + marker + '"}', encoding="utf-8")
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(replay))
    monkeypatch.setenv("CICYTEX_REPLAY_SESSION_DB", str(database))
    monkeypatch.setenv("CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON", str(legacy))
    _clear_dependencies()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v2/cicytex/replay/sessions",
                json={
                    "sensor_id": "CP1_S1",
                    "emission_date": "2023-07-06",
                    "horizon_days": 1,
                },
            )
    finally:
        _clear_dependencies()

    assert response.status_code == 503
    assert response.json()["error"]["message"] == (
        "El almacenamiento de feedback CICYTEX no esta disponible"
    )
    assert str(database) not in response.text
    assert str(legacy) not in response.text
    assert marker not in response.text


def test_feedback_paths_are_dependency_owned_and_router_has_no_storage_policy():
    root = Path(__file__).parents[2]
    router_path = root / "backend/app/routers/cicytex_replay.py"
    router_source = router_path.read_text(encoding="utf-8")
    tree = ast.parse(router_source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)}

    for forbidden in ("sqlite3", "json", "pathlib", "os", "Lock"):
        assert forbidden not in imports
    for forbidden in (
        "CICYTEX_REPLAY_SESSION_DB",
        "CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON",
        "feedback.json",
    ):
        assert forbidden not in constants
    assert "_feedback_lock" not in router_source
    assert "_read_feedback_document" not in router_source
    assert "_write_feedback_document" not in router_source


def test_historical_feedback_sqlite_path_is_an_administrator_dependency(tmp_path, monkeypatch):
    from app.config import get_historical_replay_feedback_database

    expected = tmp_path / "historical-feedback.sqlite3"
    monkeypatch.setenv("HISTORICAL_REPLAY_FEEDBACK_DB", str(expected))
    assert get_historical_replay_feedback_database() == expected

    root = Path(__file__).parents[2]
    dependency_source = (root / "backend/app/dependencies.py").read_text(encoding="utf-8")
    router_source = (root / "backend/app/routers/replay.py").read_text(encoding="utf-8")
    assert "SQLiteReplayFeedbackStore" in dependency_source
    assert "HISTORICAL_REPLAY_FEEDBACK_DB" not in router_source
    assert "sqlite3" not in router_source
