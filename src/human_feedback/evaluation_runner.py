"""Fail-closed preparation for the gold-blind LOSO evaluation runner.

The public surface intentionally remains blocked until the real corpus-custody
authority exists.  The private runner below is only a mechanical state-machine
fixture: it proves ordering, resumability, and gold-blind transport boundaries;
it cannot confer scientific authority.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import weakref
from dataclasses import dataclass, field
from typing import Any

from human_feedback import evaluation_run_protocol as _run_protocol

__all__ = (
    "HumanLosoRunnerPreflight",
    "preflight_human_loso_runner",
)

_BLOCKED_CORPUS_STATUS = "BLOCKED_CORPUS_NOT_PROVIDED"


@dataclass(frozen=True, slots=True, repr=False)
class HumanLosoRunnerPreflight:
    """Public, non-authoritative status for the not-yet-supplied real corpus."""

    status: str = _BLOCKED_CORPUS_STATUS
    ready: bool = False
    comment_consumed: bool = False
    inference_invoked: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class _AcceptedBatchReceipt:
    phase: str
    fold_index: int
    item_count: int
    request_sha256: str
    response_sha256: str
    canonical_response: bytes = field(repr=False)
    runtime_identity: object
    model_identity: object
    inference_port: object


@dataclass(frozen=True, slots=True, repr=False)
class _HumanLosoMechanicalRunEvidence:
    mechanical_execution_verified: bool = True
    scientific_execution_completed: bool = False
    calibration_fitted: bool = False
    gold_blind_execution_attested: bool = False
    scientifically_sufficient: bool = False
    eligible_for_shadow_review: bool = False
    production_enablement_authorized: bool = False


@dataclass(slots=True, repr=False)
class _FoldProgress:
    calibration_receipt: _AcceptedBatchReceipt | None = None
    calibration_seal: tuple[_AcceptedBatchReceipt, str] | None = field(default=None, repr=False)
    outer_test_released: bool = False
    test_receipt: _AcceptedBatchReceipt | None = None
    test_seal: tuple[_AcceptedBatchReceipt, str] | None = field(default=None, repr=False)


@dataclass(slots=True, repr=False)
class _ProtocolRunState:
    protocol_ref: weakref.ReferenceType[object]
    condition: threading.Condition = field(
        default_factory=lambda: threading.Condition(threading.RLock())
    )
    owner_thread: int | None = None
    inference_port: object | None = None
    runtime_identity: object | None = None
    model_identity: object | None = None
    folds: list[_FoldProgress] = field(default_factory=list)
    result: _HumanLosoMechanicalRunEvidence | None = None


_STATES_LOCK = threading.Lock()
_STATES: dict[int, _ProtocolRunState] = {}


def _raise_private_failure() -> None:
    raise ValueError("human LOSO mechanical execution is unavailable") from None


def preflight_human_loso_runner(
    protocol: object,
    inference_port: object,
) -> HumanLosoRunnerPreflight:
    """Report the real runner as blocked without inspecting either argument."""

    del protocol, inference_port
    return HumanLosoRunnerPreflight()


def _require_mechanical_fixture_authority(protocol: object) -> object:
    """Private test seam; production has no mechanical-fixture authority."""

    del protocol
    _raise_private_failure()


def _remove_expired_state(
    key: int,
    expected: _ProtocolRunState,
) -> None:
    with _STATES_LOCK:
        if _STATES.get(key) is expected:
            _STATES.pop(key, None)


def _state_for(protocol: object) -> _ProtocolRunState:
    key = id(protocol)
    with _STATES_LOCK:
        existing = _STATES.get(key)
        if existing is not None:
            if existing.protocol_ref() is protocol:
                return existing
            if existing.protocol_ref() is not None:
                _raise_private_failure()

        state: _ProtocolRunState

        def _expired(_reference: weakref.ReferenceType[object]) -> None:
            _remove_expired_state(key, state)

        try:
            protocol_ref = weakref.ref(protocol, _expired)
        except TypeError:
            _raise_private_failure()
        state = _ProtocolRunState(protocol_ref=protocol_ref)
        _STATES[key] = state
        return state


def _identity_from(grant: object, name: str) -> object:
    value = getattr(grant, name, None)
    if value is None:
        _raise_private_failure()
    return value


def _bind_state(
    state: _ProtocolRunState,
    *,
    inference_port: object,
    runtime_identity: object,
    model_identity: object,
    fold_count: int,
) -> None:
    if state.inference_port is None:
        state.inference_port = inference_port
        state.runtime_identity = runtime_identity
        state.model_identity = model_identity
        state.folds = [_FoldProgress() for _ in range(fold_count)]
        return
    if (
        state.inference_port is not inference_port
        or state.runtime_identity is not runtime_identity
        or state.model_identity is not model_identity
        or len(state.folds) != fold_count
    ):
        _raise_private_failure()


def _opaque_token(used: set[str]) -> str:
    for _ in range(4):
        token = secrets.token_hex(32)
        if token not in used:
            used.add(token)
            return token
    _raise_private_failure()


def _accepted_batch(
    *,
    adapter: Any,
    inference_port: object,
    records: tuple[object, ...],
    phase: str,
    fold_index: int,
    runtime_identity: object,
    model_identity: object,
) -> _AcceptedBatchReceipt:
    used_tokens: set[str] = set()
    inputs = tuple(
        adapter.GoldBlindOfflineInput(
            opaque_token=_opaque_token(used_tokens),
            comment=record.comment,
        )
        for record in records
    )
    request = adapter.canonical_laya_loso_offline_request_bytes(inputs)
    if type(request) is not bytes:
        _raise_private_failure()
    output = inference_port.predict(request)
    canonical_response = adapter.validate_laya_loso_offline_response(
        output,
        expected_count=len(records),
    )
    if type(canonical_response) is not bytes:
        _raise_private_failure()
    return _AcceptedBatchReceipt(
        phase=phase,
        fold_index=fold_index,
        item_count=len(records),
        request_sha256=hashlib.sha256(request).hexdigest(),
        response_sha256=hashlib.sha256(canonical_response).hexdigest(),
        canonical_response=canonical_response,
        runtime_identity=runtime_identity,
        model_identity=model_identity,
        inference_port=inference_port,
    )


def _execute_mechanical_state_machine(
    *,
    protocol: object,
    grant: object,
    inference_port: object,
    state: _ProtocolRunState,
    runtime_identity: object,
    model_identity: object,
) -> _HumanLosoMechanicalRunEvidence:
    from human_feedback import loso_offline_adapter as adapter

    for fold_index, fold in enumerate(protocol._plan.folds):
        progress = state.folds[fold_index]
        if progress.calibration_receipt is None:
            receipt = _accepted_batch(
                adapter=adapter,
                inference_port=inference_port,
                records=fold.calibration_records,
                phase="calibration",
                fold_index=fold_index,
                runtime_identity=runtime_identity,
                model_identity=model_identity,
            )
            progress.calibration_receipt = receipt
            progress.calibration_seal = (receipt, receipt.response_sha256)
        if not progress.outer_test_released:
            release = grant.authorize_outer_test(
                fold_index,
                (progress.calibration_receipt,),
            )
            if release is None:
                _raise_private_failure()
            progress.outer_test_released = True
        if progress.test_receipt is None:
            receipt = _accepted_batch(
                adapter=adapter,
                inference_port=inference_port,
                records=fold.test_records,
                phase="test",
                fold_index=fold_index,
                runtime_identity=runtime_identity,
                model_identity=model_identity,
            )
            progress.test_receipt = receipt
            progress.test_seal = (receipt, receipt.response_sha256)
    return _HumanLosoMechanicalRunEvidence()


def _run_human_loso_mechanical_fixture(
    protocol: object,
    inference_port: object,
) -> _HumanLosoMechanicalRunEvidence:
    """Run the private, non-scientific mechanical fixture exactly once."""

    failed = False
    result: _HumanLosoMechanicalRunEvidence | None = None
    state: _ProtocolRunState | None = None
    acquired = False
    try:
        _run_protocol._require_issued_human_loso_execution_protocol(protocol)
        grant = _require_mechanical_fixture_authority(protocol)
        runtime_identity = _identity_from(grant, "runtime_identity")
        model_identity = _identity_from(grant, "model_identity")
        if not callable(getattr(inference_port, "predict", None)):
            _raise_private_failure()
        state = _state_for(protocol)
        owner = threading.get_ident()
        while not acquired:
            with state.condition:
                while state.owner_thread is not None:
                    if state.owner_thread == owner:
                        _raise_private_failure()
                    state.condition.wait()

            # Waiting releases the condition and another execution may fail or
            # external code may tamper with the parent graph.  Deep validation
            # deliberately happens without holding the per-run condition.
            _run_protocol._require_issued_human_loso_execution_protocol(protocol)

            with state.condition:
                if state.owner_thread is not None:
                    continue
                if state.protocol_ref() is not protocol:
                    _raise_private_failure()
                _bind_state(
                    state,
                    inference_port=inference_port,
                    runtime_identity=runtime_identity,
                    model_identity=model_identity,
                    fold_count=len(protocol._plan.folds),
                )
                if state.result is not None:
                    return state.result
                state.owner_thread = owner
                acquired = True

        result = _execute_mechanical_state_machine(
            protocol=protocol,
            grant=grant,
            inference_port=inference_port,
            state=state,
            runtime_identity=runtime_identity,
            model_identity=model_identity,
        )
        with state.condition:
            if state.result is None:
                state.result = result
            result = state.result
    except Exception:
        failed = True
    finally:
        if acquired and state is not None:
            with state.condition:
                state.owner_thread = None
                state.condition.notify_all()
    if failed or result is None:
        _raise_private_failure()
    return result


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sealed_human_loso_mechanical_batches(
    protocol: object,
) -> tuple[_AcceptedBatchReceipt, ...]:
    """Return validated private batch receipts for a completed mechanical run."""

    sealed: tuple[_AcceptedBatchReceipt, ...] | None = None
    try:
        issued = _run_protocol._require_issued_human_loso_execution_protocol(protocol)
        key = id(issued)
        with _STATES_LOCK:
            state = _STATES.get(key)
            if state is None or state.protocol_ref() is not issued:
                raise ValueError

        from human_feedback import loso_offline_adapter as adapter

        with state.condition:
            result = state.result
            if (
                state.owner_thread is not None
                or type(result) is not _HumanLosoMechanicalRunEvidence
                or result.mechanical_execution_verified is not True
                or result.scientific_execution_completed is not False
                or result.calibration_fitted is not False
                or result.gold_blind_execution_attested is not False
                or result.scientifically_sufficient is not False
                or result.eligible_for_shadow_review is not False
                or result.production_enablement_authorized is not False
                or state.inference_port is None
                or state.runtime_identity is None
                or state.model_identity is None
                or len(state.folds) != len(issued._plan.folds)
            ):
                raise ValueError
            receipts: list[_AcceptedBatchReceipt] = []
            for fold_index, fold in enumerate(issued._plan.folds):
                progress = state.folds[fold_index]
                expected = (
                    (
                        "calibration",
                        progress.calibration_receipt,
                        progress.calibration_seal,
                        len(fold.calibration_records),
                    ),
                    (
                        "test",
                        progress.test_receipt,
                        progress.test_seal,
                        len(fold.test_records),
                    ),
                )
                if not progress.outer_test_released:
                    raise ValueError
                for phase, receipt, seal, count in expected:
                    if (
                        type(receipt) is not _AcceptedBatchReceipt
                        or type(seal) is not tuple
                        or len(seal) != 2
                        or seal[0] is not receipt
                        or seal[1] != receipt.response_sha256
                        or receipt.phase != phase
                        or type(receipt.fold_index) is not int
                        or receipt.fold_index != fold_index
                        or type(receipt.item_count) is not int
                        or receipt.item_count != count
                        or not _is_sha256(receipt.request_sha256)
                        or not _is_sha256(receipt.response_sha256)
                        or type(receipt.canonical_response) is not bytes
                        or hashlib.sha256(receipt.canonical_response).hexdigest() != seal[1]
                        or receipt.runtime_identity is not state.runtime_identity
                        or receipt.model_identity is not state.model_identity
                        or receipt.inference_port is not state.inference_port
                        or adapter.validate_laya_loso_offline_response(
                            receipt.canonical_response,
                            expected_count=receipt.item_count,
                        )
                        != receipt.canonical_response
                    ):
                        raise ValueError
                    receipts.append(receipt)
            sealed = tuple(receipts)
    except Exception:
        pass
    if sealed is None:
        _raise_private_failure()
    return sealed
