"""Pure authority boundary for one offline materialized Laya runtime."""

from __future__ import annotations

import json as _json
import threading as _threading
import weakref as _weakref
from dataclasses import InitVar as _InitVar
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from types import MappingProxyType as _MappingProxyType

from human_feedback import runtime_checkpoint as _runtime_checkpoint
from human_feedback import runtime_rootfs_materialization as _runtime_rootfs_materialization

__all__ = (
    "LayaRuntimeMaterializationPlan",
    "LayaRuntimeMaterializationEvidence",
    "prepare_laya_runtime_materialization_plan",
    "canonical_laya_runtime_materialization_summary_bytes",
)

MATERIALIZATION_PROFILE = "docker-local-offline-cpu-v1"
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
        "runtime_materialized": True,
        "executor_available": False,
        "inference_executed": False,
    }
)

_PLAN_SCHEMA = "laya-runtime-materialization-plan-v1"
_EVIDENCE_SCHEMA = "laya-runtime-materialization-evidence-v1"
_FACTORY_TOKEN = object()
_EVIDENCE_TOKEN = object()
_ISSUANCE_LOCK = _threading.Lock()


class _IssuedEvidenceRecord:
    __slots__ = (
        "reference",
        "plan",
        "image_id",
        "installation_sha256",
        "profile",
        "rootfs_evidence",
        "checkpoint_evidence",
        "supply_evidence",
        "runtime_identity",
        "revoked",
    )

    def __init__(self, reference, evidence) -> None:
        self.reference = reference
        self.plan = evidence._plan
        self.image_id = evidence._image_id
        self.installation_sha256 = evidence._installation_sha256
        self.profile = evidence.materialization_profile
        self.rootfs_evidence = evidence._plan._rootfs_evidence
        self.checkpoint_evidence = evidence._plan._checkpoint_evidence
        self.supply_evidence = evidence._plan._supply_evidence
        self.runtime_identity = evidence._plan._runtime_identity
        self.revoked = False


_ISSUED_EVIDENCE: dict[int, _IssuedEvidenceRecord] = {}


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private runtime materialization value>"


def _raise_private(message: str) -> None:
    error = ValueError(message)
    error.__suppress_context__ = True
    raise error from None


def _valid_sha256(value: object, *, prefixed: bool) -> bool:
    if type(value) is not str:
        return False
    digest = value.removeprefix("sha256:") if prefixed else value
    return (
        (not prefixed or value.startswith("sha256:"))
        and len(digest) == 64
        and digest != "0" * 64
        and all(character in "0123456789abcdef" for character in digest)
    )


def _same_runtime_identity(left: object, right: object) -> bool:
    try:
        return (
            type(left.schema_version) is str
            and left.schema_version == right.schema_version
            and type(left.sha256) is str
            and left.sha256 == right.sha256
        )
    except Exception:
        return False


def _supply_from_rootfs(rootfs_evidence: object) -> object:
    return rootfs_evidence._plan._supply_evidence


def _checkpoint_from_supply(supply_evidence: object) -> object:
    return supply_evidence._provenance_evidence.checkpoint_evidence


def _validate_predecessor_claims(rootfs_evidence: object) -> None:
    predecessor_claims = _runtime_rootfs_materialization.MATERIALIZATION_CLAIMS
    if set(predecessor_claims) != set(MATERIALIZATION_CLAIMS):
        raise ValueError("runtime materialization predecessor claim matrix is invalid")
    for claim, expected in MATERIALIZATION_CLAIMS.items():
        observed = getattr(rootfs_evidence, claim, None)
        if type(observed) is not bool:
            raise ValueError("runtime materialization predecessor claim is invalid")
        if claim == "runtime_materialized":
            if observed is not False or expected is not True:
                raise ValueError("runtime materialization claim is not newly elevated")
        elif observed is not expected:
            raise ValueError("runtime materialization predecessor claim changed")


def _validate_predecessors(rootfs_evidence: object, checkpoint_evidence: object):
    if (
        type(rootfs_evidence)
        is not _runtime_rootfs_materialization.LayaRuntimeRootfsMaterializationEvidence
        or type(checkpoint_evidence) is not _runtime_checkpoint.LayaRuntimeCheckpointEvidence
    ):
        raise TypeError("runtime materialization predecessor type is invalid")

    _runtime_rootfs_materialization.canonical_laya_runtime_rootfs_materialization_summary_bytes(
        rootfs_evidence
    )
    _runtime_checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(checkpoint_evidence)

    supply_evidence = _supply_from_rootfs(rootfs_evidence)
    expected_checkpoint = _checkpoint_from_supply(supply_evidence)
    runtime_identity = rootfs_evidence._plan._runtime_identity
    if (
        checkpoint_evidence is not expected_checkpoint
        or rootfs_evidence._plan._rootfs_evidence.runtime_identity is not runtime_identity
        or supply_evidence._runtime_identity is not runtime_identity
        or not _same_runtime_identity(runtime_identity, checkpoint_evidence.runtime_identity)
    ):
        raise ValueError("runtime materialization predecessor binding is invalid")
    _validate_predecessor_claims(rootfs_evidence)
    return supply_evidence, runtime_identity


@_dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeMaterializationPlan:
    schema_version: str
    _rootfs_evidence: _runtime_rootfs_materialization.LayaRuntimeRootfsMaterializationEvidence = (
        _field(repr=False)
    )
    _checkpoint_evidence: _runtime_checkpoint.LayaRuntimeCheckpointEvidence = _field(repr=False)
    _supply_evidence: object = _field(repr=False)
    _runtime_identity: object = _field(repr=False)
    _factory_token: _InitVar[object]
    materialization_profile: str = _field(default=MATERIALIZATION_PROFILE, init=False)
    runtime_materialized: bool = _field(default=False, init=False)
    executor_available: bool = _field(default=False, init=False)
    inference_executed: bool = _field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        try:
            valid = (
                _factory_token is _FACTORY_TOKEN
                and self.schema_version == _PLAN_SCHEMA
                and type(self._rootfs_evidence)
                is _runtime_rootfs_materialization.LayaRuntimeRootfsMaterializationEvidence
                and type(self._checkpoint_evidence)
                is _runtime_checkpoint.LayaRuntimeCheckpointEvidence
                and self._supply_evidence is _supply_from_rootfs(self._rootfs_evidence)
                and self._checkpoint_evidence is _checkpoint_from_supply(self._supply_evidence)
                and self._runtime_identity is self._rootfs_evidence._plan._runtime_identity
                and _same_runtime_identity(
                    self._runtime_identity, self._checkpoint_evidence.runtime_identity
                )
                and self.materialization_profile == MATERIALIZATION_PROFILE
                and self.runtime_materialized is False
                and self.executor_available is False
                and self.inference_executed is False
            )
        except Exception:
            valid = False
        if not valid:
            raise ValueError("runtime materialization plan binding is invalid")

    __repr__ = _private_repr


def _revalidate_plan(value: object) -> LayaRuntimeMaterializationPlan:
    if type(value) is not LayaRuntimeMaterializationPlan:
        raise TypeError("runtime materialization plan type is invalid")
    value.__post_init__(_FACTORY_TOKEN)
    supply_evidence, runtime_identity = _validate_predecessors(
        value._rootfs_evidence, value._checkpoint_evidence
    )
    if (
        supply_evidence is not value._supply_evidence
        or runtime_identity is not value._runtime_identity
    ):
        raise ValueError("runtime materialization plan revalidation failed")
    return value


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeMaterializationEvidence:
    schema_version: str
    _plan: LayaRuntimeMaterializationPlan = _field(repr=False)
    _image_id: str = _field(repr=False)
    _installation_sha256: str = _field(repr=False)
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
    runtime_materialized: bool = _field(default=True, init=False)
    executor_available: bool = _field(default=False, init=False)
    inference_executed: bool = _field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if (
            _factory_token is not _EVIDENCE_TOKEN
            or self.schema_version != _EVIDENCE_SCHEMA
            or type(self._plan) is not LayaRuntimeMaterializationPlan
            or not _valid_sha256(self._image_id, prefixed=True)
            or not _valid_sha256(self._installation_sha256, prefixed=False)
            or self.materialization_profile != MATERIALIZATION_PROFILE
            or any(
                getattr(self, claim, None) is not expected
                for claim, expected in MATERIALIZATION_CLAIMS.items()
            )
        ):
            raise ValueError("runtime materialization evidence binding is invalid")
        _revalidate_plan(self._plan)

    __repr__ = _private_repr


def prepare_laya_runtime_materialization_plan(
    rootfs_evidence: object,
    checkpoint_evidence: object,
) -> LayaRuntimeMaterializationPlan:
    """Bind exact live issued rootfs and checkpoint authorities without performing I/O."""

    result = None
    try:
        supply_evidence, runtime_identity = _validate_predecessors(
            rootfs_evidence, checkpoint_evidence
        )
        result = LayaRuntimeMaterializationPlan(
            schema_version=_PLAN_SCHEMA,
            _rootfs_evidence=rootfs_evidence,
            _checkpoint_evidence=checkpoint_evidence,
            _supply_evidence=supply_evidence,
            _runtime_identity=runtime_identity,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        result = None
    if result is None:
        _raise_private("runtime materialization predecessor validation failed")
    return result


def _record_matches(
    record: object,
    evidence: LayaRuntimeMaterializationEvidence,
) -> bool:
    return (
        type(record) is _IssuedEvidenceRecord
        and record.reference() is evidence
        and record.plan is evidence._plan
        and record.image_id == evidence._image_id
        and record.installation_sha256 == evidence._installation_sha256
        and record.profile == evidence.materialization_profile
        and record.rootfs_evidence is evidence._plan._rootfs_evidence
        and record.checkpoint_evidence is evidence._plan._checkpoint_evidence
        and record.supply_evidence is evidence._plan._supply_evidence
        and record.runtime_identity is evidence._plan._runtime_identity
    )


def _register_issued_evidence(evidence: LayaRuntimeMaterializationEvidence) -> None:
    identity = id(evidence)
    record = None

    def cleanup(expired) -> None:
        retained_plan = None
        with _ISSUANCE_LOCK:
            current = _ISSUED_EVIDENCE.get(identity)
            if current is record and current.reference is expired:
                retained_plan = current.plan
                current.plan = None
                current.image_id = ""
                current.installation_sha256 = ""
                current.profile = ""
                current.rootfs_evidence = None
                current.checkpoint_evidence = None
                current.supply_evidence = None
                current.runtime_identity = None
                _ISSUED_EVIDENCE.pop(identity, None)
        del retained_plan

    reference = _weakref.ref(evidence, cleanup)
    record = _IssuedEvidenceRecord(reference, evidence)
    with _ISSUANCE_LOCK:
        _ISSUED_EVIDENCE[identity] = record


def _seal_laya_runtime_materialization_evidence(
    plan: object,
    image_id: object,
    installation_sha256: object,
) -> LayaRuntimeMaterializationEvidence:
    """Issue authority only after the adapter completed assembly and its closed probe."""

    result = None
    try:
        issued_plan = _revalidate_plan(plan)
        if not _valid_sha256(image_id, prefixed=True) or not _valid_sha256(
            installation_sha256, prefixed=False
        ):
            raise ValueError("runtime materialization commitment is invalid")
        result = LayaRuntimeMaterializationEvidence(
            schema_version=_EVIDENCE_SCHEMA,
            _plan=issued_plan,
            _image_id=image_id,
            _installation_sha256=installation_sha256,
            _factory_token=_EVIDENCE_TOKEN,
        )
        _register_issued_evidence(result)
        _require_issued_evidence(result)
    except Exception:
        result = None
    if result is None:
        _raise_private("runtime materialization evidence sealing failed")
    return result


def _require_issued_evidence(value: object) -> LayaRuntimeMaterializationEvidence:
    if type(value) is not LayaRuntimeMaterializationEvidence:
        raise TypeError("runtime materialization evidence type is invalid")
    with _ISSUANCE_LOCK:
        record = _ISSUED_EVIDENCE.get(id(value))
        if not _record_matches(record, value) or record.revoked:
            raise ValueError("runtime materialization evidence lacks issued authority")
    value.__post_init__(_EVIDENCE_TOKEN)
    with _ISSUANCE_LOCK:
        current = _ISSUED_EVIDENCE.get(id(value))
        if current is not record or not _record_matches(current, value) or current.revoked:
            raise ValueError("runtime materialization evidence authority changed")
    return value


def _revoke_evidence(value: object) -> None:
    """Idempotently revoke one issued runtime without revalidating disposed parents."""

    try:
        if type(value) is not LayaRuntimeMaterializationEvidence:
            raise TypeError("runtime materialization evidence type is invalid")
        with _ISSUANCE_LOCK:
            record = _ISSUED_EVIDENCE.get(id(value))
            if not _record_matches(record, value):
                raise ValueError("runtime materialization evidence revocation is invalid")
            if record.revoked:
                return
            record.revoked = True
    except Exception:
        _raise_private("runtime materialization evidence revocation failed")


def canonical_laya_runtime_materialization_summary_bytes(evidence: object) -> bytes:
    """Render a privacy-safe summary for adapter-issued runtime evidence."""

    result = None
    try:
        evidence = _require_issued_evidence(evidence)
        result = _json.dumps(
            {
                "schema_version": evidence.schema_version,
                "materialization_profile": evidence.materialization_profile,
                **MATERIALIZATION_CLAIMS,
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except Exception:
        result = None
    if result is None:
        _raise_private("runtime materialization evidence validation failed")
    return result
