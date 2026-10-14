"""Pruebas de la API de solo lectura de reproducción histórica (spec
`historical-replay`, Paso 3). Usa el paquete real autorizado
(`replay_packages/base-seed4-1157696b7b-v2`, ya construido y validado en
pasos anteriores) como fixture de lectura — no genera datos científicos
nuevos, no ejecuta modelos. Un paquete forjado y autodeclarado se construye
aparte, identificado explícitamente como dato de prueba, para el caso de
candidato no autorizado.
"""

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from app.config import (
    get_historical_replay_feedback_database,
    get_historical_replay_package_dir,
    is_historical_replay_enabled,
)
from app.main import app
from fastapi.testclient import TestClient

REAL_PACKAGE_DIR = (
    Path(__file__).resolve().parents[2] / "replay_packages" / "base-seed4-1157696b7b-v2"
)
# Del propio manifiesto/predictions.json real: primera predicción del
# recorrido, horizonte +3 días.
REAL_ORIGIN = "2024-10-19"
REAL_TARGET = "2024-10-22"


def _client_with_real_package(feedback_dir: Path | None = None):
    app.dependency_overrides[get_historical_replay_package_dir] = lambda: REAL_PACKAGE_DIR
    app.dependency_overrides[is_historical_replay_enabled] = lambda: True
    if feedback_dir is not None:
        app.dependency_overrides[get_historical_replay_feedback_database] = lambda: (
            feedback_dir / "historical_feedback.sqlite3"
        )
    return TestClient(app)


def _clear_overrides():
    app.dependency_overrides.clear()


def _package_files_fingerprint() -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in REAL_PACKAGE_DIR.glob("*.json")
    }


def test_candidate_endpoint_reports_authorized_run_and_disclaimers():
    client = _client_with_real_package()
    try:
        response = client.get("/replay/candidate")
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == "1157696b7bb941e394c5af530c762b07"
        assert body["config_name"] == "base"
        assert body["horizon_days"] == 3
        assert body["disclaimers"]["reproduccion_retrospectiva"] is True
        assert body["disclaimers"]["proxy_estadistico_relativo"] is True
        assert body["disclaimers"]["utilidad_agronomica_demostrada"] is False
        assert body["periodo_inicio"] == REAL_ORIGIN
        assert len(body["limitaciones"]) > 0
    finally:
        _clear_overrides()


def test_prediction_hidden_before_its_origin():
    client = _client_with_real_package()
    try:
        response = client.get(
            f"/replay/predictions/{REAL_ORIGIN}", params={"simulated_date": "2024-10-18"}
        )
        assert response.status_code == 404
    finally:
        _clear_overrides()


def test_prediction_visible_from_origin_without_future_fields():
    client = _client_with_real_package()
    try:
        response = client.get(
            f"/replay/predictions/{REAL_ORIGIN}", params={"simulated_date": REAL_ORIGIN}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["timestamp_origen"] == REAL_ORIGIN
        assert body["target_timestamp"] == REAL_TARGET
        assert "y_pred" in body
        # Ausencia efectiva de campos futuros: el campo no está en el JSON
        # en absoluto (ni siquiera como null) — response_model_exclude_none.
        for forbidden in ("target_observed", "y_true", "coincide", "medicion_original"):
            assert forbidden not in body
        assert "y_proba" not in body  # nunca expuesto en esta API
    finally:
        _clear_overrides()


def test_observation_revealed_exactly_at_target_date():
    client = _client_with_real_package()
    try:
        response = client.get(
            f"/replay/predictions/{REAL_ORIGIN}", params={"simulated_date": REAL_TARGET}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["target_observed"] is True
        assert body["y_true"] is not None
        assert body["coincide"] in (True, False)
        assert body["medicion_original"]["estado"] == "medida"
        assert body["medicion_original"]["valor"] is not None
    finally:
        _clear_overrides()


def test_rewinding_hides_the_observation_again():
    client = _client_with_real_package()
    try:
        after = client.get(
            f"/replay/predictions/{REAL_ORIGIN}", params={"simulated_date": REAL_TARGET}
        )
        assert after.json()["target_observed"] is True

        before_again = client.get(
            f"/replay/predictions/{REAL_ORIGIN}", params={"simulated_date": "2024-10-20"}
        )
        body = before_again.json()
        assert "target_observed" not in body
        assert "y_true" not in body
    finally:
        _clear_overrides()


def test_history_is_filtered_by_the_simulated_clock():
    client = _client_with_real_package()
    try:
        response = client.get("/replay/history", params={"simulated_date": "2024-01-05"})
        assert response.status_code == 200
        body = response.json()
        assert body["simulated_date"] == "2024-01-05"
        fechas = [row["fecha"] for row in body["rows"]]
        assert fechas == sorted(fechas)
        assert fechas[-1] == "2024-01-05"
        assert all(fecha <= "2024-01-05" for fecha in fechas)
    finally:
        _clear_overrides()


def test_history_rows_expose_estado_and_causa():
    client = _client_with_real_package()
    try:
        response = client.get("/replay/history", params={"simulated_date": "2024-10-19"})
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert len(rows) > 0
        for row in rows:
            assert row["estado"] in ("medida", "imputada", "no_determinado", "sin_dato_en_fuente")
            if row["soil_moisture"] is not None:
                # Un valor crudo presente nunca se etiqueta "imputada": es
                # siempre "medida", sin importar ningún marcador (RH-05).
                assert row["estado"] == "medida"
                assert row["causa"] is None
            if row["estado"] != "medida":
                assert row["causa"] is not None and row["causa"] != ""

        # El paquete real tiene huecos genuinos rellenados por
        # interpolate_missing_causal: al menos una fila real debe quedar en
        # "imputada", con soil_moisture null y el valor derivado en el
        # campo separado (nunca dentro de soil_moisture).
        imputed_rows = [row for row in rows if row["estado"] == "imputada"]
        assert len(imputed_rows) > 0
        for row in imputed_rows:
            assert row["soil_moisture"] is None
            assert row["valor_imputado"] is not None
    finally:
        _clear_overrides()


def test_history_estado_becomes_no_determinado_under_imputation_source_drift(monkeypatch):
    from historical_replay import imputation_markers

    monkeypatch.setitem(
        imputation_markers._VERIFIED_SOURCE_SHA256,
        "data_quality.imputation",
        "0" * 64,
    )
    client = _client_with_real_package()
    try:
        response = client.get("/replay/history", params={"simulated_date": "2024-10-19"})
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert len(rows) > 0
        for row in rows:
            if row["soil_moisture"] is None:
                assert row["estado"] == "no_determinado"
                assert "ImputationSourceDriftError" in row["causa"]
            else:
                assert row["estado"] == "medida"
    finally:
        _clear_overrides()


def test_history_response_is_unaffected_by_dates_after_the_simulated_clock():
    """Ampliar el reloj simulado (que revela más filas del dataset
    empaquetado a reconstruct_imputation_markers) no debe cambiar ninguna
    fila ya devuelta antes del corte anterior — ni su soil_moisture, ni su
    estado, ni su causa (interpolate_missing_causal es forward-fill puro:
    el estado de una fecha depende solo de fechas iguales o anteriores)."""
    client = _client_with_real_package()
    try:
        early = client.get("/replay/history", params={"simulated_date": "2024-10-19"}).json()
        later = client.get("/replay/history", params={"simulated_date": "2024-12-31"}).json()
        assert len(later["rows"]) > len(early["rows"])
        assert later["rows"][: len(early["rows"])] == early["rows"]
    finally:
        _clear_overrides()


def test_unknown_prediction_identity_is_rejected():
    client = _client_with_real_package()
    try:
        response = client.get(
            "/replay/predictions/2019-01-01", params={"simulated_date": "2024-10-19"}
        )
        assert response.status_code == 404
    finally:
        _clear_overrides()


def test_disabled_by_default_returns_not_found(monkeypatch):
    # Sin overrides: el feature flag real (`HISTORICAL_REPLAY_ENABLED`) está
    # apagado por defecto, igual que `PRODUCER_V2_ENABLED`.
    monkeypatch.delenv("HISTORICAL_REPLAY_ENABLED", raising=False)
    client = TestClient(app)
    response = client.get("/replay/candidate")
    assert response.status_code == 404


def test_self_declared_unauthorized_candidate_is_rejected(tmp_path):
    # Paquete forjado, identificado como dato de prueba: autodeclara su
    # propia admisión (mismo patrón que un candidato real), pero no es el
    # admitido por la política externa. La API debe rechazarlo (503,
    # "paquete inválido"), no servir sus datos.
    forged_dir = tmp_path / "forged-package"
    shutil.copytree(REAL_PACKAGE_DIR, forged_dir)
    manifest_path = forged_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["candidate"]["run_id_child"] = "un-run-jamas-revisado"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    # No se recalculan los hashes de custodia del resto de archivos porque
    # ni siquiera se llega a verificarlos: la política de admisión se
    # comprueba contra run_metadata.json, que el lector procesa antes.
    # Alterar manifest.json además invalida su propio... en realidad
    # manifest.json no figura en su propio inventario de hashes, así que
    # esta alteración no dispara IntegrityError antes de llegar a admisión.

    app.dependency_overrides[get_historical_replay_package_dir] = lambda: forged_dir
    app.dependency_overrides[is_historical_replay_enabled] = lambda: True
    try:
        client = TestClient(app)
        response = client.get("/replay/candidate")
        assert response.status_code == 503
    finally:
        _clear_overrides()


def test_original_package_files_are_never_modified_by_the_api():
    fingerprint_before = _package_files_fingerprint()
    client = _client_with_real_package()
    try:
        client.get("/replay/candidate")
        client.get(f"/replay/predictions/{REAL_ORIGIN}", params={"simulated_date": REAL_TARGET})
        client.get(f"/replay/predictions/{REAL_ORIGIN}", params={"simulated_date": "2024-10-20"})
        client.get("/replay/history", params={"simulated_date": "2024-06-01"})
    finally:
        _clear_overrides()
    assert _package_files_fingerprint() == fingerprint_before


def test_reproduction_works_without_mlflow_or_network(monkeypatch):
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError("La API de reproducción no debe intentar conexiones de red.")

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)

    client = _client_with_real_package()
    try:
        response = client.get("/replay/candidate")
        assert response.status_code == 200
    finally:
        _clear_overrides()


def test_candidate_includes_expandable_evidence_card():
    client = _client_with_real_package()
    try:
        body = client.get("/replay/candidate").json()
        evidencia = body["evidencia"]
        assert evidencia["package_id"] == "base-seed4-1157696b7b-v2"
        assert evidencia["dataset_name"] == "melchor_romero_2024_consolidado"
        assert evidencia["commit_sha"] == "2a40ee68c52d2eb5e2040a36b1029f756f9c048a"
        assert evidencia["split_date"] == "2024-10-19"
        assert "supuesto" in evidencia["issuance_assumption"].lower()
        # Paso 4.1 §3: split_date (corte de partición) no es necesariamente
        # la última fecha usada para entrenar — deben distinguirse.
        assert evidencia["training_max_date"] == "2024-10-15"
        assert evidencia["training_max_date"] != evidencia["split_date"]
    finally:
        _clear_overrides()


def test_candidate_exposes_the_verified_label_rule():
    client = _client_with_real_package()
    try:
        body = client.get("/replay/candidate").json()
        rule = body["regla_etiqueta"]
        # Del manifiesto real: label_rule.rule ==
        # "observed_value_at_t_plus_h_less_than_frozen_threshold".
        assert rule["variable"] == "soil_moisture"
        assert rule["unidad"] == "m3/m3"
        assert rule["operador"] == "less_than"
        assert abs(rule["umbral"] - 0.31678178906440735) < 1e-9
    finally:
        _clear_overrides()


def test_list_origins_returns_only_minimal_metadata():
    client = _client_with_real_package()
    try:
        response = client.get("/replay/predictions")
        assert response.status_code == 200
        body = response.json()
        origins = [o["timestamp_origen"] for o in body["origins"]]
        assert REAL_ORIGIN in origins
        assert origins == sorted(origins)
        # Solo metadatos mínimos: ningún campo de observación/resultado.
        assert set(body["origins"][0].keys()) == {"timestamp_origen"}
    finally:
        _clear_overrides()


def test_feedback_rejected_before_reveal(tmp_path):
    client = _client_with_real_package(feedback_dir=tmp_path)
    try:
        response = client.post(
            f"/replay/predictions/{REAL_ORIGIN}/feedback",
            json={"simulated_date": "2024-10-20", "estado_validacion": "confirmada"},
        )
        assert response.status_code == 409
    finally:
        _clear_overrides()


def test_feedback_registered_after_reveal_is_visible_and_isolated(tmp_path):
    client = _client_with_real_package(feedback_dir=tmp_path)
    try:
        create = client.post(
            f"/replay/predictions/{REAL_ORIGIN}/feedback",
            json={
                "simulated_date": REAL_TARGET,
                "estado_validacion": "confirmada",
                "observacion": "Coincide con lo observado en el lote.",
            },
        )
        assert create.status_code == 201
        body = create.json()
        assert body["simulated_at"] == REAL_TARGET
        assert body["registered_at"] is not None

        visible = client.get(
            f"/replay/predictions/{REAL_ORIGIN}/feedback", params={"simulated_date": REAL_TARGET}
        )
        assert len(visible.json()["feedback"]) == 1

        # Aislado: el feedback vive en su propia base, nunca en el
        # paquete científico ni en el store operativo del sensor.
        feedback_database = tmp_path / "historical_feedback.sqlite3"
        assert feedback_database.is_file()
        assert list(tmp_path.glob("*.jsonl")) == []
    finally:
        _clear_overrides()


def test_corrupt_historical_feedback_returns_sanitized_503(tmp_path):
    database = tmp_path / "historical_feedback.sqlite3"
    client = _client_with_real_package(feedback_dir=tmp_path)
    marker = "private-historical-corruption-marker"
    try:
        created = client.post(
            f"/replay/predictions/{REAL_ORIGIN}/feedback",
            json={"simulated_date": REAL_TARGET, "estado_validacion": "confirmada"},
        )
        assert created.status_code == 201
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE historical_feedback SET registered_at=?",
                (marker,),
            )
        response = client.get(
            f"/replay/predictions/{REAL_ORIGIN}/feedback",
            params={"simulated_date": REAL_TARGET},
        )
    finally:
        client.close()
        _clear_overrides()

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "http_error"
    assert error["message"] == "El almacenamiento de feedback historico no esta disponible"
    assert str(database) not in response.text
    assert marker not in response.text
    assert "historical_feedback" not in response.text


def test_feedback_hidden_again_after_rewinding_but_not_deleted(tmp_path):
    client = _client_with_real_package(feedback_dir=tmp_path)
    try:
        client.post(
            f"/replay/predictions/{REAL_ORIGIN}/feedback",
            json={"simulated_date": REAL_TARGET, "estado_validacion": "confirmada"},
        )
        hidden = client.get(
            f"/replay/predictions/{REAL_ORIGIN}/feedback", params={"simulated_date": "2024-10-20"}
        )
        assert hidden.json()["feedback"] == []

        # El registro persiste: al reavanzar el reloj vuelve a verse.
        revealed_again = client.get(
            f"/replay/predictions/{REAL_ORIGIN}/feedback", params={"simulated_date": REAL_TARGET}
        )
        assert len(revealed_again.json()["feedback"]) == 1
    finally:
        _clear_overrides()


def test_feedback_rejects_unknown_prediction_identity(tmp_path):
    client = _client_with_real_package(feedback_dir=tmp_path)
    try:
        response = client.post(
            "/replay/predictions/2019-01-01/feedback",
            json={"simulated_date": "2024-10-22", "estado_validacion": "confirmada"},
        )
        assert response.status_code == 404
    finally:
        _clear_overrides()
