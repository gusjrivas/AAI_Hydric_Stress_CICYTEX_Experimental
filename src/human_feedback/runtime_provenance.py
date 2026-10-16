"""Pure, bounded verification of the pinned Laya Git provenance objects."""

from __future__ import annotations

import hashlib
import json
import re
import weakref
from dataclasses import InitVar, dataclass, field

import tomllib

from . import (
    runtime_bundle,
    runtime_checkpoint,
    runtime_deployment_metadata,
)

PROVENANCE_PLAN_SCHEMA = "laya-runtime-provenance-plan-v1"
PROVENANCE_EVIDENCE_SCHEMA = "laya-runtime-provenance-evidence-v1"
SOURCE_REPOSITORY = "https://github.com/NandhaKishorM/laya"
CHECKPOINT_REPOSITORY = "https://huggingface.co/convaiinnovations/laya"
SOURCE_COMMIT = "68804629e8ccd9d616d48a40e87de9fabbeae069"
CHECKPOINT_COMMIT = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"

MAX_PROVENANCE_OBJECTS = 16
MAX_PROVENANCE_OBJECT_BYTES = 64 * 1024
MAX_PROVENANCE_TOTAL_BYTES = MAX_PROVENANCE_OBJECTS * MAX_PROVENANCE_OBJECT_BYTES
MAX_PROVENANCE_CHUNK_BYTES = 64 * 1024
MAX_PROVENANCE_CHUNKS = 64
MAX_PROVENANCE_TREE_ENTRIES = 256
MAX_PROVENANCE_PATH_COMPONENTS = 8
MAX_PROVENANCE_DAG_VISITS = 64

_FACTORY_TOKEN = object()
_ITERATOR_EOF = object()
_SAFE_TREE_MODES = frozenset({"100644", "100755", "040000", "40000"})
_APACHE_2_SHORT_DECLARATION = b"Apache License\nVersion 2.0, January 2004\n"
_APACHE_2_OFFICIAL_HEADER = (
    b"                                 Apache License\n"
    b"                           Version 2.0, January 2004\n"
    b"                        http://www.apache.org/licenses/\n"
)
_APACHE_2_OFFICIAL_SHA256 = "a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9"

__all__ = (
    "PROVENANCE_PLAN_SCHEMA",
    "PROVENANCE_EVIDENCE_SCHEMA",
    "SOURCE_REPOSITORY",
    "CHECKPOINT_REPOSITORY",
    "SOURCE_COMMIT",
    "CHECKPOINT_COMMIT",
    "MAX_PROVENANCE_OBJECTS",
    "MAX_PROVENANCE_OBJECT_BYTES",
    "MAX_PROVENANCE_TOTAL_BYTES",
    "MAX_PROVENANCE_CHUNK_BYTES",
    "MAX_PROVENANCE_CHUNKS",
    "MAX_PROVENANCE_TREE_ENTRIES",
    "MAX_PROVENANCE_PATH_COMPONENTS",
    "MAX_PROVENANCE_DAG_VISITS",
    "PROVENANCE_OBJECTS",
    "LayaGitObjectSpec",
    "LayaRuntimeProvenancePlan",
    "LayaGitObjectEnvelope",
    "VerifiedLayaProvenanceObject",
    "LayaRuntimeProvenanceEvidence",
    "prepare_laya_runtime_provenance_plan",
    "verify_laya_runtime_provenance_objects",
    "canonical_laya_runtime_provenance_summary_bytes",
)


class _FactorySealed:
    __slots__ = ("_factory_capability", "_semantic_capability")


class _IssuedRecord:
    __slots__ = ("reference", "semantics")

    def __init__(
        self,
        reference: weakref.ReferenceType[object],
        semantics: tuple[object, ...],
    ) -> None:
        self.reference = reference
        self.semantics = semantics


class _IdentitySeal:
    __slots__ = ("value",)

    def __init__(self, value: object) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return type(other) is _IdentitySeal and self.value is other.value

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: private identity seal>"


def _caller_semantic_mirror(value: object) -> object:
    if type(value) is _IdentitySeal:
        return _IdentitySeal(value.value)
    if type(value) is tuple:
        return tuple(_caller_semantic_mirror(item) for item in value)
    if type(value) is list:
        return [_caller_semantic_mirror(item) for item in value]
    if type(value) is dict:
        return {key: _caller_semantic_mirror(item) for key, item in value.items()}
    return value


_ISSUED_PLANS: dict[int, _IssuedRecord] = {}
_ISSUED_ENVELOPES: dict[int, _IssuedRecord] = {}
_ISSUED_RECEIPTS: dict[int, _IssuedRecord] = {}
_ISSUED_EVIDENCE: dict[int, _IssuedRecord] = {}


def _register_issued(
    value: object,
    registry: dict[int, _IssuedRecord],
    semantics: tuple[object, ...],
) -> None:
    # Compatibility mirror only; module-side records remain authoritative.
    object.__setattr__(value, "_semantic_capability", _caller_semantic_mirror(semantics))
    object.__setattr__(value, "_factory_capability", _FACTORY_TOKEN)
    identity = id(value)

    def cleanup(expired: weakref.ReferenceType[object]) -> None:
        record = registry.get(identity)
        if record is not None and record.reference is expired:
            registry.pop(identity, None)

    reference = weakref.ref(value, cleanup)
    registry[identity] = _IssuedRecord(reference, semantics)


def _requires_issued(
    value: object,
    expected_type: type,
    registry: dict[int, _IssuedRecord],
    semantics: tuple[object, ...],
    message: str,
) -> None:
    record = registry.get(id(value))
    if (
        type(value) is not expected_type
        or not _has_factory_capability(value)
        or record is None
        or record.reference() is not value
        or record.semantics != semantics
    ):
        raise ValueError(message)


def _has_factory_capability(value: object) -> bool:
    return getattr(value, "_factory_capability", None) is _FACTORY_TOKEN


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private provenance value>"


def _raise_private(message: str) -> None:
    error = ValueError(message)
    error.__suppress_context__ = True
    raise error


def _valid_sha1(value: object) -> bool:
    return (
        type(value) is str
        and re.fullmatch(r"[0-9a-f]{40}", value) is not None
        and value != "0" * 40
    )


def _valid_sha256(value: object) -> bool:
    return (
        type(value) is str
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        and value != "0" * 64
    )


@dataclass(frozen=True, slots=True, repr=False)
class LayaGitObjectSpec:
    role: str
    repository: str = field(repr=False)
    kind: str
    sha1: str = field(repr=False)
    sha256: str = field(repr=False)
    size_bytes: int
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("provenance object specification is invalid")
        _validate_object_spec_shape(self)

    __repr__ = _private_repr


def _validate_object_spec_shape(value: object) -> LayaGitObjectSpec:
    if (
        type(value) is not LayaGitObjectSpec
        or type(value.role) is not str
        or not value.role
        or value.repository
        != (SOURCE_REPOSITORY if value.role.startswith("source_") else CHECKPOINT_REPOSITORY)
        or value.kind not in {"blob", "commit", "tag", "tree"}
        or not _valid_sha1(value.sha1)
        or not _valid_sha256(value.sha256)
        or type(value.size_bytes) is not int
        or not 0 < value.size_bytes <= MAX_PROVENANCE_OBJECT_BYTES
    ):
        raise ValueError("provenance object specification is invalid")
    return value


_OBJECT_PROFILE = (
    (
        "source_tag",
        "tag",
        "a0d473b307b7eaa7385ae04feea43c52581c4f5a",
        "7f7f43c230ac6e106c3cc3ee713b905964cd66cd8c4c91435f6441be0f8b91ed",
        912,
    ),
    (
        "source_commit",
        "commit",
        SOURCE_COMMIT,
        "f40967375c7dd748a8060268384ef4103830c19798b5954da485234ccc7cef7f",
        975,
    ),
    (
        "source_tree",
        "tree",
        "1f64e459fd2b9f55d7672b0457a2245faa49dce7",
        "da1be47947c251b312b4007946b4460dfca97ec3f5f88c9c2ba75203d976a218",
        1686,
    ),
    (
        "source_license",
        "blob",
        "d9a10c0d8e868ebf8da0b3dc95bb0be634c34bfe",
        "a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9",
        10173,
    ),
    (
        "source_pyproject",
        "blob",
        "4f05fe8dcd6c6e131c8200648e024d1bad7fc920",
        "375130a133e96f0c7481ed38f1cc59a86aea79a5dd984770215fecc8e1bedaa6",
        3956,
    ),
    (
        "checkpoint_commit",
        "commit",
        CHECKPOINT_COMMIT,
        "4e00a98879150b4c17b83ec48688c81e0b14a2b62ebf35b2c831ab67eb95fb75",
        1149,
    ),
    (
        "checkpoint_tree",
        "tree",
        "61ea5230f8c24a7b55f9b37e74518c6ef17e62b3",
        "0c4cc02bf64c39e2594beb5021c49193a857302c18d9f3aa121d67d179ee74d3",
        512,
    ),
    (
        "checkpoint_readme",
        "blob",
        "ac11a565c217959d0cb062748a2f83e05da446a5",
        "00355613796b3f5860b0d5b20392381d26580ec242e04a1fd150c7f116858602",
        23187,
    ),
    (
        "multilingual_tree",
        "tree",
        "de7883e4ef73e15f09af019dd10526bfd3099bcc",
        "23b429e24c9cc58fa0afe42aa15b91f45f02e463cec666dbe50e389d82189ea4",
        163,
    ),
    (
        "encoder_tree",
        "tree",
        "3dab0f21aa014e7aded1f8e8087665d2a501b457",
        "37615bcb694d28a74ad14f87e3969d1158c3c96e19365f59918331e3548517d0",
        39,
    ),
    (
        "tokenizer_tree",
        "tree",
        "fb46ae282300390f9b4441103b7186ec6694d59a",
        "b0956a8fbb7183c7270faf8491235ea8c33c9c104f54ac594c0ea72f500b341b",
        91,
    ),
    (
        "encoder_config",
        "blob",
        "0de0e2d30638873790cf962def52e2acf4db3eef",
        "83f6916d13ef0f556ac461f28308dc2bffa7ebeadee8ec9e2db5812020ea5bb4",
        1938,
    ),
    (
        "weights_lfs",
        "blob",
        "b99c8bea239c53f6f6bce734557dc6c403fa6b3e",
        "728656cf0aacad64dea942a0438242d8d5199db39e5602a77ebee6cd0319c759",
        134,
    ),
    (
        "laya_config",
        "blob",
        "00e35f88bb731bb9126a914666ab1cdac8a204c8",
        "25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6",
        472,
    ),
    (
        "tokenizer_lfs",
        "blob",
        "56d765858ed38eaabd35cd90759cbb1f89b0baa4",
        "9ca6155812f67a58160ce2cded92df5912c97509d38937ddc200f7fc8e142566",
        133,
    ),
    (
        "tokenizer_config",
        "blob",
        "c255ac0c8cb34a37d066cd0dafe313fd769d27ae",
        "6c6b2d8e3c84ce0e671c129cd6b374b235d6f9863042a5836358d00a89bbb5a1",
        524,
    ),
)

PROVENANCE_OBJECTS = tuple(
    LayaGitObjectSpec(
        role=item[0],
        repository=(SOURCE_REPOSITORY if item[0].startswith("source_") else CHECKPOINT_REPOSITORY),
        kind=item[1],
        sha1=item[2],
        sha256=item[3],
        size_bytes=item[4],
        _factory_token=_FACTORY_TOKEN,
    )
    for item in _OBJECT_PROFILE
)


@dataclass(frozen=True, slots=True, repr=False)
class _GitCommit:
    tree_sha1: str
    parent_sha1s: tuple[str, ...]

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class _GitTag:
    object_sha1: str
    object_kind: str
    tag: str

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class _GitTreeEntry:
    mode: str
    path: str = field(repr=False)
    sha1: str = field(repr=False)

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class _LfsPointer:
    sha256: str = field(repr=False)
    size_bytes: int

    __repr__ = _private_repr


def _parse_commit(payload: object) -> _GitCommit:
    if type(payload) is not bytes or not payload or len(payload) > MAX_PROVENANCE_OBJECT_BYTES:
        raise ValueError("invalid commit payload")
    text = payload.decode("utf-8", errors="strict")
    if "\x00" in text or "\r" in text or not text.endswith("\n") or "\n\n" not in text:
        raise ValueError("invalid commit encoding")
    header, message = text.split("\n\n", 1)
    if not message or not message.endswith("\n"):
        raise ValueError("invalid commit message")
    lines = header.split("\n")
    if not lines or not lines[0].startswith("tree "):
        raise ValueError("invalid commit tree")
    tree = lines[0][5:]
    if not _valid_sha1(tree):
        raise ValueError("invalid commit tree")
    parents: list[str] = []
    seen_author = False
    seen_committer = False
    continuation_allowed = False
    for line in lines[1:]:
        if line.startswith("parent ") and not seen_author:
            parent = line[7:]
            if not _valid_sha1(parent):
                raise ValueError("invalid commit parent")
            parents.append(parent)
            continuation_allowed = False
        elif line.startswith("author ") and not seen_author and not seen_committer:
            if len(line) == 7:
                raise ValueError("invalid commit author")
            seen_author = True
            continuation_allowed = False
        elif line.startswith("committer ") and seen_author and not seen_committer:
            if len(line) == 10:
                raise ValueError("invalid commit committer")
            seen_committer = True
            continuation_allowed = False
        elif line.startswith(("gpgsig ", "encoding ", "mergetag ")) and seen_committer:
            continuation_allowed = True
        elif line.startswith(" ") and continuation_allowed:
            continue
        else:
            raise ValueError("invalid commit header")
    if not seen_author or not seen_committer:
        raise ValueError("incomplete commit headers")
    return _GitCommit(tree_sha1=tree, parent_sha1s=tuple(parents))


def _parse_git_commit_bytes(payload: object) -> _GitCommit:
    failed = False
    result = None
    try:
        result = _parse_commit(payload)
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("Git commit validation failed")
    return result


def _parse_tag(payload: object) -> _GitTag:
    if type(payload) is not bytes or not payload or len(payload) > MAX_PROVENANCE_OBJECT_BYTES:
        raise ValueError("invalid tag payload")
    text = payload.decode("utf-8", errors="strict")
    if "\x00" in text or "\r" in text or not text.endswith("\n") or "\n\n" not in text:
        raise ValueError("invalid tag encoding")
    header, message = text.split("\n\n", 1)
    if not message or not message.endswith("\n"):
        raise ValueError("invalid tag message")
    lines = header.split("\n")
    if len(lines) != 4:
        raise ValueError("invalid annotated tag headers")
    expected_prefixes = ("object ", "type ", "tag ", "tagger ")
    if any(not line.startswith(prefix) for line, prefix in zip(lines, expected_prefixes)):
        raise ValueError("invalid annotated tag headers")
    target = lines[0][7:]
    kind = lines[1][5:]
    tag = lines[2][4:]
    if target != SOURCE_COMMIT or kind != "commit" or tag != "v0.4.2" or len(lines[3]) == 7:
        raise ValueError("annotated tag binding is invalid")
    return _GitTag(object_sha1=target, object_kind=kind, tag=tag)


def _parse_git_tag_bytes(payload: object) -> _GitTag:
    failed = False
    result = None
    try:
        result = _parse_tag(payload)
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("Git tag validation failed")
    return result


def _tree_sort_key(entry: _GitTreeEntry) -> bytes:
    suffix = b"/" if entry.mode in {"040000", "40000"} else b""
    return entry.path.encode("utf-8") + suffix


def _parse_tree(payload: object) -> tuple[_GitTreeEntry, ...]:
    if type(payload) is not bytes or len(payload) > MAX_PROVENANCE_OBJECT_BYTES:
        raise ValueError("invalid tree payload")
    entries: list[_GitTreeEntry] = []
    offset = 0
    while offset < len(payload):
        if len(entries) >= MAX_PROVENANCE_TREE_ENTRIES:
            raise ValueError("tree entry limit exceeded")
        separator = payload.find(b" ", offset)
        terminator = payload.find(b"\0", separator + 1) if separator >= 0 else -1
        if separator <= offset or terminator <= separator + 1 or terminator + 21 > len(payload):
            raise ValueError("invalid tree entry framing")
        mode = payload[offset:separator].decode("ascii", errors="strict")
        path_bytes = payload[separator + 1 : terminator]
        path = path_bytes.decode("utf-8", errors="strict")
        object_id = payload[terminator + 1 : terminator + 21].hex()
        if (
            mode not in _SAFE_TREE_MODES
            or not path
            or path in {".", ".."}
            or any(character in path for character in ("/", "\\", ":", "\x00"))
            or len(path_bytes) > 255
            or not _valid_sha1(object_id)
        ):
            raise ValueError("unsafe tree entry")
        entries.append(_GitTreeEntry(mode=mode, path=path, sha1=object_id))
        offset = terminator + 21
    if not entries:
        raise ValueError("empty tree is not part of the profile")
    keys = tuple(_tree_sort_key(entry) for entry in entries)
    if keys != tuple(sorted(keys)) or len({entry.path for entry in entries}) != len(entries):
        raise ValueError("tree order or uniqueness is invalid")
    return tuple(entries)


def _parse_git_tree_bytes(payload: object) -> tuple[_GitTreeEntry, ...]:
    failed = False
    result = None
    try:
        result = _parse_tree(payload)
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("Git tree validation failed")
    return result


def _parse_lfs(payload: object) -> _LfsPointer:
    if type(payload) is not bytes or len(payload) > MAX_PROVENANCE_OBJECT_BYTES:
        raise ValueError("invalid LFS pointer")
    match = re.fullmatch(
        rb"version https://git-lfs.github.com/spec/v1\n"
        rb"oid sha256:([0-9a-f]{64})\n"
        rb"size ([1-9][0-9]*)\n",
        payload,
    )
    if match is None:
        raise ValueError("invalid LFS pointer")
    digest = match.group(1).decode("ascii")
    size = int(match.group(2))
    if not _valid_sha256(digest) or size > runtime_checkpoint.MAX_CHECKPOINT_FILE_BYTES:
        raise ValueError("invalid LFS authority")
    return _LfsPointer(sha256=digest, size_bytes=size)


def _parse_lfs_pointer_bytes(payload: object) -> _LfsPointer:
    failed = False
    result = None
    try:
        result = _parse_lfs(payload)
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("Git LFS pointer validation failed")
    return result


def _source_license(payload: object) -> None:
    if type(payload) is not bytes or len(payload) > MAX_PROVENANCE_OBJECT_BYTES:
        raise ValueError("invalid source declaration")
    payload.decode("utf-8", errors="strict")
    non_crlf = payload.replace(b"\r\n", b"")
    if b"\r" in non_crlf or (b"\r\n" in payload and b"\n" in non_crlf):
        raise ValueError("invalid source declaration")
    normalized = payload.replace(b"\r\n", b"\n")
    is_short_declaration = normalized == _APACHE_2_SHORT_DECLARATION
    is_official_license = normalized.startswith(_APACHE_2_OFFICIAL_HEADER) and (
        hashlib.sha256(normalized).hexdigest() == _APACHE_2_OFFICIAL_SHA256
    )
    if not (is_short_declaration or is_official_license):
        raise ValueError("source declaration is absent")


def _validate_source_license_bytes(payload: object) -> None:
    failed = False
    try:
        _source_license(payload)
    except Exception:
        failed = True
    if failed:
        _raise_private("source license declaration validation failed")


def _source_pyproject(payload: object) -> None:
    if type(payload) is not bytes or len(payload) > MAX_PROVENANCE_OBJECT_BYTES:
        raise ValueError("invalid project declaration")
    parsed = tomllib.loads(payload.decode("utf-8", errors="strict"))
    project = parsed.get("project")
    if type(project) is not dict:
        raise ValueError("project declaration is absent")
    license_value = project.get("license")
    license_matches = license_value == "Apache-2.0" or (
        type(license_value) is dict and license_value.get("text") == "Apache-2.0"
    )
    if project.get("name") != "laya" or project.get("version") != "0.4.2" or not license_matches:
        raise ValueError("project declaration is invalid")


def _validate_source_pyproject_bytes(payload: object) -> None:
    failed = False
    try:
        _source_pyproject(payload)
    except Exception:
        failed = True
    if failed:
        _raise_private("source package declaration validation failed")


def _checkpoint_readme(payload: object) -> None:
    if type(payload) is not bytes or len(payload) > MAX_PROVENANCE_OBJECT_BYTES:
        raise ValueError("invalid checkpoint declaration")
    expected = (
        b"---\nlicense: apache-2.0\nlibrary_name: transformers\n"
        b"pipeline_tag: text-classification\n"
        b"tags: [laya, system-one, calibrated-decisions, rlcd, classification, routing, "
        b"scoring, guardrails, moderation, reinforcement-learning, commercial-use]\n---\n"
    )
    if not payload.startswith(expected):
        raise ValueError("checkpoint declaration is absent")


def _validate_checkpoint_readme_bytes(payload: object) -> None:
    failed = False
    try:
        _checkpoint_readme(payload)
    except Exception:
        failed = True
    if failed:
        _raise_private("checkpoint declaration validation failed")


def _deep_validate_checkpoint_evidence(value: object) -> object:
    if type(value) is not runtime_checkpoint.LayaRuntimeCheckpointEvidence:
        raise TypeError("checkpoint evidence must be exact")
    plan = value.plan
    deployment = value.deployment_evidence
    if (
        type(plan) is not runtime_checkpoint.LayaRuntimeCheckpointPlan
        or type(deployment) is not runtime_deployment_metadata.LayaRuntimeDeploymentEvidence
        or value.deployment_evidence is not plan.deployment_evidence
        or value.runtime_identity is not plan.runtime_identity
        or type(value.receipts) is not tuple
        or type(plan.files) is not tuple
    ):
        raise ValueError("checkpoint evidence graph is invalid")
    snapshot = deployment.snapshot
    if (
        type(snapshot) is not runtime_bundle.LayaRuntimeBundleSnapshot
        or type(snapshot.artifacts) is not tuple
        or any(
            type(item) is not runtime_bundle.CapturedRuntimeArtifact for item in snapshot.artifacts
        )
    ):
        raise ValueError("checkpoint deployment snapshot is invalid")
    payload_by_path = {item.spec.path: item.content for item in snapshot.artifacts}
    if len(payload_by_path) != len(snapshot.artifacts):
        raise ValueError("checkpoint deployment artifacts are invalid")
    rebuilt_snapshot = runtime_bundle.verify_laya_runtime_artifact_bytes(
        snapshot.manifest, payload_by_path
    )
    rebuilt_deployment = runtime_deployment_metadata.validate_laya_runtime_deployment_metadata(
        rebuilt_snapshot
    )
    rebuilt_plan = runtime_checkpoint.prepare_laya_runtime_checkpoint_plan(rebuilt_deployment)
    if (
        snapshot != rebuilt_snapshot
        or deployment != rebuilt_deployment
        or plan != rebuilt_plan
        or value.runtime_identity is not deployment.runtime_identity
        or len(value.receipts) != len(plan.files)
    ):
        raise ValueError("checkpoint evidence reconstruction differs")
    for position, receipt in enumerate(value.receipts):
        if (
            type(receipt) is not runtime_checkpoint.VerifiedLayaCheckpointFile
            or receipt.plan is not plan
            or receipt.file is not plan.files[position]
            or receipt.checkpoint_file_bytes_verified is not True
        ):
            raise ValueError("checkpoint receipt graph is invalid")
    runtime_checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(value)
    if (
        deployment.checkpoint_manifest.repository != "convaiinnovations/laya"
        or deployment.checkpoint_manifest.revision != CHECKPOINT_COMMIT
        or deployment.checkpoint_manifest.subfolder != "multilingual"
    ):
        raise ValueError("checkpoint repository binding is invalid")
    return value


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeProvenancePlan(_FactorySealed):
    schema_version: str
    checkpoint_evidence: runtime_checkpoint.LayaRuntimeCheckpointEvidence = field(repr=False)
    runtime_identity: object = field(repr=False)
    objects: tuple[LayaGitObjectSpec, ...] = field(repr=False)
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("provenance plan binding is invalid")
        _validate_plan_shape(self)

    __repr__ = _private_repr


def _validate_plan_shape(value: object) -> LayaRuntimeProvenancePlan:
    if (
        type(value) is not LayaRuntimeProvenancePlan
        or value.schema_version != PROVENANCE_PLAN_SCHEMA
        or type(value.checkpoint_evidence) is not runtime_checkpoint.LayaRuntimeCheckpointEvidence
        or value.runtime_identity is not value.checkpoint_evidence.runtime_identity
        or type(value.objects) is not tuple
        or value.objects != PROVENANCE_OBJECTS
        or len(value.objects) != MAX_PROVENANCE_OBJECTS
        or sum(item.size_bytes for item in value.objects) > MAX_PROVENANCE_TOTAL_BYTES
    ):
        raise ValueError("provenance plan binding is invalid")
    for item in value.objects:
        _validate_object_spec_shape(item)
    return value


def _plan_semantics(plan: LayaRuntimeProvenancePlan) -> tuple[object, ...]:
    return (
        plan.schema_version,
        _IdentitySeal(plan.checkpoint_evidence),
        _IdentitySeal(plan.runtime_identity),
        tuple(_IdentitySeal(item) for item in plan.objects),
        tuple(
            (item.role, item.repository, item.kind, item.sha1, item.sha256, item.size_bytes)
            for item in plan.objects
        ),
    )


def _require_verified_plan(value: object) -> LayaRuntimeProvenancePlan:
    if type(value) is not LayaRuntimeProvenancePlan:
        raise ValueError("provenance plan lacks issued checkpoint authority")
    _requires_issued(
        value,
        LayaRuntimeProvenancePlan,
        _ISSUED_PLANS,
        _plan_semantics(value),
        "provenance plan lacks issued checkpoint authority",
    )
    _validate_plan_shape(value)
    _deep_validate_checkpoint_evidence(value.checkpoint_evidence)
    return value


def prepare_laya_runtime_provenance_plan(
    checkpoint_evidence: runtime_checkpoint.LayaRuntimeCheckpointEvidence,
) -> LayaRuntimeProvenancePlan:
    """Bind the closed provenance profile to exact PR34 checkpoint evidence."""

    failed = False
    result = None
    try:
        validated = _deep_validate_checkpoint_evidence(checkpoint_evidence)
        result = LayaRuntimeProvenancePlan(
            schema_version=PROVENANCE_PLAN_SCHEMA,
            checkpoint_evidence=validated,
            runtime_identity=validated.runtime_identity,
            objects=PROVENANCE_OBJECTS,
            _factory_token=_FACTORY_TOKEN,
        )
        _register_issued(result, _ISSUED_PLANS, _plan_semantics(result))
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("provenance plan validation failed")
    return result


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaGitObjectEnvelope(_FactorySealed):
    spec: LayaGitObjectSpec = field(repr=False)
    tree_sha1: str | None = field(repr=False)
    parent_sha1s: tuple[str, ...]
    target_sha1: str | None = field(repr=False)
    target_kind: str | None
    tag_name: str | None
    tree_entries: tuple[_GitTreeEntry, ...] = field(repr=False)
    lfs_sha256: str | None = field(repr=False)
    lfs_size_bytes: int | None
    source_license_declared: bool
    checkpoint_license_declared: bool
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if (
            _factory_token is not _FACTORY_TOKEN
            or type(self.spec) is not LayaGitObjectSpec
            or type(self.parent_sha1s) is not tuple
            or type(self.tree_entries) is not tuple
            or type(self.source_license_declared) is not bool
            or type(self.checkpoint_license_declared) is not bool
        ):
            raise ValueError("provenance envelope is invalid")
        _validate_object_spec_shape(self.spec)
        _validate_envelope_role_matrix(self)
        _register_issued(self, _ISSUED_ENVELOPES, _envelope_semantics(self))

    __repr__ = _private_repr


def _envelope_semantics(envelope: LayaGitObjectEnvelope) -> tuple[object, ...]:
    return (
        _IdentitySeal(envelope.spec),
        envelope.tree_sha1,
        envelope.parent_sha1s,
        envelope.target_sha1,
        envelope.target_kind,
        envelope.tag_name,
        tuple((entry.mode, entry.path, entry.sha1) for entry in envelope.tree_entries),
        envelope.lfs_sha256,
        envelope.lfs_size_bytes,
        envelope.source_license_declared,
        envelope.checkpoint_license_declared,
    )


def _validate_envelope_role_matrix(envelope: LayaGitObjectEnvelope) -> None:
    role = envelope.spec.role
    empty_common = (
        envelope.tree_sha1 is None
        and envelope.parent_sha1s == ()
        and envelope.target_sha1 is None
        and envelope.target_kind is None
        and envelope.tag_name is None
        and envelope.tree_entries == ()
        and envelope.lfs_sha256 is None
        and envelope.lfs_size_bytes is None
    )
    declarations = (
        envelope.source_license_declared,
        envelope.checkpoint_license_declared,
    )
    if role == "source_tag":
        valid = (
            envelope.tree_sha1 is None
            and envelope.parent_sha1s == ()
            and envelope.target_sha1 == SOURCE_COMMIT
            and envelope.target_kind == "commit"
            and envelope.tag_name == "v0.4.2"
            and envelope.tree_entries == ()
            and envelope.lfs_sha256 is None
            and envelope.lfs_size_bytes is None
            and declarations == (False, False)
        )
    elif role in {"source_commit", "checkpoint_commit"}:
        valid = (
            _valid_sha1(envelope.tree_sha1)
            and type(envelope.parent_sha1s) is tuple
            and all(_valid_sha1(parent) for parent in envelope.parent_sha1s)
            and envelope.target_sha1 is None
            and envelope.target_kind is None
            and envelope.tag_name is None
            and envelope.tree_entries == ()
            and envelope.lfs_sha256 is None
            and envelope.lfs_size_bytes is None
            and declarations == (False, False)
        )
    elif role.endswith("_tree"):
        valid = (
            envelope.tree_sha1 is None
            and envelope.parent_sha1s == ()
            and envelope.target_sha1 is None
            and envelope.target_kind is None
            and envelope.tag_name is None
            and type(envelope.tree_entries) is tuple
            and bool(envelope.tree_entries)
            and all(type(entry) is _GitTreeEntry for entry in envelope.tree_entries)
            and envelope.lfs_sha256 is None
            and envelope.lfs_size_bytes is None
            and declarations == (False, False)
        )
    elif role in {"weights_lfs", "tokenizer_lfs"}:
        valid = (
            envelope.tree_sha1 is None
            and envelope.parent_sha1s == ()
            and envelope.target_sha1 is None
            and envelope.target_kind is None
            and envelope.tag_name is None
            and envelope.tree_entries == ()
            and _valid_sha256(envelope.lfs_sha256)
            and type(envelope.lfs_size_bytes) is int
            and envelope.lfs_size_bytes > 0
            and declarations == (False, False)
        )
    elif role in {"source_license", "source_pyproject"}:
        valid = empty_common and declarations == (True, False)
    elif role == "checkpoint_readme":
        valid = empty_common and declarations == (False, True)
    else:
        valid = empty_common and declarations == (False, False)
    if not valid:
        raise ValueError("provenance envelope role semantics are invalid")


def _require_verified_envelope(value: object) -> LayaGitObjectEnvelope:
    if type(value) is not LayaGitObjectEnvelope:
        raise ValueError("provenance envelope lacks verifier authority")
    _requires_issued(
        value,
        LayaGitObjectEnvelope,
        _ISSUED_ENVELOPES,
        _envelope_semantics(value),
        "provenance envelope lacks verifier authority",
    )
    _validate_envelope_role_matrix(value)
    return value


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class VerifiedLayaProvenanceObject(_FactorySealed):
    plan: LayaRuntimeProvenancePlan = field(repr=False)
    spec: LayaGitObjectSpec = field(repr=False)
    envelope: LayaGitObjectEnvelope = field(repr=False)
    _factory_token: InitVar[object]
    provenance_object_verified: bool = field(default=True, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if (
            _factory_token is not _FACTORY_TOKEN
            or type(self.plan) is not LayaRuntimeProvenancePlan
            or type(self.spec) is not LayaGitObjectSpec
            or type(self.envelope) is not LayaGitObjectEnvelope
            or self.envelope.spec is not self.spec
            or not any(self.spec is item for item in self.plan.objects)
            or self.provenance_object_verified is not True
        ):
            raise ValueError("provenance receipt is invalid")
        _require_verified_plan(self.plan)
        _validate_object_spec_shape(self.spec)
        _require_verified_envelope(self.envelope)
        _register_issued(
            self,
            _ISSUED_RECEIPTS,
            (
                _IdentitySeal(self.plan),
                _IdentitySeal(self.spec),
                _IdentitySeal(self.envelope),
                True,
            ),
        )

    __repr__ = _private_repr


def _require_verified_receipt(value: object) -> VerifiedLayaProvenanceObject:
    if type(value) is not VerifiedLayaProvenanceObject:
        raise ValueError("provenance receipt lacks verifier authority")
    _require_verified_envelope(value.envelope)
    expected = (
        _IdentitySeal(value.plan),
        _IdentitySeal(value.spec),
        _IdentitySeal(value.envelope),
        True,
    )
    _requires_issued(
        value,
        VerifiedLayaProvenanceObject,
        _ISSUED_RECEIPTS,
        expected,
        "provenance receipt lacks verifier authority",
    )
    if value.envelope.spec is not value.spec or value.provenance_object_verified is not True:
        raise ValueError("provenance receipt semantics changed")
    return value


def _envelope_for(spec: LayaGitObjectSpec, payload: bytes) -> LayaGitObjectEnvelope:
    tree_sha1 = None
    parents: tuple[str, ...] = ()
    target_sha1 = None
    target_kind = None
    tag_name = None
    entries: tuple[_GitTreeEntry, ...] = ()
    lfs_sha256 = None
    lfs_size = None
    source_license = False
    checkpoint_license = False
    if spec.kind == "commit":
        parsed_commit = _parse_commit(payload)
        tree_sha1 = parsed_commit.tree_sha1
        parents = parsed_commit.parent_sha1s
    elif spec.kind == "tag":
        parsed_tag = _parse_tag(payload)
        target_sha1 = parsed_tag.object_sha1
        target_kind = parsed_tag.object_kind
        tag_name = parsed_tag.tag
    elif spec.kind == "tree":
        entries = _parse_tree(payload)
    elif spec.role in {"weights_lfs", "tokenizer_lfs"}:
        pointer = _parse_lfs(payload)
        lfs_sha256 = pointer.sha256
        lfs_size = pointer.size_bytes
    elif spec.role == "source_license":
        _source_license(payload)
        source_license = True
    elif spec.role == "source_pyproject":
        _source_pyproject(payload)
        source_license = True
    elif spec.role == "checkpoint_readme":
        _checkpoint_readme(payload)
        checkpoint_license = True
    return LayaGitObjectEnvelope(
        spec=spec,
        tree_sha1=tree_sha1,
        parent_sha1s=parents,
        target_sha1=target_sha1,
        target_kind=target_kind,
        tag_name=tag_name,
        tree_entries=entries,
        lfs_sha256=lfs_sha256,
        lfs_size_bytes=lfs_size,
        source_license_declared=source_license,
        checkpoint_license_declared=checkpoint_license,
        _factory_token=_FACTORY_TOKEN,
    )


def _verify_object_chunks(
    plan: object, digest: object, chunks: object
) -> VerifiedLayaProvenanceObject:
    plan = _require_verified_plan(plan)
    if not 0 < MAX_PROVENANCE_CHUNK_BYTES <= MAX_PROVENANCE_OBJECT_BYTES:
        raise ValueError("provenance live chunk cap is invalid")
    if not _valid_sha1(digest):
        raise ValueError("provenance object identity is invalid")
    matches = [item for item in plan.objects if item.sha1 == digest]
    if len(matches) != 1:
        raise ValueError("provenance object is not authorized")
    spec = matches[0]
    iterator = iter(chunks)
    git_hasher = hashlib.sha1(usedforsecurity=False)
    git_hasher.update(f"{spec.kind} {spec.size_bytes}\0".encode("ascii"))
    content_hasher = hashlib.sha256()
    payload = bytearray()
    chunk_count = 0
    while True:
        chunk = next(iterator, _ITERATOR_EOF)
        if chunk is _ITERATOR_EOF:
            break
        chunk_count += 1
        if (
            type(chunk) is not bytes
            or not chunk
            or len(chunk) > MAX_PROVENANCE_CHUNK_BYTES
            or chunk_count > MAX_PROVENANCE_CHUNKS
            or len(payload) + len(chunk) > spec.size_bytes
        ):
            raise ValueError("provenance object stream is invalid")
        git_hasher.update(chunk)
        content_hasher.update(chunk)
        payload.extend(chunk)
    if (
        len(payload) != spec.size_bytes
        or git_hasher.hexdigest() != spec.sha1
        or content_hasher.hexdigest() != spec.sha256
    ):
        raise ValueError("provenance object authority differs")
    envelope = _envelope_for(spec, bytes(payload))
    _deep_validate_checkpoint_evidence(plan.checkpoint_evidence)
    return VerifiedLayaProvenanceObject(
        plan=plan,
        spec=spec,
        envelope=envelope,
        _factory_token=_FACTORY_TOKEN,
    )


def _verify_laya_runtime_provenance_object_chunks(
    plan: LayaRuntimeProvenancePlan,
    sha1: str,
    chunks: object,
) -> VerifiedLayaProvenanceObject:
    """Verify one authorized Git object for internal bounded composition."""

    failed = False
    result = None
    try:
        result = _verify_object_chunks(plan, sha1, chunks)
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("provenance object verification failed")
    return result


def _tree_map(envelope: LayaGitObjectEnvelope) -> dict[str, _GitTreeEntry]:
    return {entry.path: entry for entry in envelope.tree_entries}


def _validate_graph(
    plan: LayaRuntimeProvenancePlan,
    receipts: object,
) -> tuple[VerifiedLayaProvenanceObject, ...]:
    if type(receipts) is not tuple or len(receipts) != len(plan.objects):
        raise ValueError("provenance receipt coverage is invalid")
    if len(receipts) > MAX_PROVENANCE_DAG_VISITS:
        raise ValueError("provenance DAG visit limit exceeded")
    by_role: dict[str, VerifiedLayaProvenanceObject] = {}
    for position, receipt in enumerate(receipts):
        _require_verified_receipt(receipt)
        if (
            receipt.plan is not plan
            or receipt.spec is not plan.objects[position]
            or receipt.provenance_object_verified is not True
        ):
            raise ValueError("provenance receipt binding is invalid")
        by_role[receipt.spec.role] = receipt
    if len(by_role) != MAX_PROVENANCE_OBJECTS:
        raise ValueError("provenance role coverage is invalid")
    envelope = {role: receipt.envelope for role, receipt in by_role.items()}
    if (
        envelope["source_tag"].target_sha1 != SOURCE_COMMIT
        or envelope["source_commit"].tree_sha1 != by_role["source_tree"].spec.sha1
        or envelope["checkpoint_commit"].tree_sha1 != by_role["checkpoint_tree"].spec.sha1
    ):
        raise ValueError("provenance commit graph is invalid")
    source_tree = _tree_map(envelope["source_tree"])
    checkpoint_tree = _tree_map(envelope["checkpoint_tree"])
    multilingual_tree = _tree_map(envelope["multilingual_tree"])
    encoder_tree = _tree_map(envelope["encoder_tree"])
    tokenizer_tree = _tree_map(envelope["tokenizer_tree"])
    expected_links = (
        (source_tree, "LICENSE", "source_license", frozenset({"100644"}), 1),
        (source_tree, "pyproject.toml", "source_pyproject", frozenset({"100644"}), 1),
        (checkpoint_tree, "README.md", "checkpoint_readme", frozenset({"100644"}), 1),
        (
            checkpoint_tree,
            "multilingual",
            "multilingual_tree",
            frozenset({"040000", "40000"}),
            1,
        ),
        (
            multilingual_tree,
            "encoder",
            "encoder_tree",
            frozenset({"040000", "40000"}),
            2,
        ),
        (
            multilingual_tree,
            "model.safetensors",
            "weights_lfs",
            frozenset({"100644"}),
            2,
        ),
        (
            multilingual_tree,
            "rl_agent_config.json",
            "laya_config",
            frozenset({"100644"}),
            2,
        ),
        (
            multilingual_tree,
            "tokenizer",
            "tokenizer_tree",
            frozenset({"040000", "40000"}),
            2,
        ),
        (encoder_tree, "config.json", "encoder_config", frozenset({"100644"}), 3),
        (tokenizer_tree, "tokenizer.json", "tokenizer_lfs", frozenset({"100644"}), 3),
        (
            tokenizer_tree,
            "tokenizer_config.json",
            "tokenizer_config",
            frozenset({"100644"}),
            3,
        ),
    )
    for tree, path, role, modes, components in expected_links:
        entry = tree.get(path)
        if (
            entry is None
            or entry.sha1 != by_role[role].spec.sha1
            or entry.mode not in modes
            or components > MAX_PROVENANCE_PATH_COMPONENTS
        ):
            raise ValueError("provenance tree graph is invalid")
    checkpoint_files = {item.role: item for item in plan.checkpoint_evidence.plan.files}
    direct = {
        "encoder_config": "encoder_config",
        "laya_config": "laya_config",
        "tokenizer_config": "tokenizer_config",
    }
    if any(
        by_role[object_role].spec.sha256 != checkpoint_files[file_role].sha256
        or by_role[object_role].spec.size_bytes != checkpoint_files[file_role].size_bytes
        for object_role, file_role in direct.items()
    ):
        raise ValueError("checkpoint small blob binding is invalid")
    pointers = {"weights_lfs": "weights", "tokenizer_lfs": "tokenizer"}
    if any(
        envelope[object_role].lfs_sha256 != checkpoint_files[file_role].sha256
        or envelope[object_role].lfs_size_bytes != checkpoint_files[file_role].size_bytes
        for object_role, file_role in pointers.items()
    ):
        raise ValueError("checkpoint LFS link is invalid")
    if (
        not envelope["source_license"].source_license_declared
        or not envelope["source_pyproject"].source_license_declared
        or not envelope["checkpoint_readme"].checkpoint_license_declared
    ):
        raise ValueError("provenance declaration is invalid")
    return receipts


def verify_laya_runtime_provenance_objects(
    plan: LayaRuntimeProvenancePlan,
    object_packets: object,
) -> LayaRuntimeProvenanceEvidence:
    """Verify the exact ordered sixteen-object profile and seal aggregate evidence."""

    failed = False
    result = None
    try:
        plan = _require_verified_plan(plan)
        if (
            type(object_packets) is not tuple
            or len(object_packets) != len(plan.objects)
            or len(object_packets) > MAX_PROVENANCE_OBJECTS
            or not 0 < MAX_PROVENANCE_CHUNK_BYTES <= MAX_PROVENANCE_OBJECT_BYTES
        ):
            raise ValueError("provenance packet coverage is invalid")
        for position, packet in enumerate(object_packets):
            spec = plan.objects[position]
            if (
                type(packet) is not tuple
                or len(packet) != 4
                or packet[0] != spec.repository
                or packet[1] != spec.kind
                or packet[2] != spec.sha1
                or type(packet[3]) is not tuple
                or not 0 < len(packet[3]) <= MAX_PROVENANCE_CHUNKS
                or any(
                    type(chunk) is not bytes or not chunk or len(chunk) > MAX_PROVENANCE_CHUNK_BYTES
                    for chunk in packet[3]
                )
                or sum(len(chunk) for chunk in packet[3]) != spec.size_bytes
            ):
                raise ValueError("provenance packet authority is invalid")
        receipts = tuple(
            _verify_object_chunks(plan, plan.objects[position].sha1, packet[3])
            for position, packet in enumerate(object_packets)
        )
        validated = _validate_graph(plan, receipts)
        _deep_validate_checkpoint_evidence(plan.checkpoint_evidence)
        result = LayaRuntimeProvenanceEvidence(
            schema_version=PROVENANCE_EVIDENCE_SCHEMA,
            plan=plan,
            checkpoint_evidence=plan.checkpoint_evidence,
            runtime_identity=plan.runtime_identity,
            receipts=validated,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("provenance aggregate validation failed")
    return result


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeProvenanceEvidence(_FactorySealed):
    schema_version: str
    plan: LayaRuntimeProvenancePlan = field(repr=False)
    checkpoint_evidence: runtime_checkpoint.LayaRuntimeCheckpointEvidence = field(repr=False)
    runtime_identity: object = field(repr=False)
    receipts: tuple[VerifiedLayaProvenanceObject, ...] = field(repr=False)
    _factory_token: InitVar[object]
    artifact_integrity_verified: bool = field(default=True, init=False)
    runtime_config_semantics_verified: bool = field(default=True, init=False)
    checkpoint_manifest_semantics_verified: bool = field(default=True, init=False)
    checkpoint_bytes_verified: bool = field(default=True, init=False)
    provenance_objects_verified: bool = field(default=True, init=False)
    source_git_content_verified: bool = field(default=True, init=False)
    checkpoint_git_content_verified: bool = field(default=True, init=False)
    source_license_declaration_observed: bool = field(default=True, init=False)
    checkpoint_license_declaration_observed: bool = field(default=True, init=False)
    lock_verified: bool = field(default=False, init=False)
    sbom_verified: bool = field(default=False, init=False)
    lock_sbom_consistent: bool = field(default=False, init=False)
    oci_bytes_verified: bool = field(default=False, init=False)
    oci_manifest_semantics_verified: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)
    license_verified: bool = field(default=False, init=False)
    base_ancestry_verified: bool = field(default=False, init=False)
    runtime_materialized: bool = field(default=False, init=False)
    executor_available: bool = field(default=False, init=False)
    inference_executed: bool = field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if (
            _factory_token is not _FACTORY_TOKEN
            or self.schema_version != PROVENANCE_EVIDENCE_SCHEMA
            or type(self.plan) is not LayaRuntimeProvenancePlan
            or self.checkpoint_evidence is not self.plan.checkpoint_evidence
            or self.runtime_identity is not self.plan.runtime_identity
        ):
            raise ValueError("provenance evidence binding is invalid")
        inherited_true = (
            "artifact_integrity_verified",
            "runtime_config_semantics_verified",
            "checkpoint_manifest_semantics_verified",
            "checkpoint_bytes_verified",
            "provenance_objects_verified",
            "source_git_content_verified",
            "checkpoint_git_content_verified",
            "source_license_declaration_observed",
            "checkpoint_license_declaration_observed",
        )
        conservative_false = (
            "lock_verified",
            "sbom_verified",
            "lock_sbom_consistent",
            "oci_bytes_verified",
            "oci_manifest_semantics_verified",
            "origin_verified",
            "license_verified",
            "base_ancestry_verified",
            "runtime_materialized",
            "executor_available",
            "inference_executed",
        )
        if any(getattr(self, name) is not True for name in inherited_true) or any(
            getattr(self, name) is not False for name in conservative_false
        ):
            raise ValueError("provenance evidence claims are invalid")
        _require_verified_plan(self.plan)
        _validate_graph(self.plan, self.receipts)
        _register_issued(
            self,
            _ISSUED_EVIDENCE,
            (
                _IdentitySeal(self.plan),
                _IdentitySeal(self.checkpoint_evidence),
                _IdentitySeal(self.runtime_identity),
                tuple(_IdentitySeal(receipt) for receipt in self.receipts),
                tuple(getattr(self, name) for name in inherited_true + conservative_false),
            ),
        )

    __repr__ = _private_repr


def _require_verified_evidence(value: object) -> LayaRuntimeProvenanceEvidence:
    if type(value) is not LayaRuntimeProvenanceEvidence:
        raise ValueError("provenance evidence lacks verifier authority")
    inherited_true = (
        "artifact_integrity_verified",
        "runtime_config_semantics_verified",
        "checkpoint_manifest_semantics_verified",
        "checkpoint_bytes_verified",
        "provenance_objects_verified",
        "source_git_content_verified",
        "checkpoint_git_content_verified",
        "source_license_declaration_observed",
        "checkpoint_license_declaration_observed",
    )
    conservative_false = (
        "lock_verified",
        "sbom_verified",
        "lock_sbom_consistent",
        "oci_bytes_verified",
        "oci_manifest_semantics_verified",
        "origin_verified",
        "license_verified",
        "base_ancestry_verified",
        "runtime_materialized",
        "executor_available",
        "inference_executed",
    )
    expected = (
        _IdentitySeal(value.plan),
        _IdentitySeal(value.checkpoint_evidence),
        _IdentitySeal(value.runtime_identity),
        tuple(_IdentitySeal(receipt) for receipt in value.receipts),
        tuple(getattr(value, name) for name in inherited_true + conservative_false),
    )
    _requires_issued(
        value,
        LayaRuntimeProvenanceEvidence,
        _ISSUED_EVIDENCE,
        expected,
        "provenance evidence lacks verifier authority",
    )
    if (
        value.schema_version != PROVENANCE_EVIDENCE_SCHEMA
        or value.checkpoint_evidence is not value.plan.checkpoint_evidence
        or value.runtime_identity is not value.plan.runtime_identity
        or any(getattr(value, name) is not True for name in inherited_true)
        or any(getattr(value, name) is not False for name in conservative_false)
    ):
        raise ValueError("provenance evidence semantics changed")
    _require_verified_plan(value.plan)
    _validate_graph(value.plan, value.receipts)
    return value


def _seal_laya_runtime_provenance_evidence(
    plan: LayaRuntimeProvenancePlan,
    receipts: tuple[VerifiedLayaProvenanceObject, ...],
) -> LayaRuntimeProvenanceEvidence:
    failed = False
    result = None
    try:
        plan = _require_verified_plan(plan)
        validated_receipts = _validate_graph(plan, receipts)
        result = LayaRuntimeProvenanceEvidence(
            schema_version=PROVENANCE_EVIDENCE_SCHEMA,
            plan=plan,
            checkpoint_evidence=plan.checkpoint_evidence,
            runtime_identity=plan.runtime_identity,
            receipts=validated_receipts,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("provenance evidence sealing failed")
    return result


def canonical_laya_runtime_provenance_summary_bytes(
    evidence: LayaRuntimeProvenanceEvidence,
) -> bytes:
    """Render only runtime identity and conservative provenance claims."""

    failed = False
    result = None
    try:
        if type(evidence) is not LayaRuntimeProvenanceEvidence:
            raise TypeError("provenance evidence must be exact")
        _require_verified_evidence(evidence)
        _deep_validate_checkpoint_evidence(evidence.checkpoint_evidence)
        payload = {
            "schema_version": evidence.schema_version,
            "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
            "runtime_identity_sha256": evidence.runtime_identity.sha256,
            "artifact_integrity_verified": evidence.artifact_integrity_verified,
            "runtime_config_semantics_verified": evidence.runtime_config_semantics_verified,
            "checkpoint_manifest_semantics_verified": (
                evidence.checkpoint_manifest_semantics_verified
            ),
            "checkpoint_bytes_verified": evidence.checkpoint_bytes_verified,
            "provenance_objects_verified": evidence.provenance_objects_verified,
            "source_git_content_verified": evidence.source_git_content_verified,
            "checkpoint_git_content_verified": evidence.checkpoint_git_content_verified,
            "source_license_declaration_observed": evidence.source_license_declaration_observed,
            "checkpoint_license_declaration_observed": (
                evidence.checkpoint_license_declaration_observed
            ),
            "lock_verified": evidence.lock_verified,
            "sbom_verified": evidence.sbom_verified,
            "lock_sbom_consistent": evidence.lock_sbom_consistent,
            "oci_bytes_verified": evidence.oci_bytes_verified,
            "oci_manifest_semantics_verified": evidence.oci_manifest_semantics_verified,
            "origin_verified": evidence.origin_verified,
            "license_verified": evidence.license_verified,
            "base_ancestry_verified": evidence.base_ancestry_verified,
            "runtime_materialized": evidence.runtime_materialized,
            "executor_available": evidence.executor_available,
            "inference_executed": evidence.inference_executed,
        }
        result = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("provenance evidence validation failed")
    return result
