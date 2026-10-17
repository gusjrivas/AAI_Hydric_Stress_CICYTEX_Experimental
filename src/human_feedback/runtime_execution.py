"""Pure authority boundary for one bounded synthetic Laya execution."""

from __future__ import annotations

from dataclasses import InitVar as _InitVar
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from types import MappingProxyType as _MappingProxyType

from human_feedback import runtime_materialization as _runtime_materialization

__all__ = (
    "LayaRuntimeExecutionPlan",
    "LayaRuntimeExecutionEvidence",
    "prepare_laya_runtime_execution_plan",
    "canonical_laya_runtime_execution_summary_bytes",
)

EXECUTION_PROFILE = "docker-local-offline-cpu-synthetic-v1"
EXECUTION_CLAIMS = _MappingProxyType(
    {
        "artifact_integrity_verified": True,
        "oci_manifest_semantics_verified": True,
        "oci_layout_controls_bytes_verified": True,
        "oci_blob_inventory_verified": True,
        "oci_same_root_capture_verified": True,
        "oci_manifest_blob_bytes_verified": True,
        "oci_config_blob_bytes_verified": True,
        "oci_layer_blobs_bytes_verified": True,
        "oci_bytes_verified": True,
        "oci_config_semantics_verified": True,
        "oci_layer_diff_ids_verified": True,
        "base_ancestry_verified": True,
        "runtime_config_semantics_verified": True,
        "checkpoint_manifest_semantics_verified": True,
        "checkpoint_bytes_verified": True,
        "provenance_objects_verified": True,
        "source_git_content_verified": True,
        "checkpoint_git_content_verified": True,
        "source_license_declaration_observed": True,
        "checkpoint_license_declaration_observed": True,
        "runtime_supply_content_convergence_verified": True,
        "tar_semantics_verified": True,
        "oci_rootfs_verified": True,
        "rootfs_materialized": True,
        "lock_verified": False,
        "sbom_verified": False,
        "lock_sbom_consistent": False,
        "origin_verified": False,
        "license_verified": False,
        "runtime_build_recipe_verified": False,
        "build_process_attested": False,
        "reproducible_build_verified": False,
        "runtime_materialized": True,
        "executor_available": True,
        "inference_executed": True,
    }
)

_PLAN_SCHEMA = "laya-runtime-execution-plan-v1"
_EVIDENCE_SCHEMA = "laya-runtime-execution-evidence-v1"
_FACTORY_TOKEN = object()
_EVIDENCE_TOKEN = object()


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private runtime execution value>"


def _raise_private(message: str) -> None:
    error = ValueError(message)
    error.__suppress_context__ = True
    raise error from None


def _validate_claim_boundary(runtime_evidence: object) -> None:
    predecessor = _runtime_materialization.MATERIALIZATION_CLAIMS
    if set(predecessor) != set(EXECUTION_CLAIMS):
        raise ValueError("runtime execution predecessor claim matrix is invalid")
    changed = {
        claim for claim, expected in EXECUTION_CLAIMS.items() if predecessor[claim] is not expected
    }
    if changed != {"executor_available", "inference_executed"}:
        raise ValueError("runtime execution claim boundary is invalid")
    for claim, expected in predecessor.items():
        observed = getattr(runtime_evidence, claim, None)
        if type(observed) is not bool or observed is not expected:
            raise ValueError("runtime execution predecessor claim is invalid")


def _validate_runtime(value: object):
    if type(value) is not _runtime_materialization.LayaRuntimeMaterializationEvidence:
        raise TypeError("runtime execution predecessor type is invalid")
    issued = _runtime_materialization._require_issued_evidence(value)
    _validate_claim_boundary(issued)
    return issued


@_dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeExecutionPlan:
    schema_version: str
    _runtime_evidence: _runtime_materialization.LayaRuntimeMaterializationEvidence = _field(
        repr=False
    )
    _materialization_plan: _runtime_materialization.LayaRuntimeMaterializationPlan = _field(
        repr=False
    )
    _image_id: str = _field(repr=False)
    _installation_sha256: str = _field(repr=False)
    _runtime_identity: object = _field(repr=False)
    _factory_token: _InitVar[object]
    execution_profile: str = _field(default=EXECUTION_PROFILE, init=False)
    executor_available: bool = _field(default=False, init=False)
    inference_executed: bool = _field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        try:
            issued = _validate_runtime(self._runtime_evidence)
            valid = (
                _factory_token is _FACTORY_TOKEN
                and self.schema_version == _PLAN_SCHEMA
                and self._materialization_plan is issued._plan
                and self._image_id is issued._image_id
                and self._installation_sha256 is issued._installation_sha256
                and self._runtime_identity is issued._plan._runtime_identity
                and self.execution_profile == EXECUTION_PROFILE
                and self.executor_available is False
                and self.inference_executed is False
            )
        except Exception:
            valid = False
        if not valid:
            _raise_private("runtime execution plan binding is invalid")

    __repr__ = _private_repr


def _revalidate_plan(value: object) -> LayaRuntimeExecutionPlan:
    if type(value) is not LayaRuntimeExecutionPlan:
        raise TypeError("runtime execution plan type is invalid")
    value.__post_init__(_FACTORY_TOKEN)
    return value


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeExecutionEvidence:
    schema_version: str
    _plan: LayaRuntimeExecutionPlan = _field(repr=False)
    _factory_token: _InitVar[object]
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
    runtime_config_semantics_verified: bool = _field(default=True, init=False)
    checkpoint_manifest_semantics_verified: bool = _field(default=True, init=False)
    checkpoint_bytes_verified: bool = _field(default=True, init=False)
    provenance_objects_verified: bool = _field(default=True, init=False)
    source_git_content_verified: bool = _field(default=True, init=False)
    checkpoint_git_content_verified: bool = _field(default=True, init=False)
    source_license_declaration_observed: bool = _field(default=True, init=False)
    checkpoint_license_declaration_observed: bool = _field(default=True, init=False)
    runtime_supply_content_convergence_verified: bool = _field(default=True, init=False)
    tar_semantics_verified: bool = _field(default=True, init=False)
    oci_rootfs_verified: bool = _field(default=True, init=False)
    rootfs_materialized: bool = _field(default=True, init=False)
    lock_verified: bool = _field(default=False, init=False)
    sbom_verified: bool = _field(default=False, init=False)
    lock_sbom_consistent: bool = _field(default=False, init=False)
    origin_verified: bool = _field(default=False, init=False)
    license_verified: bool = _field(default=False, init=False)
    runtime_build_recipe_verified: bool = _field(default=False, init=False)
    build_process_attested: bool = _field(default=False, init=False)
    reproducible_build_verified: bool = _field(default=False, init=False)
    runtime_materialized: bool = _field(default=True, init=False)
    executor_available: bool = _field(default=True, init=False)
    inference_executed: bool = _field(default=True, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if (
            _factory_token is not _EVIDENCE_TOKEN
            or self.schema_version != _EVIDENCE_SCHEMA
            or type(self._plan) is not LayaRuntimeExecutionPlan
            or any(
                getattr(self, claim, None) is not expected
                for claim, expected in EXECUTION_CLAIMS.items()
            )
        ):
            _raise_private("runtime execution evidence binding is invalid")
        _revalidate_plan(self._plan)

    __repr__ = _private_repr


def prepare_laya_runtime_execution_plan(
    runtime_evidence: object,
) -> LayaRuntimeExecutionPlan:
    """Bind one exact live issued runtime without performing external work."""

    result = None
    try:
        issued = _validate_runtime(runtime_evidence)
        result = LayaRuntimeExecutionPlan(
            schema_version=_PLAN_SCHEMA,
            _runtime_evidence=issued,
            _materialization_plan=issued._plan,
            _image_id=issued._image_id,
            _installation_sha256=issued._installation_sha256,
            _runtime_identity=issued._plan._runtime_identity,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        result = None
    if result is None:
        _raise_private("runtime execution predecessor validation failed")
    return result


def _require_issued_evidence(value: object) -> LayaRuntimeExecutionEvidence:
    if type(value) is not LayaRuntimeExecutionEvidence:
        raise TypeError("runtime execution evidence type is invalid")
    value.__post_init__(_EVIDENCE_TOKEN)
    # Positive issuance is intentionally absent until the PR40 acceptance gate closes.
    raise ValueError("runtime execution evidence lacks issued authority")


def canonical_laya_runtime_execution_summary_bytes(evidence: object) -> bytes:
    """Reject unissued scaffolds without exposing runtime or execution details."""

    failed = False
    try:
        _require_issued_evidence(evidence)
    except Exception:
        failed = True
    if failed:
        _raise_private("runtime execution evidence validation failed")
    raise AssertionError("unreachable")
