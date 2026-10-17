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
        "tar_semantics_verified": True,
        "oci_rootfs_verified": True,
        "rootfs_materialized": True,
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
    __slots__ = ("reference", "plan", "commitment")

    def __init__(self, reference, plan, commitment: str) -> None:
        self.reference = reference
        self.plan = plan
        self.commitment = commitment


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
    tar_semantics_verified: bool = _field(default=True, init=False)
    oci_rootfs_verified: bool = _field(default=True, init=False)
    rootfs_materialized: bool = _field(default=True, init=False)
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

    __repr__ = _private_repr


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
        ):
            raise ValueError("rootfs materialization evidence authority changed")
    return evidence


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
