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
PRODUCER_CATALOG_API = FRONTEND_SOURCE / "features" / "producer" / "catalogApi.ts"
PRODUCER_READINGS_API = FRONTEND_SOURCE / "features" / "producer" / "readingsApi.ts"
PRODUCER_FORECASTS_API = FRONTEND_SOURCE / "features" / "producer" / "forecastsApi.ts"
PRODUCER_HISTORICAL_API = FRONTEND_SOURCE / "features" / "producer" / "historicalApi.ts"
PRODUCER_PROVENANCE_API = FRONTEND_SOURCE / "features" / "producer" / "provenanceApi.ts"
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


def _assert_producer_slice_a_binding(path: Path, source: str) -> None:
    expected = {
        PRODUCER_CATALOG_API: {
            "list_sectors_api_v2_sectors_get",
            "list_sensors_api_v2_sensors_get",
        },
        PRODUCER_READINGS_API: {
            "get_readings_api_v2_sensors__sensor_id__readings_get",
        },
    }[path]
    component_aliases = {
        PRODUCER_CATALOG_API: {
            "Sector": "SectorResponse",
            "SensorSummary": "SensorResponse",
            "SectorListResult": "SectorListResponse",
            "SensorListResult": "SensorListResponse",
        },
        PRODUCER_READINGS_API: {
            "ReadingRow": "ReadingRow",
            "VariableCoverage": "VariableCoverage",
            "ReadingsResult": "ReadingsResponse",
        },
    }[path]

    assert _generated_import_names(source) == {"components", "operations"}
    assert not re.search(r"\b(?:export\s+)?interface\s+", source)
    assert not re.search(r"(?<![\w.])any(?!\w)", source)
    assert not re.search(r"\bas\s+unknown\s+as\b", source)
    for operation_id in expected:
        assert f'operations["{operation_id}"]' in source
    for public_name, schema_name in component_aliases.items():
        assert re.search(
            rf'export\s+type\s+{public_name}\s*=\s*components\["schemas"\]'
            rf'\["{schema_name}"\]\s*;',
            source,
        )


def _assert_producer_forecasts_binding(source: str) -> None:
    operation_ids = {
        "list_forecasts_api_v2_sensors__sensor_id__forecasts_get",
        "get_forecast_api_v2_sensors__sensor_id__forecasts__forecast_id__get",
        "create_review_api_v2_sensors__sensor_id__forecasts__forecast_id__reviews_post",
        "create_forecasts_api_v2_sensors__sensor_id__forecasts_post",
    }
    assert _generated_import_names(source) == {"components", "operations"}
    for operation_id in operation_ids:
        assert f'operations["{operation_id}"]' in source
    for public_name in (
        "EventThreshold",
        "ModelReference",
        "LatestReview",
        "ForecastReview",
        "EnsembleComponentVote",
        "EnsembleDetail",
        "Forecast",
        "ForecastListResult",
        "ReviewRequest",
        "ForecastSlot",
        "ForecastBatch",
    ):
        assert re.search(rf"\bexport\s+type\s+{public_name}\b", source)
        assert not re.search(rf"\bexport\s+interface\s+{public_name}\b", source)
    assert re.search(r"}\s+satisfies\s+ReviewCreate\s*;", source)
    assert re.search(r"}\s+satisfies\s+EmissionRequest\s*;", source)
    assert "CreateForecastsOperation" in source
    assert re.search(
        r'type\s+IdempotencyKey\s*=\s*CreateForecastsOperation\["parameters"\]'
        r'\["header"\]\["idempotency-key"\]\s*;',
        source,
    )
    assert re.search(r'"Idempotency-Key"\s*:\s*idempotencyKey\b', source)
    assert re.search(r'CreateReviewOperation\["responses"\]\[201\]', source)
    assert re.search(
        r'CreateForecastsOperation\["responses"\]\[(?:200\s*\|\s*201|201\s*\|\s*200)\]', source
    )


def _assert_producer_historical_binding(source: str) -> None:
    operation_ids = {
        "get_historical_forecasts_api_v2_sensors__sensor_id__historical__as_of_date__forecasts_get",
        "get_historical_readings_api_v2_sensors__sensor_id__historical__as_of_date__readings_get",
        "create_historical_review_api_v2_sensors__sensor_id__historical__as_of_date__forecasts__forecast_id__reviews_post",
    }
    assert _generated_import_names(source) == {"components", "operations"}
    for operation_id in operation_ids:
        assert f'operations["{operation_id}"]' in source
    assert re.search(r"}\s+satisfies\s+ReviewCreate\s*;", source)
    assert re.search(r'HistoricalForecastsOperation\["responses"\]\[200\]', source)
    assert re.search(r'HistoricalReadingsOperation\["responses"\]\[200\]', source)
    assert re.search(r'HistoricalReviewOperation\["responses"\]\[201\]', source)


def test_only_owned_clients_consume_the_generated_schema():
    assert _generated_schema_consumers() == {
        HISTORICAL_API,
        CICYTEX_API,
        QUALITY_API,
        LINEAGE_API,
        SENSOR_LAB_API,
        FORECAST_API,
        PRODUCER_CATALOG_API,
        PRODUCER_READINGS_API,
        PRODUCER_FORECASTS_API,
        PRODUCER_HISTORICAL_API,
        PRODUCER_PROVENANCE_API,
    }


def test_producer_catalog_and_readings_use_generated_operation_contracts():
    for path in (PRODUCER_CATALOG_API, PRODUCER_READINGS_API):
        _assert_producer_slice_a_binding(path, path.read_text(encoding="utf-8"))


def test_producer_slice_a_binding_rejects_manual_or_import_only_false_greens():
    valid = {
        PRODUCER_CATALOG_API: (
            'import type { components, operations } from "../../api/generated/schema";\n' """
export type Sector = components["schemas"]["SectorResponse"];
export type SensorSummary = components["schemas"]["SensorResponse"];
export type SectorListResult = components["schemas"]["SectorListResponse"];
export type SensorListResult = components["schemas"]["SensorListResponse"];
type SectorList = operations["list_sectors_api_v2_sectors_get"];
type SensorList = operations["list_sensors_api_v2_sensors_get"];
"""
        ),
        PRODUCER_READINGS_API: (
            'import type { components, operations } from "../../api/generated/schema";\n' """
export type ReadingRow = components["schemas"]["ReadingRow"];
export type VariableCoverage = components["schemas"]["VariableCoverage"];
export type ReadingsResult = components["schemas"]["ReadingsResponse"];
type Readings = operations["get_readings_api_v2_sensors__sensor_id__readings_get"];
"""
        ),
    }
    for path, source in valid.items():
        _assert_producer_slice_a_binding(path, source)

        import_only = re.sub(r"type\s+\w+\s*=\s*operations\[[^;]+;", "", source)
        manual = re.sub(
            r'export\s+type\s+(\w+)\s*=\s*components\["schemas"\]\["[^"]+"\];',
            r"export type \1 = { value: string };",
            source,
            count=1,
        )
        assert manual != source
        with pytest.raises(AssertionError):
            _assert_producer_slice_a_binding(path, import_only)
        with pytest.raises(AssertionError):
            _assert_producer_slice_a_binding(path, manual)


def test_producer_forecasts_use_four_generated_operations_and_checked_writes():
    _assert_producer_forecasts_binding(PRODUCER_FORECASTS_API.read_text(encoding="utf-8"))


def test_producer_forecasts_binding_rejects_manual_and_unchecked_mutations():
    source = (
        'import type { components, operations } from "../../api/generated/schema";\n'
        + "\n".join(
            [
                f'type Op{index} = operations["{operation_id}"];'
                for index, operation_id in enumerate(
                    (
                        "list_forecasts_api_v2_sensors__sensor_id__forecasts_get",
                        "get_forecast_api_v2_sensors__sensor_id__forecasts__forecast_id__get",
                        "create_review_api_v2_sensors__sensor_id__forecasts__forecast_id__reviews_post",
                        "create_forecasts_api_v2_sensors__sensor_id__forecasts_post",
                    )
                )
            ]
        )
        + "\n"
        + "\n".join(
            f'export type {name} = components["schemas"]["ForecastResponse"];'
            for name in (
                "EventThreshold",
                "ModelReference",
                "LatestReview",
                "ForecastReview",
                "EnsembleComponentVote",
                "EnsembleDetail",
                "Forecast",
                "ForecastListResult",
                "ReviewRequest",
                "ForecastSlot",
                "ForecastBatch",
            )
        )
        + '\ntype ReviewCreate = components["schemas"]["ReviewCreate"];\n'
        + 'type EmissionRequest = components["schemas"]["EmissionRequest"];\n'
        + (
            'type CreateForecastsOperation = operations["create_forecasts_api_v2_'
            'sensors__sensor_id__forecasts_post"];\n'
        )
        + (
            'type CreateReviewOperation = operations["create_review_api_v2_sensors_'
            '__sensor_id__forecasts__forecast_id__reviews_post"];\n'
        )
        + 'type ReviewResponse = CreateReviewOperation["responses"][201];\n'
        + 'type EmissionResponse = CreateForecastsOperation["responses"][200 | 201];\n'
        + 'type IdempotencyKey = CreateForecastsOperation["parameters"]["header"]'
        + '["idempotency-key"];\n'
        + 'const review = { request_id: "r" } satisfies ReviewCreate;\n'
        + "const emission = {} satisfies EmissionRequest;\n"
        + 'const idempotencyKey: IdempotencyKey = "r";\n'
        + 'const header = { "Idempotency-Key": idempotencyKey };\n'
    )
    _assert_producer_forecasts_binding(source)

    mutations = (
        source.replace("satisfies ReviewCreate", "as ReviewCreate"),
        source.replace("satisfies EmissionRequest", "as EmissionRequest"),
        source.replace('["idempotency-key"]', '["request-id"]'),
        source.replace('"Idempotency-Key": idempotencyKey', '"Idempotency-Key": "r"'),
        source.replace(
            "create_review_api_v2_sensors__sensor_id__forecasts__forecast_id__reviews_post",
            "wrong_review_operation",
        ),
        source.replace(
            'CreateReviewOperation["responses"][201]', 'CreateReviewOperation["responses"][200]'
        ),
        source.replace("export type Forecast =", "export interface Forecast {}\ntype X ="),
    )
    for mutation in mutations:
        with pytest.raises(AssertionError):
            _assert_producer_forecasts_binding(mutation)


def test_producer_historical_uses_three_generated_operations_and_checked_review():
    _assert_producer_historical_binding(PRODUCER_HISTORICAL_API.read_text(encoding="utf-8"))


def test_producer_historical_binding_rejects_import_only_and_wrong_contracts():
    source = (
        'import type { components, operations } from "../../api/generated/schema";\n'
        'type HistoricalForecastsOperation = operations["get_historical_forecasts_api_v2_'
        'sensors__sensor_id__historical__as_of_date__forecasts_get"];\n'
        'type HistoricalReadingsOperation = operations["get_historical_readings_api_v2_'
        'sensors__sensor_id__historical__as_of_date__readings_get"];\n'
        'type HistoricalReviewOperation = operations["create_historical_review_api_v2_'
        'sensors__sensor_id__historical__as_of_date__forecasts__forecast_id__reviews_post"];\n'
        'type ForecastResponse = HistoricalForecastsOperation["responses"][200];\n'
        'type ReadingsResponse = HistoricalReadingsOperation["responses"][200];\n'
        'type ReviewResponse = HistoricalReviewOperation["responses"][201];\n'
        'type ReviewCreate = components["schemas"]["ReviewCreate"];\n'
        'const review = { request_id: "r" } satisfies ReviewCreate;\n'
    )
    _assert_producer_historical_binding(source)
    mutations = (
        source.replace("satisfies ReviewCreate", "as ReviewCreate"),
        source.replace(
            'HistoricalReviewOperation["responses"][201]',
            'HistoricalReviewOperation["responses"][200]',
        ),
        source.replace(
            "get_historical_readings_api_v2_sensors__sensor_id__historical__as_of_date__readings_get",
            "wrong_historical_readings_operation",
        ),
        re.sub(
            r"type HistoricalForecastsOperation = operations\[[^;]+;\n",
            "",
            source,
        ),
    )
    for mutation in mutations:
        with pytest.raises(AssertionError):
            _assert_producer_historical_binding(mutation)


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
