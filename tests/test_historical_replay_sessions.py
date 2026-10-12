from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

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
