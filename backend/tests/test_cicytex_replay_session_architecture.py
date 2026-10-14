from __future__ import annotations

import ast
from pathlib import Path


def test_cicytex_router_depends_on_application_facades_not_session_domain():
    repository = Path(__file__).parents[2]
    router = repository / "backend" / "app" / "routers" / "cicytex_replay.py"
    tree = ast.parse(router.read_text(encoding="utf-8"))

    top_level_assignments = {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
        if isinstance(target, ast.Name)
    }
    local_classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    imported_names = {
        alias.name
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    imported_modules = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names}

    assert "_sessions" not in top_level_assignments
    assert top_level_assignments.isdisjoint({"_lock", "_session_lock", "_sessions_lock"})
    assert {name for name in top_level_assignments if name.endswith("_lock")} <= {"_feedback_lock"}
    assert "Session" not in local_classes
    assert "Lock" not in imported_names
    assert "uuid4" not in imported_names
    assert "historical_replay.cicytex_application" in imported_modules
    assert {"CicytexReplayApplication", "CicytexFeedbackApplication"} <= imported_names
    assert {"ReplaySession", "ReplaySessionService"}.isdisjoint(imported_names)
    assert "historical_replay.sessions" not in imported_modules


def test_backend_exposes_injectable_cicytex_application_facades():
    repository = Path(__file__).parents[2]
    dependencies = repository / "backend" / "app" / "dependencies.py"
    tree = ast.parse(dependencies.read_text(encoding="utf-8"))
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert {
        "get_cicytex_catalog_application",
        "get_cicytex_feedback_application",
        "get_cicytex_replay_application",
    } <= functions


def test_feedback_delegates_to_application_without_session_coordination_or_fallbacks():
    repository = Path(__file__).parents[2]
    router = repository / "backend" / "app" / "routers" / "cicytex_replay.py"
    tree = ast.parse(router.read_text(encoding="utf-8"))
    create_feedback = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_feedback"
    )
    calls = [node for node in ast.walk(create_feedback) if isinstance(node, ast.Call)]
    violations = []
    for call in calls:
        if isinstance(call.func, ast.Name) and call.func.id in {
            "__import__",
            "getattr",
            "hasattr",
        }:
            violations.append(f"{call.func.id} bypass")
        if (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "sessions"
        ):
            violations.append(f"sessions.{call.func.attr} coordination")

    assert any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "create_feedback"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "application"
        for call in calls
    )
    assert violations == []
    assert not {"ReplaySession", "ReplaySessionService", "with_session"} & {
        node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
    }
