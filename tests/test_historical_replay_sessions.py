from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest

from tests.helpers.in_memory_sessions import InMemorySessionRepository

LEGACY_IN_MEMORY_MODULE = "historical_replay.adapters.in_memory_sessions"


def _imports_legacy_in_memory_module(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == LEGACY_IN_MEMORY_MODULE
            or alias.name.startswith(f"{LEGACY_IN_MEMORY_MODULE}.")
            for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom):
            if node.module is not None and (
                node.module == LEGACY_IN_MEMORY_MODULE
                or node.module.startswith(f"{LEGACY_IN_MEMORY_MODULE}.")
            ):
                return True
            if node.module == "historical_replay.adapters" and any(
                alias.name == "in_memory_sessions" for alias in node.names
            ):
                return True
            if node.level > 0 and (
                node.module == "in_memory_sessions"
                or (
                    node.module is None
                    and any(alias.name == "in_memory_sessions" for alias in node.names)
                )
            ):
                return True
        if isinstance(node, ast.Constant) and node.value == LEGACY_IN_MEMORY_MODULE:
            return True
    return False


def _session_contract():
    from historical_replay.sessions import ReplaySessionNotFound, ReplaySessionService

    repository = InMemorySessionRepository()
    service = ReplaySessionService(
        repository,
        id_factory=lambda: "a" * 32,
        last_observation=date(2023, 7, 25),
    )
    return repository, service, ReplaySessionNotFound


def test_session_repository_boundary_is_explicit_and_in_memory_adapter_conforms():
    from historical_replay.ports import SessionRepository

    repository = InMemorySessionRepository()

    assert isinstance(repository, SessionRepository)


def test_create_and_get_session_preserve_the_current_replay_clock_contract():
    repository, service, _ = _session_contract()

    created = service.create(
        sensor_id="CP1_S1",
        emission_date=date(2023, 7, 6),
        horizon_days=2,
    )

    assert created.session_id == "a" * 32
    assert created.sensor_id == "CP1_S1"
    assert created.start_date == date(2023, 7, 6)
    assert created.emission_date == date(2023, 7, 6)
    assert created.horizon_days == 2
    assert created.revealed_through == date(2023, 7, 6)
    assert service.get(created.session_id) == created
    assert repository.get(created.session_id) == created
    with pytest.raises(FrozenInstanceError):
        created.revealed_through = date(2023, 7, 7)


def test_advance_is_bounded_and_reset_returns_to_the_emission_date():
    _, service, _ = _session_contract()
    created = service.create(
        sensor_id="CP1_S1",
        emission_date=date(2023, 7, 24),
        horizon_days=1,
    )

    first = service.advance(created.session_id)
    bounded = service.advance(created.session_id)
    reset = service.reset(created.session_id)

    assert first.revealed_through == date(2023, 7, 25)
    assert bounded.revealed_through == date(2023, 7, 25)
    assert reset.revealed_through == created.emission_date
    assert reset.session_id == created.session_id
    assert reset.sensor_id == created.sensor_id
    assert reset.horizon_days == created.horizon_days


@pytest.mark.parametrize("operation", ["get", "advance", "reset"])
def test_missing_session_has_one_domain_error_for_all_use_cases(operation):
    _, service, error_type = _session_contract()

    with pytest.raises(error_type):
        getattr(service, operation)("missing-session")


def test_sessions_are_isolated_by_repository_identity():
    from historical_replay.sessions import ReplaySessionNotFound, ReplaySessionService

    first = ReplaySessionService(
        InMemorySessionRepository(),
        id_factory=lambda: "a" * 32,
        last_observation=date(2023, 7, 25),
    )
    second = ReplaySessionService(
        InMemorySessionRepository(),
        id_factory=lambda: "b" * 32,
        last_observation=date(2023, 7, 25),
    )
    first.create(sensor_id="CP1_S1", emission_date=date(2023, 7, 6), horizon_days=1)

    with pytest.raises(ReplaySessionNotFound):
        second.get("a" * 32)


def test_concurrent_advances_are_atomic_without_lost_updates():
    _, service, _ = _session_contract()
    created = service.create(
        sensor_id="CP1_S1",
        emission_date=date(2023, 7, 6),
        horizon_days=1,
    )
    workers = 10
    barrier = Barrier(workers)

    def advance_once():
        barrier.wait()
        return service.advance(created.session_id)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = tuple(executor.map(lambda _index: advance_once(), range(workers)))

    expected_dates = tuple(
        created.emission_date + timedelta(days=offset) for offset in range(1, 11)
    )
    assert tuple(sorted(result.revealed_through for result in results)) == expected_dates
    assert service.get(created.session_id).revealed_through == expected_dates[-1]


def test_duplicate_generated_session_id_fails_closed_without_overwrite():
    _, service, _ = _session_contract()
    from historical_replay.sessions import ReplaySessionConflict

    original = service.create(
        sensor_id="CP1_S1",
        emission_date=date(2023, 7, 6),
        horizon_days=1,
    )

    with pytest.raises(ReplaySessionConflict):
        service.create(
            sensor_id="CP2_S1",
            emission_date=date(2023, 7, 7),
            horizon_days=3,
        )

    assert service.get(original.session_id) == original


@pytest.mark.parametrize(
    "overrides",
    [
        {"session_id": ""},
        {"sensor_id": ""},
        {"horizon_days": 0},
        {"horizon_days": 4},
        {"horizon_days": True},
        {"start_date": date(2023, 7, 7)},
        {"revealed_through": date(2023, 7, 5)},
    ],
)
def test_session_domain_rejects_invalid_identity_horizon_and_clock(overrides):
    from historical_replay.sessions import ReplaySession

    values = {
        "session_id": "a" * 32,
        "sensor_id": "CP1_S1",
        "start_date": date(2023, 7, 6),
        "emission_date": date(2023, 7, 6),
        "horizon_days": 1,
        "revealed_through": date(2023, 7, 6),
        "last_observation": date(2023, 7, 25),
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        ReplaySession(**values)


def test_service_rejects_emission_after_last_observation():
    _, service, _ = _session_contract()

    with pytest.raises(ValueError):
        service.create(
            sensor_id="CP1_S1",
            emission_date=date(2023, 7, 26),
            horizon_days=1,
        )


@pytest.mark.parametrize(
    "invalid_last_observation",
    [None, True, "2023-07-25", datetime(2023, 7, 25, 0, 0)],
)
def test_session_advance_rejects_non_exact_date_last_observation(
    invalid_last_observation,
):
    from historical_replay.sessions import ReplaySession

    session = ReplaySession(
        session_id="a" * 32,
        sensor_id="CP1_S1",
        start_date=date(2023, 7, 6),
        emission_date=date(2023, 7, 6),
        horizon_days=1,
        revealed_through=date(2023, 7, 10),
        last_observation=date(2023, 7, 25),
    )

    with pytest.raises(ValueError, match="last|observation|date"):
        session.advance(invalid_last_observation)


@pytest.mark.parametrize(
    "invalid_last_observation",
    [date(2023, 7, 5), date(2023, 7, 8)],
)
def test_session_advance_rejects_last_observation_before_its_clock(
    invalid_last_observation,
):
    from historical_replay.sessions import ReplaySession

    session = ReplaySession(
        session_id="a" * 32,
        sensor_id="CP1_S1",
        start_date=date(2023, 7, 6),
        emission_date=date(2023, 7, 6),
        horizon_days=1,
        revealed_through=date(2023, 7, 10),
        last_observation=date(2023, 7, 25),
    )

    with pytest.raises(ValueError, match="last|observation|clock|revealed"):
        session.advance(invalid_last_observation)
    assert session.revealed_through == date(2023, 7, 10)


def test_session_advance_is_monotonic_at_and_beyond_the_current_clock():
    from historical_replay.sessions import ReplaySession

    session = ReplaySession(
        session_id="a" * 32,
        sensor_id="CP1_S1",
        start_date=date(2023, 7, 6),
        emission_date=date(2023, 7, 6),
        horizon_days=1,
        revealed_through=date(2023, 7, 10),
        last_observation=date(2023, 7, 25),
    )

    bounded = session.advance(date(2023, 7, 10))
    advanced = session.advance(date(2023, 7, 25))

    assert bounded.revealed_through == session.revealed_through
    assert advanced.revealed_through == session.revealed_through + timedelta(days=1)
    assert bounded.revealed_through >= session.revealed_through
    assert advanced.revealed_through >= session.revealed_through


def test_session_boundary_modules_are_transport_and_io_free():
    repository = Path(__file__).parents[1]
    modules = (
        repository / "src" / "historical_replay" / "sessions.py",
        repository / "src" / "historical_replay" / "ports.py",
        repository / "tests" / "helpers" / "in_memory_sessions.py",
    )
    forbidden_modules = {
        "fastapi",
        "json",
        "os",
        "pandas",
        "pathlib",
    }

    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        } | {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert imports.isdisjoint(forbidden_modules)
        assert calls.isdisjoint({"open", "read_bytes", "read_text", "write_bytes", "write_text"})


def test_test_only_in_memory_repository_has_no_product_module_or_consumer():
    repository = Path(__file__).parents[1]
    legacy_path = repository / "src" / "historical_replay" / "adapters" / "in_memory_sessions.py"
    product_roots = tuple(
        path
        for path in (
            repository / "src",
            repository / "backend" / "app",
            repository / "scripts",
            repository / "config",
            repository / "recovery",
        )
        if path.exists()
    )
    consumers: list[str] = []
    for root in product_roots:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if _imports_legacy_in_memory_module(tree):
                consumers.append(path.relative_to(repository).as_posix())

    violations = []
    if legacy_path.exists():
        violations.append(legacy_path.relative_to(repository).as_posix())
    violations.extend(consumers)
    assert violations == []


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("import historical_replay.adapters.in_memory_sessions", True),
        ("from historical_replay.adapters.in_memory_sessions import Adapter", True),
        ("from historical_replay.adapters import in_memory_sessions", True),
        ("from . import in_memory_sessions", True),
        ("__import__('historical_replay.adapters.in_memory_sessions')", True),
        ("from tests.helpers.in_memory_sessions import InMemorySessionRepository", False),
    ),
)
def test_legacy_in_memory_repository_consumer_detector_is_not_tautological(
    source: str,
    expected: bool,
):
    assert _imports_legacy_in_memory_module(ast.parse(source)) is expected
