"""Pure identity-bound planning for OCI layer DiffID verification."""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field

from human_feedback.runtime_oci_config import (
    LayaRuntimeOciConfigEvidence,
    canonical_laya_runtime_oci_config_summary_bytes,
)

OCI_LAYER_DIFF_ID_PLAN_SCHEMA = "laya-oci-layer-diff-id-plan-v1"

_FACTORY_TOKEN = object()
_LAYER_ROLES = tuple(f"layer-{index:02d}" for index in range(10))


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
