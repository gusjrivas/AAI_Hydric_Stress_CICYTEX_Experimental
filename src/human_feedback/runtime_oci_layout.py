"""Pure preparation of a closed OCI layout verification plan."""

from __future__ import annotations

import hashlib
import json as _json_parser
from dataclasses import InitVar, dataclass, field
from typing import Any

from human_feedback.runtime_oci_metadata import LayaRuntimeOciEvidence

MAX_OCI_LAYOUT_BYTES = 1_024
MAX_OCI_INDEX_BYTES = 64 * 1_024
MAX_OCI_CONTROL_JSON_DEPTH = 32
MAX_OCI_CONTROL_STRING_LENGTH = 256
MAX_OCI_BLOB_CHUNK_BYTES = 1_024 * 1_024
MAX_OCI_BLOB_CHUNKS = 1_024

LAYOUT_PLAN_SCHEMA = "laya-oci-layout-plan-v1"
LAYOUT_PROFILE_ID = "laya-runtime-oci-layout-profile-v1"
LAYOUT_EVIDENCE_SCHEMA = "laya-runtime-oci-layout-evidence-v1"

_LAYOUT_SIZE_BYTES = 30
_LAYOUT_SHA256 = "18f0797eab35a4597c1e9624aa4f15fd91f6254e5538c1e0d193b2a95dd4acc6"
_INDEX_SIZE_BYTES = 423
_INDEX_SHA256 = "3d28b2fd93177f35031d802b830e2807253ea19838fb0386b14688a49dd75b39"
_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
_INDEX_ANNOTATIONS = {
    "org.opencontainers.image.created": "1970-01-01T00:00:00Z",
    "org.opencontainers.image.ref.name": "laya-runtime-v0.4.2",
}
_INDEX_PLATFORM = {"architecture": "amd64", "os": "linux"}
_FACTORY_TOKEN = object()
_GIT_LFS_POINTER_SIGNATURE = b"version https://git-lfs.github.com/spec/v1"


class _BlobVerificationTypeError(TypeError):
    pass


class _BlobVerificationValueError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("OCI control JSON contains a duplicate key")
        result[key] = value
    return result


def _reject_nonfinite_number(_value: str) -> None:
    raise ValueError("OCI control JSON number must be finite")


def _strict_json_loads(text: str) -> object:
    return _json_parser.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonfinite_number,
    )


class _JsonReader:
    loads = staticmethod(_strict_json_loads)


json = _JsonReader()


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: validated private plan>"


@dataclass(frozen=True, slots=True, repr=False)
class LayaOciBlobPlan:
    role: str
    path: str
    media_type: str
    digest: str
    size_bytes: int
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI blob plan construction is factory-sealed")
        if not all(
            isinstance(value, str) for value in (self.role, self.path, self.media_type, self.digest)
        ):
            raise TypeError("OCI blob plan field type is invalid")
        if type(self.size_bytes) is not int or self.size_bytes <= 0:
            raise ValueError("OCI blob plan size is invalid")
        if not self.digest.startswith("sha256:"):
            raise ValueError("OCI blob plan digest is invalid")
        digest_value = self.digest.removeprefix("sha256:")
        if self.path != f"blobs/sha256/{digest_value}":
            raise ValueError("OCI blob plan path is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class LayaOciLayoutPlan:
    schema_version: str
    oci_evidence: LayaRuntimeOciEvidence
    runtime_identity: object
    control_paths: tuple[str, ...]
    control_file_count: int
    blobs: tuple[LayaOciBlobPlan, ...]
    index_manifest: LayaOciBlobPlan
    blob_count: int
    logical_file_count: int
    blob_total_size_bytes: int
    total_size_bytes: int
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI layout plan construction is factory-sealed")
        if self.schema_version != LAYOUT_PLAN_SCHEMA:
            raise ValueError("OCI layout plan schema is invalid")
        if type(self.oci_evidence) is not LayaRuntimeOciEvidence:
            raise ValueError("OCI layout evidence type is invalid")
        if self.runtime_identity is not self.oci_evidence.runtime_identity:
            raise ValueError("OCI layout runtime identity is invalid")
        if self.control_paths != ("oci-layout", "index.json") or self.control_file_count != 2:
            raise ValueError("OCI layout control profile is invalid")
        if type(self.blobs) is not tuple or len(self.blobs) != 12:
            raise ValueError("OCI layout blob graph is invalid")
        if any(type(blob) is not LayaOciBlobPlan for blob in self.blobs):
            raise ValueError("OCI layout blob graph contains an invalid plan")
        if self.index_manifest is not self.blobs[0]:
            raise ValueError("OCI index manifest binding is invalid")
        if self.blob_count != 12 or self.logical_file_count != 14:
            raise ValueError("OCI layout file counts are invalid")
        if self.blob_total_size_bytes != sum(blob.size_bytes for blob in self.blobs):
            raise ValueError("OCI layout blob total size is invalid")
        if (
            self.total_size_bytes
            != self.blob_total_size_bytes + _LAYOUT_SIZE_BYTES + _INDEX_SIZE_BYTES
        ):
            raise ValueError("OCI layout total size is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedLayaOciBlob:
    plan: LayaOciLayoutPlan
    blob: LayaOciBlobPlan
    blob_bytes_verified: bool
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI blob receipt construction is factory-sealed")
        if type(self.plan) is not LayaOciLayoutPlan:
            raise TypeError("OCI blob receipt plan type is invalid")
        if type(self.blob) is not LayaOciBlobPlan or not any(
            candidate is self.blob for candidate in self.plan.blobs
        ):
            raise ValueError("OCI blob receipt binding is invalid")
        if self.blob_bytes_verified is not True:
            raise ValueError("OCI blob receipt verification flag is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class _LayaOciLayoutCaptureAuthority:
    plan: LayaOciLayoutPlan = field(repr=False)
    receipts: tuple[VerifiedLayaOciBlob, ...] = field(repr=False)
    controls_captured_from_same_root: bool = field(repr=False)
    inventory_captured_from_same_root: bool = field(repr=False)
    final_fd_sweep_verified: bool = field(repr=False)
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI capture authority construction is factory-sealed")
        if type(self.plan) is not LayaOciLayoutPlan:
            raise TypeError("OCI capture authority plan type is invalid")
        if type(self.receipts) is not tuple or len(self.receipts) != len(self.plan.blobs):
            raise ValueError("OCI capture authority receipt tuple is incomplete")
        if not all(
            flag is True
            for flag in (
                self.controls_captured_from_same_root,
                self.inventory_captured_from_same_root,
                self.final_fd_sweep_verified,
            )
        ):
            raise ValueError("OCI capture authority attestation flag is invalid")
        for position, receipt in enumerate(self.receipts):
            if type(receipt) is not VerifiedLayaOciBlob:
                raise TypeError("OCI capture authority receipt type is invalid")
            if receipt.plan is not self.plan:
                raise ValueError("OCI capture authority plan identity is foreign")
            if receipt.blob is not self.plan.blobs[position]:
                raise ValueError("OCI capture authority receipt order is invalid")
            if receipt.blob_bytes_verified is not True:
                raise ValueError("OCI capture authority verification is incomplete")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeOciLayoutEvidence:
    schema_version: str
    plan: LayaOciLayoutPlan = field(repr=False)
    runtime_identity: object = field(repr=False)
    receipts: tuple[VerifiedLayaOciBlob, ...] = field(repr=False)
    _factory_token: InitVar[object]
    artifact_integrity_verified: bool = field(init=False, default=True)
    oci_manifest_semantics_verified: bool = field(init=False, default=True)
    oci_layout_controls_bytes_verified: bool = field(init=False, default=True)
    oci_blob_inventory_verified: bool = field(init=False, default=True)
    oci_same_root_capture_verified: bool = field(init=False, default=True)
    oci_manifest_blob_bytes_verified: bool = field(init=False, default=True)
    oci_config_blob_bytes_verified: bool = field(init=False, default=True)
    oci_layer_blobs_bytes_verified: bool = field(init=False, default=True)
    oci_bytes_verified: bool = field(init=False, default=True)
    lock_verified: bool = field(init=False, default=False)
    sbom_verified: bool = field(init=False, default=False)
    lock_sbom_consistent: bool = field(init=False, default=False)
    runtime_config_semantics_verified: bool = field(init=False, default=False)
    checkpoint_manifest_semantics_verified: bool = field(init=False, default=False)
    checkpoint_bytes_verified: bool = field(init=False, default=False)
    oci_config_semantics_verified: bool = field(init=False, default=False)
    oci_layer_diff_ids_verified: bool = field(init=False, default=False)
    oci_rootfs_verified: bool = field(init=False, default=False)
    origin_verified: bool = field(init=False, default=False)
    license_verified: bool = field(init=False, default=False)
    base_ancestry_verified: bool = field(init=False, default=False)
    rootfs_materialized: bool = field(init=False, default=False)
    runtime_materialized: bool = field(init=False, default=False)
    executor_available: bool = field(init=False, default=False)
    inference_executed: bool = field(init=False, default=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI layout evidence construction is factory-sealed")
        if self.schema_version != LAYOUT_EVIDENCE_SCHEMA:
            raise ValueError("OCI layout evidence schema is invalid")
        if type(self.plan) is not LayaOciLayoutPlan:
            raise TypeError("OCI layout evidence plan type is invalid")
        if self.runtime_identity is not self.plan.runtime_identity:
            raise ValueError("OCI layout evidence runtime identity is invalid")
        if type(self.receipts) is not tuple or len(self.receipts) != len(self.plan.blobs):
            raise ValueError("OCI layout evidence receipt tuple is incomplete")
        for position, receipt in enumerate(self.receipts):
            if (
                type(receipt) is not VerifiedLayaOciBlob
                or receipt.plan is not self.plan
                or receipt.blob is not self.plan.blobs[position]
                or receipt.blob_bytes_verified is not True
            ):
                raise ValueError("OCI layout evidence receipt binding is invalid")
        if not all(
            flag is True
            for flag in (
                self.artifact_integrity_verified,
                self.oci_manifest_semantics_verified,
                self.oci_layout_controls_bytes_verified,
                self.oci_blob_inventory_verified,
                self.oci_same_root_capture_verified,
                self.oci_manifest_blob_bytes_verified,
                self.oci_config_blob_bytes_verified,
                self.oci_layer_blobs_bytes_verified,
                self.oci_bytes_verified,
            )
        ):
            raise ValueError("OCI layout evidence positive claim is invalid")
        if not all(
            flag is False
            for flag in (
                self.lock_verified,
                self.sbom_verified,
                self.lock_sbom_consistent,
                self.runtime_config_semantics_verified,
                self.checkpoint_manifest_semantics_verified,
                self.checkpoint_bytes_verified,
                self.oci_config_semantics_verified,
                self.oci_layer_diff_ids_verified,
                self.oci_rootfs_verified,
                self.origin_verified,
                self.license_verified,
                self.base_ancestry_verified,
                self.rootfs_materialized,
                self.runtime_materialized,
                self.executor_available,
                self.inference_executed,
            )
        ):
            raise ValueError("OCI layout evidence conservative claim is invalid")

    __repr__ = _private_repr


def _validate_json_limits(value: object, *, depth: int = 0) -> None:
    if depth > MAX_OCI_CONTROL_JSON_DEPTH:
        raise ValueError("OCI control JSON depth exceeds limit")
    if isinstance(value, str):
        if len(value) > MAX_OCI_CONTROL_STRING_LENGTH:
            raise ValueError("OCI control JSON string length exceeds limit")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_json_limits(key, depth=depth + 1)
            _validate_json_limits(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _validate_json_limits(item, depth=depth + 1)


def _preflight_control(payload: bytes, *, byte_limit: int) -> None:
    if type(payload) is not bytes:
        raise TypeError("OCI control payload must be immutable bytes")
    if len(payload) > byte_limit:
        raise ValueError("OCI control payload size exceeds limit")


def _parse_control(payload: bytes, *, name: str, byte_limit: int) -> dict[str, Any]:
    _preflight_control(payload, byte_limit=byte_limit)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("OCI control payload is not strict UTF-8") from None
    try:
        parsed = json.loads(text)
    except Exception:
        raise ValueError("OCI control payload is not valid strict JSON") from None
    _validate_json_limits(parsed)
    if not isinstance(parsed, dict):
        raise ValueError(f"OCI {name} control profile must be an object")
    return parsed


def _require_exact_control_bytes(payload: bytes, *, name: str) -> None:
    if name == "layout":
        expected_size = _LAYOUT_SIZE_BYTES
        expected_sha256 = _LAYOUT_SHA256
        message = "OCI layout version exact byte profile is invalid"
    elif name == "index":
        expected_size = _INDEX_SIZE_BYTES
        expected_sha256 = _INDEX_SHA256
        message = "OCI index exact byte digest profile is invalid"
    else:
        raise ValueError("OCI control profile is invalid")
    if len(payload) != expected_size or hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError(message)


def _validate_layout_marker(value: dict[str, Any]) -> None:
    if set(value) != {"imageLayoutVersion"} or value["imageLayoutVersion"] != "1.0.0":
        raise ValueError("OCI layout version field profile is not exact")


def _validate_index(
    value: dict[str, Any],
    *,
    manifest_digest: str,
    manifest_size: int,
    manifest_media_type: str,
) -> None:
    if set(value) != {"schemaVersion", "mediaType", "manifests"}:
        raise ValueError("OCI index fields are not exact")
    manifests = value["manifests"]
    if (
        type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 2
        or value["mediaType"] != _INDEX_MEDIA_TYPE
        or not isinstance(manifests, list)
        or len(manifests) != 1
    ):
        raise ValueError("OCI index schema manifest profile is invalid")
    descriptor = manifests[0]
    if not isinstance(descriptor, dict) or set(descriptor) != {
        "mediaType",
        "digest",
        "size",
        "annotations",
        "platform",
    }:
        raise ValueError("OCI index manifest descriptor fields are invalid")
    if (
        descriptor["mediaType"] != manifest_media_type
        or descriptor["digest"] != manifest_digest
        or type(descriptor["size"]) is not int
        or descriptor["size"] != manifest_size
    ):
        raise ValueError("OCI index manifest descriptor identity profile is invalid")
    if descriptor["annotations"] != _INDEX_ANNOTATIONS:
        raise ValueError("OCI index annotation profile is invalid")
    if descriptor["platform"] != _INDEX_PLATFORM:
        raise ValueError("OCI index platform profile is invalid")


def _blob_plan(role: str, media_type: str, digest: str, size_bytes: int) -> LayaOciBlobPlan:
    digest_value = digest.removeprefix("sha256:")
    return LayaOciBlobPlan(
        role=role,
        path=f"blobs/sha256/{digest_value}",
        media_type=media_type,
        digest=digest,
        size_bytes=size_bytes,
        _factory_token=_FACTORY_TOKEN,
    )


def _require_exact_laya_oci_evidence(oci_evidence: object) -> LayaRuntimeOciEvidence:
    if type(oci_evidence) is not LayaRuntimeOciEvidence:
        raise TypeError("OCI evidence must be an exact factory-sealed type")
    if (
        oci_evidence.artifact_integrity_verified is not True
        or oci_evidence.oci_manifest_semantics_verified is not True
        or oci_evidence.runtime_identity is not oci_evidence.snapshot.runtime_identity
    ):
        raise ValueError("OCI evidence identity or verification state is invalid")
    return oci_evidence


def _prepare_laya_oci_layout_plan(
    oci_evidence: LayaRuntimeOciEvidence,
    oci_layout_bytes: bytes,
    index_bytes: bytes,
) -> LayaOciLayoutPlan:
    _require_exact_laya_oci_evidence(oci_evidence)

    _preflight_control(oci_layout_bytes, byte_limit=MAX_OCI_LAYOUT_BYTES)
    _preflight_control(index_bytes, byte_limit=MAX_OCI_INDEX_BYTES)
    layout = _parse_control(oci_layout_bytes, name="layout", byte_limit=MAX_OCI_LAYOUT_BYTES)
    index = _parse_control(index_bytes, name="index", byte_limit=MAX_OCI_INDEX_BYTES)
    _require_exact_control_bytes(oci_layout_bytes, name="layout")
    _require_exact_control_bytes(index_bytes, name="index")
    _validate_layout_marker(layout)

    captured_oci = tuple(
        artifact
        for artifact in oci_evidence.snapshot.artifacts
        if artifact.spec.kind == "oci_manifest"
    )
    if len(captured_oci) != 1:
        raise ValueError("OCI evidence manifest artifact coverage is invalid")
    manifest_artifact = captured_oci[0]
    manifest_digest = f"sha256:{manifest_artifact.spec.sha256}"
    manifest_size = manifest_artifact.spec.size_bytes
    manifest_media_type = oci_evidence.oci_manifest.media_type
    _validate_index(
        index,
        manifest_digest=manifest_digest,
        manifest_size=manifest_size,
        manifest_media_type=manifest_media_type,
    )

    index_manifest = _blob_plan("manifest", manifest_media_type, manifest_digest, manifest_size)
    config = oci_evidence.oci_manifest.config
    blobs = (
        index_manifest,
        _blob_plan("config", config.media_type, config.digest, config.size_bytes),
        *(
            _blob_plan(f"layer-{position:02d}", layer.media_type, layer.digest, layer.size_bytes)
            for position, layer in enumerate(oci_evidence.oci_manifest.layers)
        ),
    )
    blob_total_size_bytes = sum(blob.size_bytes for blob in blobs)
    return LayaOciLayoutPlan(
        schema_version=LAYOUT_PLAN_SCHEMA,
        oci_evidence=oci_evidence,
        runtime_identity=oci_evidence.runtime_identity,
        control_paths=("oci-layout", "index.json"),
        control_file_count=2,
        blobs=blobs,
        index_manifest=index_manifest,
        blob_count=len(blobs),
        logical_file_count=len(blobs) + 2,
        blob_total_size_bytes=blob_total_size_bytes,
        total_size_bytes=blob_total_size_bytes + len(oci_layout_bytes) + len(index_bytes),
        _factory_token=_FACTORY_TOKEN,
    )


def prepare_laya_oci_layout_plan(
    oci_evidence: LayaRuntimeOciEvidence,
    oci_layout_bytes: bytes,
    index_bytes: bytes,
) -> LayaOciLayoutPlan:
    """Prepare a closed immutable plan from evidence and exact controls."""

    try:
        return _prepare_laya_oci_layout_plan(oci_evidence, oci_layout_bytes, index_bytes)
    except (TypeError, ValueError) as error:
        raise type(error)(str(error)) from None


def _authorize_laya_oci_blob(plan: LayaOciLayoutPlan, digest: str) -> LayaOciBlobPlan:
    if type(plan) is not LayaOciLayoutPlan:
        raise _BlobVerificationTypeError("OCI blob plan must be an exact factory-sealed type")
    try:
        plan.__post_init__(_FACTORY_TOKEN)
    except (TypeError, ValueError):
        raise _BlobVerificationValueError("OCI blob plan validation failed") from None
    if type(digest) is not str:
        raise _BlobVerificationTypeError("OCI blob digest identity is invalid")
    if (
        len(digest) != 71
        or not digest.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in digest[7:])
    ):
        raise _BlobVerificationValueError("OCI blob digest identity is invalid")

    authorized_blob = None
    for candidate in plan.blobs:
        if candidate.digest == digest:
            if authorized_blob is not None:
                raise _BlobVerificationValueError("OCI blob digest authorization is ambiguous")
            authorized_blob = candidate
    if authorized_blob is None:
        raise _BlobVerificationValueError("OCI blob digest is not authorized by the plan")
    return authorized_blob


def _verify_laya_oci_blob_chunks(
    plan: LayaOciLayoutPlan,
    digest: str,
    chunks: object,
) -> VerifiedLayaOciBlob:
    blob = _authorize_laya_oci_blob(plan, digest)
    if type(chunks) in {bytes, bytearray, memoryview, str}:
        raise _BlobVerificationTypeError("OCI blob chunks must be an unambiguous iterable")

    digest_hasher = hashlib.sha256()
    total_size = 0
    chunk_count = 0
    lfs_prefix = b""
    lfs_candidate = True
    for chunk in chunks:  # type: ignore[union-attr]
        chunk_count += 1
        if chunk_count > MAX_OCI_BLOB_CHUNKS:
            raise _BlobVerificationValueError("OCI blob chunk count exceeds limit")
        if type(chunk) is not bytes:
            raise _BlobVerificationTypeError("OCI blob chunk must be exact bytes")
        if not chunk:
            raise _BlobVerificationValueError("OCI blob chunk must not be empty or zero length")
        if len(chunk) > MAX_OCI_BLOB_CHUNK_BYTES:
            raise _BlobVerificationValueError("OCI blob chunk size exceeds limit")

        total_size += len(chunk)
        if total_size > blob.size_bytes:
            raise _BlobVerificationValueError("OCI blob size exceeds the expected content length")

        if lfs_candidate and len(lfs_prefix) < len(_GIT_LFS_POINTER_SIGNATURE):
            remaining = len(_GIT_LFS_POINTER_SIGNATURE) - len(lfs_prefix)
            lfs_prefix += chunk[:remaining]
            if not _GIT_LFS_POINTER_SIGNATURE.startswith(lfs_prefix):
                lfs_candidate = False
            elif len(lfs_prefix) == len(_GIT_LFS_POINTER_SIGNATURE):
                raise _BlobVerificationValueError("OCI blob content is a Git LFS pointer")

        digest_hasher.update(chunk)

    if total_size != blob.size_bytes:
        raise _BlobVerificationValueError("OCI blob size does not match expected content length")
    if digest_hasher.hexdigest() != blob.digest.removeprefix("sha256:"):
        raise _BlobVerificationValueError("OCI blob digest verification failed")
    return VerifiedLayaOciBlob(
        plan=plan,
        blob=blob,
        blob_bytes_verified=True,
        _factory_token=_FACTORY_TOKEN,
    )


def verify_laya_oci_blob_chunks(
    plan: LayaOciLayoutPlan,
    digest: str,
    chunks: object,
) -> VerifiedLayaOciBlob:
    """Verify one authorized OCI blob incrementally from bounded chunks."""

    try:
        return _verify_laya_oci_blob_chunks(plan, digest, chunks)
    except _BlobVerificationTypeError as error:
        sanitized = TypeError(str(error))
        sanitized.__suppress_context__ = True
        raise sanitized
    except _BlobVerificationValueError as error:
        sanitized = ValueError(str(error))
        sanitized.__suppress_context__ = True
        raise sanitized
    except Exception:
        sanitized = ValueError("OCI blob stream iteration failed")
        sanitized.__suppress_context__ = True
        raise sanitized


def _seal_laya_oci_layout_capture_authority(
    plan: LayaOciLayoutPlan,
    receipts: tuple[VerifiedLayaOciBlob, ...],
    *,
    controls_captured_from_same_root: bool,
    inventory_captured_from_same_root: bool,
    final_fd_sweep_verified: bool,
) -> _LayaOciLayoutCaptureAuthority:
    if type(plan) is not LayaOciLayoutPlan:
        raise TypeError("OCI capture authority requires an exact factory-sealed plan")
    for flag in (
        controls_captured_from_same_root,
        inventory_captured_from_same_root,
        final_fd_sweep_verified,
    ):
        if flag is not True:
            raise ValueError("OCI capture same-root inventory sweep flag is invalid")
    if type(receipts) is not tuple:
        raise TypeError("OCI capture receipt container must be an exact tuple")
    if len(receipts) != len(plan.blobs):
        raise ValueError("OCI capture receipt count is incomplete")
    for position, receipt in enumerate(receipts):
        if type(receipt) is not VerifiedLayaOciBlob:
            raise TypeError("OCI capture receipt type is invalid")
        if receipt.plan is not plan:
            raise ValueError("OCI capture plan identity is foreign")
        if receipt.blob is not plan.blobs[position]:
            raise ValueError("OCI capture receipt order or duplicate identity is invalid")
        if receipt.blob_bytes_verified is not True:
            raise ValueError("OCI capture receipt verification is incomplete")
    return _LayaOciLayoutCaptureAuthority(
        plan=plan,
        receipts=receipts,
        controls_captured_from_same_root=controls_captured_from_same_root,
        inventory_captured_from_same_root=inventory_captured_from_same_root,
        final_fd_sweep_verified=final_fd_sweep_verified,
        _factory_token=_FACTORY_TOKEN,
    )


def _seal_laya_oci_layout_evidence(
    authority: _LayaOciLayoutCaptureAuthority,
) -> LayaRuntimeOciLayoutEvidence:
    if type(authority) is not _LayaOciLayoutCaptureAuthority:
        raise TypeError("OCI capture authority must be an exact factory-sealed type")
    authority.__post_init__(_FACTORY_TOKEN)
    return LayaRuntimeOciLayoutEvidence(
        schema_version=LAYOUT_EVIDENCE_SCHEMA,
        plan=authority.plan,
        runtime_identity=authority.plan.runtime_identity,
        receipts=authority.receipts,
        _factory_token=_FACTORY_TOKEN,
    )


def canonical_laya_runtime_oci_layout_summary_bytes(
    evidence: LayaRuntimeOciLayoutEvidence,
) -> bytes:
    """Return the privacy-safe canonical summary of sealed layout evidence."""

    if type(evidence) is not LayaRuntimeOciLayoutEvidence:
        error = TypeError("OCI layout evidence must be an exact factory-sealed type")
        error.__suppress_context__ = True
        raise error
    try:
        evidence.__post_init__(_FACTORY_TOKEN)
        summary = {
            "schema_version": evidence.schema_version,
            "profile_id": LAYOUT_PROFILE_ID,
            "plan_schema_version": evidence.plan.schema_version,
            "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
            "runtime_identity_sha256": evidence.runtime_identity.sha256,
            "artifact_integrity_verified": evidence.artifact_integrity_verified,
            "oci_manifest_semantics_verified": evidence.oci_manifest_semantics_verified,
            "oci_layout_controls_bytes_verified": evidence.oci_layout_controls_bytes_verified,
            "oci_blob_inventory_verified": evidence.oci_blob_inventory_verified,
            "oci_same_root_capture_verified": evidence.oci_same_root_capture_verified,
            "oci_manifest_blob_bytes_verified": evidence.oci_manifest_blob_bytes_verified,
            "oci_config_blob_bytes_verified": evidence.oci_config_blob_bytes_verified,
            "oci_layer_blobs_bytes_verified": evidence.oci_layer_blobs_bytes_verified,
            "oci_bytes_verified": evidence.oci_bytes_verified,
            "lock_verified": evidence.lock_verified,
            "sbom_verified": evidence.sbom_verified,
            "lock_sbom_consistent": evidence.lock_sbom_consistent,
            "runtime_config_semantics_verified": evidence.runtime_config_semantics_verified,
            "checkpoint_manifest_semantics_verified": (
                evidence.checkpoint_manifest_semantics_verified
            ),
            "checkpoint_bytes_verified": evidence.checkpoint_bytes_verified,
            "oci_config_semantics_verified": evidence.oci_config_semantics_verified,
            "oci_layer_diff_ids_verified": evidence.oci_layer_diff_ids_verified,
            "oci_rootfs_verified": evidence.oci_rootfs_verified,
            "origin_verified": evidence.origin_verified,
            "license_verified": evidence.license_verified,
            "base_ancestry_verified": evidence.base_ancestry_verified,
            "rootfs_materialized": evidence.rootfs_materialized,
            "runtime_materialized": evidence.runtime_materialized,
            "executor_available": evidence.executor_available,
            "inference_executed": evidence.inference_executed,
        }
        return _json_parser.dumps(
            summary,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except Exception:
        error = ValueError("OCI layout evidence summary validation failed")
        error.__suppress_context__ = True
        raise error
