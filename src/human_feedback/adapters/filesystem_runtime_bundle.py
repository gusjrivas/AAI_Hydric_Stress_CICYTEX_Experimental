"""Secure Linux filesystem boundary for portable runtime bundle verification."""

from __future__ import annotations

import os
import stat
import sys
from typing import Any

from .. import runtime_bundle, runtime_identity

LayaRuntimeBundleSnapshot = runtime_bundle.LayaRuntimeBundleSnapshot
LayaRuntimeManifest = runtime_identity.LayaRuntimeManifest
RuntimeArtifactSpec = runtime_identity.RuntimeArtifactSpec
verify_laya_runtime_artifact_bytes = runtime_bundle.verify_laya_runtime_artifact_bytes

MAX_RUNTIME_BUNDLE_BYTES = 256 * 1024 * 1024


class RuntimeArtifactCaptureError(ValueError):
    """The declared runtime bundle could not be captured safely and completely."""


class SecureRuntimeCaptureUnavailableError(RuntimeArtifactCaptureError):
    """The host lacks the descriptor capabilities required by this boundary."""


def _secure_runtime_capture_available() -> bool:
    required_flags = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    return (
        sys.platform.startswith("linux")
        and all(hasattr(os, name) for name in required_flags)
        and os.open in os.supports_dir_fd
    )


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _file_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def _root_components(root: Any) -> tuple[str, ...]:
    try:
        raw_root = os.fspath(root)
    except TypeError as error:
        raise RuntimeArtifactCaptureError("secure runtime root is invalid") from error
    if not isinstance(raw_root, str) or not os.path.isabs(raw_root):
        raise RuntimeArtifactCaptureError("secure runtime root must be absolute")
    components = tuple(component for component in raw_root.split(os.sep) if component)
    if any(component in {".", ".."} for component in components):
        raise RuntimeArtifactCaptureError("secure runtime root is not canonical")
    return components


def _close_owned_once(owned: list[int]) -> OSError | None:
    """Attempt every owned close once, transferring ownership before the call."""

    first_error: OSError | None = None
    while owned:
        file_descriptor = owned.pop()
        try:
            os.close(file_descriptor)
        except OSError as error:
            if first_error is None:
                first_error = error
    return first_error


def _open_root_directory(root: Any) -> int:
    components = _root_components(root)
    owned: list[int] = []
    try:
        owned.append(os.open("/", _directory_flags()))
        for component in components:
            owned.append(os.open(component, _directory_flags(), dir_fd=owned[-1]))
        root_fd = owned.pop()
        if _close_owned_once(owned) is not None:
            _close_owned_once([root_fd])
            raise RuntimeArtifactCaptureError("secure runtime root traversal cleanup failed")
        return root_fd
    except BaseException:
        _close_owned_once(owned)
        raise


def _stat_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _bounded_read(file_descriptor: int, expected_size: int) -> bytes:
    maximum = expected_size + 1
    chunks: list[bytes] = []
    captured = 0
    while captured < maximum:
        chunk = os.read(file_descriptor, maximum - captured)
        if not chunk:
            break
        chunks.append(chunk)
        captured += len(chunk)
    return b"".join(chunks)


def _path_fingerprint(
    root_fd: int,
    spec: RuntimeArtifactSpec,
) -> tuple[tuple[int, ...], ...]:
    components = spec.path.split("/")
    directory_fds = [os.dup(root_fd)]
    file_fds: list[int] = []
    try:
        fingerprints = [_stat_fingerprint(os.fstat(directory_fds[-1]))]
        for component in components[:-1]:
            directory_fds.append(os.open(component, _directory_flags(), dir_fd=directory_fds[-1]))
            fingerprints.append(_stat_fingerprint(os.fstat(directory_fds[-1])))
        file_fds.append(os.open(components[-1], _file_flags(), dir_fd=directory_fds[-1]))
        metadata = os.fstat(file_fds[-1])
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != spec.size_bytes:
            raise RuntimeArtifactCaptureError(
                "runtime artifact metadata does not match declaration"
            )
        fingerprints.append(_stat_fingerprint(metadata))
        return tuple(fingerprints)
    finally:
        close_error = _close_owned_once(file_fds)
        directory_error = _close_owned_once(directory_fds)
        if close_error is not None or directory_error is not None:
            raise RuntimeArtifactCaptureError(
                "runtime artifact metadata traversal cleanup failed"
            ) from None


def _capture_one(root_fd: int, spec: RuntimeArtifactSpec) -> bytes:
    components = spec.path.split("/")
    directory_fds = [os.dup(root_fd)]
    file_fds: list[int] = []
    try:
        for component in components[:-1]:
            directory_fds.append(os.open(component, _directory_flags(), dir_fd=directory_fds[-1]))
        file_fds.append(os.open(components[-1], _file_flags(), dir_fd=directory_fds[-1]))
        before = os.fstat(file_fds[-1])
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeArtifactCaptureError("runtime artifact target is not a regular file")
        if before.st_size != spec.size_bytes:
            raise RuntimeArtifactCaptureError("runtime artifact size does not match declaration")
        content = _bounded_read(file_fds[-1], spec.size_bytes)
        after = os.fstat(file_fds[-1])
        if _stat_fingerprint(before) != _stat_fingerprint(after):
            raise RuntimeArtifactCaptureError("runtime artifact changed during secure capture")
        if len(content) != spec.size_bytes:
            raise RuntimeArtifactCaptureError("runtime artifact bounded read size mismatch")
        return content
    finally:
        close_error = _close_owned_once(file_fds)
        directory_error = _close_owned_once(directory_fds)
        if close_error is not None or directory_error is not None:
            raise RuntimeArtifactCaptureError("runtime artifact capture cleanup failed") from None


def _preflight_manifest(manifest: object) -> LayaRuntimeManifest:
    if not isinstance(manifest, LayaRuntimeManifest):
        raise RuntimeArtifactCaptureError("runtime artifact manifest is invalid")
    if sum(spec.size_bytes for spec in manifest.artifacts) > MAX_RUNTIME_BUNDLE_BYTES:
        raise RuntimeArtifactCaptureError("declared runtime bundle exceeds capture limit")
    return manifest


def capture_and_verify_laya_runtime_artifacts(
    manifest: LayaRuntimeManifest,
    root: Any,
) -> LayaRuntimeBundleSnapshot:
    """Capture the complete declared bundle and then invoke portable verification."""

    validated_manifest = _preflight_manifest(manifest)
    if not _secure_runtime_capture_available():
        raise SecureRuntimeCaptureUnavailableError(
            "secure runtime capture capability is unavailable"
        )

    root_fds: list[int] = []
    try:
        root_fds.append(_open_root_directory(root))
        root_fd = root_fds[-1]
        payloads: dict[str, bytes] = {}
        fingerprints: dict[str, tuple[tuple[int, ...], ...]] = {}
        for spec in validated_manifest.artifacts:
            fingerprints[spec.path] = _path_fingerprint(root_fd, spec)
            payloads[spec.path] = _capture_one(root_fd, spec)
        for spec in validated_manifest.artifacts:
            if _path_fingerprint(root_fd, spec) != fingerprints[spec.path]:
                raise RuntimeArtifactCaptureError(
                    "runtime artifact path changed before bundle verification"
                )
        if _close_owned_once(root_fds) is not None:
            raise RuntimeArtifactCaptureError("runtime root cleanup failed")
        return verify_laya_runtime_artifact_bytes(validated_manifest, payloads)
    except SecureRuntimeCaptureUnavailableError:
        raise
    except RuntimeArtifactCaptureError:
        raise
    except (OSError, TypeError, ValueError):
        raise RuntimeArtifactCaptureError(
            "secure runtime artifact capture or verification failed"
        ) from None
    finally:
        if _close_owned_once(root_fds) is not None:
            raise RuntimeArtifactCaptureError("runtime root cleanup failed") from None
