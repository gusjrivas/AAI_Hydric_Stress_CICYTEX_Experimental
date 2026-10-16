"""Pure bounded verification of the five declared Laya checkpoint files."""

from __future__ import annotations

import hashlib
import json
import weakref
from dataclasses import InitVar, dataclass, field, fields, is_dataclass

from . import runtime_bundle, runtime_deployment_metadata

CHECKPOINT_PLAN_SCHEMA = "laya-runtime-checkpoint-plan-v1"
CHECKPOINT_EVIDENCE_SCHEMA = "laya-runtime-checkpoint-evidence-v1"
MAX_CHECKPOINT_FILE_BYTES = 700 * 1024 * 1024
MAX_CHECKPOINT_TOTAL_BYTES = 768 * 1024 * 1024
MAX_CHECKPOINT_CHUNK_BYTES = 1024 * 1024
MAX_CHECKPOINT_CHUNKS = 1024
MAX_SEMANTIC_SNAPSHOT_NODES = 2048
MAX_SEMANTIC_CONTAINER_ITEMS = 2048
MAX_SEMANTIC_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_SEMANTIC_SNAPSHOT_DEPTH = 64

_FACTORY_TOKEN = object()
_ITERATOR_EOF = object()
_LFS_SIGNATURE = b"version https://git-lfs.github.com/spec/v1"
_TRUE_FLAGS = (
    "artifact_integrity_verified",
    "runtime_config_semantics_verified",
    "checkpoint_manifest_semantics_verified",
)
_FALSE_FLAGS = (
    "lock_verified",
    "sbom_verified",
    "lock_sbom_consistent",
    "oci_bytes_verified",
    "oci_manifest_semantics_verified",
    "runtime_materialized",
    "origin_verified",
    "executor_available",
    "inference_executed",
)


class _FactorySealed:
    __slots__ = ("_factory_capability", "_semantic_capability")


class _IssuedRecord:
    __slots__ = ("reference", "semantics")

    def __init__(
        self,
        reference: weakref.ReferenceType[object],
        semantics: tuple[object, ...],
    ) -> None:
        self.reference = reference
        self.semantics = semantics


def _caller_semantic_mirror(value: object) -> object:
    if type(value) is _IdentitySeal:
        return _IdentitySeal(value.value)
    if type(value) is tuple:
        return tuple(_caller_semantic_mirror(item) for item in value)
    if type(value) is list:
        return [_caller_semantic_mirror(item) for item in value]
    if type(value) is dict:
        return {key: _caller_semantic_mirror(item) for key, item in value.items()}
    return value


_ISSUED_PLANS: dict[int, _IssuedRecord] = {}
_ISSUED_RECEIPTS: dict[int, _IssuedRecord] = {}
_ISSUED_AUTHORITIES: dict[int, _IssuedRecord] = {}
_ISSUED_EVIDENCE: dict[int, _IssuedRecord] = {}


def _has_factory_capability(value: object) -> bool:
    return getattr(value, "_factory_capability", None) is _FACTORY_TOKEN


def _register_issued(
    value: object,
    registry: dict[int, _IssuedRecord],
    semantics: tuple[object, ...],
) -> None:
    # Compatibility mirror only; module-side records remain authoritative.
    object.__setattr__(value, "_semantic_capability", _caller_semantic_mirror(semantics))
    object.__setattr__(value, "_factory_capability", _FACTORY_TOKEN)
    identity = id(value)

    def cleanup(expired: weakref.ReferenceType[object]) -> None:
        record = registry.get(identity)
        if record is not None and record.reference is expired:
            registry.pop(identity, None)

    reference = weakref.ref(value, cleanup)
    registry[identity] = _IssuedRecord(reference, semantics)


def _requires_issued(
    value: object,
    expected_type: type,
    registry: dict[int, _IssuedRecord],
    semantics: tuple[object, ...],
    message: str,
) -> None:
    record = registry.get(id(value))
    if (
        type(value) is not expected_type
        or not _has_factory_capability(value)
        or record is None
        or record.reference() is not value
        or record.semantics != semantics
    ):
        raise ValueError(message)


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private checkpoint value>"


def _raise_private(message: str) -> None:
    error = ValueError(message)
    error.__suppress_context__ = True
    raise error


def _valid_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
        and value != "0" * 64
    )


class _IdentitySeal:
    __slots__ = ("value",)

    def __init__(self, value: object) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return type(other) is _IdentitySeal and self.value is other.value

    __repr__ = _private_repr


def _consume_semantic_bytes(size: int, budget: list[int]) -> None:
    if type(size) is not int or size < 0 or size > budget[0]:
        raise ValueError("checkpoint semantic bytes exceed the aggregate budget")
    budget[0] -= size


def _deep_semantic_snapshot(
    value: object,
    *,
    _active: set[int] | None = None,
    _budget: list[int] | None = None,
    _byte_limit: int = MAX_SEMANTIC_SNAPSHOT_BYTES,
    _byte_budget: list[int] | None = None,
    _depth: int = 0,
    _leaf_limit: int = MAX_SEMANTIC_SNAPSHOT_BYTES,
) -> tuple[object, ...]:
    """Freeze a bounded, identity-sealed view of the issued deployment graph."""

    if type(_depth) is not int or not 0 <= _depth <= MAX_SEMANTIC_SNAPSHOT_DEPTH:
        raise ValueError("checkpoint semantic graph exceeds the depth budget")
    if type(_byte_limit) is not int or _byte_limit < 0:
        raise ValueError("checkpoint semantic byte budget is invalid")
    active = set() if _active is None else _active
    budget = [MAX_SEMANTIC_SNAPSHOT_NODES] if _budget is None else _budget
    byte_budget = [_byte_limit] if _byte_budget is None else _byte_budget
    budget[0] -= 1
    if budget[0] < 0:
        raise ValueError("checkpoint semantic graph exceeds the validation budget")
    if value is None:
        return ("none",)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    if type(value) is float:
        return ("float", value.hex())
    if type(value) is str:
        if len(value) > byte_budget[0]:
            raise ValueError("checkpoint semantic text exceeds the aggregate budget")
        encoded_size = len(value.encode("utf-8"))
        _consume_semantic_bytes(encoded_size, byte_budget)
        return ("str", value)
    if type(value) is bytes:
        size = len(value)
        if type(_leaf_limit) is not int or not 0 <= size <= _leaf_limit:
            raise ValueError("checkpoint semantic byte leaf exceeds its budget")
        _consume_semantic_bytes(size, byte_budget)
        return (
            "bytes",
            _IdentitySeal(value),
            size,
            hashlib.new("sha256", value).hexdigest(),
        )

    identity = id(value)
    if identity in active:
        raise ValueError("checkpoint semantic graph contains a cycle")
    active.add(identity)
    try:
        if type(value) in {tuple, list}:
            if len(value) > MAX_SEMANTIC_CONTAINER_ITEMS:
                raise ValueError("checkpoint semantic sequence exceeds the validation budget")
            return (
                type(value).__name__,
                _IdentitySeal(value),
                tuple(
                    _deep_semantic_snapshot(
                        item,
                        _active=active,
                        _budget=budget,
                        _byte_limit=_byte_limit,
                        _byte_budget=byte_budget,
                        _depth=_depth + 1,
                    )
                    for item in value
                ),
            )
        if type(value) is dict:
            if len(value) > MAX_SEMANTIC_CONTAINER_ITEMS:
                raise ValueError("checkpoint semantic mapping exceeds the validation budget")
            if any(type(key) is not str for key in value):
                raise ValueError("checkpoint semantic mapping key is invalid")
            for key in value:
                if len(key) > byte_budget[0]:
                    raise ValueError("checkpoint mapping key exceeds the aggregate budget")
                encoded_key = key.encode("utf-8")
                _consume_semantic_bytes(len(encoded_key), byte_budget)
            return (
                "dict",
                _IdentitySeal(value),
                tuple(
                    (
                        key,
                        _deep_semantic_snapshot(
                            value[key],
                            _active=active,
                            _budget=budget,
                            _byte_limit=_byte_limit,
                            _byte_budget=byte_budget,
                            _depth=_depth + 1,
                        ),
                    )
                    for key in sorted(value)
                ),
            )
        if is_dataclass(value) and not isinstance(value, type):
            declared_content_size = None
            if hasattr(value, "content") and hasattr(value, "spec"):
                spec = getattr(value, "spec")
                declared_content_size = getattr(spec, "size_bytes", None)
                content = getattr(value, "content")
                if (
                    type(content) is not bytes
                    or type(declared_content_size) is not int
                    or not 0 <= declared_content_size <= MAX_SEMANTIC_SNAPSHOT_BYTES
                    or len(content) != declared_content_size
                ):
                    raise ValueError("checkpoint artifact content exceeds its declared budget")
            return (
                "dataclass",
                _IdentitySeal(value),
                type(value).__module__,
                type(value).__qualname__,
                tuple(
                    (
                        item.name,
                        _deep_semantic_snapshot(
                            getattr(value, item.name),
                            _active=active,
                            _budget=budget,
                            _byte_limit=_byte_limit,
                            _byte_budget=byte_budget,
                            _depth=_depth + 1,
                            _leaf_limit=(
                                declared_content_size
                                if item.name == "content" and declared_content_size is not None
                                else MAX_SEMANTIC_SNAPSHOT_BYTES
                            ),
                        ),
                    )
                    for item in fields(value)
                ),
            )
        raise ValueError("checkpoint semantic graph contains an unsupported value")
    finally:
        active.remove(identity)


@dataclass(frozen=True, slots=True, repr=False)
class LayaCheckpointFilePlan:
    role: str
    path: str = field(repr=False)
    sha256: str = field(repr=False)
    size_bytes: int
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("checkpoint file plan binding is invalid")
        _validate_file_plan_shape(self)

    __repr__ = _private_repr


def _validate_file_plan_shape(value: object) -> LayaCheckpointFilePlan:
    expected = {
        role: (path, digest, size)
        for role, path, digest, size in runtime_deployment_metadata.CHECKPOINT_FILES
    }
    if (
        type(value) is not LayaCheckpointFilePlan
        or value.role not in expected
        or (value.path, value.sha256, value.size_bytes) != expected.get(value.role)
        or not _valid_digest(value.sha256)
        or type(value.size_bytes) is not int
        or not 0 < value.size_bytes <= MAX_CHECKPOINT_FILE_BYTES
    ):
        raise ValueError("checkpoint file plan binding is invalid")
    return value


def _validate_deployment_claims(evidence: object) -> object:
    expected_type = runtime_deployment_metadata.LayaRuntimeDeploymentEvidence
    if type(evidence) is not expected_type:
        raise TypeError("deployment evidence must be an exact sealed value")
    if (
        any(getattr(evidence, name) is not True for name in _TRUE_FLAGS)
        or evidence.checkpoint_bytes_verified is not False
        or any(getattr(evidence, name) is not False for name in _FALSE_FLAGS)
        or type(evidence.checkpoint_manifest)
        is not runtime_deployment_metadata.ValidatedCheckpointManifest
        or type(evidence.checkpoint_manifest.files) is not tuple
    ):
        raise ValueError("deployment evidence claims are invalid")
    return evidence


def _validate_deployment(evidence: object) -> object:
    _validate_deployment_claims(evidence)
    snapshot = evidence.snapshot
    if (
        type(snapshot) is not runtime_bundle.LayaRuntimeBundleSnapshot
        or type(snapshot.artifacts) is not tuple
        or any(
            type(artifact) is not runtime_bundle.CapturedRuntimeArtifact
            for artifact in snapshot.artifacts
        )
    ):
        raise ValueError("deployment snapshot graph is invalid")
    payload_by_path = {artifact.spec.path: artifact.content for artifact in snapshot.artifacts}
    if len(payload_by_path) != len(snapshot.artifacts):
        raise ValueError("deployment snapshot artifact paths are invalid")
    rebuilt_snapshot = runtime_bundle.verify_laya_runtime_artifact_bytes(
        snapshot.manifest,
        payload_by_path,
    )
    if snapshot != rebuilt_snapshot:
        raise ValueError("deployment snapshot does not match verified artifact bytes")
    rebuilt_evidence = runtime_deployment_metadata.validate_laya_runtime_deployment_metadata(
        rebuilt_snapshot
    )
    if evidence != rebuilt_evidence or evidence.runtime_identity is not snapshot.runtime_identity:
        raise ValueError("deployment evidence does not match reconstructed metadata")
    return evidence


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeCheckpointPlan(_FactorySealed):
    schema_version: str
    deployment_evidence: runtime_deployment_metadata.LayaRuntimeDeploymentEvidence = field(
        repr=False
    )
    runtime_identity: object = field(repr=False)
    files: tuple[LayaCheckpointFilePlan, ...] = field(repr=False)
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("checkpoint plan requires the factory seal token")
        _validate_plan_shape(self)

    __repr__ = _private_repr


def _validate_plan_shape(value: object) -> LayaRuntimeCheckpointPlan:
    if type(value) is not LayaRuntimeCheckpointPlan:
        raise TypeError("checkpoint plan type is invalid")
    _validate_deployment_claims(value.deployment_evidence)
    expected_roles = tuple(item[0] for item in runtime_deployment_metadata.CHECKPOINT_FILES)
    if (
        value.schema_version != CHECKPOINT_PLAN_SCHEMA
        or value.runtime_identity is not value.deployment_evidence.runtime_identity
        or type(value.files) is not tuple
        or tuple(item.role for item in value.files) != expected_roles
        or any(type(item) is not LayaCheckpointFilePlan for item in value.files)
        or sum(item.size_bytes for item in value.files) > MAX_CHECKPOINT_TOTAL_BYTES
    ):
        raise ValueError("checkpoint plan binding is invalid")
    for item in value.files:
        _validate_file_plan_shape(item)
    return value


def _plan_semantics(plan: LayaRuntimeCheckpointPlan) -> tuple[object, ...]:
    return (
        plan.schema_version,
        _IdentitySeal(plan.deployment_evidence),
        _IdentitySeal(plan.runtime_identity),
        tuple(_IdentitySeal(item) for item in plan.files),
        tuple((item.role, item.path, item.sha256, item.size_bytes) for item in plan.files),
        _deep_semantic_snapshot(plan.deployment_evidence),
    )


def _require_issued_plan(value: object) -> LayaRuntimeCheckpointPlan:
    value = _validate_plan_shape(value)
    _requires_issued(
        value,
        LayaRuntimeCheckpointPlan,
        _ISSUED_PLANS,
        _plan_semantics(value),
        "checkpoint plan lacks issued authority",
    )
    return value


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class VerifiedLayaCheckpointFile(_FactorySealed):
    plan: LayaRuntimeCheckpointPlan = field(repr=False)
    file: LayaCheckpointFilePlan = field(repr=False)
    _factory_token: InitVar[object]
    checkpoint_file_bytes_verified: bool = field(default=True, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("checkpoint file receipt binding is invalid")
        _validate_receipt_shape(self)

    __repr__ = _private_repr


def _validate_receipt_shape(value: object) -> VerifiedLayaCheckpointFile:
    if (
        type(value) is not VerifiedLayaCheckpointFile
        or type(value.plan) is not LayaRuntimeCheckpointPlan
        or type(value.file) is not LayaCheckpointFilePlan
        or value.checkpoint_file_bytes_verified is not True
    ):
        raise ValueError("checkpoint file receipt binding is invalid")
    _require_issued_plan(value.plan)
    _validate_file_plan_shape(value.file)
    if not any(value.file is item for item in value.plan.files):
        raise ValueError("checkpoint file receipt binding is invalid")
    return value


def _receipt_semantics(receipt: VerifiedLayaCheckpointFile) -> tuple[object, ...]:
    return (
        _IdentitySeal(receipt.plan),
        _IdentitySeal(receipt.file),
        receipt.checkpoint_file_bytes_verified,
    )


def _require_issued_receipt(value: object) -> VerifiedLayaCheckpointFile:
    value = _validate_receipt_shape(value)
    _requires_issued(
        value,
        VerifiedLayaCheckpointFile,
        _ISSUED_RECEIPTS,
        _receipt_semantics(value),
        "checkpoint receipt lacks verifier authority",
    )
    return value


def _validate_receipts(
    plan: LayaRuntimeCheckpointPlan,
    receipts: object,
) -> tuple[VerifiedLayaCheckpointFile, ...]:
    if type(receipts) is not tuple or len(receipts) != len(plan.files):
        raise ValueError("checkpoint receipt coverage is invalid")
    for position, receipt in enumerate(receipts):
        _require_issued_receipt(receipt)
        if receipt.plan is not plan or receipt.file is not plan.files[position]:
            raise ValueError("checkpoint receipt order is invalid")
    return receipts


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class _LayaCheckpointCaptureAuthority(_FactorySealed):
    plan: LayaRuntimeCheckpointPlan = field(repr=False)
    receipts: tuple[VerifiedLayaCheckpointFile, ...] = field(repr=False)
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("checkpoint authority requires the factory seal token")
        _validate_authority_shape(self)

    __repr__ = _private_repr


def _validate_authority_shape(value: object) -> _LayaCheckpointCaptureAuthority:
    if type(value) is not _LayaCheckpointCaptureAuthority:
        raise TypeError("checkpoint authority type is invalid")
    _require_issued_plan(value.plan)
    _validate_receipts(value.plan, value.receipts)
    return value


def _authority_semantics(authority: _LayaCheckpointCaptureAuthority) -> tuple[object, ...]:
    return (
        _IdentitySeal(authority.plan),
        tuple(_IdentitySeal(receipt) for receipt in authority.receipts),
    )


def _require_issued_authority(value: object) -> _LayaCheckpointCaptureAuthority:
    value = _validate_authority_shape(value)
    _requires_issued(
        value,
        _LayaCheckpointCaptureAuthority,
        _ISSUED_AUTHORITIES,
        _authority_semantics(value),
        "checkpoint authority lacks capture authority",
    )
    return value


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaRuntimeCheckpointEvidence(_FactorySealed):
    schema_version: str
    plan: LayaRuntimeCheckpointPlan = field(repr=False)
    deployment_evidence: runtime_deployment_metadata.LayaRuntimeDeploymentEvidence = field(
        repr=False
    )
    runtime_identity: object = field(repr=False)
    receipts: tuple[VerifiedLayaCheckpointFile, ...] = field(repr=False)
    _factory_token: InitVar[object]
    artifact_integrity_verified: bool = field(default=True, init=False)
    runtime_config_semantics_verified: bool = field(default=True, init=False)
    checkpoint_manifest_semantics_verified: bool = field(default=True, init=False)
    checkpoint_bytes_verified: bool = field(default=True, init=False)
    lock_verified: bool = field(default=False, init=False)
    sbom_verified: bool = field(default=False, init=False)
    lock_sbom_consistent: bool = field(default=False, init=False)
    oci_bytes_verified: bool = field(default=False, init=False)
    oci_manifest_semantics_verified: bool = field(default=False, init=False)
    runtime_materialized: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)
    executor_available: bool = field(default=False, init=False)
    inference_executed: bool = field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("checkpoint evidence binding or claim is invalid")
        _validate_evidence_shape(self)

    __repr__ = _private_repr


def _validate_evidence_shape(value: object) -> LayaRuntimeCheckpointEvidence:
    if (
        type(value) is not LayaRuntimeCheckpointEvidence
        or value.schema_version != CHECKPOINT_EVIDENCE_SCHEMA
        or type(value.plan) is not LayaRuntimeCheckpointPlan
        or value.deployment_evidence is not value.plan.deployment_evidence
        or value.runtime_identity is not value.plan.runtime_identity
        or any(getattr(value, name) is not True for name in _TRUE_FLAGS)
        or value.checkpoint_bytes_verified is not True
        or any(getattr(value, name) is not False for name in _FALSE_FLAGS)
    ):
        raise ValueError("checkpoint evidence binding or claim is invalid")
    _require_issued_plan(value.plan)
    _validate_receipts(value.plan, value.receipts)
    return value


def _evidence_semantics(evidence: LayaRuntimeCheckpointEvidence) -> tuple[object, ...]:
    return (
        evidence.schema_version,
        _IdentitySeal(evidence.plan),
        _IdentitySeal(evidence.deployment_evidence),
        _IdentitySeal(evidence.runtime_identity),
        tuple(_IdentitySeal(receipt) for receipt in evidence.receipts),
        _deep_semantic_snapshot(evidence.deployment_evidence),
        tuple(
            getattr(evidence, name)
            for name in _TRUE_FLAGS + ("checkpoint_bytes_verified",) + _FALSE_FLAGS
        ),
    )


def _require_issued_evidence(value: object) -> LayaRuntimeCheckpointEvidence:
    value = _validate_evidence_shape(value)
    _requires_issued(
        value,
        LayaRuntimeCheckpointEvidence,
        _ISSUED_EVIDENCE,
        _evidence_semantics(value),
        "checkpoint evidence lacks byte-verification authority",
    )
    return value


def prepare_laya_runtime_checkpoint_plan(
    deployment_evidence: runtime_deployment_metadata.LayaRuntimeDeploymentEvidence,
) -> LayaRuntimeCheckpointPlan:
    """Bind an immutable five-file plan to exact deployment evidence."""

    failed = False
    result = None
    try:
        validated = _validate_deployment(deployment_evidence)
        files = tuple(
            LayaCheckpointFilePlan(
                role=item.role,
                path=item.path,
                sha256=item.sha256,
                size_bytes=item.size_bytes,
                _factory_token=_FACTORY_TOKEN,
            )
            for item in validated.checkpoint_manifest.files
        )
        result = LayaRuntimeCheckpointPlan(
            schema_version=CHECKPOINT_PLAN_SCHEMA,
            deployment_evidence=validated,
            runtime_identity=validated.runtime_identity,
            files=files,
            _factory_token=_FACTORY_TOKEN,
        )
        _register_issued(result, _ISSUED_PLANS, _plan_semantics(result))
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("checkpoint deployment validation failed")
    return result


def _authorize_file(plan: object, digest: object) -> LayaCheckpointFilePlan:
    plan = _require_issued_plan(plan)
    if not _valid_digest(digest):
        raise ValueError("checkpoint digest is invalid")
    matches = [item for item in plan.files if item.sha256 == digest]
    if len(matches) != 1:
        raise ValueError("checkpoint digest is not authorized")
    return matches[0]


def _verify_laya_checkpoint_file_chunks(
    plan: object,
    digest: object,
    chunks: object,
) -> VerifiedLayaCheckpointFile:
    descriptor = _authorize_file(plan, digest)
    iterator = iter(chunks)
    hasher = hashlib.sha256()
    captured = 0
    chunk_count = 0
    lfs_prefix = b""
    while True:
        chunk = next(iterator, _ITERATOR_EOF)
        if chunk is _ITERATOR_EOF:
            break
        chunk_count += 1
        if (
            type(chunk) is not bytes
            or not chunk
            or len(chunk) > MAX_CHECKPOINT_CHUNK_BYTES
            or chunk_count > MAX_CHECKPOINT_CHUNKS
        ):
            raise ValueError("checkpoint stream chunk limit is invalid")
        if len(lfs_prefix) < len(_LFS_SIGNATURE):
            lfs_prefix = (lfs_prefix + chunk)[: len(_LFS_SIGNATURE)]
            if len(lfs_prefix) == len(_LFS_SIGNATURE) and lfs_prefix == _LFS_SIGNATURE:
                raise ValueError("checkpoint Git LFS pointer is invalid")
        remaining = descriptor.size_bytes + 1 - captured
        consumed = chunk[:remaining]
        hasher.update(consumed)
        captured += len(consumed)
        if captured > descriptor.size_bytes or len(consumed) != len(chunk):
            raise ValueError("checkpoint stream exceeds declared size")
    if captured != descriptor.size_bytes or hasher.hexdigest() != descriptor.sha256:
        raise ValueError("checkpoint stream size or digest is invalid")
    receipt = VerifiedLayaCheckpointFile(
        plan=plan,
        file=descriptor,
        _factory_token=_FACTORY_TOKEN,
    )
    _register_issued(receipt, _ISSUED_RECEIPTS, _receipt_semantics(receipt))
    return receipt


def verify_laya_checkpoint_file_chunks(
    plan: LayaRuntimeCheckpointPlan,
    digest: str,
    chunks: object,
) -> VerifiedLayaCheckpointFile:
    """Incrementally verify one authorized checkpoint file."""

    failed = False
    result = None
    try:
        result = _verify_laya_checkpoint_file_chunks(plan, digest, chunks)
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("checkpoint stream verification failed")
    return result


def _seal_laya_checkpoint_capture_authority(
    plan: LayaRuntimeCheckpointPlan,
    receipts: tuple[VerifiedLayaCheckpointFile, ...],
) -> _LayaCheckpointCaptureAuthority:
    try:
        _require_issued_plan(plan)
        _validate_receipts(plan, receipts)
        authority = _LayaCheckpointCaptureAuthority(
            plan=plan,
            receipts=receipts,
            _factory_token=_FACTORY_TOKEN,
        )
        _register_issued(
            authority,
            _ISSUED_AUTHORITIES,
            _authority_semantics(authority),
        )
        return authority
    except Exception:
        _raise_private("checkpoint capture authority validation failed")


def _seal_laya_runtime_checkpoint_evidence(
    authority: object,
) -> LayaRuntimeCheckpointEvidence:
    failed = False
    result = None
    try:
        authority = _require_issued_authority(authority)
        result = LayaRuntimeCheckpointEvidence(
            schema_version=CHECKPOINT_EVIDENCE_SCHEMA,
            plan=authority.plan,
            deployment_evidence=authority.plan.deployment_evidence,
            runtime_identity=authority.plan.runtime_identity,
            receipts=authority.receipts,
            _factory_token=_FACTORY_TOKEN,
        )
        _register_issued(result, _ISSUED_EVIDENCE, _evidence_semantics(result))
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("checkpoint evidence sealing failed")
    return result


def canonical_laya_runtime_checkpoint_summary_bytes(
    evidence: LayaRuntimeCheckpointEvidence,
) -> bytes:
    """Return a canonical privacy-safe aggregate checkpoint summary."""

    failed = False
    result = None
    try:
        evidence = _require_issued_evidence(evidence)
        payload = {
            "schema_version": evidence.schema_version,
            "runtime_identity_sha256": evidence.runtime_identity.sha256,
            "artifact_integrity_verified": evidence.artifact_integrity_verified,
            "runtime_config_semantics_verified": evidence.runtime_config_semantics_verified,
            "checkpoint_manifest_semantics_verified": (
                evidence.checkpoint_manifest_semantics_verified
            ),
            "checkpoint_bytes_verified": evidence.checkpoint_bytes_verified,
            "lock_verified": evidence.lock_verified,
            "sbom_verified": evidence.sbom_verified,
            "lock_sbom_consistent": evidence.lock_sbom_consistent,
            "oci_bytes_verified": evidence.oci_bytes_verified,
            "oci_manifest_semantics_verified": evidence.oci_manifest_semantics_verified,
            "runtime_materialized": evidence.runtime_materialized,
            "origin_verified": evidence.origin_verified,
            "executor_available": evidence.executor_available,
            "inference_executed": evidence.inference_executed,
        }
        result = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("checkpoint evidence validation failed")
    return result
