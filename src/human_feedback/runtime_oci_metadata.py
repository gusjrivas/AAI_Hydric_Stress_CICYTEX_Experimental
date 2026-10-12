"""Pure validation for the pinned local OCI image manifest metadata."""

from __future__ import annotations

import hashlib
import json as _json_parser
from dataclasses import InitVar, dataclass, field
from typing import Any

from human_feedback import runtime_bundle, runtime_identity

MAX_OCI_MANIFEST_BYTES = 64 * 1024
MAX_OCI_JSON_DEPTH = 32
MAX_OCI_STRING_LENGTH = 4_096
MAX_OCI_LAYERS = 128
MAX_OCI_ANNOTATIONS = 64
OCI_EVIDENCE_SCHEMA_VERSION = "laya-runtime-oci-evidence-v1"

_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
_CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"
_LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
_CONFIG = (
    _CONFIG_MEDIA_TYPE,
    "sha256:bdd27ffe0d14dd637985f09bcdf461e58a64348829a4b3ad3cb7886ff56e20c5",
    10_261,
)
_LAYERS = (
    ("sha256:bc0965b23a04fe7f2d9fb20f597008fcf89891de1c705ffc1c80483a1f098e4f", 28_231_580),
    ("sha256:c58b365c3bcb57c930511e3fef962d15491ef2daba1e111fb5a6b41dbdecfc6b", 3_317_301),
    ("sha256:3bc3f72291794502343f023ab10455e459897b13a73f38b6b56cf266dccb7ec5", 16_202_769),
    ("sha256:42dacf6a4601de71542906f1be2bca5a78b8f430479b260a7097b9870498af69", 251),
    ("sha256:418d9aeceb23d76e9191b40d18f9c73816dc849ef0e1111a42343b73c8ccc51c", 21_573_096),
    ("sha256:ce65de5ef47521f33f7eb5bb76b05d5ff9c5a562e110b077449ff3af802803df", 31_693_638),
    ("sha256:eb0f362469da4169812e6a645b36eca3678d6aaf06acb0297850b2c525692398", 11_510),
    ("sha256:4f4fb700ef54461cfa02571ae0db9a0dc1e0cdb5577484a6d75e68dc38e8acc1", 32),
    ("sha256:890fbe6d21f33111795ef040fe123b712444c40bc1f4e93a940a8baf9a93d339", 511_506_914),
    ("sha256:f3d008f925e78af5c67f1e8b54aead83de30df814e105ff93e12f02c0d515c14", 19_739),
)
_ANNOTATIONS = {
    "org.aai-hydric.runtime.checkpoint-manifest.sha256": (
        "e54ad4cf767dd653c0703f3671e5317a5dca18c351bee2ab0b7943b5472900bf"
    ),
    "org.aai-hydric.runtime.config.sha256": (
        "9a14323b31c463add7188331ce2c98bb3afbd491e15d06b1f98838a917454b5f"
    ),
    "org.aai-hydric.runtime.sbom.sha256": (
        "f2fde1a342990e3b5b4d74d4930bf37f6d2229768b509a27f34edffc009a03b2"
    ),
    "org.aai-hydric.runtime.uv-lock.sha256": (
        "e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526"
    ),
    "org.opencontainers.image.base.digest": (
        "sha256:840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e"
    ),
    "org.opencontainers.image.base.name": "docker.io/library/python:3.11.10-slim-bookworm",
    "org.opencontainers.image.licenses": "Apache-2.0",
    "org.opencontainers.image.revision": "68804629e8ccd9d616d48a40e87de9fabbeae069",
    "org.opencontainers.image.source": "https://github.com/NandhaKishorM/laya",
    "org.opencontainers.image.version": "0.4.2",
}
_SEMANTICS_SHA256 = "e8b3c42b7698c4e821abbb6dca21e3226c8eca59d62983c2ba7ad0b1010539e5"
_OCI_PAYLOAD_SIZE_BYTES = 3_166
_OCI_PAYLOAD_SHA256 = "7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0"
_FACTORY_TOKEN = object()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("OCI manifest JSON contains a duplicate key")
        result[key] = value
    return result


def _reject_nonfinite_number(_value: str) -> None:
    raise ValueError("OCI manifest JSON number must be finite")


def _strict_json_loads(text: str) -> object:
    return _json_parser.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_nonfinite_number,
    )


class _JsonReader:
    loads = staticmethod(_strict_json_loads)
    dumps = staticmethod(_json_parser.dumps)


json = _JsonReader()


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: validated private evidence>"


@dataclass(frozen=True, slots=True, repr=False)
class OciDescriptor:
    media_type: str
    digest: str
    size_bytes: int
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI descriptor construction is factory-sealed")
        if not isinstance(self.media_type, str) or not isinstance(self.digest, str):
            raise TypeError("OCI descriptor field type is invalid")
        if type(self.size_bytes) is not int or self.size_bytes <= 0:
            raise ValueError("OCI descriptor size is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class ValidatedLayaOciManifest:
    schema_version: int
    media_type: str
    config: OciDescriptor
    layers: tuple[OciDescriptor, ...]
    annotations: tuple[tuple[str, str], ...]
    semantics_sha256: str
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI manifest construction is factory-sealed")
        if type(self.schema_version) is not int or self.schema_version != 2:
            raise ValueError("OCI manifest schema version is invalid")
        if self.media_type != _MANIFEST_MEDIA_TYPE:
            raise ValueError("OCI manifest media profile is invalid")
        if self.semantics_sha256 != _SEMANTICS_SHA256:
            raise ValueError("OCI manifest semantic commitment is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeOciEvidence:
    schema_version: str
    snapshot: runtime_bundle.LayaRuntimeBundleSnapshot
    oci_manifest: ValidatedLayaOciManifest
    runtime_identity: runtime_identity.RuntimeIdentityRef
    _factory_token: InitVar[object]
    artifact_integrity_verified: bool = field(default=True, init=False)
    oci_manifest_semantics_verified: bool = field(default=True, init=False)
    lock_verified: bool = field(default=False, init=False)
    sbom_verified: bool = field(default=False, init=False)
    lock_sbom_consistent: bool = field(default=False, init=False)
    runtime_config_semantics_verified: bool = field(default=False, init=False)
    checkpoint_manifest_semantics_verified: bool = field(default=False, init=False)
    checkpoint_bytes_verified: bool = field(default=False, init=False)
    oci_bytes_verified: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)
    runtime_materialized: bool = field(default=False, init=False)
    executor_available: bool = field(default=False, init=False)
    inference_executed: bool = field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI evidence construction is factory-sealed")
        if self.schema_version != OCI_EVIDENCE_SCHEMA_VERSION:
            raise ValueError("OCI evidence schema version is invalid")
        if type(self.snapshot) is not runtime_bundle.LayaRuntimeBundleSnapshot:
            raise ValueError("OCI evidence bundle snapshot is invalid")
        if type(self.oci_manifest) is not ValidatedLayaOciManifest:
            raise ValueError("OCI manifest evidence is invalid")
        if type(self.runtime_identity) is not runtime_identity.RuntimeIdentityRef:
            raise ValueError("OCI runtime identity is invalid")
        if self.runtime_identity != self.snapshot.runtime_identity:
            raise ValueError("OCI runtime identity is inconsistent")

    __repr__ = _private_repr


def _mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _validate_json_limits(value: object, *, depth: int = 0) -> None:
    if depth > MAX_OCI_JSON_DEPTH:
        raise ValueError("OCI manifest JSON depth exceeds limit")
    if isinstance(value, str):
        if len(value) > MAX_OCI_STRING_LENGTH:
            raise ValueError("OCI manifest string length exceeds limit")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_json_limits(key, depth=depth + 1)
            _validate_json_limits(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _validate_json_limits(item, depth=depth + 1)


def _parse_descriptor(
    value: object,
    *,
    expected: tuple[str, str, int],
    context: str,
) -> OciDescriptor:
    descriptor = _mapping(value, context=f"OCI {context} descriptor")
    if set(descriptor) != {"mediaType", "digest", "size"}:
        raise ValueError(f"OCI {context} descriptor fields are not exact")
    media_type = descriptor["mediaType"]
    digest = descriptor["digest"]
    size = descriptor["size"]
    if not isinstance(media_type, str) or not isinstance(digest, str):
        raise TypeError(f"OCI {context} descriptor field type is invalid")
    if type(size) is not int or size <= 0:
        raise ValueError(f"OCI {context} descriptor size is invalid")
    if (media_type, digest, size) != expected:
        raise ValueError(f"OCI {context} descriptor profile is not exact")
    return OciDescriptor(media_type, digest, size, _factory_token=_FACTORY_TOKEN)


def _canonical_semantics_sha256(value: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError):
        raise ValueError("OCI manifest semantic profile cannot be canonicalized") from None
    return hashlib.sha256(encoded).hexdigest()


def _validate_laya_oci_manifest_bytes(payload: bytes) -> ValidatedLayaOciManifest:
    if not isinstance(payload, bytes):
        raise TypeError("OCI manifest payload must be bytes")
    if len(payload) > MAX_OCI_MANIFEST_BYTES:
        raise ValueError("OCI manifest payload size exceeds limit")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("OCI manifest payload is not strict UTF-8") from None
    try:
        parsed = json.loads(text)
    except Exception:
        raise ValueError("OCI manifest payload is not valid strict JSON") from None
    _validate_json_limits(parsed)
    manifest = _mapping(parsed, context="OCI manifest")
    if set(manifest) != {"schemaVersion", "mediaType", "config", "layers", "annotations"}:
        raise ValueError("OCI manifest fields are not exact")
    if type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 2:
        raise ValueError("OCI manifest schema profile is invalid")
    if manifest["mediaType"] != _MANIFEST_MEDIA_TYPE:
        raise ValueError("OCI manifest media profile is invalid")
    raw_layers = manifest["layers"]
    annotations = manifest["annotations"]
    if not isinstance(raw_layers, list):
        raise ValueError("OCI manifest layers must be a list")
    if len(raw_layers) > MAX_OCI_LAYERS:
        raise ValueError("OCI layer cardinality exceeds limit")
    if not isinstance(annotations, dict):
        raise ValueError("OCI manifest annotations must be an object")
    if len(annotations) > MAX_OCI_ANNOTATIONS:
        raise ValueError("OCI annotation count exceeds limit")
    config = _parse_descriptor(manifest["config"], expected=_CONFIG, context="config")
    if len(raw_layers) != len(_LAYERS):
        raise ValueError("OCI layer order and cardinality profile is not exact")
    layers = tuple(
        _parse_descriptor(
            raw_layer,
            expected=(_LAYER_MEDIA_TYPE, expected_digest, expected_size),
            context="layer",
        )
        for raw_layer, (expected_digest, expected_size) in zip(raw_layers, _LAYERS)
    )
    layer_digests = tuple(layer.digest for layer in layers)
    if len(set(layer_digests)) != len(layer_digests) or config.digest in layer_digests:
        raise ValueError("OCI layer digest identity profile is not exact")
    if annotations != _ANNOTATIONS:
        raise ValueError("OCI annotation crosslink profile is not exact")
    semantics_sha256 = _canonical_semantics_sha256(manifest)
    if semantics_sha256 != _SEMANTICS_SHA256:
        raise ValueError("OCI manifest semantic profile is not exact")
    return ValidatedLayaOciManifest(
        2,
        _MANIFEST_MEDIA_TYPE,
        config,
        layers,
        tuple(sorted(annotations.items())),
        semantics_sha256,
        _factory_token=_FACTORY_TOKEN,
    )


def validate_laya_oci_manifest_bytes(payload: bytes) -> ValidatedLayaOciManifest:
    """Validate caller-provided OCI manifest bytes without external state."""

    try:
        return _validate_laya_oci_manifest_bytes(payload)
    except (TypeError, ValueError) as error:
        raise type(error)(str(error)) from None


def _captured_payloads(
    snapshot: runtime_bundle.LayaRuntimeBundleSnapshot,
) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    for artifact in snapshot.artifacts:
        if artifact.spec.kind in payloads or type(artifact.content) is not bytes:
            raise ValueError("OCI bundle artifact coverage is invalid")
        if (
            len(artifact.content) != artifact.spec.size_bytes
            or hashlib.sha256(artifact.content).hexdigest() != artifact.spec.sha256
        ):
            raise ValueError("OCI bundle artifact integrity is invalid")
        payloads[artifact.spec.kind] = artifact.content
    if set(payloads) != set(runtime_identity.ARTIFACT_KINDS):
        raise ValueError("OCI bundle artifact coverage is invalid")
    return payloads


def _cross_check_oci_annotations(
    snapshot: runtime_bundle.LayaRuntimeBundleSnapshot,
    manifest: ValidatedLayaOciManifest,
    payloads: dict[str, bytes],
) -> None:
    annotations = dict(manifest.annotations)
    artifact_links = {
        "dependency_lock": "org.aai-hydric.runtime.uv-lock.sha256",
        "sbom": "org.aai-hydric.runtime.sbom.sha256",
        "runtime_config": "org.aai-hydric.runtime.config.sha256",
        "checkpoint_manifest": "org.aai-hydric.runtime.checkpoint-manifest.sha256",
    }
    if any(
        annotations[annotation] != hashlib.sha256(payloads[kind]).hexdigest()
        for kind, annotation in artifact_links.items()
    ):
        raise ValueError("OCI annotation artifact digest crosslink is inconsistent")

    runtime_manifest = snapshot.manifest
    source, separator, revision = runtime_manifest.source.rpartition("@")
    base_digest = annotations["org.opencontainers.image.base.digest"]
    expected_base_name = f"docker.io/library/python:{runtime_identity.PYTHON_VERSION}-slim-bookworm"
    if (
        not separator
        or runtime_manifest.source != runtime_identity.LAYA_SOURCE
        or annotations["org.opencontainers.image.source"] != source
        or annotations["org.opencontainers.image.revision"] != revision
        or annotations["org.opencontainers.image.licenses"] != runtime_manifest.license
        or runtime_manifest.license != runtime_identity.LAYA_LICENSE
        or annotations["org.opencontainers.image.version"]
        != runtime_manifest.engine.removeprefix("laya==")
        or runtime_manifest.engine != runtime_identity.LAYA_ENGINE
        or annotations["org.opencontainers.image.base.name"] != expected_base_name
        or runtime_manifest.base_image_ref != f"docker.io/library/python@{base_digest}"
    ):
        raise ValueError("OCI runtime source base image profile is inconsistent")


def _validate_laya_runtime_oci_metadata(
    snapshot: runtime_bundle.LayaRuntimeBundleSnapshot,
) -> LayaRuntimeOciEvidence:
    if type(snapshot) is not runtime_bundle.LayaRuntimeBundleSnapshot:
        raise TypeError("OCI metadata input must be an exact verified bundle snapshot")
    if snapshot.artifact_integrity_verified is not True:
        raise ValueError("OCI bundle artifact integrity is not verified")
    expected_identity = runtime_identity.runtime_identity_ref(snapshot.manifest)
    if (
        type(snapshot.runtime_identity) is not runtime_identity.RuntimeIdentityRef
        or snapshot.runtime_identity != expected_identity
    ):
        raise ValueError("OCI bundle runtime identity is invalid")
    payloads = _captured_payloads(snapshot)
    oci_payload = payloads["oci_manifest"]
    if (
        len(oci_payload) != _OCI_PAYLOAD_SIZE_BYTES
        or hashlib.sha256(oci_payload).hexdigest() != _OCI_PAYLOAD_SHA256
    ):
        raise ValueError("OCI manifest artifact exact byte profile is invalid")
    oci_manifest = validate_laya_oci_manifest_bytes(oci_payload)
    _cross_check_oci_annotations(snapshot, oci_manifest, payloads)
    return LayaRuntimeOciEvidence(
        schema_version=OCI_EVIDENCE_SCHEMA_VERSION,
        snapshot=snapshot,
        oci_manifest=oci_manifest,
        runtime_identity=snapshot.runtime_identity,
        _factory_token=_FACTORY_TOKEN,
    )


def validate_laya_runtime_oci_metadata(
    snapshot: runtime_bundle.LayaRuntimeBundleSnapshot,
) -> LayaRuntimeOciEvidence:
    """Bind the exact captured OCI manifest to one verified snapshot."""

    try:
        return _validate_laya_runtime_oci_metadata(snapshot)
    except (TypeError, ValueError) as error:
        raise type(error)(str(error)) from None


def canonical_laya_runtime_oci_summary_bytes(evidence: LayaRuntimeOciEvidence) -> bytes:
    """Return a minimal deterministic summary without captured metadata."""

    if type(evidence) is not LayaRuntimeOciEvidence:
        raise ValueError("OCI evidence must be an exact sealed value")
    payload = {
        "schema_version": evidence.schema_version,
        "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
        "runtime_identity_sha256": evidence.runtime_identity.sha256,
        "artifact_integrity_verified": evidence.artifact_integrity_verified,
        "oci_manifest_semantics_verified": evidence.oci_manifest_semantics_verified,
        "lock_verified": evidence.lock_verified,
        "sbom_verified": evidence.sbom_verified,
        "lock_sbom_consistent": evidence.lock_sbom_consistent,
        "runtime_config_semantics_verified": evidence.runtime_config_semantics_verified,
        "checkpoint_manifest_semantics_verified": (evidence.checkpoint_manifest_semantics_verified),
        "checkpoint_bytes_verified": evidence.checkpoint_bytes_verified,
        "oci_bytes_verified": evidence.oci_bytes_verified,
        "origin_verified": evidence.origin_verified,
        "runtime_materialized": evidence.runtime_materialized,
        "executor_available": evidence.executor_available,
        "inference_executed": evidence.inference_executed,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
