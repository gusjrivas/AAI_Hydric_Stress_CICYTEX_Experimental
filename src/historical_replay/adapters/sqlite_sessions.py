"""Durable SQLite adapter for replay sessions.

The adapter owns the database lifecycle and translates every storage failure
to a deliberately opaque error.  Domain transitions remain in
``ReplaySession`` and are executed while the write transaction is held.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import TypeVar

from data_ingestion.storage import StorageLockTimeout, interprocess_lock
from historical_replay.sessions import ReplaySession, ReplaySessionConflict

T = TypeVar("T")

_SCHEMA_VERSION = 1
_DEFAULT_BUSY_TIMEOUT_MS = 5_000
_REPOSITORY_ERROR = "replay session store is unavailable"
_METADATA_DDL = """CREATE TABLE replay_session_metadata (
                           key TEXT PRIMARY KEY NOT NULL,
                           value TEXT NOT NULL
                       ) WITHOUT ROWID"""
_SESSION_DDL = """CREATE TABLE replay_sessions (
                           session_id TEXT PRIMARY KEY NOT NULL,
                           sensor_id TEXT NOT NULL,
                           start_date TEXT NOT NULL,
                           emission_date TEXT NOT NULL,
                           horizon_days INTEGER NOT NULL,
                           revealed_through TEXT NOT NULL,
                           last_observation TEXT NOT NULL
                       ) WITHOUT ROWID"""
_SESSION_COLUMNS = (
    "session_id",
    "sensor_id",
    "start_date",
    "emission_date",
    "horizon_days",
    "revealed_through",
    "last_observation",
)
_METADATA_SCHEMA = (
    ("key", "TEXT", 1, None, 1),
    ("value", "TEXT", 1, None, 0),
)
_SESSION_SCHEMA = (
    ("session_id", "TEXT", 1, None, 1),
    ("sensor_id", "TEXT", 1, None, 0),
    ("start_date", "TEXT", 1, None, 0),
    ("emission_date", "TEXT", 1, None, 0),
    ("horizon_days", "INTEGER", 1, None, 0),
    ("revealed_through", "TEXT", 1, None, 0),
    ("last_observation", "TEXT", 1, None, 0),
)


class SQLiteSessionRepositoryError(RuntimeError):
    """A private SQLite storage failure occurred."""


class SQLiteSessionRepository:
    """Process-safe implementation of the replay-session repository port."""

    def __init__(self, database: Path, *, busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS) -> None:
        if not isinstance(database, Path):
            raise TypeError("database must be a Path")
        if type(busy_timeout_ms) is not int or not 1 <= busy_timeout_ms <= 60_000:
            raise ValueError("busy_timeout_ms must be an integer between 1 and 60000")
        self._database = database
        self._busy_timeout_ms = busy_timeout_ms
        self._bootstrap_or_validate()

    def add(self, session: ReplaySession) -> None:
        if type(session) is not ReplaySession:
            raise TypeError("session must be a ReplaySession")
        connection = self._open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO replay_sessions (
                           session_id, sensor_id, start_date, emission_date,
                           horizon_days, revealed_through, last_observation
                       ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    self._encode(session),
                )
            except sqlite3.IntegrityError:
                connection.rollback()
                raise ReplaySessionConflict(session.session_id) from None
            connection.commit()
        except ReplaySessionConflict:
            raise
        except sqlite3.Error:
            self._rollback(connection)
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None
        finally:
            connection.close()

    def get(self, session_id: str) -> ReplaySession | None:
        self._validate_session_id(session_id)
        connection = self._open()
        try:
            row = connection.execute(
                """SELECT session_id, sensor_id, start_date, emission_date,
                          horizon_days, revealed_through, last_observation
                   FROM replay_sessions WHERE session_id = ?""",
                (session_id,),
            ).fetchone()
            return None if row is None else self._decode(row)
        except (sqlite3.Error, TypeError, ValueError):
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None
        finally:
            connection.close()

    def update(
        self,
        session_id: str,
        transition: Callable[[ReplaySession], ReplaySession],
    ) -> ReplaySession | None:
        self._validate_session_id(session_id)
        if not callable(transition):
            raise TypeError("transition must be callable")
        connection = self._open()
        try:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._select(connection, session_id)
                if row is None:
                    connection.commit()
                    return None
                current = self._decode_persisted(row)
            except SQLiteSessionRepositoryError:
                self._rollback(connection)
                raise
            except sqlite3.Error:
                self._rollback(connection)
                raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

            try:
                updated = transition(current)
            except BaseException:
                self._rollback(connection)
                raise

            try:
                if type(updated) is not ReplaySession or updated.session_id != current.session_id:
                    raise ValueError("transition must preserve the replay session identity")
                cursor = connection.execute(
                    """UPDATE replay_sessions
                       SET sensor_id = ?, start_date = ?, emission_date = ?,
                           horizon_days = ?, revealed_through = ?, last_observation = ?
                       WHERE session_id = ? AND sensor_id = ? AND start_date = ?
                         AND emission_date = ? AND horizon_days = ?
                         AND revealed_through = ? AND last_observation = ?""",
                    self._encode_update(updated, current),
                )
                if cursor.rowcount != 1:
                    raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
                connection.commit()
                return updated
            except SQLiteSessionRepositoryError:
                self._rollback(connection)
                raise
            except sqlite3.Error:
                self._rollback(connection)
                raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None
        finally:
            connection.close()

    def with_session(
        self,
        session_id: str,
        operation: Callable[[ReplaySession], T],
    ) -> T | None:
        self._validate_session_id(session_id)
        if not callable(operation):
            raise TypeError("operation must be callable")
        connection = self._open()
        try:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._select(connection, session_id)
                if row is None:
                    connection.commit()
                    return None
                session = self._decode_persisted(row)
            except SQLiteSessionRepositoryError:
                self._rollback(connection)
                raise
            except sqlite3.Error:
                self._rollback(connection)
                raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

            try:
                result = operation(session)
            except BaseException:
                self._rollback(connection)
                raise

            try:
                connection.commit()
                return result
            except sqlite3.Error:
                self._rollback(connection)
                raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None
        finally:
            connection.close()

    def _bootstrap_or_validate(self) -> None:
        lock_path = self._database.with_name(f".{self._database.name}.bootstrap.lock")
        try:
            with interprocess_lock(lock_path, timeout=self._busy_timeout_ms / 1_000):
                if self._database.exists():
                    self._validate_existing()
                else:
                    self._initialize()
        except SQLiteSessionRepositoryError:
            raise
        except (OSError, sqlite3.Error, StorageLockTimeout):
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

    def _initialize(self) -> None:
        self._database.parent.mkdir(parents=True, exist_ok=True)
        try:
            with closing(
                sqlite3.connect(
                    self._database,
                    timeout=self._busy_timeout_ms / 1_000,
                    isolation_level=None,
                )
            ) as connection:
                connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(_METADATA_DDL)
                connection.execute(_SESSION_DDL)
                connection.execute(
                    "INSERT INTO replay_session_metadata(key, value) VALUES ('schema_version', '1')"
                )
                connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                connection.commit()
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = FULL")
        except sqlite3.Error:
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

    def _validate_existing(self) -> None:
        if not self._database.is_file() or self._database.stat().st_size == 0:
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
        try:
            uri = f"{self._database.resolve().as_uri()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, isolation_level=None)) as connection:
                if connection.execute("PRAGMA user_version").fetchone() != (_SCHEMA_VERSION,):
                    raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
                schema_objects = tuple(
                    row for row in connection.execute("""SELECT type, name, tbl_name, sql
                           FROM sqlite_master
                           ORDER BY type, name""")
                )
                if schema_objects != (
                    (
                        "table",
                        "replay_session_metadata",
                        "replay_session_metadata",
                        _METADATA_DDL,
                    ),
                    ("table", "replay_sessions", "replay_sessions", _SESSION_DDL),
                ):
                    raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
                metadata = connection.execute(
                    "SELECT key, value FROM replay_session_metadata"
                ).fetchall()
                if metadata != [("schema_version", "1")]:
                    raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
                metadata_schema = tuple(
                    row[1:6]
                    for row in connection.execute("PRAGMA table_info(replay_session_metadata)")
                )
                session_schema = tuple(
                    row[1:6] for row in connection.execute("PRAGMA table_info(replay_sessions)")
                )
                if metadata_schema != _METADATA_SCHEMA or session_schema != _SESSION_SCHEMA:
                    raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
                for row in connection.execute(
                    """SELECT session_id, sensor_id, start_date, emission_date,
                              horizon_days, revealed_through, last_observation
                       FROM replay_sessions"""
                ):
                    self._decode(row)
                if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
        except SQLiteSessionRepositoryError:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError):
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

    def _open(self) -> sqlite3.Connection:
        try:
            uri = f"{self._database.resolve().as_uri()}?mode=rw"
            connection = sqlite3.connect(
                uri,
                uri=True,
                timeout=self._busy_timeout_ms / 1_000,
                isolation_level=None,
            )
            connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
            if connection.execute("PRAGMA journal_mode = WAL").fetchone() != ("wal",):
                raise sqlite3.OperationalError("journal mode unavailable")
            connection.execute("PRAGMA synchronous = FULL")
            return connection
        except sqlite3.Error:
            try:
                connection.close()
            except (UnboundLocalError, sqlite3.Error):
                pass
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

    @staticmethod
    def _select(connection: sqlite3.Connection, session_id: str) -> tuple | None:
        return connection.execute(
            """SELECT session_id, sensor_id, start_date, emission_date,
                      horizon_days, revealed_through, last_observation
               FROM replay_sessions WHERE session_id = ?""",
            (session_id,),
        ).fetchone()

    @staticmethod
    def _encode(session: ReplaySession) -> tuple[str, str, str, str, int, str, str]:
        return (
            session.session_id,
            session.sensor_id,
            session.start_date.isoformat(),
            session.emission_date.isoformat(),
            session.horizon_days,
            session.revealed_through.isoformat(),
            session.last_observation.isoformat(),
        )

    @classmethod
    def _encode_update(cls, updated: ReplaySession, current: ReplaySession) -> tuple:
        new = cls._encode(updated)
        old = cls._encode(current)
        return (*new[1:], *old)

    @staticmethod
    def _decode(row: tuple) -> ReplaySession:
        if len(row) != len(_SESSION_COLUMNS):
            raise ValueError("invalid persisted replay session")
        return ReplaySession(
            session_id=row[0],
            sensor_id=row[1],
            start_date=SQLiteSessionRepository._decode_date(row[2]),
            emission_date=SQLiteSessionRepository._decode_date(row[3]),
            horizon_days=row[4],
            revealed_through=SQLiteSessionRepository._decode_date(row[5]),
            last_observation=SQLiteSessionRepository._decode_date(row[6]),
        )

    @classmethod
    def _decode_persisted(cls, row: tuple) -> ReplaySession:
        try:
            return cls._decode(row)
        except (TypeError, ValueError):
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

    @staticmethod
    def _decode_date(value: object) -> date:
        if type(value) is not str:
            raise ValueError("invalid persisted replay session")
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("invalid persisted replay session")
        return parsed

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        if type(session_id) is not str or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass
