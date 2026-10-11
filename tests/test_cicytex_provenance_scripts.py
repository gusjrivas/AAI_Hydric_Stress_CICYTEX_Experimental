from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

from experiment_runner.cicytex.dataset_contract import CICYTEX_NORMALIZED_V1

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_normalized(directory: Path) -> None:
    directory.mkdir(parents=True)
    for index, sensor_id in enumerate(CICYTEX_NORMALIZED_V1.sensor_ids):
        pd.DataFrame(
            {
                "timestamp": ["2023-01-01", "2023-01-02"],
                "soil_moisture": [0.2 + index / 1000, 0.21 + index / 1000],
                "sensor_id": [sensor_id, sensor_id],
            }
        ).to_csv(directory / CICYTEX_NORMALIZED_V1.file_name_for(sensor_id), index=False)


def test_experiment_script_passes_one_typed_snapshot_and_three_distinct_identities(
    monkeypatch, tmp_path: Path
):
    module = _load_script("run_cicytex_experiment")
    raw_root = tmp_path / "raw"
    _write_normalized(raw_root / "normalizados")
    primary = raw_root / "originales" / "cicytex" / "DTPT_Figure_8.csv"
    primary.parent.mkdir(parents=True)
    primary.write_bytes(b"primary")
    archive = tmp_path / "delivery.zip"
    archive.write_bytes(b"archive")
    output = tmp_path / "output"
    observed: dict[str, object] = {}

    def fake_run(data, destination, dataset_sha256, zip_sha256, tracking_uri, **kwargs):
        observed.update(
            data=data,
            destination=destination,
            dataset_sha256=dataset_sha256,
            zip_sha256=zip_sha256,
            tracking_uri=tracking_uri,
            provenance=kwargs["dataset_provenance"],
        )
        return {"ok": True}

    monkeypatch.setattr(module, "run_experiment", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_cicytex_experiment.py",
            "--raw-root",
            str(raw_root),
            "--zip",
            str(archive),
            "--output",
            str(output),
        ],
    )

    module.main()

    provenance = observed["provenance"]
    assert observed["data"] is provenance.snapshot.dataframe
    assert observed["dataset_sha256"] == provenance.primary_source.sha256
    assert observed["zip_sha256"] == provenance.source_archive.sha256
    assert provenance.snapshot.dataset_sha256 not in {
        observed["dataset_sha256"],
        observed["zip_sha256"],
    }


def test_causal_script_passes_one_typed_snapshot_and_three_distinct_identities(
    monkeypatch, tmp_path: Path
):
    module = _load_script("run_cicytex_causal_ensemble")
    normalized = tmp_path / "normalizados"
    _write_normalized(normalized)
    primary = tmp_path / "DTPT_Figure_8.csv"
    primary.write_bytes(b"primary")
    archive = tmp_path / "delivery.zip"
    archive.write_bytes(b"archive")
    output = tmp_path / "output"
    observed: dict[str, object] = {}

    def fake_run(data, destination, **kwargs):
        observed.update(data=data, destination=destination, **kwargs)
        return {"ok": True}

    monkeypatch.setattr(module, "run_causal_ensemble", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_cicytex_causal_ensemble.py",
            "--normalized-dir",
            str(normalized),
            "--dataset-file",
            str(primary),
            "--zip",
            str(archive),
            "--output-dir",
            str(output),
            "--tracking-uri",
            "",
        ],
    )

    assert module.main() == 0

    provenance = observed["dataset_provenance"]
    assert observed["data"] is provenance.snapshot.dataframe
    assert observed["dataset_sha256"] == provenance.primary_source.sha256
    assert observed["zip_sha256"] == provenance.source_archive.sha256
    assert provenance.snapshot.dataset_sha256 not in {
        observed["dataset_sha256"],
        observed["zip_sha256"],
    }
