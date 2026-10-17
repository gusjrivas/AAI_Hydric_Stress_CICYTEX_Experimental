"""Concrete, gold-blind LOSO port over one exact local runtime image."""

from __future__ import annotations

import json
import secrets
import threading
import weakref
from dataclasses import dataclass, field

from human_feedback import runtime_materialization as _authority
from human_feedback.adapters.docker_runtime_materialization import (
    _lease_laya_runtime_image,
)
from human_feedback.adapters.local_docker_engine import LocalDockerEngine
from human_feedback.loso_offline_adapter import (
    GoldBlindOfflineInput,
    canonical_laya_loso_offline_request_bytes,
    validate_laya_loso_offline_response,
)

_ERROR_MESSAGE = "secure offline Laya prediction failed"
_REQUEST_SCHEMA = "laya-gold-blind-offline-request-v2"
_LOCK = threading.RLock()
_CLEANUP_ATTEMPTS: dict[int, _CleanupAttempt] = {}


@dataclass(slots=True)
class _CleanupAttempt:
    error_ref: weakref.ReferenceType
    engine: object
    pending: bool = True
    lock: object = field(default_factory=threading.RLock, repr=False)


class DockerLayaLosoOfflineError(ValueError):
    """Generic failure with private authority to retry an owned child cleanup."""

    __slots__ = ("__weakref__",)

    def __init__(self) -> None:
        super().__init__(_ERROR_MESSAGE)

    @property
    def cleanup_pending(self) -> bool:
        with _LOCK:
            attempt = _CLEANUP_ATTEMPTS.get(id(self))
            return bool(attempt and attempt.error_ref() is self and attempt.pending)

    def __reduce__(self):
        return _restore_error, ()


def _restore_error() -> DockerLayaLosoOfflineError:
    error = DockerLayaLosoOfflineError()
    error.__suppress_context__ = True
    return error


def _fail(*, pending_engine=None) -> None:
    error = DockerLayaLosoOfflineError()
    error.__suppress_context__ = True
    if pending_engine is not None:
        identity = id(error)
        attempt = None

        def abandon(_reference):
            with _LOCK:
                if _CLEANUP_ATTEMPTS.get(identity) is attempt:
                    _CLEANUP_ATTEMPTS.pop(identity, None)

        attempt = _CleanupAttempt(weakref.ref(error, abandon), pending_engine)
        with _LOCK:
            _CLEANUP_ATTEMPTS[identity] = attempt
    raise error from None


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if type(key) is not str or key in value:
            raise ValueError("offline request object is not closed")
        value[key] = item
    return value


def _reject_nonfinite(_value: str) -> None:
    raise ValueError("offline request contains a non-finite number")


def _preflight_request(canonical_request: object) -> int:
    if type(canonical_request) is not bytes:
        raise ValueError("offline request is not immutable bytes")
    if not 0 < len(canonical_request) <= 64 * 1024:
        raise ValueError("offline request has invalid size")
    request = json.loads(
        canonical_request.decode("utf-8"),
        object_pairs_hook=_closed_object,
        parse_constant=_reject_nonfinite,
    )
    if type(request) is not dict or set(request) != {"schema_version", "items"}:
        raise ValueError("offline request envelope is invalid")
    if request["schema_version"] != _REQUEST_SCHEMA:
        raise ValueError("offline request schema is invalid")
    items = request["items"]
    if type(items) is not list:
        raise ValueError("offline request items are invalid")
    projected = []
    for item in items:
        if type(item) is not dict or set(item) != {"token", "comment"}:
            raise ValueError("offline request item is invalid")
        projected.append(
            GoldBlindOfflineInput(
                opaque_token=item["token"],
                comment=item["comment"],
            )
        )
    canonical = canonical_laya_loso_offline_request_bytes(tuple(projected))
    if canonical != canonical_request:
        raise ValueError("offline request is not canonical")
    return len(projected)


def _cleanup_failed_attempt(engine: object) -> bool:
    try:
        engine.cleanup_owned_resources()
        return True
    except Exception:
        return False


@dataclass(frozen=True, slots=True, repr=False, init=False)
class DockerLayaLosoOfflinePort:
    """A private immutable binding to one live runtime materialization."""

    _runtime_evidence: _authority.LayaRuntimeMaterializationEvidence = field(repr=False)

    def __init__(self, runtime_evidence):
        issued = None
        try:
            issued = _authority._require_issued_evidence(runtime_evidence)
        except Exception:
            pass
        if issued is None:
            _fail()
        object.__setattr__(self, "_runtime_evidence", issued)

    def predict(self, canonical_request: bytes) -> bytes:
        """Run one bounded batch and return only a canonical closed response."""

        engine = None
        result = None
        pending_engine = None
        cleanup_attempted = False
        cleanup_succeeded = False
        valid = False
        try:
            expected_count = _preflight_request(canonical_request)
            runtime = _authority._require_issued_evidence(self._runtime_evidence)
            with _lease_laya_runtime_image(runtime) as lease:
                try:
                    current = _authority._require_issued_evidence(runtime)
                    if current is not runtime or lease.image_id != runtime._image_id:
                        raise ValueError("offline runtime image binding is invalid")
                    engine = LocalDockerEngine(secrets.token_hex(32))
                    container_id = engine.create_closed_loso_offline_container(lease.image_id)
                    engine.inspect_closed_loso_offline_container(
                        container_id,
                        expected_image_id=lease.image_id,
                    )
                    stdout = engine.run_closed_loso_offline(
                        container_id,
                        expected_image_id=lease.image_id,
                        canonical_request=canonical_request,
                    )
                    result = validate_laya_loso_offline_response(
                        stdout,
                        expected_count=expected_count,
                    )
                    cleanup_attempted = True
                    engine.cleanup_owned_resources()
                    cleanup_succeeded = True
                finally:
                    if engine is not None and not cleanup_attempted:
                        cleanup_attempted = True
                        cleanup_succeeded = _cleanup_failed_attempt(engine)
                        if not cleanup_succeeded:
                            pending_engine = engine
            valid = True
        except Exception:
            valid = False
        finally:
            if not valid and engine is not None and not cleanup_succeeded:
                if cleanup_attempted:
                    pending_engine = engine
                elif not _cleanup_failed_attempt(engine):
                    pending_engine = engine
        if not valid or result is None:
            _fail(pending_engine=pending_engine)
        return result


def retry_laya_loso_offline_cleanup(error: DockerLayaLosoOfflineError) -> None:
    """Retry cleanup only for the exact failed prediction attempt."""

    valid = False
    try:
        with _LOCK:
            attempt = _CLEANUP_ATTEMPTS.get(id(error))
        exact = (
            type(error) is DockerLayaLosoOfflineError
            and attempt is not None
            and attempt.error_ref() is error
        )
        if exact:
            with attempt.lock:
                if not attempt.pending or _cleanup_failed_attempt(attempt.engine):
                    attempt.pending = False
                    attempt.engine = None
                    valid = True
    except Exception:
        valid = False
    if not valid:
        _fail()
