"""Pure validation of the closed Laya OCI runtime-config profile."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import InitVar, dataclass, field

import human_feedback.runtime_oci_layout as runtime_oci_layout
from human_feedback.runtime_bundle import verify_laya_runtime_artifact_bytes
from human_feedback.runtime_oci_metadata import validate_laya_runtime_oci_metadata

MAX_OCI_CONFIG_BYTES = 64 * 1_024
MAX_OCI_CONFIG_JSON_DEPTH = 32
MAX_OCI_CONFIG_OBJECT_MEMBERS = 64
MAX_OCI_CONFIG_LIST_ITEMS = 256
MAX_OCI_CONFIG_STRING_LENGTH = 4_096
MAX_OCI_CONFIG_JSON_NODES = 2_048
OCI_CONFIG_PROFILE_SCHEMA = "laya-runtime-oci-config-profile-v1"
OCI_CONFIG_EVIDENCE_SCHEMA = "laya-runtime-oci-config-evidence-v1"

_FACTORY_TOKEN = object()
_CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"
_CONFIG_SIZE_BYTES = 10_261
_CONFIG_SHA256 = "bdd27ffe0d14dd637985f09bcdf461e58a64348829a4b3ad3cb7886ff56e20c5"
_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
_LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
_OCI_MANIFEST_SEMANTICS_SHA256 = "e8b3c42b7698c4e821abbb6dca21e3226c8eca59d62983c2ba7ad0b1010539e5"
_TOP_LEVEL_FIELDS = {"architecture", "config", "created", "history", "os", "rootfs"}
_CONFIG_FIELDS = {"User", "Env", "Entrypoint", "WorkingDir", "Labels"}
_HISTORY_REQUIRED_FIELDS = {"created", "created_by", "comment"}
_HISTORY_ALLOWED_FIELDS = {*_HISTORY_REQUIRED_FIELDS, "empty_layer"}
_RFC3339_UTC = (
    r"(?:[0-9]{4})-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z"
)

_EXPECTED_ENVIRONMENT = (
    "PATH=/opt/laya-runtime/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG=C.UTF-8",
    "GPG_KEY=A035C8C19219BA821ECEA86B64E628F8D684696D",
    "PYTHON_VERSION=3.11.10",
    "PYTHON_SHA256=07a4356e912900e61a15cb0949a06c4a05012e213ecd6b4e84d0f67aabbee372",
    "UV_LINK_MODE=copy",
    "UV_PYTHON_DOWNLOADS=never",
    "UV_PROJECT_ENVIRONMENT=/opt/laya-runtime/.venv",
    "LAYA_DEVICE=cpu",
    "LAYA_PRELOAD=1",
    "LAYA_MODELS=multilingual",
    "LAYA_AUTO_TASK=0",
    "LAYA_DEFAULT_MODEL=multilingual",
    "LAYA_REVISION=55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851",
    "HF_HUB_OFFLINE=1",
)

_EXPECTED_LABELS = {
    "org.aai-hydric.runtime.checkpoint-manifest.sha256": (
        "e54ad4cf767dd653c0703f3671e5317a5dca18c351bee2ab0b7943b5472900bf"
    ),
    "org.aai-hydric.runtime.config.sha256": (
        "9a14323b31c463add7188331ce2c98bb3afbd491e15d06b1f98838a917454b5f"
    ),
    "org.aai-hydric.runtime.sbom.sha256": (
        "f2fde1a342990e3b5b4d74d4930bf37f6d2229768b509a27f34edffc009a03b2"
    ),
    "org.aai-hydric.runtime.uv-lock.sha256": (
        "e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526"
    ),
    "org.opencontainers.image.base.digest": (
        "sha256:840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e"
    ),
    "org.opencontainers.image.base.name": "docker.io/library/python:3.11.10-slim-bookworm",
    "org.opencontainers.image.licenses": "Apache-2.0",
    "org.opencontainers.image.revision": "68804629e8ccd9d616d48a40e87de9fabbeae069",
    "org.opencontainers.image.source": "https://github.com/NandhaKishorM/laya",
    "org.opencontainers.image.version": "0.4.2",
}

_EXPECTED_DIFF_IDS = (
    "sha256:c0f1022b22a9b36851b358f44e5475e39d166e71a8073cf53c894a299239b1c5",
    "sha256:bc9155b10ccec596b3283ceca7cc847bc4046db14eab7f77b9b170b5e825e0a5",
    "sha256:0266a6d27cd42ef4422dfb0b6dbd4186f3524600502559e13947f8d4de65c931",
    "sha256:cfc6e3b5400ce78d3df9c4826f39a78db0e7e9a01d2581b860b5611ac6829af6",
    "sha256:3b0ebae606bef07327bd2eb738a1fbb118531d66d718cb0e4308a2a8ef6ee147",
    "sha256:32da0000f413e50749de746d1b8c6178ba367bb9fb8b071578b06b9f029fefaa",
    "sha256:4db0c1957d9b2082f64699c9af2a21da88c9db1afe5f1eb702d268a6a3beecb7",
    "sha256:5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef",
    "sha256:23a2fba237de474cf363c925aedf483647f31f2f3510e2dced6e629a319961b4",
    "sha256:1805c5276e5a93fa136190900c0469b491e778b00748a739c78e2698427e0758",
)

_EXPECTED_BLOBS = (
    (
        "manifest",
        _MANIFEST_MEDIA_TYPE,
        "sha256:7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0",
        3_166,
    ),
    ("config", _CONFIG_MEDIA_TYPE, "sha256:" + _CONFIG_SHA256, _CONFIG_SIZE_BYTES),
    (
        "layer-00",
        _LAYER_MEDIA_TYPE,
        "sha256:bc0965b23a04fe7f2d9fb20f597008fcf89891de1c705ffc1c80483a1f098e4f",
        28_231_580,
    ),
    (
        "layer-01",
        _LAYER_MEDIA_TYPE,
        "sha256:c58b365c3bcb57c930511e3fef962d15491ef2daba1e111fb5a6b41dbdecfc6b",
        3_317_301,
    ),
    (
        "layer-02",
        _LAYER_MEDIA_TYPE,
        "sha256:3bc3f72291794502343f023ab10455e459897b13a73f38b6b56cf266dccb7ec5",
        16_202_769,
    ),
    (
        "layer-03",
        _LAYER_MEDIA_TYPE,
        "sha256:42dacf6a4601de71542906f1be2bca5a78b8f430479b260a7097b9870498af69",
        251,
    ),
    (
        "layer-04",
        _LAYER_MEDIA_TYPE,
        "sha256:418d9aeceb23d76e9191b40d18f9c73816dc849ef0e1111a42343b73c8ccc51c",
        21_573_096,
    ),
    (
        "layer-05",
        _LAYER_MEDIA_TYPE,
        "sha256:ce65de5ef47521f33f7eb5bb76b05d5ff9c5a562e110b077449ff3af802803df",
        31_693_638,
    ),
    (
        "layer-06",
        _LAYER_MEDIA_TYPE,
        "sha256:eb0f362469da4169812e6a645b36eca3678d6aaf06acb0297850b2c525692398",
        11_510,
    ),
    (
        "layer-07",
        _LAYER_MEDIA_TYPE,
        "sha256:4f4fb700ef54461cfa02571ae0db9a0dc1e0cdb5577484a6d75e68dc38e8acc1",
        32,
    ),
    (
        "layer-08",
        _LAYER_MEDIA_TYPE,
        "sha256:890fbe6d21f33111795ef040fe123b712444c40bc1f4e93a940a8baf9a93d339",
        511_506_914,
    ),
    (
        "layer-09",
        _LAYER_MEDIA_TYPE,
        "sha256:f3d008f925e78af5c67f1e8b54aead83de30df814e105ff93e12f02c0d515c14",
        19_739,
    ),
)

_LAYOUT_TRUE_FLAGS = (
    "artifact_integrity_verified",
    "oci_manifest_semantics_verified",
    "oci_layout_controls_bytes_verified",
    "oci_blob_inventory_verified",
    "oci_same_root_capture_verified",
    "oci_manifest_blob_bytes_verified",
    "oci_config_blob_bytes_verified",
    "oci_layer_blobs_bytes_verified",
    "oci_bytes_verified",
)
_LAYOUT_FALSE_FLAGS = (
    "lock_verified",
    "sbom_verified",
    "lock_sbom_consistent",
    "runtime_config_semantics_verified",
    "checkpoint_manifest_semantics_verified",
    "checkpoint_bytes_verified",
    "oci_config_semantics_verified",
    "oci_layer_diff_ids_verified",
    "oci_rootfs_verified",
    "origin_verified",
    "license_verified",
    "base_ancestry_verified",
    "rootfs_materialized",
    "runtime_materialized",
    "executor_available",
    "inference_executed",
)
_CONFIG_TRUE_FLAGS = (*_LAYOUT_TRUE_FLAGS, "oci_config_semantics_verified")
_CONFIG_FALSE_FLAGS = tuple(
    flag for flag in _LAYOUT_FALSE_FLAGS if flag != "oci_config_semantics_verified"
)


class _ConfigValueError(ValueError):
    pass


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: validated private OCI config profile>"


@dataclass(frozen=True, slots=True, repr=False)
class ValidatedLayaRuntimeOciConfig:
    schema_version: str
    architecture: str
    operating_system: str
    created: str
    user: str
    entrypoint: tuple[str, ...]
    working_directory: str
    environment_count: int
    label_count: int
    diff_id_count: int
    declared_diff_ids: tuple[str, ...] = field(repr=False)
    history_count: int
    non_empty_history_count: int
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI config projection construction is factory-sealed")
        if (
            self.schema_version != OCI_CONFIG_PROFILE_SCHEMA
            or self.architecture != "amd64"
            or self.operating_system != "linux"
            or self.created != "1970-01-01T00:00:00Z"
            or self.user != "65532:65532"
            or self.entrypoint != ("laya-serve",)
            or self.working_directory != "/opt/laya-runtime"
            or self.environment_count != 15
            or self.label_count != 10
            or self.diff_id_count != 10
            or type(self.declared_diff_ids) is not tuple
            or self.declared_diff_ids != _EXPECTED_DIFF_IDS
            or self.diff_id_count != len(self.declared_diff_ids)
            or self.history_count != 21
            or self.non_empty_history_count != 10
        ):
            raise ValueError("OCI config projection validation failed")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeOciConfigEvidence:
    schema_version: str
    layout_evidence: runtime_oci_layout.LayaRuntimeOciLayoutEvidence = field(repr=False)
    config_receipt: runtime_oci_layout.VerifiedLayaOciBlob = field(repr=False)
    config: ValidatedLayaRuntimeOciConfig = field(repr=False)
    runtime_identity: object = field(repr=False)
    _factory_token: InitVar[object]
    artifact_integrity_verified: bool = field(init=False, default=True)
    oci_manifest_semantics_verified: bool = field(init=False, default=True)
    oci_layout_controls_bytes_verified: bool = field(init=False, default=True)
    oci_blob_inventory_verified: bool = field(init=False, default=True)
    oci_same_root_capture_verified: bool = field(init=False, default=True)
    oci_manifest_blob_bytes_verified: bool = field(init=False, default=True)
    oci_config_blob_bytes_verified: bool = field(init=False, default=True)
    oci_layer_blobs_bytes_verified: bool = field(init=False, default=True)
    oci_bytes_verified: bool = field(init=False, default=True)
    oci_config_semantics_verified: bool = field(init=False, default=True)
    lock_verified: bool = field(init=False, default=False)
    sbom_verified: bool = field(init=False, default=False)
    lock_sbom_consistent: bool = field(init=False, default=False)
    runtime_config_semantics_verified: bool = field(init=False, default=False)
    checkpoint_manifest_semantics_verified: bool = field(init=False, default=False)
    checkpoint_bytes_verified: bool = field(init=False, default=False)
    oci_layer_diff_ids_verified: bool = field(init=False, default=False)
    oci_rootfs_verified: bool = field(init=False, default=False)
    origin_verified: bool = field(init=False, default=False)
    license_verified: bool = field(init=False, default=False)
    base_ancestry_verified: bool = field(init=False, default=False)
    rootfs_materialized: bool = field(init=False, default=False)
    runtime_materialized: bool = field(init=False, default=False)
    executor_available: bool = field(init=False, default=False)
    inference_executed: bool = field(init=False, default=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI config evidence construction is factory-sealed")
        _validate_config_evidence_seal(self)

    __repr__ = _private_repr


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _ConfigValueError("OCI config JSON contains a duplicate key")
        result[key] = value
    return result


def _reject_nonfinite_number(_value: str) -> None:
    raise _ConfigValueError("OCI config JSON number must be finite")


def _raise_private(error_type: type[Exception], message: str) -> None:
    error = error_type(message)
    error.__suppress_context__ = True
    raise error


def _validate_json_limits(value: object, *, depth: int = 0, nodes: list[int]) -> None:
    nodes[0] += 1
    if nodes[0] > MAX_OCI_CONFIG_JSON_NODES:
        raise _ConfigValueError("OCI config JSON node limit exceeded")
    if depth > MAX_OCI_CONFIG_JSON_DEPTH:
        raise _ConfigValueError("OCI config JSON depth limit exceeded")
    if type(value) is str:
        if len(value) > MAX_OCI_CONFIG_STRING_LENGTH:
            raise _ConfigValueError("OCI config JSON string length limit exceeded")
        return
    if type(value) is dict:
        if len(value) > MAX_OCI_CONFIG_OBJECT_MEMBERS:
            raise _ConfigValueError("OCI config JSON object member limit exceeded")
        for key, item in value.items():
            if type(key) is not str or len(key) > MAX_OCI_CONFIG_STRING_LENGTH:
                raise _ConfigValueError("OCI config JSON key string limit exceeded")
            nodes[0] += 1
            if nodes[0] > MAX_OCI_CONFIG_JSON_NODES:
                raise _ConfigValueError("OCI config JSON node limit exceeded")
            _validate_json_limits(item, depth=depth + 1, nodes=nodes)
        return
    if type(value) is list:
        if len(value) > MAX_OCI_CONFIG_LIST_ITEMS:
            raise _ConfigValueError("OCI config JSON list item limit exceeded")
        for item in value:
            _validate_json_limits(item, depth=depth + 1, nodes=nodes)


def _is_rfc3339_utc(value: object) -> bool:
    if type(value) is not str or re.fullmatch(_RFC3339_UTC, value) is None:
        return False
    year = int(value[0:4])
    month = int(value[5:7])
    day = int(value[8:10])
    if year < 1:
        return False
    leap_year = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days_by_month = (31, 29 if leap_year else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return day <= days_by_month[month - 1]


def _validate_history(value: object) -> tuple[int, int]:
    if type(value) is not list or len(value) != 21:
        raise _ConfigValueError("OCI config history count is invalid")
    non_empty_count = 0
    for item in value:
        if type(item) is not dict or not _HISTORY_REQUIRED_FIELDS <= set(item):
            raise _ConfigValueError("OCI config history fields are invalid")
        if not set(item) <= _HISTORY_ALLOWED_FIELDS:
            raise _ConfigValueError("OCI config history fields are invalid")
        if not _is_rfc3339_utc(item["created"]):
            raise _ConfigValueError("OCI config history created RFC3339 value is invalid")
        if type(item["created_by"]) is not str:
            raise _ConfigValueError("OCI config history command type is invalid")
        if type(item["comment"]) is not str:
            raise _ConfigValueError("OCI config history comment type is invalid")
        if "empty_layer" in item:
            if item["empty_layer"] is not True:
                raise _ConfigValueError("OCI config history empty-layer value is invalid")
        else:
            non_empty_count += 1
    if non_empty_count != 10:
        raise _ConfigValueError("OCI config history non-empty count is invalid")
    return len(value), non_empty_count


def _validate_profile(value: object) -> ValidatedLayaRuntimeOciConfig:
    if type(value) is not dict or set(value) != _TOP_LEVEL_FIELDS:
        raise _ConfigValueError("OCI config top-level field profile is invalid")
    if value["architecture"] != "amd64" or type(value["architecture"]) is not str:
        raise _ConfigValueError("OCI config architecture profile is invalid")
    if value["os"] != "linux" or type(value["os"]) is not str:
        raise _ConfigValueError("OCI config platform profile is invalid")
    if value["created"] != "1970-01-01T00:00:00Z" or not _is_rfc3339_utc(value["created"]):
        raise _ConfigValueError("OCI config created RFC3339 profile is invalid")

    config = value["config"]
    if type(config) is not dict or set(config) != _CONFIG_FIELDS:
        raise _ConfigValueError("OCI config nested field profile is invalid")
    if config["User"] != "65532:65532" or type(config["User"]) is not str:
        raise _ConfigValueError("OCI config user profile is invalid")
    if type(config["Entrypoint"]) is not list or config["Entrypoint"] != ["laya-serve"]:
        raise _ConfigValueError("OCI config entrypoint profile is invalid")
    if config["WorkingDir"] != "/opt/laya-runtime" or type(config["WorkingDir"]) is not str:
        raise _ConfigValueError("OCI config working-directory profile is invalid")

    environment = config["Env"]
    if type(environment) is not list or environment != list(_EXPECTED_ENVIRONMENT):
        raise _ConfigValueError("OCI config environment offline profile is invalid")
    labels = config["Labels"]
    if (
        type(labels) is not dict
        or labels != _EXPECTED_LABELS
        or not all(type(key) is str and type(item) is str for key, item in labels.items())
    ):
        raise _ConfigValueError("OCI config label profile is invalid")

    rootfs = value["rootfs"]
    if type(rootfs) is not dict or set(rootfs) != {"type", "diff_ids"}:
        raise _ConfigValueError("OCI config rootfs field profile is invalid")
    diff_ids = rootfs["diff_ids"]
    if (
        rootfs["type"] != "layers"
        or type(rootfs["type"]) is not str
        or type(diff_ids) is not list
        or diff_ids != list(_EXPECTED_DIFF_IDS)
        or len(set(diff_ids)) != len(diff_ids)
    ):
        raise _ConfigValueError("OCI config rootfs diff-layer profile is invalid")

    history_count, non_empty_history_count = _validate_history(value["history"])
    return ValidatedLayaRuntimeOciConfig(
        schema_version=OCI_CONFIG_PROFILE_SCHEMA,
        architecture="amd64",
        operating_system="linux",
        created="1970-01-01T00:00:00Z",
        user="65532:65532",
        entrypoint=("laya-serve",),
        working_directory="/opt/laya-runtime",
        environment_count=len(environment),
        label_count=len(labels),
        diff_id_count=len(diff_ids),
        declared_diff_ids=tuple(diff_ids),
        history_count=history_count,
        non_empty_history_count=non_empty_history_count,
        _factory_token=_FACTORY_TOKEN,
    )


def _parse_laya_runtime_oci_config_bytes(payload: bytes) -> ValidatedLayaRuntimeOciConfig:
    """Parse exact immutable bytes into a minimal privacy-safe projection."""

    if type(payload) is not bytes:
        _raise_private(TypeError, "OCI config payload must be exact immutable bytes")
    if len(payload) > MAX_OCI_CONFIG_BYTES:
        _raise_private(ValueError, "OCI config payload size exceeds limit")

    decode_failed = False
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        decode_failed = True
    if decode_failed:
        _raise_private(ValueError, "OCI config payload is not strict UTF-8")

    parse_failed = False
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_number,
        )
    except (RecursionError, ValueError, TypeError):
        parse_failed = True
    if parse_failed:
        _raise_private(ValueError, "OCI config payload is not valid strict JSON")

    error_message = ""
    try:
        _validate_json_limits(value, nodes=[0])
        return _validate_profile(value)
    except (_ConfigValueError, RecursionError) as error:
        error_message = (
            str(error)
            if isinstance(error, _ConfigValueError)
            else "OCI config JSON depth limit exceeded"
        )
    _raise_private(ValueError, error_message or "OCI config validation failed")


def _rebuild_prior_oci_evidence(prior: object) -> object:
    snapshot = prior.snapshot
    manifest = snapshot.manifest
    manifest_specs = manifest.artifacts
    artifacts = snapshot.artifacts
    if (
        type(manifest_specs) is not tuple
        or type(artifacts) is not tuple
        or len(manifest_specs) != 5
        or len(artifacts) != len(manifest_specs)
    ):
        raise _ConfigValueError("OCI metadata snapshot collection is invalid")

    payload_by_path: dict[str, bytes] = {}
    for position, artifact in enumerate(artifacts):
        spec = artifact.spec
        expected_spec = manifest_specs[position]
        if spec != expected_spec or type(artifact.content) is not bytes:
            raise _ConfigValueError("OCI metadata snapshot artifact binding is invalid")
        if spec.path in payload_by_path:
            raise _ConfigValueError("OCI metadata snapshot artifact coverage is invalid")
        payload_by_path[spec.path] = artifact.content
    if len(payload_by_path) != len(manifest_specs):
        raise _ConfigValueError("OCI metadata snapshot artifact coverage is invalid")

    rebuilt_snapshot = verify_laya_runtime_artifact_bytes(manifest, payload_by_path)
    if rebuilt_snapshot is snapshot or type(rebuilt_snapshot) is not type(snapshot):
        raise _ConfigValueError("OCI metadata snapshot reconstruction is invalid")
    if (
        rebuilt_snapshot.manifest is not manifest
        or rebuilt_snapshot.schema_version != snapshot.schema_version
        or rebuilt_snapshot.runtime_identity != snapshot.runtime_identity
        or manifest.identity_sha256 != rebuilt_snapshot.runtime_identity.sha256
        or type(rebuilt_snapshot.artifacts) is not tuple
        or len(rebuilt_snapshot.artifacts) != len(manifest_specs)
        or tuple(item.spec for item in rebuilt_snapshot.artifacts) != manifest_specs
        or tuple(item.content for item in rebuilt_snapshot.artifacts)
        != tuple(payload_by_path[spec.path] for spec in manifest_specs)
    ):
        raise _ConfigValueError("OCI metadata rebuilt snapshot binding is invalid")

    snapshot_true_flags = ("artifact_integrity_verified",)
    snapshot_false_flags = (
        "lock_verified",
        "sbom_verified",
        "lock_sbom_consistent",
        "runtime_config_semantics_verified",
        "checkpoint_manifest_semantics_verified",
        "oci_manifest_semantics_verified",
        "runtime_materialized",
        "origin_verified",
        "executor_available",
        "inference_executed",
    )
    if any(getattr(snapshot, flag, None) is not True for flag in snapshot_true_flags) or any(
        getattr(snapshot, flag, None) is not False for flag in snapshot_false_flags
    ):
        raise _ConfigValueError("OCI metadata snapshot claim is invalid")
    manifest_true_flags = ("structurally_valid",)
    manifest_false_flags = (
        "artifact_integrity_verified",
        "lock_verified",
        "sbom_verified",
        "lock_sbom_consistent",
        "checkpoint_bytes_verified",
        "oci_bytes_verified",
        "runtime_materialized",
        "origin_verified",
        "executor_available",
        "inference_executed",
    )
    if any(getattr(manifest, flag, None) is not True for flag in manifest_true_flags) or any(
        getattr(manifest, flag, None) is not False for flag in manifest_false_flags
    ):
        raise _ConfigValueError("OCI metadata runtime manifest claim is invalid")

    rebuilt_prior = validate_laya_runtime_oci_metadata(rebuilt_snapshot)
    if type(rebuilt_prior) is not type(prior):
        raise _ConfigValueError("OCI metadata ancestry type is invalid")
    if (
        type(prior.schema_version) is not str
        or prior.schema_version != rebuilt_prior.schema_version
        or rebuilt_prior.snapshot is not rebuilt_snapshot
        or type(rebuilt_prior.oci_manifest) is not type(prior.oci_manifest)
        or rebuilt_prior.oci_manifest != prior.oci_manifest
        or type(rebuilt_prior.runtime_identity) is not type(prior.runtime_identity)
        or rebuilt_prior.runtime_identity != prior.runtime_identity
        or snapshot.runtime_identity != prior.runtime_identity
    ):
        raise _ConfigValueError("OCI metadata ancestry binding is invalid")
    prior_true_flags = (
        "artifact_integrity_verified",
        "oci_manifest_semantics_verified",
    )
    prior_false_flags = (
        "lock_verified",
        "sbom_verified",
        "lock_sbom_consistent",
        "runtime_config_semantics_verified",
        "checkpoint_manifest_semantics_verified",
        "checkpoint_bytes_verified",
        "oci_bytes_verified",
        "origin_verified",
        "runtime_materialized",
        "executor_available",
        "inference_executed",
    )
    if any(getattr(prior, flag, None) is not True for flag in prior_true_flags) or any(
        getattr(prior, flag, None) is not False for flag in prior_false_flags
    ):
        raise _ConfigValueError("OCI metadata ancestry claim is invalid")
    if any(
        getattr(prior, flag) is not getattr(rebuilt_prior, flag)
        for flag in (*prior_true_flags, *prior_false_flags)
    ):
        raise _ConfigValueError("OCI metadata rebuilt claims are inconsistent")
    return rebuilt_prior


def _revalidate_layout_evidence(
    layout_evidence: object,
) -> tuple[
    runtime_oci_layout.LayaRuntimeOciLayoutEvidence,
    runtime_oci_layout.VerifiedLayaOciBlob,
]:
    if type(layout_evidence) is not runtime_oci_layout.LayaRuntimeOciLayoutEvidence:
        raise _ConfigValueError("OCI layout evidence must be an exact sealed value")
    try:
        runtime_oci_layout.canonical_laya_runtime_oci_layout_summary_bytes(layout_evidence)
    except (TypeError, ValueError):
        raise _ConfigValueError("OCI layout evidence binding is invalid") from None
    if layout_evidence.schema_version != runtime_oci_layout.LAYOUT_EVIDENCE_SCHEMA:
        raise _ConfigValueError("OCI layout evidence schema is invalid")
    for flag in _LAYOUT_TRUE_FLAGS:
        if getattr(layout_evidence, flag, None) is not True:
            raise _ConfigValueError("OCI layout evidence positive claim flag is invalid")
    for flag in _LAYOUT_FALSE_FLAGS:
        if getattr(layout_evidence, flag, None) is not False:
            raise _ConfigValueError("OCI layout evidence conservative claim flag is invalid")

    plan = layout_evidence.plan
    if type(plan) is not runtime_oci_layout.LayaOciLayoutPlan:
        raise _ConfigValueError("OCI layout plan type is invalid")
    _rebuild_prior_oci_evidence(plan.oci_evidence)
    if (
        plan.schema_version != runtime_oci_layout.LAYOUT_PLAN_SCHEMA
        or plan.runtime_identity is not plan.oci_evidence.runtime_identity
        or layout_evidence.runtime_identity is not plan.runtime_identity
        or plan.control_paths != ("oci-layout", "index.json")
        or plan.control_file_count != 2
        or type(plan.blobs) is not tuple
        or len(plan.blobs) != len(_EXPECTED_BLOBS)
        or plan.blob_count != len(_EXPECTED_BLOBS)
        or plan.logical_file_count != len(_EXPECTED_BLOBS) + 2
    ):
        raise _ConfigValueError("OCI layout plan binding or count is invalid")

    for blob, expected in zip(plan.blobs, _EXPECTED_BLOBS):
        role, media_type, digest, size_bytes = expected
        if type(blob) is not runtime_oci_layout.LayaOciBlobPlan:
            raise _ConfigValueError("OCI layout blob descriptor type is invalid")
        if (
            blob.role != role
            or blob.media_type != media_type
            or blob.digest != digest
            or blob.size_bytes != size_bytes
            or blob.path != "blobs/sha256/" + digest.removeprefix("sha256:")
        ):
            raise _ConfigValueError("OCI layout blob descriptor profile is invalid")
    expected_total = sum(item[3] for item in _EXPECTED_BLOBS)
    if (
        plan.index_manifest is not plan.blobs[0]
        or plan.blob_total_size_bytes != expected_total
        or plan.total_size_bytes != expected_total + 30 + 423
    ):
        raise _ConfigValueError("OCI layout index or total binding is invalid")

    receipts = layout_evidence.receipts
    if type(receipts) is not tuple or len(receipts) != len(plan.blobs):
        raise _ConfigValueError("OCI layout receipt count is invalid")
    for position, receipt in enumerate(receipts):
        if (
            type(receipt) is not runtime_oci_layout.VerifiedLayaOciBlob
            or receipt.plan is not plan
            or receipt.blob is not plan.blobs[position]
            or receipt.blob_bytes_verified is not True
        ):
            raise _ConfigValueError("OCI layout receipt order or blob binding is invalid")
    config_positions = tuple(
        position for position, blob in enumerate(plan.blobs) if blob.role == "config"
    )
    if config_positions != (1,):
        raise _ConfigValueError("OCI layout config descriptor uniqueness is invalid")
    return layout_evidence, receipts[1]


def _revalidate_config_projection(config: object) -> ValidatedLayaRuntimeOciConfig:
    if type(config) is not ValidatedLayaRuntimeOciConfig:
        raise _ConfigValueError("OCI config projection type is invalid")
    try:
        config.__post_init__(_FACTORY_TOKEN)
    except (TypeError, ValueError):
        raise _ConfigValueError("OCI config projection binding is invalid") from None
    return config


def _validate_config_evidence_seal(evidence: object) -> None:
    if type(evidence) is not LayaRuntimeOciConfigEvidence:
        raise _ConfigValueError("OCI config evidence must be an exact sealed value")
    if evidence.schema_version != OCI_CONFIG_EVIDENCE_SCHEMA:
        raise _ConfigValueError("OCI config evidence schema binding is invalid")
    if type(evidence.layout_evidence) is not runtime_oci_layout.LayaRuntimeOciLayoutEvidence:
        raise _ConfigValueError("OCI config layout evidence binding is invalid")
    if type(evidence.config_receipt) is not runtime_oci_layout.VerifiedLayaOciBlob:
        raise _ConfigValueError("OCI config receipt binding is invalid")
    _revalidate_config_projection(evidence.config)
    if (
        type(evidence.layout_evidence.receipts) is not tuple
        or len(evidence.layout_evidence.receipts) < 2
        or evidence.config_receipt is not evidence.layout_evidence.receipts[1]
        or evidence.config_receipt.plan is not evidence.layout_evidence.plan
        or evidence.runtime_identity is not evidence.layout_evidence.runtime_identity
    ):
        raise _ConfigValueError("OCI config evidence binding is invalid")
    for flag in _CONFIG_TRUE_FLAGS:
        if getattr(evidence, flag, None) is not True:
            raise _ConfigValueError("OCI config evidence positive claim flag is invalid")
    for flag in _CONFIG_FALSE_FLAGS:
        if getattr(evidence, flag, None) is not False:
            raise _ConfigValueError("OCI config evidence conservative claim flag is invalid")


def _revalidate_config_evidence(
    evidence: object,
) -> LayaRuntimeOciConfigEvidence:
    _validate_config_evidence_seal(evidence)
    layout_evidence, config_receipt = _revalidate_layout_evidence(evidence.layout_evidence)
    if (
        evidence.config_receipt is not config_receipt
        or evidence.runtime_identity is not layout_evidence.runtime_identity
    ):
        raise _ConfigValueError("OCI config evidence binding is invalid")
    return evidence


def validate_laya_runtime_oci_config_semantics(
    layout_evidence: runtime_oci_layout.LayaRuntimeOciLayoutEvidence,
    config_bytes: bytes,
) -> LayaRuntimeOciConfigEvidence:
    """Bind exact config bytes and semantics to one deeply validated layout."""

    layout_failed = False
    try:
        validated_layout, config_receipt = _revalidate_layout_evidence(layout_evidence)
    except Exception:
        layout_failed = True
    if layout_failed:
        _raise_private(ValueError, "OCI layout evidence validation failed")
    if type(config_bytes) is not bytes:
        _raise_private(TypeError, "OCI config payload must be exact bytes")
    if len(config_bytes) != _CONFIG_SIZE_BYTES:
        _raise_private(ValueError, "OCI config payload size is invalid")
    if hashlib.sha256(config_bytes).hexdigest() != _CONFIG_SHA256:
        _raise_private(ValueError, "OCI config payload digest is invalid")
    config = _parse_laya_runtime_oci_config_bytes(config_bytes)
    return LayaRuntimeOciConfigEvidence(
        schema_version=OCI_CONFIG_EVIDENCE_SCHEMA,
        layout_evidence=validated_layout,
        config_receipt=config_receipt,
        config=config,
        runtime_identity=validated_layout.runtime_identity,
        _factory_token=_FACTORY_TOKEN,
    )


def canonical_laya_runtime_oci_config_summary_bytes(
    evidence: LayaRuntimeOciConfigEvidence,
) -> bytes:
    """Return a canonical privacy-safe summary after full deep revalidation."""

    validation_failed = False
    try:
        validated = _revalidate_config_evidence(evidence)
    except Exception:
        validation_failed = True
    if validation_failed:
        _raise_private(ValueError, "OCI config evidence binding validation failed")
    payload = {
        "schema_version": validated.schema_version,
        "profile_schema_version": validated.config.schema_version,
        "runtime_identity_schema_version": validated.runtime_identity.schema_version,
        "runtime_identity_sha256": validated.runtime_identity.sha256,
        **{flag: True for flag in _CONFIG_TRUE_FLAGS},
        **{flag: False for flag in _CONFIG_FALSE_FLAGS},
    }
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
