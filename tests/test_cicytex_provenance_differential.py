import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest

from experiment_runner.cicytex.dataset_contract import CICYTEX_NORMALIZED_V1
from experiment_runner.cicytex.experiment import FEATURES


def _write_dataset(root: Path) -> None:
    timestamps = pd.date_range("2023-01-01", periods=120, freq="D")
    for sensor_index, sensor_id in enumerate(CICYTEX_NORMALIZED_V1.sensor_ids):
        values = [0.12 + ((day + sensor_index) % 10) / 100 for day in range(len(timestamps))]
        pd.DataFrame(
            {
                "timestamp": timestamps,
                "soil_moisture": values,
                "sensor_id": sensor_id,
            }
        ).to_csv(root / CICYTEX_NORMALIZED_V1.file_name_for(sensor_id), index=False)


def _provenance(root: Path):
    ingestion = importlib.import_module("experiment_runner.cicytex.ingestion")
    load_snapshot = getattr(ingestion, "load_normalized_cicytex_snapshot")
    build_provenance = getattr(ingestion, "build_cicytex_dataset_provenance")
    legacy_snapshot = load_snapshot(root)
    enriched_snapshot = load_snapshot(root)
    primary = root.parent / "primary.csv"
    archive = root.parent / "source.zip"
    primary.write_bytes(b"primary")
    archive.write_bytes(b"archive")
    return (
        legacy_snapshot,
        enriched_snapshot,
        build_provenance(enriched_snapshot, primary, archive),
    )


class _Run:
    def __init__(self, run_id: str):
        self.info = SimpleNamespace(run_id=run_id)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def _install_deterministic_runtime(monkeypatch, module):
    counter = {"value": 0}

    def reset() -> None:
        counter["value"] = 0

    def start_run(**_kwargs):
        counter["value"] += 1
        return _Run(f"run-{counter['value']}")

    monkeypatch.setattr(module.mlflow, "start_run", start_run)
    for name in (
        "set_tracking_uri",
        "set_experiment",
        "log_params",
        "log_metrics",
        "log_artifact",
        "log_artifacts",
    ):
        monkeypatch.setattr(module.mlflow, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.subprocess, "check_output", lambda *_args, **_kwargs: "stable\n")
    return reset


def _strip_additive_provenance(payload: dict) -> dict:
    result = dict(payload)
    result.pop("dataset_provenance", None)
    result.pop("normalized_dataset_sha256", None)
    return result


def _parameter_signature(model) -> dict[str, object]:
    signature: dict[str, object] = {}
    for name, value in model.get_params(deep=True).items():
        if value is None or isinstance(value, (bool, int, float, str)):
            signature[name] = value
        elif isinstance(value, tuple) and all(
            item is None or isinstance(item, (bool, int, float, str)) for item in value
        ):
            signature[name] = value
        else:
            signature[name] = f"{type(value).__module__}.{type(value).__qualname__}"
    return signature


def _assert_models_semantically_equal(left_path: Path, right_path: Path) -> None:
    left = joblib.load(left_path)
    right = joblib.load(right_path)
    assert type(right) is type(left)
    assert _parameter_signature(right) == _parameter_signature(left)
    feature_count = len(FEATURES)
    probe = pd.DataFrame(
        np.vstack(
            [
                np.zeros(feature_count),
                np.full(feature_count, 0.25),
                np.arange(feature_count, dtype=float) / max(feature_count, 1),
            ]
        ),
        columns=FEATURES,
    )
    np.testing.assert_allclose(
        right.predict_proba(probe),
        left.predict_proba(probe),
        rtol=0,
        atol=0,
    )


def _assert_common_artifacts_equal(legacy: Path, enriched: Path) -> None:
    legacy_files = {
        path.relative_to(legacy).as_posix() for path in legacy.rglob("*") if path.is_file()
    }
    enriched_files = {
        path.relative_to(enriched).as_posix() for path in enriched.rglob("*") if path.is_file()
    }
    assert enriched_files == legacy_files | {"cicytex_dataset_provenance.json"}
    assert "cicytex_dataset_provenance.json" not in legacy_files

    for relative in sorted(legacy_files):
        left = legacy / relative
        right = enriched / relative
        if relative == "summary.json":
            assert _strip_additive_provenance(
                json.loads(right.read_text(encoding="utf-8"))
            ) == json.loads(left.read_text(encoding="utf-8"))
        elif relative.endswith(".joblib"):
            _assert_models_semantically_equal(left, right)
        else:
            assert right.read_bytes() == left.read_bytes(), relative


@pytest.mark.parametrize("runner_name", ["experiment", "causal_ensemble"])
def test_enriched_runner_is_strictly_additive_to_legacy_outputs(
    runner_name: str, monkeypatch, tmp_path: Path
):
    normalized = tmp_path / "normalizados"
    normalized.mkdir()
    _write_dataset(normalized)
    legacy_snapshot, enriched_snapshot, provenance = _provenance(normalized)
    module = importlib.import_module(f"experiment_runner.cicytex.{runner_name}")
    reset_runtime = _install_deterministic_runtime(monkeypatch, module)
    runner = getattr(
        module, "run_experiment" if runner_name == "experiment" else "run_causal_ensemble"
    )
    legacy_dir = tmp_path / "legacy"
    enriched_dir = tmp_path / "enriched"
    kwargs = {
        "dataset_sha256": provenance.primary_source.sha256,
        "zip_sha256": provenance.source_archive.sha256,
        "tracking_uri": None,
    }

    legacy_result = runner(legacy_snapshot.dataframe, legacy_dir, **kwargs)
    reset_runtime()
    enriched_result = runner(
        enriched_snapshot.dataframe,
        enriched_dir,
        **kwargs,
        dataset_provenance=provenance,
    )

    assert _strip_additive_provenance(enriched_result) == legacy_result
    _assert_common_artifacts_equal(legacy_dir, enriched_dir)
