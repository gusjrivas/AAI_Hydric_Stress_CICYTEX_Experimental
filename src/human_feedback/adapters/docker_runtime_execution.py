"""Trusted local-Docker orchestration for one closed synthetic Laya execution."""

from __future__ import annotations

import secrets
import threading
import weakref
from dataclasses import dataclass, field
from enum import Enum

from human_feedback import runtime_execution as _authority
from human_feedback.adapters.docker_runtime_materialization import (
    _lease_laya_runtime_image,
)
from human_feedback.adapters.local_docker_engine import LocalDockerEngine

_LOCK = threading.RLock()
_CLEANUP_ATTEMPTS: dict[int, _CleanupAttempt] = {}
_ERROR_MESSAGE = "secure runtime execution failed"


class RuntimeExecutionFailureStage(str, Enum):
    """Closed privacy-safe stage for one failed synthetic execution attempt."""

    UNKNOWN = "unknown"
    PREDECESSOR_VALIDATION = "predecessor_validation"
    IMAGE_LEASE = "image_lease"
    ENGINE_INITIALIZATION = "engine_initialization"
    CONTAINER_CREATE = "container_create"
    ISOLATION_INSPECTION = "isolation_inspection"
    SYNTHETIC_EXECUTION = "synthetic_execution"
    CONTAINER_CLEANUP = "container_cleanup"
    RECEIPT_ISSUANCE = "receipt_issuance"
    EVIDENCE_ISSUANCE = "evidence_issuance"
    RESOURCE_CLEANUP = "resource_cleanup"


@dataclass(slots=True)
class _CleanupAttempt:
    error_ref: weakref.ReferenceType
    engine: object
    pending: bool = True
    lock: object = field(default_factory=threading.RLock, repr=False)


class DockerRuntimeExecutionError(ValueError):
    """Generic failure with optional private authority to retry child cleanup."""

    __slots__ = ("_failure_stage", "__weakref__")

    def __init__(self, failure_stage: RuntimeExecutionFailureStage) -> None:
        if type(failure_stage) is not RuntimeExecutionFailureStage:
            raise TypeError("runtime execution failure stage is invalid")
        super().__init__(_ERROR_MESSAGE)
        self._failure_stage = failure_stage

    @property
    def failure_stage(self) -> RuntimeExecutionFailureStage:
        return self._failure_stage

    @property
    def cleanup_pending(self) -> bool:
        with _LOCK:
            attempt = _CLEANUP_ATTEMPTS.get(id(self))
            return bool(attempt and attempt.error_ref() is self and attempt.pending)

    def __reduce__(self):
        return _restore_execution_error, (self._failure_stage,)


def _restore_execution_error(
    failure_stage: RuntimeExecutionFailureStage,
) -> DockerRuntimeExecutionError:
    error = DockerRuntimeExecutionError(failure_stage)
    error.__suppress_context__ = True
    return error


def _fail(
    failure_stage: RuntimeExecutionFailureStage = RuntimeExecutionFailureStage.UNKNOWN,
    *,
    pending_engine=None,
) -> None:
    error = DockerRuntimeExecutionError(failure_stage)
    error.__suppress_context__ = True
    if pending_engine is not None:
        identity = id(error)

        def abandon(_reference):
            with _LOCK:
                _CLEANUP_ATTEMPTS.pop(identity, None)

        attempt = _CleanupAttempt(weakref.ref(error, abandon), pending_engine)
        with _LOCK:
            _CLEANUP_ATTEMPTS[identity] = attempt
    raise error from None


def _cleanup_failed_attempt(engine: object) -> bool:
    """Delete only resources owned by this fresh execution engine."""

    try:
        engine.cleanup_owned_resources()
        return True
    except Exception:
        return False


def execute_laya_runtime(plan: _authority.LayaRuntimeExecutionPlan):
    """Execute the fixed synthetic probe and issue authority only after cleanup."""

    engine = None
    evidence = None
    pending_engine = None
    cleanup_attempted = False
    cleanup_succeeded = False
    valid = False
    lease_body_completed = False
    stage = RuntimeExecutionFailureStage.PREDECESSOR_VALIDATION
    try:
        issued_plan = _authority._revalidate_plan(plan)
        stage = RuntimeExecutionFailureStage.IMAGE_LEASE
        with _lease_laya_runtime_image(issued_plan._runtime_evidence) as lease:
            try:
                if lease.image_id != issued_plan._image_id:
                    raise ValueError("runtime execution image lease binding is invalid")
                stage = RuntimeExecutionFailureStage.ENGINE_INITIALIZATION
                engine = LocalDockerEngine(secrets.token_hex(32))
                stage = RuntimeExecutionFailureStage.CONTAINER_CREATE
                container_id = engine.create_closed_synthetic_probe_container(lease.image_id)
                stage = RuntimeExecutionFailureStage.ISOLATION_INSPECTION
                engine.inspect_closed_synthetic_probe_container(
                    container_id,
                    expected_image_id=lease.image_id,
                )
                stage = RuntimeExecutionFailureStage.SYNTHETIC_EXECUTION
                canonical_observation = engine.run_closed_synthetic_probe(
                    container_id,
                    expected_image_id=lease.image_id,
                )
                stage = RuntimeExecutionFailureStage.CONTAINER_CLEANUP
                cleanup_attempted = True
                engine.cleanup_owned_resources()
                cleanup_succeeded = True
                stage = RuntimeExecutionFailureStage.RECEIPT_ISSUANCE
                receipt = _authority._issue_laya_runtime_execution_receipt(
                    issued_plan,
                    canonical_observation,
                )
                stage = RuntimeExecutionFailureStage.EVIDENCE_ISSUANCE
                evidence = _authority._seal_laya_runtime_execution_evidence(issued_plan, receipt)
                lease_body_completed = True
            finally:
                # Normal failures must remove the child while the borrowed image is
                # still leased.  A failed cleanup is recorded once for explicit retry;
                # it is never repeated automatically after the lease is released.
                if engine is not None and not cleanup_attempted:
                    cleanup_attempted = True
                    cleanup_succeeded = _cleanup_failed_attempt(engine)
                    if not cleanup_succeeded:
                        pending_engine = engine
        valid = True
    except Exception:
        if lease_body_completed:
            stage = RuntimeExecutionFailureStage.UNKNOWN
        valid = False
    finally:
        if not valid:
            if evidence is not None:
                try:
                    _authority._revoke_evidence(evidence)
                except Exception:
                    pass
            if engine is not None and not cleanup_succeeded:
                if cleanup_attempted:
                    pending_engine = engine
                elif not _cleanup_failed_attempt(engine):
                    pending_engine = engine
    if not valid:
        _fail(stage, pending_engine=pending_engine)
    return evidence


def retry_laya_runtime_execution_cleanup(error: DockerRuntimeExecutionError) -> None:
    """Retry only the exact failed attempt's child cleanup; never touch its image."""

    valid = False
    try:
        with _LOCK:
            attempt = _CLEANUP_ATTEMPTS.get(id(error))
        exact = (
            type(error) is DockerRuntimeExecutionError
            and attempt is not None
            and attempt.error_ref() is error
        )
        if exact:
            with attempt.lock:
                if not attempt.pending or _cleanup_failed_attempt(attempt.engine):
                    attempt.pending = False
                    valid = True
    except Exception:
        valid = False
    if not valid:
        _fail(RuntimeExecutionFailureStage.RESOURCE_CLEANUP)
