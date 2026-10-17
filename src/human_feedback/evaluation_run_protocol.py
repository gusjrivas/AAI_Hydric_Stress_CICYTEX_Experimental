"""Pure, blocked protocol boundary for future gold-blind LOSO execution.

This module binds an exact issued preregistration to a successor protocol.  It
does not read corpus inputs, choose a calibration method, execute inference, or
grant scientific or operational authority.
"""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
import threading as _threading
import weakref as _weakref
from dataclasses import InitVar as _InitVar
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from typing import Any as _Any

from human_feedback import evaluation_preregistration as _preregistration

__all__ = (
    "HumanLosoExecutionProtocol",
    "prepare_human_loso_execution_protocol",
    "canonical_human_loso_execution_protocol_summary_bytes",
)

_SCHEMA_VERSION = "laya-human-loso-execution-protocol-v1"
_BLOCKED_STATUS = "BLOCKED_CORPUS_NOT_PROVIDED"
_FACTORY_TOKEN = object()
_LOCK = _threading.RLock()


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class HumanLosoExecutionProtocol:
    """Exact-instance protocol binding with deliberately blocked claims."""

    _preregistration: _preregistration.HumanEvaluationPreregistration = _field(repr=False)
    _corpus: _Any = _field(repr=False)
    _plan: _Any = _field(repr=False)
    _preregistration_sha256: str = _field(repr=False)
    _factory_token: _InitVar[object]
    schema_version: str = _field(default=_SCHEMA_VERSION, init=False)
    status: str = _field(default=_BLOCKED_STATUS, init=False)
    protocol_bound: bool = _field(default=True, init=False)
    scientific_execution_completed: bool = _field(default=False, init=False)
    calibration_fitted: bool = _field(default=False, init=False)
    gold_blind_execution_attested: bool = _field(default=False, init=False)
    scientifically_sufficient: bool = _field(default=False, init=False)
    eligible_for_shadow_review: bool = _field(default=False, init=False)
    production_enablement_authorized: bool = _field(default=False, init=False)
    calibration_method_authorized: bool = _field(default=False, init=False)
    outer_test_release_authorized: bool = _field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            _raise_private_protocol_error()


@_dataclass(frozen=True, slots=True, repr=False)
class _IssuedProtocolRecord:
    reference: _Any
    preregistration: _preregistration.HumanEvaluationPreregistration
    corpus: _Any
    plan: _Any
    preregistration_sha256: str


_ISSUED_PROTOCOLS: dict[int, _IssuedProtocolRecord] = {}


def _raise_private_protocol_error() -> None:
    error = ValueError("human LOSO execution protocol authority is invalid")
    error.__suppress_context__ = True
    raise error from None


def _preregistration_digest(
    value: _preregistration.HumanEvaluationPreregistration,
) -> str:
    payload = _preregistration.canonical_human_evaluation_preregistration_summary_bytes(value)
    return _hashlib.sha256(payload).hexdigest()


def _register_protocol(value: HumanLosoExecutionProtocol) -> None:
    key = id(value)

    def cleanup(reference: _weakref.ReferenceType[HumanLosoExecutionProtocol]) -> None:
        with _LOCK:
            current = _ISSUED_PROTOCOLS.get(key)
            if current is not None and current.reference is reference:
                _ISSUED_PROTOCOLS.pop(key, None)

    reference = _weakref.ref(value, cleanup)
    record = _IssuedProtocolRecord(
        reference=reference,
        preregistration=value._preregistration,
        corpus=value._corpus,
        plan=value._plan,
        preregistration_sha256=value._preregistration_sha256,
    )
    with _LOCK:
        if key in _ISSUED_PROTOCOLS:
            _raise_private_protocol_error()
        _ISSUED_PROTOCOLS[key] = record


def _require_issued_human_loso_execution_protocol(
    value: object,
) -> HumanLosoExecutionProtocol:
    """Return only the exact live factory-issued protocol instance."""

    if type(value) is not HumanLosoExecutionProtocol:
        _raise_private_protocol_error()
    with _LOCK:
        record = _ISSUED_PROTOCOLS.get(id(value))
        if record is None or record.reference() is not value:
            _raise_private_protocol_error()
        preregistration = record.preregistration
        corpus = record.corpus
        plan = record.plan
        preregistration_sha256 = record.preregistration_sha256

    issued_preregistration = _preregistration._require_issued_human_evaluation_preregistration(
        preregistration
    )
    try:
        valid = (
            value._preregistration is issued_preregistration
            and value._corpus is corpus
            and value._plan is plan
            and issued_preregistration.corpus is corpus
            and issued_preregistration.plan is plan
            and value._preregistration_sha256 == preregistration_sha256
            and _preregistration_digest(issued_preregistration) == preregistration_sha256
            and value.schema_version == _SCHEMA_VERSION
            and value.status == _BLOCKED_STATUS
            and value.protocol_bound is True
            and value.scientific_execution_completed is False
            and value.calibration_fitted is False
            and value.gold_blind_execution_attested is False
            and value.scientifically_sufficient is False
            and value.eligible_for_shadow_review is False
            and value.production_enablement_authorized is False
            and value.calibration_method_authorized is False
            and value.outer_test_release_authorized is False
        )
    except Exception:
        valid = False
    if not valid:
        _raise_private_protocol_error()
    return value


def prepare_human_loso_execution_protocol(
    preregistration: _preregistration.HumanEvaluationPreregistration,
) -> HumanLosoExecutionProtocol:
    """Bind an exact preregistration while keeping all execution gates blocked."""

    issued = _preregistration._require_issued_human_evaluation_preregistration(preregistration)
    digest = _preregistration_digest(issued)
    protocol = HumanLosoExecutionProtocol(
        _preregistration=issued,
        _corpus=issued.corpus,
        _plan=issued.plan,
        _preregistration_sha256=digest,
        _factory_token=_FACTORY_TOKEN,
    )
    _register_protocol(protocol)
    return _require_issued_human_loso_execution_protocol(protocol)


def _summary(protocol: HumanLosoExecutionProtocol) -> dict[str, object]:
    value = _require_issued_human_loso_execution_protocol(protocol)
    return {
        "schema_version": value.schema_version,
        "status": value.status,
        "protocol_bound": value.protocol_bound,
        "scientific_execution_completed": value.scientific_execution_completed,
        "calibration_fitted": value.calibration_fitted,
        "gold_blind_execution_attested": value.gold_blind_execution_attested,
        "scientifically_sufficient": value.scientifically_sufficient,
        "eligible_for_shadow_review": value.eligible_for_shadow_review,
        "production_enablement_authorized": value.production_enablement_authorized,
        "calibration_method_authorized": value.calibration_method_authorized,
        "outer_test_release_authorized": value.outer_test_release_authorized,
    }


def canonical_human_loso_execution_protocol_summary_bytes(
    protocol: HumanLosoExecutionProtocol,
) -> bytes:
    """Return the closed public blocked-state summary without private bindings."""

    return _json.dumps(
        _summary(protocol),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
