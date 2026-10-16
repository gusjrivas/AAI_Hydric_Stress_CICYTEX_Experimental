"""Pure bounded verification of the pinned external OCI base ancestry."""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
import threading as _threading
import weakref as _weakref
from dataclasses import InitVar as _InitVar
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from human_feedback import runtime_oci_layers as _runtime_oci_layers

__all__ = (
    "LayaRuntimeBaseAncestryPlan",
    "LayaRuntimeBaseAncestryEvidence",
    "prepare_laya_runtime_base_ancestry_plan",
    "verify_laya_runtime_base_ancestry_objects",
    "canonical_laya_runtime_base_ancestry_summary_bytes",
)

BASE_ANCESTRY_PLAN_SCHEMA = "laya-runtime-base-ancestry-plan-v1"
BASE_ANCESTRY_EVIDENCE_SCHEMA = "laya-runtime-base-ancestry-evidence-v1"
MAX_BASE_ANCESTRY_CHUNK_BYTES = 16 * 1024
MAX_BASE_ANCESTRY_CHUNKS = 64
MAX_BASE_ANCESTRY_OBJECT_BYTES = 16 * 1024
MAX_BASE_ANCESTRY_TOTAL_BYTES = 32 * 1024
MAX_BASE_ANCESTRY_JSON_DEPTH = 16
MAX_BASE_ANCESTRY_JSON_NODES = 512
MAX_BASE_ANCESTRY_JSON_STRING_BYTES = 4 * 1024
MAX_BASE_ANCESTRY_JSON_ARRAY_ITEMS = 32
MAX_BASE_ANCESTRY_JSON_OBJECT_KEYS = 64

_FACTORY_TOKEN = object()
_ITERATOR_EOF = object()
_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
_CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"
_LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
_ROOT_DIGEST = "840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e"
_MANIFEST_DIGEST = "efc99f05ec45381aac55e2803c9a0245ea5b8c74965264498338e24e4bf66cc7"
_CONFIG_DIGEST = "80abb94774d660831663290fe0b208b3e067b88647902f0f9e1d3a331a997afd"
_OBJECT_SPECS = (
    (9131, _ROOT_DIGEST),
    (1752, _MANIFEST_DIGEST),
    (5295, _CONFIG_DIGEST),
)
_BASE_LAYERS = (
    (
        "sha256:bc0965b23a04fe7f2d9fb20f597008fcf89891de1c705ffc1c80483a1f098e4f",
        28231580,
        _LAYER_MEDIA_TYPE,
    ),
    (
        "sha256:c58b365c3bcb57c930511e3fef962d15491ef2daba1e111fb5a6b41dbdecfc6b",
        3317301,
        _LAYER_MEDIA_TYPE,
    ),
    (
        "sha256:3bc3f72291794502343f023ab10455e459897b13a73f38b6b56cf266dccb7ec5",
        16202769,
        _LAYER_MEDIA_TYPE,
    ),
    (
        "sha256:42dacf6a4601de71542906f1be2bca5a78b8f430479b260a7097b9870498af69",
        251,
        _LAYER_MEDIA_TYPE,
    ),
)
_BASE_DIFF_IDS = (
    "sha256:c0f1022b22a9b36851b358f44e5475e39d166e71a8073cf53c894a299239b1c5",
    "sha256:bc9155b10ccec596b3283ceca7cc847bc4046db14eab7f77b9b170b5e825e0a5",
    "sha256:0266a6d27cd42ef4422dfb0b6dbd4186f3524600502559e13947f8d4de65c931",
    "sha256:cfc6e3b5400ce78d3df9c4826f39a78db0e7e9a01d2581b860b5611ac6829af6",
)
_TRUE_CLAIMS = (
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
    "base_ancestry_verified",
)
_FALSE_CLAIMS = (
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
    "rootfs_materialized",
    "runtime_materialized",
    "executor_available",
    "inference_executed",
    "runtime_build_recipe_verified",
    "build_process_attested",
    "reproducible_build_verified",
)


class _FactorySealed:
    __slots__ = ("_factory_capability", "_semantic_capability")


class _IdentitySeal:
    __slots__ = ("value",)

    def __init__(self, value: object) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return type(other) is _IdentitySeal and self.value is other.value


class _IssuedRecord:
    __slots__ = ("reference", "semantics", "active")

    def __init__(
        self,
        reference: _weakref.ReferenceType[object],
        semantics: tuple[object, ...],
        *,
        active: bool,
    ) -> None:
        self.reference = reference
        self.semantics = semantics
        self.active = active


_ISSUED_PLANS: dict[int, _IssuedRecord] = {}
_ISSUED_EVIDENCE: dict[int, _IssuedRecord] = {}
_ISSUANCE_LOCK = _threading.Lock()


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private base ancestry value>"


def _raise_sanitized(message: str) -> None:
    error = ValueError(message)
    error.__suppress_context__ = True
    raise error from None


def _mirror_semantics(value: object) -> object:
    if type(value) is _IdentitySeal:
        return _IdentitySeal(value.value)
    if type(value) is tuple:
        return tuple(_mirror_semantics(item) for item in value)
    return value


def _register_issued(
    value: object,
    registry: dict[int, _IssuedRecord],
    semantics: tuple[object, ...],
    *,
    active: bool,
) -> None:
    object.__setattr__(value, "_factory_capability", _FACTORY_TOKEN)
    object.__setattr__(value, "_semantic_capability", _mirror_semantics(semantics))
    identity = id(value)
    record: _IssuedRecord | None = None

    def cleanup(expired: _weakref.ReferenceType[object]) -> None:
        retained_semantics: tuple[object, ...] = ()
        with _ISSUANCE_LOCK:
            if record is not None:
                # Retain the old graph until after unlocking so releasing the
                # final nested reference cannot re-enter another callback here.
                retained_semantics = record.semantics
                record.semantics = ()
                record.active = False
            current = registry.get(identity)
            if current is record and current.reference is expired:
                registry.pop(identity, None)
        del retained_semantics

    reference = _weakref.ref(value, cleanup)
    record = _IssuedRecord(reference, semantics, active=active)
    with _ISSUANCE_LOCK:
        registry[identity] = record


def _require_record(
    value: object,
    expected_type: type,
    registry: dict[int, _IssuedRecord],
    semantics: tuple[object, ...],
    message: str,
    *,
    active: bool | None = None,
) -> _IssuedRecord:
    with _ISSUANCE_LOCK:
        record = registry.get(id(value))
        if (
            type(value) is not expected_type
            or getattr(value, "_factory_capability", None) is not _FACTORY_TOKEN
            or record is None
            or record.reference() is not value
            or record.semantics != semantics
            or (active is not None and record.active is not active)
        ):
            raise ValueError(message)
        return record


def _valid_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and value[7:] != "0" * 64
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _layer_profile(layer_evidence: object) -> tuple[tuple[object, ...], tuple[str, ...]]:
    plan = layer_evidence.plan
    blobs = plan.layer_blobs
    diff_ids = plan.declared_diff_ids
    if (
        type(blobs) is not tuple
        or type(diff_ids) is not tuple
        or len(blobs) != 10
        or len(diff_ids) != 10
        or tuple(blob.role for blob in blobs)
        != tuple(f"layer-{position:02d}" for position in range(10))
        or layer_evidence.runtime_identity is not plan.runtime_identity
        or layer_evidence.config_evidence is not plan.config_evidence
        or layer_evidence.layout_evidence is not plan.layout_evidence
        or layer_evidence.layout_plan is not plan.layout_plan
        or type(plan.layer_receipts) is not tuple
        or len(plan.layer_receipts) != 10
        or type(layer_evidence.receipts) is not tuple
        or len(layer_evidence.receipts) != 10
    ):
        raise ValueError("PR22 layer prefix profile is invalid")
    compressed_prefix = tuple((blob.digest, blob.size_bytes, blob.media_type) for blob in blobs[:4])
    diff_id_prefix = diff_ids[:4]
    if compressed_prefix != _BASE_LAYERS or diff_id_prefix != _BASE_DIFF_IDS:
        raise ValueError("PR22 compressed layer and DiffID prefixes are invalid")
    if any(
        not _valid_digest(blob.digest)
        or type(blob.size_bytes) is not int
        or blob.size_bytes < 1
        or type(blob.media_type) is not str
        for blob in blobs
    ) or any(not _valid_digest(value) for value in diff_ids):
        raise ValueError("PR22 layer digest profile is invalid")
    for position, receipt in enumerate(layer_evidence.receipts):
        if (
            receipt.plan is not plan
            or receipt.layer_blob is not blobs[position]
            or receipt.compressed_receipt is not plan.layer_receipts[position]
            or receipt.layer_position != position
            or receipt.declared_diff_id != diff_ids[position]
            or receipt.computed_diff_id != diff_ids[position]
            or receipt.layer_diff_id_verified is not True
        ):
            raise ValueError("PR22 ordered layer receipt profile is invalid")
    return compressed_prefix, diff_id_prefix


def _validate_predecessor(layer_evidence: object) -> object:
    if type(layer_evidence) is not _runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence:
        raise TypeError("PR22 layer evidence must be an exact issued value")
    _runtime_oci_layers.canonical_laya_runtime_oci_layer_diff_ids_summary_bytes(layer_evidence)
    if any(getattr(layer_evidence, claim, None) is not True for claim in _TRUE_CLAIMS[:-1]):
        raise ValueError("PR22 positive layer evidence claim is invalid")
    predecessor_false = tuple(
        claim
        for claim in _FALSE_CLAIMS
        if claim
        not in {
            "runtime_build_recipe_verified",
            "build_process_attested",
            "reproducible_build_verified",
        }
    )
    if (
        any(getattr(layer_evidence, claim, None) is not False for claim in predecessor_false)
        or getattr(layer_evidence, "base_ancestry_verified", None) is not False
    ):
        raise ValueError("PR22 conservative layer evidence claim is invalid")
    _layer_profile(layer_evidence)
    return layer_evidence


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeBaseAncestryPlan(_FactorySealed):
    schema_version: str
    layer_evidence: _runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence = _field(repr=False)
    layer_plan: object = _field(repr=False)
    config_evidence: object = _field(repr=False)
    layout_evidence: object = _field(repr=False)
    layout_plan: object = _field(repr=False)
    runtime_identity: object = _field(repr=False)
    layer_blobs: tuple[object, ...] = _field(repr=False)
    compressed_receipts: tuple[object, ...] = _field(repr=False)
    diff_id_receipts: tuple[object, ...] = _field(repr=False)
    declared_diff_ids: tuple[str, ...] = _field(repr=False)
    object_specs: tuple[tuple[int, str], ...] = _field(repr=False)
    compressed_layer_prefix: tuple[tuple[object, ...], ...] = _field(repr=False)
    diff_id_prefix: tuple[str, ...] = _field(repr=False)
    _factory_token: _InitVar[object] = None
    base_ancestry_verified: bool = _field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("base ancestry plan requires the factory seal token")
        _validate_plan_shape(self)

    __repr__ = _private_repr


def _validate_plan_shape(value: object) -> LayaRuntimeBaseAncestryPlan:
    if type(value) is not LayaRuntimeBaseAncestryPlan:
        raise TypeError("base ancestry plan type is invalid")
    predecessor = _validate_predecessor(value.layer_evidence)
    compressed_prefix, diff_id_prefix = _layer_profile(predecessor)
    if (
        value.schema_version != BASE_ANCESTRY_PLAN_SCHEMA
        or value.layer_plan is not predecessor.plan
        or value.config_evidence is not predecessor.config_evidence
        or value.layout_evidence is not predecessor.layout_evidence
        or value.layout_plan is not predecessor.layout_plan
        or value.runtime_identity is not predecessor.runtime_identity
        or value.layer_blobs is not predecessor.plan.layer_blobs
        or value.compressed_receipts is not predecessor.plan.layer_receipts
        or value.diff_id_receipts is not predecessor.receipts
        or value.declared_diff_ids is not predecessor.plan.declared_diff_ids
        or value.object_specs != _OBJECT_SPECS
        or value.compressed_layer_prefix != compressed_prefix
        or value.diff_id_prefix != diff_id_prefix
        or value.base_ancestry_verified is not False
    ):
        raise ValueError("base ancestry plan binding is invalid")
    return value


def _plan_semantics(plan: LayaRuntimeBaseAncestryPlan) -> tuple[object, ...]:
    compressed_prefix, diff_id_prefix = _layer_profile(plan.layer_evidence)
    return (
        plan.schema_version,
        _IdentitySeal(plan.layer_evidence),
        _IdentitySeal(plan.layer_plan),
        _IdentitySeal(plan.config_evidence),
        _IdentitySeal(plan.layout_evidence),
        _IdentitySeal(plan.layout_plan),
        _IdentitySeal(plan.runtime_identity),
        _IdentitySeal(plan.layer_blobs),
        tuple(_IdentitySeal(value) for value in plan.layer_blobs),
        _IdentitySeal(plan.compressed_receipts),
        tuple(_IdentitySeal(value) for value in plan.compressed_receipts),
        _IdentitySeal(plan.diff_id_receipts),
        tuple(_IdentitySeal(value) for value in plan.diff_id_receipts),
        _IdentitySeal(plan.declared_diff_ids),
        plan.runtime_identity.schema_version,
        plan.runtime_identity.sha256,
        plan.object_specs,
        compressed_prefix,
        diff_id_prefix,
        plan.base_ancestry_verified,
    )


def _require_issued_plan(
    value: object, *, active: bool | None = None
) -> tuple[LayaRuntimeBaseAncestryPlan, _IssuedRecord]:
    plan = _validate_plan_shape(value)
    record = _require_record(
        plan,
        LayaRuntimeBaseAncestryPlan,
        _ISSUED_PLANS,
        _plan_semantics(plan),
        "base ancestry plan lacks an issued active session",
        active=active,
    )
    return plan, record


def _claim_issued_plan(value: object) -> LayaRuntimeBaseAncestryPlan:
    """Atomically consume one exact issued plan before any stream is touched."""

    plan = _validate_plan_shape(value)
    semantics = _plan_semantics(plan)
    with _ISSUANCE_LOCK:
        record = _ISSUED_PLANS.get(id(plan))
        if (
            type(plan) is not LayaRuntimeBaseAncestryPlan
            or getattr(plan, "_factory_capability", None) is not _FACTORY_TOKEN
            or record is None
            or record.reference() is not plan
            or record.semantics != semantics
            or record.active is not True
        ):
            raise ValueError("base ancestry plan session is not active")
        record.active = False
    return plan


def _revoke_exact_plan(value: object) -> None:
    """Revoke a genuine issued identity after any failed verification attempt."""

    with _ISSUANCE_LOCK:
        record = _ISSUED_PLANS.get(id(value))
        if record is not None and record.reference() is value:
            record.active = False


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeBaseAncestryEvidence(_FactorySealed):
    schema_version: str
    plan: LayaRuntimeBaseAncestryPlan = _field(repr=False)
    layer_evidence: _runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence = _field(repr=False)
    runtime_identity: object = _field(repr=False)
    _factory_token: _InitVar[object] = None
    artifact_integrity_verified: bool = _field(default=True, init=False)
    oci_manifest_semantics_verified: bool = _field(default=True, init=False)
    oci_layout_controls_bytes_verified: bool = _field(default=True, init=False)
    oci_blob_inventory_verified: bool = _field(default=True, init=False)
    oci_same_root_capture_verified: bool = _field(default=True, init=False)
    oci_manifest_blob_bytes_verified: bool = _field(default=True, init=False)
    oci_config_blob_bytes_verified: bool = _field(default=True, init=False)
    oci_layer_blobs_bytes_verified: bool = _field(default=True, init=False)
    oci_bytes_verified: bool = _field(default=True, init=False)
    oci_config_semantics_verified: bool = _field(default=True, init=False)
    oci_layer_diff_ids_verified: bool = _field(default=True, init=False)
    base_ancestry_verified: bool = _field(default=True, init=False)
    lock_verified: bool = _field(default=False, init=False)
    sbom_verified: bool = _field(default=False, init=False)
    lock_sbom_consistent: bool = _field(default=False, init=False)
    runtime_config_semantics_verified: bool = _field(default=False, init=False)
    checkpoint_manifest_semantics_verified: bool = _field(default=False, init=False)
    checkpoint_bytes_verified: bool = _field(default=False, init=False)
    oci_rootfs_verified: bool = _field(default=False, init=False)
    tar_semantics_verified: bool = _field(default=False, init=False)
    origin_verified: bool = _field(default=False, init=False)
    license_verified: bool = _field(default=False, init=False)
    rootfs_materialized: bool = _field(default=False, init=False)
    runtime_materialized: bool = _field(default=False, init=False)
    executor_available: bool = _field(default=False, init=False)
    inference_executed: bool = _field(default=False, init=False)
    runtime_build_recipe_verified: bool = _field(default=False, init=False)
    build_process_attested: bool = _field(default=False, init=False)
    reproducible_build_verified: bool = _field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("base ancestry evidence requires the factory seal token")
        _validate_evidence_shape(self)

    __repr__ = _private_repr


def _validate_evidence_shape(value: object) -> LayaRuntimeBaseAncestryEvidence:
    if type(value) is not LayaRuntimeBaseAncestryEvidence:
        raise TypeError("base ancestry evidence type is invalid")
    plan, record = _require_issued_plan(value.plan, active=False)
    if (
        record.active is not False
        or value.schema_version != BASE_ANCESTRY_EVIDENCE_SCHEMA
        or value.layer_evidence is not plan.layer_evidence
        or value.runtime_identity is not plan.runtime_identity
        or any(getattr(value, claim, None) is not True for claim in _TRUE_CLAIMS)
        or any(getattr(value, claim, None) is not False for claim in _FALSE_CLAIMS)
    ):
        raise ValueError("base ancestry evidence binding or claim is invalid")
    return value


def _evidence_semantics(evidence: LayaRuntimeBaseAncestryEvidence) -> tuple[object, ...]:
    return (
        evidence.schema_version,
        _IdentitySeal(evidence.plan),
        _IdentitySeal(evidence.layer_evidence),
        _IdentitySeal(evidence.runtime_identity),
        tuple(getattr(evidence, claim) for claim in _TRUE_CLAIMS + _FALSE_CLAIMS),
    )


def _require_issued_evidence(value: object) -> LayaRuntimeBaseAncestryEvidence:
    evidence = _validate_evidence_shape(value)
    _require_record(
        evidence,
        LayaRuntimeBaseAncestryEvidence,
        _ISSUED_EVIDENCE,
        _evidence_semantics(evidence),
        "base ancestry evidence lacks issued authority",
    )
    return evidence


def _duplicate_object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_number(value: str) -> object:
    raise ValueError("non-canonical JSON number")


def _validate_json_graph(
    value: object,
    *,
    depth: int = 1,
    nodes: list[int] | None = None,
) -> None:
    if depth > MAX_BASE_ANCESTRY_JSON_DEPTH:
        raise ValueError("JSON depth limit exceeded")
    budget = [0] if nodes is None else nodes
    budget[0] += 1
    if budget[0] > MAX_BASE_ANCESTRY_JSON_NODES:
        raise ValueError("JSON node limit exceeded")
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is str:
        if len(value.encode("utf-8")) > MAX_BASE_ANCESTRY_JSON_STRING_BYTES:
            raise ValueError("JSON string limit exceeded")
        return
    if type(value) is list:
        if len(value) > MAX_BASE_ANCESTRY_JSON_ARRAY_ITEMS:
            raise ValueError("JSON array limit exceeded")
        for item in value:
            _validate_json_graph(item, depth=depth + 1, nodes=budget)
        return
    if type(value) is dict:
        if len(value) > MAX_BASE_ANCESTRY_JSON_OBJECT_KEYS:
            raise ValueError("JSON object key limit exceeded")
        for key, item in value.items():
            if (
                type(key) is not str
                or len(key.encode("utf-8")) > MAX_BASE_ANCESTRY_JSON_STRING_BYTES
            ):
                raise ValueError("JSON key limit exceeded")
            _validate_json_graph(item, depth=depth + 1, nodes=budget)
        return
    raise ValueError("JSON value type is invalid")


def _load_laya_base_ancestry_json(payload: object) -> object:
    failed = False
    result = None
    try:
        if (
            type(payload) is not bytes
            or not payload
            or len(payload) > MAX_BASE_ANCESTRY_OBJECT_BYTES
        ):
            raise ValueError("JSON payload size is invalid")
        text = payload.decode("ascii")
        value = _json.loads(
            text,
            object_pairs_hook=_duplicate_object_pairs,
            parse_float=_reject_json_number,
            parse_constant=_reject_json_number,
        )
        _validate_json_graph(value)
        result = value
    except Exception:
        failed = True
    if failed:
        _raise_sanitized("base ancestry JSON validation failed")
    return result


def _descriptor(value: object, *, allowed: set[str]) -> tuple[str, int, str]:
    if type(value) is not dict or not set(value).issubset(allowed):
        raise ValueError("OCI descriptor is invalid")
    digest = value.get("digest")
    size = value.get("size")
    media_type = value.get("mediaType")
    if (
        not _valid_digest(digest)
        or type(size) is not int
        or size < 1
        or type(media_type) is not str
    ):
        raise ValueError("OCI descriptor is invalid")
    return digest, size, media_type


def _parse_laya_base_index(payload: object) -> tuple[str, int, str]:
    failed = False
    result = None
    try:
        value = _load_laya_base_ancestry_json(payload)
        if (
            type(value) is not dict
            or set(value) != {"schemaVersion", "mediaType", "manifests"}
            or value["schemaVersion"] != 2
            or value["mediaType"] != _INDEX_MEDIA_TYPE
            or type(value["manifests"]) is not list
            or len(value["manifests"]) != 14
        ):
            raise ValueError("OCI base index is invalid")
        for item in value["manifests"]:
            _descriptor(
                item,
                allowed={"digest", "size", "mediaType", "platform", "annotations"},
            )
            if (
                type(item.get("platform")) is not dict
                or not set(item["platform"]).issubset({"architecture", "os", "variant"})
                or type(item["platform"].get("architecture")) is not str
                or type(item["platform"].get("os")) is not str
                or ("variant" in item["platform"] and type(item["platform"]["variant"]) is not str)
                or ("annotations" in item and type(item["annotations"]) is not dict)
            ):
                raise ValueError("OCI base index descriptor platform is invalid")
        selected = tuple(
            item
            for item in value["manifests"]
            if type(item) is dict
            and item.get("platform") == {"architecture": "amd64", "os": "linux"}
        )
        if len(selected) != 1:
            raise ValueError("OCI base index platform selection is invalid")
        descriptor = _descriptor(
            selected[0],
            allowed={"digest", "size", "mediaType", "platform", "annotations"},
        )
        if descriptor != ("sha256:" + _MANIFEST_DIGEST, 1752, _MANIFEST_MEDIA_TYPE):
            raise ValueError("OCI base index manifest descriptor is invalid")
        result = descriptor
    except Exception:
        failed = True
    if failed or result is None:
        _raise_sanitized("base ancestry index validation failed")
    return result


def _parse_laya_base_manifest(
    payload: object,
) -> tuple[tuple[str, int, str], tuple[tuple[str, int, str], ...]]:
    failed = False
    result = None
    try:
        value = _load_laya_base_ancestry_json(payload)
        if (
            type(value) is not dict
            or set(value) != {"schemaVersion", "mediaType", "config", "layers", "annotations"}
            or value["schemaVersion"] != 2
            or value["mediaType"] != _MANIFEST_MEDIA_TYPE
            or type(value["layers"]) is not list
        ):
            raise ValueError("OCI base manifest is invalid")
        config = _descriptor(value["config"], allowed={"digest", "size", "mediaType"})
        layers = tuple(
            _descriptor(item, allowed={"digest", "size", "mediaType"}) for item in value["layers"]
        )
        if config != ("sha256:" + _CONFIG_DIGEST, 5295, _CONFIG_MEDIA_TYPE):
            raise ValueError("OCI base config descriptor is invalid")
        if layers != _BASE_LAYERS:
            raise ValueError("OCI base layer descriptors are invalid")
        result = (config, layers)
    except Exception:
        failed = True
    if failed or result is None:
        _raise_sanitized("base ancestry manifest validation failed")
    return result


def _parse_laya_base_config(payload: object) -> tuple[str, ...]:
    failed = False
    result = None
    try:
        value = _load_laya_base_ancestry_json(payload)
        if (
            type(value) is not dict
            or set(value) != {"architecture", "config", "created", "history", "os", "rootfs"}
            or value["architecture"] != "amd64"
            or value["os"] != "linux"
            or type(value["rootfs"]) is not dict
            or set(value["rootfs"]) != {"type", "diff_ids"}
            or value["rootfs"]["type"] != "layers"
            or type(value["rootfs"]["diff_ids"]) is not list
        ):
            raise ValueError("OCI base config platform or rootfs is invalid")
        diff_ids = tuple(value["rootfs"]["diff_ids"])
        if diff_ids != _BASE_DIFF_IDS or any(not _valid_digest(item) for item in diff_ids):
            raise ValueError("OCI base config DiffID profile is invalid")
        result = diff_ids
    except Exception:
        failed = True
    if failed or result is None:
        _raise_sanitized("base ancestry config validation failed")
    return result


def _validate_object_specs(value: object) -> tuple[tuple[int, str], ...]:
    if type(value) is not tuple or len(value) != 3:
        raise ValueError("base ancestry object profile is invalid")
    total = 0
    for item in value:
        if (
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not int
            or not 0 < item[0] <= MAX_BASE_ANCESTRY_OBJECT_BYTES
            or type(item[1]) is not str
            or len(item[1]) != 64
            or any(character not in "0123456789abcdef" for character in item[1])
        ):
            raise ValueError("base ancestry object profile is invalid")
        total += item[0]
    if total > MAX_BASE_ANCESTRY_TOTAL_BYTES:
        raise ValueError("base ancestry aggregate size exceeds total limit")
    return value


def _consume_laya_base_ancestry_object_streams(
    object_streams: object,
    object_specs: object,
) -> tuple[bytes, bytes, bytes]:
    failed = False
    result = None
    try:
        specs = _validate_object_specs(object_specs)
        if type(object_streams) is not tuple or len(object_streams) != 3:
            raise ValueError("base ancestry object streams must be an exact tuple")
        if any(type(stream) in {bytes, bytearray, memoryview, str} for stream in object_streams):
            raise ValueError("base ancestry nested stream type is invalid")
        captured_objects: list[bytes] = []
        aggregate_size = 0
        for position, stream in enumerate(object_streams):
            expected_size, expected_digest = specs[position]
            iterator = iter(stream)
            chunks: list[bytes] = []
            captured_size = 0
            chunk_count = 0
            hasher = _hashlib.sha256()
            while True:
                chunk = next(iterator, _ITERATOR_EOF)
                if chunk is _ITERATOR_EOF:
                    break
                chunk_count += 1
                if chunk_count > MAX_BASE_ANCESTRY_CHUNKS:
                    raise ValueError("base ancestry chunk count exceeds limit")
                if type(chunk) is not bytes or not chunk:
                    raise ValueError("base ancestry stream chunk must be nonempty exact bytes")
                if len(chunk) > MAX_BASE_ANCESTRY_CHUNK_BYTES:
                    raise ValueError("base ancestry chunk size exceeds limit")
                captured_size += len(chunk)
                aggregate_size += len(chunk)
                if captured_size > MAX_BASE_ANCESTRY_OBJECT_BYTES:
                    raise ValueError("base ancestry object size exceeds limit")
                if aggregate_size > MAX_BASE_ANCESTRY_TOTAL_BYTES:
                    raise ValueError("base ancestry aggregate total exceeds limit")
                hasher.update(chunk)
                chunks.append(chunk)
            if captured_size != expected_size or hasher.hexdigest() != expected_digest:
                raise ValueError("base ancestry object size or digest is invalid")
            captured_objects.append(b"".join(chunks))
        result = tuple(captured_objects)
    except Exception:
        failed = True
    if failed or result is None:
        _raise_sanitized("base ancestry object stream aggregate size limit validation failed")
    return result  # type: ignore[return-value]


def prepare_laya_runtime_base_ancestry_plan(
    layer_evidence: _runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence,
) -> LayaRuntimeBaseAncestryPlan:
    """Bind one-use verification to exact issued PR22 layer evidence."""

    failed = False
    result = None
    try:
        predecessor = _validate_predecessor(layer_evidence)
        compressed_prefix, diff_id_prefix = _layer_profile(predecessor)
        plan = LayaRuntimeBaseAncestryPlan(
            schema_version=BASE_ANCESTRY_PLAN_SCHEMA,
            layer_evidence=predecessor,
            layer_plan=predecessor.plan,
            config_evidence=predecessor.config_evidence,
            layout_evidence=predecessor.layout_evidence,
            layout_plan=predecessor.layout_plan,
            runtime_identity=predecessor.runtime_identity,
            layer_blobs=predecessor.plan.layer_blobs,
            compressed_receipts=predecessor.plan.layer_receipts,
            diff_id_receipts=predecessor.receipts,
            declared_diff_ids=predecessor.plan.declared_diff_ids,
            object_specs=_OBJECT_SPECS,
            compressed_layer_prefix=compressed_prefix,
            diff_id_prefix=diff_id_prefix,
            _factory_token=_FACTORY_TOKEN,
        )
        _register_issued(plan, _ISSUED_PLANS, _plan_semantics(plan), active=True)
        result = plan
    except Exception:
        failed = True
    if failed or result is None:
        _raise_sanitized("PR22 layer evidence validation failed")
    return result


def verify_laya_runtime_base_ancestry_objects(
    plan: LayaRuntimeBaseAncestryPlan,
    object_streams: object,
) -> LayaRuntimeBaseAncestryEvidence:
    """Verify the exact index, amd64 manifest, config and four-layer prefix."""

    failed = False
    result = None
    try:
        issued_plan = _claim_issued_plan(plan)
        payloads = _consume_laya_base_ancestry_object_streams(
            object_streams, issued_plan.object_specs
        )
        manifest_descriptor = _parse_laya_base_index(payloads[0])
        config_descriptor, layers = _parse_laya_base_manifest(payloads[1])
        diff_ids = _parse_laya_base_config(payloads[2])
        if (
            manifest_descriptor != ("sha256:" + _MANIFEST_DIGEST, 1752, _MANIFEST_MEDIA_TYPE)
            or config_descriptor != ("sha256:" + _CONFIG_DIGEST, 5295, _CONFIG_MEDIA_TYPE)
            or layers != issued_plan.compressed_layer_prefix
            or diff_ids != issued_plan.diff_id_prefix
        ):
            raise ValueError("base ancestry semantic graph is invalid")
        evidence = LayaRuntimeBaseAncestryEvidence(
            schema_version=BASE_ANCESTRY_EVIDENCE_SCHEMA,
            plan=issued_plan,
            layer_evidence=issued_plan.layer_evidence,
            runtime_identity=issued_plan.runtime_identity,
            _factory_token=_FACTORY_TOKEN,
        )
        _register_issued(
            evidence,
            _ISSUED_EVIDENCE,
            _evidence_semantics(evidence),
            active=False,
        )
        result = evidence
    except Exception:
        _revoke_exact_plan(plan)
        failed = True
    if failed or result is None:
        _raise_sanitized("base ancestry plan or object session validation failed")
    return result


def canonical_laya_runtime_base_ancestry_summary_bytes(
    evidence: LayaRuntimeBaseAncestryEvidence,
) -> bytes:
    """Return a minimal canonical summary without ancestry source metadata."""

    failed = False
    result = None
    try:
        value = _require_issued_evidence(evidence)
        payload = {
            "schema_version": value.schema_version,
            "plan_schema_version": value.plan.schema_version,
            "runtime_identity_schema_version": value.runtime_identity.schema_version,
            "runtime_identity_sha256": value.runtime_identity.sha256,
            **{claim: True for claim in _TRUE_CLAIMS},
            **{claim: False for claim in _FALSE_CLAIMS},
        }
        result = _json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except Exception:
        failed = True
    if failed or result is None:
        _raise_sanitized("base ancestry evidence validation failed")
    return result
