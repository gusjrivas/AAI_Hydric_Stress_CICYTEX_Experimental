from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SOURCE = ROOT / "frontend" / "src"
HISTORICAL_API = FRONTEND_SOURCE / "features" / "historical-replay" / "api.ts"
CICYTEX_API = FRONTEND_SOURCE / "features" / "defense" / "cicytexApi.ts"
QUALITY_API = FRONTEND_SOURCE / "features" / "quality" / "api.ts"
LINEAGE_API = FRONTEND_SOURCE / "features" / "lineage" / "api.ts"
SENSOR_LAB_API = FRONTEND_SOURCE / "features" / "lab" / "sensorLabApi.ts"
FORECAST_API = FRONTEND_SOURCE / "features" / "forecast" / "api.ts"
GENERATED_IMPORT = "../../api/generated/schema"

EXPECTED_OPERATION_IDS = {
    HISTORICAL_API: {
        "get_candidate_replay_candidate_get",
        "list_origins_replay_predictions_get",
        "get_prediction_replay_predictions__timestamp_origen__get",
        "get_history_replay_history_get",
        "get_feedback_replay_predictions__timestamp_origen__feedback_get",
        "create_feedback_replay_predictions__timestamp_origen__feedback_post",
    },
    CICYTEX_API: {
        "catalog_api_v2_cicytex_replay_catalog_get",
        "create_session_api_v2_cicytex_replay_sessions_post",
        "advance_api_v2_cicytex_replay_sessions__session_id__advance_post",
        "reset_api_v2_cicytex_replay_sessions__session_id__reset_post",
        "create_feedback_api_v2_cicytex_replay_sessions__session_id__feedback_post",
    },
}

EXPECTED_EXPORTS = {
    HISTORICAL_API: {
        "ReplayDisclaimers",
        "ReplayEvidenceCard",
        "ReplayLabelRule",
        "ReplayCandidateInfo",
        "ReplayOriginsResponse",
        "MedicionOriginal",
        "ReplayPredictionResponse",
        "ReplayHistoryRow",
        "ReplayHistoryResponse",
        "EstadoValidacion",
        "ReplayFeedbackEntry",
        "ReplayFeedbackListResponse",
        "ReplayNotFoundError",
        "ReplayNotYetRevealedError",
        "ReplayApiError",
        "getCandidate",
        "listOrigins",
        "getPrediction",
        "getHistory",
        "getFeedback",
        "createFeedback",
    },
    CICYTEX_API: {
        "CicytexCatalog",
        "ReplayPrediction",
        "ReplayMetric",
        "ReplayFeedback",
        "CicytexSession",
        "getCicytexCatalog",
        "createCicytexSession",
        "advanceCicytexSession",
        "resetCicytexSession",
        "submitCicytexFeedback",
    },
}


def _productive_typescript_sources() -> list[Path]:
    return [
        path
        for path in FRONTEND_SOURCE.rglob("*.ts*")
        if ".test." not in path.name
        and not path.name.endswith(".d.ts")
        and "generated" not in path.parts
    ]


def _generated_schema_consumers() -> set[Path]:
    consumers = set()
    for path in _productive_typescript_sources():
        source = path.read_text(encoding="utf-8")
        if re.search(r"from\s+['\"][^'\"]*api/generated/schema['\"]", source):
            consumers.add(path)
    return consumers


def _generated_import_names(source: str) -> set[str]:
    match = re.search(
        rf"import\s+type\s+\{{(?P<names>[^}}]+)\}}\s+from\s+"
        rf'["\']{re.escape(GENERATED_IMPORT)}["\'];',
        source,
        re.DOTALL,
    )
    if match is None:
        return set()
    return {name.strip() for name in match.group("names").split(",")}


def _assert_sensor_lab_request_binding(source: str) -> None:
    assert re.search(
        r'type\s+LabIngestRequest\s*=\s*LabIngestOperation\["requestBody"\]'
        r'\["content"\]\["application/json"\]\s*;',
        source,
    )
    assert re.search(r"}\s+satisfies\s+LabIngestRequest\s*;", source)
    assert not re.search(
        r"(?:interface\s+LabIngestRequest\b|type\s+LabIngestRequest\s*=\s*\{)",
        source,
    )


def test_only_owned_clients_consume_the_generated_schema():
    assert _generated_schema_consumers() == {
        HISTORICAL_API,
        CICYTEX_API,
        QUALITY_API,
        LINEAGE_API,
        SENSOR_LAB_API,
        FORECAST_API,
    }


def test_replay_clients_use_generated_operation_contracts_without_duplicate_dtos():
    for path, operation_ids in EXPECTED_OPERATION_IDS.items():
        source = path.read_text(encoding="utf-8")
        assert _generated_import_names(source) == {"components", "operations"}
        assert not re.search(r"\b(?:export\s+)?interface\s+", source)
        assert not re.search(r"(?<![\w.])any(?!\w)", source)
        assert not re.search(r"\bas\s+unknown\s+as\b", source)
        assert not re.search(r"\bRecord\s*<\s*string\s*,\s*unknown\s*>", source)
        for operation_id in operation_ids:
            assert f'operations["{operation_id}"]' in source


def test_replay_client_public_names_and_transport_helpers_remain_stable():
    historical = HISTORICAL_API.read_text(encoding="utf-8")
    cicytex = CICYTEX_API.read_text(encoding="utf-8")

    assert "async function requestJson<" in historical
    assert "async function json<" not in historical
    assert "async function json<" in cicytex
    assert "async function requestJson<" not in cicytex

    for path, names in EXPECTED_EXPORTS.items():
        source = path.read_text(encoding="utf-8")
        for name in names:
            assert re.search(
                rf"\bexport\s+(?:type|interface|class|function|const)\s+{name}\b", source
            )


def test_quality_client_uses_its_generated_operation_without_a_duplicate_dto():
    source = QUALITY_API.read_text(encoding="utf-8")

    assert _generated_import_names(source) == {"components", "operations"}
    assert 'operations["get_quality_report_quality__sensor_id__get"]' in source
    assert not re.search(r"\b(?:export\s+)?interface\s+", source)
    assert not re.search(r"(?<![\w.])any(?!\w)", source)
    assert not re.search(r"\bas\s+unknown\s+as\b", source)
    assert not re.search(r"\bRecord\s*<\s*string\s*,\s*unknown\s*>", source)
    assert re.search(r"\bexport\s+type\s+QualityReport\b", source)
    assert re.search(r"\bexport\s+(?:function|const)\s+getQualityReport\b", source)


def test_lineage_client_uses_its_generated_operation_without_duplicate_dtos():
    source = LINEAGE_API.read_text(encoding="utf-8")

    assert _generated_import_names(source) == {"components", "operations"}
    assert 'operations["get_lineage_lineage__sensor_id__get"]' in source
    assert not re.search(r"\b(?:export\s+)?interface\s+", source)
    assert not re.search(r"(?<![\w.])any(?!\w)", source)
    assert not re.search(r"\bas\s+unknown\s+as\b", source)
    assert not re.search(r"\bRecord\s*<\s*string\s*,\s*unknown\s*>", source)
    for name in ("FeedbackReference", "LineageEntry", "LineageResponse"):
        assert re.search(rf"\bexport\s+type\s+{name}\b", source)
    assert re.search(r"\bexport\s+(?:function|const)\s+getLineage\b", source)


def test_sensor_lab_client_uses_its_generated_operation_without_duplicate_dtos():
    source = SENSOR_LAB_API.read_text(encoding="utf-8")

    assert _generated_import_names(source) == {"components", "operations"}
    assert 'operations["ingest_reading_sensors__sensor_id__readings_post"]' in source
    assert not re.search(r"\b(?:export\s+)?interface\s+LabIngestResult\b", source)
    assert not re.search(r"(?<![\w.])any(?!\w)", source)
    assert not re.search(r"\bas\s+unknown\s+as\b", source)
    assert not re.search(r"\bRecord\s*<\s*string\s*,\s*unknown\s*>", source)
    _assert_sensor_lab_request_binding(source)
    assert re.search(r"\bexport\s+type\s+LabIngestResult\b", source)
    assert re.search(r"\bexport\s+(?:function|const)\s+ingestLabReading\b", source)


def test_sensor_lab_request_binding_rejects_manual_or_unchecked_mutations():
    source = SENSOR_LAB_API.read_text(encoding="utf-8")
    generated_alias = (
        'type LabIngestRequest = LabIngestOperation["requestBody"]'
        '["content"]["application/json"];'
    )

    manual_request = source.replace(
        generated_alias,
        "interface LabIngestRequest { timestamp: string }",
    )
    unchecked_payload = source.replace("} satisfies LabIngestRequest;", "};")
    assert manual_request != source
    assert unchecked_payload != source
    with pytest.raises(AssertionError):
        _assert_sensor_lab_request_binding(manual_request)
    with pytest.raises(AssertionError):
        _assert_sensor_lab_request_binding(unchecked_payload)


def test_forecast_client_uses_all_generated_operations_without_duplicate_dtos():
    source = FORECAST_API.read_text(encoding="utf-8")

    assert _generated_import_names(source) == {"components", "operations"}
    for operation_id in (
        "run_forecast_forecast__sensor_id__run_post",
        "list_feedback_feedback__sensor_id__get",
        "confirm_feedback_feedback__sensor_id___fecha__confirm_post",
        "reject_feedback_feedback__sensor_id___fecha__reject_post",
        "recalibrate_recalibrate__sensor_id__post",
        "get_active_predictor_models__sensor_id__active_get",
    ):
        assert f'operations["{operation_id}"]' in source
    assert not re.search(r"\b(?:export\s+)?interface\s+", source)
    assert not re.search(r"(?<![\w.])any(?!\w)", source)
    assert not re.search(r"\bas\s+unknown\s+as\b", source)
    assert not re.search(r"\bRecord\s*<\s*string\s*,\s*unknown\s*>", source)
    for name in (
        "Verdict",
        "ForecastRunResponse",
        "FeedbackRow",
        "FeedbackListResponse",
        "RecalibrationResponse",
        "ActivePredictor",
    ):
        assert re.search(rf"\bexport\s+type\s+{name}\b", source)
    for name in (
        "HttpError",
        "NO_READINGS_MESSAGE",
        "runForecast",
        "listFeedback",
        "confirmAlert",
        "rejectAlert",
        "recalibrate",
        "getActivePredictor",
    ):
        assert re.search(rf"\bexport\s+(?:async\s+)?(?:class|const|function)\s+{name}\b", source)
