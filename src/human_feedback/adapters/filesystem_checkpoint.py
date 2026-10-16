"""Secure Linux descriptor boundary for exact Laya checkpoint bytes."""

from __future__ import annotations

import os
import stat
import sys
from typing import Any

import human_feedback.runtime_checkpoint as runtime_checkpoint

_MAX_CHECKPOINT_ROOT_COMPONENTS = 128


class CheckpointCaptureError(ValueError):
    """The complete checkpoint could not be captured safely."""


class SecureCheckpointCaptureUnavailableError(CheckpointCaptureError):
    """The host lacks the required secure descriptor capabilities."""


def _secure_capture_available() -> bool:
    return (
        sys.platform.startswith("linux")
        and all(
            hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
        )
        and os.open in os.supports_dir_fd
    )


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _file_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def _close_owned(owned: list[int]) -> OSError | None:
    first_error = None
    while owned:
        descriptor = owned.pop()
        try:
            os.close(descriptor)
        except OSError as error:
            if first_error is None:
                first_error = error
    return first_error


def _drain_owned(owned: list[int]) -> OSError | None:
    return _close_owned(owned)


def _root_components(root: Any) -> tuple[str, ...]:
    coercion_failed = False
    try:
        raw = os.fspath(root)
    except BaseException:
        coercion_failed = True
        raw = None
    if coercion_failed:
        error = CheckpointCaptureError("checkpoint root is invalid")
        error.__suppress_context__ = True
        raise error
    if type(raw) is not str or not os.path.isabs(raw):
        raise CheckpointCaptureError("checkpoint root must be absolute")
    if raw == os.sep:
        raise CheckpointCaptureError("filesystem root cannot be a checkpoint root")
    if raw.startswith(os.sep * 2) or os.sep * 2 in raw or raw.endswith(os.sep):
        raise CheckpointCaptureError("checkpoint root is not canonical")
    components = tuple(raw.split(os.sep)[1:])
    if not components or any(component in ("", ".", "..") for component in components):
        raise CheckpointCaptureError("checkpoint root is not canonical")
    if len(components) > _MAX_CHECKPOINT_ROOT_COMPONENTS:
        raise CheckpointCaptureError("checkpoint root has too many components")
    return components


def _open_root(components: tuple[str, ...]) -> int:
    owned: list[int] = []
    try:
        owned.append(os.open(os.sep, _directory_flags()))
        for component in components:
            next_descriptor = os.open(component, _directory_flags(), dir_fd=owned[-1])
            owned.append(next_descriptor)
        result = owned.pop()
        if _close_owned(owned) is not None:
            _close_owned([result])
            raise CheckpointCaptureError("checkpoint root traversal cleanup failed")
        return result
    except Exception:
        _close_owned(owned)
        raise


def _open_absolute_chain(components: tuple[str, ...]) -> list[int]:
    """Open and retain every descriptor from the filesystem root to the checkpoint."""

    owned: list[int] = []
    try:
        owned.append(os.open(os.sep, _directory_flags()))
        for component in components:
            owned.append(os.open(component, _directory_flags(), dir_fd=owned[-1]))
        return owned
    except Exception:
        _close_owned(owned)
        raise


def _fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _expected_inventory(plan: runtime_checkpoint.LayaRuntimeCheckpointPlan) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for descriptor in plan.files:
        components = descriptor.path.split("/")
        current = ""
        for component in components[:-1]:
            current = component if not current else current + "/" + component
            inventory[current] = "directory"
        inventory[descriptor.path] = "file"
    return inventory


def _expected_adjacency(
    plan: runtime_checkpoint.LayaRuntimeCheckpointPlan,
) -> dict[str, dict[str, str]]:
    adjacency: dict[str, dict[str, str]] = {"": {}}
    for path, kind in _expected_inventory(plan).items():
        parent, _, name = path.rpartition("/")
        adjacency.setdefault(parent, {})[name] = kind
        if kind == "directory":
            adjacency.setdefault(path, {})
    return adjacency


def _scan_inventory(
    root_fd: int,
    plan: runtime_checkpoint.LayaRuntimeCheckpointPlan,
) -> dict[str, str]:
    expected = _expected_adjacency(plan)
    result: dict[str, str] = {}
    owned = [os.dup(root_fd)]
    pending: list[tuple[int, str]] = [(owned[-1], "")]
    try:
        while pending:
            directory_fd, prefix = pending.pop()
            expected_children = expected[prefix]
            observed: set[str] = set()
            with os.scandir(directory_fd) as entries:
                for entry in entries:
                    if entry.name in observed or entry.name not in expected_children:
                        raise CheckpointCaptureError("checkpoint inventory is invalid")
                    observed.add(entry.name)
                    relative = entry.name if not prefix else prefix + "/" + entry.name
                    metadata = entry.stat(follow_symlinks=False)
                    expected_kind = expected_children[entry.name]
                    if expected_kind == "directory" and stat.S_ISDIR(metadata.st_mode):
                        result[relative] = "directory"
                        child = os.open(entry.name, _directory_flags(), dir_fd=directory_fd)
                        owned.append(child)
                        pending.append((child, relative))
                    elif expected_kind == "file" and stat.S_ISREG(metadata.st_mode):
                        result[relative] = "file"
                    else:
                        raise CheckpointCaptureError("checkpoint inventory is invalid")
            if observed != set(expected_children):
                raise CheckpointCaptureError("checkpoint inventory is invalid")
        return result
    finally:
        if _close_owned(owned) is not None:
            raise CheckpointCaptureError("checkpoint inventory cleanup failed") from None


def _open_file_path(root_fd: int, path: str) -> tuple[list[int], int]:
    components = path.split("/")
    directories = [os.dup(root_fd)]
    files: list[int] = []
    try:
        for component in components[:-1]:
            directories.append(os.open(component, _directory_flags(), dir_fd=directories[-1]))
        files.append(os.open(components[-1], _file_flags(), dir_fd=directories[-1]))
        return directories, files.pop()
    except Exception:
        _close_owned(files)
        _close_owned(directories)
        raise


def _path_fingerprint(
    root_fd: int,
    descriptor: runtime_checkpoint.LayaCheckpointFilePlan,
) -> tuple[tuple[int, ...], ...]:
    directories, file_fd = _open_file_path(root_fd, descriptor.path)
    files = [file_fd]
    try:
        directory_fingerprints = tuple(_fingerprint(os.fstat(item)) for item in directories)
        metadata = os.fstat(file_fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size != descriptor.size_bytes
        ):
            raise CheckpointCaptureError("checkpoint file metadata is invalid")
        return directory_fingerprints + (_fingerprint(metadata),)
    finally:
        file_error = _close_owned(files)
        directory_error = _close_owned(directories)
        if file_error is not None or directory_error is not None:
            raise CheckpointCaptureError("checkpoint fingerprint cleanup failed") from None


def _file_chunks(file_fd: int, expected_size: int):
    remaining = expected_size + 1
    while remaining:
        chunk = os.read(
            file_fd,
            min(runtime_checkpoint.MAX_CHECKPOINT_CHUNK_BYTES, remaining),
        )
        if not chunk:
            return
        remaining -= len(chunk)
        yield chunk


def _capture_one(
    root_fd: int,
    plan: runtime_checkpoint.LayaRuntimeCheckpointPlan,
    descriptor: runtime_checkpoint.LayaCheckpointFilePlan,
) -> runtime_checkpoint.VerifiedLayaCheckpointFile:
    directories, file_fd = _open_file_path(root_fd, descriptor.path)
    files = [file_fd]
    try:
        before = os.fstat(file_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size != descriptor.size_bytes
        ):
            raise CheckpointCaptureError("checkpoint file metadata is invalid")
        receipt = runtime_checkpoint.verify_laya_checkpoint_file_chunks(
            plan,
            descriptor.sha256,
            _file_chunks(file_fd, descriptor.size_bytes),
        )
        after = os.fstat(file_fd)
        if _fingerprint(before) != _fingerprint(after):
            raise CheckpointCaptureError("checkpoint file changed during capture")
        return receipt
    finally:
        file_error = _close_owned(files)
        directory_error = _close_owned(directories)
        if file_error is not None or directory_error is not None:
            raise CheckpointCaptureError("checkpoint file capture cleanup failed") from None


def _validate_inventory(
    root_fd: int,
    plan: runtime_checkpoint.LayaRuntimeCheckpointPlan,
) -> None:
    if _scan_inventory(root_fd, plan) != _expected_inventory(plan):
        raise CheckpointCaptureError("checkpoint inventory is invalid")


def _chain_fingerprints(descriptors: list[int]) -> tuple[tuple[int, ...], ...]:
    return tuple(_fingerprint(os.fstat(descriptor)) for descriptor in descriptors)


def capture_and_verify_laya_runtime_checkpoint(
    deployment_evidence: object,
    root: Any,
) -> runtime_checkpoint.LayaRuntimeCheckpointEvidence:
    """Capture exactly five checkpoint files from one stable Linux directory tree."""

    try:
        plan = runtime_checkpoint.prepare_laya_runtime_checkpoint_plan(deployment_evidence)
    except Exception:
        raise CheckpointCaptureError("checkpoint deployment evidence is invalid") from None
    if not _secure_capture_available():
        raise SecureCheckpointCaptureUnavailableError(
            "secure checkpoint capture capability is unavailable"
        )

    components = _root_components(root)

    owned: list[int] = []
    failed = False
    result = None
    try:
        owned.append(_open_root(components))
        root_fd = owned[-1]
        initial_chain = _open_absolute_chain(components)
        owned.extend(initial_chain)
        initial_chain_fingerprints = _chain_fingerprints(initial_chain)
        if _fingerprint(os.fstat(root_fd)) != initial_chain_fingerprints[-1]:
            raise CheckpointCaptureError("checkpoint root path changed during traversal")
        _validate_inventory(root_fd, plan)
        fingerprints = {
            descriptor.role: _path_fingerprint(root_fd, descriptor) for descriptor in plan.files
        }
        receipts = tuple(_capture_one(root_fd, plan, descriptor) for descriptor in plan.files)
        _validate_inventory(root_fd, plan)
        for descriptor in plan.files:
            if _path_fingerprint(root_fd, descriptor) != fingerprints[descriptor.role]:
                raise CheckpointCaptureError("checkpoint path changed before sealing")
        final_chain = _open_absolute_chain(components)
        owned.extend(final_chain)
        if _chain_fingerprints(final_chain) != initial_chain_fingerprints:
            raise CheckpointCaptureError("checkpoint root path changed before sealing")
        if _close_owned(owned) is not None:
            raise CheckpointCaptureError("checkpoint root cleanup failed")
        authority = runtime_checkpoint._seal_laya_checkpoint_capture_authority(plan, receipts)
        result = runtime_checkpoint._seal_laya_runtime_checkpoint_evidence(authority)
    except Exception:
        failed = True
    cleanup_error = _drain_owned(owned)
    if failed or cleanup_error is not None or result is None:
        error = CheckpointCaptureError("secure checkpoint capture failed")
        error.__suppress_context__ = True
        raise error
    return result
