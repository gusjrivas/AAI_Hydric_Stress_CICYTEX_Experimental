"""Fail-closed filesystem boundary for a disposable Laya rootfs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import sys
import threading
import weakref
from collections import Counter
from dataclasses import dataclass

from human_feedback import runtime_oci_rootfs as _rootfs
from human_feedback import runtime_rootfs_materialization as _authority
from human_feedback.adapters import filesystem_oci_layout as _capture

__all__ = (
    "RootfsMaterializationError",
    "SecureRootfsMaterializationUnavailableError",
    "materialize_laya_runtime_rootfs",
    "dispose_laya_runtime_rootfs",
)

STAGING_MODE = 0o700
DESTINATION_MUST_BE_ABSENT = True
STAGING_IS_DESTINATION_SIBLING = True
ATOMIC_NO_CLOBBER_REQUIRED = True
_MAX_ROOT_COMPONENTS = 128
_DESTINATION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_RESOURCE_LOCK = threading.RLock()
_RESOURCES: dict[int, _MaterializedResource] = {}


@dataclass(slots=True, repr=False)
class _MaterializedResource:
    reference: object
    parent_components: tuple[str, ...]
    parent_fd: int | None
    root_fd: int | None
    name: str
    identity: tuple[int, int]
    disposed: bool = False


def _close_resource_descriptors(resource: _MaterializedResource) -> None:
    failed = False
    for field in ("root_fd", "parent_fd"):
        descriptor = getattr(resource, field)
        setattr(resource, field, None)
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                failed = True
    if failed:
        raise RootfsMaterializationError("rootfs resource descriptor cleanup failed")


def _register_resource(evidence, parent_components, parent_fd, root_fd, name, identity):
    key = id(evidence)

    def release(expired):
        with _RESOURCE_LOCK:
            current = _RESOURCES.get(key)
            if current is not None and current.reference is expired:
                _RESOURCES.pop(key, None)
                # Forgetting an attestation closes handles, but never deletes data silently.
                _close_resource_descriptors(current)

    resource = _MaterializedResource(
        weakref.ref(evidence, release), parent_components, parent_fd, root_fd, name, identity
    )
    with _RESOURCE_LOCK:
        _RESOURCES[key] = resource


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
    descriptor = None
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent_fd)
        metadata = os.fstat(descriptor)
        if stat.S_IMODE(metadata.st_mode) != STAGING_MODE or metadata.st_uid != os.geteuid():
            raise RootfsMaterializationError("private staging verification failed")
        return name, descriptor, _inode(metadata)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
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
    try:
        _require_owned_name(parent_fd, name, descriptor, identity)
    except FileNotFoundError:
        metadata = os.fstat(descriptor)
        if _inode(metadata) == identity and metadata.st_nlink == 0:
            return
        _raise_private(RootfsMaterializationError, "owned rootfs name disappeared")
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
                if metadata.st_dev != identity[0]:
                    raise RootfsMaterializationError("rootfs cleanup device changed")
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


def _terminal(node: object, namespace: dict[str, object]) -> object:
    return _rootfs._resolve_hardlink_target(node.link_target, namespace)


def _create_final_links(root_fd: int, nodes: tuple[object, ...]) -> None:
    namespace = {node.path: node for node in nodes}
    for node in nodes:
        if node.typeflag != "1":
            continue
        terminal = _terminal(node, namespace)
        source_parent, source_name = _open_relative_parent(root_fd, terminal.path)
        try:
            parent, name = _open_relative_parent(root_fd, node.path)
            try:
                os.link(
                    source_name,
                    name,
                    src_dir_fd=source_parent,
                    dst_dir_fd=parent,
                    follow_symlinks=False,
                )
            finally:
                os.close(parent)
        finally:
            os.close(source_parent)
    # Symlinks, including absolute OCI targets, are leaves and are never traversed.
    for node in nodes:
        if node.typeflag == "2":
            parent, name = _open_relative_parent(root_fd, node.path)
            try:
                os.symlink(node.link_target, name, dir_fd=parent)
            finally:
                os.close(parent)


def _hash_regular(parent: int, name: str, node: object, links: int) -> tuple[str, tuple[int, int]]:
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent
    )
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size != node.size_bytes
            or before.st_nlink != links
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != 0o600 | (node.mode & 0o100)
        ):
            raise RootfsMaterializationError("staged regular metadata mismatch")
        digest = hashlib.sha256()
        remaining = node.size_bytes
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise RootfsMaterializationError("staged regular payload truncated")
            digest.update(chunk)
            remaining -= len(chunk)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_uid",
            "st_gid",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        after = os.fstat(descriptor)
        if os.read(descriptor, 1) or any(
            getattr(after, field) != getattr(before, field) for field in stable_fields
        ):
            raise RootfsMaterializationError("staged regular payload changed")
        os.fsync(descriptor)
        return digest.hexdigest(), _inode(before)
    finally:
        os.close(descriptor)


def _verify_staged_tree(
    root_fd: int, nodes: tuple[object, ...], hashes: dict[str, str], logical_digest: str
) -> str:
    namespace = {node.path: node for node in nodes}
    groups = Counter(_terminal(node, namespace).path for node in nodes if node.typeflag == "1")
    children: dict[str, set[str]] = {"": set()}
    for node in nodes:
        parent, _, name = node.path.rpartition("/")
        children.setdefault(parent, set()).add(name)
        if node.typeflag == "5":
            children.setdefault(node.path, set())
    for path, expected in children.items():
        descriptor = None
        try:
            if path:
                parent, name = _open_relative_parent(root_fd, path)
                try:
                    descriptor = os.open(name, _directory_flags(), dir_fd=parent)
                finally:
                    os.close(parent)
            else:
                descriptor = os.dup(root_fd)
            metadata = os.fstat(descriptor)
            if (
                set(os.listdir(descriptor)) != expected
                or metadata.st_uid != os.geteuid()
                or stat.S_IMODE(metadata.st_mode) != STAGING_MODE
            ):
                raise RootfsMaterializationError("staged directory inventory mismatch")
            os.fsync(descriptor)
        finally:
            if descriptor is not None:
                os.close(descriptor)
    verified: dict[str, tuple[str, tuple[int, int]]] = {}
    for node in nodes:
        if node.typeflag == "0":
            parent, name = _open_relative_parent(root_fd, node.path)
            try:
                verified[node.path] = _hash_regular(parent, name, node, 1 + groups[node.path])
            finally:
                os.close(parent)
            if verified[node.path][0] != hashes.get(node.path):
                raise RootfsMaterializationError("staged content commitment mismatch")
    commitment = hashlib.sha256(b"laya-rootfs-content-v1\x00" + logical_digest.encode("ascii"))
    for node in sorted(nodes, key=lambda item: item.path):
        terminal = _terminal(node, namespace) if node.typeflag == "1" else None
        parent, name = _open_relative_parent(root_fd, node.path)
        try:
            metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if node.typeflag == "1" and (
                not stat.S_ISREG(metadata.st_mode) or _inode(metadata) != verified[terminal.path][1]
            ):
                raise RootfsMaterializationError("staged hardlink topology mismatch")
            if node.typeflag == "2" and (
                not stat.S_ISLNK(metadata.st_mode)
                or os.readlink(name, dir_fd=parent) != node.link_target
            ):
                raise RootfsMaterializationError("staged symlink topology mismatch")
        finally:
            os.close(parent)
        record = [
            node.path,
            node.typeflag,
            node.size_bytes,
            node.link_target,
            node.mode,
            node.uid,
            node.gid,
            node.mtime,
            node.source_layer_position,
            None if terminal is None else terminal.path,
            hashes.get(node.path if terminal is None else terminal.path),
        ]
        encoded = json.dumps(record, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        commitment.update(len(encoded).to_bytes(8, "big"))
        commitment.update(encoded)
    return commitment.hexdigest()


def materialize_laya_runtime_rootfs(
    plan: object,
    source_root: object,
    destination_parent: object,
    destination_name: object,
) -> _authority.LayaRuntimeRootfsMaterializationEvidence:
    """Validate authority before any path coercion or filesystem mutation."""

    plan = _preflight_plan(plan)
    if not _secure_rootfs_materialization_available():
        _raise_private(
            SecureRootfsMaterializationUnavailableError,
            "secure non-root Linux rootfs materialization is unavailable",
        )
    result = None
    try:
        source = _absolute_root_components(source_root, "source root")
        parent = _absolute_root_components(destination_parent, "destination parent")
        name = _validate_destination_name(destination_name)
        result = _materialize(plan, source, parent, name)
    except Exception:
        result = None
    if result is None:
        _raise_private(RootfsMaterializationError, "secure rootfs materialization failed")
    return result


def _ancestor_identities(descriptor: int) -> set[tuple[int, int]]:
    current = os.dup(descriptor)
    result = set()
    try:
        for _ in range(256):
            identity = _inode(os.fstat(current))
            if identity in result:
                return result
            result.add(identity)
            parent = os.open("..", _directory_flags(), dir_fd=current)
            previous, current = current, parent
            os.close(previous)
        raise RootfsMaterializationError("directory ancestry budget exceeded")
    finally:
        os.close(current)


def _require_root_binding(components: tuple[str, ...], descriptor: int) -> None:
    current = _open_directory_chain(components)
    try:
        if _inode(os.fstat(current)) != _inode(os.fstat(descriptor)):
            raise RootfsMaterializationError("root directory binding changed")
    finally:
        os.close(current)


def _materialize(plan, source_components, parent_components, destination_name):
    source_fd = parent_fd = staging_fd = None
    staging_name = None
    identity = None
    writer = None
    published = False
    result = None
    try:
        source_fd = _open_directory_chain(source_components)
        parent_fd = _open_directory_chain(parent_components)
        _validate_private_parent_stat(os.fstat(parent_fd), effective_uid=os.geteuid())
        if _inode(os.fstat(source_fd)) in _ancestor_identities(parent_fd) or _inode(
            os.fstat(parent_fd)
        ) in _ancestor_identities(source_fd):
            raise RootfsMaterializationError("source and destination must be disjoint")
        _require_destination_absent(parent_fd=parent_fd, destination_name=destination_name)
        staging_name, staging_fd, identity = _create_staging(parent_fd)
        rootfs = plan._rootfs_evidence
        writer = _RootfsWriter(staging_fd, rootfs.nodes)
        _capture._capture_and_verify_tar_semantics(
            rootfs.tar_evidence.plan,
            source_components,
            _payload_sink_factory=writer.sink,
            _expected_tar_receipts=rootfs.tar_evidence.receipts,
        )
        hashes = writer.finish_regulars()
        _require_root_binding(source_components, source_fd)
        _create_final_links(staging_fd, rootfs.nodes)
        commitment = _verify_staged_tree(
            staging_fd, rootfs.nodes, hashes, rootfs.rootfs_manifest_sha256
        )
        _require_owned_name(parent_fd, staging_name, staging_fd, identity)
        _require_root_binding(parent_components, parent_fd)
        _publish_noreplace(parent_fd, staging_name, destination_name)
        published = True
        os.fsync(parent_fd)
        _require_owned_name(parent_fd, destination_name, staging_fd, identity)
        evidence = _authority._seal_laya_runtime_rootfs_materialization_evidence(plan, commitment)
        # Finish source cleanup before transferring ownership to the issued resource.
        os.close(source_fd)
        source_fd = None
        _register_resource(
            evidence, parent_components, parent_fd, staging_fd, destination_name, identity
        )
        parent_fd = staging_fd = None
        result = evidence
        return result
    finally:
        try:
            if writer is not None:
                writer.close()
        finally:
            try:
                if result is None and staging_name is not None:
                    _remove_owned_tree(
                        parent_fd,
                        destination_name if published else staging_name,
                        staging_fd,
                        identity,
                    )
                    os.fsync(parent_fd)
            finally:
                for descriptor in (staging_fd, parent_fd, source_fd):
                    if descriptor is not None:
                        os.close(descriptor)


def dispose_laya_runtime_rootfs(evidence: object) -> None:
    """Revoke and remove only the exact published inode retained by this evidence."""
    failed = False
    try:
        with _RESOURCE_LOCK:
            resource = _RESOURCES.get(id(evidence))
            if resource is None or resource.reference() is not evidence:
                raise RootfsMaterializationError("rootfs resource is not issued")
            if resource.disposed:
                return
            _authority._revoke_evidence(evidence)
            _require_root_binding(resource.parent_components, resource.parent_fd)
            _remove_owned_tree(
                resource.parent_fd, resource.name, resource.root_fd, resource.identity
            )
            os.fsync(resource.parent_fd)
            resource.disposed = True
            _close_resource_descriptors(resource)
    except Exception:
        failed = True
    if failed:
        _raise_private(RootfsMaterializationError, "owned rootfs disposal failed")
