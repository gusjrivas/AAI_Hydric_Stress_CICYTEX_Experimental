from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SOURCE = ROOT / "frontend" / "src"
HISTORICAL_API = FRONTEND_SOURCE / "features" / "historical-replay" / "api.ts"
CICYTEX_API = FRONTEND_SOURCE / "features" / "defense" / "cicytexApi.ts"
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


def test_only_the_two_initial_replay_clients_consume_the_generated_schema():
    assert _generated_schema_consumers() == {HISTORICAL_API, CICYTEX_API}


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
