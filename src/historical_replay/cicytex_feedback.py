"""Pure CICYTEX replay feedback domain and application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

from historical_replay.sessions import ReplaySession

_SCOPE = "demostracion; no recalibra ni reentrena"


class CicytexFeedbackConflict(ValueError):
    """The natural prediction identity already has feedback."""


class CicytexFeedbackUnavailable(ValueError):
    """The session outcome is not currently available for feedback."""


class CicytexFeedbackRepositoryError(RuntimeError):
    """The durable CICYTEX feedback store is unavailable."""


@dataclass(frozen=True, slots=True)
class CicytexFeedbackRecord:
    sensor_id: str
    emission_date: date
    horizon_days: int
    estado_validacion: str
    etiqueta_corregida: int | None
    observacion: str | None
    registered_at: str
    simulated_at: date
    scope: str

    def __post_init__(self) -> None:
        if type(self.sensor_id) is not str or not self.sensor_id or len(self.sensor_id) > 256:
            raise ValueError("invalid sensor identity")
        if type(self.emission_date) is not date or type(self.simulated_at) is not date:
            raise ValueError("invalid feedback date")
        if type(self.horizon_days) is not int or not 1 <= self.horizon_days <= 3:
            raise ValueError("invalid feedback horizon")
        if self.estado_validacion not in {"confirmada", "rechazada"}:
            raise ValueError("invalid validation state")
        if self.etiqueta_corregida is not None and (
            type(self.etiqueta_corregida) is not int or self.etiqueta_corregida not in {0, 1}
        ):
            raise ValueError("invalid corrected label")
        if self.observacion is not None and (
            type(self.observacion) is not str or len(self.observacion) > 1_000
        ):
            raise ValueError("invalid observation")
        if type(self.registered_at) is not str or len(self.registered_at) > 64:
            raise ValueError("invalid registration timestamp")
        if datetime.fromisoformat(self.registered_at).tzinfo is None:
            raise ValueError("invalid registration timestamp")
        if self.scope != _SCOPE:
            raise ValueError("invalid feedback scope")

    def to_public_dict(self) -> dict:
        return {
            "estado_validacion": self.estado_validacion,
            "etiqueta_corregida": self.etiqueta_corregida,
            "observacion": self.observacion,
            "registered_at": self.registered_at,
            "simulated_at": self.simulated_at.isoformat(),
            "scope": self.scope,
        }


@runtime_checkable
class CicytexFeedbackRepository(Protocol):
    def register_for_session(
        self,
        session_id: str,
        factory: Callable[[ReplaySession], CicytexFeedbackRecord],
    ) -> CicytexFeedbackRecord: ...

    def get(
        self, sensor_id: str, emission_date: date, horizon_days: int
    ) -> CicytexFeedbackRecord | None: ...


class CicytexFeedbackService:
    def __init__(self, repository: CicytexFeedbackRepository) -> None:
        self._repository = repository

    def register(
        self,
        session_id: str,
        *,
        estado_validacion: str,
        etiqueta_corregida: int | None = None,
        observacion: str | None = None,
    ) -> CicytexFeedbackRecord:
        def build(session: ReplaySession) -> CicytexFeedbackRecord:
            target = session.emission_date + timedelta(days=session.horizon_days)
            if session.revealed_through < target:
                raise CicytexFeedbackUnavailable("feedback outcome is unavailable")
            return CicytexFeedbackRecord(
                sensor_id=session.sensor_id,
                emission_date=session.emission_date,
                horizon_days=session.horizon_days,
                estado_validacion=estado_validacion,
                etiqueta_corregida=etiqueta_corregida,
                observacion=observacion.strip() if observacion else None,
                registered_at=datetime.now(timezone.utc).isoformat(),
                simulated_at=session.revealed_through,
                scope=_SCOPE,
            )

        return self._repository.register_for_session(session_id, build)

    def visible_for(self, session: ReplaySession) -> CicytexFeedbackRecord | None:
        target = session.emission_date + timedelta(days=session.horizon_days)
        if session.revealed_through < target:
            return None
        return self._repository.get(session.sensor_id, session.emission_date, session.horizon_days)
