"""Pure in-memory integrity verification for a declared Laya runtime bundle."""

from __future__ import annotations

import hashlib
import json
from dataclasses import InitVar, dataclass, field
from typing import Any

from human_feedback.runtime_identity import (
    LayaRuntimeManifest,
    RuntimeArtifactSpec,
    RuntimeIdentityRef,
    runtime_identity_ref,
)

SCHEMA_VERSION = "laya-runtime-bundle-snapshot-v1"

_VERIFICATION_TOKEN = object()
_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _require_verified_content(spec: RuntimeArtifactSpec, content: object) -> bytes:
    if not isinstance(spec, RuntimeArtifactSpec):
        raise ValueError("runtime artifact specification is invalid")
    if type(content) is not bytes:
        raise TypeError("runtime artifact payload must be bytes")
    if content.startswith(_LFS_POINTER_PREFIX):
        raise ValueError("Git LFS pointer is not runtime artifact content")
    if len(content) != spec.size_bytes:
        raise ValueError("runtime artifact integrity size mismatch")
    if hashlib.sha256(content).hexdigest() != spec.sha256:
        raise ValueError("runtime artifact integrity digest mismatch")
    return content


@dataclass(frozen=True, slots=True)
class CapturedRuntimeArtifact:
    """One artifact whose private bytes match its declared specification."""

    spec: RuntimeArtifactSpec = field(repr=False)
    content: bytes = field(repr=False)
    _verification_token: InitVar[object]

    def __post_init__(self, _verification_token: object) -> None:
        if _verification_token is not _VERIFICATION_TOKEN:
            raise ValueError("runtime artifact requires the verification factory token")
        _require_verified_content(self.spec, self.content)


@dataclass(frozen=True, slots=True)
class LayaRuntimeBundleSnapshot:
    """All-or-nothing integrity snapshot with conservative attestations."""

    schema_version: str
    manifest: LayaRuntimeManifest = field(repr=False)
    artifacts: tuple[CapturedRuntimeArtifact, ...] = field(repr=False)
    runtime_identity: RuntimeIdentityRef
    _verification_token: InitVar[object]
    artifact_integrity_verified: bool = field(default=True, init=False)
    lock_verified: bool = field(default=False, init=False)
    sbom_verified: bool = field(default=False, init=False)
    lock_sbom_consistent: bool = field(default=False, init=False)
    runtime_config_semantics_verified: bool = field(default=False, init=False)
    checkpoint_manifest_semantics_verified: bool = field(default=False, init=False)
    oci_manifest_semantics_verified: bool = field(default=False, init=False)
    runtime_materialized: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)
    executor_available: bool = field(default=False, init=False)
    inference_executed: bool = field(default=False, init=False)

    def __post_init__(self, _verification_token: object) -> None:
        if _verification_token is not _VERIFICATION_TOKEN:
            raise ValueError("runtime bundle requires the verification factory token")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("runtime bundle snapshot schema version is invalid")
        if not isinstance(self.manifest, LayaRuntimeManifest):
            raise ValueError("runtime bundle manifest is invalid")
        if not isinstance(self.artifacts, tuple):
            raise ValueError("runtime bundle artifacts must be a canonical tuple")
        if any(not isinstance(artifact, CapturedRuntimeArtifact) for artifact in self.artifacts):
            raise ValueError("runtime bundle contains an invalid captured artifact")
        expected_specs = self.manifest.artifacts
        if tuple(artifact.spec for artifact in self.artifacts) != expected_specs:
            raise ValueError("runtime bundle artifacts do not match the manifest order")
        for artifact in self.artifacts:
            _require_verified_content(artifact.spec, artifact.content)
        if self.runtime_identity != runtime_identity_ref(self.manifest):
            raise ValueError("runtime bundle identity does not match the manifest")


def verify_laya_runtime_artifact_bytes(
    manifest: LayaRuntimeManifest,
    payload_by_path: dict[str, bytes],
) -> LayaRuntimeBundleSnapshot:
    """Verify an exact path-to-bytes bundle without performing any I/O."""

    if not isinstance(manifest, LayaRuntimeManifest):
        raise ValueError("runtime artifact manifest is invalid")
    if type(payload_by_path) is not dict:
        raise TypeError("runtime artifact payload collection must be a dict of bytes")
    expected_paths = {artifact.path for artifact in manifest.artifacts}
    if set(payload_by_path) != expected_paths:
        raise ValueError("runtime artifact payload coverage has missing or additional paths")
    if any(type(content) is not bytes for content in payload_by_path.values()):
        raise TypeError("runtime artifact payload values must be bytes")

    captured = tuple(
        CapturedRuntimeArtifact(
            spec=spec,
            content=_require_verified_content(spec, payload_by_path[spec.path]),
            _verification_token=_VERIFICATION_TOKEN,
        )
        for spec in manifest.artifacts
    )
    return LayaRuntimeBundleSnapshot(
        schema_version=SCHEMA_VERSION,
        manifest=manifest,
        artifacts=captured,
        runtime_identity=runtime_identity_ref(manifest),
        _verification_token=_VERIFICATION_TOKEN,
    )


def canonical_laya_runtime_bundle_summary_bytes(
    snapshot: LayaRuntimeBundleSnapshot,
) -> bytes:
    """Return a deterministic public summary without private artifact bytes."""

    if not isinstance(snapshot, LayaRuntimeBundleSnapshot):
        raise ValueError("runtime bundle snapshot is invalid")
    payload = {
        "schema_version": snapshot.schema_version,
        "runtime_identity_schema_version": snapshot.runtime_identity.schema_version,
        "runtime_identity_sha256": snapshot.runtime_identity.sha256,
        "artifacts_count": len(snapshot.artifacts),
        "artifact_integrity_verified": snapshot.artifact_integrity_verified,
        "lock_verified": snapshot.lock_verified,
        "sbom_verified": snapshot.sbom_verified,
        "lock_sbom_consistent": snapshot.lock_sbom_consistent,
        "runtime_config_semantics_verified": snapshot.runtime_config_semantics_verified,
        "checkpoint_manifest_semantics_verified": (snapshot.checkpoint_manifest_semantics_verified),
        "oci_manifest_semantics_verified": snapshot.oci_manifest_semantics_verified,
        "runtime_materialized": snapshot.runtime_materialized,
        "origin_verified": snapshot.origin_verified,
        "executor_available": snapshot.executor_available,
        "inference_executed": snapshot.inference_executed,
    }
    return _canonical_json_bytes(payload)
