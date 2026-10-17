"""Assemble, independently recapture and load one owned offline Laya image.

The local daemon/kernel are trusted.  This is not a scientific executor and
never invokes inference.  Imported images are new disposable derivatives; the
source OCI, checkpoint and PR39 tree remain unchanged.
"""

from __future__ import annotations

import secrets
import threading
import weakref
from dataclasses import dataclass, field

from human_feedback import runtime_materialization as _authority
from human_feedback.adapters.filesystem_rootfs_materialization import _lease_laya_runtime_rootfs
from human_feedback.adapters.local_docker_engine import LocalDockerEngine
from human_feedback.adapters.runtime_installation_archive import (
    _write_laya_runtime_installation_archive,
)
from human_feedback.adapters.runtime_installation_verifier import (
    _InstallationTarObservation,
    _verify_exported_installation,
)

_LOCK = threading.RLock()
_RESOURCES: dict[int, _RuntimeResource] = {}
_CLEANUP_ATTEMPTS: dict[int, _CleanupAttempt] = {}


@dataclass(slots=True)
class _RuntimeResource:
    evidence_ref: weakref.ReferenceType
    engine: object
    image_id: str
    revoked: bool = False
    disposed: bool = False
    lock: object = field(default_factory=threading.RLock, repr=False)


@dataclass(slots=True)
class _CleanupAttempt:
    error_ref: weakref.ReferenceType
    engine: object
    pending: bool = True
    lock: object = field(default_factory=threading.RLock, repr=False)


class LayaRuntimeMaterializationError(ValueError):
    """Private failure with an optional issued handle for explicit cleanup retry."""

    __slots__ = ("__weakref__",)

    @property
    def cleanup_pending(self) -> bool:
        with _LOCK:
            attempt = _CLEANUP_ATTEMPTS.get(id(self))
            return bool(attempt and attempt.error_ref() is self and attempt.pending)


def _fail(pending_engine=None) -> None:
    error = LayaRuntimeMaterializationError("secure runtime materialization failed")
    error.__suppress_context__ = True
    if pending_engine is not None:
        identity = id(error)

        def abandon(_reference):
            with _LOCK:
                _CLEANUP_ATTEMPTS.pop(identity, None)

        record = _CleanupAttempt(weakref.ref(error, abandon), pending_engine)
        with _LOCK:
            _CLEANUP_ATTEMPTS[identity] = record
    raise error from None


def _cleanup_failed_attempt(engine):
    # No broad listing/adoption/prune. The engine verifies local IDs and nonce
    # again before each operation. An unavailable daemon can leave an orphan;
    # it can never turn a failed attempt into issued runtime authority.
    try:
        engine.cleanup_owned_resources()
        return True
    except Exception:
        return False


def materialize_laya_runtime(
    plan: _authority.LayaRuntimeMaterializationPlan,
    checkpoint_source_root: str,
) -> _authority.LayaRuntimeMaterializationEvidence:
    """Return authority only for an independently recaptured, loaded derivative."""

    engine = None
    pending_engine = None
    image_id = container_id = evidence = None
    valid = False
    try:
        _authority._revalidate_plan(plan)
        # Keep source disposal serialized until the derivative has been sealed.
        with _lease_laya_runtime_rootfs(plan._rootfs_evidence) as root_fd:
            engine = LocalDockerEngine(secrets.token_hex(32))
            expected = None

            def produce(writer):
                nonlocal expected
                if expected is not None:
                    _fail()
                observer = _InstallationTarObservation(writer)
                written = _write_laya_runtime_installation_archive(
                    observer,
                    lease_root_fd=root_fd,
                    rootfs_evidence=plan._rootfs_evidence,
                    checkpoint_evidence=plan._checkpoint_evidence,
                    checkpoint_source_root=checkpoint_source_root,
                )
                expected = observer.finish()
                return written

            image_id = engine.import_normalized_image(produce)
            if expected is None:
                _fail()
            container_id = engine.create_closed_probe_container(image_id)
            engine.inspect_closed_probe_container(container_id, expected_image_id=image_id)
            with engine.export_stopped_container_stream(container_id) as chunks:
                commitment = _verify_exported_installation(chunks, expected)
            engine.run_closed_probe(container_id, expected_image_id=image_id)
            engine.remove_owned_container(container_id)
            container_id = None
            evidence = _authority._seal_laya_runtime_materialization_evidence(
                plan, image_id, commitment
            )
            key = id(evidence)

            def abandon(_reference):
                # GC never silently deletes external Docker resources.
                with _LOCK:
                    _RESOURCES.pop(key, None)

            resource = _RuntimeResource(weakref.ref(evidence, abandon), engine, image_id)
            with _LOCK:
                _RESOURCES[key] = resource
            valid = True
    except Exception:
        valid = False
    finally:
        if not valid:
            if evidence is not None:
                _authority._revoke_evidence(evidence)
            if engine is not None:
                if not _cleanup_failed_attempt(engine):
                    pending_engine = engine
    if not valid:
        _fail(pending_engine)
    return evidence


def retry_laya_runtime_materialization_cleanup(error: LayaRuntimeMaterializationError) -> None:
    """Retry an exact issued failed-attempt handle without creating authority."""
    valid = False
    try:
        with _LOCK:
            attempt = _CLEANUP_ATTEMPTS.get(id(error))
        if (
            type(error) is not LayaRuntimeMaterializationError
            or attempt is None
            or attempt.error_ref() is not error
        ):
            _fail()
        with attempt.lock:
            if not attempt.pending or _cleanup_failed_attempt(attempt.engine):
                attempt.pending = False
                valid = True
    except Exception:
        valid = False
    if not valid:
        _fail()


def dispose_laya_runtime(evidence: _authority.LayaRuntimeMaterializationEvidence) -> None:
    """Revoke first, then delete only the owned image; retry cleanup explicitly."""

    valid = False
    try:
        with _LOCK:
            resource = _RESOURCES.get(id(evidence))
        if resource is None or resource.evidence_ref() is not evidence:
            _fail()
        with resource.lock:
            if not resource.revoked:
                _authority._revoke_evidence(evidence)
                resource.revoked = True
            if not resource.disposed:
                resource.engine.remove_owned_image(resource.image_id)
                resource.disposed = True
            valid = True
    except Exception:
        valid = False
    if not valid:
        _fail()
