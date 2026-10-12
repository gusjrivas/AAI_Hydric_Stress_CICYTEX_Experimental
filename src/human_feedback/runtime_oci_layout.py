"""Pure preparation of a closed OCI layout verification plan."""

from __future__ import annotations

import hashlib
import json as _json_parser
from dataclasses import InitVar, dataclass
from typing import Any

from human_feedback.runtime_oci_metadata import LayaRuntimeOciEvidence

MAX_OCI_LAYOUT_BYTES = 1_024
MAX_OCI_INDEX_BYTES = 64 * 1_024
MAX_OCI_CONTROL_JSON_DEPTH = 32
MAX_OCI_CONTROL_STRING_LENGTH = 256

LAYOUT_PLAN_SCHEMA = "laya-oci-layout-plan-v1"

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


def _prepare_laya_oci_layout_plan(
    oci_evidence: LayaRuntimeOciEvidence,
    oci_layout_bytes: bytes,
    index_bytes: bytes,
) -> LayaOciLayoutPlan:
    if type(oci_evidence) is not LayaRuntimeOciEvidence:
        raise TypeError("OCI evidence must be an exact factory-sealed type")
    if (
        oci_evidence.artifact_integrity_verified is not True
        or oci_evidence.oci_manifest_semantics_verified is not True
        or oci_evidence.runtime_identity is not oci_evidence.snapshot.runtime_identity
    ):
        raise ValueError("OCI evidence identity or verification state is invalid")

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
