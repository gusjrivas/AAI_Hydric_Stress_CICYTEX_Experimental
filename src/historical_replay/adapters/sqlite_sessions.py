"""Durable SQLite adapter for replay sessions.

The adapter owns the database lifecycle and translates every storage failure
to a deliberately opaque error.  Domain transitions remain in
``ReplaySession`` and are executed while the write transaction is held.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import TypeVar

from data_ingestion.storage import StorageLockTimeout, interprocess_lock
from historical_replay.cicytex_feedback import (
    CicytexFeedbackConflict,
    CicytexFeedbackRecord,
    CicytexFeedbackRepositoryError,
    CicytexFeedbackUnavailable,
)
from historical_replay.sessions import ReplaySession, ReplaySessionConflict

T = TypeVar("T")

MAX_CICYTEX_LEGACY_FEEDBACK_BYTES = 1_048_576
MAX_CICYTEX_LEGACY_FEEDBACK_RECORDS = 1_000

_SCHEMA_VERSION = 2
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
_CICYTEX_TABLE = "cicytex_replay_feedback"
_LEGACY_DIGEST_KEY = "legacy_cicytex_feedback_sha256"
_CICYTEX_FEEDBACK_DDL = f"""CREATE TABLE {_CICYTEX_TABLE} (
                           sensor_id TEXT NOT NULL,
                           emission_date TEXT NOT NULL,
                           horizon_days INTEGER NOT NULL,
                           estado_validacion TEXT NOT NULL,
                           etiqueta_corregida INTEGER,
                           observacion TEXT,
                           registered_at TEXT NOT NULL,
                           simulated_at TEXT NOT NULL,
                           scope TEXT NOT NULL,
                           PRIMARY KEY (sensor_id, emission_date, horizon_days)
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
                connection.execute(_CICYTEX_FEEDBACK_DDL)
                connection.execute(
                    "INSERT INTO replay_session_metadata(key, value) VALUES ('schema_version', '2')"
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
                expected_schema_objects = (
                    (
                        "table",
                        _CICYTEX_TABLE,
                        _CICYTEX_TABLE,
                        _CICYTEX_FEEDBACK_DDL,
                    ),
                    (
                        "table",
                        "replay_session_metadata",
                        "replay_session_metadata",
                        _METADATA_DDL,
                    ),
                    ("table", "replay_sessions", "replay_sessions", _SESSION_DDL),
                )
                if not _same_schema_objects(schema_objects, expected_schema_objects):
                    raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
                metadata = dict(
                    connection.execute("SELECT key, value FROM replay_session_metadata")
                )
                if metadata.get("schema_version") != "2" or not set(metadata) <= {
                    "schema_version",
                    _LEGACY_DIGEST_KEY,
                }:
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


_LEGACY_FIELDS = {
    "estado_validacion",
    "etiqueta_corregida",
    "observacion",
    "registered_at",
    "simulated_at",
    "scope",
}


def _strict_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _same_schema_objects(actual: tuple, expected: tuple) -> bool:
    if len(actual) != len(expected):
        return False
    for actual_row, expected_row in zip(actual, expected, strict=True):
        if actual_row[:3] != expected_row[:3]:
            return False
        if " ".join(actual_row[3].split()) != " ".join(expected_row[3].split()):
            return False
    return True


def _parse_cicytex_legacy(path: Path) -> tuple[bytes, tuple[CicytexFeedbackRecord, ...]]:
    try:
        size = path.stat().st_size
        if size <= 0 or size > MAX_CICYTEX_LEGACY_FEEDBACK_BYTES:
            raise ValueError("invalid legacy size")
        raw = path.read_bytes()
        if len(raw) != size:
            raise ValueError("invalid legacy size")
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_strict_json_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
        if type(payload) is not dict or len(payload) > MAX_CICYTEX_LEGACY_FEEDBACK_RECORDS:
            raise ValueError("invalid legacy document")
        records = []
        for key, value in payload.items():
            if type(key) is not str or len(key) > 300 or type(value) is not dict:
                raise ValueError("invalid legacy record")
            if set(value) != _LEGACY_FIELDS:
                raise ValueError("invalid legacy record")
            if any(type(item) is str and len(item) > 1_000 for item in value.values()):
                raise ValueError("invalid legacy string")
            parts = key.split("|")
            if len(parts) != 3:
                raise ValueError("invalid legacy identity")
            emission = date.fromisoformat(parts[1])
            horizon = int(parts[2])
            record = CicytexFeedbackRecord(
                sensor_id=parts[0],
                emission_date=emission,
                horizon_days=horizon,
                estado_validacion=value["estado_validacion"],
                etiqueta_corregida=value["etiqueta_corregida"],
                observacion=value["observacion"],
                registered_at=value["registered_at"],
                simulated_at=date.fromisoformat(value["simulated_at"]),
                scope=value["scope"],
            )
            if (
                f"{record.sensor_id}|{record.emission_date.isoformat()}|{record.horizon_days}"
                != key
            ):
                raise ValueError("invalid legacy identity")
            records.append(record)
        return raw, tuple(records)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None


class SQLiteCicytexFeedbackRepository:
    """Atomic session-bound review repository sharing the session database."""

    def __init__(
        self,
        database: Path,
        *,
        busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS,
        legacy_feedback_path: Path | None = None,
    ) -> None:
        if not isinstance(database, Path):
            raise TypeError("database must be a Path")
        if type(busy_timeout_ms) is not int or not 1 <= busy_timeout_ms <= 60_000:
            raise ValueError("busy_timeout_ms must be an integer between 1 and 60000")
        if legacy_feedback_path is not None and not isinstance(legacy_feedback_path, Path):
            raise TypeError("legacy path must be a Path")
        self._database = database
        self._busy_timeout_ms = busy_timeout_ms
        imported = (
            _parse_cicytex_legacy(legacy_feedback_path)
            if legacy_feedback_path is not None
            else None
        )
        self._bootstrap(imported)

    def register_for_session(
        self,
        session_id: str,
        factory: Callable[[ReplaySession], CicytexFeedbackRecord],
    ) -> CicytexFeedbackRecord:
        if type(session_id) is not str or not session_id or not callable(factory):
            raise TypeError("invalid review registration")
        connection = self._open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = SQLiteSessionRepository._select(connection, session_id)
            if row is None:
                raise CicytexFeedbackUnavailable("review session unavailable")
            try:
                session = SQLiteSessionRepository._decode(row)
            except (TypeError, ValueError):
                raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None
            try:
                record = factory(session)
            except BaseException:
                connection.rollback()
                raise
            if type(record) is not CicytexFeedbackRecord or (
                record.sensor_id,
                record.emission_date,
                record.horizon_days,
            ) != (session.sensor_id, session.emission_date, session.horizon_days):
                raise ValueError("review identity must match session")
            target = session.emission_date.toordinal() + session.horizon_days
            if (
                session.revealed_through.toordinal() < target
                or record.simulated_at != session.revealed_through
            ):
                raise CicytexFeedbackUnavailable("review outcome unavailable")
            existing = connection.execute(
                f"""SELECT sensor_id, emission_date, horizon_days, estado_validacion,
                          etiqueta_corregida, observacion, registered_at, simulated_at, scope
                   FROM {_CICYTEX_TABLE}
                   WHERE sensor_id=? AND emission_date=? AND horizon_days=?""",
                (
                    record.sensor_id,
                    record.emission_date.isoformat(),
                    record.horizon_days,
                ),
            ).fetchone()
            if existing is not None:
                try:
                    self._decode(existing)
                except (TypeError, ValueError):
                    raise CicytexFeedbackRepositoryError(
                        "cicytex review store unavailable"
                    ) from None
                raise CicytexFeedbackConflict("review already exists")
            try:
                connection.execute(
                    f"INSERT INTO {_CICYTEX_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    self._encode(record),
                )
            except sqlite3.IntegrityError:
                connection.rollback()
                raise CicytexFeedbackConflict("review already exists") from None
            connection.commit()
            return record
        except (CicytexFeedbackConflict, CicytexFeedbackUnavailable):
            connection.rollback()
            raise
        except CicytexFeedbackRepositoryError:
            connection.rollback()
            raise
        except sqlite3.Error:
            connection.rollback()
            raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None
        finally:
            connection.close()

    def get(
        self, sensor_id: str, emission_date: date, horizon_days: int
    ) -> CicytexFeedbackRecord | None:
        connection = self._open()
        try:
            row = connection.execute(
                f"""SELECT sensor_id, emission_date, horizon_days, estado_validacion,
                          etiqueta_corregida, observacion, registered_at, simulated_at, scope
                   FROM {_CICYTEX_TABLE}
                   WHERE sensor_id=? AND emission_date=? AND horizon_days=?""",
                (sensor_id, emission_date.isoformat(), horizon_days),
            ).fetchone()
            return None if row is None else self._decode(row)
        except (sqlite3.Error, TypeError, ValueError):
            raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None
        finally:
            connection.close()

    def _bootstrap(
        self,
        imported: tuple[bytes, tuple[CicytexFeedbackRecord, ...]] | None,
    ) -> None:
        lock = self._database.with_name(f".{self._database.name}.bootstrap.lock")
        try:
            with interprocess_lock(lock, timeout=self._busy_timeout_ms / 1_000):
                exists = self._database.exists()
                if not exists:
                    self._database.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(
                    self._database,
                    timeout=self._busy_timeout_ms / 1_000,
                    isolation_level=None,
                )
                importing_legacy = False
                try:
                    connection.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
                    connection.execute("BEGIN IMMEDIATE")
                    if exists:
                        version = connection.execute("PRAGMA user_version").fetchone()
                        if version == (1,):
                            self._validate_v1(connection)
                            if imported is not None:
                                self._validate_legacy_records(connection, imported[1])
                            connection.execute(_CICYTEX_FEEDBACK_DDL)
                            connection.execute(
                                "UPDATE replay_session_metadata "
                                "SET value='2' WHERE key='schema_version'"
                            )
                            connection.execute("PRAGMA user_version=2")
                        elif version == (2,):
                            self._validate_v2(connection)
                            if imported is not None:
                                self._validate_legacy_records(connection, imported[1])
                        else:
                            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
                    else:
                        if imported is not None and imported[1]:
                            raise CicytexFeedbackRepositoryError("cicytex review store unavailable")
                        connection.execute(_METADATA_DDL)
                        connection.execute(_SESSION_DDL)
                        connection.execute(_CICYTEX_FEEDBACK_DDL)
                        connection.execute(
                            "INSERT INTO replay_session_metadata(key, value) "
                            "VALUES ('schema_version', '2')"
                        )
                        connection.execute("PRAGMA user_version=2")
                    if imported is not None:
                        importing_legacy = True
                        self._import_on_connection(connection, *imported)
                        importing_legacy = False
                    connection.commit()
                except sqlite3.Error:
                    connection.rollback()
                    if importing_legacy:
                        raise CicytexFeedbackRepositoryError(
                            "cicytex review store unavailable"
                        ) from None
                    raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None
                except BaseException:
                    connection.rollback()
                    raise
                finally:
                    connection.close()
                self._enable_durability()
        except CicytexFeedbackRepositoryError:
            raise
        except SQLiteSessionRepositoryError:
            raise
        except (OSError, sqlite3.Error, StorageLockTimeout, TypeError, ValueError):
            raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None

    def _validate_v1(self, connection: sqlite3.Connection) -> None:
        try:
            objects = tuple(
                connection.execute(
                    "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
                )
            )
            expected = (
                (
                    "table",
                    "replay_session_metadata",
                    "replay_session_metadata",
                    _METADATA_DDL,
                ),
                ("table", "replay_sessions", "replay_sessions", _SESSION_DDL),
            )
            if not _same_schema_objects(objects, expected):
                raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
            if connection.execute("SELECT key,value FROM replay_session_metadata").fetchall() != [
                ("schema_version", "1")
            ]:
                raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
            self._validate_sessions(connection)
        except SQLiteSessionRepositoryError:
            raise
        except (sqlite3.Error, TypeError, ValueError):
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

    def _validate_v2(self, connection: sqlite3.Connection) -> None:
        try:
            objects = tuple(
                connection.execute(
                    "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
                )
            )
            expected = (
                ("table", _CICYTEX_TABLE, _CICYTEX_TABLE, _CICYTEX_FEEDBACK_DDL),
                (
                    "table",
                    "replay_session_metadata",
                    "replay_session_metadata",
                    _METADATA_DDL,
                ),
                ("table", "replay_sessions", "replay_sessions", _SESSION_DDL),
            )
            if not _same_schema_objects(objects, expected):
                raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
            metadata = dict(connection.execute("SELECT key,value FROM replay_session_metadata"))
            if metadata.get("schema_version") != "2" or not set(metadata) <= {
                "schema_version",
                _LEGACY_DIGEST_KEY,
            }:
                raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
            self._validate_sessions(connection)
        except SQLiteSessionRepositoryError:
            raise
        except (sqlite3.Error, TypeError, ValueError):
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

        try:
            for row in connection.execute(
                f"""SELECT sensor_id, emission_date, horizon_days, estado_validacion,
                           etiqueta_corregida, observacion, registered_at, simulated_at, scope
                    FROM {_CICYTEX_TABLE}"""
            ):
                self._decode(row)
        except (sqlite3.Error, TypeError, ValueError):
            raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None

        try:
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
        except SQLiteSessionRepositoryError:
            raise
        except sqlite3.Error:
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR) from None

    @staticmethod
    def _validate_legacy_records(
        connection: sqlite3.Connection,
        records: tuple[CicytexFeedbackRecord, ...],
    ) -> None:
        try:
            for record in records:
                target = date.fromordinal(record.emission_date.toordinal() + record.horizon_days)
                if record.simulated_at < target:
                    raise CicytexFeedbackRepositoryError("cicytex review store unavailable")
                matching_limits = tuple(
                    row[0]
                    for row in connection.execute(
                        """SELECT last_observation
                           FROM replay_sessions
                           WHERE sensor_id=? AND emission_date=? AND horizon_days=?""",
                        (
                            record.sensor_id,
                            record.emission_date.isoformat(),
                            record.horizon_days,
                        ),
                    )
                )
                if not matching_limits or not any(
                    record.simulated_at <= SQLiteSessionRepository._decode_date(limit)
                    for limit in matching_limits
                ):
                    raise CicytexFeedbackRepositoryError("cicytex review store unavailable")
        except CicytexFeedbackRepositoryError:
            raise
        except (OverflowError, sqlite3.Error, TypeError, ValueError):
            raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None

    @staticmethod
    def _validate_sessions(connection: sqlite3.Connection) -> None:
        metadata_schema = tuple(
            row[1:6] for row in connection.execute("PRAGMA table_info(replay_session_metadata)")
        )
        session_schema = tuple(
            row[1:6] for row in connection.execute("PRAGMA table_info(replay_sessions)")
        )
        if metadata_schema != _METADATA_SCHEMA or session_schema != _SESSION_SCHEMA:
            raise SQLiteSessionRepositoryError(_REPOSITORY_ERROR)
        for row in connection.execute("""SELECT session_id, sensor_id, start_date, emission_date,
                      horizon_days, revealed_through, last_observation
               FROM replay_sessions"""):
            SQLiteSessionRepository._decode(row)

    def _enable_durability(self) -> None:
        try:
            with closing(
                sqlite3.connect(
                    self._database,
                    timeout=self._busy_timeout_ms / 1_000,
                    isolation_level=None,
                )
            ) as connection:
                connection.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
                if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
                    raise sqlite3.OperationalError("journal mode unavailable")
                connection.execute("PRAGMA synchronous=FULL")
        except sqlite3.Error:
            raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None

    def _import_on_connection(
        self,
        connection: sqlite3.Connection,
        raw: bytes,
        records: tuple[CicytexFeedbackRecord, ...],
    ) -> None:
        digest = hashlib.sha256(raw).hexdigest()
        found = connection.execute(
            "SELECT value FROM replay_session_metadata WHERE key=?", (_LEGACY_DIGEST_KEY,)
        ).fetchone()
        if found is not None:
            if found != (digest,):
                raise CicytexFeedbackRepositoryError("cicytex review store unavailable")
            return
        for record in records:
            connection.execute(
                f"INSERT INTO {_CICYTEX_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                self._encode(record),
            )
        connection.execute(
            "INSERT INTO replay_session_metadata VALUES (?,?)",
            (_LEGACY_DIGEST_KEY, digest),
        )

    def _open(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                f"{self._database.resolve().as_uri()}?mode=rw",
                uri=True,
                timeout=self._busy_timeout_ms / 1_000,
                isolation_level=None,
            )
            connection.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            return connection
        except sqlite3.Error:
            raise CicytexFeedbackRepositoryError("cicytex review store unavailable") from None

    @staticmethod
    def _encode(record: CicytexFeedbackRecord) -> tuple:
        return (
            record.sensor_id,
            record.emission_date.isoformat(),
            record.horizon_days,
            record.estado_validacion,
            record.etiqueta_corregida,
            record.observacion,
            record.registered_at,
            record.simulated_at.isoformat(),
            record.scope,
        )

    @staticmethod
    def _decode(row: tuple) -> CicytexFeedbackRecord:
        return CicytexFeedbackRecord(
            sensor_id=row[0],
            emission_date=date.fromisoformat(row[1]),
            horizon_days=row[2],
            estado_validacion=row[3],
            etiqueta_corregida=row[4],
            observacion=row[5],
            registered_at=row[6],
            simulated_at=date.fromisoformat(row[7]),
            scope=row[8],
        )
