"""Fail-closed filesystem boundary for a disposable Laya rootfs."""

from __future__ import annotations

import os
import hashlib
import re
import secrets
import stat
import sys

from human_feedback import runtime_rootfs_materialization as _authority

__all__ = (
    "RootfsMaterializationError",
    "SecureRootfsMaterializationUnavailableError",
    "materialize_laya_runtime_rootfs",
)

STAGING_MODE = 0o700
DESTINATION_MUST_BE_ABSENT = True
STAGING_IS_DESTINATION_SIBLING = True
ATOMIC_NO_CLOBBER_REQUIRED = True
_MAX_ROOT_COMPONENTS = 128
_DESTINATION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class RootfsMaterializationError(ValueError):
    """A rootfs could not be materialized without weakening its authority."""


class SecureRootfsMaterializationUnavailableError(RootfsMaterializationError):
    """The host lacks the required non-root Linux filesystem capabilities."""


def _raise_private(error_type: type[RootfsMaterializationError], message: str) -> None:
    error = error_type(message)
    error.__suppress_context__ = True
    raise error from None


def _secure_rootfs_materialization_available() -> bool:
    required_flags = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW")
    return (
        sys.platform.startswith("linux")
        and hasattr(os, "geteuid")
        and os.geteuid() != 0
        and all(hasattr(os, flag) for flag in required_flags)
        and os.open in os.supports_dir_fd
        and os.mkdir in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
    )


def _absolute_root_components(value: object, label: str) -> tuple[str, ...]:
    if (
        type(value) is not str
        or not value.startswith("/")
        or value.startswith("//")
        or value == "/"
        or value.endswith("/")
        or "\\" in value
        or "\x00" in value
    ):
        _raise_private(RootfsMaterializationError, f"{label} is not a canonical root")
    components = tuple(value[1:].split("/"))
    if (
        not components
        or len(components) > _MAX_ROOT_COMPONENTS
        or any(component in {"", ".", ".."} for component in components)
    ):
        _raise_private(RootfsMaterializationError, f"{label} is not a canonical root")
    return components


def _validate_destination_name(value: object) -> str:
    if type(value) is not str or value in {".", ".."} or _DESTINATION_NAME.fullmatch(value) is None:
        _raise_private(RootfsMaterializationError, "destination name is invalid")
    return value


def _validate_private_parent_stat(parent_stat: object, *, effective_uid: int) -> None:
    try:
        mode = parent_stat.st_mode
        uid = parent_stat.st_uid
        valid = (
            type(mode) is int
            and type(uid) is int
            and type(effective_uid) is int
            and stat.S_ISDIR(mode)
            and uid == effective_uid
            and mode & 0o022 == 0
        )
    except Exception:
        valid = False
    if not valid:
        _raise_private(RootfsMaterializationError, "destination parent is not private")


def _require_destination_absent(
    *,
    parent_fd: int,
    destination_name: str,
    stat_fn: object = os.stat,
) -> None:
    try:
        stat_fn(destination_name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except Exception:
        _raise_private(RootfsMaterializationError, "destination absence check failed")
    _raise_private(RootfsMaterializationError, "destination already exists")


def _preflight_plan(plan: object) -> _authority.LayaRuntimeRootfsMaterializationPlan:
    result = None
    try:
        if type(plan) is not _authority.LayaRuntimeRootfsMaterializationPlan:
            raise TypeError("rootfs materialization plan type is invalid")
        plan.__post_init__(_authority._FACTORY_TOKEN)
        _authority.prepare_laya_runtime_rootfs_materialization_plan(
            plan._rootfs_evidence,
            plan._supply_evidence,
        )
        result = plan
    except Exception:
        result = None
    if result is None:
        _raise_private(
            RootfsMaterializationError,
            "rootfs materialization authority validation failed",
        )
    return result


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _inode(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _open_directory_chain(components: tuple[str, ...]) -> int:
    descriptor = None
    result = None
    try:
        descriptor = os.open("/", _directory_flags())
        for component in components:
            if type(component) is not str or component in {"", ".", ".."} or "/" in component:
                raise ValueError("invalid directory component")
            child = os.open(component, _directory_flags(), dir_fd=descriptor)
            previous, descriptor = descriptor, child
            os.close(previous)
        result, descriptor = descriptor, None
    except Exception:
        result = None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if result is None:
        _raise_private(RootfsMaterializationError, "secure directory traversal failed")
    return result


def _create_staging(parent_fd: int) -> tuple[str, int, tuple[int, int]]:
    name = ".laya-staging-" + secrets.token_hex(16)
    os.mkdir(name, STAGING_MODE, dir_fd=parent_fd)
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent_fd)
        metadata = os.fstat(descriptor)
        if stat.S_IMODE(metadata.st_mode) != STAGING_MODE or metadata.st_uid != os.geteuid():
            os.close(descriptor)
            raise RootfsMaterializationError("private staging verification failed")
        return name, descriptor, _inode(metadata)
    except Exception:
        os.rmdir(name, dir_fd=parent_fd)
        raise


def _require_owned_name(parent_fd: int, name: str, descriptor: int, identity: tuple[int, int]):
    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or _inode(metadata) != identity
        or _inode(os.fstat(descriptor)) != identity
        or metadata.st_uid != os.geteuid()
    ):
        _raise_private(RootfsMaterializationError, "owned rootfs identity changed")


def _remove_owned_tree(
    parent_fd: int, name: str, descriptor: int, identity: tuple[int, int]
) -> None:
    _require_owned_name(parent_fd, name, descriptor, identity)
    # Keep traversal bounded and descriptor-relative; symlinks are unlinked as leaves.
    remaining = 131072

    def remove_children(directory: int, depth: int) -> None:
        nonlocal remaining
        if depth > 128:
            raise RootfsMaterializationError("rootfs cleanup depth exceeded")
        os.fchmod(directory, STAGING_MODE)
        with os.scandir(directory) as entries:
            for entry in entries:
                remaining -= 1
                if remaining < 0:
                    raise RootfsMaterializationError("rootfs cleanup entry budget exceeded")
                metadata = os.stat(entry.name, dir_fd=directory, follow_symlinks=False)
                if stat.S_ISDIR(metadata.st_mode):
                    child = os.open(entry.name, _directory_flags(), dir_fd=directory)
                    try:
                        if _inode(os.fstat(child)) != _inode(metadata):
                            raise RootfsMaterializationError("rootfs cleanup identity changed")
                        remove_children(child, depth + 1)
                        _require_owned_name(directory, entry.name, child, _inode(metadata))
                        os.rmdir(entry.name, dir_fd=directory)
                    finally:
                        os.close(child)
                else:
                    os.unlink(entry.name, dir_fd=directory)

    remove_children(descriptor, 0)
    _require_owned_name(parent_fd, name, descriptor, identity)
    os.rmdir(name, dir_fd=parent_fd)


def _publish_noreplace(parent_fd: int, source: str, destination: str) -> None:
    import ctypes

    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        _raise_private(
            SecureRootfsMaterializationUnavailableError, "atomic rootfs publication unavailable"
        )
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(parent_fd, os.fsencode(source), parent_fd, os.fsencode(destination), 1) != 0:
        _raise_private(RootfsMaterializationError, "atomic rootfs publication failed")


def _open_relative_parent(root_fd: int, path: str) -> tuple[int, str]:
    components = path.split("/")
    if any(part in {"", ".", ".."} for part in components):
        raise RootfsMaterializationError("invalid relative rootfs path")
    descriptor = os.dup(root_fd)
    try:
        for component in components[:-1]:
            child = os.open(component, _directory_flags(), dir_fd=descriptor)
            previous, descriptor = descriptor, child
            os.close(previous)
        return descriptor, components[-1]
    except BaseException:
        os.close(descriptor)
        raise


class _RootfsWriter:
    """Route bounded chunks only to regular files surviving the final namespace."""

    def __init__(self, root_fd: int, nodes: tuple[object, ...]) -> None:
        self.root_fd = root_fd
        self.expected = {node.path: node for node in nodes if node.typeflag == "0"}
        self.hashes: dict[str, str] = {}
        self.active: set[_RegularPayloadSink] = set()
        self.budget = sum(node.size_bytes for node in self.expected.values())
        if self.budget > 3 * 1024 * 1024 * 1024:
            raise RootfsMaterializationError("rootfs payload budget exceeded")
        capacity = os.fstatvfs(root_fd)
        if self.budget > capacity.f_bavail * capacity.f_frsize:
            raise RootfsMaterializationError("rootfs scratch capacity unavailable")
        for node in sorted(nodes, key=lambda item: (item.path.count("/"), item.path)):
            if node.typeflag == "5":
                parent, name = _open_relative_parent(root_fd, node.path)
                try:
                    os.mkdir(name, STAGING_MODE, dir_fd=parent)
                finally:
                    os.close(parent)

    def sink(self, position: int) -> _RegularPayloadSink:
        return _RegularPayloadSink(self, position)

    def finish_regulars(self) -> dict[str, str]:
        if self.active or self.budget != 0 or self.hashes.keys() != self.expected.keys():
            raise RootfsMaterializationError("rootfs payload coverage incomplete")
        return dict(self.hashes)

    def close(self) -> None:
        for sink in tuple(self.active):
            sink.close()


class _RegularPayloadSink:
    def __init__(self, owner: _RootfsWriter, position: int) -> None:
        self.owner = owner
        self.position = position
        self.descriptor: int | None = None
        self.node = None
        self.remaining = 0
        self.digest = None

    def start(self, entry: object) -> None:
        if self.descriptor is not None:
            raise RootfsMaterializationError("rootfs payload already active")
        node = self.owner.expected.get(entry.path)
        self.node = None
        if node is None or node.source_layer_position != self.position:
            return
        if node.path in self.owner.hashes or any(
            getattr(node, field) != getattr(entry, field)
            for field in ("typeflag", "size_bytes", "link_target", "mode", "uid", "gid", "mtime")
        ):
            raise RootfsMaterializationError("rootfs payload header mismatch")
        parent, name = _open_relative_parent(self.owner.root_fd, node.path)
        try:
            self.descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=parent,
            )
        finally:
            os.close(parent)
        self.node = node
        self.remaining = node.size_bytes
        self.digest = hashlib.sha256()
        self.owner.active.add(self)

    def chunk(self, payload: bytes) -> None:
        if self.node is None:
            return
        if (
            type(payload) is not bytes
            or len(payload) > self.remaining
            or len(payload) > self.owner.budget
        ):
            raise RootfsMaterializationError("rootfs payload byte budget exceeded")
        offset = 0
        while offset < len(payload):
            written = os.write(self.descriptor, payload[offset:])
            if written <= 0 or written > len(payload) - offset:
                raise RootfsMaterializationError("rootfs payload write failed")
            offset += written
            self.remaining -= written
            self.owner.budget -= written
        self.digest.update(payload)

    def end(self) -> None:
        if self.node is None:
            return
        if self.remaining != 0:
            raise RootfsMaterializationError("rootfs payload truncated")
        os.fchmod(self.descriptor, 0o600 | (self.node.mode & 0o100))
        os.fsync(self.descriptor)
        self.owner.hashes[self.node.path] = self.digest.hexdigest()
        self.close()

    def close(self) -> None:
        descriptor, self.descriptor = self.descriptor, None
        self.node = None
        self.owner.active.discard(self)
        if descriptor is not None:
            os.close(descriptor)


def materialize_laya_runtime_rootfs(
    plan: object,
    source_root: object,
    destination_parent: object,
    destination_name: object,
) -> _authority.LayaRuntimeRootfsMaterializationEvidence:
    """Validate authority before any path coercion or filesystem mutation."""

    _preflight_plan(plan)
    if not _secure_rootfs_materialization_available():
        _raise_private(
            SecureRootfsMaterializationUnavailableError,
            "secure non-root Linux rootfs materialization is unavailable",
        )
    _raise_private(
        SecureRootfsMaterializationUnavailableError,
        "secure rootfs materialization backend is not installed",
    )
