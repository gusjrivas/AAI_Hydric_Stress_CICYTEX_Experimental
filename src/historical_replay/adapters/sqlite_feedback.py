"""SQLite append-only adapter for historical replay feedback."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from data_ingestion.storage import StorageLockTimeout, interprocess_lock
from historical_replay.feedback import ReplayFeedbackRecord

MAX_HISTORICAL_FEEDBACK_IMPORT_BYTES = 1_048_576
MAX_HISTORICAL_FEEDBACK_IMPORT_RECORDS = 1_000
MAX_HISTORICAL_FEEDBACK_LINE_BYTES = 65_536

_ERROR = "historical replay feedback store is unavailable"
_METADATA_DDL = """CREATE TABLE historical_feedback_metadata (
                           key TEXT PRIMARY KEY NOT NULL,
                           value TEXT NOT NULL
                       ) WITHOUT ROWID"""
_FEEDBACK_DDL = """CREATE TABLE historical_feedback (
                           sequence INTEGER PRIMARY KEY NOT NULL,
                           package_id TEXT NOT NULL,
                           timestamp_origen TEXT NOT NULL,
                           experiment_id TEXT NOT NULL,
                           run_id TEXT NOT NULL,
                           estado_validacion TEXT NOT NULL,
                           etiqueta_corregida INTEGER,
                           observacion TEXT,
                           registered_at TEXT NOT NULL,
                           simulated_at TEXT NOT NULL
                       )"""
_FIELDS = {
    "timestamp_origen",
    "experiment_id",
    "run_id",
    "estado_validacion",
    "etiqueta_corregida",
    "observacion",
    "registered_at",
    "simulated_at",
}


class SQLiteReplayFeedbackStoreError(RuntimeError):
    """A private historical-feedback persistence failure occurred."""


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _parse_import(path: Path) -> tuple[bytes, tuple[ReplayFeedbackRecord, ...]]:
    try:
        size = path.stat().st_size
        if size <= 0 or size > MAX_HISTORICAL_FEEDBACK_IMPORT_BYTES:
            raise ValueError("invalid import size")
        raw = path.read_bytes()
        if len(raw) != size or not raw.endswith(b"\n"):
            raise ValueError("invalid import framing")
        lines = raw.splitlines(keepends=True)
        if len(lines) > MAX_HISTORICAL_FEEDBACK_IMPORT_RECORDS:
            raise ValueError("too many import records")
        records = []
        for line in lines:
            if len(line) > MAX_HISTORICAL_FEEDBACK_LINE_BYTES or line in {b"", b"\n"}:
                raise ValueError("invalid import line")
            payload = json.loads(
                line[:-1].decode("utf-8"),
                object_pairs_hook=_strict_object,
                parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
            )
            if type(payload) is not dict or set(payload) != _FIELDS:
                raise ValueError("invalid import record")
            records.append(ReplayFeedbackRecord(**payload))
        return raw, tuple(records)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        raise SQLiteReplayFeedbackStoreError(_ERROR) from None


class SQLiteReplayFeedbackStore:
    def __init__(
        self,
        database: Path,
        *,
        package_id: str,
        legacy_jsonl_path: Path | None = None,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        if not isinstance(database, Path) or type(package_id) is not str or not package_id:
            raise TypeError("invalid historical feedback store configuration")
        if len(package_id) > 256 or type(busy_timeout_ms) is not int or busy_timeout_ms <= 0:
            raise ValueError("invalid historical feedback store configuration")
        if legacy_jsonl_path is not None and not isinstance(legacy_jsonl_path, Path):
            raise TypeError("legacy_jsonl_path must be a Path")
        self._database = database
        self._package_id = package_id
        self._busy_timeout_ms = busy_timeout_ms
        imported = _parse_import(legacy_jsonl_path) if legacy_jsonl_path is not None else None
        self._bootstrap(imported)

    def append(self, record: ReplayFeedbackRecord) -> None:
        if type(record) is not ReplayFeedbackRecord:
            raise TypeError("record must be ReplayFeedbackRecord")
        connection = self._open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._validate_rows(connection)
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM historical_feedback"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO historical_feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sequence, self._package_id, *self._encode(record)),
            )
            connection.commit()
        except (sqlite3.Error, TypeError, ValueError):
            connection.rollback()
            raise SQLiteReplayFeedbackStoreError(_ERROR) from None
        finally:
            connection.close()

    def list_for(self, timestamp_origen: str) -> list[ReplayFeedbackRecord]:
        if type(timestamp_origen) is not str:
            raise TypeError("timestamp_origen must be a string")
        connection = self._open()
        try:
            rows = connection.execute(
                """SELECT timestamp_origen, experiment_id, run_id, estado_validacion,
                          etiqueta_corregida, observacion, registered_at, simulated_at
                   FROM historical_feedback
                   WHERE package_id = ? AND timestamp_origen = ? ORDER BY sequence""",
                (self._package_id, timestamp_origen),
            ).fetchall()
            return [self._decode(row) for row in rows]
        except (sqlite3.Error, TypeError, ValueError):
            raise SQLiteReplayFeedbackStoreError(_ERROR) from None
        finally:
            connection.close()

    def _bootstrap(self, imported: tuple[bytes, tuple[ReplayFeedbackRecord, ...]] | None) -> None:
        lock = self._database.with_name(f".{self._database.name}.bootstrap.lock")
        try:
            with interprocess_lock(lock, timeout=self._busy_timeout_ms / 1_000):
                self._database.parent.mkdir(parents=True, exist_ok=True)
                new = not self._database.exists()
                connection = sqlite3.connect(
                    self._database,
                    timeout=self._busy_timeout_ms / 1_000,
                    isolation_level=None,
                )
                try:
                    connection.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
                    connection.execute("BEGIN IMMEDIATE")
                    if new:
                        connection.execute(_METADATA_DDL)
                        connection.execute(_FEEDBACK_DDL)
                        connection.execute("PRAGMA user_version=1")
                        connection.execute(
                            "INSERT INTO historical_feedback_metadata VALUES ('schema_version','1')"
                        )
                    else:
                        self._validate_schema(connection)
                    if imported is not None:
                        self._import(connection, *imported)
                    connection.commit()
                    connection.execute("PRAGMA journal_mode=WAL")
                    connection.execute("PRAGMA synchronous=FULL")
                except BaseException:
                    connection.rollback()
                    raise
                finally:
                    connection.close()
        except SQLiteReplayFeedbackStoreError:
            raise
        except (OSError, sqlite3.Error, StorageLockTimeout, TypeError, ValueError):
            raise SQLiteReplayFeedbackStoreError(_ERROR) from None

    def _import(
        self,
        connection: sqlite3.Connection,
        raw: bytes,
        records: tuple[ReplayFeedbackRecord, ...],
    ) -> None:
        key = f"legacy_jsonl_sha256:{self._package_id}"
        digest = hashlib.sha256(raw).hexdigest()
        found = connection.execute(
            "SELECT value FROM historical_feedback_metadata WHERE key=?", (key,)
        ).fetchone()
        if found is not None:
            if found != (digest,):
                raise SQLiteReplayFeedbackStoreError(_ERROR)
            return
        start = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM historical_feedback"
        ).fetchone()[0]
        for offset, record in enumerate(records, 1):
            connection.execute(
                "INSERT INTO historical_feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (start + offset, self._package_id, *self._encode(record)),
            )
        connection.execute(
            "INSERT INTO historical_feedback_metadata(key,value) VALUES (?,?)", (key, digest)
        )

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        if connection.execute("PRAGMA user_version").fetchone() != (1,):
            raise SQLiteReplayFeedbackStoreError(_ERROR)
        objects = tuple(
            connection.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            )
        )
        if objects != (
            ("table", "historical_feedback", "historical_feedback", _FEEDBACK_DDL),
            (
                "table",
                "historical_feedback_metadata",
                "historical_feedback_metadata",
                _METADATA_DDL,
            ),
        ):
            raise SQLiteReplayFeedbackStoreError(_ERROR)
        metadata = dict(connection.execute("SELECT key,value FROM historical_feedback_metadata"))
        if metadata.get("schema_version") != "1":
            raise SQLiteReplayFeedbackStoreError(_ERROR)
        self._validate_rows(connection)

    def _validate_rows(self, connection: sqlite3.Connection) -> None:
        for row in connection.execute(
            """SELECT timestamp_origen, experiment_id, run_id, estado_validacion,
                      etiqueta_corregida, observacion, registered_at, simulated_at
               FROM historical_feedback"""
        ):
            self._decode(row)

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
            raise SQLiteReplayFeedbackStoreError(_ERROR) from None

    @staticmethod
    def _encode(record: ReplayFeedbackRecord) -> tuple:
        return (
            record.timestamp_origen,
            record.experiment_id,
            record.run_id,
            record.estado_validacion,
            record.etiqueta_corregida,
            record.observacion,
            record.registered_at,
            record.simulated_at,
        )

    @staticmethod
    def _decode(row: tuple) -> ReplayFeedbackRecord:
        return ReplayFeedbackRecord(*row)
