"""Pure identity-bound planning for OCI layer DiffID verification."""

from __future__ import annotations

import hashlib
import json
import zlib
from dataclasses import InitVar, dataclass, field

import human_feedback.runtime_oci_layout as runtime_oci_layout
from human_feedback.runtime_oci_config import (
    LayaRuntimeOciConfigEvidence,
    canonical_laya_runtime_oci_config_summary_bytes,
)

OCI_LAYER_DIFF_ID_PLAN_SCHEMA = "laya-oci-layer-diff-id-plan-v1"
OCI_LAYER_DIFF_IDS_EVIDENCE_SCHEMA = "laya-runtime-oci-layer-diff-ids-evidence-v1"
MAX_OCI_LAYER_CHUNK_BYTES = 1_024 * 1_024
MAX_OCI_LAYER_CHUNKS = 1_024
MAX_OCI_LAYER_UNCOMPRESSED_BYTES = 2 * 1_024 * 1_024 * 1_024
MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES = 3 * 1_024 * 1_024 * 1_024

_FACTORY_TOKEN = object()
_LAYER_ROLES = tuple(f"layer-{index:02d}" for index in range(10))


class _LayerExpansionError(ValueError):
    pass


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private OCI layer DiffID plan>"


def _raise_private(error_type: type[Exception], message: str) -> None:
    error = error_type(message)
    error.__suppress_context__ = True
    raise error


@dataclass(frozen=True, slots=True, repr=False)
class LayaOciLayerDiffIdPlan:
    schema_version: str
    config_evidence: LayaRuntimeOciConfigEvidence = field(repr=False)
    layout_evidence: object = field(repr=False)
    layout_plan: object = field(repr=False)
    runtime_identity: object = field(repr=False)
    layer_blobs: tuple[object, ...] = field(repr=False)
    layer_receipts: tuple[object, ...] = field(repr=False)
    declared_diff_ids: tuple[str, ...] = field(repr=False)
    _factory_token: InitVar[object]
    oci_layer_diff_ids_verified: bool = field(default=False, init=False)
    oci_rootfs_verified: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI layer DiffID plan requires the factory seal token")
        if self.schema_version != OCI_LAYER_DIFF_ID_PLAN_SCHEMA:
            raise ValueError("OCI layer DiffID plan schema is invalid")
        if type(self.config_evidence) is not LayaRuntimeOciConfigEvidence:
            raise ValueError("OCI layer DiffID config evidence is invalid")
        if (
            self.layout_evidence is not self.config_evidence.layout_evidence
            or self.layout_plan is not self.layout_evidence.plan
            or self.runtime_identity is not self.config_evidence.runtime_identity
            or self.runtime_identity is not self.layout_evidence.runtime_identity
            or type(self.layer_blobs) is not tuple
            or type(self.layer_receipts) is not tuple
            or len(self.layer_blobs) != 10
            or len(self.layer_receipts) != 10
            or tuple(blob.role for blob in self.layer_blobs) != _LAYER_ROLES
            or any(
                blob is not self.layout_plan.blobs[position + 2]
                for position, blob in enumerate(self.layer_blobs)
            )
            or any(
                receipt is not self.layout_evidence.receipts[position + 2]
                or receipt.plan is not self.layout_plan
                or receipt.blob is not self.layer_blobs[position]
                or receipt.blob_bytes_verified is not True
                for position, receipt in enumerate(self.layer_receipts)
            )
            or type(self.declared_diff_ids) is not tuple
            or self.declared_diff_ids is not self.config_evidence.config.declared_diff_ids
            or len(self.declared_diff_ids) != 10
            or self.oci_layer_diff_ids_verified is not False
            or self.oci_rootfs_verified is not False
            or self.origin_verified is not False
        ):
            raise ValueError("OCI layer DiffID plan binding is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedLayaOciLayerDiffId:
    plan: LayaOciLayerDiffIdPlan = field(repr=False)
    layer_blob: object = field(repr=False)
    compressed_receipt: object = field(repr=False)
    layer_position: int
    declared_diff_id: str = field(repr=False)
    computed_diff_id: str = field(repr=False)
    uncompressed_size_bytes: int = field(repr=False)
    _factory_token: InitVar[object]
    compressed_blob_bytes_verified: bool = field(default=True, init=False)
    layer_diff_id_verified: bool = field(default=True, init=False)
    tar_semantics_verified: bool = field(default=False, init=False)
    rootfs_verified: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI layer DiffID receipt requires the factory seal token")
        if type(self.plan) is not LayaOciLayerDiffIdPlan:
            raise ValueError("OCI layer DiffID receipt plan is invalid")
        if (
            type(self.layer_position) is not int
            or not 0 <= self.layer_position < len(self.plan.layer_blobs)
            or self.layer_blob is not self.plan.layer_blobs[self.layer_position]
            or self.compressed_receipt is not self.plan.layer_receipts[self.layer_position]
            or self.declared_diff_id is not self.plan.declared_diff_ids[self.layer_position]
            or type(self.computed_diff_id) is not str
            or self.computed_diff_id != self.declared_diff_id
            or type(self.uncompressed_size_bytes) is not int
            or self.uncompressed_size_bytes < 0
            or self.uncompressed_size_bytes > MAX_OCI_LAYER_UNCOMPRESSED_BYTES
            or self.compressed_blob_bytes_verified is not True
            or self.layer_diff_id_verified is not True
            or self.tar_semantics_verified is not False
            or self.rootfs_verified is not False
            or self.origin_verified is not False
        ):
            raise ValueError("OCI layer DiffID receipt binding is invalid")

    __repr__ = _private_repr


def _validate_verified_receipts(
    plan: LayaOciLayerDiffIdPlan,
    receipts: object,
) -> tuple[VerifiedLayaOciLayerDiffId, ...]:
    if type(receipts) is not tuple or len(receipts) != len(plan.layer_blobs):
        raise ValueError("OCI layer DiffID receipt coverage is invalid")
    total_size = 0
    for position, receipt in enumerate(receipts):
        if type(receipt) is not VerifiedLayaOciLayerDiffId:
            raise ValueError("OCI layer DiffID receipt type is invalid")
        receipt.__post_init__(_FACTORY_TOKEN)
        if (
            receipt.plan is not plan
            or receipt.layer_blob is not plan.layer_blobs[position]
            or receipt.compressed_receipt is not plan.layer_receipts[position]
            or receipt.layer_position != position
            or receipt.declared_diff_id is not plan.declared_diff_ids[position]
        ):
            raise ValueError("OCI layer DiffID receipt order is invalid")
        total_size += receipt.uncompressed_size_bytes
        if total_size > MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES:
            raise ValueError("OCI layer DiffID aggregate size exceeds rootfs limit")
    return receipts


@dataclass(frozen=True, slots=True, repr=False)
class _LayaOciLayerDiffIdsCaptureAuthority:
    plan: LayaOciLayerDiffIdPlan = field(repr=False)
    receipts: tuple[VerifiedLayaOciLayerDiffId, ...] = field(repr=False)
    layers_captured_from_same_root: bool
    inventory_captured_from_same_root: bool
    final_fd_sweep_verified: bool
    descriptors_closed_before_seal: bool
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI layer DiffID authority requires the factory seal token")
        if type(self.plan) is not LayaOciLayerDiffIdPlan:
            raise ValueError("OCI layer DiffID authority plan is invalid")
        canonical_laya_runtime_oci_config_summary_bytes(self.plan.config_evidence)
        self.plan.__post_init__(_FACTORY_TOKEN)
        _validate_verified_receipts(self.plan, self.receipts)
        if any(
            flag is not True
            for flag in (
                self.layers_captured_from_same_root,
                self.inventory_captured_from_same_root,
                self.final_fd_sweep_verified,
                self.descriptors_closed_before_seal,
            )
        ):
            raise ValueError("OCI layer DiffID authority closure is invalid")

    __repr__ = _private_repr


_EVIDENCE_TRUE_FLAGS = (
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
)
_EVIDENCE_FALSE_FLAGS = (
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


@dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeOciLayerDiffIdsEvidence:
    schema_version: str
    plan: LayaOciLayerDiffIdPlan = field(repr=False)
    config_evidence: LayaRuntimeOciConfigEvidence = field(repr=False)
    layout_evidence: object = field(repr=False)
    layout_plan: object = field(repr=False)
    runtime_identity: object = field(repr=False)
    receipts: tuple[VerifiedLayaOciLayerDiffId, ...] = field(repr=False)
    _factory_token: InitVar[object]
    artifact_integrity_verified: bool = field(default=True, init=False)
    oci_manifest_semantics_verified: bool = field(default=True, init=False)
    oci_layout_controls_bytes_verified: bool = field(default=True, init=False)
    oci_blob_inventory_verified: bool = field(default=True, init=False)
    oci_same_root_capture_verified: bool = field(default=True, init=False)
    oci_manifest_blob_bytes_verified: bool = field(default=True, init=False)
    oci_config_blob_bytes_verified: bool = field(default=True, init=False)
    oci_layer_blobs_bytes_verified: bool = field(default=True, init=False)
    oci_bytes_verified: bool = field(default=True, init=False)
    oci_config_semantics_verified: bool = field(default=True, init=False)
    oci_layer_diff_ids_verified: bool = field(default=True, init=False)
    lock_verified: bool = field(default=False, init=False)
    sbom_verified: bool = field(default=False, init=False)
    lock_sbom_consistent: bool = field(default=False, init=False)
    runtime_config_semantics_verified: bool = field(default=False, init=False)
    checkpoint_manifest_semantics_verified: bool = field(default=False, init=False)
    checkpoint_bytes_verified: bool = field(default=False, init=False)
    oci_rootfs_verified: bool = field(default=False, init=False)
    tar_semantics_verified: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)
    license_verified: bool = field(default=False, init=False)
    base_ancestry_verified: bool = field(default=False, init=False)
    rootfs_materialized: bool = field(default=False, init=False)
    runtime_materialized: bool = field(default=False, init=False)
    executor_available: bool = field(default=False, init=False)
    inference_executed: bool = field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI layer DiffID evidence requires the factory seal token")
        _revalidate_layer_evidence(self)

    __repr__ = _private_repr


def _prepare_laya_oci_layer_diff_id_plan(
    config_evidence: object,
) -> LayaOciLayerDiffIdPlan:
    if type(config_evidence) is not LayaRuntimeOciConfigEvidence:
        raise TypeError("OCI config evidence must be an exact sealed value")
    canonical_laya_runtime_oci_config_summary_bytes(config_evidence)
    layout_evidence = config_evidence.layout_evidence
    layout_plan = layout_evidence.plan
    layer_blobs = layout_plan.blobs[2:]
    layer_receipts = layout_evidence.receipts[2:]
    if (
        type(layer_blobs) is not tuple
        or type(layer_receipts) is not tuple
        or len(layer_blobs) != 10
        or len(layer_receipts) != 10
        or tuple(blob.role for blob in layer_blobs) != _LAYER_ROLES
    ):
        raise ValueError("OCI layer DiffID layout binding is invalid")
    return LayaOciLayerDiffIdPlan(
        schema_version=OCI_LAYER_DIFF_ID_PLAN_SCHEMA,
        config_evidence=config_evidence,
        layout_evidence=layout_evidence,
        layout_plan=layout_plan,
        runtime_identity=config_evidence.runtime_identity,
        layer_blobs=layer_blobs,
        layer_receipts=layer_receipts,
        declared_diff_ids=config_evidence.config.declared_diff_ids,
        _factory_token=_FACTORY_TOKEN,
    )


def prepare_laya_oci_layer_diff_id_plan(
    config_evidence: LayaRuntimeOciConfigEvidence,
) -> LayaOciLayerDiffIdPlan:
    """Create a conservative plan without reading or decompressing layer bytes."""

    failed = False
    try:
        return _prepare_laya_oci_layer_diff_id_plan(config_evidence)
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI layer DiffID config evidence validation failed")
    raise AssertionError("unreachable")


def _authorize_layer(
    plan: object,
    digest: object,
) -> tuple[LayaOciLayerDiffIdPlan, int]:
    if type(plan) is not LayaOciLayerDiffIdPlan:
        raise TypeError("OCI layer plan must be an exact sealed value")
    canonical_laya_runtime_oci_config_summary_bytes(plan.config_evidence)
    plan.__post_init__(_FACTORY_TOKEN)
    if (
        type(digest) is not str
        or len(digest) != 71
        or not digest.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in digest[7:])
    ):
        raise ValueError("OCI layer digest authorization is invalid")
    positions = tuple(
        position for position, blob in enumerate(plan.layer_blobs) if blob.digest == digest
    )
    if len(positions) != 1:
        raise ValueError("OCI layer digest is not uniquely authorized by the plan")
    return plan, positions[0]


def _verify_laya_oci_layer_diff_id_chunks_core(
    plan: object,
    digest: object,
    chunks: object,
    *,
    max_uncompressed_bytes: object = None,
    output_consumer: object = None,
) -> VerifiedLayaOciLayerDiffId:
    global_limit = min(
        MAX_OCI_LAYER_UNCOMPRESSED_BYTES,
        MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES,
    )
    if max_uncompressed_bytes is None:
        expansion_limit = global_limit
    elif (
        type(max_uncompressed_bytes) is not int
        or max_uncompressed_bytes < 1
        or max_uncompressed_bytes > global_limit
    ):
        raise ValueError("OCI layer uncompressed budget must be a bounded positive integer")
    else:
        expansion_limit = max_uncompressed_bytes
    authorized_plan, position = _authorize_layer(plan, digest)
    if type(chunks) in {bytes, bytearray, memoryview, str}:
        raise TypeError("OCI layer chunks must be an unambiguous byte stream")
    if output_consumer is not None and not callable(output_consumer):
        raise TypeError("OCI layer output consumer must be callable")

    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    uncompressed_hasher = hashlib.sha256()
    uncompressed_size = 0
    chunk_count = 0
    decompression_failed = False
    consumer_failed = False

    def consume_output(output: bytes) -> None:
        nonlocal consumer_failed, uncompressed_size
        uncompressed_size += len(output)
        if uncompressed_size > expansion_limit:
            raise _LayerExpansionError("OCI layer uncompressed expansion exceeds size limit")
        uncompressed_hasher.update(output)
        if output and output_consumer is not None:
            try:
                output_consumer(output)
            except Exception:
                consumer_failed = True
                raise

    def decompress_input(compressed: bytes) -> None:
        if decompressor.eof:
            raise ValueError("OCI layer gzip stream has trailing or multiple members")
        pending = compressed
        while pending:
            previous_size = len(pending)
            remaining = expansion_limit - uncompressed_size
            output_limit = min(MAX_OCI_LAYER_CHUNK_BYTES, remaining + 1)
            output = decompressor.decompress(pending, output_limit)
            consume_output(output)
            if decompressor.unused_data:
                raise ValueError("OCI layer gzip stream has trailing or multiple members")
            pending = decompressor.unconsumed_tail
            if pending and len(pending) >= previous_size and not output:
                raise ValueError("OCI layer gzip decompression made no progress")

    def wrapped_chunks():
        nonlocal chunk_count, decompression_failed
        for chunk in chunks:  # type: ignore[union-attr]
            chunk_count += 1
            if chunk_count > MAX_OCI_LAYER_CHUNKS:
                raise ValueError("OCI layer chunk count exceeds limit")
            if type(chunk) is not bytes:
                raise TypeError("OCI layer chunk must be exact bytes")
            if not chunk:
                raise ValueError("OCI layer chunk must not be empty")
            if len(chunk) > MAX_OCI_LAYER_CHUNK_BYTES:
                raise ValueError("OCI layer chunk size exceeds limit")
            if not decompression_failed:
                try:
                    decompress_input(chunk)
                except _LayerExpansionError:
                    raise
                except (ValueError, zlib.error):
                    if consumer_failed:
                        raise
                    decompression_failed = True
            yield chunk

    wrapped = wrapped_chunks()
    runtime_oci_layout.verify_laya_oci_blob_chunks(
        authorized_plan.layout_plan,
        digest,
        wrapped,
    )
    for _chunk in wrapped:
        pass

    if decompression_failed:
        raise ValueError("OCI layer gzip member is invalid")
    while not decompressor.eof:
        remaining = expansion_limit - uncompressed_size
        output_limit = min(MAX_OCI_LAYER_CHUNK_BYTES, remaining + 1)
        output = decompressor.decompress(b"", output_limit)
        consume_output(output)
        if decompressor.unused_data:
            raise ValueError("OCI layer gzip stream has trailing or multiple members")
        if not output:
            break
    if not decompressor.eof:
        raise ValueError("OCI layer gzip member is truncated or invalid")
    if decompressor.unused_data or decompressor.unconsumed_tail:
        raise ValueError("OCI layer gzip stream has trailing or multiple members")

    computed_diff_id = f"sha256:{uncompressed_hasher.hexdigest()}"
    declared_diff_id = authorized_plan.declared_diff_ids[position]
    if computed_diff_id != declared_diff_id:
        raise ValueError("OCI layer computed DiffID does not match the declared digest")
    return VerifiedLayaOciLayerDiffId(
        plan=authorized_plan,
        layer_blob=authorized_plan.layer_blobs[position],
        compressed_receipt=authorized_plan.layer_receipts[position],
        layer_position=position,
        declared_diff_id=declared_diff_id,
        computed_diff_id=computed_diff_id,
        uncompressed_size_bytes=uncompressed_size,
        _factory_token=_FACTORY_TOKEN,
    )


def _verify_laya_oci_layer_diff_id_chunks(
    plan: object,
    digest: object,
    chunks: object,
    *,
    max_uncompressed_bytes: object = None,
) -> VerifiedLayaOciLayerDiffId:
    return _verify_laya_oci_layer_diff_id_chunks_core(
        plan,
        digest,
        chunks,
        max_uncompressed_bytes=max_uncompressed_bytes,
    )


def _verify_laya_oci_layer_diff_id_chunks_with_consumer(
    plan: object,
    digest: object,
    chunks: object,
    consume: object,
) -> VerifiedLayaOciLayerDiffId:
    return _verify_laya_oci_layer_diff_id_chunks_core(
        plan,
        digest,
        chunks,
        output_consumer=consume,
    )


def verify_laya_oci_layer_diff_id_chunks(
    plan: LayaOciLayerDiffIdPlan,
    digest: str,
    chunks: object,
    *,
    max_uncompressed_bytes: int | None = None,
) -> VerifiedLayaOciLayerDiffId:
    """Verify compressed bytes and their declared uncompressed OCI DiffID."""

    global_limit = min(
        MAX_OCI_LAYER_UNCOMPRESSED_BYTES,
        MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES,
    )
    if max_uncompressed_bytes is None:
        effective_limit = global_limit
    elif (
        type(max_uncompressed_bytes) is not int
        or max_uncompressed_bytes < 1
        or max_uncompressed_bytes > global_limit
    ):
        _raise_private(
            ValueError,
            "OCI layer uncompressed budget must be a bounded positive integer",
        )
    else:
        effective_limit = max_uncompressed_bytes
    failed = False
    try:
        return _verify_laya_oci_layer_diff_id_chunks(
            plan,
            digest,
            chunks,
            max_uncompressed_bytes=effective_limit,
        )
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI layer chunk stream validation failed")
    raise AssertionError("unreachable")


def _seal_laya_oci_layer_diff_ids_capture_authority(
    plan: LayaOciLayerDiffIdPlan,
    receipts: tuple[VerifiedLayaOciLayerDiffId, ...],
    *,
    layers_captured_from_same_root: bool,
    inventory_captured_from_same_root: bool,
    final_fd_sweep_verified: bool,
    descriptors_closed_before_seal: bool,
) -> _LayaOciLayerDiffIdsCaptureAuthority:
    failed = False
    try:
        return _LayaOciLayerDiffIdsCaptureAuthority(
            plan=plan,
            receipts=receipts,
            layers_captured_from_same_root=layers_captured_from_same_root,
            inventory_captured_from_same_root=inventory_captured_from_same_root,
            final_fd_sweep_verified=final_fd_sweep_verified,
            descriptors_closed_before_seal=descriptors_closed_before_seal,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI layer DiffID capture authority validation failed")
    raise AssertionError("unreachable")


def _revalidate_layer_evidence(evidence: object) -> LayaRuntimeOciLayerDiffIdsEvidence:
    if type(evidence) is not LayaRuntimeOciLayerDiffIdsEvidence:
        raise ValueError("OCI layer DiffID evidence must be an exact sealed value")
    if evidence.schema_version != OCI_LAYER_DIFF_IDS_EVIDENCE_SCHEMA:
        raise ValueError("OCI layer DiffID evidence schema is invalid")
    if type(evidence.plan) is not LayaOciLayerDiffIdPlan:
        raise ValueError("OCI layer DiffID evidence plan is invalid")
    canonical_laya_runtime_oci_config_summary_bytes(evidence.config_evidence)
    evidence.plan.__post_init__(_FACTORY_TOKEN)
    if (
        evidence.config_evidence is not evidence.plan.config_evidence
        or evidence.layout_evidence is not evidence.config_evidence.layout_evidence
        or evidence.layout_evidence is not evidence.plan.layout_evidence
        or evidence.layout_plan is not evidence.layout_evidence.plan
        or evidence.layout_plan is not evidence.plan.layout_plan
        or evidence.runtime_identity is not evidence.config_evidence.runtime_identity
        or evidence.runtime_identity is not evidence.plan.runtime_identity
    ):
        raise ValueError("OCI layer DiffID evidence binding is invalid")
    _validate_verified_receipts(evidence.plan, evidence.receipts)
    if any(getattr(evidence, flag, None) is not True for flag in _EVIDENCE_TRUE_FLAGS):
        raise ValueError("OCI layer DiffID positive evidence claim is invalid")
    if any(getattr(evidence, flag, None) is not False for flag in _EVIDENCE_FALSE_FLAGS):
        raise ValueError("OCI layer DiffID conservative evidence claim is invalid")
    return evidence


def _seal_laya_runtime_oci_layer_diff_ids_evidence(
    authority: object,
) -> LayaRuntimeOciLayerDiffIdsEvidence:
    if type(authority) is not _LayaOciLayerDiffIdsCaptureAuthority:
        _raise_private(ValueError, "OCI layer DiffID evidence authority is invalid")
    failed = False
    try:
        authority.__post_init__(_FACTORY_TOKEN)
        plan = authority.plan
        return LayaRuntimeOciLayerDiffIdsEvidence(
            schema_version=OCI_LAYER_DIFF_IDS_EVIDENCE_SCHEMA,
            plan=plan,
            config_evidence=plan.config_evidence,
            layout_evidence=plan.layout_evidence,
            layout_plan=plan.layout_plan,
            runtime_identity=plan.runtime_identity,
            receipts=authority.receipts,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI layer DiffID evidence authority validation failed")
    raise AssertionError("unreachable")


def canonical_laya_runtime_oci_layer_diff_ids_summary_bytes(
    evidence: LayaRuntimeOciLayerDiffIdsEvidence,
) -> bytes:
    """Return a canonical privacy-safe summary after deep evidence validation."""

    failed = False
    try:
        validated = _revalidate_layer_evidence(evidence)
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI layer DiffID evidence validation failed")
    payload = {
        "schema_version": validated.schema_version,
        "plan_schema_version": validated.plan.schema_version,
        "runtime_identity_schema_version": validated.runtime_identity.schema_version,
        "runtime_identity_sha256": validated.runtime_identity.sha256,
        **{flag: True for flag in _EVIDENCE_TRUE_FLAGS},
        **{flag: False for flag in _EVIDENCE_FALSE_FLAGS},
    }
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
