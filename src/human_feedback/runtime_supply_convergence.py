"""Pure convergence proof for independently issued Laya runtime supply evidence."""

from __future__ import annotations

import json as _json
import threading as _threading
import weakref as _weakref
from dataclasses import InitVar as _InitVar
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from human_feedback import runtime_base_ancestry as _runtime_base_ancestry
from human_feedback import runtime_bundle as _runtime_bundle
from human_feedback import runtime_oci_layers as _runtime_oci_layers
from human_feedback import runtime_provenance as _runtime_provenance

__all__ = (
    "LayaRuntimeSupplyConvergenceEvidence",
    "verify_laya_runtime_supply_convergence",
    "canonical_laya_runtime_supply_convergence_summary_bytes",
)

_EVIDENCE_SCHEMA = "laya-runtime-supply-convergence-evidence-v1"
_FACTORY_TOKEN = object()

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
    "runtime_config_semantics_verified",
    "checkpoint_manifest_semantics_verified",
    "checkpoint_bytes_verified",
    "provenance_objects_verified",
    "source_git_content_verified",
    "checkpoint_git_content_verified",
    "source_license_declaration_observed",
    "checkpoint_license_declaration_observed",
    "runtime_supply_content_convergence_verified",
)
_FALSE_CLAIMS = (
    "lock_verified",
    "sbom_verified",
    "lock_sbom_consistent",
    "oci_rootfs_verified",
    "tar_semantics_verified",
    "origin_verified",
    "license_verified",
    "runtime_build_recipe_verified",
    "build_process_attested",
    "reproducible_build_verified",
    "rootfs_materialized",
    "runtime_materialized",
    "executor_available",
    "inference_executed",
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
    __slots__ = ("reference", "semantics")

    def __init__(
        self,
        reference: _weakref.ReferenceType[object],
        semantics: tuple[object, ...],
    ) -> None:
        self.reference = reference
        self.semantics = semantics


_ISSUED_EVIDENCE: dict[int, _IssuedRecord] = {}
_ISSUANCE_LOCK = _threading.Lock()


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private supply convergence value>"


def _raise_private(message: str) -> None:
    error = ValueError(message)
    error.__suppress_context__ = True
    raise error from None


def _mirror_semantics(value: object) -> object:
    if type(value) is _IdentitySeal:
        return _IdentitySeal(value.value)
    if type(value) is tuple:
        return tuple(_mirror_semantics(item) for item in value)
    return value


def _register_issued(value: object, semantics: tuple[object, ...]) -> None:
    object.__setattr__(value, "_factory_capability", _FACTORY_TOKEN)
    object.__setattr__(value, "_semantic_capability", _mirror_semantics(semantics))
    identity = id(value)
    record: _IssuedRecord | None = None

    def cleanup(expired: _weakref.ReferenceType[object]) -> None:
        retained_semantics: tuple[object, ...] = ()
        with _ISSUANCE_LOCK:
            if record is not None:
                retained_semantics = record.semantics
                record.semantics = ()
            current = _ISSUED_EVIDENCE.get(identity)
            if current is record and current.reference is expired:
                _ISSUED_EVIDENCE.pop(identity, None)
        del retained_semantics

    reference = _weakref.ref(value, cleanup)
    record = _IssuedRecord(reference, semantics)
    with _ISSUANCE_LOCK:
        _ISSUED_EVIDENCE[identity] = record


def _require_record(value: object, semantics: tuple[object, ...]) -> None:
    with _ISSUANCE_LOCK:
        record = _ISSUED_EVIDENCE.get(id(value))
        if (
            type(value) is not LayaRuntimeSupplyConvergenceEvidence
            or getattr(value, "_factory_capability", None) is not _FACTORY_TOKEN
            or record is None
            or record.reference() is not value
            or record.semantics != semantics
        ):
            raise ValueError("supply convergence evidence lacks issued authority")


@_dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeSupplyConvergenceEvidence(_FactorySealed):
    schema_version: str
    _layer_evidence: _runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence = _field(repr=False)
    _provenance_evidence: _runtime_provenance.LayaRuntimeProvenanceEvidence = _field(repr=False)
    _base_ancestry_evidence: _runtime_base_ancestry.LayaRuntimeBaseAncestryEvidence = _field(
        repr=False
    )
    _runtime_identity: object = _field(repr=False)
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
    lock_verified: bool = _field(default=False, init=False)
    sbom_verified: bool = _field(default=False, init=False)
    lock_sbom_consistent: bool = _field(default=False, init=False)
    oci_rootfs_verified: bool = _field(default=False, init=False)
    tar_semantics_verified: bool = _field(default=False, init=False)
    origin_verified: bool = _field(default=False, init=False)
    license_verified: bool = _field(default=False, init=False)
    runtime_build_recipe_verified: bool = _field(default=False, init=False)
    build_process_attested: bool = _field(default=False, init=False)
    reproducible_build_verified: bool = _field(default=False, init=False)
    rootfs_materialized: bool = _field(default=False, init=False)
    runtime_materialized: bool = _field(default=False, init=False)
    executor_available: bool = _field(default=False, init=False)
    inference_executed: bool = _field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("supply convergence evidence requires the factory seal token")
        _validate_evidence_shape(self)

    __repr__ = _private_repr


def _snapshot_from_layer_evidence(layer_evidence: object) -> object:
    return layer_evidence.layout_evidence.plan.oci_evidence.snapshot


def _snapshot_from_provenance_evidence(provenance_evidence: object) -> object:
    return provenance_evidence.checkpoint_evidence.deployment_evidence.snapshot


def _rebuild_snapshot(snapshot: object) -> object:
    artifacts = snapshot.artifacts
    if type(artifacts) is not tuple or len(artifacts) != 5:
        raise ValueError("supply snapshot artifact cardinality is invalid")
    payload_by_path = {artifact.spec.path: artifact.content for artifact in artifacts}
    if len(payload_by_path) != 5:
        raise ValueError("supply snapshot artifact paths are invalid")
    rebuilt = _runtime_bundle.verify_laya_runtime_artifact_bytes(snapshot.manifest, payload_by_path)
    if rebuilt != snapshot:
        raise ValueError("supply snapshot reconstruction is invalid")
    return rebuilt


def _validate_cardinalities(
    layer_evidence: object,
    provenance_evidence: object,
    base_ancestry_evidence: object,
) -> None:
    if (
        type(layer_evidence.plan.layer_blobs) is not tuple
        or len(layer_evidence.plan.layer_blobs) != 10
        or type(layer_evidence.plan.declared_diff_ids) is not tuple
        or len(layer_evidence.plan.declared_diff_ids) != 10
        or type(provenance_evidence.checkpoint_evidence.plan.files) is not tuple
        or len(provenance_evidence.checkpoint_evidence.plan.files) != 5
        or type(provenance_evidence.plan.objects) is not tuple
        or len(provenance_evidence.plan.objects) != 16
        or type(provenance_evidence.receipts) is not tuple
        or len(provenance_evidence.receipts) != 16
        or type(base_ancestry_evidence.plan.compressed_layer_prefix) is not tuple
        or len(base_ancestry_evidence.plan.compressed_layer_prefix) != 4
        or type(base_ancestry_evidence.plan.diff_id_prefix) is not tuple
        or len(base_ancestry_evidence.plan.diff_id_prefix) != 4
    ):
        raise ValueError("supply predecessor cardinality is invalid")


def _validate_predecessors(
    layer_evidence: object,
    provenance_evidence: object,
    base_ancestry_evidence: object,
) -> tuple[object, object, object, object]:
    if type(layer_evidence) is not _runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence:
        raise TypeError("layer evidence must be an exact issued value")
    if type(provenance_evidence) is not _runtime_provenance.LayaRuntimeProvenanceEvidence:
        raise TypeError("provenance evidence must be an exact issued value")
    if type(base_ancestry_evidence) is not _runtime_base_ancestry.LayaRuntimeBaseAncestryEvidence:
        raise TypeError("base ancestry evidence must be an exact issued value")

    _runtime_oci_layers.canonical_laya_runtime_oci_layer_diff_ids_summary_bytes(layer_evidence)
    _runtime_provenance.canonical_laya_runtime_provenance_summary_bytes(provenance_evidence)
    _runtime_base_ancestry.canonical_laya_runtime_base_ancestry_summary_bytes(
        base_ancestry_evidence
    )

    if base_ancestry_evidence.layer_evidence is not layer_evidence:
        raise ValueError("base ancestry to layer evidence identity binding is invalid")
    if (
        base_ancestry_evidence.runtime_identity is not layer_evidence.runtime_identity
        or layer_evidence.runtime_identity.schema_version
        != provenance_evidence.runtime_identity.schema_version
        or layer_evidence.runtime_identity.sha256 != provenance_evidence.runtime_identity.sha256
    ):
        raise ValueError("supply runtime identity binding is invalid")

    _validate_cardinalities(layer_evidence, provenance_evidence, base_ancestry_evidence)
    left = _rebuild_snapshot(_snapshot_from_layer_evidence(layer_evidence))
    right = _rebuild_snapshot(_snapshot_from_provenance_evidence(provenance_evidence))
    if (
        left != right
        or left.manifest != right.manifest
        or left.runtime_identity != right.runtime_identity
        or tuple(artifact.spec for artifact in left.artifacts)
        != tuple(artifact.spec for artifact in right.artifacts)
        or tuple(artifact.content for artifact in left.artifacts)
        != tuple(artifact.content for artifact in right.artifacts)
    ):
        raise ValueError("supply snapshot content convergence is invalid")
    return (
        layer_evidence,
        provenance_evidence,
        base_ancestry_evidence,
        layer_evidence.runtime_identity,
    )


def _evidence_semantics(
    evidence: LayaRuntimeSupplyConvergenceEvidence,
) -> tuple[object, ...]:
    return (
        evidence.schema_version,
        _IdentitySeal(evidence._layer_evidence),
        _IdentitySeal(evidence._provenance_evidence),
        _IdentitySeal(evidence._base_ancestry_evidence),
        _IdentitySeal(evidence._runtime_identity),
        tuple(getattr(evidence, claim) for claim in _TRUE_CLAIMS + _FALSE_CLAIMS),
    )


def _validate_evidence_shape(value: object) -> LayaRuntimeSupplyConvergenceEvidence:
    if type(value) is not LayaRuntimeSupplyConvergenceEvidence:
        raise TypeError("supply convergence evidence type is invalid")
    if (
        value.schema_version != _EVIDENCE_SCHEMA
        or any(getattr(value, claim, None) is not True for claim in _TRUE_CLAIMS)
        or any(getattr(value, claim, None) is not False for claim in _FALSE_CLAIMS)
    ):
        raise ValueError("supply convergence evidence claim is invalid")
    return value


def _require_issued_evidence(value: object) -> LayaRuntimeSupplyConvergenceEvidence:
    evidence = _validate_evidence_shape(value)
    semantics = _evidence_semantics(evidence)
    _require_record(evidence, semantics)
    return evidence


def verify_laya_runtime_supply_convergence(
    layer_evidence,
    provenance_evidence,
    base_ancestry_evidence,
):
    """Verify immutable content convergence across the PR22/PR35/PR36 graph."""

    failed = False
    result = None
    try:
        layer, provenance, base, runtime_identity = _validate_predecessors(
            layer_evidence, provenance_evidence, base_ancestry_evidence
        )
        _runtime_oci_layers.canonical_laya_runtime_oci_layer_diff_ids_summary_bytes(layer)
        _runtime_provenance.canonical_laya_runtime_provenance_summary_bytes(provenance)
        _runtime_base_ancestry.canonical_laya_runtime_base_ancestry_summary_bytes(base)
        evidence = LayaRuntimeSupplyConvergenceEvidence(
            schema_version=_EVIDENCE_SCHEMA,
            _layer_evidence=layer,
            _provenance_evidence=provenance,
            _base_ancestry_evidence=base,
            _runtime_identity=runtime_identity,
            _factory_token=_FACTORY_TOKEN,
        )
        _register_issued(evidence, _evidence_semantics(evidence))
        result = evidence
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("supply convergence predecessor evidence validation failed")
    return result


def canonical_laya_runtime_supply_convergence_summary_bytes(evidence):
    """Return the exact privacy-safe claim allowlist after deep revalidation."""

    failed = False
    result = None
    try:
        value = _require_issued_evidence(evidence)
        layer, provenance, base, runtime_identity = _validate_predecessors(
            value._layer_evidence,
            value._provenance_evidence,
            value._base_ancestry_evidence,
        )
        _require_issued_evidence(value)
        if value._runtime_identity is not runtime_identity:
            raise ValueError("supply convergence runtime identity is invalid")
        payload = {
            "schema_version": value.schema_version,
            "layer_evidence_schema_version": layer.schema_version,
            "provenance_evidence_schema_version": provenance.schema_version,
            "base_ancestry_evidence_schema_version": base.schema_version,
            "runtime_identity_schema_version": runtime_identity.schema_version,
            "runtime_identity_sha256": runtime_identity.sha256,
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
        _raise_private("supply convergence evidence validation failed")
    return result
