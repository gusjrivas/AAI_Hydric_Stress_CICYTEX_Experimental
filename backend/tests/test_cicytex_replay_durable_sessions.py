from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pandas as pd
import pathspec
from app.config import get_cicytex_replay_session_database
from app.dependencies import get_cicytex_replay_sessions
from app.main import app
from fastapi.testclient import TestClient


def _package(root: Path) -> None:
    pd.DataFrame(
        [
            {
                "sensor_id": "CP1_S1",
                "emission_date": "2023-07-06",
                "target_timestamp": "2023-07-07",
                "soil_moisture": 0.25,
                "observed_soil_moisture": 0.18,
                "observed_label": 1,
                "event_threshold": 0.21,
                "method": "ensemble",
                "score": 0.8,
                "alert": True,
                "horizon_days": 1,
            }
        ]
    ).to_csv(root / "predictions.csv", index=False)
    pd.DataFrame(
        [
            {"sensor_id": "CP1_S1", "timestamp": "2023-07-06", "soil_moisture": 0.25},
            {"sensor_id": "CP1_S1", "timestamp": "2023-07-07", "soil_moisture": 0.18},
        ]
    ).to_csv(root / "observations.csv", index=False)


def _clear_session_dependency() -> None:
    assert hasattr(get_cicytex_replay_sessions, "cache_clear")
    get_cicytex_replay_sessions.cache_clear()


def test_http_session_survives_dependency_restart_at_overridden_path(tmp_path, monkeypatch):
    replay = tmp_path / "replay"
    replay.mkdir()
    _package(replay)
    database = tmp_path / "durable" / "sessions.sqlite3"
    database.parent.mkdir()
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(replay))
    monkeypatch.setenv("CICYTEX_REPLAY_SESSION_DB", str(database))
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(tmp_path / "feedback"))
    _clear_session_dependency()
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
            session_id = created.json()["session_id"]
            advanced = client.post(f"/api/v2/cicytex/replay/sessions/{session_id}/advance")
            assert advanced.status_code == 200
        assert database.is_file()

        _clear_session_dependency()
        with TestClient(app) as restarted_client:
            restored = restarted_client.get(f"/api/v2/cicytex/replay/sessions/{session_id}")
        assert restored.status_code == 200
        assert restored.json() == advanced.json()
    finally:
        _clear_session_dependency()


def test_corrupt_store_returns_sanitized_503_without_in_memory_fallback(tmp_path, monkeypatch):
    replay = tmp_path / "replay"
    replay.mkdir()
    _package(replay)
    database = tmp_path / "private-store-name.sqlite3"
    private_marker = "private-corrupt-session-store-marker"
    database.write_text(private_marker, encoding="utf-8")
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(replay))
    monkeypatch.setenv("CICYTEX_REPLAY_SESSION_DB", str(database))
    _clear_session_dependency()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v2/cicytex/replay/sessions/any-session")
    finally:
        _clear_session_dependency()

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "http_error"
    assert error["message"] == "El almacenamiento de sesiones CICYTEX no esta disponible"
    rendered = response.text
    assert str(database) not in rendered
    assert private_marker not in rendered


def test_post_bootstrap_corrupt_row_returns_private_503_for_advance_and_feedback(
    tmp_path, monkeypatch
):
    replay = tmp_path / "replay"
    replay.mkdir()
    _package(replay)
    database = tmp_path / "private-store-name.sqlite3"
    private_marker = "private-corrupt-row-marker"
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(replay))
    monkeypatch.setenv("CICYTEX_REPLAY_SESSION_DB", str(database))
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(tmp_path / "feedback"))
    _clear_session_dependency()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
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
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "UPDATE replay_sessions SET start_date = ? WHERE session_id = ?",
                    (private_marker, session_id),
                )
            responses = (
                client.post(f"/api/v2/cicytex/replay/sessions/{session_id}/advance"),
                client.post(
                    f"/api/v2/cicytex/replay/sessions/{session_id}/feedback",
                    json={"estado_validacion": "confirmada"},
                ),
            )
    finally:
        _clear_session_dependency()

    for response in responses:
        assert response.status_code == 503
        error = response.json()["error"]
        assert error["code"] == "http_error"
        assert error["message"] == ("El almacenamiento de sesiones CICYTEX no esta disponible")
        rendered = response.text
        assert str(database) not in rendered
        assert private_marker not in rendered
        assert "replay_sessions" not in rendered


def test_session_database_override_isolates_scenarios(tmp_path, monkeypatch):
    replay = tmp_path / "replay"
    replay.mkdir()
    _package(replay)
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(replay))
    monkeypatch.setenv("CICYTEX_REPLAY_FEEDBACK_DIR", str(tmp_path / "feedback"))
    first_database = tmp_path / "first.sqlite3"
    second_database = tmp_path / "second.sqlite3"

    monkeypatch.setenv("CICYTEX_REPLAY_SESSION_DB", str(first_database))
    _clear_session_dependency()
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

        monkeypatch.setenv("CICYTEX_REPLAY_SESSION_DB", str(second_database))
        _clear_session_dependency()
        with TestClient(app) as isolated_client:
            missing = isolated_client.get(
                f"/api/v2/cicytex/replay/sessions/{created.json()['session_id']}"
            )
        assert missing.status_code == 404
        assert first_database.is_file()
        assert second_database.is_file()
    finally:
        _clear_session_dependency()


def test_router_has_no_sqlite_or_session_store_path_policy():
    repository = Path(__file__).parents[2]
    router = repository / "backend" / "app" / "routers" / "cicytex_replay.py"
    tree = ast.parse(router.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)}

    assert "sqlite3" not in imports
    assert "SQLiteSessionRepository" not in imports
    assert "CICYTEX_REPLAY_SESSION_DB" not in constants


def test_default_bootstrap_lock_is_ignored_by_git(monkeypatch):
    monkeypatch.delenv("CICYTEX_REPLAY_SESSION_DB", raising=False)
    repository = Path(__file__).parents[2]
    database = get_cicytex_replay_session_database()
    bootstrap_lock = database.with_name(f".{database.name}.bootstrap.lock")
    relative_lock = bootstrap_lock.relative_to(repository).as_posix()
    assert relative_lock == ("data/.cicytex_replay_sessions.sqlite3.bootstrap.lock")

    ignore_spec = pathspec.GitIgnoreSpec.from_lines(
        (repository / ".gitignore").read_text(encoding="utf-8").splitlines(),
    )
    assert ignore_spec.match_file(relative_lock)
