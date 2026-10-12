from __future__ import annotations

import ast
from pathlib import Path


def test_cicytex_router_has_no_session_store_or_domain_model():
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

    assert "_sessions" not in top_level_assignments
    assert top_level_assignments.isdisjoint({"_lock", "_session_lock", "_sessions_lock"})
    assert {name for name in top_level_assignments if name.endswith("_lock")} <= {"_feedback_lock"}
    assert "Session" not in local_classes
    if "Lock" in imported_names:
        assert "_feedback_lock" in top_level_assignments
    assert "uuid4" not in imported_names
    assert "ReplaySession" in imported_names
    assert "ReplaySessionService" in imported_names


def test_backend_exposes_an_injectable_session_use_case_dependency():
    repository = Path(__file__).parents[2]
    dependencies = repository / "backend" / "app" / "dependencies.py"
    tree = ast.parse(dependencies.read_text(encoding="utf-8"))
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "get_cicytex_replay_sessions" in functions


def test_feedback_requires_the_atomic_session_operation_without_fallback_reads():
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
        if isinstance(call.func, ast.Name) and call.func.id == "hasattr":
            violations.append("hasattr fallback")
        if (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "get"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "sessions"
        ):
            violations.append("sessions.get fallback")

    assert any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "with_session"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "sessions"
        for call in calls
    )
    assert violations == []
