"""Pure, fail-closed identity contract for a pinned Laya runtime.

This module validates caller-provided manifest bytes.  It deliberately does not
inspect artifacts, materialize a runtime, or attest origin or execution.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "laya-runtime-manifest-v1"
IDENTITY_SCHEMA_VERSION = "laya-runtime-identity-v1"
LAYA_PROVIDER = "laya-http"
LAYA_ENGINE = "laya==0.4.2"
LAYA_RUNTIME_ID = "laya-0.4.2-python-3.11.10-linux-amd64"
LAYA_SOURCE_PREFIX = "https://github.com/convaiinnovations/laya@"
LAYA_LICENSE = "Apache-2.0"
PYTHON_VERSION = "3.11.10"
RUNTIME_PLATFORM = "linux/amd64"
BASE_IMAGE_PREFIX = "docker.io/library/python@sha256:"

ARTIFACT_KINDS = (
    "dependency_lock",
    "sbom",
    "runtime_config",
    "checkpoint_manifest",
    "oci_manifest",
)
ARTIFACT_FORMATS = {
    "dependency_lock": "uv-lock-v1",
    "sbom": "cyclonedx-json-1.6",
    "runtime_config": "json",
    "checkpoint_manifest": "json",
    "oci_manifest": "oci-image-manifest-v1",
}

_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "runtime_id",
        "provider",
        "engine",
        "source",
        "license",
        "python",
        "platform",
        "base_image_ref",
        "artifacts",
    }
)
_ARTIFACT_FIELDS = frozenset({"kind", "format", "path", "sha256", "size_bytes"})
_RELATIVE_POSIX_PATH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*\Z")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _require_digest(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        or value == "0" * 64
    ):
        raise ValueError(f"{label} must be a non-null lowercase SHA-256 digest")
    return value


def _require_sha1(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
        or value == "0" * 40
    ):
        raise ValueError(f"{label} must be a non-null lowercase commit SHA-1")
    return value


def _require_runtime_id(value: object) -> str:
    if value != LAYA_RUNTIME_ID:
        raise ValueError(f"runtime id must be exactly {LAYA_RUNTIME_ID}")
    return value


def _require_artifact_path(value: object) -> str:
    if not isinstance(value, str) or _RELATIVE_POSIX_PATH.fullmatch(value) is None:
        raise ValueError("artifact path must be a canonical relative POSIX path")
    return value


@dataclass(frozen=True, slots=True)
class RuntimeIdentityRef:
    """Opaque reference shared with the LOSO execution evidence contract."""

    schema_version: str
    sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != IDENTITY_SCHEMA_VERSION:
            raise ValueError("runtime identity schema version is invalid")
        _require_digest(self.sha256, label="runtime identity digest")


@dataclass(frozen=True, slots=True)
class RuntimeArtifactSpec:
    """Declared identity of one required runtime artifact."""

    kind: str
    format: str
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if self.kind not in ARTIFACT_KINDS:
            raise ValueError("runtime artifact kind is invalid")
        if self.format != ARTIFACT_FORMATS[self.kind]:
            raise ValueError("runtime artifact format is invalid for its kind")
        _require_artifact_path(self.path)
        _require_digest(self.sha256, label="runtime artifact digest")
        if type(self.size_bytes) is not int or self.size_bytes <= 0:
            raise ValueError("runtime artifact size must be a positive integer")


@dataclass(frozen=True, slots=True)
class LayaRuntimeManifest:
    """Canonical structural manifest; verification attestations remain false."""

    schema_version: str
    runtime_id: str
    provider: str
    engine: str
    source: str
    license: str
    python: str
    platform: str
    base_image_ref: str
    artifacts: tuple[RuntimeArtifactSpec, ...]
    identity_sha256: str = field(init=False)
    structurally_valid: bool = field(default=True, init=False)
    artifact_integrity_verified: bool = field(default=False, init=False)
    lock_verified: bool = field(default=False, init=False)
    sbom_verified: bool = field(default=False, init=False)
    lock_sbom_consistent: bool = field(default=False, init=False)
    checkpoint_bytes_verified: bool = field(default=False, init=False)
    oci_bytes_verified: bool = field(default=False, init=False)
    runtime_materialized: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)
    executor_available: bool = field(default=False, init=False)
    inference_executed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _validate_manifest(self)
        object.__setattr__(
            self,
            "identity_sha256",
            hashlib.sha256(canonical_laya_runtime_manifest_bytes(self)).hexdigest(),
        )


def _validate_manifest(manifest: LayaRuntimeManifest) -> None:
    if manifest.schema_version != SCHEMA_VERSION:
        raise ValueError("runtime manifest schema version is invalid")
    _require_runtime_id(manifest.runtime_id)
    if manifest.provider != LAYA_PROVIDER:
        raise ValueError("runtime provider must be laya-http")
    if manifest.engine != LAYA_ENGINE:
        raise ValueError("runtime engine must be pinned to laya==0.4.2")
    if not isinstance(manifest.source, str) or not manifest.source.startswith(LAYA_SOURCE_PREFIX):
        raise ValueError("runtime source must pin the canonical Laya repository")
    _require_sha1(manifest.source.removeprefix(LAYA_SOURCE_PREFIX), label="source commit")
    if manifest.license != LAYA_LICENSE:
        raise ValueError("runtime license must be Apache-2.0")
    if manifest.python != PYTHON_VERSION:
        raise ValueError("runtime python version is invalid")
    if manifest.platform != RUNTIME_PLATFORM:
        raise ValueError("runtime platform is invalid")
    if not isinstance(manifest.base_image_ref, str) or not manifest.base_image_ref.startswith(
        BASE_IMAGE_PREFIX
    ):
        raise ValueError("runtime base image must use the canonical digest reference")
    _require_digest(
        manifest.base_image_ref.removeprefix(BASE_IMAGE_PREFIX),
        label="base image digest",
    )
    if not isinstance(manifest.artifacts, tuple):
        raise ValueError("runtime artifacts must be a canonical tuple")
    if any(not isinstance(artifact, RuntimeArtifactSpec) for artifact in manifest.artifacts):
        raise ValueError("runtime artifacts contain an invalid artifact")
    kinds = tuple(artifact.kind for artifact in manifest.artifacts)
    if kinds != ARTIFACT_KINDS:
        raise ValueError("runtime artifacts require each exact artifact kind once")
    paths = tuple(artifact.path for artifact in manifest.artifacts)
    if len(paths) != len(set(paths)):
        raise ValueError("runtime artifact paths must be unique without duplicates")


def _manifest_payload(manifest: LayaRuntimeManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "runtime_id": manifest.runtime_id,
        "provider": manifest.provider,
        "engine": manifest.engine,
        "source": manifest.source,
        "license": manifest.license,
        "python": manifest.python,
        "platform": manifest.platform,
        "base_image_ref": manifest.base_image_ref,
        "artifacts": [
            {
                "kind": artifact.kind,
                "format": artifact.format,
                "path": artifact.path,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
            }
            for artifact in manifest.artifacts
        ],
    }


def canonical_laya_runtime_manifest_bytes(manifest: LayaRuntimeManifest) -> bytes:
    """Serialize only canonical declared identity, excluding all attestations."""

    if not isinstance(manifest, LayaRuntimeManifest):
        raise ValueError("runtime manifest is invalid")
    _validate_manifest(manifest)
    return _canonical_json_bytes(_manifest_payload(manifest))


def laya_runtime_identity_digest(manifest: LayaRuntimeManifest) -> str:
    """Return the canonical SHA-256 identity of the declared runtime."""

    return hashlib.sha256(canonical_laya_runtime_manifest_bytes(manifest)).hexdigest()


def runtime_identity_ref(manifest: LayaRuntimeManifest) -> RuntimeIdentityRef:
    """Create an opaque reference without upgrading verification state."""

    if not isinstance(manifest, LayaRuntimeManifest):
        raise ValueError("runtime manifest is invalid")
    return RuntimeIdentityRef(
        schema_version=IDENTITY_SCHEMA_VERSION,
        sha256=laya_runtime_identity_digest(manifest),
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("runtime manifest JSON contains a duplicate key")
        result[key] = value
    return result


def _reject_nonfinite(_value: str) -> None:
    raise ValueError("runtime manifest JSON numeric value must be finite")


def _require_exact_object(
    value: object,
    fields: frozenset[str],
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields or keys do not match the schema")
    return value


def _parse_artifacts(value: object) -> tuple[RuntimeArtifactSpec, ...]:
    if not isinstance(value, list):
        raise ValueError("runtime artifacts must be a JSON array")
    artifacts: list[RuntimeArtifactSpec] = []
    for item in value:
        raw = _require_exact_object(item, _ARTIFACT_FIELDS, label="runtime artifact")
        artifacts.append(
            RuntimeArtifactSpec(
                kind=raw["kind"],
                format=raw["format"],
                path=raw["path"],
                sha256=raw["sha256"],
                size_bytes=raw["size_bytes"],
            )
        )
    kinds = [artifact.kind for artifact in artifacts]
    if len(kinds) != len(ARTIFACT_KINDS) or set(kinds) != set(ARTIFACT_KINDS):
        raise ValueError("runtime artifacts require each exact kind once without duplicates")
    order = {kind: index for index, kind in enumerate(ARTIFACT_KINDS)}
    return tuple(sorted(artifacts, key=lambda artifact: order[artifact.kind]))


def load_laya_runtime_manifest_bytes(payload: bytes) -> LayaRuntimeManifest:
    """Parse and canonicalize caller-provided UTF-8 JSON bytes only."""

    if not isinstance(payload, bytes):
        raise TypeError("runtime manifest payload must be bytes")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("runtime manifest payload must be valid UTF-8") from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except json.JSONDecodeError as error:
        raise ValueError("runtime manifest payload must be valid JSON") from error

    raw = _require_exact_object(value, _MANIFEST_FIELDS, label="runtime manifest")
    return LayaRuntimeManifest(
        schema_version=raw["schema_version"],
        runtime_id=raw["runtime_id"],
        provider=raw["provider"],
        engine=raw["engine"],
        source=raw["source"],
        license=raw["license"],
        python=raw["python"],
        platform=raw["platform"],
        base_image_ref=raw["base_image_ref"],
        artifacts=_parse_artifacts(raw["artifacts"]),
    )
