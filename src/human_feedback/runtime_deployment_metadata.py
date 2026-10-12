"""Pure semantic validation for captured Laya runtime deployment metadata."""

from __future__ import annotations

import hashlib
import json
from dataclasses import InitVar, dataclass, field
from typing import Any

from . import runtime_bundle, runtime_identity

DEPLOYMENT_SCHEMA_VERSION = "laya-runtime-deployment-evidence-v1"
RUNTIME_CONFIG_SCHEMA_VERSION = "laya-runtime-config-v1"
CHECKPOINT_SCHEMA_VERSION = "laya-checkpoint-manifest-v1"
MAX_RUNTIME_CONFIG_BYTES = 16 * 1024
MAX_CHECKPOINT_MANIFEST_BYTES = 64 * 1024

ENTRYPOINT = "laya-serve"
MODEL_REPOSITORY = "convaiinnovations/laya"
MODEL_REVISION = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
MODEL_SUBFOLDER = "multilingual"
MODEL_NAME = "multilingual"
ENVIRONMENT = {
    "LAYA_DEVICE": "cpu",
    "LAYA_PRELOAD": "1",
    "LAYA_MODELS": "multilingual",
    "LAYA_AUTO_TASK": "0",
    "LAYA_DEFAULT_MODEL": "multilingual",
    "LAYA_REVISION": MODEL_REVISION,
    "HF_HUB_OFFLINE": "1",
}
CHECKPOINT_FILES = (
    (
        "encoder_config",
        "encoder/config.json",
        "83f6916d13ef0f556ac461f28308dc2bffa7ebeadee8ec9e2db5812020ea5bb4",
        1938,
    ),
    (
        "weights",
        "model.safetensors",
        "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204",
        643835514,
    ),
    (
        "laya_config",
        "rl_agent_config.json",
        "25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6",
        472,
    ),
    (
        "tokenizer",
        "tokenizer/tokenizer.json",
        "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f",
        34363188,
    ),
    (
        "tokenizer_config",
        "tokenizer/tokenizer_config.json",
        "6c6b2d8e3c84ce0e671c129cd6b374b235d6f9863042a5836358d00a89bbb5a1",
        524,
    ),
)

_CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "entrypoint",
        "provider",
        "engine",
        "source",
        "python",
        "platform",
        "model",
        "environment",
        "checkpoint_manifest_sha256",
    }
)
_MODEL_FIELDS = frozenset({"repository", "revision", "subfolder", "name"})
_CHECKPOINT_FIELDS = frozenset({"schema_version", "repository", "revision", "subfolder", "files"})
_CHECKPOINT_FILE_FIELDS = frozenset({"role", "path", "sha256", "size_bytes"})
_FACTORY_TOKEN = object()


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


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("metadata JSON contains a duplicate key")
        result[key] = value
    return result


def _reject_nonfinite(_value: str) -> None:
    raise ValueError("metadata JSON numeric value must be finite")


def _load_json_object_bytes(
    payload: bytes,
    *,
    label: str,
    maximum_bytes: int,
) -> dict[str, Any]:
    if not isinstance(payload, bytes):
        raise TypeError(f"{label} payload must be bytes")
    if len(payload) > maximum_bytes:
        raise ValueError(f"{label} payload size exceeds limit")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"{label} payload must be valid UTF-8 JSON") from None
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (json.JSONDecodeError, RecursionError):
        raise ValueError(f"{label} payload must be valid JSON") from None
    if not isinstance(value, dict):
        raise ValueError(f"{label} payload must be a JSON object")
    return value


def _exact_object(
    value: object,
    fields: frozenset[str],
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} fields or keys do not match the exact schema")
    return value


@dataclass(frozen=True, slots=True, repr=False)
class CheckpointFileSpec:
    role: str
    path: str
    sha256: str
    size_bytes: int
    _factory_token: InitVar[object]

    def __repr__(self) -> str:
        return "CheckpointFileSpec()"

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("checkpoint file requires the validated factory token")
        expected = {role: (path, digest, size) for role, path, digest, size in CHECKPOINT_FILES}
        if self.role not in expected:
            raise ValueError("checkpoint file role is not exact")
        _require_digest(self.sha256, label="checkpoint file digest")
        if type(self.size_bytes) is not int or self.size_bytes <= 0:
            raise ValueError("checkpoint file size must be a positive plain integer")
        if (self.path, self.sha256, self.size_bytes) != expected[self.role]:
            raise ValueError("checkpoint file path, digest, or size is not exact")


@dataclass(frozen=True, slots=True, repr=False)
class ValidatedCheckpointManifest:
    schema_version: str
    repository: str
    revision: str
    subfolder: str
    files: tuple[CheckpointFileSpec, ...]
    _factory_token: InitVar[object]

    def __repr__(self) -> str:
        return "ValidatedCheckpointManifest()"

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("checkpoint manifest requires the validated factory token")
        if self.schema_version != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError("checkpoint manifest schema is invalid")
        if (
            self.repository != MODEL_REPOSITORY
            or self.revision != MODEL_REVISION
            or self.subfolder != MODEL_SUBFOLDER
        ):
            raise ValueError("checkpoint repository, revision, or subfolder is invalid")
        if not isinstance(self.files, tuple) or any(
            not isinstance(item, CheckpointFileSpec) for item in self.files
        ):
            raise ValueError("checkpoint files are invalid")
        if tuple(item.role for item in self.files) != tuple(item[0] for item in CHECKPOINT_FILES):
            raise ValueError("checkpoint requires each exact file role once")


@dataclass(frozen=True, slots=True, repr=False)
class ValidatedRuntimeConfig:
    schema_version: str
    entrypoint: str
    provider: str
    engine: str
    source: str
    python: str
    platform: str
    model_repository: str
    model_revision: str
    model_subfolder: str
    model_name: str
    environment: tuple[tuple[str, str], ...]
    checkpoint_manifest_sha256: str
    _factory_token: InitVar[object]

    def __repr__(self) -> str:
        return "ValidatedRuntimeConfig()"

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("runtime config requires the validated factory token")
        if self.schema_version != RUNTIME_CONFIG_SCHEMA_VERSION:
            raise ValueError("runtime config schema is invalid")
        if self.entrypoint != ENTRYPOINT:
            raise ValueError("runtime config entrypoint is invalid")
        if (
            self.provider != runtime_identity.LAYA_PROVIDER
            or self.engine != runtime_identity.LAYA_ENGINE
            or self.source != runtime_identity.LAYA_SOURCE
            or self.python != runtime_identity.PYTHON_VERSION
            or self.platform != runtime_identity.RUNTIME_PLATFORM
        ):
            raise ValueError("runtime config identity is invalid")
        if (
            self.model_repository != MODEL_REPOSITORY
            or self.model_revision != MODEL_REVISION
            or self.model_subfolder != MODEL_SUBFOLDER
            or self.model_name != MODEL_NAME
        ):
            raise ValueError("runtime config model identity is invalid")
        if self.environment != tuple(sorted(ENVIRONMENT.items())):
            raise ValueError("runtime config environment must contain exact variables")
        _require_digest(
            self.checkpoint_manifest_sha256,
            label="runtime config checkpoint manifest digest",
        )


def validate_laya_runtime_config_bytes(payload: bytes) -> ValidatedRuntimeConfig:
    """Validate strict runtime config bytes without consulting external state."""

    raw = _exact_object(
        _load_json_object_bytes(
            payload,
            label="runtime config",
            maximum_bytes=MAX_RUNTIME_CONFIG_BYTES,
        ),
        _CONFIG_FIELDS,
        label="runtime config",
    )
    model = _exact_object(raw["model"], _MODEL_FIELDS, label="runtime config model")
    environment = raw["environment"]
    if not isinstance(environment, dict) or set(environment) != set(ENVIRONMENT):
        raise ValueError("runtime config environment keys must be exact")
    return ValidatedRuntimeConfig(
        schema_version=raw["schema_version"],
        entrypoint=raw["entrypoint"],
        provider=raw["provider"],
        engine=raw["engine"],
        source=raw["source"],
        python=raw["python"],
        platform=raw["platform"],
        model_repository=model["repository"],
        model_revision=model["revision"],
        model_subfolder=model["subfolder"],
        model_name=model["name"],
        environment=tuple(sorted(environment.items())),
        checkpoint_manifest_sha256=_require_digest(
            raw["checkpoint_manifest_sha256"],
            label="runtime config checkpoint manifest digest",
        ),
        _factory_token=_FACTORY_TOKEN,
    )


def _parse_checkpoint_file(raw_value: object) -> CheckpointFileSpec:
    raw = _exact_object(raw_value, _CHECKPOINT_FILE_FIELDS, label="checkpoint file")
    if type(raw["size_bytes"]) is not int or raw["size_bytes"] <= 0:
        raise ValueError("checkpoint file size must be a positive plain integer")
    return CheckpointFileSpec(
        role=raw["role"],
        path=raw["path"],
        sha256=raw["sha256"],
        size_bytes=raw["size_bytes"],
        _factory_token=_FACTORY_TOKEN,
    )


def validate_laya_checkpoint_manifest_bytes(payload: bytes) -> ValidatedCheckpointManifest:
    """Validate and canonically order exact checkpoint manifest bytes."""

    raw = _exact_object(
        _load_json_object_bytes(
            payload,
            label="checkpoint manifest",
            maximum_bytes=MAX_CHECKPOINT_MANIFEST_BYTES,
        ),
        _CHECKPOINT_FIELDS,
        label="checkpoint manifest",
    )
    raw_files = raw["files"]
    if not isinstance(raw_files, list):
        raise ValueError("checkpoint files must be a JSON array")
    if len(raw_files) != len(CHECKPOINT_FILES):
        raise ValueError("checkpoint files count must be exactly five")
    files = [_parse_checkpoint_file(item) for item in raw_files]
    roles = [item.role for item in files]
    expected_roles = tuple(item[0] for item in CHECKPOINT_FILES)
    if len(roles) != len(expected_roles) or set(roles) != set(expected_roles):
        raise ValueError("checkpoint requires each exact file role once without duplicates")
    order = {role: index for index, role in enumerate(expected_roles)}
    canonical_files = tuple(sorted(files, key=lambda item: order[item.role]))
    return ValidatedCheckpointManifest(
        schema_version=raw["schema_version"],
        repository=raw["repository"],
        revision=raw["revision"],
        subfolder=raw["subfolder"],
        files=canonical_files,
        _factory_token=_FACTORY_TOKEN,
    )


@dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeDeploymentEvidence:
    schema_version: str
    snapshot: runtime_bundle.LayaRuntimeBundleSnapshot = field(repr=False)
    runtime_config: ValidatedRuntimeConfig = field(repr=False)
    checkpoint_manifest: ValidatedCheckpointManifest = field(repr=False)
    runtime_identity: runtime_identity.RuntimeIdentityRef
    _factory_token: InitVar[object]
    artifact_integrity_verified: bool = field(default=True, init=False)
    runtime_config_semantics_verified: bool = field(default=True, init=False)
    checkpoint_manifest_semantics_verified: bool = field(default=True, init=False)
    lock_verified: bool = field(default=False, init=False)
    sbom_verified: bool = field(default=False, init=False)
    lock_sbom_consistent: bool = field(default=False, init=False)
    checkpoint_bytes_verified: bool = field(default=False, init=False)
    oci_bytes_verified: bool = field(default=False, init=False)
    oci_manifest_semantics_verified: bool = field(default=False, init=False)
    runtime_materialized: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)
    executor_available: bool = field(default=False, init=False)
    inference_executed: bool = field(default=False, init=False)

    def __repr__(self) -> str:
        return "LayaRuntimeDeploymentEvidence()"

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("deployment evidence requires the validated factory token")
        if self.schema_version != DEPLOYMENT_SCHEMA_VERSION:
            raise ValueError("deployment evidence schema is invalid")
        if not isinstance(self.snapshot, runtime_bundle.LayaRuntimeBundleSnapshot):
            raise ValueError("deployment evidence snapshot is invalid")
        if not isinstance(self.runtime_config, ValidatedRuntimeConfig) or not isinstance(
            self.checkpoint_manifest, ValidatedCheckpointManifest
        ):
            raise ValueError("deployment metadata is invalid")
        if self.runtime_identity != self.snapshot.runtime_identity:
            raise ValueError("deployment runtime identity does not match snapshot")
        _validate_deployment_links(self.snapshot, self.runtime_config, self.checkpoint_manifest)


def _captured_content_by_kind(
    snapshot: runtime_bundle.LayaRuntimeBundleSnapshot,
) -> dict[str, bytes]:
    return {artifact.spec.kind: artifact.content for artifact in snapshot.artifacts}


def _validate_deployment_links(
    snapshot: runtime_bundle.LayaRuntimeBundleSnapshot,
    config: ValidatedRuntimeConfig,
    checkpoint: ValidatedCheckpointManifest,
) -> None:
    manifest = snapshot.manifest
    if (
        config.provider != manifest.provider
        or config.engine != manifest.engine
        or config.source != manifest.source
        or config.python != manifest.python
        or config.platform != manifest.platform
    ):
        raise ValueError("deployment runtime metadata does not match the bundle manifest")
    if (
        config.model_repository != checkpoint.repository
        or config.model_revision != checkpoint.revision
        or config.model_subfolder != checkpoint.subfolder
    ):
        raise ValueError("deployment model metadata does not match checkpoint")
    checkpoint_bytes = _captured_content_by_kind(snapshot)["checkpoint_manifest"]
    if config.checkpoint_manifest_sha256 != hashlib.sha256(checkpoint_bytes).hexdigest():
        raise ValueError("deployment checkpoint metadata digest does not match captured bytes")


def validate_laya_runtime_deployment_metadata(
    snapshot: runtime_bundle.LayaRuntimeBundleSnapshot,
) -> LayaRuntimeDeploymentEvidence:
    """Validate metadata extracted only from a sealed portable bundle snapshot."""

    if not isinstance(snapshot, runtime_bundle.LayaRuntimeBundleSnapshot):
        raise TypeError("deployment snapshot must be a validated runtime bundle")
    content_by_kind = _captured_content_by_kind(snapshot)
    try:
        runtime_config_bytes = content_by_kind["runtime_config"]
        checkpoint_manifest_bytes = content_by_kind["checkpoint_manifest"]
    except KeyError:
        raise ValueError("deployment snapshot lacks required metadata artifacts") from None
    config = validate_laya_runtime_config_bytes(runtime_config_bytes)
    checkpoint = validate_laya_checkpoint_manifest_bytes(checkpoint_manifest_bytes)
    _validate_deployment_links(snapshot, config, checkpoint)
    return LayaRuntimeDeploymentEvidence(
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        snapshot=snapshot,
        runtime_config=config,
        checkpoint_manifest=checkpoint,
        runtime_identity=snapshot.runtime_identity,
        _factory_token=_FACTORY_TOKEN,
    )


def canonical_laya_runtime_deployment_summary_bytes(
    evidence: LayaRuntimeDeploymentEvidence,
) -> bytes:
    """Return only aggregate identity and conservative semantic attestations."""

    if not isinstance(evidence, LayaRuntimeDeploymentEvidence):
        raise TypeError("deployment evidence must be validated")
    payload = {
        "schema_version": evidence.schema_version,
        "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
        "runtime_identity_sha256": evidence.runtime_identity.sha256,
        "artifact_integrity_verified": evidence.artifact_integrity_verified,
        "runtime_config_semantics_verified": evidence.runtime_config_semantics_verified,
        "checkpoint_manifest_semantics_verified": (evidence.checkpoint_manifest_semantics_verified),
        "lock_verified": evidence.lock_verified,
        "sbom_verified": evidence.sbom_verified,
        "lock_sbom_consistent": evidence.lock_sbom_consistent,
        "checkpoint_bytes_verified": evidence.checkpoint_bytes_verified,
        "oci_bytes_verified": evidence.oci_bytes_verified,
        "oci_manifest_semantics_verified": evidence.oci_manifest_semantics_verified,
        "runtime_materialized": evidence.runtime_materialized,
        "origin_verified": evidence.origin_verified,
        "executor_available": evidence.executor_available,
        "inference_executed": evidence.inference_executed,
    }
    return _canonical_json_bytes(payload)
