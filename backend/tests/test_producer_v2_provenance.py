"""Procedencia de solo lectura de una emisión v2 (HU6, alerting-ui;
add-emission-provenance-panel).

`GET /api/v2/sensors/{sensor_id}/batches/{batch_id}/provenance` expone una
lista blanca de campos de identidad. Nunca el `input_snapshot` (parquet
base64) ni un commit inferido del checkout actual: lo que no se persistió se
devuelve como `null` ("no registrado").
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from app.config import get_dataset_data_dir, is_producer_v2_enabled
from app.main import app
from fastapi.testclient import TestClient

from human_feedback.operational_repository import (
    OperationalRepository,
    SlotSeed,
    compute_batch_id,
)

CONTRACT_VERSION = "producer_daily_h123_v1"
UTC = timezone.utc
COMMIT = "c" * 40
DATASET_SHA = "d" * 64
ENSEMBLE_SHA = "e" * 64
AS_OF = date(2026, 9, 18)


def _ref(horizon: int, **overrides):
    base = {
        "model_version": f"joblib-sha-{horizon}",
        "horizon_days": horizon,
        "contract_version": CONTRACT_VERSION,
        "trained_through": "2026-09-15",
        "calibration_version": "cal-v1",
        "assessment_reference": None,
    }
    base.update(overrides)
    return base


def _slot(horizon: int, **ref_overrides) -> SlotSeed:
    return SlotSeed(
        horizon_days=horizon,
        status="available",
        alert=True,
        score=0.7,
        score_kind="calibrated_probability",
        display_probability=0.7,
        probability_status="development_assessed",
        probability_reason_code=None,
        decision_threshold=0.5,
        event_threshold={
            "variable": "soil_moisture",
            "value": 0.18,
            "unit": "m3/m3",
            "comparison": "lt",
        },
        model_reference=_ref(horizon, **ref_overrides),
    )


def _seed(tmp_path, sensor_id="sensor-a", *, bundles=None, with_snapshot=True):
    repo = OperationalRepository(tmp_path, sensor_id)
    issued = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    repo.record_batch(
        as_of_date=AS_OF,
        issued_at=issued,
        snapshot_id=DATASET_SHA,
        data_age_days=0,
        provenance="real",
        slots=[
            _slot(1),
            _slot(2),
            SlotSeed(horizon_days=3, status="unavailable", reason_code="model_not_available"),
        ],
        idempotency_key="k1",
        now=issued,
    )
    if with_snapshot:
        document = json.loads(repo.path.read_text(encoding="utf-8"))
        batch_id = compute_batch_id(sensor_id, AS_OF, CONTRACT_VERSION)
        document["batches"][batch_id]["input_snapshot"] = {
            "sha256": DATASET_SHA,
            "parquet_base64": "SECRET-PARQUET-BYTES",
            "bundles": bundles or {},
        }
        repo.path.write_text(json.dumps(document), encoding="utf-8")
    return compute_batch_id(sensor_id, AS_OF, CONTRACT_VERSION)


@pytest.fixture
def client(tmp_path):
    app.dependency_overrides[get_dataset_data_dir] = lambda: tmp_path
    app.dependency_overrides[is_producer_v2_enabled] = lambda: True
    try:
        with TestClient(app) as test_client:
            yield test_client, tmp_path
    finally:
        app.dependency_overrides.clear()


def _url(batch_id, sensor="sensor-a"):
    return f"/api/v2/sensors/{sensor}/batches/{batch_id}/provenance"


def test_new_emission_exposes_code_identity_and_model_reference(client):
    test_client, tmp_path = client
    batch_id = _seed(
        tmp_path,
        bundles={
            "1": {
                "contract": {"horizon_days": 1},
                "code_identity": {"available": True, "commit": COMMIT, "dirty": False},
                "environment": {"python": "3.13"},
            },
            "2": {"code_identity": {"available": True, "commit": COMMIT, "dirty": True}},
        },
    )
    response = test_client.get(_url(batch_id))
    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == batch_id
    assert body["snapshot_id"] == DATASET_SHA
    h1, h2, h3 = body["horizons"]
    assert h1["status"] == "available"
    assert h1["code_identity"] == {"available": True, "commit": COMMIT, "dirty": False}
    assert h1["model_reference"]["model_version"] == "joblib-sha-1"
    assert h1["model_reference"]["trained_through"] == "2026-09-15"
    assert h1["model_reference"]["calibration_version"] == "cal-v1"
    assert h2["code_identity"]["dirty"] is True
    assert h3["status"] == "unavailable"
    assert h3["reason_code"] == "model_not_available"
    assert h3["model_reference"] is None
    assert h3["code_identity"] is None


def test_batch_without_code_identity_is_explicitly_not_registered(client):
    test_client, tmp_path = client
    batch_id = _seed(tmp_path, bundles={"1": {"contract": {"horizon_days": 1}}})
    body = test_client.get(_url(batch_id)).json()
    assert "code_identity" in body["horizons"][0]
    assert body["horizons"][0]["code_identity"] is None
    # sin bundle persistido para el horizonte 2: tampoco se infiere nada
    assert body["horizons"][1]["code_identity"] is None
    assert body["horizons"][1]["mode"] is None


def test_batch_without_input_snapshot_is_not_registered_not_error(client):
    test_client, tmp_path = client
    batch_id = _seed(tmp_path, with_snapshot=False)
    response = test_client.get(_url(batch_id))
    assert response.status_code == 200
    assert response.json()["horizons"][0]["code_identity"] is None


def test_unknown_batch_returns_404_in_existing_error_format(client):
    test_client, _ = client
    response = test_client.get(_url("batch_unknown"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "batch_not_found"


def test_response_never_leaks_input_snapshot_or_unlisted_fields(client):
    test_client, tmp_path = client
    batch_id = _seed(
        tmp_path,
        bundles={
            "1": {
                "code_identity": {
                    "available": True,
                    "commit": COMMIT,
                    "dirty": False,
                    "reason": "C:/secret/path",
                    "extra": "x",
                },
                "environment": {"python": "3.13"},
                "files": {"model.joblib": "abc"},
            }
        },
    )
    raw = test_client.get(_url(batch_id)).text
    for forbidden in (
        "SECRET-PARQUET-BYTES",
        "parquet_base64",
        "input_snapshot",
        "C:/secret",
        "environment",
        "files",
    ):
        assert forbidden not in raw
    body = json.loads(raw)
    assert set(body) == {
        "batch_id",
        "sensor_id",
        "as_of_date",
        "contract_version",
        "snapshot_id",
        "horizons",
        "not_persisted",
    }
    assert set(body["horizons"][0]) == {
        "horizon_days",
        "status",
        "reason_code",
        "mode",
        "model_reference",
        "ensemble_identity_sha256",
        "code_identity",
        "components",
    }
    assert set(body["horizons"][0]["code_identity"]) == {"available", "commit", "dirty"}


def test_ensemble_identity_and_component_code_identity(client):
    test_client, tmp_path = client
    batch_id = _seed(
        tmp_path,
        bundles={
            "1": {
                "mode": "ensemble",
                "ensemble_manifest": {"contract_version": CONTRACT_VERSION},
                "components": {
                    "random_forest": {
                        "code_identity": {"available": True, "commit": COMMIT, "dirty": False}
                    },
                    "logistic_regression": {},
                },
            }
        },
    )
    repo = OperationalRepository(tmp_path, "sensor-a")
    document = json.loads(repo.path.read_text(encoding="utf-8"))
    forecast_id = document["batches"][batch_id]["slots"]["1"]["forecast_id"]
    document["forecasts"][forecast_id]["ensemble"] = {"ensemble_identity_sha256": ENSEMBLE_SHA}
    repo.path.write_text(json.dumps(document), encoding="utf-8")

    h1 = test_client.get(_url(batch_id)).json()["horizons"][0]
    assert h1["mode"] == "ensemble"
    assert h1["ensemble_identity_sha256"] == ENSEMBLE_SHA
    assert h1["code_identity"] is None
    by_family = {c["family"]: c["code_identity"] for c in h1["components"]}
    assert by_family["random_forest"] == {"available": True, "commit": COMMIT, "dirty": False}
    assert by_family["logistic_regression"] is None


def test_declares_fields_that_are_not_persisted(client):
    test_client, tmp_path = client
    batch_id = _seed(tmp_path)
    body = test_client.get(_url(batch_id)).json()
    assert body["not_persisted"] == ["full_config", "mlflow_run", "seed"]


def test_provenance_is_read_only_and_does_not_modify_the_repository(client):
    test_client, tmp_path = client
    batch_id = _seed(tmp_path)
    path = OperationalRepository(tmp_path, "sensor-a").path
    before = path.read_bytes()
    assert test_client.get(_url(batch_id)).status_code == 200
    assert path.read_bytes() == before
    assert test_client.post(_url(batch_id)).status_code == 405


def test_batch_of_another_sensor_is_not_found_under_this_sensor(client):
    test_client, tmp_path = client
    batch_id = _seed(tmp_path, "sensor-a")
    _seed(tmp_path, "sensor-b")
    other = test_client.get(_url(batch_id, "sensor-c"))
    assert other.status_code == 404
    assert other.json()["error"]["code"] == "batch_not_found"
    # un archivo de otro sensor copiado bajo este: el lote debe pertenecer al sensor de la ruta
    repo_a = OperationalRepository(tmp_path, "sensor-a")
    repo_c = OperationalRepository(tmp_path, "sensor-c")
    repo_c.path.write_bytes(repo_a.path.read_bytes())
    mismatched = test_client.get(_url(batch_id, "sensor-c"))
    assert mismatched.status_code == 404
    assert mismatched.json()["error"]["code"] == "batch_not_found"
