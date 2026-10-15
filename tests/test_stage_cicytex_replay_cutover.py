from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "stage_cicytex_replay_cutover.py"
DATABASE_NAME = "cicytex_replay_sessions.sqlite3"
EVIDENCE_NAME = "cutover-evidence.json"
EVIDENCE_SCHEMA = "cicytex-replay-storage-cutover-v1"


def _load_cutover_module() -> ModuleType | None:
    if not SCRIPT.is_file():
        return None
    spec = importlib.util.spec_from_file_location("stage_cicytex_replay_cutover", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CUTOVER = _load_cutover_module()
requires_cutover_tool = pytest.mark.skipif(CUTOVER is None, reason="cutover tool is still RED")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _create_v1_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        with connection:
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
            connection.execute(
                "INSERT INTO replay_sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "session-1",
                    "CP1_S1",
                    "2023-07-06",
                    "2023-07-06",
                    1,
                    "2023-07-07",
                    "2023-07-25",
                ),
            )
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode = DELETE")


def _write_legacy_feedback(path: Path, marker: str = "captured-review") -> None:
    path.write_text(
        json.dumps(
            {
                "CP1_S1|2023-07-06|1": {
                    "estado_validacion": "confirmada",
                    "etiqueta_corregida": 1,
                    "observacion": marker,
                    "registered_at": "2026-10-12T10:00:00+00:00",
                    "simulated_at": "2023-07-07",
                    "scope": "demostracion; no recalibra ni reentrena",
                }
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _stage(
    *,
    source_database: Path | None,
    legacy_feedback_json: Path | None,
    output_dir: Path,
    empty_source: bool = False,
):
    assert CUTOVER is not None
    return CUTOVER.stage_cutover(
        source_database=source_database,
        legacy_feedback_json=legacy_feedback_json,
        output_dir=output_dir,
        expected_database_sha256=(
            _sha256(source_database) if source_database is not None else None
        ),
        expected_legacy_sha256=(
            _sha256(legacy_feedback_json) if legacy_feedback_json is not None else None
        ),
        empty_source=empty_source,
    )


def test_offline_cicytex_replay_cutover_tool_is_present():
    assert SCRIPT.is_file(), "scripts/stage_cicytex_replay_cutover.py is required"


@requires_cutover_tool
def test_stage_uses_backup_and_existing_repositories_without_reimplementing_schema():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        (node.module, alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    constants = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)}

    assert (
        "historical_replay.adapters.sqlite_sessions",
        "SQLiteSessionRepository",
    ) in imported
    assert (
        "historical_replay.adapters.sqlite_sessions",
        "SQLiteCicytexFeedbackRepository",
    ) in imported
    assert not any(
        isinstance(value, str) and "CREATE TABLE" in value.upper() for value in constants
    )
    assert any(isinstance(value, str) and "mode=ro" in value for value in constants)


@requires_cutover_tool
def test_source_database_and_matching_legacy_feedback_stage_atomically(tmp_path: Path):
    source = tmp_path / "captured.sqlite3"
    legacy = tmp_path / "feedback.json"
    output = tmp_path / "staged-cutover"
    _create_v1_database(source)
    _write_legacy_feedback(legacy)
    source_before = source.read_bytes()
    legacy_before = legacy.read_bytes()

    evidence = _stage(
        source_database=source,
        legacy_feedback_json=legacy,
        output_dir=output,
    )

    assert source.read_bytes() == source_before
    assert legacy.read_bytes() == legacy_before
    assert sorted(path.name for path in output.iterdir()) == [DATABASE_NAME, EVIDENCE_NAME]
    staged = output / DATABASE_NAME
    with sqlite3.connect(f"file:{staged.as_posix()}?mode=ro", uri=True) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM replay_sessions").fetchone() == (1,)
        assert connection.execute("SELECT COUNT(*) FROM cicytex_replay_feedback").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE forbidden_write(value TEXT)")
    assert evidence == json.loads((output / EVIDENCE_NAME).read_text(encoding="utf-8"))
    assert evidence["schema_version"] == EVIDENCE_SCHEMA
    assert evidence["source_database_sha256"] == hashlib.sha256(source_before).hexdigest()
    assert evidence["legacy_feedback_sha256"] == hashlib.sha256(legacy_before).hexdigest()
    assert evidence["staged_database_sha256"] == _sha256(staged)
    assert evidence["database_user_version"] == 2
    assert evidence["integrity_check"] == "ok"
    assert evidence["source_database_user_version"] == 1
    assert evidence["source_integrity_check"] == "ok"
    assert evidence["source_session_count"] == 1
    assert evidence["source_feedback_count"] == 0
    assert evidence["legacy_feedback_imported_count"] == 1
    assert evidence["session_count"] == 1
    assert evidence["feedback_count"] == 1
    assert evidence["session_count"] == evidence["source_session_count"]
    assert evidence["feedback_count"] == (
        evidence["source_feedback_count"] + evidence["legacy_feedback_imported_count"]
    )
    assert evidence["staged_database_size_bytes"] == staged.stat().st_size
    serialized = json.dumps(evidence, sort_keys=True)
    assert str(tmp_path) not in serialized
    assert "captured-review" not in serialized
    assert "session-1" not in serialized


@requires_cutover_tool
def test_sqlite_backup_captures_committed_wal_without_publishing_companions(tmp_path: Path):
    source = tmp_path / "wal-source.sqlite3"
    output = tmp_path / "staged-cutover"
    _create_v1_database(source)
    with sqlite3.connect(source) as writer:
        assert writer.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
        writer.execute(
            "INSERT INTO replay_sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "session-2",
                "CP1_S2",
                "2023-07-07",
                "2023-07-07",
                2,
                "2023-07-09",
                "2023-07-25",
            ),
        )
        writer.commit()
        wal = source.with_name(f"{source.name}-wal")
        assert wal.is_file()
        source_before = source.read_bytes()
        wal_before = wal.read_bytes()

        evidence = _stage(
            source_database=source,
            legacy_feedback_json=None,
            output_dir=output,
        )

        assert source.read_bytes() == source_before
        assert wal.read_bytes() == wal_before
    assert evidence["session_count"] == 2
    assert evidence["source_database_user_version"] == 1
    assert evidence["source_integrity_check"] == "ok"
    assert evidence["source_session_count"] == 2
    assert evidence["source_feedback_count"] == 0
    assert evidence["legacy_feedback_imported_count"] == 0
    assert evidence["session_count"] == evidence["source_session_count"]
    assert sorted(path.name for path in output.iterdir()) == [DATABASE_NAME, EVIDENCE_NAME]


@requires_cutover_tool
def test_wal_created_during_backup_aborts_without_deleting_source_sidecar(
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source.sqlite3"
    output = tmp_path / "must-not-publish"
    _create_v1_database(source)
    real_backup = CUTOVER._backup_database
    real_unlink = CUTOVER.Path.unlink
    writers: list[sqlite3.Connection] = []
    captured: dict[str, Path | bytes | bool] = {"unlink_attempted": False}

    def backup_after_concurrent_commit(database: Path, destination: Path) -> None:
        writer = sqlite3.connect(database)
        writers.append(writer)
        assert writer.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
        writer.execute(
            "INSERT INTO replay_sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "session-race",
                "CP1_S2",
                "2023-07-07",
                "2023-07-07",
                2,
                "2023-07-09",
                "2023-07-25",
            ),
        )
        writer.commit()
        wal = database.with_name(f"{database.name}-wal")
        assert wal.is_file()
        captured["wal"] = wal
        captured["wal_bytes"] = wal.read_bytes()
        real_backup(database, destination)

    def preserve_source_wal(path: Path, *args, **kwargs) -> None:
        if path == captured.get("wal"):
            captured["unlink_attempted"] = True
            return
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(CUTOVER, "_backup_database", backup_after_concurrent_commit)
    monkeypatch.setattr(CUTOVER.Path, "unlink", preserve_source_wal)
    try:
        with pytest.raises(CUTOVER.CutoverError):
            _stage(source_database=source, legacy_feedback_json=None, output_dir=output)

        wal = captured["wal"]
        assert isinstance(wal, Path)
        assert wal.is_file()
        assert wal.read_bytes() == captured["wal_bytes"]
        assert captured["unlink_attempted"] is False
        assert not output.exists()
    finally:
        for writer in writers:
            writer.close()


@requires_cutover_tool
def test_explicit_empty_source_stages_an_empty_v2_database(tmp_path: Path):
    output = tmp_path / "empty-cutover"

    evidence = _stage(
        source_database=None,
        legacy_feedback_json=None,
        output_dir=output,
        empty_source=True,
    )

    assert evidence["database_user_version"] == 2
    assert evidence["session_count"] == 0
    assert evidence["feedback_count"] == 0
    assert (output / DATABASE_NAME).is_file()


@requires_cutover_tool
def test_empty_source_rejects_nonempty_legacy_feedback_for_manual_reconciliation(
    tmp_path: Path,
):
    legacy = tmp_path / "feedback.json"
    output = tmp_path / "must-not-publish"
    _write_legacy_feedback(legacy, marker="private-orphan-review")
    before = legacy.read_bytes()

    with pytest.raises(CUTOVER.CutoverError) as captured:
        _stage(
            source_database=None,
            legacy_feedback_json=legacy,
            output_dir=output,
            empty_source=True,
        )

    assert legacy.read_bytes() == before
    assert not output.exists()
    assert "private-orphan-review" not in str(captured.value)
    assert str(tmp_path) not in str(captured.value)


@requires_cutover_tool
def test_corrupt_database_is_private_and_never_published(tmp_path: Path):
    source = tmp_path / "private-corrupt.sqlite3"
    output = tmp_path / "must-not-publish"
    marker = b"private-corrupt-database-content"
    source.write_bytes(marker)

    with pytest.raises(CUTOVER.CutoverError) as captured:
        _stage(source_database=source, legacy_feedback_json=None, output_dir=output)

    assert source.read_bytes() == marker
    assert not output.exists()
    assert marker.decode() not in str(captured.value)
    assert str(tmp_path) not in str(captured.value)


@requires_cutover_tool
@pytest.mark.parametrize("bad_hash_target", ("database", "legacy"))
def test_expected_hash_mismatch_is_fail_closed_and_preserves_sources(
    tmp_path: Path,
    bad_hash_target: str,
):
    source = tmp_path / "source.sqlite3"
    legacy = tmp_path / "feedback.json"
    output = tmp_path / "must-not-publish"
    _create_v1_database(source)
    _write_legacy_feedback(legacy)
    source_before = source.read_bytes()
    legacy_before = legacy.read_bytes()
    arguments = {
        "source_database": source,
        "legacy_feedback_json": legacy,
        "output_dir": output,
        "expected_database_sha256": _sha256(source),
        "expected_legacy_sha256": _sha256(legacy),
        "empty_source": False,
    }
    arguments[f"expected_{bad_hash_target}_sha256"] = "f" * 64

    with pytest.raises(CUTOVER.CutoverError):
        CUTOVER.stage_cutover(**arguments)

    assert source.read_bytes() == source_before
    assert legacy.read_bytes() == legacy_before
    assert not output.exists()


@requires_cutover_tool
def test_existing_or_symlinked_output_is_rejected_before_staging(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    _create_v1_database(source)
    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(CUTOVER.CutoverError):
        _stage(source_database=source, legacy_feedback_json=None, output_dir=existing)

    symlink = tmp_path / "output-link"
    try:
        symlink.symlink_to(existing, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")
    with pytest.raises(CUTOVER.CutoverError):
        _stage(source_database=source, legacy_feedback_json=None, output_dir=symlink)


@requires_cutover_tool
def test_symlinked_input_is_rejected_without_touching_its_target(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    source_link = tmp_path / "source-link.sqlite3"
    output = tmp_path / "must-not-publish"
    _create_v1_database(source)
    before = source.read_bytes()
    try:
        source_link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")

    with pytest.raises(CUTOVER.CutoverError):
        _stage(source_database=source_link, legacy_feedback_json=None, output_dir=output)

    assert source.read_bytes() == before
    assert not output.exists()


@requires_cutover_tool
@pytest.mark.parametrize("path_role", ("database", "legacy", "output"))
def test_symlinked_path_ancestor_is_rejected_before_staging(
    tmp_path: Path,
    path_role: str,
):
    real_root = tmp_path / "real-root"
    real_root.mkdir()
    nested = real_root / "nested"
    nested.mkdir()
    alias_root = tmp_path / "alias-root"
    try:
        alias_root.symlink_to(real_root, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")

    source = nested / "source.sqlite3"
    legacy = nested / "feedback.json"
    _create_v1_database(source)
    _write_legacy_feedback(legacy)
    source_before = source.read_bytes()
    legacy_before = legacy.read_bytes()
    source_argument = alias_root / "nested" / source.name if path_role == "database" else source
    legacy_argument = alias_root / "nested" / legacy.name if path_role == "legacy" else legacy
    output = (
        alias_root / "nested" / "must-not-publish"
        if path_role == "output"
        else tmp_path / "must-not-publish"
    )

    with pytest.raises(CUTOVER.CutoverError):
        _stage(
            source_database=source_argument,
            legacy_feedback_json=legacy_argument,
            output_dir=output,
        )

    assert source.read_bytes() == source_before
    assert legacy.read_bytes() == legacy_before
    assert not output.exists()


@requires_cutover_tool
def test_publish_failure_never_exposes_partial_output(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.sqlite3"
    output = tmp_path / "must-not-publish"
    _create_v1_database(source)
    before = source.read_bytes()

    def fail_publish(*_args, **_kwargs):
        raise OSError("private-publish-failure")

    monkeypatch.setattr(CUTOVER.os, "replace", fail_publish)
    with pytest.raises(CUTOVER.CutoverError) as captured:
        _stage(source_database=source, legacy_feedback_json=None, output_dir=output)

    assert source.read_bytes() == before
    assert not output.exists()
    assert {path.name for path in tmp_path.iterdir()} == {source.name}
    assert "private-publish-failure" not in str(captured.value)
    assert str(tmp_path) not in str(captured.value)


@requires_cutover_tool
def test_cli_failure_is_stable_nonzero_and_private(tmp_path: Path):
    source = tmp_path / "private-source.sqlite3"
    output = tmp_path / "private-output"
    _create_v1_database(source)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-database",
            str(source),
            "--expected-database-sha256",
            "f" * 64,
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip() == "cicytex replay cutover failed"
    assert str(tmp_path) not in result.stderr
    assert not output.exists()
