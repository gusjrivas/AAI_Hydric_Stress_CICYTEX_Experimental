"""Framework-free application use cases for archived historical replay."""

from __future__ import annotations

from datetime import date

import pandas as pd

from historical_replay.feedback import (
    FeedbackNotYetRevealedError,
    HistoricalReplayFeedbackRepository,
    InvalidFeedbackContentError,
    UnknownPredictionError,
    register_feedback,
    visible_feedback_for,
)
from historical_replay.history_state import classify_history_row
from historical_replay.history_view import filtered_history
from historical_replay.imputation_markers import (
    ImputationSourceDriftError,
    reconstruct_imputation_markers,
)
from historical_replay.observations import (
    CrossSeriesObservationError,
    ObservationConsistencyError,
    link_observation,
)
from historical_replay.package_loader import LoadedReplayPackage
from historical_replay.projection import project

_LABEL_RULE_OPERATORS = {
    "observed_value_at_t_plus_h_less_than_frozen_threshold": "less_than",
}
_ISSUANCE_TEXT = {
    "after_daily_observations_available": (
        "Se supone que las mediciones diarias ya están disponibles al emitir "
        "el pronóstico de ese día — es un supuesto documentado del protocolo, "
        "no un timestamp de recepción verificado por fila."
    ),
}


class ReplayApplicationError(RuntimeError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ReplayPackageEmpty(ReplayApplicationError):
    pass


class ReplayPredictionNotFound(ReplayApplicationError):
    pass


class ReplayPredictionNotEmitted(ReplayApplicationError):
    pass


class ReplayInternalConsistencyError(ReplayApplicationError):
    pass


class ReplayUnknownFeedbackPrediction(ReplayApplicationError):
    pass


class ReplayFeedbackNotRevealed(ReplayApplicationError):
    pass


class ReplayInvalidFeedback(ReplayApplicationError):
    pass


class HistoricalReplayApplication:
    def __init__(self, package: LoadedReplayPackage) -> None:
        self._package = package

    def candidate(self) -> dict:
        candidate = self._package.manifest["candidate"]
        origins = [record.identity.timestamp_origen for record in self._package.records]
        targets = [record.target_timestamp for record in self._package.records]
        if not origins:
            raise ReplayPackageEmpty("El paquete autorizado no tiene predicciones.")
        temporal = self._package.manifest["temporal_semantics"]
        issuance = temporal.get("issuance", "")
        return {
            "experiment_id": candidate["experiment_id"],
            "run_id": candidate["run_id_child"],
            "config_name": candidate["config_name"],
            "seed": candidate["seed"],
            "horizon_days": temporal["horizon_days"],
            "periodo_inicio": min(origins),
            "periodo_fin": max(targets),
            "disclaimers": {},
            "limitaciones": self._package.manifest["known_limitations"],
            "evidencia": {
                "package_id": self._package.manifest["package_id"],
                "dataset_name": self._package.manifest["dataset"]["name"],
                "commit_sha": self._package.manifest["execution_identity"]["commit_sha"],
                "split_date": temporal["split_date"],
                "training_max_date": _training_max_date(self._package.effective_configuration),
                "day_convention": temporal.get("day_convention", ""),
                "issuance_assumption": _ISSUANCE_TEXT.get(issuance, issuance),
            },
            "regla_etiqueta": _label_rule(self._package.manifest),
        }

    def origins(self) -> dict:
        origins = sorted({record.identity.timestamp_origen for record in self._package.records})
        return {"origins": [{"timestamp_origen": origin} for origin in origins]}

    def prediction(self, *, timestamp_origen: date, simulated_date: date) -> dict:
        record = self._find_record(timestamp_origen)
        if record is None:
            raise ReplayPredictionNotFound(
                "No hay ninguna predicción archivada con origen " f"{timestamp_origen.isoformat()}."
            )
        view = project(record, simulated_date)
        if view is None:
            raise ReplayPredictionNotEmitted(
                "Esa predicción todavía no fue emitida en la fecha simulada indicada "
                f"({simulated_date.isoformat()} es anterior a su origen)."
            )
        payload = {
            "timestamp_origen": record.identity.timestamp_origen,
            "target_timestamp": record.target_timestamp,
            "experiment_id": record.identity.experiment_id,
            "run_id": record.identity.run_id,
            "config_name": record.identity.config_name,
            "seed": record.identity.seed,
            "horizon_days": self._package.manifest["temporal_semantics"]["horizon_days"],
            "disclaimers": {},
            "y_pred": view.get("y_pred"),
        }
        if "target_observed" in view:
            payload["target_observed"] = view["target_observed"]
            if view["target_observed"]:
                payload["y_true"] = view["y_true"]
                payload["coincide"] = view["y_pred"] == view["y_true"]
                payload["medicion_original"] = self._linked_observation(record)
        return payload

    def history(self, *, simulated_date: date) -> dict:
        label_column = self._package.manifest["label_rule"]["label_column"]
        history = filtered_history(
            self._package.dataset,
            columns=[label_column],
            simulated_clock=simulated_date,
        )
        try:
            markers = reconstruct_imputation_markers(self._package.dataset, [label_column])
            drift_causa = None
        except ImputationSourceDriftError as error:
            markers = None
            drift_causa = (
                f"ImputationSourceDriftError: {error} No se reconstruyen marcadores "
                "de imputación hasta revisar este cambio."
            )
        rows = []
        for _, row in history.iterrows():
            fecha = row["timestamp"].date()
            raw_value = None if pd.isna(row[label_column]) else float(row[label_column])
            state = classify_history_row(
                raw_value=raw_value,
                target_date=fecha,
                label_column=label_column,
                imputation_markers_df=markers,
                undetermined_causa=drift_causa,
            )
            rows.append(
                {
                    "fecha": fecha,
                    "soil_moisture": raw_value,
                    "estado": state.estado,
                    "causa": state.causa,
                    "valor_imputado": state.valor_imputado,
                }
            )
        return {"simulated_date": simulated_date, "rows": rows}

    def _find_record(self, timestamp_origen: date):
        for record in self._package.records:
            if record.identity.timestamp_origen == timestamp_origen:
                return record
        return None

    def _linked_observation(self, record) -> dict:
        dataset_name = self._package.manifest["dataset"]["name"]
        label_column = self._package.manifest["label_rule"]["label_column"]
        try:
            observation = link_observation(
                record=record,
                dataset_name=dataset_name,
                expected_dataset_name=dataset_name,
                dataset_df=self._package.dataset,
                label_column=label_column,
                imputation_markers_df=None,
            )
        except (CrossSeriesObservationError, ObservationConsistencyError) as error:
            raise ReplayInternalConsistencyError(
                f"Inconsistencia al vincular la observación: {error}"
            ) from None
        return {"estado": observation.state, "valor": observation.raw_value}


class HistoricalReplayFeedbackApplication:
    def __init__(
        self,
        package: LoadedReplayPackage,
        store: HistoricalReplayFeedbackRepository,
    ) -> None:
        self._records = package.records
        self._store = store

    def create_feedback(
        self,
        *,
        timestamp_origen: date,
        simulated_date: date,
        estado_validacion: str,
        etiqueta_corregida: int | None,
        observacion: str | None,
    ) -> dict:
        try:
            record = register_feedback(
                self._records,
                self._store,
                timestamp_origen=timestamp_origen,
                simulated_date=simulated_date,
                estado_validacion=estado_validacion,
                etiqueta_corregida=etiqueta_corregida,
                observacion=observacion,
            )
        except UnknownPredictionError as error:
            raise ReplayUnknownFeedbackPrediction(str(error)) from None
        except FeedbackNotYetRevealedError as error:
            raise ReplayFeedbackNotRevealed(str(error)) from None
        except InvalidFeedbackContentError as error:
            raise ReplayInvalidFeedback(str(error)) from None
        return _feedback_dict(record)

    def feedback(self, *, timestamp_origen: date, simulated_date: date) -> dict:
        visible = visible_feedback_for(
            self._records,
            self._store,
            timestamp_origen=timestamp_origen,
            simulated_date=simulated_date,
        )
        return {
            "timestamp_origen": timestamp_origen,
            "feedback": [_feedback_dict(entry) for entry in visible],
        }


def _label_rule(manifest: dict) -> dict:
    label_rule = manifest["label_rule"]
    rule_id = label_rule["rule"]
    if rule_id not in _LABEL_RULE_OPERATORS:
        raise ReplayInternalConsistencyError(
            f"Regla de etiqueta no reconocida en el manifiesto: {rule_id!r}."
        )
    return {
        "variable": label_rule["label_column"],
        "unidad": label_rule["unit"],
        "operador": _LABEL_RULE_OPERATORS[rule_id],
        "umbral": label_rule["frozen_threshold"],
        "percentil": label_rule.get("percentile"),
    }


def _training_max_date(effective_configuration: dict) -> date:
    return max(date.fromisoformat(raw[:10]) for raw in effective_configuration["training_dates"])


def _feedback_dict(record) -> dict:
    return {
        "timestamp_origen": date.fromisoformat(record.timestamp_origen),
        "estado_validacion": record.estado_validacion,
        "etiqueta_corregida": record.etiqueta_corregida,
        "observacion": record.observacion,
        "registered_at": record.registered_at,
        "simulated_at": date.fromisoformat(record.simulated_at),
    }
