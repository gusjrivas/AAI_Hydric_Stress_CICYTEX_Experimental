from __future__ import annotations

import hashlib
import json
import multiprocessing
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from historical_replay.adapters.sqlite_sessions import SQLiteSessionRepository
from historical_replay.sessions import ReplaySession, ReplaySessionService


def _api():
    from historical_replay.adapters.sqlite_sessions import SQLiteCicytexFeedbackRepository
    from historical_replay.cicytex_feedback import (
        CicytexFeedbackConflict,
        CicytexFeedbackRecord,
        CicytexFeedbackRepositoryError,
        CicytexFeedbackService,
        CicytexFeedbackUnavailable,
    )

    return {
        "adapter": SQLiteCicytexFeedbackRepository,
        "conflict": CicytexFeedbackConflict,
        "record": CicytexFeedbackRecord,
        "repository_error": CicytexFeedbackRepositoryError,
        "service": CicytexFeedbackService,
        "unavailable": CicytexFeedbackUnavailable,
    }


def _session(
    session_id: str = "session-1",
    *,
    sensor_id: str = "CP1_S1",
    emission_date: date = date(2023, 7, 6),
    horizon_days: int = 1,
    revealed: date = date(2023, 7, 7),
):
    return ReplaySession(
        session_id=session_id,
        sensor_id=sensor_id,
        start_date=emission_date,
        emission_date=emission_date,
        horizon_days=horizon_days,
        revealed_through=revealed,
        last_observation=date(2023, 7, 25),
    )


def _create_v1(database: Path, *sessions: ReplaySession) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("""CREATE TABLE replay_session_metadata (
                   key TEXT PRIMARY KEY NOT NULL,
                   value TEXT NOT NULL
               ) WITHOUT ROWID""")
        connection.execute("""CREATE TABLE replay_sessions (
                   session_id TEXT PRIMARY KEY NOT NULL,
                   sensor_id TEXT NOT NULL,
                   start_date TEXT NOT NULL,
                   emission_date TEXT NOT NULL,
                   horizon_days INTEGER NOT NULL,
                   revealed_through TEXT NOT NULL,
                   last_observation TEXT NOT NULL
               ) WITHOUT ROWID""")
        connection.execute(
            "INSERT INTO replay_session_metadata(key, value) VALUES ('schema_version', '1')"
        )
        connection.execute("PRAGMA user_version = 1")
        connection.executemany(
            "INSERT INTO replay_sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item.session_id,
                    item.sensor_id,
                    item.start_date.isoformat(),
                    item.emission_date.isoformat(),
                    item.horizon_days,
                    item.revealed_through.isoformat(),
                    item.last_observation.isoformat(),
                )
                for item in sessions
            ],
        )


def _legacy_entry(
    *,
    sensor_id: str = "CP1_S1",
    emission_date: str = "2023-07-06",
    horizon_days: int = 1,
    simulated_at: str = "2023-07-07",
    observation: str = "Revisado",
) -> dict:
    return {
        f"{sensor_id}|{emission_date}|{horizon_days}": {
            "estado_validacion": "confirmada",
            "etiqueta_corregida": 1,
            "observacion": observation,
            "registered_at": "2026-10-12T10:00:00+00:00",
            "simulated_at": simulated_at,
            "scope": "demostracion; no recalibra ni reentrena",
        }
    }


def _record(api, *, observation: str = "Revisado"):
    return api["record"](
        sensor_id="CP1_S1",
        emission_date=date(2023, 7, 6),
        horizon_days=1,
        estado_validacion="confirmada",
        etiqueta_corregida=1,
        observacion=observation,
        registered_at="2026-10-12T10:00:00+00:00",
        simulated_at=date(2023, 7, 7),
        scope="demostracion; no recalibra ni reentrena",
    )


def _register_process(database: str, start, results) -> None:
    api = _api()
    try:
        repository = api["adapter"](Path(database))
        start.wait()
        stored = repository.register_for_session(
            "session-1", lambda _session: _record(api, observation="process")
        )
        results.put(("stored", stored.observacion))
    except api["conflict"]:
        results.put(("conflict", None))
    except api["unavailable"]:
        results.put(("unavailable", None))


def _reset_process(database: str, start, results) -> None:
    try:
        service = ReplaySessionService(
            SQLiteSessionRepository(Path(database)),
            id_factory=lambda: "unused",
            last_observation=date(2023, 7, 25),
        )
        start.wait()
        results.put(("reset", service.reset("session-1").revealed_through.isoformat()))
    except Exception as error:  # pragma: no cover - asserted in parent
        results.put(("error", type(error).__name__))


def _join(process) -> None:
    process.join(10)
    assert not process.is_alive()
    assert process.exitcode == 0


def test_v1_migrates_to_closed_v2_without_losing_sessions(tmp_path):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    expected = _session()
    _create_v1(database, expected)

    api["adapter"](database)

    assert SQLiteSessionRepository(database).get(expected.session_id) == expected
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        assert connection.execute(
            "SELECT value FROM replay_session_metadata WHERE key='schema_version'"
        ).fetchone() == ("2",)
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert tables == {
            "replay_session_metadata",
            "replay_sessions",
            "cicytex_replay_feedback",
        }
        assert [
            row[1] for row in connection.execute("PRAGMA table_info(cicytex_replay_feedback)")
        ] == [
            "sensor_id",
            "emission_date",
            "horizon_days",
            "estado_validacion",
            "etiqueta_corregida",
            "observacion",
            "registered_at",
            "simulated_at",
            "scope",
        ]


def test_valid_legacy_json_is_imported_once_and_digest_bound(tmp_path):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    legacy = tmp_path / "private-feedback.json"
    _create_v1(database, _session())
    raw = json.dumps(_legacy_entry(), ensure_ascii=False).encode()
    legacy.write_bytes(raw)

    repository = api["adapter"](database, legacy_feedback_path=legacy)
    assert repository.get("CP1_S1", date(2023, 7, 6), 1).observacion == "Revisado"
    with sqlite3.connect(database) as connection:
        metadata = dict(connection.execute("SELECT key, value FROM replay_session_metadata"))
    assert metadata["legacy_cicytex_feedback_sha256"] == hashlib.sha256(raw).hexdigest()

    restarted = api["adapter"](database, legacy_feedback_path=legacy)
    assert restarted.get("CP1_S1", date(2023, 7, 6), 1).observacion == "Revisado"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cicytex_replay_feedback").fetchone() == (1,)

    legacy.write_text(json.dumps(_legacy_entry(observation="private-changed")), encoding="utf-8")
    with pytest.raises(api["repository_error"]) as captured:
        api["adapter"](database, legacy_feedback_path=legacy)
    assert "private-changed" not in str(captured.value)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{",
        b'{"duplicate": 1, "duplicate": 2}',
        b'{"CP1_S1|2023-07-06|1":{"estado_validacion":"private-invalid"}}',
        b'{"private-foreign-key":{}}',
    ],
)
def test_invalid_legacy_json_aborts_migration_and_preserves_v1_session(tmp_path, raw):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    legacy = tmp_path / "private-feedback.json"
    expected = _session()
    _create_v1(database, expected)
    legacy.write_bytes(raw)

    with pytest.raises(api["repository_error"]) as captured:
        api["adapter"](database, legacy_feedback_path=legacy)
    assert str(database) not in str(captured.value)
    assert "private" not in str(captured.value)
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM replay_sessions").fetchone() == (1,)
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='cicytex_replay_feedback'"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    ("payload", "sessions", "private_marker"),
    [
        pytest.param(
            _legacy_entry(sensor_id="PRIVATE_FOREIGN_SENSOR", observation="private-foreign"),
            (
                _session("same-natural-key-one"),
                _session("same-natural-key-two", revealed=date(2023, 7, 8)),
                _session(
                    "other-natural-key",
                    sensor_id="CP2_S1",
                    emission_date=date(2023, 7, 8),
                    horizon_days=2,
                    revealed=date(2023, 7, 10),
                ),
            ),
            "private-foreign",
            id="no-session-has-the-natural-identity",
        ),
        pytest.param(
            _legacy_entry(simulated_at="2023-07-26", observation="private-after-observation"),
            (
                _session("matching-but-not-revealed-one"),
                _session("matching-but-not-revealed-two", revealed=date(2023, 7, 8)),
            ),
            "private-after-observation",
            id="simulated-at-is-after-last-observation",
        ),
    ],
)
def test_semantically_foreign_or_out_of_range_legacy_feedback_preserves_v1_bytes(
    tmp_path, payload, sessions, private_marker
):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    legacy = tmp_path / "private-feedback.json"
    _create_v1(database, *sessions)
    legacy.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    before = database.read_bytes()

    with pytest.raises(api["repository_error"]) as captured:
        api["adapter"](database, legacy_feedback_path=legacy)

    assert private_marker not in str(captured.value)
    assert str(database) not in str(captured.value)
    assert str(legacy) not in str(captured.value)
    assert database.read_bytes() == before
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        assert connection.execute(
            "SELECT value FROM replay_session_metadata WHERE key='schema_version'"
        ).fetchone() == ("1",)
        assert connection.execute("SELECT COUNT(*) FROM replay_sessions").fetchone() == (
            len(sessions),
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='cicytex_replay_feedback'"
        ).fetchone() == (0,)


def test_legacy_feedback_before_prediction_target_preserves_v1_bytes(tmp_path):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    legacy = tmp_path / "private-feedback.json"
    sessions = (
        _session("matching-reset", revealed=date(2023, 7, 6)),
        _session("matching-revealed", revealed=date(2023, 7, 8)),
    )
    _create_v1(database, *sessions)
    marker = "private-before-target"
    legacy.write_text(
        json.dumps(
            _legacy_entry(simulated_at="2023-07-06", observation=marker),
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    before = database.read_bytes()

    with pytest.raises(api["repository_error"]) as captured:
        api["adapter"](database, legacy_feedback_path=legacy)

    assert marker not in str(captured.value)
    assert database.read_bytes() == before
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='cicytex_replay_feedback'"
        ).fetchone() == (0,)


def test_mixed_valid_and_foreign_legacy_batch_rolls_back_every_record(tmp_path):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    legacy = tmp_path / "private-feedback.json"
    _create_v1(database, _session())
    marker = "private-mixed-foreign"
    payload = {
        **_legacy_entry(observation="valid-record-must-also-roll-back"),
        **_legacy_entry(sensor_id="PRIVATE_FOREIGN_SENSOR", observation=marker),
    }
    legacy.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    before = database.read_bytes()

    with pytest.raises(api["repository_error"]) as captured:
        api["adapter"](database, legacy_feedback_path=legacy)

    assert marker not in str(captured.value)
    assert "valid-record-must-also-roll-back" not in str(captured.value)
    assert database.read_bytes() == before
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='cicytex_replay_feedback'"
        ).fetchone() == (0,)


def test_reset_session_can_authorize_historical_legacy_simulated_at(tmp_path):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    legacy = tmp_path / "feedback.json"
    reset_session = _session("matching-reset", revealed=date(2023, 7, 6))
    _create_v1(database, reset_session)
    legacy.write_text(json.dumps(_legacy_entry(), separators=(",", ":")), encoding="utf-8")

    repository = api["adapter"](database, legacy_feedback_path=legacy)

    assert repository.get("CP1_S1", date(2023, 7, 6), 1).simulated_at == date(2023, 7, 7)
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM replay_sessions").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM cicytex_replay_feedback").fetchone() == (1,)


def test_legacy_import_cap_is_enforced_before_json_decode(tmp_path, monkeypatch):
    api = _api()
    module = __import__(
        "historical_replay.adapters.sqlite_sessions", fromlist=["_MAX_LEGACY_FEEDBACK_BYTES"]
    )
    database = tmp_path / "sessions.sqlite3"
    legacy = tmp_path / "feedback.json"
    _create_v1(database, _session())
    legacy.write_bytes(b" " * (module.MAX_CICYTEX_LEGACY_FEEDBACK_BYTES + 1))
    monkeypatch.setattr(json, "loads", lambda *_args, **_kwargs: pytest.fail("decoded oversized"))

    with pytest.raises(api["repository_error"]):
        api["adapter"](database, legacy_feedback_path=legacy)


def test_legacy_record_and_string_caps_fail_closed_without_logging(tmp_path, caplog):
    api = _api()
    module = __import__(
        "historical_replay.adapters.sqlite_sessions",
        fromlist=["MAX_CICYTEX_LEGACY_FEEDBACK_RECORDS"],
    )
    database = tmp_path / "sessions.sqlite3"
    legacy = tmp_path / "private-feedback.json"
    _create_v1(database, _session())
    marker = "private-legacy-observation-marker"
    payload = {
        f"CP1_S1|2023-07-{day:02d}|1": _legacy_entry(observation=marker)["CP1_S1|2023-07-06|1"]
        for day in range(1, module.MAX_CICYTEX_LEGACY_FEEDBACK_RECORDS + 2)
    }
    legacy.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(api["repository_error"]):
        api["adapter"](database, legacy_feedback_path=legacy)
    assert marker not in caplog.text


def test_natural_prediction_identity_is_unique_and_conflicts_without_overwrite(tmp_path):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    sessions = SQLiteSessionRepository(database)
    sessions.add(_session("first"))
    sessions.add(_session("second"))
    feedback = api["adapter"](database)

    first = feedback.register_for_session("first", lambda _session: _record(api))
    with pytest.raises(api["conflict"]):
        feedback.register_for_session(
            "second", lambda _session: _record(api, observation="must-not-overwrite")
        )
    assert feedback.get("CP1_S1", date(2023, 7, 6), 1) == first


def test_feedback_callback_exception_rolls_back_and_releases_database(tmp_path):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    SQLiteSessionRepository(database).add(_session())
    feedback = api["adapter"](database)

    with pytest.raises(RuntimeError, match="private-callback-marker"):
        feedback.register_for_session(
            "session-1",
            lambda _session: (_ for _ in ()).throw(RuntimeError("private-callback-marker")),
        )
    assert feedback.get("CP1_S1", date(2023, 7, 6), 1) is None
    assert feedback.register_for_session("session-1", lambda _session: _record(api))


def test_feedback_and_reset_are_linearizable_across_processes(tmp_path):
    api = _api()
    database = tmp_path / "sessions.sqlite3"
    SQLiteSessionRepository(database).add(_session())
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    processes = (
        context.Process(target=_register_process, args=(str(database), start, results)),
        context.Process(target=_reset_process, args=(str(database), start, results)),
    )
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        _join(process)

    outcomes = {results.get(timeout=2)[0], results.get(timeout=2)[0]}
    assert outcomes in ({"reset", "stored"}, {"reset", "unavailable"})
    stored = api["adapter"](database).get("CP1_S1", date(2023, 7, 6), 1)
    if stored is not None:
        assert stored.simulated_at == date(2023, 7, 7)
    assert SQLiteSessionRepository(database).get("session-1").revealed_through == date(2023, 7, 6)


def test_cicytex_feedback_domain_and_router_boundaries_are_pure():
    root = Path(__file__).parents[1]
    domain = (root / "src/historical_replay/cicytex_feedback.py").read_text(encoding="utf-8")
    router = (root / "backend/app/routers/cicytex_replay.py").read_text(encoding="utf-8")
    for forbidden in ("fastapi", "sqlite3", "pandas", "json", "pathlib", "os."):
        assert forbidden not in domain
    for forbidden in ("sqlite3", "json", "Path(", "CICYTEX_REPLAY_SESSION_DB", "Lock("):
        assert forbidden not in router
