from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from experiment_runner.cicytex.dataset_contract import CICYTEX_NORMALIZED_V1
from experiment_runner.cicytex.ingestion import (
    CsvCicytexDatasetSource,
    load_normalized_cicytex,
)

CICYTEX_SNAPSHOT_MANIFEST_VERSION = "cicytex-normalized-snapshot-v1"
CICYTEX_DATASET_PROVENANCE_VERSION = "cicytex-dataset-provenance-v2"


def _ingestion_symbol(name: str):
    return getattr(importlib.import_module("experiment_runner.cicytex.ingestion"), name)


def load_normalized_cicytex_snapshot(*args, **kwargs):
    return _ingestion_symbol("load_normalized_cicytex_snapshot")(*args, **kwargs)


def build_cicytex_dataset_provenance(*args, **kwargs):
    return _ingestion_symbol("build_cicytex_dataset_provenance")(*args, **kwargs)


def write_cicytex_dataset_provenance(*args, **kwargs):
    return _ingestion_symbol("write_cicytex_dataset_provenance")(*args, **kwargs)


def _write_dataset(directory: Path) -> dict[str, bytes]:
    contents: dict[str, bytes] = {}
    for index, sensor_id in enumerate(CICYTEX_NORMALIZED_V1.sensor_ids):
        frame = pd.DataFrame(
            {
                "timestamp": ["2023-01-02", "2023-01-01"],
                "soil_moisture": [0.2 + index / 1000, 0.1 + index / 1000],
                "sensor_id": [sensor_id, sensor_id],
            }
        )
        path = directory / CICYTEX_NORMALIZED_V1.file_name_for(sensor_id)
        frame.to_csv(path, index=False)
        contents[path.name] = path.read_bytes()
    return contents


def _expected_dataset_sha256(files: list[dict[str, object]]) -> str:
    payload = {
        "contract_version": CICYTEX_NORMALIZED_V1.version,
        "files": files,
        "hash_algorithm": "sha256",
        "manifest_version": CICYTEX_SNAPSHOT_MANIFEST_VERSION,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_manifest_hash_has_a_frozen_cross_platform_vector():
    input_file = _ingestion_symbol("CicytexInputFile")
    manifest_type = _ingestion_symbol("CicytexDatasetManifest")
    files = tuple(
        input_file(
            sensor_id,
            CICYTEX_NORMALIZED_V1.file_name_for(sensor_id),
            len(f"{sensor_id}\n".encode()),
            hashlib.sha256(f"{sensor_id}\n".encode()).hexdigest(),
        )
        for sensor_id in CICYTEX_NORMALIZED_V1.sensor_ids
    )

    manifest = manifest_type(CICYTEX_NORMALIZED_V1.version, files)

    assert manifest.dataset_sha256 == (
        "42c2a6cecdacbe8112f9d772ea447cad144a1c6df0351be74698566588a76f85"
    )


def test_snapshot_hashes_and_parses_the_exact_declared_bytes(tmp_path: Path):
    contents = _write_dataset(tmp_path)

    snapshot = load_normalized_cicytex_snapshot(tmp_path)

    expected_files = [
        {
            "sensor_id": sensor_id,
            "file_name": CICYTEX_NORMALIZED_V1.file_name_for(sensor_id),
            "size_bytes": len(contents[CICYTEX_NORMALIZED_V1.file_name_for(sensor_id)]),
            "sha256": hashlib.sha256(
                contents[CICYTEX_NORMALIZED_V1.file_name_for(sensor_id)]
            ).hexdigest(),
        }
        for sensor_id in CICYTEX_NORMALIZED_V1.sensor_ids
    ]
    assert snapshot.manifest.to_dict() == {
        "manifest_version": CICYTEX_SNAPSHOT_MANIFEST_VERSION,
        "contract_version": CICYTEX_NORMALIZED_V1.version,
        "hash_algorithm": "sha256",
        "files": expected_files,
        "dataset_sha256": _expected_dataset_sha256(expected_files),
    }
    assert snapshot.dataset_sha256 == _expected_dataset_sha256(expected_files)
    assert_frame_equal(snapshot.dataframe, load_normalized_cicytex(tmp_path), check_exact=True)


def test_snapshot_manifest_is_deterministic_and_contains_no_absolute_paths(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    contents = _write_dataset(first)
    for file_name, content in contents.items():
        (second / file_name).write_bytes(content)
    (first / "unexpected.csv").write_text("ignored", encoding="utf-8")

    manifest_a = load_normalized_cicytex_snapshot(first).manifest
    manifest_b = load_normalized_cicytex_snapshot(second).manifest

    assert manifest_a == manifest_b
    encoded = json.dumps(manifest_a.to_dict(), sort_keys=True)
    assert str(first) not in encoded
    assert str(second) not in encoded


def test_one_byte_change_changes_only_its_entry_and_the_aggregate_hash(tmp_path: Path):
    _write_dataset(tmp_path)
    before = load_normalized_cicytex_snapshot(tmp_path).manifest
    changed_sensor = CICYTEX_NORMALIZED_V1.sensor_ids[0]
    changed_path = tmp_path / CICYTEX_NORMALIZED_V1.file_name_for(changed_sensor)
    changed_path.write_bytes(changed_path.read_bytes().replace(b"0.2", b"0.3", 1))

    after = load_normalized_cicytex_snapshot(tmp_path).manifest

    assert before.dataset_sha256 != after.dataset_sha256
    changed = [
        (left.sensor_id, left.sha256 != right.sha256)
        for left, right in zip(before.files, after.files, strict=True)
    ]
    assert changed == [
        (sensor_id, sensor_id == changed_sensor) for sensor_id in CICYTEX_NORMALIZED_V1.sensor_ids
    ]


def test_snapshot_metadata_is_immutable_and_defensively_serialized(tmp_path: Path):
    _write_dataset(tmp_path)
    snapshot = load_normalized_cicytex_snapshot(tmp_path)

    with pytest.raises(FrozenInstanceError):
        snapshot.manifest.contract_version = "changed"
    with pytest.raises(TypeError):
        snapshot.manifest.files[0] = snapshot.manifest.files[0]

    serialized = snapshot.manifest.to_dict()
    serialized["files"][0]["sha256"] = "changed"
    assert snapshot.manifest.files[0].sha256 != "changed"

    with pytest.raises(ValueError, match="orden contractual"):
        replace(snapshot.manifest, files=tuple(reversed(snapshot.manifest.files)))
    with pytest.raises(ValueError, match="nombre relativo seguro"):
        replace(snapshot.manifest.files[0], file_name="../escape.csv")


def test_load_snapshot_reads_each_declared_file_once_and_pandas_receives_bytes_buffer(
    monkeypatch, tmp_path: Path
):
    _write_dataset(tmp_path)
    source = CsvCicytexDatasetSource(tmp_path)
    original_read_bytes = Path.read_bytes
    read_counts: dict[Path, int] = {}
    original_read_csv = pd.read_csv
    observed_inputs: list[object] = []

    def counted_read_bytes(path: Path) -> bytes:
        read_counts[path] = read_counts.get(path, 0) + 1
        return original_read_bytes(path)

    def observed_read_csv(value, *args, **kwargs):
        observed_inputs.append(value)
        return original_read_csv(value, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)
    monkeypatch.setattr(pd, "read_csv", observed_read_csv)

    source.load_snapshot()

    assert set(read_counts.values()) == {1}
    assert len(read_counts) == len(CICYTEX_NORMALIZED_V1.sensor_ids)
    assert all(not isinstance(value, (str, Path)) for value in observed_inputs)


def test_load_remains_a_dataframe_compatibility_facade(monkeypatch, tmp_path: Path):
    source = CsvCicytexDatasetSource(tmp_path)
    expected = pd.DataFrame({"sentinel": [1]})
    observed: list[str] = []

    class Snapshot:
        dataframe = expected

    def fake_load_snapshot():
        observed.append("snapshot")
        return Snapshot()

    monkeypatch.setattr(source.__class__, "load_snapshot", lambda self: fake_load_snapshot())

    assert source.load() is expected
    assert observed == ["snapshot"]


def test_snapshot_fails_closed_when_a_file_changes_during_its_read(monkeypatch, tmp_path: Path):
    _write_dataset(tmp_path)
    ingestion = importlib.import_module("experiment_runner.cicytex.ingestion")
    original = ingestion._fingerprint
    target = tmp_path / CICYTEX_NORMALIZED_V1.file_name_for(CICYTEX_NORMALIZED_V1.sensor_ids[0])
    calls = 0

    def changing_fingerprint(path: Path):
        nonlocal calls
        value = original(path)
        if path == target:
            calls += 1
            if calls == 2:
                return (*value[:3], value[3] + 1)
        return value

    monkeypatch.setattr(ingestion, "_fingerprint", changing_fingerprint)

    with pytest.raises(ingestion.CicytexSnapshotChangedError, match="cambió"):
        ingestion.CsvCicytexDatasetSource(tmp_path).load_snapshot()


def test_snapshot_rechecks_early_files_after_the_full_capture(monkeypatch, tmp_path: Path):
    _write_dataset(tmp_path)
    ingestion = importlib.import_module("experiment_runner.cicytex.ingestion")
    original = ingestion._fingerprint
    target = tmp_path / CICYTEX_NORMALIZED_V1.file_name_for(CICYTEX_NORMALIZED_V1.sensor_ids[0])
    calls = 0

    def changing_fingerprint(path: Path):
        nonlocal calls
        value = original(path)
        if path == target:
            calls += 1
            if calls == 3:
                return (*value[:3], value[3] + 1)
        return value

    monkeypatch.setattr(ingestion, "_fingerprint", changing_fingerprint)

    with pytest.raises(ingestion.CicytexSnapshotChangedError, match="cambió"):
        ingestion.CsvCicytexDatasetSource(tmp_path).load_snapshot()


def test_provenance_separates_normalized_primary_and_archive_identities(tmp_path: Path):
    normalized = tmp_path / "normalizados"
    normalized.mkdir()
    _write_dataset(normalized)
    primary = tmp_path / "DTPT_Figure_8.csv"
    archive = tmp_path / "delivery.zip"
    primary.write_bytes(b"primary-source")
    archive.write_bytes(b"archive-source")
    snapshot = load_normalized_cicytex_snapshot(normalized)

    provenance = build_cicytex_dataset_provenance(snapshot, primary, archive)

    assert isinstance(provenance, _ingestion_symbol("CicytexDatasetProvenance"))
    assert provenance.to_dict() == {
        "provenance_schema_version": CICYTEX_DATASET_PROVENANCE_VERSION,
        "derivation_status": "external_derivative_unverified",
        "normalized_snapshot": snapshot.manifest.to_dict(),
        "primary_source": {
            "file_name": primary.name,
            "size_bytes": len(b"primary-source"),
            "sha256": hashlib.sha256(b"primary-source").hexdigest(),
        },
        "source_archive": {
            "file_name": archive.name,
            "size_bytes": len(b"archive-source"),
            "sha256": hashlib.sha256(b"archive-source").hexdigest(),
        },
        "dataset_quality": {
            "rows": 42,
            "sensors": 21,
            "start": "2023-01-01",
            "end": "2023-01-02",
            "missing_soil_moisture": 0,
            "duplicate_sensor_dates": 0,
            "rows_per_sensor_min": 2,
            "rows_per_sensor_max": 2,
            "partial_days": 0,
        },
        "legacy_aliases": {
            "dataset_sha256": "primary_source.sha256",
            "zip_sha256": "source_archive.sha256",
        },
    }
    with pytest.raises(FrozenInstanceError):
        provenance.derivation_status = "verified"
    with pytest.raises(FrozenInstanceError):
        provenance.primary_source.sha256 = "f" * 64


def test_provenance_writer_is_deterministic_and_validates_legacy_hashes(tmp_path: Path):
    normalized = tmp_path / "normalizados"
    normalized.mkdir()
    _write_dataset(normalized)
    primary = tmp_path / "primary.csv"
    archive = tmp_path / "delivery.zip"
    primary.write_bytes(b"primary")
    archive.write_bytes(b"archive")
    snapshot = load_normalized_cicytex_snapshot(normalized)
    provenance = build_cicytex_dataset_provenance(snapshot, primary, archive)
    primary_hash = hashlib.sha256(b"primary").hexdigest()
    archive_hash = hashlib.sha256(b"archive").hexdigest()

    path = write_cicytex_dataset_provenance(
        tmp_path / "output",
        provenance,
        dataset_sha256=primary_hash,
        zip_sha256=archive_hash,
        data=snapshot.dataframe,
    )

    assert path.name == "cicytex_dataset_provenance.json"
    assert path.read_text(encoding="utf-8") == (
        json.dumps(provenance.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    assert (
        write_cicytex_dataset_provenance(
            tmp_path / "output",
            provenance,
            dataset_sha256=primary_hash,
            zip_sha256=archive_hash,
            data=snapshot.dataframe,
        )
        == path
    )

    archive.write_bytes(b"different-archive")
    different = build_cicytex_dataset_provenance(snapshot, primary, archive)
    with pytest.raises(FileExistsError, match="procedencia CICYTEX diferente"):
        write_cicytex_dataset_provenance(
            tmp_path / "output",
            different,
            dataset_sha256=primary_hash,
            zip_sha256=hashlib.sha256(b"different-archive").hexdigest(),
            data=snapshot.dataframe,
        )
    with pytest.raises(ValueError, match="dataset_sha256"):
        write_cicytex_dataset_provenance(
            tmp_path / "invalid",
            provenance,
            dataset_sha256="0" * 64,
            zip_sha256=archive_hash,
            data=snapshot.dataframe,
        )
    assert not (tmp_path / "invalid" / "cicytex_dataset_provenance.json").exists()

    with pytest.raises(ValueError, match="zip_sha256"):
        write_cicytex_dataset_provenance(
            tmp_path / "invalid-zip",
            provenance,
            dataset_sha256=primary_hash,
            zip_sha256="0" * 64,
            data=snapshot.dataframe,
        )
    assert not (tmp_path / "invalid-zip" / "cicytex_dataset_provenance.json").exists()

    changed_data = snapshot.dataframe.copy()
    changed_data.loc[0, "soil_moisture"] = 0.999
    with pytest.raises(ValueError, match="DataFrame del snapshot"):
        write_cicytex_dataset_provenance(
            tmp_path / "stale-quality",
            provenance,
            dataset_sha256=primary_hash,
            zip_sha256=archive_hash,
            data=changed_data,
        )
    assert not (tmp_path / "stale-quality" / "cicytex_dataset_provenance.json").exists()

    snapshot.dataframe.loc[0, "soil_moisture"] = 0.999
    with pytest.raises(ValueError, match="data cambió"):
        write_cicytex_dataset_provenance(
            tmp_path / "mutated-snapshot",
            provenance,
            dataset_sha256=primary_hash,
            zip_sha256=archive_hash,
            data=snapshot.dataframe,
        )
    assert not (tmp_path / "mutated-snapshot" / "cicytex_dataset_provenance.json").exists()

    with pytest.raises(TypeError, match="CicytexDatasetProvenance"):
        write_cicytex_dataset_provenance(
            tmp_path / "mutable-dict",
            provenance.to_dict(),
            dataset_sha256=primary_hash,
            zip_sha256=archive_hash,
            data=snapshot.dataframe,
        )


def test_runners_accept_optional_provenance_without_breaking_legacy_signatures():
    from experiment_runner.cicytex.causal_ensemble import run_causal_ensemble
    from experiment_runner.cicytex.experiment import run_experiment

    experiment = inspect.signature(run_experiment).parameters
    causal = inspect.signature(run_causal_ensemble).parameters

    assert experiment["dataset_provenance"].default is None
    assert experiment["dataset_provenance"].kind is inspect.Parameter.KEYWORD_ONLY
    assert causal["dataset_provenance"].default is None
    assert causal["dataset_provenance"].kind is inspect.Parameter.KEYWORD_ONLY


def test_atomic_writer_rejects_a_different_sidecar_winning_after_preflight(
    monkeypatch, tmp_path: Path
):
    normalized = tmp_path / "normalizados"
    normalized.mkdir()
    _write_dataset(normalized)
    snapshot = load_normalized_cicytex_snapshot(normalized)
    primary = tmp_path / "primary.csv"
    archive = tmp_path / "delivery.zip"
    primary.write_bytes(b"primary")
    archive.write_bytes(b"archive")
    provenance = build_cicytex_dataset_provenance(snapshot, primary, archive)
    output = tmp_path / "output"
    ingestion = importlib.import_module("experiment_runner.cicytex.ingestion")
    original_preflight = ingestion.assert_cicytex_provenance_slot

    def racing_preflight(*args, **kwargs):
        expected = original_preflight(*args, **kwargs)
        output.mkdir(parents=True, exist_ok=True)
        (output / "cicytex_dataset_provenance.json").write_bytes(b"different-winner")
        return expected

    monkeypatch.setattr(ingestion, "assert_cicytex_provenance_slot", racing_preflight)

    with pytest.raises(FileExistsError, match="procedencia CICYTEX diferente"):
        ingestion.write_cicytex_dataset_provenance(
            output,
            provenance,
            dataset_sha256=provenance.primary_source.sha256,
            zip_sha256=provenance.source_archive.sha256,
            data=snapshot.dataframe,
        )


@pytest.mark.parametrize("runner_name", ["experiment", "causal_ensemble"])
def test_runner_rejects_an_existing_different_sidecar_before_starting_mlflow(
    runner_name: str, monkeypatch, tmp_path: Path
):
    normalized = tmp_path / "normalizados"
    normalized.mkdir()
    _write_dataset(normalized)
    snapshot = load_normalized_cicytex_snapshot(normalized)
    primary = tmp_path / "primary.csv"
    archive = tmp_path / "delivery.zip"
    primary.write_bytes(b"primary")
    archive.write_bytes(b"archive-a")
    provenance_a = build_cicytex_dataset_provenance(snapshot, primary, archive)
    output = tmp_path / "output"
    write_cicytex_dataset_provenance(
        output,
        provenance_a,
        dataset_sha256=provenance_a.primary_source.sha256,
        zip_sha256=provenance_a.source_archive.sha256,
        data=snapshot.dataframe,
    )
    original_sidecar = (output / "cicytex_dataset_provenance.json").read_bytes()

    archive.write_bytes(b"archive-b")
    provenance_b = build_cicytex_dataset_provenance(snapshot, primary, archive)
    module = importlib.import_module(f"experiment_runner.cicytex.{runner_name}")
    monkeypatch.setattr(
        module.mlflow,
        "set_experiment",
        lambda *args, **kwargs: pytest.fail("MLflow no debe iniciarse"),
    )

    kwargs = {
        "dataset_sha256": provenance_b.primary_source.sha256,
        "zip_sha256": provenance_b.source_archive.sha256,
        "dataset_provenance": provenance_b,
    }
    runner = module.run_experiment if runner_name == "experiment" else module.run_causal_ensemble
    with pytest.raises(FileExistsError, match="procedencia CICYTEX diferente"):
        runner(snapshot.dataframe, output, **kwargs)

    assert (output / "cicytex_dataset_provenance.json").read_bytes() == original_sidecar
    assert not (output / "dependencies.txt").exists()
    assert not (output / "observations.csv").exists()
    assert not (output / "models").exists()
