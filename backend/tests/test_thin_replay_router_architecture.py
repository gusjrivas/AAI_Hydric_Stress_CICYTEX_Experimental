from __future__ import annotations

import ast
from pathlib import Path

import pytest
from app.main import app

ROOT = Path(__file__).resolve().parents[2]

ROUTER_CONTRACTS = {
    "backend/app/routers/cicytex_replay.py": {
        "application_module": "historical_replay.cicytex_application",
        "forbidden_helpers": {"_iso", "_metric", "_render"},
        "forbidden_imports": {
            "pandas",
            "historical_replay.cicytex_feedback",
            "historical_replay.sessions",
        },
        "forbidden_calls": {
            "groupby",
            "iterrows",
            "register",
            "to_public_dict",
            "visible_for",
            "with_session",
        },
    },
    "backend/app/routers/replay.py": {
        "application_module": "historical_replay.replay_application",
        "forbidden_helpers": {
            "_disclaimers",
            "_find_record",
            "_label_rule",
            "_training_max_date",
        },
        "forbidden_imports": {
            "pandas",
            "historical_replay.feedback",
            "historical_replay.history_state",
            "historical_replay.history_view",
            "historical_replay.imputation_markers",
            "historical_replay.observations",
            "historical_replay.projection",
        },
        "forbidden_calls": {
            "classify_history_row",
            "filtered_history",
            "link_observation",
            "project",
            "reconstruct_imputation_markers",
            "register_feedback",
            "visible_feedback_for",
        },
    },
}

EXPECTED_REPLAY_OPENAPI = {
    "/api/v2/cicytex/replay/catalog": {
        "get": ("catalog_api_v2_cicytex_replay_catalog_get", ("200",), None)
    },
    "/api/v2/cicytex/replay/sessions": {
        "post": ("create_session_api_v2_cicytex_replay_sessions_post", ("201", "422"), None)
    },
    "/api/v2/cicytex/replay/sessions/{session_id}": {
        "get": (
            "get_session_api_v2_cicytex_replay_sessions__session_id__get",
            ("200", "422"),
            None,
        )
    },
    "/api/v2/cicytex/replay/sessions/{session_id}/advance": {
        "post": (
            "advance_api_v2_cicytex_replay_sessions__session_id__advance_post",
            ("200", "422"),
            None,
        )
    },
    "/api/v2/cicytex/replay/sessions/{session_id}/feedback": {
        "post": (
            "create_feedback_api_v2_cicytex_replay_sessions__session_id__feedback_post",
            ("201", "422"),
            None,
        )
    },
    "/api/v2/cicytex/replay/sessions/{session_id}/reset": {
        "post": (
            "reset_api_v2_cicytex_replay_sessions__session_id__reset_post",
            ("200", "422"),
            None,
        )
    },
    "/replay/candidate": {
        "get": ("get_candidate_replay_candidate_get", ("200",), "ReplayCandidateInfo")
    },
    "/replay/history": {
        "get": (
            "get_history_replay_history_get",
            ("200", "422"),
            "ReplayHistoryResponse",
        )
    },
    "/replay/predictions": {
        "get": ("list_origins_replay_predictions_get", ("200",), "ReplayOriginsResponse")
    },
    "/replay/predictions/{timestamp_origen}": {
        "get": (
            "get_prediction_replay_predictions__timestamp_origen__get",
            ("200", "422"),
            "ReplayPredictionResponse",
        )
    },
    "/replay/predictions/{timestamp_origen}/feedback": {
        "get": (
            "get_feedback_replay_predictions__timestamp_origen__feedback_get",
            ("200", "422"),
            "ReplayFeedbackListResponse",
        ),
        "post": (
            "create_feedback_replay_predictions__timestamp_origen__feedback_post",
            ("201", "422"),
            "ReplayFeedbackEntry",
        ),
    },
}


def _imports(tree: ast.AST) -> set[str]:
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _called_attributes(tree: ast.AST) -> set[str]:
    called = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
    return called


def _response_ref(operation: dict) -> str | None:
    responses = operation["responses"]
    response = responses.get("200") or responses.get("201")
    schema = response.get("content", {}).get("application/json", {}).get("schema", {})
    reference = schema.get("$ref")
    return reference.rsplit("/", 1)[-1] if reference else None


def test_replay_openapi_surface_remains_exact_during_router_refactor():
    schema = app.openapi()
    actual = {}
    for path, path_item in schema["paths"].items():
        if not (path.startswith("/replay") or path.startswith("/api/v2/cicytex/replay")):
            continue
        actual[path] = {}
        for method in ("get", "post"):
            if method not in path_item:
                continue
            operation = path_item[method]
            actual[path][method] = (
                operation["operationId"],
                tuple(sorted(operation["responses"])),
                _response_ref(operation),
            )

    assert actual == EXPECTED_REPLAY_OPENAPI


@pytest.mark.parametrize(("relative_path", "contract"), ROUTER_CONTRACTS.items())
def test_replay_routers_are_http_adapters_without_projection_or_persistence_logic(
    relative_path, contract
):
    path = ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = _imports(tree)
    helpers = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert contract["application_module"] in imported, relative_path
    assert not contract["forbidden_imports"] & imported, relative_path
    assert not contract["forbidden_helpers"] & helpers, relative_path
    assert not contract["forbidden_calls"] & _called_attributes(tree), relative_path


@pytest.mark.parametrize(
    "module_name",
    (
        "historical_replay.cicytex_application",
        "historical_replay.replay_application",
    ),
)
def test_replay_application_modules_are_framework_free_and_live_outside_backend(module_name):
    path = ROOT / "src" / Path(*module_name.split("."))
    path = path.with_suffix(".py")
    assert path.is_file(), module_name
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = _imports(tree)

    assert not any(
        name == "backend"
        or name.startswith("backend.")
        or name == "fastapi"
        or name.startswith("fastapi.")
        or name == "starlette"
        or name.startswith("starlette.")
        for name in imported
    ), module_name
    assert not {"APIRouter", "Depends", "HTTPException"} & {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }, module_name


def test_architecture_detector_rejects_router_or_framework_logic():
    hostile_router = ast.parse(
        "import pandas\n"
        "from historical_replay.projection import project\n"
        "def _render():\n"
        "    return project(pandas.DataFrame(), None)\n"
    )
    assert "pandas" in _imports(hostile_router)
    assert {"project", "DataFrame"} <= _called_attributes(hostile_router)

    hostile_application = ast.parse(
        "from fastapi import HTTPException\n" "def execute():\n" "    raise HTTPException(500)\n"
    )
    assert "fastapi" in _imports(hostile_application)
    assert "HTTPException" in {
        node.id for node in ast.walk(hostile_application) if isinstance(node, ast.Name)
    }
