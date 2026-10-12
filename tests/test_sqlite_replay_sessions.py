from __future__ import annotations

import multiprocessing
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from historical_replay.adapters.sqlite_sessions import (
    SQLiteSessionRepository,
    SQLiteSessionRepositoryError,
)

from historical_replay.sessions import (
    ReplaySession,
    ReplaySessionConflict,
    ReplaySessionService,
)


def _session(session_id: str = "session-1") -> ReplaySession:
    emission = date(2023, 7, 6)
    return ReplaySession(
        session_id=session_id,
        sensor_id="CP1_S1",
        start_date=emission,
        emission_date=emission,
        horizon_days=1,
        revealed_through=emission,
        last_observation=date(2023, 7, 25),
    )


def _advance_process(database: str, session_id: str, start, results) -> None:
    try:
        repository = SQLiteSessionRepository(Path(database))
        service = ReplaySessionService(
            repository,
            id_factory=lambda: "unused",
            last_observation=date(2023, 7, 25),
        )
        start.wait()
        results.put(("ok", service.advance(session_id).revealed_through.isoformat()))
    except Exception as error:  # pragma: no cover - asserted in parent process
        results.put(("error", type(error).__name__))


def _bootstrap_process(database: str, start, results) -> None:
    try:
        start.wait()
        SQLiteSessionRepository(Path(database))
        results.put("ok")
    except Exception as error:  # pragma: no cover - asserted in parent process
        results.put(type(error).__name__)


def _hold_session_process(database: str, entered, release, results) -> None:
    try:
        repository = SQLiteSessionRepository(Path(database))

        def hold(session):
            entered.set()
            if not release.wait(timeout=5):
                raise RuntimeError("release was not signalled")
            return session.revealed_through.isoformat()

        results.put(("held", repository.with_session("session-1", hold)))
    except Exception as error:  # pragma: no cover - asserted in parent process
        results.put(("error", type(error).__name__))


def _reset_process(database: str, started, completed, results) -> None:
    try:
        repository = SQLiteSessionRepository(Path(database))
        service = ReplaySessionService(
            repository,
            id_factory=lambda: "unused",
            last_observation=date(2023, 7, 25),
        )
        started.set()
        reset = service.reset("session-1")
        results.put(("reset", reset.revealed_through.isoformat()))
    except Exception as error:  # pragma: no cover - asserted in parent process
        results.put(("error", type(error).__name__))
    finally:
        completed.set()


def _join(process, *, timeout: float = 10) -> None:
    process.join(timeout)
    assert not process.is_alive(), f"child process did not finish: {process.pid}"
    assert process.exitcode == 0


def test_new_database_has_closed_v1_schema_and_metadata(tmp_path):
    database = tmp_path / "sessions.sqlite3"

    SQLiteSessionRepository(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert tables == {"replay_session_metadata", "replay_sessions"}
        assert connection.execute(
            "SELECT value FROM replay_session_metadata WHERE key = 'schema_version'"
        ).fetchone() == ("1",)
        assert [row[1] for row in connection.execute("PRAGMA table_info(replay_sessions)")] == [
            "session_id",
            "sensor_id",
            "start_date",
            "emission_date",
            "horizon_days",
            "revealed_through",
            "last_observation",
        ]


def test_session_survives_repository_restart_and_collision_is_closed(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    first = SQLiteSessionRepository(database)
    session = _session()
    first.add(session)

    restarted = SQLiteSessionRepository(database)
    assert restarted.get(session.session_id) == session
    with pytest.raises(ReplaySessionConflict):
        restarted.add(session)
    assert restarted.get(session.session_id) == session


@pytest.mark.parametrize("kind", ["empty", "corrupt", "foreign", "future", "partial"])
def test_invalid_existing_database_fails_closed_without_reinitializing(tmp_path, kind):
    database = tmp_path / f"{kind}.sqlite3"
    if kind == "empty":
        database.write_bytes(b"")
    elif kind == "corrupt":
        database.write_bytes(b"private-corrupt-sqlite-content")
    else:
        with sqlite3.connect(database) as connection:
            if kind == "foreign":
                connection.execute("CREATE TABLE unrelated(secret TEXT)")
            elif kind == "future":
                connection.execute("PRAGMA user_version = 2")
            else:
                connection.execute("PRAGMA user_version = 1")
                connection.execute("CREATE TABLE replay_session_metadata(key TEXT, value TEXT)")

    before = database.read_bytes()
    with pytest.raises(SQLiteSessionRepositoryError) as captured:
        SQLiteSessionRepository(database)
    assert database.read_bytes() == before
    assert str(database) not in str(captured.value)
    assert "private-corrupt-sqlite-content" not in str(captured.value)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("session_id", ""),
        ("sensor_id", ""),
        ("horizon_days", 0),
        ("revealed_through", "not-a-date"),
        ("last_observation", "2023-07-01"),
    ],
)
def test_invalid_persisted_row_fails_closed(tmp_path, column, value):
    database = tmp_path / "sessions.sqlite3"
    repository = SQLiteSessionRepository(database)
    repository.add(_session())
    with sqlite3.connect(database) as connection:
        connection.execute(
            f"UPDATE replay_sessions SET {column} = ? WHERE session_id = ?",
            (value, "session-1"),
        )

    with pytest.raises(SQLiteSessionRepositoryError):
        SQLiteSessionRepository(database).get("session-1")


def test_two_adapters_and_threads_do_not_lose_updates(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    SQLiteSessionRepository(database).add(_session())
    adapters = (SQLiteSessionRepository(database), SQLiteSessionRepository(database))

    def advance(repository):
        return repository.update("session-1", ReplaySession.advance)

    with ThreadPoolExecutor(max_workers=2) as pool:
        updates = [pool.submit(advance, adapter) for adapter in adapters]
        assert all(future.result(timeout=5) is not None for future in updates)

    assert SQLiteSessionRepository(database).get("session-1").revealed_through == date(2023, 7, 8)


def test_real_processes_do_not_lose_concurrent_updates(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    SQLiteSessionRepository(database).add(_session())
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    processes = [
        context.Process(
            target=_advance_process,
            args=(str(database), "session-1", start, results),
        )
        for _ in range(4)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        _join(process)

    assert [results.get(timeout=2)[0] for _ in processes] == ["ok"] * 4
    assert SQLiteSessionRepository(database).get("session-1").revealed_through == date(2023, 7, 10)


def test_with_session_blocks_interprocess_reset_until_callback_finishes(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    repository = SQLiteSessionRepository(database)
    repository.add(replace(_session(), revealed_through=date(2023, 7, 7)))
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    reset_started = context.Event()
    reset_completed = context.Event()
    results = context.Queue()
    holder = context.Process(
        target=_hold_session_process,
        args=(str(database), entered, release, results),
    )
    resetter = context.Process(
        target=_reset_process,
        args=(str(database), reset_started, reset_completed, results),
    )
    holder.start()
    assert entered.wait(timeout=5)
    resetter.start()
    assert reset_started.wait(timeout=5)
    assert not reset_completed.wait(timeout=0.2)
    release.set()
    _join(holder)
    _join(resetter)
    assert {results.get(timeout=2)[0], results.get(timeout=2)[0]} == {"held", "reset"}
    assert repository.get("session-1").revealed_through == date(2023, 7, 6)


def test_reset_winning_inverse_order_is_observed_by_with_session(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    repository = SQLiteSessionRepository(database)
    repository.add(replace(_session(), revealed_through=date(2023, 7, 7)))
    ReplaySessionService(
        SQLiteSessionRepository(database),
        id_factory=lambda: "unused",
        last_observation=date(2023, 7, 25),
    ).reset("session-1")

    observed = SQLiteSessionRepository(database).with_session(
        "session-1", lambda session: session.revealed_through
    )
    assert observed == date(2023, 7, 6)


def test_callback_exception_rolls_back_and_releases_transaction(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    first = SQLiteSessionRepository(database)
    first.add(replace(_session(), revealed_through=date(2023, 7, 7)))

    def explode(_session):
        raise RuntimeError("private-callback-marker")

    with pytest.raises(RuntimeError, match="private-callback-marker"):
        first.with_session("session-1", explode)
    second = SQLiteSessionRepository(database)
    assert second.update("session-1", ReplaySession.reset).revealed_through == date(2023, 7, 6)


def test_busy_database_raises_controlled_private_error_without_fallback(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    SQLiteSessionRepository(database).add(_session())
    blocker = sqlite3.connect(database)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        repository = SQLiteSessionRepository(database, busy_timeout_ms=25)
        with pytest.raises(SQLiteSessionRepositoryError) as captured:
            repository.update("session-1", ReplaySession.advance)
    finally:
        blocker.rollback()
        blocker.close()
    assert str(database) not in str(captured.value)
    assert SQLiteSessionRepository(database).get("session-1") == _session()


def test_concurrent_bootstrap_is_idempotent_and_complete(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    processes = [
        context.Process(
            target=_bootstrap_process,
            args=(str(database), start, results),
        )
        for _ in range(3)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        _join(process)
    assert [results.get(timeout=2) for _ in processes] == ["ok"] * 3
    assert SQLiteSessionRepository(database).get("missing") is None


def test_adapter_has_no_backend_router_or_feedback_dependency():
    source = (
        Path(__file__).parents[1] / "src" / "historical_replay" / "adapters" / "sqlite_sessions.py"
    ).read_text(encoding="utf-8")
    assert "backend" not in source
    assert "fastapi" not in source
    assert "feedback" not in source
