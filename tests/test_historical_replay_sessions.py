from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import date, timedelta
from pathlib import Path
from threading import Barrier

import pytest


def _session_contract():
    from historical_replay.adapters.in_memory_sessions import InMemorySessionRepository
    from historical_replay.sessions import ReplaySessionNotFound, ReplaySessionService

    repository = InMemorySessionRepository()
    service = ReplaySessionService(
        repository,
        id_factory=lambda: "a" * 32,
        last_observation=date(2023, 7, 25),
    )
    return repository, service, ReplaySessionNotFound


def test_session_repository_boundary_is_explicit_and_in_memory_adapter_conforms():
    from historical_replay.adapters.in_memory_sessions import InMemorySessionRepository

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
    from historical_replay.adapters.in_memory_sessions import InMemorySessionRepository
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


def test_session_boundary_modules_are_transport_and_io_free():
    repository = Path(__file__).parents[1]
    modules = (
        repository / "src" / "historical_replay" / "sessions.py",
        repository / "src" / "historical_replay" / "ports.py",
        repository / "src" / "historical_replay" / "adapters" / "in_memory_sessions.py",
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
