"""`bundle.json` records the code identity captured at training time (new runs).

Old bundles without the key must keep loading and report "not registered"
(None); the value is never inferred. Synthetic data only; no holdouts.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from predictive_modeling.operational_inference import load_operational_bundle
from predictive_modeling.operational_run import run_operational_manifest
from predictive_modeling.operational_run_artifacts import persist_operational_run
from tests.test_operational_run import (
    _dataset_sha256,
    _synthetic_frame,
    _synthetic_ready_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def run_result():
    frame = _synthetic_frame()
    fingerprint = _dataset_sha256(frame)
    manifest = _synthetic_ready_manifest(fingerprint)
    return run_operational_manifest(manifest, frame, dataset_sha256=fingerprint)


def _persist(run_result, root: Path) -> Path:
    persist_operational_run(
        run_result,
        output_dir=root / "run",
        run_id="synthetic-code-identity-test",
        manifest_path=root / "fixture.json",
        manifest_identity_sha256="a" * 64,
        dataset_id="synthetic-fixture",
        repo_root=REPO_ROOT,
    )
    return root / "run"


@pytest.fixture(scope="module")
def exported(run_result, tmp_path_factory):
    return _persist(run_result, tmp_path_factory.mktemp("code-identity"))


@pytest.mark.parametrize("horizon", [1, 2, 3])
def test_bundle_json_records_code_identity_matching_run_metadata(exported, horizon):
    bundle_meta = json.loads((exported / f"horizon_{horizon}" / "bundle.json").read_text())
    run_meta = json.loads((exported / "run_metadata.json").read_text())
    assert "code_identity" in bundle_meta
    assert bundle_meta["code_identity"] == run_meta["code_identity"]


def test_persisted_commit_equals_captured_commit(exported):
    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    loaded = load_operational_bundle(
        exported / "horizon_1", sensor_id="synthetic-sensor", horizon=1
    )
    assert loaded.code_identity["available"] is True
    assert loaded.code_identity["commit"] == expected
    assert isinstance(loaded.code_identity["dirty"], bool)


def test_old_bundle_without_code_identity_loads_and_reports_not_registered(exported, tmp_path):
    directory = tmp_path / "bundle"
    shutil.copytree(exported / "horizon_1", directory)
    path = directory / "bundle.json"
    metadata = json.loads(path.read_text())
    del metadata["code_identity"]
    path.write_text(json.dumps(metadata))
    loaded = load_operational_bundle(directory, sensor_id="synthetic-sensor", horizon=1)
    assert loaded.code_identity is None
    assert "code_identity" not in loaded.metadata


def test_git_unavailable_never_invents_a_commit(run_result, tmp_path, monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("predictive_modeling.operational_run_artifacts.subprocess.run", no_git)
    run = _persist(run_result, tmp_path)
    identity = json.loads((run / "horizon_1" / "bundle.json").read_text())["code_identity"]
    assert identity["available"] is False
    assert "commit" not in identity and "dirty" not in identity
    loaded = load_operational_bundle(run / "horizon_1", sensor_id="synthetic-sensor", horizon=1)
    assert loaded.code_identity == identity


def test_code_identity_does_not_alter_artifact_hashes(run_result, tmp_path_factory):
    first = _persist(run_result, tmp_path_factory.mktemp("a"))
    second = _persist(run_result, tmp_path_factory.mktemp("b"))
    meta_a = json.loads((first / "horizon_1" / "bundle.json").read_text())
    meta_b = json.loads((second / "horizon_1" / "bundle.json").read_text())
    assert meta_a["contract"] == meta_b["contract"]
    assert meta_a["files"]["contract.json"] == meta_b["files"]["contract.json"]
