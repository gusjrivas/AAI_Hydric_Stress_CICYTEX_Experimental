"""Pure authority for one safely materialized Laya OCI rootfs."""

from __future__ import annotations

import json as _json
import threading as _threading
import weakref as _weakref
from dataclasses import InitVar as _InitVar
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from types import MappingProxyType as _MappingProxyType

from human_feedback import runtime_oci_rootfs as _runtime_oci_rootfs
from human_feedback import runtime_supply_convergence as _runtime_supply_convergence

__all__ = (
    "LayaRuntimeRootfsMaterializationPlan",
    "LayaRuntimeRootfsMaterializationEvidence",
    "prepare_laya_runtime_rootfs_materialization_plan",
    "canonical_laya_runtime_rootfs_materialization_summary_bytes",
)

MATERIALIZATION_PROFILE = "nonroot-disposable-v1"
MATERIALIZATION_CLAIMS = _MappingProxyType(
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
        "runtime_materialized": False,
        "executor_available": False,
        "inference_executed": False,
    }
)

_PLAN_SCHEMA = "laya-runtime-rootfs-materialization-plan-v1"
_EVIDENCE_SCHEMA = "laya-runtime-rootfs-materialization-evidence-v1"
_FACTORY_TOKEN = object()
_EVIDENCE_TOKEN = object()


class _IssuedEvidenceRecord:
    __slots__ = (
        "reference",
        "plan",
        "commitment",
        "rootfs_evidence",
        "supply_evidence",
        "runtime_identity",
    )

    def __init__(self, reference, plan, commitment: str) -> None:
        self.reference = reference
        self.plan = plan
        self.commitment = commitment
        self.rootfs_evidence = plan._rootfs_evidence
        self.supply_evidence = plan._supply_evidence
        self.runtime_identity = plan._runtime_identity


_ISSUED_EVIDENCE: dict[int, _IssuedEvidenceRecord] = {}
_ISSUANCE_LOCK = _threading.Lock()


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private rootfs materialization value>"


def _raise_private(message: str) -> None:
    error = ValueError(message)
    error.__suppress_context__ = True
    raise error from None


@_dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeRootfsMaterializationPlan:
    schema_version: str
    _rootfs_evidence: _runtime_oci_rootfs.LayaRuntimeOciRootfsEvidence = _field(repr=False)
    _supply_evidence: _runtime_supply_convergence.LayaRuntimeSupplyConvergenceEvidence = _field(
        repr=False
    )
    _runtime_identity: object = _field(repr=False)
    _factory_token: _InitVar[object]
    materialization_profile: str = _field(default=MATERIALIZATION_PROFILE, init=False)
    rootfs_materialized: bool = _field(default=False, init=False)
    runtime_materialized: bool = _field(default=False, init=False)
    executor_available: bool = _field(default=False, init=False)
    inference_executed: bool = _field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("rootfs materialization plan requires the factory seal token")
        if (
            self.schema_version != _PLAN_SCHEMA
            or type(self._rootfs_evidence) is not _runtime_oci_rootfs.LayaRuntimeOciRootfsEvidence
            or type(self._supply_evidence)
            is not _runtime_supply_convergence.LayaRuntimeSupplyConvergenceEvidence
            or self._rootfs_evidence.plan.tar_evidence.plan.layer_evidence
            is not self._supply_evidence._layer_evidence
            or self._runtime_identity is not self._rootfs_evidence.runtime_identity
            or self._runtime_identity is not self._supply_evidence._runtime_identity
            or self.materialization_profile != MATERIALIZATION_PROFILE
            or self.rootfs_materialized is not False
            or self.runtime_materialized is not False
            or self.executor_available is not False
            or self.inference_executed is not False
        ):
            raise ValueError("rootfs materialization plan binding is invalid")

    __repr__ = _private_repr


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeRootfsMaterializationEvidence:
    schema_version: str
    _plan: LayaRuntimeRootfsMaterializationPlan = _field(repr=False)
    _content_manifest_sha256: str = _field(repr=False)
    _factory_token: _InitVar[object]
    materialization_profile: str = _field(default=MATERIALIZATION_PROFILE, init=False)
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
    runtime_materialized: bool = _field(default=False, init=False)
    executor_available: bool = _field(default=False, init=False)
    inference_executed: bool = _field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _EVIDENCE_TOKEN:
            raise ValueError("rootfs materialization evidence requires the factory seal token")
        if (
            self.schema_version != _EVIDENCE_SCHEMA
            or type(self._plan) is not LayaRuntimeRootfsMaterializationPlan
            or type(self._content_manifest_sha256) is not str
            or len(self._content_manifest_sha256) != 64
            or any(
                character not in "0123456789abcdef" for character in self._content_manifest_sha256
            )
            or self.materialization_profile != MATERIALIZATION_PROFILE
            or any(
                getattr(self, claim, None) is not expected
                for claim, expected in MATERIALIZATION_CLAIMS.items()
            )
        ):
            raise ValueError("rootfs materialization evidence binding is invalid")
        self._plan.__post_init__(_FACTORY_TOKEN)
        _validate_predecessor_claim_union(self._plan)

    __repr__ = _private_repr


def _validate_predecessor_claim_union(
    plan: LayaRuntimeRootfsMaterializationPlan,
) -> None:
    predecessors = (plan._rootfs_evidence, plan._supply_evidence)
    for claim, expected in MATERIALIZATION_CLAIMS.items():
        observed = tuple(
            getattr(predecessor, claim)
            for predecessor in predecessors
            if hasattr(predecessor, claim)
        )
        if not observed or any(type(value) is not bool for value in observed):
            raise ValueError("rootfs materialization predecessor claim is invalid")
        if claim == "rootfs_materialized":
            if expected is not True or any(observed):
                raise ValueError("rootfs materialization claim is not newly elevated")
        elif any(observed) is not expected:
            raise ValueError("rootfs materialization predecessor claim union is invalid")


def _revalidate_plan(value: object) -> LayaRuntimeRootfsMaterializationPlan:
    if type(value) is not LayaRuntimeRootfsMaterializationPlan:
        raise TypeError("rootfs materialization plan type is invalid")
    value.__post_init__(_FACTORY_TOKEN)
    rebuilt = prepare_laya_runtime_rootfs_materialization_plan(
        value._rootfs_evidence,
        value._supply_evidence,
    )
    if (
        rebuilt._rootfs_evidence is not value._rootfs_evidence
        or rebuilt._supply_evidence is not value._supply_evidence
        or rebuilt._runtime_identity is not value._runtime_identity
        or rebuilt.schema_version != value.schema_version
        or rebuilt.materialization_profile != value.materialization_profile
        or rebuilt.rootfs_materialized is not value.rootfs_materialized
        or rebuilt.runtime_materialized is not value.runtime_materialized
        or rebuilt.executor_available is not value.executor_available
        or rebuilt.inference_executed is not value.inference_executed
    ):
        raise ValueError("rootfs materialization plan revalidation failed")
    _validate_predecessor_claim_union(value)
    return value


def _register_issued_evidence(
    evidence: LayaRuntimeRootfsMaterializationEvidence,
    plan: LayaRuntimeRootfsMaterializationPlan,
    commitment: str,
) -> None:
    identity = id(evidence)
    record = None

    def cleanup(expired) -> None:
        retained_plan = None
        with _ISSUANCE_LOCK:
            current = _ISSUED_EVIDENCE.get(identity)
            if current is record and current.reference is expired:
                retained_plan = current.plan
                current.plan = None
                current.commitment = ""
                current.rootfs_evidence = None
                current.supply_evidence = None
                current.runtime_identity = None
                _ISSUED_EVIDENCE.pop(identity, None)
        del retained_plan

    reference = _weakref.ref(evidence, cleanup)
    record = _IssuedEvidenceRecord(reference, plan, commitment)
    with _ISSUANCE_LOCK:
        _ISSUED_EVIDENCE[identity] = record


def _require_issued_evidence(
    evidence: object,
) -> LayaRuntimeRootfsMaterializationEvidence:
    if type(evidence) is not LayaRuntimeRootfsMaterializationEvidence:
        raise TypeError("rootfs materialization evidence type is invalid")
    evidence.__post_init__(_EVIDENCE_TOKEN)
    with _ISSUANCE_LOCK:
        record = _ISSUED_EVIDENCE.get(id(evidence))
        if (
            record is None
            or record.reference() is not evidence
            or record.plan is not evidence._plan
            or record.commitment != evidence._content_manifest_sha256
            or record.rootfs_evidence is not evidence._plan._rootfs_evidence
            or record.supply_evidence is not evidence._plan._supply_evidence
            or record.runtime_identity is not evidence._plan._runtime_identity
        ):
            raise ValueError("rootfs materialization evidence lacks issued authority")
    _revalidate_plan(evidence._plan)
    with _ISSUANCE_LOCK:
        current = _ISSUED_EVIDENCE.get(id(evidence))
        if (
            current is not record
            or current.reference() is not evidence
            or current.plan is not evidence._plan
            or current.commitment != evidence._content_manifest_sha256
            or current.rootfs_evidence is not evidence._plan._rootfs_evidence
            or current.supply_evidence is not evidence._plan._supply_evidence
            or current.runtime_identity is not evidence._plan._runtime_identity
        ):
            raise ValueError("rootfs materialization evidence authority changed")
    return evidence


def _revoke_evidence(evidence: object) -> None:
    """Revoke one exact issued authority after owned filesystem disposal."""

    value = _require_issued_evidence(evidence)
    retained_plan = None
    with _ISSUANCE_LOCK:
        record = _ISSUED_EVIDENCE.get(id(value))
        if record is None or record.reference() is not value:
            raise ValueError("rootfs materialization evidence revocation is invalid")
        retained_plan = record.plan
        record.plan = None
        record.commitment = ""
        record.rootfs_evidence = None
        record.supply_evidence = None
        record.runtime_identity = None
        _ISSUED_EVIDENCE.pop(id(value), None)
    del retained_plan


def prepare_laya_runtime_rootfs_materialization_plan(
    rootfs_evidence: object,
    supply_evidence: object,
) -> LayaRuntimeRootfsMaterializationPlan:
    """Bind exact rootfs and issued supply authority without performing I/O."""

    result = None
    try:
        _runtime_oci_rootfs.canonical_laya_runtime_oci_rootfs_summary_bytes(rootfs_evidence)
        issued_supply = _runtime_supply_convergence._require_issued_evidence(supply_evidence)
        result = LayaRuntimeRootfsMaterializationPlan(
            schema_version=_PLAN_SCHEMA,
            _rootfs_evidence=rootfs_evidence,
            _supply_evidence=issued_supply,
            _runtime_identity=rootfs_evidence.runtime_identity,
            _factory_token=_FACTORY_TOKEN,
        )
        result.__post_init__(_FACTORY_TOKEN)
    except Exception:
        result = None
    if result is None:
        _raise_private("rootfs materialization predecessor validation failed")
    return result


def _seal_laya_runtime_rootfs_materialization_evidence(
    plan: object,
    content_manifest_sha256: object,
) -> LayaRuntimeRootfsMaterializationEvidence:
    """Issue authority only after the filesystem adapter completed verification."""

    result = None
    try:
        issued_plan = _revalidate_plan(plan)
        if (
            type(content_manifest_sha256) is not str
            or len(content_manifest_sha256) != 64
            or any(character not in "0123456789abcdef" for character in content_manifest_sha256)
        ):
            raise ValueError("rootfs materialization content commitment is invalid")
        result = LayaRuntimeRootfsMaterializationEvidence(
            schema_version=_EVIDENCE_SCHEMA,
            _plan=issued_plan,
            _content_manifest_sha256=content_manifest_sha256,
            _factory_token=_EVIDENCE_TOKEN,
        )
        _register_issued_evidence(result, issued_plan, content_manifest_sha256)
        _require_issued_evidence(result)
    except Exception:
        result = None
    if result is None:
        _raise_private("rootfs materialization evidence sealing failed")
    return result


def canonical_laya_runtime_rootfs_materialization_summary_bytes(
    evidence: object,
) -> bytes:
    """Render a public summary without filesystem or content identifiers."""

    result = None
    try:
        evidence = _require_issued_evidence(evidence)
        payload = {
            "schema_version": evidence.schema_version,
            "materialization_profile": evidence.materialization_profile,
            **MATERIALIZATION_CLAIMS,
        }
        result = _json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except Exception:
        result = None
    if result is None:
        _raise_private("rootfs materialization evidence validation failed")
    return result
