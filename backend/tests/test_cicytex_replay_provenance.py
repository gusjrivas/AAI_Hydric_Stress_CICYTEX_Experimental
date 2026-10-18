import json
from pathlib import Path

from app.dependencies import get_cicytex_replay_provenance
from app.main import app
from fastapi.testclient import TestClient

SUMMARY = (
    Path(__file__).resolve().parents[2] / "results" / "cicytex" / "causal_replay" / "summary.json"
)


def _get(client: TestClient):
    return client.get("/api/v2/cicytex/replay/provenance")


def test_provenance_exposes_the_archived_package_facts_read_only():
    expected = json.loads(SUMMARY.read_text(encoding="utf-8"))

    with TestClient(app) as client:
        response = _get(client)

    assert response.status_code == 200
    body = response.json()
    assert body["dataset_sha256"] == expected["dataset_sha256"]
    assert body["git_commit"] == expected["git_commit"]
    assert body["seed"] == expected["seed"]
    assert body["ensemble_policy"] == expected["ensemble_policy"]
    assert body["mlflow_parent_run_id"] == expected["mlflow_parent_run_id"]
    horizon = body["horizons"]["1"]
    source = expected["horizons"]["1"]
    assert horizon["threshold_train_p20"] == source["threshold_train_p20"]
    assert horizon["split"] == source["split"]
    assert horizon["component_mlflow_runs"] == source["component_mlflow_runs"]


def test_provenance_does_not_leak_results_or_predictions():
    with TestClient(app) as client:
        body = _get(client).json()

    assert "metrics" not in body
    assert "prediction_rows" not in body
    assert "prediction_sha256" not in body or isinstance(body["prediction_sha256"], str)
    for horizon in body["horizons"].values():
        assert set(horizon) == {
            "threshold_train_p20",
            "first_legitimate_emission",
            "split",
            "partition_rows",
            "component_mlflow_runs",
        }


def test_provenance_is_unavailable_when_the_summary_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CICYTEX_REPLAY_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = _get(client)

    assert response.status_code == 503


def test_provenance_endpoint_delegates_to_the_injected_application():
    class Fake:
        def provenance(self) -> dict:
            return {
                "dataset_sha256": "abc",
                "git_commit": "def",
                "seed": 1,
                "proxy": "p",
                "ensemble_policy": "e",
                "mlflow_parent_run_id": "m",
                "prediction_sha256": "s",
                "horizons": {},
            }

    app.dependency_overrides[get_cicytex_replay_provenance] = Fake
    try:
        with TestClient(app) as client:
            response = _get(client)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["dataset_sha256"] == "abc"
