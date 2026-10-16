"""Pure bounded verification of the five declared Laya checkpoint files."""

from __future__ import annotations

import hashlib
import json
from dataclasses import InitVar, dataclass, field

from . import runtime_bundle, runtime_deployment_metadata

CHECKPOINT_PLAN_SCHEMA = "laya-runtime-checkpoint-plan-v1"
CHECKPOINT_EVIDENCE_SCHEMA = "laya-runtime-checkpoint-evidence-v1"
MAX_CHECKPOINT_FILE_BYTES = 700 * 1024 * 1024
MAX_CHECKPOINT_TOTAL_BYTES = 768 * 1024 * 1024
MAX_CHECKPOINT_CHUNK_BYTES = 1024 * 1024
MAX_CHECKPOINT_CHUNKS = 1024

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


@dataclass(frozen=True, slots=True, repr=False)
class LayaCheckpointFilePlan:
    role: str
    path: str = field(repr=False)
    sha256: str = field(repr=False)
    size_bytes: int
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        expected = {
            role: (path, digest, size)
            for role, path, digest, size in runtime_deployment_metadata.CHECKPOINT_FILES
        }
        if (
            _factory_token is not _FACTORY_TOKEN
            or self.role not in expected
            or (self.path, self.sha256, self.size_bytes) != expected.get(self.role)
            or not _valid_digest(self.sha256)
            or type(self.size_bytes) is not int
            or not 0 < self.size_bytes <= MAX_CHECKPOINT_FILE_BYTES
        ):
            raise ValueError("checkpoint file plan binding is invalid")

    __repr__ = _private_repr


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


@dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeCheckpointPlan:
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
        _validate_deployment_claims(self.deployment_evidence)
        expected_roles = tuple(item[0] for item in runtime_deployment_metadata.CHECKPOINT_FILES)
        if (
            self.schema_version != CHECKPOINT_PLAN_SCHEMA
            or self.runtime_identity is not self.deployment_evidence.runtime_identity
            or type(self.files) is not tuple
            or tuple(item.role for item in self.files) != expected_roles
            or any(type(item) is not LayaCheckpointFilePlan for item in self.files)
            or sum(item.size_bytes for item in self.files) > MAX_CHECKPOINT_TOTAL_BYTES
        ):
            raise ValueError("checkpoint plan binding is invalid")
        for item in self.files:
            item.__post_init__(_FACTORY_TOKEN)

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedLayaCheckpointFile:
    plan: LayaRuntimeCheckpointPlan = field(repr=False)
    file: LayaCheckpointFilePlan = field(repr=False)
    _factory_token: InitVar[object]
    checkpoint_file_bytes_verified: bool = field(default=True, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if (
            _factory_token is not _FACTORY_TOKEN
            or type(self.plan) is not LayaRuntimeCheckpointPlan
            or type(self.file) is not LayaCheckpointFilePlan
            or not any(self.file is item for item in self.plan.files)
            or self.checkpoint_file_bytes_verified is not True
        ):
            raise ValueError("checkpoint file receipt binding is invalid")
        self.plan.__post_init__(_FACTORY_TOKEN)
        self.file.__post_init__(_FACTORY_TOKEN)

    __repr__ = _private_repr


def _validate_receipts(
    plan: LayaRuntimeCheckpointPlan,
    receipts: object,
) -> tuple[VerifiedLayaCheckpointFile, ...]:
    if type(receipts) is not tuple or len(receipts) != len(plan.files):
        raise ValueError("checkpoint receipt coverage is invalid")
    for position, receipt in enumerate(receipts):
        if type(receipt) is not VerifiedLayaCheckpointFile:
            raise ValueError("checkpoint receipt type is invalid")
        receipt.__post_init__(_FACTORY_TOKEN)
        if receipt.plan is not plan or receipt.file is not plan.files[position]:
            raise ValueError("checkpoint receipt order is invalid")
    return receipts


@dataclass(frozen=True, slots=True, repr=False)
class _LayaCheckpointCaptureAuthority:
    plan: LayaRuntimeCheckpointPlan = field(repr=False)
    receipts: tuple[VerifiedLayaCheckpointFile, ...] = field(repr=False)
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("checkpoint authority requires the factory seal token")
        self.plan.__post_init__(_FACTORY_TOKEN)
        _validate_receipts(self.plan, self.receipts)

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeCheckpointEvidence:
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
        if (
            _factory_token is not _FACTORY_TOKEN
            or self.schema_version != CHECKPOINT_EVIDENCE_SCHEMA
            or type(self.plan) is not LayaRuntimeCheckpointPlan
            or self.deployment_evidence is not self.plan.deployment_evidence
            or self.runtime_identity is not self.plan.runtime_identity
            or any(getattr(self, name) is not True for name in _TRUE_FLAGS)
            or self.checkpoint_bytes_verified is not True
            or any(getattr(self, name) is not False for name in _FALSE_FLAGS)
        ):
            raise ValueError("checkpoint evidence binding or claim is invalid")
        self.plan.__post_init__(_FACTORY_TOKEN)
        _validate_receipts(self.plan, self.receipts)

    __repr__ = _private_repr


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
    except Exception:
        failed = True
    if failed or result is None:
        _raise_private("checkpoint deployment validation failed")
    return result


def _authorize_file(plan: object, digest: object) -> LayaCheckpointFilePlan:
    if type(plan) is not LayaRuntimeCheckpointPlan:
        raise TypeError("checkpoint plan type is invalid")
    plan.__post_init__(_FACTORY_TOKEN)
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
    return VerifiedLayaCheckpointFile(
        plan=plan,
        file=descriptor,
        _factory_token=_FACTORY_TOKEN,
    )


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
        return _LayaCheckpointCaptureAuthority(
            plan=plan,
            receipts=receipts,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        _raise_private("checkpoint capture authority validation failed")


def _seal_laya_runtime_checkpoint_evidence(
    authority: object,
) -> LayaRuntimeCheckpointEvidence:
    failed = False
    result = None
    try:
        if type(authority) is not _LayaCheckpointCaptureAuthority:
            raise TypeError("checkpoint authority type is invalid")
        authority.__post_init__(_FACTORY_TOKEN)
        result = LayaRuntimeCheckpointEvidence(
            schema_version=CHECKPOINT_EVIDENCE_SCHEMA,
            plan=authority.plan,
            deployment_evidence=authority.plan.deployment_evidence,
            runtime_identity=authority.plan.runtime_identity,
            receipts=authority.receipts,
            _factory_token=_FACTORY_TOKEN,
        )
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
        if type(evidence) is not LayaRuntimeCheckpointEvidence:
            raise TypeError("checkpoint evidence type is invalid")
        evidence.__post_init__(_FACTORY_TOKEN)
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
