"""Stage a verified CICYTEX replay database without touching its source."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from historical_replay.adapters.sqlite_sessions import (
    SQLiteCicytexFeedbackRepository,
    SQLiteSessionRepository,
)

_DATABASE_NAME = "cicytex_replay_sessions.sqlite3"
_EVIDENCE_NAME = "cutover-evidence.json"
_EVIDENCE_SCHEMA = "cicytex-replay-storage-cutover-v1"
_FAILURE_MESSAGE = "cicytex replay cutover failed"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class CutoverError(RuntimeError):
    """The offline cutover could not be staged safely."""


def _fail() -> CutoverError:
    return CutoverError(_FAILURE_MESSAGE)


def _require_regular_file(path: Path) -> None:
    details = path.lstat()
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        raise _fail()


def _require_no_symlink_ancestry(path: Path) -> None:
    absolute = path.absolute()
    for candidate in (absolute, *absolute.parents):
        if os.path.lexists(candidate) and candidate.is_symlink():
            raise _fail()


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_digest(path: Path, expected: str | None) -> str:
    if type(expected) is not str or _SHA256.fullmatch(expected) is None:
        raise _fail()
    actual = _digest(path)
    if not hmac.compare_digest(actual, expected):
        raise _fail()
    return actual


def _backup_database(source: Path, destination: Path) -> None:
    source_uri = f"{source.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True, isolation_level=None)) as source_connection:
        with closing(sqlite3.connect(destination, isolation_level=None)) as destination_connection:
            source_connection.backup(destination_connection)


def _source_wal_state(database: Path) -> tuple[Path, str | None]:
    wal = database.with_name(f"{database.name}-wal")
    return wal, _digest(wal) if wal.is_file() else None


def _require_unchanged_source_wal(state: tuple[Path, str | None]) -> None:
    wal, expected = state
    actual = _digest(wal) if wal.is_file() else None
    if actual != expected:
        raise _fail()


def _remove_staging_auxiliaries(database: Path) -> None:
    for path in (
        database.with_name(f".{database.name}.bootstrap.lock"),
        database.with_name(f"{database.name}-wal"),
        database.with_name(f"{database.name}-shm"),
        database.with_name(f"{database.name}-journal"),
    ):
        path.unlink(missing_ok=True)


def _checkpoint_staged_database(database: Path) -> None:
    with closing(sqlite3.connect(database, isolation_level=None)) as connection:
        result = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if result is None or result[0] != 0:
            raise _fail()


def _verify_source_snapshot(database: Path) -> dict[str, int | str]:
    database_uri = f"{database.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True, isolation_level=None)) as connection:
        connection.execute("PRAGMA query_only=ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        version = connection.execute("PRAGMA user_version").fetchone()
        sessions = connection.execute("SELECT COUNT(*) FROM replay_sessions").fetchone()
        feedback_table = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND name = 'cicytex_replay_feedback'"
        ).fetchone()
        if feedback_table == (1,):
            feedback = connection.execute("SELECT COUNT(*) FROM cicytex_replay_feedback").fetchone()
        elif feedback_table == (0,):
            feedback = (0,)
        else:
            raise _fail()
    if integrity != ("ok",) or version is None:
        raise _fail()
    if sessions is None or feedback is None:
        raise _fail()
    if any(type(value) is not int for value in (version[0], sessions[0], feedback[0])):
        raise _fail()
    return {
        "source_database_user_version": version[0],
        "source_integrity_check": integrity[0],
        "source_session_count": sessions[0],
        "source_feedback_count": feedback[0],
    }


def _verify_staged_database(database: Path) -> dict[str, int | str]:
    database_uri = f"{database.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True, isolation_level=None)) as connection:
        connection.execute("PRAGMA query_only=ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        version = connection.execute("PRAGMA user_version").fetchone()
        sessions = connection.execute("SELECT COUNT(*) FROM replay_sessions").fetchone()
        feedback = connection.execute("SELECT COUNT(*) FROM cicytex_replay_feedback").fetchone()
    if integrity != ("ok",) or version != (2,):
        raise _fail()
    if sessions is None or feedback is None:
        raise _fail()
    if type(sessions[0]) is not int or type(feedback[0]) is not int:
        raise _fail()
    return {
        "database_user_version": version[0],
        "integrity_check": integrity[0],
        "session_count": sessions[0],
        "feedback_count": feedback[0],
    }


def _write_evidence(path: Path, evidence: dict[str, int | str | None]) -> None:
    payload = json.dumps(
        evidence,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def stage_cutover(
    *,
    source_database: Path | None,
    legacy_feedback_json: Path | None,
    output_dir: Path,
    expected_database_sha256: str | None,
    expected_legacy_sha256: str | None,
    empty_source: bool = False,
) -> dict[str, int | str | None]:
    """Build and atomically publish a validated, self-contained v2 database."""

    staging: Path | None = None
    try:
        if not isinstance(output_dir, Path) or type(empty_source) is not bool:
            raise _fail()
        _require_no_symlink_ancestry(output_dir)
        if os.path.lexists(output_dir) or not output_dir.parent.is_dir():
            raise _fail()
        if empty_source == (source_database is not None):
            raise _fail()
        if legacy_feedback_json is not None and source_database is None:
            raise _fail()

        source_digest = None
        source_wal_digest = None
        if source_database is not None:
            if not isinstance(source_database, Path):
                raise _fail()
            _require_no_symlink_ancestry(source_database)
            _require_regular_file(source_database)
            source_digest = _require_digest(source_database, expected_database_sha256)
        elif expected_database_sha256 is not None:
            raise _fail()

        legacy_digest = None
        if legacy_feedback_json is not None:
            if not isinstance(legacy_feedback_json, Path):
                raise _fail()
            _require_no_symlink_ancestry(legacy_feedback_json)
            _require_regular_file(legacy_feedback_json)
            legacy_digest = _require_digest(legacy_feedback_json, expected_legacy_sha256)
        elif expected_legacy_sha256 is not None:
            raise _fail()

        staging = Path(tempfile.mkdtemp(prefix=".cicytex-replay-cutover-", dir=output_dir.parent))
        staged_database = staging / _DATABASE_NAME
        source_verification: dict[str, int | str | None] = {
            "source_database_user_version": None,
            "source_integrity_check": None,
            "source_session_count": 0,
            "source_feedback_count": 0,
        }
        source_snapshot_digest = None
        source_snapshot_size = None
        if source_database is not None:
            source_wal_state = _source_wal_state(source_database)
            source_wal_digest = source_wal_state[1]
            _backup_database(source_database, staged_database)
            _require_unchanged_source_wal(source_wal_state)
            source_verification = _verify_source_snapshot(staged_database)
            source_snapshot_digest = _digest(staged_database)
            source_snapshot_size = staged_database.stat().st_size

        SQLiteCicytexFeedbackRepository(
            staged_database,
            legacy_feedback_path=legacy_feedback_json,
        )
        SQLiteSessionRepository(staged_database)
        _checkpoint_staged_database(staged_database)

        if source_database is not None and _digest(source_database) != source_digest:
            raise _fail()
        if source_database is not None:
            _require_unchanged_source_wal(source_wal_state)
        if legacy_feedback_json is not None and _digest(legacy_feedback_json) != legacy_digest:
            raise _fail()

        verification = _verify_staged_database(staged_database)
        imported_feedback_count = (
            verification["feedback_count"] - source_verification["source_feedback_count"]
        )
        if verification["session_count"] != source_verification["source_session_count"]:
            raise _fail()
        if type(imported_feedback_count) is not int or imported_feedback_count < 0:
            raise _fail()
        if legacy_feedback_json is None and imported_feedback_count != 0:
            raise _fail()
        _remove_staging_auxiliaries(staged_database)
        evidence: dict[str, int | str | None] = {
            "schema_version": _EVIDENCE_SCHEMA,
            "source_database_sha256": source_digest,
            "source_wal_sha256": source_wal_digest,
            "source_snapshot_sha256": source_snapshot_digest,
            "source_snapshot_size_bytes": source_snapshot_size,
            "legacy_feedback_sha256": legacy_digest,
            "staged_database_sha256": _digest(staged_database),
            "staged_database_size_bytes": staged_database.stat().st_size,
            "legacy_feedback_imported_count": imported_feedback_count,
            **source_verification,
            **verification,
        }
        _write_evidence(staging / _EVIDENCE_NAME, evidence)

        if os.path.lexists(output_dir):
            raise _fail()
        os.replace(staging, output_dir)
        staging = None
        return evidence
    except CutoverError:
        raise
    except Exception:
        raise _fail() from None
    finally:
        if staging is not None:
            try:
                shutil.rmtree(staging)
            except OSError:
                pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage a CICYTEX replay storage cutover")
    parser.add_argument("--source-database", type=Path)
    parser.add_argument("--legacy-feedback-json", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-database-sha256")
    parser.add_argument("--expected-legacy-sha256")
    parser.add_argument("--empty-source", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        stage_cutover(
            source_database=arguments.source_database,
            legacy_feedback_json=arguments.legacy_feedback_json,
            output_dir=arguments.output_dir,
            expected_database_sha256=arguments.expected_database_sha256,
            expected_legacy_sha256=arguments.expected_legacy_sha256,
            empty_source=arguments.empty_source,
        )
    except Exception:
        print(_FAILURE_MESSAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
