"""Pure authority boundary for one bounded synthetic Laya execution."""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
import threading as _threading
import weakref as _weakref
from dataclasses import InitVar as _InitVar
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from types import MappingProxyType as _MappingProxyType

from human_feedback import runtime_materialization as _runtime_materialization
from human_feedback.runtime_execution_observation import (
    validate_synthetic_probe_observation as _validate_synthetic_probe_observation,
)

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
_RECEIPT_TOKEN = object()
_EVIDENCE_TOKEN = object()
_ISSUANCE_LOCK = _threading.RLock()


class _ReceiptRecord:
    __slots__ = (
        "reference",
        "plan",
        "runtime_evidence",
        "materialization_plan",
        "image_id",
        "installation_sha256",
        "runtime_identity",
        "profile",
        "observation_sha256",
        "consumed",
    )

    def __init__(self, reference, receipt) -> None:
        self.reference = reference
        self.plan = receipt._plan
        self.runtime_evidence = receipt._runtime_evidence
        self.materialization_plan = receipt._materialization_plan
        self.image_id = receipt._image_id
        self.installation_sha256 = receipt._installation_sha256
        self.runtime_identity = receipt._runtime_identity
        self.profile = receipt._execution_profile
        self.observation_sha256 = receipt._observation_sha256
        self.consumed = False


class _IssuedPlanRecord:
    __slots__ = (
        "reference",
        "runtime_evidence",
        "materialization_plan",
        "image_id",
        "installation_sha256",
        "runtime_identity",
        "profile",
    )

    def __init__(self, reference, plan) -> None:
        self.reference = reference
        self.runtime_evidence = plan._runtime_evidence
        self.materialization_plan = plan._materialization_plan
        self.image_id = plan._image_id
        self.installation_sha256 = plan._installation_sha256
        self.runtime_identity = plan._runtime_identity
        self.profile = plan.execution_profile


class _IssuedEvidenceRecord:
    __slots__ = (
        "reference",
        "plan",
        "runtime_evidence",
        "materialization_plan",
        "image_id",
        "installation_sha256",
        "runtime_identity",
        "profile",
        "revoked",
    )

    def __init__(self, reference, evidence) -> None:
        plan = evidence._plan
        self.reference = reference
        self.plan = plan
        self.runtime_evidence = plan._runtime_evidence
        self.materialization_plan = plan._materialization_plan
        self.image_id = plan._image_id
        self.installation_sha256 = plan._installation_sha256
        self.runtime_identity = plan._runtime_identity
        self.profile = evidence.execution_profile
        self.revoked = False


_ISSUED_PLANS: dict[int, _IssuedPlanRecord] = {}
_ISSUED_RECEIPTS: dict[int, _ReceiptRecord] = {}
_ISSUED_EVIDENCE: dict[int, _IssuedEvidenceRecord] = {}


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


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
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
    with _ISSUANCE_LOCK:
        record = _ISSUED_PLANS.get(id(value))
        if not _plan_record_matches(record, value):
            raise ValueError("runtime execution plan lacks issued authority")
    value.__post_init__(_FACTORY_TOKEN)
    with _ISSUANCE_LOCK:
        current = _ISSUED_PLANS.get(id(value))
        if current is not record or not _plan_record_matches(current, value):
            raise ValueError("runtime execution plan authority changed")
    return value


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class _LayaRuntimeExecutionReceipt:
    _plan: LayaRuntimeExecutionPlan = _field(repr=False)
    _runtime_evidence: _runtime_materialization.LayaRuntimeMaterializationEvidence = _field(
        repr=False
    )
    _materialization_plan: _runtime_materialization.LayaRuntimeMaterializationPlan = _field(
        repr=False
    )
    _image_id: str = _field(repr=False)
    _installation_sha256: str = _field(repr=False)
    _runtime_identity: object = _field(repr=False)
    _execution_profile: str = _field(repr=False)
    _observation_sha256: str = _field(repr=False)
    _factory_token: _InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        valid = False
        try:
            plan = _revalidate_plan(self._plan)
            valid = (
                _factory_token is _RECEIPT_TOKEN
                and self._runtime_evidence is plan._runtime_evidence
                and self._materialization_plan is plan._materialization_plan
                and self._image_id == plan._image_id
                and self._installation_sha256 == plan._installation_sha256
                and self._runtime_identity is plan._runtime_identity
                and self._execution_profile == plan.execution_profile
                and type(self._observation_sha256) is str
                and len(self._observation_sha256) == 64
                and all(character in "0123456789abcdef" for character in self._observation_sha256)
            )
        except Exception:
            valid = False
        if not valid:
            _raise_private("runtime execution receipt binding is invalid")

    __repr__ = _private_repr


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeExecutionEvidence:
    schema_version: str
    _plan: LayaRuntimeExecutionPlan = _field(repr=False)
    _factory_token: _InitVar[object]
    execution_profile: str = _field(default=EXECUTION_PROFILE, init=False)
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
            or self.execution_profile != EXECUTION_PROFILE
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
        _register_issued_plan(result)
        _revalidate_plan(result)
    except Exception:
        result = None
    if result is None:
        _raise_private("runtime execution predecessor validation failed")
    return result


def _plan_record_matches(record: object, plan: LayaRuntimeExecutionPlan) -> bool:
    return (
        type(record) is _IssuedPlanRecord
        and record.reference() is plan
        and record.runtime_evidence is plan._runtime_evidence
        and record.materialization_plan is plan._materialization_plan
        and record.image_id == plan._image_id
        and record.installation_sha256 == plan._installation_sha256
        and record.runtime_identity is plan._runtime_identity
        and record.profile == plan.execution_profile
    )


def _register_issued_plan(plan: LayaRuntimeExecutionPlan) -> None:
    identity = id(plan)
    record = None

    def cleanup(expired) -> None:
        with _ISSUANCE_LOCK:
            current = _ISSUED_PLANS.get(identity)
            if current is not None and current is record and current.reference is expired:
                current.runtime_evidence = None
                current.materialization_plan = None
                current.image_id = ""
                current.installation_sha256 = ""
                current.runtime_identity = None
                current.profile = ""
                _ISSUED_PLANS.pop(identity, None)

    reference = _weakref.ref(plan, cleanup)
    record = _IssuedPlanRecord(reference, plan)
    with _ISSUANCE_LOCK:
        _ISSUED_PLANS[identity] = record


def _receipt_record_matches(record: object, receipt: _LayaRuntimeExecutionReceipt) -> bool:
    return (
        type(record) is _ReceiptRecord
        and record.reference() is receipt
        and record.plan is receipt._plan
        and record.runtime_evidence is receipt._runtime_evidence
        and record.materialization_plan is receipt._materialization_plan
        and record.image_id == receipt._image_id
        and record.installation_sha256 == receipt._installation_sha256
        and record.runtime_identity is receipt._runtime_identity
        and record.profile == receipt._execution_profile
        and record.observation_sha256 == receipt._observation_sha256
    )


def _evidence_record_matches(
    record: object,
    evidence: LayaRuntimeExecutionEvidence,
) -> bool:
    plan = evidence._plan
    return (
        type(record) is _IssuedEvidenceRecord
        and record.reference() is evidence
        and record.plan is plan
        and record.runtime_evidence is plan._runtime_evidence
        and record.materialization_plan is plan._materialization_plan
        and record.image_id == plan._image_id
        and record.installation_sha256 == plan._installation_sha256
        and record.runtime_identity is plan._runtime_identity
        and record.profile == evidence.execution_profile
    )


def _clear_receipt_record(record: _ReceiptRecord) -> None:
    record.plan = None
    record.runtime_evidence = None
    record.materialization_plan = None
    record.image_id = ""
    record.installation_sha256 = ""
    record.runtime_identity = None
    record.profile = ""
    record.observation_sha256 = ""


def _register_receipt(receipt: _LayaRuntimeExecutionReceipt) -> None:
    identity = id(receipt)
    record = None

    def cleanup(expired) -> None:
        with _ISSUANCE_LOCK:
            current = _ISSUED_RECEIPTS.get(identity)
            if current is not None and current is record and current.reference is expired:
                _clear_receipt_record(current)
                _ISSUED_RECEIPTS.pop(identity, None)

    reference = _weakref.ref(receipt, cleanup)
    record = _ReceiptRecord(reference, receipt)
    with _ISSUANCE_LOCK:
        _ISSUED_RECEIPTS[identity] = record


def _register_issued_evidence(evidence: LayaRuntimeExecutionEvidence) -> None:
    identity = id(evidence)
    record = None

    def cleanup(expired) -> None:
        retained_plan = None
        with _ISSUANCE_LOCK:
            current = _ISSUED_EVIDENCE.get(identity)
            if current is not None and current is record and current.reference is expired:
                retained_plan = current.plan
                current.plan = None
                current.runtime_evidence = None
                current.materialization_plan = None
                current.image_id = ""
                current.installation_sha256 = ""
                current.runtime_identity = None
                current.profile = ""
                _ISSUED_EVIDENCE.pop(identity, None)
        del retained_plan

    reference = _weakref.ref(evidence, cleanup)
    record = _IssuedEvidenceRecord(reference, evidence)
    with _ISSUANCE_LOCK:
        _ISSUED_EVIDENCE[identity] = record


def _issue_laya_runtime_execution_receipt(
    plan: object,
    canonical_observation: object,
) -> _LayaRuntimeExecutionReceipt:
    """Issue a private one-shot receipt for exact canonical probe bytes."""

    result = None
    try:
        issued_plan = _revalidate_plan(plan)
        if type(canonical_observation) is not bytes:
            raise TypeError("runtime execution observation type is invalid")
        canonical = _validate_synthetic_probe_observation(canonical_observation)
        if canonical != canonical_observation:
            raise ValueError("runtime execution observation is not canonical")
        observation_sha256 = _hashlib.sha256(canonical).hexdigest()
        result = _LayaRuntimeExecutionReceipt(
            _plan=issued_plan,
            _runtime_evidence=issued_plan._runtime_evidence,
            _materialization_plan=issued_plan._materialization_plan,
            _image_id=issued_plan._image_id,
            _installation_sha256=issued_plan._installation_sha256,
            _runtime_identity=issued_plan._runtime_identity,
            _execution_profile=issued_plan.execution_profile,
            _observation_sha256=observation_sha256,
            _factory_token=_RECEIPT_TOKEN,
        )
        _register_receipt(result)
    except Exception:
        result = None
    if result is None:
        _raise_private("runtime execution receipt issuance failed")
    return result


def _seal_laya_runtime_execution_evidence(
    plan: object,
    receipt: object,
) -> LayaRuntimeExecutionEvidence:
    """Consume one exact receipt and issue execution authority once."""

    result = None
    try:
        issued_plan = _revalidate_plan(plan)
        if type(receipt) is not _LayaRuntimeExecutionReceipt:
            raise TypeError("runtime execution receipt type is invalid")
        receipt.__post_init__(_RECEIPT_TOKEN)
        with _ISSUANCE_LOCK:
            record = _ISSUED_RECEIPTS.get(id(receipt))
            if (
                not _receipt_record_matches(record, receipt)
                or record.consumed
                or record.plan is not issued_plan
            ):
                raise ValueError("runtime execution receipt lacks issued authority")
            record.consumed = True
            _ISSUED_RECEIPTS.pop(id(receipt), None)
            _clear_receipt_record(record)
        issued_plan = _revalidate_plan(issued_plan)
        result = LayaRuntimeExecutionEvidence(
            schema_version=_EVIDENCE_SCHEMA,
            _plan=issued_plan,
            _factory_token=_EVIDENCE_TOKEN,
        )
        _register_issued_evidence(result)
        _require_issued_evidence(result)
    except Exception:
        result = None
    if result is None:
        _raise_private("runtime execution evidence sealing failed")
    return result


def _require_issued_evidence(value: object) -> LayaRuntimeExecutionEvidence:
    result = None
    try:
        if type(value) is not LayaRuntimeExecutionEvidence:
            raise TypeError("runtime execution evidence type is invalid")
        with _ISSUANCE_LOCK:
            record = _ISSUED_EVIDENCE.get(id(value))
            if not _evidence_record_matches(record, value) or record.revoked:
                raise ValueError("runtime execution evidence lacks issued authority")
        value.__post_init__(_EVIDENCE_TOKEN)
        with _ISSUANCE_LOCK:
            current = _ISSUED_EVIDENCE.get(id(value))
            if (
                current is not record
                or not _evidence_record_matches(current, value)
                or current.revoked
            ):
                raise ValueError("runtime execution evidence authority changed")
        result = value
    except Exception:
        result = None
    if result is None:
        _raise_private("runtime execution evidence validation failed")
    return result


def _revoke_evidence(value: object) -> None:
    """Idempotently revoke one exact issued execution authority."""

    valid = False
    try:
        if type(value) is not LayaRuntimeExecutionEvidence:
            raise TypeError("runtime execution evidence type is invalid")
        with _ISSUANCE_LOCK:
            record = _ISSUED_EVIDENCE.get(id(value))
            if not _evidence_record_matches(record, value):
                raise ValueError("runtime execution evidence revocation is invalid")
            record.revoked = True
            valid = True
    except Exception:
        valid = False
    if not valid:
        _raise_private("runtime execution evidence revocation failed")


def canonical_laya_runtime_execution_summary_bytes(evidence: object) -> bytes:
    """Render exact claims only for live adapter-issued execution evidence."""

    result = None
    try:
        issued = _require_issued_evidence(evidence)
        result = _json.dumps(
            {
                "schema_version": issued.schema_version,
                "execution_profile": issued.execution_profile,
                **EXECUTION_CLAIMS,
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except Exception:
        result = None
    if result is None:
        _raise_private("runtime execution evidence validation failed")
    return result
