"""Descriptor-bound, bounded TAR assembly for one offline Laya runtime."""

from __future__ import annotations

import hashlib
import os
import posixpath
import stat
import tarfile
from collections import Counter
from dataclasses import dataclass

from human_feedback import runtime_checkpoint, runtime_oci_tar, runtime_rootfs_materialization
from human_feedback.adapters import filesystem_checkpoint as _checkpoint
from human_feedback.adapters import filesystem_rootfs_materialization as _rootfs

MAX_INSTALLATION_ENTRIES = runtime_oci_tar.MAX_OCI_TAR_ENTRIES
MAX_INSTALLATION_PAYLOAD_BYTES = 3 * 1024 * 1024 * 1024
MAX_INSTALLATION_ARCHIVE_BYTES = 3 * 1024 * 1024 * 1024
_CHUNK_BYTES = 1024 * 1024
_UID = 65532
_GID = 65532
_DOCKER_MANAGED_PATHS = ("etc/hostname", "etc/hosts", "etc/resolv.conf")
_DOCKER_MANAGED_PATH_SET = frozenset(_DOCKER_MANAGED_PATHS)
_MAX_SYMLINK_ALIAS_HOPS = 16
_CHECKPOINT_PREFIX = "opt/laya-runtime/checkpoints/multilingual"
_CHECKPOINT_FILES = (
    ("encoder_config", "encoder/config.json"),
    ("weights", "model.safetensors"),
    ("laya_config", "rl_agent_config.json"),
    ("tokenizer", "tokenizer/tokenizer.json"),
    ("tokenizer_config", "tokenizer/tokenizer_config.json"),
)


class RuntimeInstallationArchiveError(ValueError):
    """The derived runtime archive could not be emitted without weakening authority."""


def _raise_private(message: str = "secure runtime installation archive failed") -> None:
    error = RuntimeInstallationArchiveError(message)
    error.__suppress_context__ = True
    raise error from None


@dataclass(frozen=True, slots=True)
class _InstallationEntry:
    path: str
    kind: str
    mode: int
    size_bytes: int = 0
    link_target: str | None = None
    source: object | None = None
    checkpoint_path: str | None = None
    uid: int = _UID
    gid: int = _GID
    mtime: int = 0
    projected_empty: bool = False


def _same_identity(left: object, right: object) -> bool:
    try:
        return (
            type(left.schema_version) is str
            and left.schema_version == right.schema_version
            and type(left.sha256) is str
            and left.sha256 == right.sha256
        )
    except Exception:
        return False


def _checkpoint_descriptor_tuple(plan: object) -> tuple[tuple[object, ...], ...]:
    return tuple((item.role, item.path, item.sha256, item.size_bytes) for item in plan.files)


def _preflight_authorities(rootfs_evidence: object, checkpoint_evidence: object):
    runtime_rootfs_materialization.canonical_laya_runtime_rootfs_materialization_summary_bytes(
        rootfs_evidence
    )
    runtime_checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(checkpoint_evidence)
    plan = rootfs_evidence._plan
    expected_checkpoint = plan._supply_evidence._provenance_evidence.checkpoint_evidence
    logical_rootfs = plan._rootfs_evidence
    if (
        checkpoint_evidence is not expected_checkpoint
        or logical_rootfs is not plan._rootfs_evidence
        or type(logical_rootfs.nodes) is not tuple
        or type(rootfs_evidence._content_manifest_sha256) is not str
        or len(rootfs_evidence._content_manifest_sha256) != 64
        or not _same_identity(plan._runtime_identity, checkpoint_evidence.runtime_identity)
    ):
        raise ValueError("runtime installation authority binding is invalid")
    return logical_rootfs, logical_rootfs.nodes, rootfs_evidence._content_manifest_sha256


def _checkpoint_installation_entries(
    rootfs_nodes: tuple[object, ...], checkpoint_plan: object
) -> tuple[_InstallationEntry, ...]:
    expected = tuple((role, path) for role, path in _CHECKPOINT_FILES)
    observed = tuple((item.role, item.path) for item in checkpoint_plan.files)
    if observed != expected:
        _raise_private("checkpoint installation mapping is invalid")
    namespace = {node.path: node for node in rootfs_nodes}
    if len(namespace) != len(rootfs_nodes):
        _raise_private("rootfs namespace is invalid")
    for base_parent in ("opt", "opt/laya-runtime"):
        node = namespace.get(base_parent)
        if node is not None and node.typeflag != "5":
            _raise_private("checkpoint installation parent is unsafe")
    reserved = "opt/laya-runtime/checkpoints"
    if any(path == reserved or path.startswith(reserved + "/") for path in namespace):
        _raise_private("checkpoint installation collides with rootfs")

    result: list[_InstallationEntry] = []
    for base_parent in ("opt", "opt/laya-runtime"):
        if base_parent not in namespace:
            result.append(_InstallationEntry(base_parent, "directory", 0o700))
    directories = (
        reserved,
        _CHECKPOINT_PREFIX,
        _CHECKPOINT_PREFIX + "/encoder",
        _CHECKPOINT_PREFIX + "/tokenizer",
    )
    result.extend(_InstallationEntry(path, "directory", 0o555) for path in directories)
    for descriptor in checkpoint_plan.files:
        result.append(
            _InstallationEntry(
                path=_CHECKPOINT_PREFIX + "/" + descriptor.path,
                kind="regular",
                mode=0o444,
                size_bytes=descriptor.size_bytes,
                source=descriptor,
                checkpoint_path=descriptor.path,
            )
        )
    return tuple(result)


def _normalized_symlink_target(node: object) -> str | None:
    target = node.link_target
    if type(target) is not str or not target:
        return None
    if target.startswith("/"):
        candidate = target.lstrip("/")
    else:
        candidate = posixpath.join(posixpath.dirname(node.path), target)
    normalized = posixpath.normpath(candidate)
    if normalized == ".":
        return ""
    if normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def _resolved_symlink_target(node: object, namespace: dict[str, object]) -> str | None:
    target = _normalized_symlink_target(node)
    if target is None:
        return None
    visited: set[str] = set()
    for _hop in range(_MAX_SYMLINK_ALIAS_HOPS):
        if target in visited:
            _raise_private("rootfs symlink alias cycle is unsafe")
        visited.add(target)
        components = target.split("/") if target else ()
        for position in range(len(components)):
            prefix = "/".join(components[: position + 1])
            candidate = namespace.get(prefix)
            if candidate is None or candidate.typeflag != "2":
                continue
            replacement = _normalized_symlink_target(candidate)
            if replacement is None:
                return None
            suffix = "/".join(components[position + 1 :])
            target = posixpath.normpath(posixpath.join(replacement, suffix))
            if target == ".":
                target = ""
            if target == ".." or target.startswith("../"):
                return None
            break
        else:
            return target
    _raise_private("rootfs symlink alias hop budget exceeded")


def _aliases_docker_managed_path(node: object, namespace: dict[str, object]) -> bool:
    if node.typeflag == "1":
        return _rootfs._terminal(node, namespace).path in _DOCKER_MANAGED_PATH_SET
    if node.typeflag != "2":
        return False
    target = _resolved_symlink_target(node, namespace)
    if target is None:
        return False
    if target in ("", "etc") or target in _DOCKER_MANAGED_PATH_SET:
        return True
    terminal = namespace.get(target)
    return (
        terminal is not None
        and terminal.typeflag == "1"
        and (_rootfs._terminal(terminal, namespace).path in _DOCKER_MANAGED_PATH_SET)
    )


def _rootfs_entries(nodes: tuple[object, ...]) -> tuple[_InstallationEntry, ...]:
    namespace = {node.path: node for node in nodes}
    if len(namespace) != len(nodes):
        _raise_private("rootfs namespace is invalid")
    etc = namespace.get("etc")
    if etc is not None and etc.typeflag != "5":
        _raise_private("Docker-managed installation parent is unsafe")
    for path in _DOCKER_MANAGED_PATHS:
        node = namespace.get(path)
        if node is not None and node.typeflag != "0":
            _raise_private("Docker-managed installation path is unsafe")
    for node in nodes:
        if node.path not in _DOCKER_MANAGED_PATH_SET and _aliases_docker_managed_path(
            node, namespace
        ):
            _raise_private("Docker-managed installation alias is unsafe")

    result = []
    for node in nodes:
        if node.path in _DOCKER_MANAGED_PATH_SET:
            continue
        if node.typeflag == "5":
            result.append(_InstallationEntry(node.path, "directory", 0o700, source=node))
        elif node.typeflag == "0":
            result.append(
                _InstallationEntry(
                    node.path,
                    "regular",
                    0o600 | (node.mode & 0o100),
                    size_bytes=node.size_bytes,
                    source=node,
                )
            )
        elif node.typeflag == "1":
            terminal = _rootfs._terminal(node, namespace)
            result.append(
                _InstallationEntry(
                    node.path,
                    "hardlink",
                    0o600 | (terminal.mode & 0o100),
                    link_target=terminal.path,
                    source=node,
                )
            )
        elif node.typeflag == "2":
            result.append(
                _InstallationEntry(
                    node.path, "symlink", 0o600, link_target=node.link_target, source=node
                )
            )
        else:
            _raise_private("rootfs archive node type is invalid")
    if etc is None:
        result.append(_InstallationEntry("etc", "directory", 0o700))
    for path in _DOCKER_MANAGED_PATHS:
        result.append(
            _InstallationEntry(
                path=path,
                kind="regular",
                mode=0o755,
                source=namespace.get(path),
                uid=0,
                gid=0,
                projected_empty=True,
            )
        )
    return tuple(result)


def _ordered_entries(
    rootfs_nodes: tuple[object, ...], checkpoint_plan: object
) -> tuple[_InstallationEntry, ...]:
    entries = (
        *_rootfs_entries(rootfs_nodes),
        *_checkpoint_installation_entries(rootfs_nodes, checkpoint_plan),
    )
    rank = {"directory": 0, "regular": 1, "hardlink": 2, "symlink": 3}
    ordered = tuple(
        sorted(entries, key=lambda item: (rank[item.kind], item.path.count("/"), item.path))
    )
    if len(ordered) > MAX_INSTALLATION_ENTRIES or len({item.path for item in ordered}) != len(
        ordered
    ):
        _raise_private("runtime installation entry budget is invalid")
    return ordered


def _tar_info(entry: _InstallationEntry) -> tarfile.TarInfo:
    info = tarfile.TarInfo(entry.path)
    info.uid = entry.uid
    info.gid = entry.gid
    info.uname = ""
    info.gname = ""
    info.mtime = entry.mtime
    info.mode = entry.mode
    if entry.kind == "directory":
        info.type = tarfile.DIRTYPE
        info.size = 0
    elif entry.kind == "regular":
        info.type = tarfile.REGTYPE
        info.size = entry.size_bytes
    elif entry.kind == "hardlink":
        info.type = tarfile.LNKTYPE
        info.linkname = entry.link_target
        info.size = 0
    elif entry.kind == "symlink":
        info.type = tarfile.SYMTYPE
        info.linkname = entry.link_target
        info.size = 0
    else:
        raise ValueError("archive entry kind is invalid")
    return info


def _encoded_header(entry: _InstallationEntry) -> tuple[bytes, int]:
    try:
        info = _tar_info(entry)
        path_bytes = info.name.encode("utf-8", errors="strict")
        link_bytes = info.linkname.encode("utf-8", errors="strict")
        if (
            not path_bytes
            or len(path_bytes) > runtime_oci_tar.MAX_OCI_TAR_PATH_BYTES
            or len(link_bytes) > runtime_oci_tar.MAX_OCI_TAR_LINK_BYTES
        ):
            _raise_private("runtime installation TAR path budget is invalid")
        try:
            return (
                info.tobuf(format=tarfile.USTAR_FORMAT, encoding="utf-8", errors="strict"),
                1,
            )
        except ValueError:
            encoded = info.tobuf(
                format=tarfile.GNU_FORMAT,
                encoding="utf-8",
                errors="strict",
            )
            header_count = 1 + (len(path_bytes) > 100) + (len(link_bytes) > 100)
            return encoded, header_count
    except RuntimeInstallationArchiveError:
        raise
    except Exception:
        _raise_private("runtime installation TAR header is invalid")


def _header(entry: _InstallationEntry) -> bytes:
    return _encoded_header(entry)[0]


def _archive_size(entries: tuple[_InstallationEntry, ...]) -> tuple[int, int]:
    payload = sum(item.size_bytes for item in entries if item.kind == "regular")
    if payload > MAX_INSTALLATION_PAYLOAD_BYTES:
        _raise_private("runtime installation payload budget exceeded")
    total = 1024
    header_count = 0
    for item in entries:
        encoded, physical_headers = _encoded_header(item)
        header_count += physical_headers
        if header_count > MAX_INSTALLATION_ENTRIES:
            _raise_private("runtime installation physical header budget exceeded")
        total += len(encoded)
        if item.kind == "regular":
            total += item.size_bytes + (-item.size_bytes % 512)
        if total > MAX_INSTALLATION_ARCHIVE_BYTES:
            _raise_private("runtime installation archive budget exceeded")
    return payload, total


def _write_all(writer: object, payload: bytes) -> int:
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        written = writer.write(view[offset:])
        if type(written) is not int or written <= 0 or written > len(view) - offset:
            raise RuntimeInstallationArchiveError("runtime installation archive write failed")
        offset += written
    return offset


def _stable_fields(metadata: os.stat_result) -> tuple[object, ...]:
    return tuple(
        getattr(metadata, field)
        for field in (
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
    )


def _stream_file_payload(
    writer: object,
    file_fd: int,
    size_bytes: int,
    expected_sha256: str,
    *,
    checkpoint_path: str | None,
) -> tuple[int, str]:
    before = os.fstat(file_fd)
    if not stat.S_ISREG(before.st_mode) or before.st_size != size_bytes:
        raise RuntimeInstallationArchiveError("runtime installation file metadata changed")
    digest = hashlib.sha256()
    remaining = size_bytes
    written = 0
    while remaining:
        chunk = os.read(file_fd, min(_CHUNK_BYTES, remaining))
        if not chunk:
            raise RuntimeInstallationArchiveError("runtime installation file was truncated")
        digest.update(chunk)
        written += _write_all(writer, chunk)
        remaining -= len(chunk)
    after = os.fstat(file_fd)
    actual = digest.hexdigest()
    if (
        os.read(file_fd, 1)
        or _stable_fields(before) != _stable_fields(after)
        or actual != expected_sha256
    ):
        raise RuntimeInstallationArchiveError("runtime installation file changed")
    return written, actual


def _rootfs_hashes(root_fd: int, nodes: tuple[object, ...]) -> dict[str, str]:
    namespace = {node.path: node for node in nodes}
    groups = Counter(
        _rootfs._terminal(node, namespace).path for node in nodes if node.typeflag == "1"
    )
    result = {}
    for node in nodes:
        if node.typeflag != "0":
            continue
        parent, name = _rootfs._open_relative_parent(root_fd, node.path)
        try:
            result[node.path] = _rootfs._hash_regular(parent, name, node, 1 + groups[node.path])[0]
        finally:
            os.close(parent)
    return result


def _canonical_checkpoint_root(value: object) -> tuple[str, tuple[str, ...]]:
    if (
        type(value) is not str
        or not value.startswith("/")
        or value.startswith("//")
        or value == "/"
        or value.endswith("/")
        or os.path.normpath(value) != value
        or "\\" in value
        or "\x00" in value
    ):
        _raise_private("checkpoint source root is not canonical")
    return value, _checkpoint._root_components(value)


def _open_checkpoint_source(
    checkpoint_evidence: object, checkpoint_source_root: object
) -> tuple[int, tuple[tuple[int, ...], ...], dict[str, tuple[tuple[int, ...], ...]]]:
    root, components = _canonical_checkpoint_root(checkpoint_source_root)
    recaptured = _checkpoint.capture_and_verify_laya_runtime_checkpoint(
        checkpoint_evidence.deployment_evidence, root
    )
    if (
        _checkpoint_descriptor_tuple(recaptured.plan)
        != _checkpoint_descriptor_tuple(checkpoint_evidence.plan)
        or tuple(item.checkpoint_file_bytes_verified for item in recaptured.receipts)
        != (True,) * len(checkpoint_evidence.plan.files)
        or not _same_identity(recaptured.runtime_identity, checkpoint_evidence.runtime_identity)
    ):
        raise RuntimeInstallationArchiveError("checkpoint recapture binding is invalid")
    root_fd = _checkpoint._open_root(components)
    try:
        chain = _checkpoint._open_absolute_chain(components)
        try:
            chain_fingerprints = _checkpoint._chain_fingerprints(chain)
            if _checkpoint._fingerprint(os.fstat(root_fd)) != chain_fingerprints[-1]:
                raise RuntimeInstallationArchiveError("checkpoint source binding changed")
        finally:
            if _checkpoint._close_owned(chain) is not None:
                raise RuntimeInstallationArchiveError("checkpoint source cleanup failed")
        _checkpoint._validate_inventory(root_fd, checkpoint_evidence.plan)
        fingerprints = {
            item.role: _checkpoint._path_fingerprint(root_fd, item)
            for item in checkpoint_evidence.plan.files
        }
        return root_fd, chain_fingerprints, fingerprints
    except BaseException:
        os.close(root_fd)
        raise


def _final_checkpoint_validation(
    root_fd: int,
    checkpoint_source_root: str,
    plan: object,
    chain_fingerprints: tuple[tuple[int, ...], ...],
    fingerprints: dict[str, tuple[tuple[int, ...], ...]],
) -> None:
    _checkpoint._validate_inventory(root_fd, plan)
    if any(
        _checkpoint._path_fingerprint(root_fd, item) != fingerprints[item.role]
        for item in plan.files
    ):
        raise RuntimeInstallationArchiveError("checkpoint source changed during archive")
    components = _checkpoint._root_components(checkpoint_source_root)
    final_chain = _checkpoint._open_absolute_chain(components)
    try:
        if _checkpoint._chain_fingerprints(final_chain) != chain_fingerprints:
            raise RuntimeInstallationArchiveError("checkpoint source root changed during archive")
    finally:
        if _checkpoint._close_owned(final_chain) is not None:
            raise RuntimeInstallationArchiveError("checkpoint source cleanup failed")


def _write_laya_runtime_installation_archive(
    writer: object,
    *,
    lease_root_fd: int,
    rootfs_evidence: object,
    checkpoint_evidence: object,
    checkpoint_source_root: str,
) -> int:
    """Write a deterministic TAR to a caller-owned binary stream; never close it."""

    root_fd = checkpoint_fd = None
    failed = False
    result = None
    try:
        if not callable(getattr(writer, "write", None)) or type(lease_root_fd) is not int:
            raise TypeError("runtime installation archive arguments are invalid")
        logical_rootfs, nodes, commitment = _preflight_authorities(
            rootfs_evidence, checkpoint_evidence
        )
        root_fd = os.dup(lease_root_fd)
        root_metadata = os.fstat(root_fd)
        if not stat.S_ISDIR(root_metadata.st_mode):
            raise RuntimeInstallationArchiveError("leased rootfs descriptor is invalid")
        hashes = _rootfs_hashes(root_fd, nodes)
        if (
            _rootfs._verify_staged_tree(
                root_fd, nodes, hashes, logical_rootfs.rootfs_manifest_sha256
            )
            != commitment
        ):
            raise RuntimeInstallationArchiveError("leased rootfs commitment is invalid")
        checkpoint_fd, chain_fingerprints, checkpoint_fingerprints = _open_checkpoint_source(
            checkpoint_evidence, checkpoint_source_root
        )
        entries = _ordered_entries(nodes, checkpoint_evidence.plan)
        _payload_size, expected_archive_size = _archive_size(entries)

        total = 0
        streamed_rootfs_hashes: dict[str, str] = {}
        for entry in entries:
            total += _write_all(writer, _header(entry))
            if entry.kind != "regular":
                continue
            if entry.projected_empty:
                if (
                    entry.checkpoint_path is not None
                    or entry.size_bytes != 0
                    or entry.path not in _DOCKER_MANAGED_PATH_SET
                ):
                    raise RuntimeInstallationArchiveError(
                        "Docker-managed installation projection is invalid"
                    )
                if entry.source is not None:
                    streamed_rootfs_hashes[entry.path] = hashes[entry.path]
                continue
            descriptor = None
            directories = None
            try:
                if entry.checkpoint_path is not None:
                    directories, descriptor = _checkpoint._open_file_path(
                        checkpoint_fd, entry.checkpoint_path
                    )
                    expected_digest = entry.source.sha256
                else:
                    parent, name = _rootfs._open_relative_parent(root_fd, entry.path)
                    directories = [parent]
                    descriptor = os.open(
                        name,
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                        dir_fd=parent,
                    )
                    expected_digest = hashes[entry.path]
                payload_written, actual_digest = _stream_file_payload(
                    writer,
                    descriptor,
                    entry.size_bytes,
                    expected_digest,
                    checkpoint_path=entry.checkpoint_path,
                )
                total += payload_written
                if entry.checkpoint_path is None:
                    streamed_rootfs_hashes[entry.path] = actual_digest
                padding = -entry.size_bytes % 512
                if padding:
                    total += _write_all(writer, b"\0" * padding)
            finally:
                cleanup_failed = False
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        cleanup_failed = True
                if directories is not None and _checkpoint._close_owned(directories) is not None:
                    cleanup_failed = True
                if cleanup_failed:
                    raise RuntimeInstallationArchiveError(
                        "runtime installation descriptor cleanup failed"
                    )

        _final_checkpoint_validation(
            checkpoint_fd,
            checkpoint_source_root,
            checkpoint_evidence.plan,
            chain_fingerprints,
            checkpoint_fingerprints,
        )
        if (
            streamed_rootfs_hashes != hashes
            or _rootfs._verify_staged_tree(
                root_fd, nodes, streamed_rootfs_hashes, logical_rootfs.rootfs_manifest_sha256
            )
            != commitment
            or _stable_fields(root_metadata) != _stable_fields(os.fstat(root_fd))
        ):
            raise RuntimeInstallationArchiveError("leased rootfs changed during archive")
        total += _write_all(writer, b"\0" * 1024)
        if total != expected_archive_size:
            raise RuntimeInstallationArchiveError("runtime installation archive size is invalid")
        result = total
    except Exception:
        failed = True
    for descriptor in (checkpoint_fd, root_fd):
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                failed = True
    if failed or result is None:
        _raise_private()
    return result
