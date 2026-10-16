"""Pure, bounded composition of a verified OCI root filesystem manifest."""

from __future__ import annotations

import hashlib
import json
from dataclasses import InitVar, dataclass, field

import human_feedback.runtime_oci_tar as runtime_oci_tar

OCI_ROOTFS_PLAN_SCHEMA = "laya-oci-rootfs-plan-v1"
OCI_ROOTFS_EVIDENCE_SCHEMA = "laya-runtime-oci-rootfs-evidence-v1"
MAX_OCI_ROOTFS_ENTRIES = 65_536
MAX_OCI_ROOTFS_WHITEOUTS = 4_096
MAX_OCI_ROOTFS_METADATA_BYTES = 8 * 1024 * 1024
MAX_OCI_ROOTFS_PATH_COMPONENTS = 32
MAX_OCI_ROOTFS_LINK_HOPS = 16
MAX_OCI_ROOTFS_MUTATIONS = 131_072
MAX_OCI_ROOTFS_MODE = runtime_oci_tar.MAX_OCI_TAR_MODE
MAX_OCI_ROOTFS_UID = runtime_oci_tar.MAX_OCI_TAR_UID
MAX_OCI_ROOTFS_GID = runtime_oci_tar.MAX_OCI_TAR_GID
MAX_OCI_ROOTFS_MTIME = runtime_oci_tar.MAX_OCI_TAR_MTIME

_FACTORY_TOKEN = object()
_CLAIMS = (
    "artifact_integrity_verified",
    "oci_manifest_semantics_verified",
    "oci_layout_controls_bytes_verified",
    "oci_blob_inventory_verified",
    "oci_same_root_capture_verified",
    "oci_manifest_blob_bytes_verified",
    "oci_config_blob_bytes_verified",
    "oci_layer_blobs_bytes_verified",
    "oci_bytes_verified",
    "oci_config_semantics_verified",
    "oci_layer_diff_ids_verified",
    "lock_verified",
    "sbom_verified",
    "lock_sbom_consistent",
    "runtime_config_semantics_verified",
    "checkpoint_manifest_semantics_verified",
    "checkpoint_bytes_verified",
    "oci_rootfs_verified",
    "tar_semantics_verified",
    "origin_verified",
    "license_verified",
    "base_ancestry_verified",
    "rootfs_materialized",
    "runtime_materialized",
    "executor_available",
    "inference_executed",
)


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private OCI rootfs value>"


def _raise_private(message: str) -> None:
    error = ValueError(message)
    error.__suppress_context__ = True
    raise error


def _validate_metadata(mode: object, uid: object, gid: object, mtime: object) -> None:
    if any(
        type(value) is not int or not 0 <= value <= maximum
        for value, maximum in (
            (mode, MAX_OCI_ROOTFS_MODE),
            (uid, MAX_OCI_ROOTFS_UID),
            (gid, MAX_OCI_ROOTFS_GID),
            (mtime, MAX_OCI_ROOTFS_MTIME),
        )
    ):
        raise ValueError("OCI rootfs node metadata is invalid")


@dataclass(frozen=True, slots=True, repr=False)
class LayaOciRootfsPlan:
    schema_version: str
    tar_evidence: runtime_oci_tar.LayaRuntimeOciTarSemanticsEvidence = field(repr=False)
    tar_plan: runtime_oci_tar.LayaOciTarSemanticsPlan = field(repr=False)
    layer_receipts: tuple[runtime_oci_tar.VerifiedLayaOciTarLayer, ...] = field(repr=False)
    runtime_identity: object = field(repr=False)
    _factory_token: InitVar[object]
    oci_rootfs_verified: bool = field(default=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI rootfs plan requires the factory seal token")
        if (
            self.schema_version != OCI_ROOTFS_PLAN_SCHEMA
            or type(self.tar_evidence) is not runtime_oci_tar.LayaRuntimeOciTarSemanticsEvidence
            or self.tar_plan is not self.tar_evidence.plan
            or self.layer_receipts is not self.tar_evidence.receipts
            or self.runtime_identity is not self.tar_evidence.runtime_identity
            or self.oci_rootfs_verified is not False
        ):
            raise ValueError("OCI rootfs plan binding is invalid")
        runtime_oci_tar.canonical_laya_runtime_oci_tar_semantics_summary_bytes(self.tar_evidence)

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class LayaOciRootfsNode:
    path: str = field(repr=False)
    typeflag: str
    size_bytes: int
    link_target: str | None = field(repr=False)
    mode: int = field(repr=False)
    uid: int = field(repr=False)
    gid: int = field(repr=False)
    mtime: int = field(repr=False)
    source_layer_position: int
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI rootfs node requires the factory seal token")
        if (
            type(self.path) is not str
            or not self.path
            or self.path.startswith("/")
            or "\\" in self.path
            or any(part in ("", ".", "..") for part in self.path.split("/"))
            or (len(self.path) >= 2 and self.path[1] == ":")
            or len(self.path.encode("utf-8")) > runtime_oci_tar.MAX_OCI_TAR_PATH_BYTES
            or len(self.path.split("/")) > MAX_OCI_ROOTFS_PATH_COMPONENTS
            or any(ord(character) < 32 or ord(character) == 127 for character in self.path)
            or self.typeflag not in ("0", "1", "2", "5")
            or type(self.size_bytes) is not int
            or not 0 <= self.size_bytes <= runtime_oci_tar.MAX_OCI_TAR_ENTRY_PAYLOAD_BYTES
            or (self.typeflag != "0" and self.size_bytes != 0)
            or (self.typeflag in ("1", "2")) != (type(self.link_target) is str)
            or (self.typeflag not in ("1", "2") and self.link_target is not None)
            or (
                self.link_target is not None
                and (
                    not self.link_target
                    or len(self.link_target.encode("utf-8"))
                    > runtime_oci_tar.MAX_OCI_TAR_LINK_BYTES
                    or any(
                        ord(character) < 32 or ord(character) == 127
                        for character in self.link_target
                    )
                )
            )
            or type(self.source_layer_position) is not int
            or not 0 <= self.source_layer_position < 10
        ):
            raise ValueError("OCI rootfs node binding is invalid")
        _validate_metadata(self.mode, self.uid, self.gid, self.mtime)

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class _LayaOciRootDirectory:
    source_layer_position: int
    mode: int = field(repr=False)
    uid: int = field(repr=False)
    gid: int = field(repr=False)
    mtime: int = field(repr=False)
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if (
            _factory_token is not _FACTORY_TOKEN
            or type(self.source_layer_position) is not int
            or not 0 <= self.source_layer_position < 10
        ):
            raise ValueError("OCI rootfs root directory binding is invalid")
        _validate_metadata(self.mode, self.uid, self.gid, self.mtime)

    __repr__ = _private_repr


def _expected_claims(tar_evidence: object) -> tuple[bool, ...]:
    return tuple(
        True if name == "oci_rootfs_verified" else getattr(tar_evidence, name) for name in _CLAIMS
    )


@dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeOciRootfsEvidence:
    schema_version: str
    plan: LayaOciRootfsPlan = field(repr=False)
    tar_evidence: runtime_oci_tar.LayaRuntimeOciTarSemanticsEvidence = field(repr=False)
    runtime_identity: object = field(repr=False)
    root_directory: _LayaOciRootDirectory | None = field(repr=False)
    nodes: tuple[LayaOciRootfsNode, ...] = field(repr=False)
    rootfs_manifest_sha256: str = field(repr=False)
    _factory_token: InitVar[object]
    artifact_integrity_verified: bool = field(default=True)
    oci_manifest_semantics_verified: bool = field(default=True)
    oci_layout_controls_bytes_verified: bool = field(default=True)
    oci_blob_inventory_verified: bool = field(default=True)
    oci_same_root_capture_verified: bool = field(default=True)
    oci_manifest_blob_bytes_verified: bool = field(default=True)
    oci_config_blob_bytes_verified: bool = field(default=True)
    oci_layer_blobs_bytes_verified: bool = field(default=True)
    oci_bytes_verified: bool = field(default=True)
    oci_config_semantics_verified: bool = field(default=True)
    oci_layer_diff_ids_verified: bool = field(default=True)
    lock_verified: bool = field(default=False)
    sbom_verified: bool = field(default=False)
    lock_sbom_consistent: bool = field(default=False)
    runtime_config_semantics_verified: bool = field(default=False)
    checkpoint_manifest_semantics_verified: bool = field(default=False)
    checkpoint_bytes_verified: bool = field(default=False)
    oci_rootfs_verified: bool = field(default=True)
    tar_semantics_verified: bool = field(default=True)
    origin_verified: bool = field(default=False)
    license_verified: bool = field(default=False)
    base_ancestry_verified: bool = field(default=False)
    rootfs_materialized: bool = field(default=False)
    runtime_materialized: bool = field(default=False)
    executor_available: bool = field(default=False)
    inference_executed: bool = field(default=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI rootfs evidence requires the factory seal token")
        if (
            self.schema_version != OCI_ROOTFS_EVIDENCE_SCHEMA
            or type(self.plan) is not LayaOciRootfsPlan
            or self.tar_evidence is not self.plan.tar_evidence
            or self.runtime_identity is not self.tar_evidence.runtime_identity
            or type(self.nodes) is not tuple
            or tuple(node.path for node in self.nodes)
            != tuple(sorted(node.path for node in self.nodes))
            or len({node.path for node in self.nodes}) != len(self.nodes)
            or any(type(node) is not LayaOciRootfsNode for node in self.nodes)
            or (
                self.root_directory is not None
                and type(self.root_directory) is not _LayaOciRootDirectory
            )
            or any(
                actual is not expected
                for actual, expected in zip(
                    (getattr(self, name) for name in _CLAIMS),
                    _expected_claims(self.tar_evidence),
                    strict=True,
                )
            )
        ):
            raise ValueError("OCI rootfs evidence binding or claim is invalid")
        self.plan.__post_init__(_FACTORY_TOKEN)
        for node in self.nodes:
            node.__post_init__(_FACTORY_TOKEN)
        _validate_namespace({node.path: node for node in self.nodes})
        if self.root_directory is not None:
            self.root_directory.__post_init__(_FACTORY_TOKEN)
        metadata_bytes = sum(
            len(node.path.encode("utf-8"))
            + (0 if node.link_target is None else len(node.link_target.encode("utf-8")))
            for node in self.nodes
        )
        if (
            len(self.nodes) > MAX_OCI_ROOTFS_ENTRIES
            or metadata_bytes > MAX_OCI_ROOTFS_METADATA_BYTES
        ):
            raise ValueError("OCI rootfs evidence aggregate budget is invalid")
        derived_root, derived_nodes = _compose_rootfs_state(self.plan)
        if self.nodes != derived_nodes or self.root_directory != derived_root:
            raise ValueError("OCI rootfs evidence does not match its TAR plan")
        if self.rootfs_manifest_sha256 != _manifest_sha256(self.nodes, self.root_directory):
            raise ValueError("OCI rootfs evidence digest is invalid")

    __repr__ = _private_repr


def _node_from_entry(entry: object, position: int) -> LayaOciRootfsNode:
    return LayaOciRootfsNode(
        path=entry.path,
        typeflag=entry.typeflag,
        size_bytes=entry.size_bytes,
        link_target=entry.link_target,
        mode=entry.mode,
        uid=entry.uid,
        gid=entry.gid,
        mtime=entry.mtime,
        source_layer_position=position,
        _factory_token=_FACTORY_TOKEN,
    )


def _parent_path(path: str) -> str:
    return path.rpartition("/")[0]


def _children_index(
    nodes: dict[str, LayaOciRootfsNode],
) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for path in nodes:
        index.setdefault(_parent_path(path), set()).add(path)
    return index


def _index_insert(children_by_parent: dict[str, set[str]], path: str) -> None:
    children_by_parent.setdefault(_parent_path(path), set()).add(path)


def _remove_subtree(
    nodes: dict[str, LayaOciRootfsNode],
    path: str,
    *,
    children_by_parent: dict[str, set[str]],
    max_removals: int,
) -> int:
    if type(max_removals) is not int or max_removals < 0:
        raise ValueError("OCI rootfs mutation budget is invalid")
    if path not in nodes:
        return 0
    pending = [path]
    removal: list[str] = []
    while pending:
        current = pending.pop()
        removal.append(current)
        if len(removal) > max_removals:
            raise ValueError("OCI rootfs mutation budget exceeded")
        pending.extend(children_by_parent.get(current, ()))
    for current in reversed(removal):
        del nodes[current]
        children_by_parent.pop(current, None)
    siblings = children_by_parent.get(_parent_path(path))
    if siblings is not None:
        siblings.discard(path)
        if not siblings:
            children_by_parent.pop(_parent_path(path), None)
    return len(removal)


def _resolve_link_path(
    path: str,
    nodes: dict[str, LayaOciRootfsNode],
) -> str | None:
    parts = path.split("/") if path else []
    resolved: list[str] = []
    hops = 0
    followed: set[str] = set()
    index = 0
    while index < len(parts):
        component = parts[index]
        candidate = "/".join((*resolved, component))
        node = nodes.get(candidate)
        if node is None or node.typeflag != "2":
            resolved.append(component)
            index += 1
            continue
        if candidate in followed:
            raise ValueError("OCI rootfs link cycle cannot be traversed")
        followed.add(candidate)
        hops += 1
        if hops > MAX_OCI_ROOTFS_LINK_HOPS:
            raise ValueError("OCI rootfs link hop budget exceeded")
        target = node.link_target
        if target is None:
            raise ValueError("OCI rootfs link target is invalid")
        target_parts = [] if target.startswith("/") else list(resolved)
        for target_part in target.split("/"):
            if target_part in ("", "."):
                continue
            if target_part == "..":
                if not target_parts:
                    raise ValueError("OCI rootfs link escapes container root")
                target_parts.pop()
            else:
                target_parts.append(target_part)
        parts = target_parts + parts[index + 1 :]
        if len(parts) > MAX_OCI_ROOTFS_PATH_COMPONENTS:
            raise ValueError("OCI rootfs effective path component budget exceeded")
        resolved = []
        index = 0
    return "/".join(resolved)


def _validate_parent_path(path: str, nodes: dict[str, LayaOciRootfsNode]) -> None:
    parent = path.rpartition("/")[0]
    if not parent:
        return
    components = parent.split("/")
    for position in range(1, len(components) + 1):
        ancestor = nodes.get("/".join(components[:position]))
        if ancestor is not None and ancestor.typeflag == "2":
            raise ValueError("OCI rootfs symlink ancestor cannot be traversed")
    parent_node = nodes.get(parent)
    if parent_node is None or parent_node.typeflag != "5":
        raise ValueError("OCI rootfs parent path is invalid")


def _normalize_root_bound_target(target: str) -> str:
    components: list[str] = []
    for component in target.split("/"):
        if component in ("", "."):
            continue
        if component == "..":
            if not components:
                raise ValueError("OCI rootfs link escapes container root")
            components.pop()
        else:
            components.append(component)
    if not components or len(components) > MAX_OCI_ROOTFS_PATH_COMPONENTS:
        raise ValueError("OCI rootfs link target is invalid")
    return "/".join(components)


def _resolve_hardlink_target(
    target: str,
    nodes: dict[str, LayaOciRootfsNode],
) -> LayaOciRootfsNode:
    current = _normalize_root_bound_target(target)
    followed: set[str] = set()
    hops = 0
    while True:
        if current in followed:
            raise ValueError("OCI rootfs hardlink target cycle is invalid")
        followed.add(current)
        node = nodes.get(current)
        if node is None:
            raise ValueError("OCI rootfs hardlink target is missing")
        if node.typeflag == "0":
            return node
        if node.typeflag != "1" or node.link_target is None:
            raise ValueError("OCI rootfs hardlink target is not regular")
        hops += 1
        if hops > MAX_OCI_ROOTFS_LINK_HOPS:
            raise ValueError("OCI rootfs hardlink hop budget exceeded")
        current = _normalize_root_bound_target(node.link_target)


def _validate_namespace(nodes: dict[str, LayaOciRootfsNode]) -> None:
    for path, node in nodes.items():
        _validate_parent_path(path, nodes)
        if node.typeflag == "1":
            _resolve_hardlink_target(node.link_target or "", nodes)
        elif node.typeflag == "2":
            _resolve_link_path(path, nodes)


def _apply_rootfs_layer(
    nodes: dict[str, LayaOciRootfsNode],
    receipt: runtime_oci_tar.VerifiedLayaOciTarLayer,
    counters: dict[str, int],
    *,
    children_by_parent: dict[str, set[str]] | None = None,
) -> _LayaOciRootDirectory | None:
    working = dict(nodes)
    source_index = _children_index(nodes) if children_by_parent is None else children_by_parent
    working_index = {parent: set(children) for parent, children in source_index.items()}
    pending = dict(counters)
    if len(receipt.entries) > MAX_OCI_ROOTFS_ENTRIES - pending["entries"]:
        raise ValueError("OCI rootfs entries budget exceeded")
    pending["entries"] += len(receipt.entries)
    whiteouts: list[tuple[str, bool]] = []
    additions = []
    for entry in receipt.entries:
        if len(entry.path.split("/")) > MAX_OCI_ROOTFS_PATH_COMPONENTS:
            raise ValueError("OCI rootfs path component budget exceeded")
        pending["metadata"] += len(entry.path.encode("utf-8"))
        if entry.link_target is not None:
            pending["metadata"] += len(entry.link_target.encode("utf-8"))
        if pending["metadata"] > MAX_OCI_ROOTFS_METADATA_BYTES:
            raise ValueError("OCI rootfs metadata budget exceeded")
        base = entry.path.rsplit("/", 1)[-1]
        if base.startswith(".wh."):
            pending["whiteouts"] += 1
            if pending["whiteouts"] > MAX_OCI_ROOTFS_WHITEOUTS:
                raise ValueError("OCI rootfs whiteout budget exceeded")
            if entry.typeflag != "0" or entry.size_bytes != 0 or entry.link_target is not None:
                raise ValueError("OCI rootfs whiteout marker is invalid")
            parent = entry.path.rpartition("/")[0]
            if base == ".wh..wh..opq":
                whiteouts.append((parent, True))
            elif base == ".wh.":
                raise ValueError("OCI rootfs whiteout marker is invalid")
            else:
                target = base[4:]
                if not target:
                    raise ValueError("OCI rootfs whiteout marker is invalid")
                whiteouts.append(((parent + "/" if parent else "") + target, False))
        else:
            additions.append(entry)
    parent_view = dict(working)
    for entry in additions:
        if entry.typeflag == "5":
            parent_view[entry.path] = _node_from_entry(entry, receipt.layer_position)
    for target, opaque in whiteouts:
        parent = target if opaque else target.rpartition("/")[0]
        if parent:
            _validate_parent_path(parent + "/.whiteout", parent_view)
    for target, opaque in whiteouts:
        removed = 0
        if opaque:
            direct_children = tuple(working_index.get(target, ()))
            for child in direct_children:
                available = MAX_OCI_ROOTFS_MUTATIONS - pending["mutations"] - removed
                if available <= 0:
                    raise ValueError("OCI rootfs mutation budget exceeded")
                removed += _remove_subtree(
                    working,
                    child,
                    children_by_parent=working_index,
                    max_removals=available,
                )
        else:
            available = MAX_OCI_ROOTFS_MUTATIONS - pending["mutations"]
            if target in working and available <= 0:
                raise ValueError("OCI rootfs mutation budget exceeded")
            removed = _remove_subtree(
                working,
                target,
                children_by_parent=working_index,
                max_removals=available,
            )
        pending["mutations"] += removed
        if pending["mutations"] > MAX_OCI_ROOTFS_MUTATIONS:
            raise ValueError("OCI rootfs mutation budget exceeded")
    additions.sort(
        key=lambda entry: (
            len(entry.path.split("/")),
            entry.typeflag == "1",
            entry.path,
        )
    )
    for entry in additions:
        _validate_parent_path(entry.path, working)
        existing = working.get(entry.path)
        if entry.typeflag == "5" and existing is not None and existing.typeflag == "5":
            if pending["mutations"] + 2 > MAX_OCI_ROOTFS_MUTATIONS:
                raise ValueError("OCI rootfs mutation budget exceeded")
            del working[entry.path]
            removed = 1
        else:
            available = MAX_OCI_ROOTFS_MUTATIONS - pending["mutations"] - 1
            if available < 0:
                raise ValueError("OCI rootfs mutation budget exceeded")
            removed = _remove_subtree(
                working,
                entry.path,
                children_by_parent=working_index,
                max_removals=available,
            )
        node = _node_from_entry(entry, receipt.layer_position)
        working[node.path] = node
        _index_insert(working_index, node.path)
        pending["mutations"] += removed + 1
        if pending["mutations"] > MAX_OCI_ROOTFS_MUTATIONS:
            raise ValueError("OCI rootfs mutation budget exceeded")
    nodes.clear()
    nodes.update(working)
    counters.clear()
    counters.update(pending)
    if children_by_parent is not None:
        children_by_parent.clear()
        children_by_parent.update(working_index)
    if receipt.root_directory is None:
        return None
    root = receipt.root_directory
    return _LayaOciRootDirectory(
        source_layer_position=receipt.layer_position,
        mode=root.mode,
        uid=root.uid,
        gid=root.gid,
        mtime=root.mtime,
        _factory_token=_FACTORY_TOKEN,
    )


def _manifest_sha256(
    nodes: tuple[LayaOciRootfsNode, ...],
    root_directory: _LayaOciRootDirectory | None,
) -> str:
    manifest = {
        "nodes": [
            {
                "gid": node.gid,
                "link_target": node.link_target,
                "mode": node.mode,
                "mtime": node.mtime,
                "path": node.path,
                "size_bytes": node.size_bytes,
                "source_layer_position": node.source_layer_position,
                "typeflag": node.typeflag,
                "uid": node.uid,
            }
            for node in nodes
        ],
        "root_directory": (
            None
            if root_directory is None
            else {
                "gid": root_directory.gid,
                "mode": root_directory.mode,
                "mtime": root_directory.mtime,
                "source_layer_position": root_directory.source_layer_position,
                "uid": root_directory.uid,
            }
        ),
    }
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _seal_laya_runtime_oci_rootfs_evidence(
    plan: LayaOciRootfsPlan,
    root_directory: _LayaOciRootDirectory | None,
    nodes: tuple[LayaOciRootfsNode, ...],
) -> LayaRuntimeOciRootfsEvidence:
    return LayaRuntimeOciRootfsEvidence(
        schema_version=OCI_ROOTFS_EVIDENCE_SCHEMA,
        plan=plan,
        tar_evidence=plan.tar_evidence,
        runtime_identity=plan.runtime_identity,
        root_directory=root_directory,
        nodes=nodes,
        rootfs_manifest_sha256=_manifest_sha256(nodes, root_directory),
        _factory_token=_FACTORY_TOKEN,
    )


def _compose_rootfs_state(
    plan: LayaOciRootfsPlan,
) -> tuple[_LayaOciRootDirectory | None, tuple[LayaOciRootfsNode, ...]]:
    nodes: dict[str, LayaOciRootfsNode] = {}
    children_by_parent: dict[str, set[str]] = {}
    counters = {"entries": 0, "whiteouts": 0, "metadata": 0, "mutations": 0}
    root_directory = None
    for receipt in plan.layer_receipts:
        current_root = _apply_rootfs_layer(
            nodes,
            receipt,
            counters,
            children_by_parent=children_by_parent,
        )
        if current_root is not None:
            root_directory = current_root
    _validate_namespace(nodes)
    return root_directory, tuple(nodes[path] for path in sorted(nodes))


def prepare_laya_oci_rootfs_plan(
    tar_evidence: runtime_oci_tar.LayaRuntimeOciTarSemanticsEvidence,
) -> LayaOciRootfsPlan:
    """Bind a pure composition plan to exact, deeply validated TAR evidence."""

    failed = False
    result = None
    try:
        result = LayaOciRootfsPlan(
            schema_version=OCI_ROOTFS_PLAN_SCHEMA,
            tar_evidence=tar_evidence,
            tar_plan=tar_evidence.plan,
            layer_receipts=tar_evidence.receipts,
            runtime_identity=tar_evidence.runtime_identity,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("OCI TAR evidence validation failed")
    return result


def compose_laya_oci_rootfs(plan: LayaOciRootfsPlan) -> LayaRuntimeOciRootfsEvidence:
    """Compose the effective rootfs manifest without materializing bytes."""

    failed = False
    result = None
    try:
        if type(plan) is not LayaOciRootfsPlan:
            raise TypeError("OCI rootfs plan type is invalid")
        plan.__post_init__(_FACTORY_TOKEN)
        root_directory, ordered = _compose_rootfs_state(plan)
        result = _seal_laya_runtime_oci_rootfs_evidence(plan, root_directory, ordered)
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("OCI rootfs composition or budget validation failed")
    return result


def canonical_laya_runtime_oci_rootfs_summary_bytes(
    evidence: LayaRuntimeOciRootfsEvidence,
) -> bytes:
    """Return a canonical privacy-safe summary of exact rootfs evidence."""

    failed = False
    result = None
    try:
        if type(evidence) is not LayaRuntimeOciRootfsEvidence:
            raise TypeError("OCI rootfs evidence type is invalid")
        evidence.__post_init__(_FACTORY_TOKEN)
        identity_sha256 = evidence.runtime_identity.sha256
        if (
            type(identity_sha256) is not str
            or len(identity_sha256) != 64
            or any(character not in "0123456789abcdef" for character in identity_sha256)
        ):
            raise ValueError("OCI rootfs runtime identity is invalid")
        summary = {
            "schema_version": evidence.schema_version,
            "plan_schema_version": evidence.plan.schema_version,
            "runtime_identity_sha256": identity_sha256,
        }
        summary.update({name: getattr(evidence, name) for name in _CLAIMS})
        result = (json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("OCI rootfs evidence validation failed")
    return result
