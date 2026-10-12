"""Pure validation of the closed Laya OCI runtime-config profile."""

from __future__ import annotations

import json
import re
from dataclasses import InitVar, dataclass

MAX_OCI_CONFIG_BYTES = 64 * 1_024
MAX_OCI_CONFIG_JSON_DEPTH = 32
MAX_OCI_CONFIG_OBJECT_MEMBERS = 64
MAX_OCI_CONFIG_LIST_ITEMS = 256
MAX_OCI_CONFIG_STRING_LENGTH = 4_096
MAX_OCI_CONFIG_JSON_NODES = 2_048
OCI_CONFIG_PROFILE_SCHEMA = "laya-runtime-oci-config-profile-v1"

_FACTORY_TOKEN = object()
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


class _ConfigTypeError(TypeError):
    pass


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
            or self.history_count != 21
            or self.non_empty_history_count != 10
        ):
            raise ValueError("OCI config projection validation failed")

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
    return type(value) is str and re.fullmatch(_RFC3339_UTC, value) is not None


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

    error_type: type[Exception] | None = None
    error_message = ""
    try:
        _validate_json_limits(value, nodes=[0])
        return _validate_profile(value)
    except _ConfigTypeError as error:
        error_type = TypeError
        error_message = str(error)
    except (_ConfigValueError, RecursionError) as error:
        error_type = ValueError
        error_message = (
            str(error)
            if isinstance(error, _ConfigValueError)
            else "OCI config JSON depth limit exceeded"
        )
    _raise_private(error_type or ValueError, error_message or "OCI config validation failed")
