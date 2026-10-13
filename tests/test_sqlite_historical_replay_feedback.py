from __future__ import annotations

import hashlib
import json
import multiprocessing
import sqlite3
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

from historical_replay.feedback import ReplayFeedbackRecord, visible_feedback_for
from historical_replay.records import build_records


def _api():
    from historical_replay.adapters.sqlite_feedback import (
        MAX_HISTORICAL_FEEDBACK_IMPORT_BYTES,
        MAX_HISTORICAL_FEEDBACK_IMPORT_RECORDS,
        MAX_HISTORICAL_FEEDBACK_LINE_BYTES,
        SQLiteReplayFeedbackStore,
        SQLiteReplayFeedbackStoreError,
    )

    from historical_replay.feedback import HistoricalReplayFeedbackRepository

    return {
        "cap": MAX_HISTORICAL_FEEDBACK_IMPORT_BYTES,
        "line_cap": MAX_HISTORICAL_FEEDBACK_LINE_BYTES,
        "record_cap": MAX_HISTORICAL_FEEDBACK_IMPORT_RECORDS,
        "repository": HistoricalReplayFeedbackRepository,
        "store": SQLiteReplayFeedbackStore,
        "store_error": SQLiteReplayFeedbackStoreError,
    }


def _record(index: int = 0) -> ReplayFeedbackRecord:
    return ReplayFeedbackRecord(
        timestamp_origen="2024-10-19",
        experiment_id="4",
        run_id="1157696b7bb941e394c5af530c762b07",
        estado_validacion="confirmada" if index % 2 == 0 else "rechazada",
        etiqueta_corregida=index % 2,
        observacion=f"observacion-{index}",
        registered_at=f"2026-10-12T10:00:{index:02d}+00:00",
        simulated_at="2024-10-22",
    )


def _package_records():
    return build_records(
        [
            {
                "experiment_id": "4",
                "run_id": "1157696b7bb941e394c5af530c762b07",
                "config_name": "base",
                "seed": 4,
                "timestamp": "2024-10-19T00:00:00.000",
                "target_timestamp": "2024-10-22T00:00:00.000",
                "target_observed": True,
                "y_true": 1.0,
                "y_proba": 0.44,
                "y_pred": 0,
            }
        ],
        horizon_days=3,
    )


def _append_process(database: str, package_id: str, index: int, start, results) -> None:
    api = _api()
    try:
        store = api["store"](Path(database), package_id=package_id)
        start.wait()
        store.append(_record(index))
        results.put("ok")
    except Exception as error:  # pragma: no cover - asserted by parent
        results.put(type(error).__name__)


def _join(process) -> None:
    process.join(10)
    assert not process.is_alive()
    assert process.exitcode == 0


def test_new_historical_store_has_closed_schema_and_implements_port(tmp_path):
    api = _api()
    database = tmp_path / "historical-feedback.sqlite3"
    store = api["store"](database, package_id="package-a")

    assert isinstance(store, api["repository"])
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert tables == {"historical_feedback_metadata", "historical_feedback"}
        columns = [row[1] for row in connection.execute("PRAGMA table_info(historical_feedback)")]
        assert columns == [
            "sequence",
            "package_id",
            "timestamp_origen",
            "experiment_id",
            "run_id",
            "estado_validacion",
            "etiqueta_corregida",
            "observacion",
            "registered_at",
            "simulated_at",
        ]


def test_append_is_durable_ordered_and_package_isolated(tmp_path):
    api = _api()
    database = tmp_path / "historical-feedback.sqlite3"
    first = api["store"](database, package_id="package-a")
    second = api["store"](database, package_id="package-b")
    expected = [_record(0), _record(1), _record(2)]
    for record in expected:
        first.append(record)
    second.append(_record(3))

    restarted = api["store"](database, package_id="package-a")
    assert restarted.list_for("2024-10-19") == expected
    assert second.list_for("2024-10-19") == [_record(3)]


def test_valid_legacy_jsonl_is_imported_once_in_file_order_with_digest(tmp_path):
    api = _api()
    database = tmp_path / "historical-feedback.sqlite3"
    legacy = tmp_path / "private-feedback.jsonl"
    expected = [_record(0), _record(1)]
    raw = b"".join(
        json.dumps(asdict(record), ensure_ascii=False).encode() + b"\n" for record in expected
    )
    legacy.write_bytes(raw)

    store = api["store"](
        database,
        package_id="package-a",
        legacy_jsonl_path=legacy,
    )
    assert store.list_for("2024-10-19") == expected
    with sqlite3.connect(database) as connection:
        metadata = dict(connection.execute("SELECT key, value FROM historical_feedback_metadata"))
    assert metadata["legacy_jsonl_sha256:package-a"] == hashlib.sha256(raw).hexdigest()

    assert (
        api["store"](database, package_id="package-a", legacy_jsonl_path=legacy).list_for(
            "2024-10-19"
        )
        == expected
    )
    legacy.write_bytes(
        json.dumps({**asdict(_record(2)), "observacion": "private-changed"}).encode() + b"\n"
    )
    with pytest.raises(api["store_error"]) as captured:
        api["store"](database, package_id="package-a", legacy_jsonl_path=legacy)
    assert "private-changed" not in str(captured.value)


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b'{"timestamp_origen":"private-partial"}',
        b'{"timestamp_origen":"2024-10-19","timestamp_origen":"duplicate"}\n',
        json.dumps({**asdict(_record(0)), "private_extra": True}).encode() + b"\n",
        json.dumps(asdict(_record(0))).encode(),
    ],
)
def test_invalid_or_partial_legacy_jsonl_imports_nothing_and_is_private(tmp_path, raw):
    api = _api()
    database = tmp_path / "historical-feedback.sqlite3"
    legacy = tmp_path / "private-feedback.jsonl"
    legacy.write_bytes(raw)

    with pytest.raises(api["store_error"]) as captured:
        api["store"](database, package_id="package-a", legacy_jsonl_path=legacy)
    assert str(database) not in str(captured.value)
    assert str(legacy) not in str(captured.value)
    assert "private" not in str(captured.value)
    if database.exists():
        with sqlite3.connect(database) as connection:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if "historical_feedback" in tables:
                assert connection.execute(
                    "SELECT COUNT(*) FROM historical_feedback"
                ).fetchone() == (0,)


def test_import_cap_fails_before_json_decode(tmp_path, monkeypatch):
    api = _api()
    database = tmp_path / "historical-feedback.sqlite3"
    legacy = tmp_path / "feedback.jsonl"
    legacy.write_bytes(b" " * (api["cap"] + 1))
    monkeypatch.setattr(json, "loads", lambda *_args, **_kwargs: pytest.fail("decoded oversized"))

    with pytest.raises(api["store_error"]):
        api["store"](database, package_id="package-a", legacy_jsonl_path=legacy)


@pytest.mark.parametrize("kind", ["line", "records"])
def test_import_line_and_record_caps_fail_closed_without_logging(tmp_path, caplog, kind):
    api = _api()
    database = tmp_path / "historical-feedback.sqlite3"
    legacy = tmp_path / "private-feedback.jsonl"
    marker = "private-import-cap-marker"
    if kind == "line":
        legacy.write_bytes(b'"' + marker.encode() + b"x" * api["line_cap"] + b'"\n')
    else:
        line = json.dumps({**asdict(_record()), "observacion": marker}).encode() + b"\n"
        legacy.write_bytes(line * (api["record_cap"] + 1))

    with pytest.raises(api["store_error"]):
        api["store"](database, package_id="package-a", legacy_jsonl_path=legacy)
    assert marker not in caplog.text


def test_two_adapters_and_processes_append_without_lost_rows(tmp_path):
    api = _api()
    database = tmp_path / "historical-feedback.sqlite3"
    api["store"](database, package_id="package-a")
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    processes = [
        context.Process(
            target=_append_process,
            args=(str(database), "package-a", index, start, results),
        )
        for index in range(6)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        _join(process)

    assert [results.get(timeout=2) for _ in processes] == ["ok"] * len(processes)
    stored = api["store"](database, package_id="package-a").list_for("2024-10-19")
    assert len(stored) == len(processes)
    assert {record.observacion for record in stored} == {
        f"observacion-{index}" for index in range(6)
    }


def test_reset_hides_feedback_without_deleting_history(tmp_path):
    api = _api()
    store = api["store"](tmp_path / "feedback.sqlite3", package_id="package-a")
    store.append(_record())
    records = _package_records()

    assert (
        visible_feedback_for(
            records,
            store,
            timestamp_origen=date(2024, 10, 19),
            simulated_date=date(2024, 10, 20),
        )
        == []
    )
    assert store.list_for("2024-10-19") == [_record()]
    assert visible_feedback_for(
        records,
        store,
        timestamp_origen=date(2024, 10, 19),
        simulated_date=date(2024, 10, 22),
    ) == [_record()]


@pytest.mark.parametrize("operation", ["append", "list"])
def test_post_bootstrap_corruption_is_a_private_repository_error(tmp_path, operation):
    api = _api()
    database = tmp_path / "private-historical-feedback.sqlite3"
    store = api["store"](database, package_id="package-a")
    store.append(_record())
    marker = "private-corrupt-history-marker"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE historical_feedback SET registered_at=? WHERE package_id=?",
            (marker, "package-a"),
        )

    with pytest.raises(api["store_error"]) as captured:
        if operation == "append":
            store.append(_record(1))
        else:
            store.list_for("2024-10-19")
    assert str(database) not in str(captured.value)
    assert marker not in str(captured.value)


def test_domain_feedback_module_has_no_filesystem_or_sqlite_dependencies():
    source = (Path(__file__).parents[1] / "src/historical_replay/feedback.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "sqlite3",
        "from pathlib import Path",
        "import json",
        "interprocess_lock",
        ".open(",
        ".read_text(",
        ".write_text(",
    ):
        assert forbidden not in source
