"""Atomic operational forecasts and human reviews, isolated per sensor (HU4/HU5/HU6).
emit_snapshot commits captured input bytes, forecasts and HTTP replay together.
record_batch remains the lower-level entry used by isolated tests.
See docs/design/backend-producer-ui-emission-dependencies.md.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from data_ingestion.sensor_naming import validate_sensor_id
from data_ingestion.storage import StorageLockTimeout, atomic_write_bytes, interprocess_lock
from predictive_modeling.operational_contract import OPERATIONAL_CONTRACT_VERSION
from predictive_modeling.operational_preparation import SUPPORTED_HORIZONS

FORMAT_VERSION = 1
METADATA_DIRECTORY = "ui_metadata"

# Base observada: `DEMO_SENSOR_PREFIX` en scripts/demo_simulation/config.py.
# Se repite aquí como literal (no como import) porque `scripts/` no forma
# parte del paquete instalable; el valor es la decisión normativa del
# documento de dependencias, no un detalle de implementación del simulador.
DEMO_SENSOR_PREFIX = "demo-"

REVIEW_ACTIONS = {"confirm", "reject"}
TRAINING_ELIGIBILITY_STATES = {
    "no_review",
    "waiting_target_maturity",
    "requires_mature_revalidation",
    "compatible_correction",
    "confirmation_only",
    "incompatible_source_model",
    "incompatible_contract",
    "insufficient_data",
    "applied",
}


class OperationalRepositoryError(Exception):
    def __init__(self, code: str, message: str, status_code: int, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def is_demo_reserved(sensor_id: str) -> bool:
    """Todo sensor_id que empiece exactamente por `demo-` queda reservado
    al flujo legacy en cualquier estado, incluso sin manifiesto local.
    """
    return sensor_id.startswith(DEMO_SENSOR_PREFIX)


def _demo_write_locked() -> OperationalRepositoryError:
    return OperationalRepositoryError(
        "demo_write_locked",
        "El espacio demo- esta reservado al flujo legacy.",
        409,
        {"reason": "legacy_demo_sensor_reserved"},
    )


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def compute_batch_id(sensor_id: str, as_of_date: date, contract_version: str) -> str:
    payload = ["producer-batch-id-v1", sensor_id, as_of_date.isoformat(), contract_version]
    return "batch_" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def compute_forecast_id(
    sensor_id: str, as_of_date: date, horizon_days: int, contract_version: str
) -> str:
    payload = [
        "producer-forecast-id-v1",
        sensor_id,
        as_of_date.isoformat(),
        horizon_days,
        contract_version,
    ]
    return "fc_" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def _isoformat_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Los instantes persistidos deben ser aware en UTC.")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_z(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _public_code_identity(raw: Any) -> dict[str, Any] | None:
    """Lista blanca de `code_identity` (available/commit/dirty). `None` si no
    fue registrado o no tiene la forma esperada; `reason` (texto libre que
    puede contener rutas) nunca se expone."""
    if not isinstance(raw, dict) or not isinstance(raw.get("available"), bool):
        return None
    if not raw["available"]:
        return {"available": False, "commit": None, "dirty": None}
    commit = raw.get("commit")
    dirty = raw.get("dirty")
    return {
        "available": True,
        "commit": commit if isinstance(commit, str) else None,
        "dirty": dirty if isinstance(dirty, bool) else None,
    }


@dataclass(frozen=True)
class SlotSeed:
    """Resultado de un horizonte, producido por inferencia o por fixtures aislados.

    `ensemble` es `None` para el camino single-model (sin cambios); cuando el
    horizonte se resolvió en modo ensamble, es el detalle completo devuelto por
    `predictive_modeling.ensemble_bundle.predict_ensemble_bundle` (un único
    objeto anidado — nunca se exponen sus claves como campos sueltos de nivel
    superior, ver `schemas_v2.EnsembleDetail`, con la misma forma exacta)."""

    horizon_days: int
    status: str  # "available" | "unavailable"
    reason_code: str | None = None
    alert: bool | None = None
    score: float | None = None
    score_kind: str | None = None
    display_probability: float | None = None
    probability_status: str | None = None
    probability_reason_code: str | None = None
    decision_threshold: float | None = None
    event_threshold: dict[str, Any] | None = None
    model_reference: dict[str, Any] | None = None
    ensemble: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.horizon_days not in SUPPORTED_HORIZONS:
            raise ValueError("horizon_days debe ser 1, 2 o 3.")
        if self.status not in {"available", "unavailable"}:
            raise ValueError("status debe ser available o unavailable.")
        if self.status == "unavailable" and not self.reason_code:
            raise ValueError("Un slot unavailable requiere reason_code.")
        if self.status == "available" and (
            self.alert is None
            or self.score is None
            or self.score_kind is None
            or self.decision_threshold is None
            or self.event_threshold is None
            or self.model_reference is None
        ):
            raise ValueError("Un slot available requiere sus campos obligatorios.")
        if self.ensemble is not None:
            if self.alert != self.ensemble["combined_alert"]:
                raise ValueError("alert debe coincidir con ensemble['combined_alert'].")
            if self.score != self.ensemble["combined_probability"]:
                raise ValueError("score debe coincidir con ensemble['combined_probability'].")


def _request_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


class OperationalRepository:
    """Documento JSON versionado por sensor: tandas, emisiones, eventos de
    revisión y resultados idempotentes en un único archivo, con lock
    entre procesos y reemplazo atómico (mismas primitivas que
    `data_ingestion.catalog.CatalogRepository`).
    """

    def __init__(self, data_dir: Path, sensor_id: str):
        try:
            self.sensor_id = validate_sensor_id(sensor_id)
        except ValueError as error:
            raise OperationalRepositoryError(
                "invalid_sensor_id", str(error), 422, {"field": "sensor_id"}
            ) from error
        self.data_dir = Path(data_dir)
        self.metadata_dir = self.data_dir / METADATA_DIRECTORY
        self.path = self.metadata_dir / f"operational_v2__{self.sensor_id}.json"
        self.lock_path = self.metadata_dir / f".operational_v2__{self.sensor_id}.lock"

    @staticmethod
    def _empty(sensor_id: str) -> dict[str, Any]:
        return {
            "format_version": FORMAT_VERSION,
            "sensor_id": sensor_id,
            "batches": {},
            "forecasts": {},
            "reviews": {},
            "idempotency": {"emission": {}, "review": {}},
        }

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty(self.sensor_id)
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise OperationalRepositoryError(
                "operational_storage_unavailable",
                "No se pudo leer el repositorio operacional.",
                503,
            ) from error
        if document.get("format_version") != FORMAT_VERSION:
            raise OperationalRepositoryError(
                "unsupported_operational_version",
                "La version persistida del repositorio no es compatible.",
                503,
                {"format_version": document.get("format_version")},
            )
        return document

    def _write(self, document: dict[str, Any]) -> None:
        content = (
            json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
        try:
            atomic_write_bytes(self.path, content)
        except OSError as error:
            raise OperationalRepositoryError(
                "operational_storage_unavailable",
                "No se pudo persistir el repositorio operacional.",
                503,
            ) from error

    @contextmanager
    def _locked_document(self, *, timeout: float = 10.0) -> Iterator[dict[str, Any]]:
        try:
            with interprocess_lock(self.lock_path, timeout=timeout):
                yield self._read()
        except StorageLockTimeout as error:
            if timeout == 0:
                raise OperationalRepositoryError(
                    "operation_in_progress", "Hay otra operación en curso. Reintentá.", 409
                ) from error
            raise OperationalRepositoryError(
                "operational_storage_unavailable",
                "No se pudo bloquear el repositorio operacional.",
                503,
            ) from error
        except OperationalRepositoryError:
            raise
        except OSError as error:
            raise OperationalRepositoryError(
                "operational_storage_unavailable",
                "No se pudo bloquear el repositorio operacional.",
                503,
            ) from error

    # -- Persistencia de resultados de inferencia y fixtures aislados --------

    def record_batch(
        self,
        *,
        as_of_date: date,
        issued_at: datetime,
        snapshot_id: str,
        data_age_days: int | None,
        provenance: str,
        slots: Sequence[SlotSeed],
        idempotency_key: str,
        contract_version: str = OPERATIONAL_CONTRACT_VERSION,
        now: datetime,
        _document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not idempotency_key:
            raise OperationalRepositoryError(
                "invalid_idempotency_key", "Idempotency-Key es obligatorio.", 422
            )
        horizons = sorted(seed.horizon_days for seed in slots)
        if horizons != list(SUPPORTED_HORIZONS):
            raise OperationalRepositoryError(
                "invalid_batch_slots",
                "Una tanda requiere exactamente los horizontes 1, 2 y 3.",
                422,
            )
        # Orden de precedencia (dependencias resueltas 2026-09-20): validar
        # entrada, luego reserva demo-, luego idempotencia y reglas
        # temporales/concurrencia.
        if is_demo_reserved(self.sensor_id):
            raise _demo_write_locked()

        def _slot_payload(seed: SlotSeed) -> dict[str, Any]:
            payload = {
                "horizon_days": seed.horizon_days,
                "status": seed.status,
                "reason_code": seed.reason_code,
                "alert": seed.alert,
                "score": seed.score,
                "score_kind": seed.score_kind,
                "display_probability": seed.display_probability,
                "probability_status": seed.probability_status,
                "probability_reason_code": seed.probability_reason_code,
                "decision_threshold": seed.decision_threshold,
                "event_threshold": seed.event_threshold,
                "model_reference": seed.model_reference,
            }
            # Omit the key entirely (never add it as `None`) for a
            # single-model slot: a legacy idempotency key retried after this
            # change must still hash to exactly what was stored before it,
            # or a legitimate retry would be rejected as `idempotency_conflict`
            # purely because this field was introduced.
            if seed.ensemble is not None:
                payload["ensemble"] = seed.ensemble
            return payload

        request_payload = {
            "as_of_date": as_of_date.isoformat(),
            "snapshot_id": snapshot_id,
            "data_age_days": data_age_days,
            "provenance": provenance,
            "slots": [
                _slot_payload(seed) for seed in sorted(slots, key=lambda seed: seed.horizon_days)
            ],
            "contract_version": contract_version,
        }
        request_hash = _request_hash(request_payload)

        context = self._locked_document() if _document is None else nullcontext(_document)
        with context as document:
            idem_store = document["idempotency"]["emission"]
            existing_idem = idem_store.get(idempotency_key)
            if existing_idem is not None:
                if existing_idem["request_hash"] != request_hash:
                    raise OperationalRepositoryError(
                        "idempotency_conflict",
                        "La clave de idempotencia ya se uso con otro contenido.",
                        409,
                    )
                return self._render_batch(document, existing_idem["batch_id"], now)

            batch_id = compute_batch_id(self.sensor_id, as_of_date, contract_version)
            existing_batch = document["batches"].get(batch_id)
            if existing_batch is not None:
                if existing_batch["snapshot_id"] != snapshot_id:
                    raise OperationalRepositoryError(
                        "issued_snapshot_conflict",
                        "El snapshot cambio para una clave ya emitida.",
                        409,
                    )
                if existing_batch["as_of_date"] != as_of_date.isoformat():
                    raise OperationalRepositoryError(
                        "batch_identity_mismatch",
                        "Las claves originales no coinciden con la tanda persistida.",
                        503,
                    )

            resolved_slots: dict[str, dict[str, Any]] = {}
            for seed in sorted(slots, key=lambda seed: seed.horizon_days):
                key = str(seed.horizon_days)
                previous = (existing_batch or {}).get("slots", {}).get(key)
                if previous is not None and previous["status"] == "available":
                    # Éxitos inmutables: un reintento con otra clave de
                    # idempotencia no recalcula slots ya exitosos.
                    resolved_slots[key] = previous
                    continue
                if seed.status == "available":
                    forecast_id = compute_forecast_id(
                        self.sensor_id, as_of_date, seed.horizon_days, contract_version
                    )
                    target_date = date.fromordinal(as_of_date.toordinal() + seed.horizon_days)
                    forecast_record = {
                        "forecast_id": forecast_id,
                        "sensor_id": self.sensor_id,
                        "batch_id": batch_id,
                        "as_of_date": as_of_date.isoformat(),
                        "horizon_days": seed.horizon_days,
                        "target_date": target_date.isoformat(),
                        "contract_version": contract_version,
                        "issued_at": _isoformat_z(issued_at),
                        "snapshot_id": snapshot_id,
                        "alert": seed.alert,
                        "score": seed.score,
                        "score_kind": seed.score_kind,
                        "display_probability": seed.display_probability,
                        "probability_status": seed.probability_status,
                        "probability_reason_code": seed.probability_reason_code,
                        "decision_threshold": seed.decision_threshold,
                        "event_threshold": seed.event_threshold,
                        "model_reference": seed.model_reference,
                        "ensemble": seed.ensemble,
                        "review": {"status": "pending", "revision": 0, "latest_review": None},
                    }
                    document["forecasts"][forecast_id] = forecast_record
                    resolved_slots[key] = {
                        "status": "available",
                        "forecast_id": forecast_id,
                        "reason_code": None,
                    }
                else:
                    resolved_slots[key] = {
                        "status": "unavailable",
                        "forecast_id": None,
                        "reason_code": seed.reason_code,
                    }

            revision = (existing_batch["revision"] + 1) if existing_batch is not None else 1
            batch_record = {
                "batch_id": batch_id,
                "sensor_id": self.sensor_id,
                "as_of_date": as_of_date.isoformat(),
                "contract_version": contract_version,
                "revision": revision,
                "issued_at": _isoformat_z(issued_at),
                "snapshot_id": snapshot_id,
                "data_age_days": data_age_days,
                "provenance": provenance,
                "slots": resolved_slots,
            }
            document["batches"][batch_id] = batch_record
            idem_store[idempotency_key] = {"request_hash": request_hash, "batch_id": batch_id}
            if _document is None:
                self._write(document)
            return self._render_batch(document, batch_id, now)

    def emit_snapshot(
        self, *, idempotency_key: str, capture: Callable, predict: Callable, now: datetime
    ) -> tuple[int, dict[str, Any]]:
        """One lock and one atomic commit for snapshot, forecasts and HTTP replay.

        Capture/predict are invoked only after replay lookup. A process crash
        before the atomic write commits neither an emission nor an HTTP success.
        """
        if not idempotency_key or len(idempotency_key) > 128:
            raise OperationalRepositoryError("invalid_idempotency_key", "Clave inválida.", 422)
        if is_demo_reserved(self.sensor_id):
            raise _demo_write_locked()
        with self._locked_document(timeout=0) as document:
            requests = document["idempotency"].setdefault("http_emission", {})
            if idempotency_key in requests:
                previous = requests[idempotency_key]
                return previous["status_code"], previous["response"]
            captured = capture()
            if captured is None:
                body = {
                    "batch_id": None,
                    "revision": 0,
                    "sensor_id": self.sensor_id,
                    "contract_version": OPERATIONAL_CONTRACT_VERSION,
                    "as_of_date": None,
                    "issued_at": None,
                    "snapshot_id": None,
                    "data_age_days": None,
                    "provenance": "unknown",
                    "slots": [
                        {
                            "horizon_days": h,
                            "target_date": None,
                            "status": "unavailable",
                            "reason_code": "no_readings",
                            "forecast_id": None,
                            "review": None,
                        }
                        for h in SUPPORTED_HORIZONS
                    ],
                }
                status_code = 200
            else:
                values = captured["batch"]
                batch_id = compute_batch_id(
                    self.sensor_id, values["as_of_date"], OPERATIONAL_CONTRACT_VERSION
                )
                existing = document["batches"].get(batch_id)
                if existing and existing["snapshot_id"] != values["snapshot_id"]:
                    raise OperationalRepositoryError(
                        "issued_snapshot_conflict", "Los datos del día ya emitido cambiaron.", 409
                    )
                missing = [
                    h
                    for h in SUPPORTED_HORIZONS
                    if not existing or existing["slots"][str(h)]["status"] != "available"
                ]
                if missing:
                    slots = predict(captured, missing)
                    body = self.record_batch(
                        **values,
                        slots=slots,
                        idempotency_key=idempotency_key,
                        issued_at=now,
                        now=now,
                        _document=document,
                    )
                    artifact = captured["artifact"]
                    previous_bundles = (existing or {}).get("input_snapshot", {}).get("bundles", {})
                    artifact["bundles"] = {**previous_bundles, **artifact.get("bundles", {})}
                    document["batches"][batch_id]["input_snapshot"] = artifact
                else:
                    body = self._render_batch(document, batch_id, now)
                status_code = 200 if existing else 201
            body.update(calendar_timezone="UTC", server_today=now.date().isoformat())
            requests[idempotency_key] = {"status_code": status_code, "response": body}
            self._write(document)
            return status_code, body

    def _render_batch(
        self, document: dict[str, Any], batch_id: str, now: datetime
    ) -> dict[str, Any]:
        batch = document["batches"][batch_id]
        slots = []
        for horizon in SUPPORTED_HORIZONS:
            slot = batch["slots"][str(horizon)]
            if slot["status"] == "unavailable":
                slots.append(
                    {
                        "horizon_days": horizon,
                        "target_date": (
                            date.fromisoformat(batch["as_of_date"]) + timedelta(days=horizon)
                        ).isoformat(),
                        "status": "unavailable",
                        "reason_code": slot["reason_code"],
                        "forecast_id": None,
                        "review": None,
                    }
                )
            else:
                forecast = document["forecasts"][slot["forecast_id"]]
                slots.append(
                    {
                        **self._render_forecast(forecast, now),
                        "status": "available",
                        "reason_code": None,
                    }
                )
        return {
            "batch_id": batch["batch_id"],
            "sensor_id": batch["sensor_id"],
            "revision": batch["revision"],
            "as_of_date": batch["as_of_date"],
            "issued_at": batch["issued_at"],
            "snapshot_id": batch["snapshot_id"],
            "data_age_days": batch["data_age_days"],
            "provenance": batch["provenance"],
            "contract_version": batch["contract_version"],
            "slots": slots,
        }

    # -- Lectura ----------------------------------------------------------

    def get_forecast(self, forecast_id: str, *, now: datetime) -> dict[str, Any] | None:
        document = self._read()
        forecast = document["forecasts"].get(forecast_id)
        if forecast is None:
            return None
        return self._render_forecast(forecast, now)

    def get_batch_by_as_of_date(
        self,
        as_of_date: date,
        *,
        contract_version: str = OPERATIONAL_CONTRACT_VERSION,
        now: datetime,
    ) -> dict[str, Any] | None:
        """Unambiguous, deterministic selection by *emission* date
        (`as_of_date`), never by `target_date` -- `compute_batch_id` is a
        pure function of `(sensor_id, as_of_date, contract_version)`, so
        this never infers, never guesses "the latest available", and never
        triggers `capture`/`predict`: only a dictionary lookup over
        already-persisted batches, exactly like `get_forecast`. Returns
        `None` when that exact date was never emitted -- never a partial or
        invented result. Two calls with the same `as_of_date`, regardless
        of how many *other* dates were emitted in between (A -> B -> A),
        return byte-identical results, because the lookup key never
        depends on what else has been emitted since.

        `now` is accepted explicitly and never defaulted to the real wall
        clock here: the caller (a historical-context route) is responsible
        for supplying a simulated clock, so that `reviewable_pending_total`/
        `_review_open_at`-derived state below reflects the point in the
        simulated timeline being browsed, never real "today". The live
        operational routes never call this method."""
        document = self._read()
        batch_id = compute_batch_id(self.sensor_id, as_of_date, contract_version)
        if batch_id not in document["batches"]:
            return None
        return self._render_batch(document, batch_id, now)

    def get_batch_provenance(self, batch_id: str) -> dict[str, Any] | None:
        """Procedencia de solo lectura de una emisión, como lista blanca de
        campos de identidad. Nunca devuelve `input_snapshot` (parquet) ni
        otros campos del bundle. `code_identity` ausente (bundles/lotes
        anteriores a su registro) queda en `None` ("no registrado"): jamás se
        infiere del checkout actual. Devuelve `None` si el lote no existe."""
        document = self._read()
        batch = document["batches"].get(batch_id)
        if batch is None or batch.get("sensor_id") != self.sensor_id:
            return None
        snapshot = batch.get("input_snapshot")
        bundles = snapshot.get("bundles") if isinstance(snapshot, dict) else None
        bundles = bundles if isinstance(bundles, dict) else {}
        horizons = []
        for horizon in SUPPORTED_HORIZONS:
            slot = batch["slots"][str(horizon)]
            bundle = bundles.get(str(horizon))
            bundle = bundle if isinstance(bundle, dict) else {}
            entry: dict[str, Any] = {
                "horizon_days": horizon,
                "status": slot["status"],
                "reason_code": slot.get("reason_code"),
                "mode": None,
                "model_reference": None,
                "ensemble_identity_sha256": None,
                "code_identity": None,
                "components": [],
            }
            if slot["status"] == "available":
                forecast = document["forecasts"][slot["forecast_id"]]
                entry["model_reference"] = forecast["model_reference"]
                if bundle.get("mode") == "ensemble":
                    entry["mode"] = "ensemble"
                    ensemble = forecast.get("ensemble") or {}
                    entry["ensemble_identity_sha256"] = ensemble.get("ensemble_identity_sha256")
                    components = bundle.get("components")
                    components = components if isinstance(components, dict) else {}
                    entry["components"] = [
                        {
                            "family": family,
                            "code_identity": _public_code_identity(
                                (meta or {}).get("code_identity")
                                if isinstance(meta, dict)
                                else None
                            ),
                        }
                        for family, meta in sorted(components.items())
                    ]
                elif bundle:
                    entry["mode"] = "single"
                    entry["code_identity"] = _public_code_identity(bundle.get("code_identity"))
            horizons.append(entry)
        return {
            "batch_id": batch["batch_id"],
            "sensor_id": batch["sensor_id"],
            "as_of_date": batch["as_of_date"],
            "contract_version": batch["contract_version"],
            "snapshot_id": batch["snapshot_id"],
            "horizons": horizons,
            "not_persisted": ["full_config", "mlflow_run", "seed"],
        }

    def list_forecasts(
        self,
        *,
        target_from: date | None,
        target_to: date | None,
        horizon_days: int | None,
        review_status: str | None,
        cutoff: datetime,
        after: tuple[str, str, str] | None,
        limit: int,
        now: datetime,
    ) -> dict[str, Any]:
        document = self._read()
        cutoff_key = _isoformat_z(cutoff)
        all_forecasts = list(document["forecasts"].values())

        pending_total = sum(
            1 for forecast in all_forecasts if forecast["review"]["status"] == "pending"
        )
        reviewable_pending_total = sum(
            1
            for forecast in all_forecasts
            if forecast["review"]["status"] == "pending" and now >= _review_open_at(forecast)
        )

        filtered = [
            forecast
            for forecast in all_forecasts
            if forecast["issued_at"] <= cutoff_key
            and (target_from is None or forecast["target_date"] >= target_from.isoformat())
            and (target_to is None or forecast["target_date"] <= target_to.isoformat())
            and (horizon_days is None or forecast["horizon_days"] == horizon_days)
            and (review_status is None or forecast["review"]["status"] == review_status)
        ]
        # Orden estable multi-clave: cada sort() es estable, así que
        # aplicar las claves de menor a mayor precedencia (ID ascendente,
        # luego issued_at descendente, luego target_date descendente)
        # produce exactamente target_date DESC, issued_at DESC, ID ASC.
        filtered.sort(key=lambda forecast: forecast["forecast_id"])
        filtered.sort(key=lambda forecast: forecast["issued_at"], reverse=True)
        filtered.sort(key=lambda forecast: forecast["target_date"], reverse=True)

        if after is not None:
            # Keyset pagination must not depend on the anchor still matching
            # a mutable review filter. Preserve target DESC, issued DESC, ID ASC.
            target, issued, forecast_id = after
            filtered = [
                forecast
                for forecast in filtered
                if forecast["target_date"] < target
                or (
                    forecast["target_date"] == target
                    and (
                        forecast["issued_at"] < issued
                        or (
                            forecast["issued_at"] == issued
                            and forecast["forecast_id"] > forecast_id
                        )
                    )
                )
            ]

        page = filtered[: limit + 1]
        has_more = len(page) > limit
        page = page[:limit]
        items = [self._render_forecast(forecast, now) for forecast in page]
        next_after = None
        if has_more and page:
            last = page[-1]
            next_after = (last["target_date"], last["issued_at"], last["forecast_id"])
        return {
            "items": items,
            "next_after": next_after,
            "pending_total": pending_total,
            "reviewable_pending_total": reviewable_pending_total,
        }

    def _render_forecast(self, forecast: dict[str, Any], now: datetime) -> dict[str, Any]:
        review_open_at = _review_open_at(forecast)
        reviewable = now >= review_open_at
        blocked_reason = None if reviewable else "review_not_open"
        review_state = forecast["review"]
        training_eligibility, applied_refs = _training_eligibility(forecast, review_state, now)
        return {
            "forecast_id": forecast["forecast_id"],
            "sensor_id": forecast["sensor_id"],
            "batch_id": forecast["batch_id"],
            "as_of_date": forecast["as_of_date"],
            "horizon_days": forecast["horizon_days"],
            "target_date": forecast["target_date"],
            "contract_version": forecast["contract_version"],
            "issued_at": forecast["issued_at"],
            "snapshot_id": forecast["snapshot_id"],
            "alert": forecast["alert"],
            "score": forecast["score"],
            "score_kind": forecast["score_kind"],
            "display_probability": forecast["display_probability"],
            "probability_status": forecast["probability_status"],
            "probability_reason_code": forecast["probability_reason_code"],
            "decision_threshold": forecast["decision_threshold"],
            "event_threshold": forecast["event_threshold"],
            "model_reference": forecast["model_reference"],
            "ensemble": forecast.get("ensemble"),
            "review": {
                "status": review_state["status"],
                "revision": review_state["revision"],
                "review_open_at": _isoformat_z(review_open_at),
                "reviewable": reviewable,
                "blocked_reason": blocked_reason,
                "latest_review": review_state["latest_review"],
                "training_eligibility": training_eligibility,
                "applied_review_references": applied_refs,
            },
        }

    # -- Revisión humana ----------------------------------------------------

    def submit_review(
        self,
        *,
        forecast_id: str,
        request_id: str,
        expected_revision: int,
        action: str,
        comment: str | None,
        now: datetime,
    ) -> tuple[int, dict[str, Any]]:
        if action not in REVIEW_ACTIONS:
            raise OperationalRepositoryError(
                "invalid_action", "action debe ser confirm o reject.", 422
            )
        if not request_id:
            raise OperationalRepositoryError(
                "invalid_request_id", "request_id es obligatorio.", 422
            )

        with self._locked_document() as document:
            forecast = document["forecasts"].get(forecast_id)
            if forecast is None or forecast["sensor_id"] != self.sensor_id:
                raise OperationalRepositoryError(
                    "forecast_not_found", "La emision no existe para este sensor.", 404
                )
            if is_demo_reserved(self.sensor_id):
                raise _demo_write_locked()

            request_payload = {
                "expected_revision": expected_revision,
                "action": action,
                "comment": comment,
            }
            request_hash = _request_hash(request_payload)
            idem_key = f"{forecast_id}:{request_id}"
            idem_store = document["idempotency"]["review"]
            existing_idem = idem_store.get(idem_key)
            if existing_idem is not None:
                if existing_idem["request_hash"] != request_hash:
                    raise OperationalRepositoryError(
                        "idempotency_conflict",
                        "El request_id ya se uso con otro contenido.",
                        409,
                    )
                snapshot = existing_idem["review_snapshot"]
                rendered = self._render_forecast(forecast, now)
                rendered["review"]["status"] = snapshot["status"]
                rendered["review"]["revision"] = snapshot["revision"]
                rendered["review"]["latest_review"] = snapshot["latest_review"]
                training_eligibility, applied_refs = _training_eligibility(forecast, snapshot, now)
                rendered["review"]["training_eligibility"] = training_eligibility
                rendered["review"]["applied_review_references"] = applied_refs
                return existing_idem["status_code"], rendered["review"]

            review_open_at = _review_open_at(forecast)
            if now < review_open_at:
                raise OperationalRepositoryError(
                    "review_not_open",
                    "La revision todavia no esta abierta.",
                    409,
                    {"review_open_at": _isoformat_z(review_open_at)},
                )

            current_revision = forecast["review"]["revision"]
            if expected_revision != current_revision:
                raise OperationalRepositoryError(
                    "revision_conflict",
                    "La revision esperada no coincide con la revision actual.",
                    409,
                    {
                        "expected_revision": expected_revision,
                        "actual_revision": current_revision,
                    },
                )

            observed_label = forecast["alert"] if action == "confirm" else not forecast["alert"]
            new_revision = current_revision + 1
            review_event = {
                "review_id": "rev_" + uuid4().hex,
                "request_id": request_id,
                "revision": new_revision,
                "forecast_id": forecast_id,
                "action": action,
                "observed_label": observed_label,
                "comment": comment,
                "reviewed_at": _isoformat_z(now),
            }
            document["reviews"].setdefault(forecast_id, []).append(review_event)
            new_status = "confirmed" if action == "confirm" else "rejected"
            forecast["review"]["revision"] = new_revision
            forecast["review"]["status"] = new_status
            forecast["review"]["latest_review"] = review_event

            idem_store[idem_key] = {
                "request_hash": request_hash,
                "status_code": 201,
                "review_snapshot": {
                    "status": new_status,
                    "revision": new_revision,
                    "latest_review": review_event,
                },
            }
            self._write(document)
            rendered = self._render_forecast(forecast, now)
            return 201, rendered["review"]


def _review_open_at(forecast: dict[str, Any]) -> datetime:
    target_date = date.fromisoformat(forecast["target_date"])
    return datetime.combine(target_date, time.min, tzinfo=timezone.utc)


def _training_eligibility(
    forecast: dict[str, Any], review_state: dict[str, Any], now: datetime
) -> tuple[str, list[str]]:
    """Orden de evaluación: madurez, compatibilidad y acción. La
    recalibración real permanece fuera de alcance en esta entrega, por lo
    que `applied` nunca se alcanza aquí: solo la recalibración futura
    puede escribir `applied_review_references`.

    Nota (integración de ensamble): en modo ensamble, `model_reference`
    persiste `calibration_version=None` deliberadamente (no hay una única
    versión de calibración cuando hay 3 calibradores distintos; el detalle
    real vive en `ensemble.components[i].model_reference.calibration_version`,
    sin perderse). Esto significa que una corrección madura (`reject`, target
    ya vencido) sobre un forecast en modo ensamble cae siempre en
    `incompatible_source_model` más abajo — es la consecuencia esperada y
    documentada de esta decisión, no un defecto. No se introduce ningún
    mecanismo de recalibración del ensamble para evitar este estado.
    """
    latest_review = review_state.get("latest_review")
    if latest_review is None:
        return "no_review", []

    target_date = date.fromisoformat(forecast["target_date"])
    server_today = now.astimezone(timezone.utc).date()
    if server_today <= target_date:
        return "waiting_target_maturity", []

    reviewed_at_date = _parse_iso_z(latest_review["reviewed_at"]).date()
    if reviewed_at_date <= target_date:
        return "requires_mature_revalidation", []

    if latest_review["action"] == "confirm":
        return "confirmation_only", []

    # Corrección madura: compatibilidad evaluada únicamente con lo que la
    # propia emisión registró (contrato/horizonte/identidad del modelo
    # fuente). No existe en esta entrega un registro de "modelo activo"
    # para comparar linaje de recalibración; ese cruce queda documentado
    # como brecha pendiente, no inferido.
    if forecast["contract_version"] != OPERATIONAL_CONTRACT_VERSION:
        return "incompatible_contract", []
    model_reference = forecast["model_reference"]
    required_fields = ("model_version", "calibration_version")
    if any(model_reference.get(field) is None for field in required_fields):
        return "incompatible_source_model", []
    return "compatible_correction", []
