"""Pure feedback domain for archived historical replay packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol, runtime_checkable

ADMITTED_VALIDATION_STATES = ("confirmada", "rechazada")
ADMITTED_ETIQUETAS = (0, 1)


class UnknownPredictionError(ValueError):
    """The referenced prediction does not exist in the loaded package."""


class FeedbackNotYetRevealedError(ValueError):
    """The prediction outcome is not visible at the simulated clock."""


class InvalidFeedbackContentError(ValueError):
    """Feedback content is outside the closed domain contract."""


@dataclass(frozen=True, slots=True)
class ReplayFeedbackRecord:
    timestamp_origen: str
    experiment_id: str
    run_id: str
    estado_validacion: str
    etiqueta_corregida: int | None
    observacion: str | None
    registered_at: str
    simulated_at: str

    def __post_init__(self) -> None:
        for value in (self.timestamp_origen, self.experiment_id, self.run_id):
            if type(value) is not str or not value or len(value) > 256:
                raise InvalidFeedbackContentError("invalid feedback identity")
        if date.fromisoformat(self.timestamp_origen).isoformat() != self.timestamp_origen:
            raise InvalidFeedbackContentError("invalid origin date")
        if self.estado_validacion not in ADMITTED_VALIDATION_STATES:
            raise InvalidFeedbackContentError("invalid validation state")
        if self.etiqueta_corregida is not None and (
            type(self.etiqueta_corregida) is not int
            or self.etiqueta_corregida not in ADMITTED_ETIQUETAS
        ):
            raise InvalidFeedbackContentError("invalid corrected label")
        if self.observacion is not None and (
            type(self.observacion) is not str or len(self.observacion) > 1_000
        ):
            raise InvalidFeedbackContentError("invalid observation")
        if type(self.registered_at) is not str or len(self.registered_at) > 64:
            raise InvalidFeedbackContentError("invalid registration timestamp")
        registered = datetime.fromisoformat(self.registered_at)
        if registered.tzinfo is None:
            raise InvalidFeedbackContentError("invalid registration timestamp")
        if type(self.simulated_at) is not str or len(self.simulated_at) > 10:
            raise InvalidFeedbackContentError("invalid simulated date")
        if date.fromisoformat(self.simulated_at).isoformat() != self.simulated_at:
            raise InvalidFeedbackContentError("invalid simulated date")


@runtime_checkable
class HistoricalReplayFeedbackRepository(Protocol):
    def append(self, record: ReplayFeedbackRecord) -> None: ...

    def list_for(self, timestamp_origen: str) -> list[ReplayFeedbackRecord]: ...


def _find_record(records, timestamp_origen: date):
    for record in records:
        if record.identity.timestamp_origen == timestamp_origen:
            return record
    return None


def register_feedback(
    records,
    store: HistoricalReplayFeedbackRepository,
    *,
    timestamp_origen: date,
    simulated_date: date,
    estado_validacion: str,
    etiqueta_corregida: int | None = None,
    observacion: str | None = None,
) -> ReplayFeedbackRecord:
    record = _find_record(records, timestamp_origen)
    if record is None:
        raise UnknownPredictionError("No hay ninguna prediccion con ese origen")
    if estado_validacion not in ADMITTED_VALIDATION_STATES:
        raise InvalidFeedbackContentError("estado_validacion invalido")
    if etiqueta_corregida is not None and (
        type(etiqueta_corregida) is not int or etiqueta_corregida not in ADMITTED_ETIQUETAS
    ):
        raise InvalidFeedbackContentError("etiqueta_corregida invalida")
    if observacion is not None and (type(observacion) is not str or len(observacion) > 1_000):
        raise InvalidFeedbackContentError("observacion invalida")
    if not record.target_observed or simulated_date < record.target_timestamp:
        raise FeedbackNotYetRevealedError("La observacion todavia no fue revelada")
    feedback = ReplayFeedbackRecord(
        timestamp_origen=timestamp_origen.isoformat(),
        experiment_id=record.identity.experiment_id,
        run_id=record.identity.run_id,
        estado_validacion=estado_validacion,
        etiqueta_corregida=etiqueta_corregida,
        observacion=observacion,
        registered_at=datetime.now(timezone.utc).isoformat(),
        simulated_at=simulated_date.isoformat(),
    )
    store.append(feedback)
    return feedback


def visible_feedback_for(
    records,
    store: HistoricalReplayFeedbackRepository,
    *,
    timestamp_origen: date,
    simulated_date: date,
) -> list[ReplayFeedbackRecord]:
    record = _find_record(records, timestamp_origen)
    if record is None or not record.target_observed or simulated_date < record.target_timestamp:
        return []
    return store.list_for(timestamp_origen.isoformat())
