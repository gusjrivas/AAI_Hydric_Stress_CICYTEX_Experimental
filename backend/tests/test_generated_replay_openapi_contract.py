from __future__ import annotations

from copy import deepcopy

from app.dependencies import (
    get_cicytex_catalog_application,
    get_cicytex_feedback_application,
    get_cicytex_replay_application,
)
from app.main import app
from app.routers.replay import router as historical_replay_router
from fastapi.testclient import TestClient

CATALOG_RESPONSE = {
    "sensors": ["CP1_S1"],
    "emission_dates": ["2023-07-06"],
    "emission_dates_by_horizon": {
        "1": ["2023-07-06"],
        "2": [],
        "3": [],
    },
    "horizons": [1],
    "first_legitimate_emission": "2023-07-06",
    "last_observation": "2023-07-25",
}
PARTIAL_HORIZON_CATALOG_RESPONSE = {
    **CATALOG_RESPONSE,
    "emission_dates_by_horizon": {"1": ["2023-07-06"]},
}
SESSION_RESPONSE = {
    "session_id": "contract-session",
    "sensor_id": "CP1_S1",
    "emission_date": "2023-07-06",
    "horizon_days": 1,
    "revealed_through": "2023-07-06",
    "threshold": 0.21,
    "proxy_notice": "P20 estimado solo con entrenamiento; no es estres fisiologico observado.",
    "predictions": [
        {
            "method": "ensemble",
            "score": 0.75,
            "alert": True,
            "target_date": "2023-07-07",
            "observed_soil_moisture": None,
            "observed_label": None,
            "outcome": None,
        }
    ],
    "readings": [{"date": "2023-07-06", "soil_moisture": 0.25}],
    "metrics": {
        "ensemble": {
            "n": 1,
            "tp": 1,
            "tn": 0,
            "fp": 0,
            "fn": 0,
            "mcc": None,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "coverage": 1.0,
        }
    },
    "feedback": None,
    "can_advance": True,
}
FEEDBACK_RESPONSE = {
    "estado_validacion": "confirmada",
    "etiqueta_corregida": None,
    "observacion": None,
    "registered_at": "2026-10-15T04:30:00+00:00",
    "simulated_at": "2023-07-07",
    "scope": "demostracion; no recalibra ni reentrena",
}


class _CatalogApplication:
    def catalog(self):
        return deepcopy(CATALOG_RESPONSE)


class _PartialHorizonCatalogApplication:
    def catalog(self):
        return deepcopy(PARTIAL_HORIZON_CATALOG_RESPONSE)


class _ReplayApplication:
    def create_session(self, **_selection):
        return deepcopy(SESSION_RESPONSE)

    def get_session(self, _session_id):
        return deepcopy(SESSION_RESPONSE)

    def advance_session(self, _session_id):
        return deepcopy(SESSION_RESPONSE)

    def reset_session(self, _session_id):
        return deepcopy(SESSION_RESPONSE)


class _FeedbackApplication:
    def create_feedback(self, _session_id, **_feedback):
        return deepcopy(FEEDBACK_RESPONSE)


def _response_schema(document: dict, path: str, method: str, status: int) -> dict:
    return document["paths"][path][method]["responses"][str(status)]["content"]["application/json"][
        "schema"
    ]


def _assert_closed_schema_graph(schema: dict, components: dict, seen: set[str]) -> None:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        if name in seen:
            return
        seen.add(name)
        _assert_closed_schema_graph(components[name], components, seen)
        return
    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False
    for key in ("properties",):
        for child in schema.get(key, {}).values():
            _assert_closed_schema_graph(child, components, seen)
    for key in ("items",):
        child = schema.get(key)
        if isinstance(child, dict):
            _assert_closed_schema_graph(child, components, seen)
    for key in ("anyOf", "oneOf", "allOf"):
        for child in schema.get(key, []):
            _assert_closed_schema_graph(child, components, seen)


def _allows_explicit_null(schema: dict) -> bool:
    return any(option.get("type") == "null" for option in schema.get("anyOf", []))


def test_cicytex_success_responses_use_six_closed_nominal_schema_families():
    document = app.openapi()
    components = document["components"]["schemas"]
    expected_components = {
        "CicytexCatalogResponse",
        "CicytexSessionResponse",
        "CicytexPredictionResponse",
        "CicytexReadingResponse",
        "CicytexMetricResponse",
        "CicytexFeedbackResponse",
    }
    assert expected_components <= components.keys()

    expected_route_models = {
        ("/api/v2/cicytex/replay/catalog", "get", 200): "CicytexCatalogResponse",
        ("/api/v2/cicytex/replay/sessions", "post", 201): "CicytexSessionResponse",
        ("/api/v2/cicytex/replay/sessions/{session_id}", "get", 200): ("CicytexSessionResponse"),
        ("/api/v2/cicytex/replay/sessions/{session_id}/advance", "post", 200): (
            "CicytexSessionResponse"
        ),
        ("/api/v2/cicytex/replay/sessions/{session_id}/reset", "post", 200): (
            "CicytexSessionResponse"
        ),
        ("/api/v2/cicytex/replay/sessions/{session_id}/feedback", "post", 201): (
            "CicytexFeedbackResponse"
        ),
    }
    for route, expected_name in expected_route_models.items():
        path, method, status = route
        assert _response_schema(document, path, method, status) == {
            "$ref": f"#/components/schemas/{expected_name}"
        }

    for name in expected_components:
        assert components[name].get("additionalProperties") is False
    _assert_closed_schema_graph(
        {"$ref": "#/components/schemas/CicytexSessionResponse"}, components, set()
    )
    _assert_closed_schema_graph(
        {"$ref": "#/components/schemas/CicytexCatalogResponse"}, components, set()
    )


def test_nullable_replay_fields_are_explicit_and_feedback_states_are_one_literal_contract():
    document = app.openapi()
    components = document["components"]["schemas"]
    prediction = components["CicytexPredictionResponse"]
    session = components["CicytexSessionResponse"]

    for field in ("observed_soil_moisture", "observed_label", "outcome"):
        assert field in prediction["required"]
        assert _allows_explicit_null(prediction["properties"][field])
    assert "feedback" in session["required"]
    assert _allows_explicit_null(session["properties"]["feedback"])

    expected_states = ["confirmada", "rechazada"]
    request_states = components["ReplayFeedbackRequest"]["properties"]["estado_validacion"]
    entry_states = components["ReplayFeedbackEntry"]["properties"]["estado_validacion"]
    cicytex_states = components["CicytexFeedbackResponse"]["properties"]["estado_validacion"]
    assert request_states["enum"] == expected_states
    assert entry_states["enum"] == expected_states
    assert cicytex_states["enum"] == expected_states

    historical_route = next(
        route
        for route in historical_replay_router.routes
        if getattr(route, "path", None) == "/replay/predictions/{timestamp_origen}"
        and "GET" in getattr(route, "methods", set())
    )
    assert historical_route.response_model_exclude_none is True


def test_catalog_horizon_keys_are_closed_but_individually_optional_in_openapi():
    document = app.openapi()
    horizon_map = document["components"]["schemas"]["CicytexEmissionDatesByHorizon"]

    assert horizon_map["additionalProperties"] is False
    assert set(horizon_map["properties"]) == {"1", "2", "3"}
    assert horizon_map.get("required", []) == []


def test_partial_catalog_horizon_map_remains_an_exact_successful_http_response():
    app.dependency_overrides[get_cicytex_catalog_application] = (
        lambda: _PartialHorizonCatalogApplication()
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v2/cicytex/replay/catalog")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == PARTIAL_HORIZON_CATALOG_RESPONSE


def test_cicytex_http_statuses_payloads_and_explicit_nulls_remain_byte_for_byte_compatible():
    app.dependency_overrides[get_cicytex_catalog_application] = lambda: _CatalogApplication()
    app.dependency_overrides[get_cicytex_replay_application] = lambda: _ReplayApplication()
    app.dependency_overrides[get_cicytex_feedback_application] = lambda: _FeedbackApplication()
    try:
        with TestClient(app) as client:
            responses = (
                (client.get("/api/v2/cicytex/replay/catalog"), 200, CATALOG_RESPONSE),
                (
                    client.post(
                        "/api/v2/cicytex/replay/sessions",
                        json={
                            "sensor_id": "CP1_S1",
                            "emission_date": "2023-07-06",
                            "horizon_days": 1,
                        },
                    ),
                    201,
                    SESSION_RESPONSE,
                ),
                (
                    client.get("/api/v2/cicytex/replay/sessions/contract-session"),
                    200,
                    SESSION_RESPONSE,
                ),
                (
                    client.post("/api/v2/cicytex/replay/sessions/contract-session/advance"),
                    200,
                    SESSION_RESPONSE,
                ),
                (
                    client.post("/api/v2/cicytex/replay/sessions/contract-session/reset"),
                    200,
                    SESSION_RESPONSE,
                ),
                (
                    client.post(
                        "/api/v2/cicytex/replay/sessions/contract-session/feedback",
                        json={"estado_validacion": "confirmada"},
                    ),
                    201,
                    FEEDBACK_RESPONSE,
                ),
            )
    finally:
        app.dependency_overrides.clear()

    for response, status, expected in responses:
        assert response.status_code == status
        assert response.json() == expected
    prediction = responses[1][0].json()["predictions"][0]
    assert prediction["observed_soil_moisture"] is None
    assert prediction["observed_label"] is None
    assert prediction["outcome"] is None
    assert responses[1][0].json()["feedback"] is None
