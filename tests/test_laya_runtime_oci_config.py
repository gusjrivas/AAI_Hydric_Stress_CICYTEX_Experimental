import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

REAL_CONFIG_SIZE_BYTES = 10_261
REAL_CONFIG_SHA256 = "bdd27ffe0d14dd637985f09bcdf461e58a64348829a4b3ad3cb7886ff56e20c5"
PROFILE_SCHEMA = "laya-runtime-oci-config-profile-v1"
EVIDENCE_SCHEMA = "laya-runtime-oci-config-evidence-v1"
REAL_CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"
REAL_LAYOUT_GATE_ENV = "LAYA_RUNTIME_OCI_LAYOUT_ROOT"
MAX_CONFIG_BYTES = 64 * 1024
MAX_JSON_DEPTH = 32
MAX_OBJECT_MEMBERS = 64
MAX_LIST_ITEMS = 256
MAX_STRING_LENGTH = 4_096
MAX_JSON_NODES = 2_048
ALLOWED_PARSER_IMPORTS = {
    "__future__",
    "dataclasses",
    "hashlib",
    "human_feedback.runtime_bundle",
    "human_feedback.runtime_oci_layout",
    "human_feedback.runtime_oci_metadata",
    "json",
    "re",
    "typing",
}
FORBIDDEN_PARSER_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "import_module",
    "open",
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
    "run",
    "Popen",
    "system",
    "socket",
    "urlopen",
}
BASE_CREATED = "2024-10-18T23:23:40Z"
EPOCH_CREATED = "1970-01-01T00:00:00Z"
EMPTY_HISTORY_INDEXES = {1, 2, 4, 5, 6, 9, 14, 17, 18, 19, 20}

ENVIRONMENT = (
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
LABELS = {
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
MUTATED_LABEL_VALUES = {
    "org.aai-hydric.runtime.checkpoint-manifest.sha256": "a" * 64,
    "org.aai-hydric.runtime.config.sha256": "b" * 64,
    "org.aai-hydric.runtime.sbom.sha256": "c" * 64,
    "org.aai-hydric.runtime.uv-lock.sha256": "d" * 64,
    "org.opencontainers.image.base.digest": "sha256:" + "e" * 64,
    "org.opencontainers.image.base.name": "docker.io/library/python:3.11.11-slim-bookworm",
    "org.opencontainers.image.licenses": "MIT",
    "org.opencontainers.image.revision": "a" * 40,
    "org.opencontainers.image.source": "https://github.com/NandhaKishorM/laya-mutated",
    "org.opencontainers.image.version": "0.4.3",
}
DIFF_IDS = (
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


def _config_object() -> dict[str, object]:
    history = []
    for index in range(21):
        item = {
            "created": BASE_CREATED if index < 10 else EPOCH_CREATED,
            "created_by": f"synthetic-private-history-command-{index}",
            "comment": "debuerreotype 0.15" if index == 0 else "buildkit.dockerfile.v0",
        }
        if index in EMPTY_HISTORY_INDEXES:
            item["empty_layer"] = True
        history.append(item)
    return {
        "architecture": "amd64",
        "config": {
            "User": "65532:65532",
            "Env": list(ENVIRONMENT),
            "Entrypoint": ["laya-serve"],
            "WorkingDir": "/opt/laya-runtime",
            "Labels": dict(LABELS),
        },
        "created": EPOCH_CREATED,
        "history": history,
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": list(DIFF_IDS)},
    }


def _encoded(value: object | None = None, *, pretty: bool = False) -> bytes:
    actual = _config_object() if value is None else value
    return json.dumps(
        actual,
        ensure_ascii=True,
        sort_keys=pretty,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        allow_nan=False,
    ).encode("ascii")


def _parse(payload: bytes | None = None):
    from human_feedback.runtime_oci_config import _parse_laya_runtime_oci_config_bytes

    return _parse_laya_runtime_oci_config_bytes(_encoded() if payload is None else payload)


def _private_error(error: BaseException, *markers: str) -> None:
    rendered = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    for marker in markers:
        assert marker not in str(error)
        assert marker not in rendered
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True


def _parser_purity_violations(source: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(source)
    forbidden_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            forbidden_imports.update(
                alias.name for alias in node.names if alias.name not in ALLOWED_PARSER_IMPORTS
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level >= 1:
                forbidden_imports.add(f"relative:{node.level}:{node.module or ''}")
            elif node.module not in ALLOWED_PARSER_IMPORTS:
                forbidden_imports.add(node.module or "<missing-module>")
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } | {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    return forbidden_imports, called.intersection(FORBIDDEN_PARSER_CALLS)


def test_synthetic_profile_builder_sanity_does_not_embed_real_config_blob():
    # Constants were derived once from the read-only captured layout. This sanity test
    # deliberately proves that neither that blob nor its real history commands are a fixture.
    value = _config_object()
    payload = _encoded()
    assert set(value) == {"architecture", "config", "created", "history", "os", "rootfs"}
    assert set(value["config"]) == {"User", "Env", "Entrypoint", "WorkingDir", "Labels"}
    assert "Cmd" not in value["config"]
    assert len(value["history"]) == 21
    assert sum("empty_layer" not in item for item in value["history"]) == 10
    assert len(value["rootfs"]["diff_ids"]) == 10
    assert len(payload) != REAL_CONFIG_SIZE_BYTES
    import hashlib

    assert hashlib.sha256(payload).hexdigest() != REAL_CONFIG_SHA256


def test_exact_synthetic_profile_parses_to_minimal_validated_projection():
    from human_feedback.runtime_oci_config import ValidatedLayaRuntimeOciConfig

    parsed = _parse()
    assert type(parsed) is ValidatedLayaRuntimeOciConfig
    assert parsed.schema_version == PROFILE_SCHEMA
    assert parsed.architecture == "amd64"
    assert parsed.operating_system == "linux"
    assert parsed.created == EPOCH_CREATED
    assert parsed.user == "65532:65532"
    assert parsed.entrypoint == ("laya-serve",)
    assert parsed.working_directory == "/opt/laya-runtime"
    assert parsed.environment_count == 15
    assert parsed.label_count == 10
    assert parsed.diff_id_count == 10
    assert parsed.history_count == 21
    assert parsed.non_empty_history_count == 10
    assert _parse(_encoded(pretty=True)) == parsed


@pytest.mark.parametrize("invalid", [None, "{}", bytearray(b"{}"), memoryview(b"{}")])
def test_parser_accepts_only_exact_immutable_bytes(invalid):
    from human_feedback.runtime_oci_config import _parse_laya_runtime_oci_config_bytes

    with pytest.raises(TypeError, match="bytes|payload"):
        _parse_laya_runtime_oci_config_bytes(invalid)


@pytest.mark.parametrize(
    ("payload", "marker"),
    [
        (b"\xffprivate-invalid-utf8", "private-invalid-utf8"),
        (b'{"private-invalid-json":', "private-invalid-json"),
        (b'{"architecture":"amd64"} trailing-private-json', "trailing-private-json"),
        (b'{"architecture":"amd64","architecture":"private-duplicate"}', "private-duplicate"),
        (b'{"architecture":NaN}', "NaN"),
        (b'{"architecture":Infinity}', "Infinity"),
    ],
)
def test_utf8_json_duplicate_nonfinite_and_trailing_fail_privately(payload, marker):
    with pytest.raises(ValueError, match="JSON|UTF|payload|config") as captured:
        _parse(payload)
    _private_error(captured.value, marker)


def test_raw_size_cap_is_public_and_checked_before_json_loads(monkeypatch):
    from human_feedback import runtime_oci_config as module

    assert module.MAX_OCI_CONFIG_BYTES == MAX_CONFIG_BYTES
    monkeypatch.setattr(
        module.json,
        "loads",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("oversized config must fail before json.loads")
        ),
    )
    with pytest.raises(ValueError, match="size|limit|large|config"):
        module._parse_laya_runtime_oci_config_bytes(b"{" + b" " * MAX_CONFIG_BYTES)


@pytest.mark.parametrize("case", ["depth", "object", "list", "string", "nodes"])
def test_json_resource_caps_fail_closed_after_parse(monkeypatch, case):
    from human_feedback import runtime_oci_config as module

    assert module.MAX_OCI_CONFIG_JSON_DEPTH == MAX_JSON_DEPTH
    assert module.MAX_OCI_CONFIG_OBJECT_MEMBERS == MAX_OBJECT_MEMBERS
    assert module.MAX_OCI_CONFIG_LIST_ITEMS == MAX_LIST_ITEMS
    assert module.MAX_OCI_CONFIG_STRING_LENGTH == MAX_STRING_LENGTH
    assert module.MAX_OCI_CONFIG_JSON_NODES == MAX_JSON_NODES
    if case == "depth":
        value = "leaf"
        for _index in range(MAX_JSON_DEPTH + 1):
            value = {"node": value}
    elif case == "object":
        value = {f"k{index}": index for index in range(MAX_OBJECT_MEMBERS + 1)}
    elif case == "list":
        value = list(range(MAX_LIST_ITEMS + 1))
    elif case == "string":
        value = "x" * (MAX_STRING_LENGTH + 1)
    else:
        value = "leaf"
        for _level in range(4):
            value = [deepcopy(value) for _branch in range(8)]
    monkeypatch.setattr(module.json, "loads", lambda *_args, **_kwargs: value)
    with pytest.raises(ValueError, match="depth|member|list|string|node|limit|config"):
        module._parse_laya_runtime_oci_config_bytes(b'{"bounded":"synthetic"}')


def test_decoder_recursion_failure_is_private_and_normalized():
    marker = "private-recursion-payload-marker"
    payload = b"[" * 2_000 + json.dumps(marker).encode("ascii") + b"]" * 2_000
    with pytest.raises(ValueError, match="JSON|depth|config|payload") as captured:
        _parse(payload)
    _private_error(captured.value, marker)


@pytest.mark.parametrize("key", ["architecture", "config", "created", "history", "os", "rootfs"])
def test_top_level_schema_is_closed_and_complete(key):
    value = _config_object()
    del value[key]
    with pytest.raises(ValueError, match="field|key|profile|config"):
        _parse(_encoded(value))
    value = _config_object()
    value["private-extra-field"] = "private-top-marker"
    with pytest.raises(ValueError, match="field|key|profile|config") as captured:
        _parse(_encoded(value))
    _private_error(captured.value, "private-top-marker")


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("architecture", "arm64"),
        ("architecture", True),
        ("os", "windows"),
        ("os", None),
        ("created", "1970-01-01T00:00:00+00:00"),
        ("created", "not-rfc3339-private"),
    ],
)
def test_platform_and_created_are_exact(field, invalid):
    value = _config_object()
    value[field] = invalid
    with pytest.raises(
        ValueError, match="architecture|platform|created|RFC|profile|config"
    ) as captured:
        _parse(_encoded(value))
    if invalid == "not-rfc3339-private":
        _private_error(captured.value, invalid)


@pytest.mark.parametrize(
    "invalid_created",
    [
        "2025-02-29T00:00:00Z",
        "2024-02-30T00:00:00Z",
        "2025-04-31T00:00:00Z",
        "2025-02-31T00:00:00Z",
        "2024-02-29T00:00:00+00:00",
        "2024-02-29T00:00:00.000Z",
    ],
)
def test_history_created_rejects_invalid_calendar_dates_offsets_and_fractions_privately(
    invalid_created,
):
    value = _config_object()
    value["history"][0]["created"] = invalid_created
    with pytest.raises(ValueError, match="history|created|RFC|config") as captured:
        _parse(_encoded(value))
    _private_error(captured.value, invalid_created)


@pytest.mark.parametrize(
    "valid_created",
    [
        "2024-02-29T00:00:00Z",
        "2025-02-28T23:59:59Z",
        "2025-04-30T12:34:56Z",
        "2025-01-31T00:00:00Z",
        "2025-12-31T23:59:59Z",
    ],
)
def test_history_created_accepts_valid_leap_day_and_real_month_endpoints(valid_created):
    expected = _parse()
    value = _config_object()
    value["history"][0]["created"] = valid_created
    assert _parse(_encoded(value)) == expected


@pytest.mark.parametrize(
    ("case", "invalid"),
    [
        ("top", []),
        ("config", []),
        ("rootfs", []),
        ("history", {}),
        ("Env", {}),
        ("Labels", []),
        ("diff_ids", {}),
        ("Entrypoint", {}),
    ],
)
def test_all_profile_containers_reject_wrong_types(case, invalid):
    value = _config_object()
    if case == "top":
        value = invalid
    elif case in {"config", "rootfs", "history"}:
        value[case] = invalid
    elif case in {"Env", "Labels", "Entrypoint"}:
        value["config"][case] = invalid
    else:
        value["rootfs"][case] = invalid
    with pytest.raises(
        ValueError, match="field|profile|config|history|rootfs|environment|label|entrypoint"
    ):
        _parse(_encoded(value))


@pytest.mark.parametrize("key", ["User", "Env", "Entrypoint", "WorkingDir", "Labels"])
def test_nested_config_schema_is_closed_and_complete(key):
    value = _config_object()
    del value["config"][key]
    with pytest.raises(ValueError, match="field|key|profile|config"):
        _parse(_encoded(value))
    value = _config_object()
    value["config"]["Cmd"] = ["private-unobserved-cmd"]
    with pytest.raises(ValueError, match="field|key|profile|config") as captured:
        _parse(_encoded(value))
    _private_error(captured.value, "private-unobserved-cmd")


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("User", "0:0"),
        ("User", 65532),
        ("Entrypoint", ["python"]),
        ("Entrypoint", "laya-serve"),
        ("WorkingDir", "/tmp"),
        ("WorkingDir", True),
    ],
)
def test_runtime_process_fields_match_observed_profile(field, invalid):
    value = _config_object()
    value["config"][field] = invalid
    with pytest.raises(ValueError, match="user|entrypoint|working|profile|config"):
        _parse(_encoded(value))


@pytest.mark.parametrize("index", range(len(ENVIRONMENT)))
def test_each_environment_declaration_is_exact_and_private(index):
    value = _config_object()
    environment = value["config"]["Env"]
    name = environment[index].split("=", 1)[0]
    marker = f"private-mutated-environment-{index}"
    environment[index] = f"{name}={marker}"
    with pytest.raises(ValueError, match="environment|Env|offline|profile|config") as captured:
        _parse(_encoded(value))
    _private_error(captured.value, marker, environment[index])


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "reorder"])
def test_environment_is_exact_unique_ordered_and_offline(mutation):
    value = _config_object()
    environment = value["config"]["Env"]
    if mutation == "missing":
        environment.pop()
    elif mutation == "extra":
        environment.append("PRIVATE_EXTRA=1")
    elif mutation == "duplicate":
        environment[-1] = environment[0]
    elif mutation == "reorder":
        environment[0], environment[1] = environment[1], environment[0]
    with pytest.raises(ValueError, match="environment|Env|offline|profile|config"):
        _parse(_encoded(value))


@pytest.mark.parametrize("key", tuple(LABELS))
def test_each_label_declaration_is_exact_type_valid_and_private(key):
    value = _config_object()
    marker = MUTATED_LABEL_VALUES[key]
    value["config"]["Labels"][key] = marker
    with pytest.raises(ValueError, match="label|profile|config") as captured:
        _parse(_encoded(value))
    _private_error(captured.value, marker)


@pytest.mark.parametrize("mutation", ["missing", "extra", "wrong-type"])
def test_labels_are_exact_closed_and_typed(mutation):
    value = _config_object()
    labels = value["config"]["Labels"]
    key = "org.opencontainers.image.version"
    if mutation == "missing":
        del labels[key]
    elif mutation == "extra":
        labels["private.extra.label"] = "private-label-marker"
    else:
        labels[key] = True
    with pytest.raises(ValueError, match="label|profile|config") as captured:
        _parse(_encoded(value))
    _private_error(captured.value, "private-label-marker")


@pytest.mark.parametrize(
    "mutation", ["type", "missing", "extra", "reorder", "duplicate", "grammar"]
)
def test_rootfs_is_exact_ordered_unique_sha256_profile(mutation):
    value = _config_object()
    rootfs = value["rootfs"]
    if mutation == "type":
        rootfs["type"] = "private-other-rootfs"
    elif mutation == "missing":
        rootfs["diff_ids"].pop()
    elif mutation == "extra":
        rootfs["diff_ids"].append("sha256:" + "a" * 64)
    elif mutation == "reorder":
        rootfs["diff_ids"][0], rootfs["diff_ids"][1] = (
            rootfs["diff_ids"][1],
            rootfs["diff_ids"][0],
        )
    elif mutation == "duplicate":
        rootfs["diff_ids"][1] = rootfs["diff_ids"][0]
    else:
        rootfs["diff_ids"][0] = "sha512:" + "a" * 64
    with pytest.raises(ValueError, match="rootfs|diff|layer|profile|config") as captured:
        _parse(_encoded(value))
    if mutation == "type":
        _private_error(captured.value, "private-other-rootfs")


@pytest.mark.parametrize("index", range(len(DIFF_IDS)))
def test_each_declared_diff_id_is_exact_but_does_not_claim_layer_verification(index):
    """This closes the expected declaration; it does not verify layers, rootfs, or origin."""

    value = _config_object()
    marker = "sha256:" + f"{index + 1:064x}"
    assert marker not in DIFF_IDS
    value["rootfs"]["diff_ids"][index] = marker
    with pytest.raises(ValueError, match="rootfs|diff|layer|profile|config") as captured:
        _parse(_encoded(value))
    _private_error(captured.value, marker)


@pytest.mark.parametrize(
    "mutation",
    [
        "count",
        "non-empty-count",
        "keys",
        "timestamp",
        "empty-false",
        "comment-type",
        "command-type",
    ],
)
def test_history_schema_types_counts_and_timestamp_rules_are_enforced(mutation):
    value = _config_object()
    history = value["history"]
    if mutation == "count":
        history.pop()
    elif mutation == "non-empty-count":
        history[0]["empty_layer"] = True
    elif mutation == "keys":
        history[0]["private"] = "private-history-marker"
    elif mutation == "timestamp":
        history[0]["created"] = "private-invalid-timestamp"
    elif mutation == "empty-false":
        history[1]["empty_layer"] = False
    elif mutation == "comment-type":
        history[0]["comment"] = ["private-comment"]
    else:
        history[0]["created_by"] = ["private-command"]
    with pytest.raises(
        ValueError, match="history|created|RFC|comment|command|profile|config"
    ) as captured:
        _parse(_encoded(value))
    _private_error(
        captured.value,
        "private-history-marker",
        "private-invalid-timestamp",
        "private-comment",
        "private-command",
    )


def test_history_command_comment_timestamp_values_and_empty_positions_are_not_overfit():
    expected = _parse()
    value = _config_object()
    for index, item in enumerate(value["history"]):
        item["created"] = "2025-02-03T04:05:06Z"
        item["created_by"] = f"alternate-private-command-{index}"
        item["comment"] = f"alternate-private-comment-{index}"
    del value["history"][1]["empty_layer"]
    value["history"][0]["empty_layer"] = True
    assert _parse(_encoded(value)) == expected


def test_validated_projection_is_frozen_slotted_factory_sealed_and_opaque():
    from human_feedback.runtime_oci_config import ValidatedLayaRuntimeOciConfig

    parsed = _parse()
    assert is_dataclass(parsed)
    assert not hasattr(parsed, "__dict__")
    rendered = repr(parsed)
    private_values = (
        *ENVIRONMENT,
        *LABELS,
        *LABELS.values(),
        *MUTATED_LABEL_VALUES.values(),
        *DIFF_IDS,
        BASE_CREATED,
        EPOCH_CREATED,
        "synthetic-private",
        "alternate-private",
        *(f"private-mutated-environment-{index}" for index in range(len(ENVIRONMENT))),
    )
    assert all(value not in rendered for value in private_values)
    retained_projection = repr(tuple(getattr(parsed, field.name) for field in fields(parsed)))
    assert "synthetic-private-history-command" not in retained_projection
    for field in fields(parsed):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(parsed, field.name, getattr(parsed, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
            replace(parsed, **{field.name: getattr(parsed, field.name)})
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        ValidatedLayaRuntimeOciConfig(
            schema_version=PROFILE_SCHEMA,
            architecture="amd64",
            operating_system="linux",
            created=EPOCH_CREATED,
            user="65532:65532",
            entrypoint=("laya-serve",),
            working_directory="/opt/laya-runtime",
            environment_count=15,
            label_count=10,
            diff_id_count=10,
            history_count=21,
            non_empty_history_count=10,
        )


def test_parser_purity_detector_accepts_only_intended_pure_stdlib():
    source = """
from __future__ import annotations
from dataclasses import dataclass
import json
import re
from typing import Any

json.loads("{}")
re.fullmatch("x", "x")
"""
    assert _parser_purity_violations(source) == (set(), set())


@pytest.mark.parametrize(
    "source",
    [
        "from . import runtime_oci_layout",
        "from .runtime_oci_layout import LayaOciLayoutPlan",
        "from ..runtime_oci_layout import LayaOciLayoutPlan",
        "import os",
        "from pathlib import Path",
        "__import__('os')",
        "import importlib\nimportlib.import_module('os')",
        "compile('x', 'private.py', 'exec')",
        "eval('1')",
        "exec('x = 1')",
        "open('private')",
        "Path('private').read_bytes()",
        "Path('private').read_text()",
        "Path('private').write_bytes(b'x')",
        "Path('private').write_text('x')",
        "subprocess.run([])",
        "subprocess.Popen([])",
        "os.system('private')",
        "socket.socket()",
        "urllib.request.urlopen('https://private.invalid')",
    ],
)
def test_parser_purity_detector_rejects_relative_dynamic_and_effectful_snippets(source):
    imports, calls = _parser_purity_violations(source)
    assert imports or calls


def test_module_public_surface_and_purity_are_exactly_allowlisted():
    from human_feedback import runtime_oci_config as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert _parser_purity_violations(source) == (set(), set())
    private_exception_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name.startswith("_")
        and any(
            isinstance(base, ast.Name) and base.id in {"TypeError", "ValueError"}
            for base in node.bases
        )
    }
    constructed_private_exceptions = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in private_exception_classes
    }
    assert "_ConfigTypeError" not in private_exception_classes
    assert private_exception_classes <= constructed_private_exceptions
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_functions == {
        "validate_laya_runtime_oci_config_semantics",
        "canonical_laya_runtime_oci_config_summary_bytes",
    }
    public_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    assert public_classes == {
        "ValidatedLayaRuntimeOciConfig",
        "LayaRuntimeOciConfigEvidence",
    }
    public_constants = {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
        if isinstance(target, ast.Name) and target.id.isupper() and not target.id.startswith("_")
    }
    assert public_constants == {
        "MAX_OCI_CONFIG_BYTES",
        "MAX_OCI_CONFIG_JSON_DEPTH",
        "MAX_OCI_CONFIG_OBJECT_MEMBERS",
        "MAX_OCI_CONFIG_LIST_ITEMS",
        "MAX_OCI_CONFIG_STRING_LENGTH",
        "MAX_OCI_CONFIG_JSON_NODES",
        "OCI_CONFIG_PROFILE_SCHEMA",
        "OCI_CONFIG_EVIDENCE_SCHEMA",
    }


COMPOSITION_SYMBOLS = {
    "LayaRuntimeOciConfigEvidence",
    "validate_laya_runtime_oci_config_semantics",
    "canonical_laya_runtime_oci_config_summary_bytes",
}
LAYOUT_TRUE_FLAGS = (
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
LAYOUT_FALSE_FLAGS = (
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
CONFIG_TRUE_FLAGS = (*LAYOUT_TRUE_FLAGS, "oci_config_semantics_verified")
CONFIG_FALSE_FLAGS = (
    "lock_verified",
    "sbom_verified",
    "lock_sbom_consistent",
    "runtime_config_semantics_verified",
    "checkpoint_manifest_semantics_verified",
    "checkpoint_bytes_verified",
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


def _uses_config_composition(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == "human_feedback.runtime_oci_config" for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom):
            if node.module == "human_feedback" and any(
                alias.name == "runtime_oci_config" for alias in node.names
            ):
                return True
            if node.module == "human_feedback.runtime_oci_config":
                return True
            if node.level and (
                node.module == "runtime_oci_config"
                or (
                    node.module in {None, ""}
                    and any(alias.name == "runtime_oci_config" for alias in node.names)
                )
            ):
                return True
        if isinstance(node, ast.Name) and node.id in COMPOSITION_SYMBOLS:
            return True
        if isinstance(node, ast.Attribute) and node.attr in COMPOSITION_SYMBOLS:
            return True
        if isinstance(node, ast.Constant) and node.value in {
            "human_feedback.runtime_oci_config",
            *COMPOSITION_SYMBOLS,
        }:
            return True
    return False


def test_no_product_module_calls_config_composition_contract():
    repository = Path(__file__).parents[1]
    owner = repository / "src" / "human_feedback" / "runtime_oci_config.py"
    offenders = []
    for relative_root in ("backend", "src", "scripts"):
        root = repository / relative_root
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if path == owner:
                continue
            if _uses_config_composition(path.read_text(encoding="utf-8")):
                offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []


@pytest.mark.parametrize(
    "source",
    [
        "import human_feedback.runtime_oci_config",
        "from human_feedback import runtime_oci_config",
        "from human_feedback.runtime_oci_config import ValidatedLayaRuntimeOciConfig",
        "from human_feedback.runtime_oci_config import _parse_laya_runtime_oci_config_bytes",
        "from human_feedback.runtime_oci_config import *",
        "from . import runtime_oci_config",
        "from .runtime_oci_config import ValidatedLayaRuntimeOciConfig",
    ],
)
def test_config_composition_caller_detector_rejects_every_owner_import_form(source):
    assert _uses_config_composition(source) is True


def test_validator_rejects_proxy_subclass_and_unsealed_layout_before_config_access(monkeypatch):
    from human_feedback import runtime_oci_config as module
    from human_feedback.runtime_oci_layout import LayaRuntimeOciLayoutEvidence

    accesses = 0

    class HostileConfig:
        def __bytes__(self):
            nonlocal accesses
            accesses += 1
            raise AssertionError("config bytes must not be coerced")

        def __len__(self):
            nonlocal accesses
            accesses += 1
            raise AssertionError("config bytes must not be sized")

    class LayoutSubclass(LayaRuntimeOciLayoutEvidence):
        pass

    invalid_layouts = (
        SimpleNamespace(oci_bytes_verified=True),
        object.__new__(LayoutSubclass),
        object.__new__(LayaRuntimeOciLayoutEvidence),
    )
    monkeypatch.setattr(
        module,
        "_parse_laya_runtime_oci_config_bytes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("parser must not run for invalid layout evidence")
        ),
    )
    for invalid in invalid_layouts:
        with pytest.raises(
            (TypeError, ValueError), match="layout|evidence|sealed|valid"
        ) as captured:
            module.validate_laya_runtime_oci_config_semantics(invalid, HostileConfig())
        _private_error(captured.value, "config bytes must not")
    assert accesses == 0


def test_config_evidence_and_summary_reject_direct_proxy_and_unsealed_values():
    from human_feedback.runtime_oci_config import (
        LayaRuntimeOciConfigEvidence,
        canonical_laya_runtime_oci_config_summary_bytes,
    )

    with pytest.raises((TypeError, ValueError), match="factory|seal|layout|valid"):
        LayaRuntimeOciConfigEvidence(
            schema_version=EVIDENCE_SCHEMA,
            layout_evidence=None,
            config_receipt=None,
            config=None,
            runtime_identity=None,
        )
    for invalid in (
        None,
        SimpleNamespace(schema_version=EVIDENCE_SCHEMA),
        object.__new__(LayaRuntimeOciConfigEvidence),
    ):
        with pytest.raises((TypeError, ValueError), match="evidence|sealed|valid"):
            canonical_laya_runtime_oci_config_summary_bytes(invalid)


def test_normal_suite_has_no_committed_config_blob_or_fabricated_positive_gate(monkeypatch):
    monkeypatch.delenv(REAL_LAYOUT_GATE_ENV, raising=False)
    repository = Path(__file__).parents[1]
    assert os.environ.get(REAL_LAYOUT_GATE_ENV) is None
    git = shutil.which("git")
    if git is not None:
        encoded_paths = subprocess.run(
            [git, "-c", f"safe.directory={repository}", "ls-files", "-z"],
            cwd=repository,
            check=True,
            capture_output=True,
        ).stdout.split(b"\0")
        paths = (repository / os.fsdecode(encoded) for encoded in encoded_paths if encoded)
    else:
        # Minimal test images may omit Git. Scanning every regular workspace file is a
        # conservative superset of tracked files and still excludes the .git boundary.
        paths = (
            path
            for path in repository.rglob("*")
            if ".git" not in path.relative_to(repository).parts
        )
    candidates = [
        path for path in paths if path.is_file() and path.stat().st_size == REAL_CONFIG_SIZE_BYTES
    ]
    assert all(
        hashlib.sha256(path.read_bytes()).hexdigest() != REAL_CONFIG_SHA256 for path in candidates
    )


@pytest.mark.skipif(
    not sys.platform.startswith("linux") or not os.environ.get(REAL_LAYOUT_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
def test_opt_in_real_config_bytes_produce_digest_bound_conservative_evidence(monkeypatch):
    from human_feedback import runtime_bundle, runtime_oci_metadata
    from human_feedback import runtime_oci_config as module
    from human_feedback.adapters.filesystem_oci_layout import (
        capture_and_verify_laya_oci_layout,
    )
    from human_feedback.runtime_oci_config import LayaRuntimeOciConfigEvidence
    from tests.test_laya_runtime_oci_layout import _oci_evidence
    from tests.test_laya_runtime_oci_layout_filesystem import _tree_fingerprint

    assert "PYTEST_XDIST_WORKER" not in os.environ, "external OCI gate must run serially"
    root = Path(os.environ[REAL_LAYOUT_GATE_ENV])
    before = _tree_fingerprint(root)
    layout_evidence = capture_and_verify_laya_oci_layout(_oci_evidence(), root)
    config_positions = [
        index for index, blob in enumerate(layout_evidence.plan.blobs) if blob.role == "config"
    ]
    assert config_positions == [1]
    position = config_positions[0]
    descriptor = layout_evidence.plan.blobs[position]
    receipt = layout_evidence.receipts[position]
    assert descriptor.media_type == REAL_CONFIG_MEDIA_TYPE
    assert descriptor.size_bytes == REAL_CONFIG_SIZE_BYTES
    assert descriptor.digest == "sha256:" + REAL_CONFIG_SHA256
    assert receipt.plan is layout_evidence.plan
    assert receipt.blob is descriptor
    assert receipt.blob_bytes_verified is True
    payload = (root / descriptor.path).read_bytes()
    assert len(payload) == REAL_CONFIG_SIZE_BYTES
    assert hashlib.sha256(payload).hexdigest() == REAL_CONFIG_SHA256

    original_parser = module._parse_laya_runtime_oci_config_bytes
    parsed_projections = []

    def parser_spy(config_bytes):
        projection = original_parser(config_bytes)
        parsed_projections.append(projection)
        return projection

    monkeypatch.setattr(module, "_parse_laya_runtime_oci_config_bytes", parser_spy)
    rebuild_events = []
    rebuilt_snapshots = []
    bundle_inputs = []
    original_bundle_verifier = runtime_bundle.verify_laya_runtime_artifact_bytes

    def bundle_verifier_spy(manifest, payload_by_path):
        rebuild_events.append("bundle")
        bundle_inputs.append((manifest, payload_by_path))
        rebuilt = original_bundle_verifier(manifest, payload_by_path)
        rebuilt_snapshots.append(rebuilt)
        return rebuilt

    monkeypatch.setattr(
        runtime_bundle,
        "verify_laya_runtime_artifact_bytes",
        bundle_verifier_spy,
    )
    monkeypatch.setattr(
        module,
        "verify_laya_runtime_artifact_bytes",
        bundle_verifier_spy,
        raising=False,
    )
    original_metadata_validator = runtime_oci_metadata.validate_laya_runtime_oci_metadata
    validated_snapshots = []

    def metadata_validator_spy(snapshot):
        rebuild_events.append("metadata")
        validated_snapshots.append(snapshot)
        return original_metadata_validator(snapshot)

    monkeypatch.setattr(
        runtime_oci_metadata,
        "validate_laya_runtime_oci_metadata",
        metadata_validator_spy,
    )
    monkeypatch.setattr(
        module,
        "validate_laya_runtime_oci_metadata",
        metadata_validator_spy,
        raising=False,
    )
    evidence = module.validate_laya_runtime_oci_config_semantics(layout_evidence, payload)
    assert len(parsed_projections) == 1
    assert rebuild_events == ["bundle", "metadata"]
    assert len(rebuilt_snapshots) == 1
    assert len(bundle_inputs) == 1
    assert bundle_inputs[0][0] is layout_evidence.plan.oci_evidence.snapshot.manifest
    assert type(bundle_inputs[0][1]) is dict
    assert bundle_inputs[0][1] == {
        artifact.spec.path: artifact.content
        for artifact in layout_evidence.plan.oci_evidence.snapshot.artifacts
    }
    assert type(rebuilt_snapshots[0]) is type(layout_evidence.plan.oci_evidence.snapshot)
    assert rebuilt_snapshots[0] == layout_evidence.plan.oci_evidence.snapshot
    assert (
        rebuilt_snapshots[0].runtime_identity
        == layout_evidence.plan.oci_evidence.snapshot.runtime_identity
    )
    assert validated_snapshots == [layout_evidence.plan.oci_evidence.snapshot]
    assert validated_snapshots[0] is rebuilt_snapshots[0]
    assert type(evidence) is LayaRuntimeOciConfigEvidence
    assert is_dataclass(evidence)
    assert not hasattr(evidence, "__dict__")
    assert evidence.schema_version == EVIDENCE_SCHEMA
    assert evidence.layout_evidence is layout_evidence
    assert evidence.config_receipt is receipt
    assert type(evidence.config) is module.ValidatedLayaRuntimeOciConfig
    assert evidence.config is parsed_projections[0]
    assert evidence.runtime_identity is layout_evidence.runtime_identity
    for flag in CONFIG_TRUE_FLAGS:
        assert getattr(evidence, flag) is True
    for flag in CONFIG_FALSE_FLAGS:
        assert getattr(evidence, flag) is False
    assert not hasattr(evidence, "oci_config_same_fd_verified")
    assert not hasattr(evidence, "oci_config_current_path_verified")

    def forged_dataclass(value, **changes):
        forged = object.__new__(type(value))
        for field in fields(value):
            object.__setattr__(
                forged,
                field.name,
                changes.get(field.name, getattr(value, field.name)),
            )
        return forged

    def populated_clone(value, target_type=None):
        clone = object.__new__(type(value) if target_type is None else target_type)
        for field in fields(value):
            object.__setattr__(clone, field.name, getattr(value, field.name))
        return clone

    def populated_proxy(value, *, marker):
        return SimpleNamespace(
            **{field.name: getattr(value, field.name) for field in fields(value)},
            marker=marker,
        )

    def private_strings(value):
        if isinstance(value, str):
            return (value,)
        if isinstance(value, dict):
            return tuple(marker for item in value.items() for marker in private_strings(item))
        if isinstance(value, (tuple, list)):
            return tuple(marker for item in value for marker in private_strings(item))
        return ()

    def evidence_with_layout(corrupt_layout):
        return forged_dataclass(
            evidence,
            layout_evidence=corrupt_layout,
            config_receipt=corrupt_layout.receipts[position],
            runtime_identity=corrupt_layout.runtime_identity,
        )

    def layout_with_prior(corrupt_prior, *, runtime_identity=None):
        identity = (
            layout_evidence.runtime_identity if runtime_identity is None else runtime_identity
        )
        plan = forged_dataclass(
            layout_evidence.plan,
            oci_evidence=corrupt_prior,
            runtime_identity=identity,
        )
        receipts = tuple(forged_dataclass(item, plan=plan) for item in layout_evidence.receipts)
        return forged_dataclass(
            layout_evidence,
            plan=plan,
            receipts=receipts,
            runtime_identity=identity,
        )

    original_config_hashlib = module.hashlib
    config_hash_calls = []

    def config_hash_spy(config_bytes):
        config_hash_calls.append(config_bytes)
        return original_config_hashlib.sha256(config_bytes)

    def assert_ancestry_rejected(corrupt_prior, *markers, runtime_identity=None):
        corrupt_layout = layout_with_prior(
            corrupt_prior,
            runtime_identity=runtime_identity,
        )
        corrupt_evidence = evidence_with_layout(corrupt_layout)
        parsed_projections.clear()
        config_hash_calls.clear()
        event_position = len(rebuild_events)
        monkeypatch.setattr(
            module,
            "hashlib",
            SimpleNamespace(sha256=config_hash_spy),
        )
        with pytest.raises(
            (TypeError, ValueError),
            match="metadata|ancestry|snapshot|manifest|identity|layout|evidence|valid",
        ) as validator_error:
            module.validate_laya_runtime_oci_config_semantics(corrupt_layout, payload)
        with pytest.raises(
            (TypeError, ValueError),
            match="metadata|ancestry|snapshot|manifest|identity|layout|evidence|valid",
        ) as summary_error:
            module.canonical_laya_runtime_oci_config_summary_bytes(corrupt_evidence)
        assert parsed_projections == []
        assert config_hash_calls == []
        pending_bundle = 0
        for event in rebuild_events[event_position:]:
            if event == "bundle":
                pending_bundle += 1
            else:
                assert event == "metadata"
                assert pending_bundle > 0
                pending_bundle -= 1
        _private_error(validator_error.value, *markers, str(root), descriptor.digest)
        _private_error(summary_error.value, *markers, str(root), descriptor.digest)

    prior = layout_evidence.plan.oci_evidence

    def assert_ancestry_canonicalized(candidate_prior):
        candidate_layout = layout_with_prior(
            candidate_prior,
            runtime_identity=candidate_prior.runtime_identity,
        )
        event_position = len(rebuild_events)
        rebuilt_position = len(rebuilt_snapshots)
        validated_position = len(validated_snapshots)
        parsed_position = len(parsed_projections)
        canonical_evidence = module.validate_laya_runtime_oci_config_semantics(
            candidate_layout,
            payload,
        )
        canonical_summary = module.canonical_laya_runtime_oci_config_summary_bytes(
            canonical_evidence
        )
        assert rebuild_events[event_position:] == [
            "bundle",
            "metadata",
            "bundle",
            "metadata",
        ]
        assert len(parsed_projections) == parsed_position + 1
        new_rebuilt = rebuilt_snapshots[rebuilt_position:]
        new_validated = validated_snapshots[validated_position:]
        assert len(new_rebuilt) == len(new_validated) == 2
        for rebuilt, validated in zip(new_rebuilt, new_validated):
            assert type(rebuilt) is type(prior.snapshot)
            assert rebuilt is not candidate_prior.snapshot
            assert type(rebuilt.artifacts) is tuple
            assert all(
                type(item) is type(prior.snapshot.artifacts[0]) for item in rebuilt.artifacts
            )
            assert tuple(item.spec for item in rebuilt.artifacts) == rebuilt.manifest.artifacts
            assert validated is rebuilt
        assert canonical_evidence.layout_evidence is candidate_layout
        assert canonical_evidence.runtime_identity == candidate_prior.runtime_identity
        assert json.loads(canonical_summary)["oci_config_semantics_verified"] is True
        assert "private-" not in repr(canonical_evidence) + canonical_summary.decode("ascii")
        return canonical_evidence

    class BundleSnapshotSubclass(type(prior.snapshot)):
        pass

    exact_snapshot_clone = populated_clone(prior.snapshot)
    exact_prior_clone = populated_clone(prior)
    object.__setattr__(exact_prior_clone, "snapshot", exact_snapshot_clone)
    assert_ancestry_canonicalized(exact_prior_clone)

    for reconstructed, marker in (
        (SimpleNamespace(marker="private-rebuilt-bundle-proxy"), "private-rebuilt-bundle-proxy"),
        (object.__new__(BundleSnapshotSubclass), "private-rebuilt-bundle-subclass"),
        (object.__new__(type(prior.snapshot)), "private-rebuilt-bundle-incomplete"),
    ):
        monkeypatch.setattr(
            module,
            "verify_laya_runtime_artifact_bytes",
            lambda _manifest, _payloads, value=reconstructed: value,
        )
        assert_ancestry_rejected(prior, marker)
    monkeypatch.setattr(
        module,
        "verify_laya_runtime_artifact_bytes",
        lambda _manifest, _payloads: prior.snapshot,
    )
    assert_ancestry_rejected(
        forged_dataclass(prior, artifact_integrity_verified=False),
        "private-rebuilt-bundle-must-not-wash-outer",
    )
    monkeypatch.setattr(
        module,
        "verify_laya_runtime_artifact_bytes",
        bundle_verifier_spy,
    )

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
    for flag in prior_true_flags:
        for invalid in (False, 1, None):
            assert_ancestry_rejected(forged_dataclass(prior, **{flag: invalid}))
    for flag in prior_false_flags:
        for invalid in (True, 1, None):
            assert_ancestry_rejected(forged_dataclass(prior, **{flag: invalid}))

    class PriorSubclass(type(prior)):
        pass

    class ManifestSubclass(type(prior.oci_manifest)):
        pass

    class SnapshotSubclass(type(prior.snapshot)):
        pass

    class HostilePrior:
        @property
        def snapshot(self):
            raise AssertionError("private-hostile-prior-property")

    class HostileManifest:
        @property
        def schema_version(self):
            raise AssertionError("private-hostile-manifest-property")

    class HostileSnapshot:
        @property
        def artifact_integrity_verified(self):
            raise AssertionError("private-hostile-snapshot-property")

    invalid_priors = (
        (SimpleNamespace(schema_version=prior.schema_version), "private-prior-proxy"),
        (object.__new__(PriorSubclass), "private-prior-subclass"),
        (object.__new__(type(prior)), "private-prior-incomplete"),
        (HostilePrior(), "private-hostile-prior-property"),
        (
            forged_dataclass(
                prior,
                oci_manifest=SimpleNamespace(marker="private-manifest-proxy"),
            ),
            "private-manifest-proxy",
        ),
        (
            forged_dataclass(prior, oci_manifest=object.__new__(ManifestSubclass)),
            "private-manifest-subclass",
        ),
        (
            forged_dataclass(prior, oci_manifest=object.__new__(type(prior.oci_manifest))),
            "private-manifest-incomplete",
        ),
        (
            forged_dataclass(prior, oci_manifest=HostileManifest()),
            "private-hostile-manifest-property",
        ),
        (
            forged_dataclass(
                prior,
                snapshot=SimpleNamespace(marker="private-snapshot-proxy"),
            ),
            "private-snapshot-proxy",
        ),
        (
            forged_dataclass(prior, snapshot=object.__new__(SnapshotSubclass)),
            "private-snapshot-subclass",
        ),
        (
            forged_dataclass(prior, snapshot=object.__new__(type(prior.snapshot))),
            "private-snapshot-incomplete",
        ),
        (
            forged_dataclass(prior, snapshot=HostileSnapshot()),
            "private-hostile-snapshot-property",
        ),
    )
    for corrupt_prior, marker in invalid_priors:
        assert_ancestry_rejected(corrupt_prior, marker)

    invalid_reconstructed_priors = (
        (SimpleNamespace(marker="private-reconstructed-proxy"), "private-reconstructed-proxy"),
        (object.__new__(PriorSubclass), "private-reconstructed-subclass"),
        (object.__new__(type(prior)), "private-reconstructed-incomplete"),
        (
            forged_dataclass(prior, artifact_integrity_verified=False),
            "private-reconstructed-mismatch",
        ),
    )
    for reconstructed, marker in invalid_reconstructed_priors:
        monkeypatch.setattr(
            module,
            "validate_laya_runtime_oci_metadata",
            lambda _snapshot, value=reconstructed: value,
        )
        parsed_projections.clear()
        config_hash_calls.clear()
        monkeypatch.setattr(
            module,
            "hashlib",
            SimpleNamespace(sha256=config_hash_spy),
        )
        with pytest.raises(
            (TypeError, ValueError), match="metadata|ancestry|layout|evidence|valid"
        ) as validator_error:
            module.validate_laya_runtime_oci_config_semantics(layout_evidence, payload)
        with pytest.raises(
            (TypeError, ValueError), match="metadata|ancestry|layout|evidence|valid"
        ) as summary_error:
            module.canonical_laya_runtime_oci_config_summary_bytes(evidence)
        assert parsed_projections == []
        assert config_hash_calls == []
        _private_error(validator_error.value, marker, str(root), descriptor.digest)
        _private_error(summary_error.value, marker, str(root), descriptor.digest)
    monkeypatch.setattr(
        module,
        "validate_laya_runtime_oci_metadata",
        metadata_validator_spy,
    )

    manifest = prior.oci_manifest
    descriptor_projection = manifest.config

    class DescriptorSubclass(type(descriptor_projection)):
        pass

    class HostileDescriptor:
        @property
        def media_type(self):
            raise AssertionError("private-hostile-descriptor-property")

    for invalid_descriptor, marker in (
        (SimpleNamespace(marker="private-descriptor-proxy"), "private-descriptor-proxy"),
        (object.__new__(DescriptorSubclass), "private-descriptor-subclass"),
        (object.__new__(type(descriptor_projection)), "private-descriptor-incomplete"),
        (HostileDescriptor(), "private-hostile-descriptor-property"),
    ):
        corrupt_manifest = forged_dataclass(manifest, config=invalid_descriptor)
        assert_ancestry_rejected(
            forged_dataclass(prior, oci_manifest=corrupt_manifest),
            marker,
        )

    original_artifacts = prior.snapshot.artifacts
    for invalid_artifacts in (
        list(original_artifacts),
        tuple(reversed(original_artifacts)),
        original_artifacts[:-1],
        (*original_artifacts, original_artifacts[-1]),
        (original_artifacts[0], *original_artifacts),
    ):
        corrupt_snapshot = forged_dataclass(
            prior.snapshot,
            artifacts=invalid_artifacts,
        )
        bundle_call_count = len(bundle_inputs)
        assert_ancestry_rejected(forged_dataclass(prior, snapshot=corrupt_snapshot))
        assert len(bundle_inputs) == bundle_call_count

    for artifact_position, artifact in enumerate(original_artifacts):

        class ArtifactSubclass(type(artifact)):
            pass

        canonicalizable_artifacts = (
            (
                populated_proxy(
                    artifact,
                    marker=f"private-artifact-{artifact_position}-proxy",
                ),
                f"private-artifact-{artifact_position}-proxy",
            ),
            (
                populated_clone(artifact, ArtifactSubclass),
                f"private-artifact-{artifact_position}-subclass",
            ),
            (
                populated_clone(artifact),
                f"private-artifact-{artifact_position}-canonical-copy",
            ),
        )
        for canonicalizable_artifact, _marker in canonicalizable_artifacts:
            artifacts = list(original_artifacts)
            artifacts[artifact_position] = canonicalizable_artifact
            candidate_snapshot = forged_dataclass(prior.snapshot, artifacts=tuple(artifacts))
            assert_ancestry_canonicalized(forged_dataclass(prior, snapshot=candidate_snapshot))

    homogeneous_proxies = tuple(
        populated_proxy(artifact, marker="private-all-artifact-proxies")
        for artifact in original_artifacts
    )
    assert_ancestry_canonicalized(
        forged_dataclass(
            prior,
            snapshot=forged_dataclass(prior.snapshot, artifacts=homogeneous_proxies),
        )
    )

    non_manifest_positions = tuple(
        index
        for index, artifact in enumerate(prior.snapshot.artifacts)
        if artifact.spec.kind != "oci_manifest"
    )
    assert len(non_manifest_positions) == 4
    for artifact_position in non_manifest_positions:
        artifact = prior.snapshot.artifacts[artifact_position]
        marker = f"private-artifact-{artifact_position}"
        corrupt_artifacts = []
        corrupt_artifacts.append(forged_dataclass(artifact, content=marker.encode("ascii")))
        corrupt_artifacts.append(
            forged_dataclass(
                artifact,
                spec=forged_dataclass(artifact.spec, sha256="a" * 64),
            )
        )
        corrupt_artifacts.append(
            SimpleNamespace(
                spec=artifact.spec,
                marker=marker + "-incomplete-proxy",
            )
        )
        for corrupt_artifact in corrupt_artifacts:
            artifacts = list(prior.snapshot.artifacts)
            artifacts[artifact_position] = corrupt_artifact
            corrupt_snapshot = forged_dataclass(prior.snapshot, artifacts=tuple(artifacts))
            assert_ancestry_rejected(
                forged_dataclass(prior, snapshot=corrupt_snapshot),
                marker,
                marker + "-incomplete-proxy",
                "a" * 64,
            )
    for invalid in (False, 1, None):
        corrupt_snapshot = forged_dataclass(
            prior.snapshot,
            artifact_integrity_verified=invalid,
        )
        assert_ancestry_rejected(forged_dataclass(prior, snapshot=corrupt_snapshot))

    for invalid_schema in ("private-snapshot-schema", 1, None):
        corrupt_snapshot = forged_dataclass(
            prior.snapshot,
            schema_version=invalid_schema,
        )
        assert_ancestry_rejected(
            forged_dataclass(prior, snapshot=corrupt_snapshot),
            *private_strings(invalid_schema),
        )
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
    for flag in snapshot_false_flags:
        for invalid in (True, 1, None):
            corrupt_snapshot = forged_dataclass(prior.snapshot, **{flag: invalid})
            assert_ancestry_rejected(forged_dataclass(prior, snapshot=corrupt_snapshot))

    runtime_manifest = prior.snapshot.manifest

    class RuntimeManifestSubclass(type(runtime_manifest)):
        pass

    class HostileRuntimeManifest:
        @property
        def schema_version(self):
            raise AssertionError("private-hostile-runtime-manifest")

    for invalid_manifest, marker in (
        (
            SimpleNamespace(marker="private-runtime-manifest-proxy"),
            "private-runtime-manifest-proxy",
        ),
        (object.__new__(RuntimeManifestSubclass), "private-runtime-manifest-subclass"),
        (object.__new__(type(runtime_manifest)), "private-runtime-manifest-incomplete"),
        (HostileRuntimeManifest(), "private-hostile-runtime-manifest"),
    ):
        corrupt_snapshot = forged_dataclass(prior.snapshot, manifest=invalid_manifest)
        assert_ancestry_rejected(
            forged_dataclass(prior, snapshot=corrupt_snapshot),
            marker,
        )

    populated_manifest_variants = (
        (
            populated_proxy(
                runtime_manifest,
                marker="private-populated-runtime-manifest-proxy",
            ),
            "private-populated-runtime-manifest-proxy",
        ),
        (
            populated_clone(runtime_manifest, RuntimeManifestSubclass),
            "private-populated-runtime-manifest-subclass",
        ),
    )
    for invalid_manifest, marker in populated_manifest_variants:
        corrupt_snapshot = forged_dataclass(prior.snapshot, manifest=invalid_manifest)
        assert_ancestry_rejected(
            forged_dataclass(prior, snapshot=corrupt_snapshot),
            marker,
        )
    assert_ancestry_canonicalized(
        forged_dataclass(
            prior,
            snapshot=forged_dataclass(
                prior.snapshot,
                manifest=populated_clone(runtime_manifest),
            ),
        )
    )

    manifest_field_mutations = {
        "schema_version": "private-runtime-manifest-schema",
        "runtime_id": "private-runtime-id",
        "provider": "private-provider",
        "engine": "private-engine",
        "source": "https://private.invalid/source@" + "a" * 40,
        "license": "private-license",
        "python": "private-python",
        "platform": "private-platform",
        "base_image_ref": "private-base-image@sha256:" + "a" * 64,
        "identity_sha256": "a" * 64,
    }
    for field_name, invalid in manifest_field_mutations.items():
        corrupt_manifest = forged_dataclass(runtime_manifest, **{field_name: invalid})
        corrupt_snapshot = forged_dataclass(prior.snapshot, manifest=corrupt_manifest)
        assert_ancestry_rejected(
            forged_dataclass(prior, snapshot=corrupt_snapshot),
            *private_strings(invalid),
        )
    for invalid in (False, 1, None):
        corrupt_manifest = forged_dataclass(runtime_manifest, structurally_valid=invalid)
        corrupt_snapshot = forged_dataclass(prior.snapshot, manifest=corrupt_manifest)
        assert_ancestry_rejected(forged_dataclass(prior, snapshot=corrupt_snapshot))
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
    for flag in manifest_false_flags:
        for invalid in (True, 1, None):
            corrupt_manifest = forged_dataclass(runtime_manifest, **{flag: invalid})
            corrupt_snapshot = forged_dataclass(prior.snapshot, manifest=corrupt_manifest)
            assert_ancestry_rejected(forged_dataclass(prior, snapshot=corrupt_snapshot))

    manifest_specs = runtime_manifest.artifacts
    for invalid_artifacts in (
        list(manifest_specs),
        manifest_specs[:-1],
        tuple(reversed(manifest_specs)),
        (SimpleNamespace(marker="private-runtime-spec-proxy"), *manifest_specs[1:]),
    ):
        corrupt_manifest = forged_dataclass(runtime_manifest, artifacts=invalid_artifacts)
        corrupt_snapshot = forged_dataclass(prior.snapshot, manifest=corrupt_manifest)
        assert_ancestry_rejected(
            forged_dataclass(prior, snapshot=corrupt_snapshot),
            "private-runtime-spec-proxy",
        )
    first_spec = manifest_specs[0]

    class HostileSpec:
        @property
        def kind(self):
            raise AssertionError("private-hostile-runtime-spec")

    hostile_specs = (HostileSpec(), *manifest_specs[1:])
    assert_ancestry_rejected(
        forged_dataclass(
            prior,
            snapshot=forged_dataclass(
                prior.snapshot,
                manifest=forged_dataclass(runtime_manifest, artifacts=hostile_specs),
            ),
        ),
        "private-hostile-runtime-spec",
    )
    for field_name, invalid in {
        "kind": "private-kind",
        "format": "private-format",
        "path": "private/path",
        "sha256": "a" * 64,
        "size_bytes": first_spec.size_bytes + 1,
    }.items():
        corrupt_specs = list(manifest_specs)
        corrupt_specs[0] = forged_dataclass(first_spec, **{field_name: invalid})
        corrupt_manifest = forged_dataclass(runtime_manifest, artifacts=tuple(corrupt_specs))
        corrupt_snapshot = forged_dataclass(prior.snapshot, manifest=corrupt_manifest)
        assert_ancestry_rejected(
            forged_dataclass(prior, snapshot=corrupt_snapshot),
            *private_strings(invalid),
        )
    for spec_position, spec in enumerate(manifest_specs):

        class SpecSubclass(type(spec)):
            pass

        for invalid_spec, marker in (
            (
                populated_proxy(
                    spec,
                    marker=f"private-spec-{spec_position}-proxy",
                ),
                f"private-spec-{spec_position}-proxy",
            ),
            (
                populated_clone(spec, SpecSubclass),
                f"private-spec-{spec_position}-subclass",
            ),
        ):
            corrupt_specs = list(manifest_specs)
            corrupt_specs[spec_position] = invalid_spec
            corrupt_manifest = forged_dataclass(
                runtime_manifest,
                artifacts=tuple(corrupt_specs),
            )
            corrupt_snapshot = forged_dataclass(prior.snapshot, manifest=corrupt_manifest)
            assert_ancestry_rejected(
                forged_dataclass(prior, snapshot=corrupt_snapshot),
                marker,
            )
        canonical_specs = list(manifest_specs)
        canonical_specs[spec_position] = populated_clone(spec)
        assert_ancestry_canonicalized(
            forged_dataclass(
                prior,
                snapshot=forged_dataclass(
                    prior.snapshot,
                    manifest=forged_dataclass(
                        runtime_manifest,
                        artifacts=tuple(canonical_specs),
                    ),
                ),
            )
        )
    all_spec_proxies = tuple(
        populated_proxy(spec, marker="private-all-spec-proxies") for spec in manifest_specs
    )
    assert_ancestry_rejected(
        forged_dataclass(
            prior,
            snapshot=forged_dataclass(
                prior.snapshot,
                manifest=forged_dataclass(runtime_manifest, artifacts=all_spec_proxies),
            ),
        ),
        "private-all-spec-proxies",
    )
    for spec_position, spec in enumerate(manifest_specs):
        corrupt_specs = list(manifest_specs)
        corrupt_specs[spec_position] = forged_dataclass(spec, sha256="a" * 64)
        corrupt_manifest = forged_dataclass(runtime_manifest, artifacts=tuple(corrupt_specs))
        corrupt_snapshot = forged_dataclass(prior.snapshot, manifest=corrupt_manifest)
        assert_ancestry_rejected(
            forged_dataclass(prior, snapshot=corrupt_snapshot),
            "a" * 64,
        )

    oci_artifact_positions = tuple(
        index
        for index, artifact in enumerate(prior.snapshot.artifacts)
        if artifact.spec.kind == "oci_manifest"
    )
    assert len(oci_artifact_positions) == 1
    oci_artifact_position = oci_artifact_positions[0]
    oci_artifact = prior.snapshot.artifacts[oci_artifact_position]

    class OciArtifactSubclass(type(oci_artifact)):
        pass

    for invalid_artifact, marker in (
        (SimpleNamespace(marker="private-oci-artifact-proxy"), "private-oci-artifact-proxy"),
        (object.__new__(OciArtifactSubclass), "private-oci-artifact-subclass"),
        (object.__new__(type(oci_artifact)), "private-oci-artifact-incomplete"),
        (
            forged_dataclass(oci_artifact, content=b"private-oci-artifact-content"),
            "private-oci-artifact-content",
        ),
        (
            forged_dataclass(
                oci_artifact,
                spec=forged_dataclass(oci_artifact.spec, sha256="a" * 64),
            ),
            "a" * 64,
        ),
    ):
        artifacts = list(prior.snapshot.artifacts)
        artifacts[oci_artifact_position] = invalid_artifact
        corrupt_snapshot = forged_dataclass(prior.snapshot, artifacts=tuple(artifacts))
        assert_ancestry_rejected(
            forged_dataclass(prior, snapshot=corrupt_snapshot),
            marker,
        )

    oci_projection = prior.oci_manifest
    projection_field_mutations = {
        "schema_version": 1,
        "media_type": "private-oci-media-type",
        "semantics_sha256": "a" * 64,
    }
    for field_name, invalid in projection_field_mutations.items():
        corrupt_projection = forged_dataclass(oci_projection, **{field_name: invalid})
        assert_ancestry_rejected(
            forged_dataclass(prior, oci_manifest=corrupt_projection),
            *private_strings(invalid),
        )
    for descriptor_field, invalid in (
        ("media_type", "private-config-descriptor-media"),
        ("digest", "sha256:" + "a" * 64),
        ("size_bytes", oci_projection.config.size_bytes + 1),
    ):
        corrupt_config_descriptor = forged_dataclass(
            oci_projection.config,
            **{descriptor_field: invalid},
        )
        corrupt_projection = forged_dataclass(
            oci_projection,
            config=corrupt_config_descriptor,
        )
        assert_ancestry_rejected(
            forged_dataclass(prior, oci_manifest=corrupt_projection),
            *private_strings(invalid),
        )
    for layer_position, layer in enumerate(oci_projection.layers):
        for descriptor_field, invalid in (
            ("media_type", f"private-layer-{layer_position}-media"),
            ("digest", "sha256:" + f"{layer_position + 1:x}" * 64),
            ("size_bytes", layer.size_bytes + 1),
        ):
            layers = list(oci_projection.layers)
            layers[layer_position] = forged_dataclass(layer, **{descriptor_field: invalid})
            corrupt_projection = forged_dataclass(oci_projection, layers=tuple(layers))
            assert_ancestry_rejected(
                forged_dataclass(prior, oci_manifest=corrupt_projection),
                *private_strings(invalid),
            )
    for invalid_layers in (
        list(oci_projection.layers),
        oci_projection.layers[:-1],
        (*oci_projection.layers, oci_projection.layers[-1]),
        tuple(reversed(oci_projection.layers)),
    ):
        corrupt_projection = forged_dataclass(oci_projection, layers=invalid_layers)
        assert_ancestry_rejected(forged_dataclass(prior, oci_manifest=corrupt_projection))
    for annotation_position, (key, value) in enumerate(oci_projection.annotations):
        annotations = list(oci_projection.annotations)
        annotations[annotation_position] = (key, f"private-annotation-{annotation_position}")
        corrupt_projection = forged_dataclass(
            oci_projection,
            annotations=tuple(annotations),
        )
        assert_ancestry_rejected(
            forged_dataclass(prior, oci_manifest=corrupt_projection),
            f"private-annotation-{annotation_position}",
        )
    for invalid_annotations in (
        list(oci_projection.annotations),
        oci_projection.annotations[:-1],
        (*oci_projection.annotations, oci_projection.annotations[-1]),
        tuple(reversed(oci_projection.annotations)),
    ):
        corrupt_projection = forged_dataclass(
            oci_projection,
            annotations=invalid_annotations,
        )
        assert_ancestry_rejected(forged_dataclass(prior, oci_manifest=corrupt_projection))

    alternate_identity = type(prior.runtime_identity)(
        schema_version=prior.runtime_identity.schema_version,
        sha256="a" * 64,
    )
    alternate_snapshot = forged_dataclass(
        prior.snapshot,
        runtime_identity=alternate_identity,
    )
    alternate_prior = forged_dataclass(
        prior,
        snapshot=alternate_snapshot,
        runtime_identity=alternate_identity,
    )

    class RuntimeIdentitySubclass(type(prior.runtime_identity)):
        pass

    class HostileRuntimeIdentity:
        @property
        def schema_version(self):
            raise AssertionError("private-hostile-runtime-identity")

    for invalid_identity, marker in (
        (
            SimpleNamespace(
                schema_version=prior.runtime_identity.schema_version,
                sha256="b" * 64,
                marker="private-runtime-identity-proxy",
            ),
            "private-runtime-identity-proxy",
        ),
        (object.__new__(RuntimeIdentitySubclass), "private-runtime-identity-subclass"),
        (object.__new__(type(prior.runtime_identity)), "private-runtime-identity-incomplete"),
        (HostileRuntimeIdentity(), "private-hostile-runtime-identity"),
    ):
        corrupt_snapshot = forged_dataclass(
            prior.snapshot,
            runtime_identity=invalid_identity,
        )
        corrupt_prior = forged_dataclass(
            prior,
            snapshot=corrupt_snapshot,
            runtime_identity=invalid_identity,
        )
        assert_ancestry_rejected(
            corrupt_prior,
            marker,
            runtime_identity=invalid_identity,
        )

    assert_ancestry_rejected(
        alternate_prior,
        "a" * 64,
        runtime_identity=alternate_identity,
    )
    monkeypatch.setattr(module, "hashlib", original_config_hashlib)
    parsed_projections.clear()

    summary = module.canonical_laya_runtime_oci_config_summary_bytes(evidence)
    decoded = json.loads(summary)
    expected = {
        "schema_version": EVIDENCE_SCHEMA,
        "profile_schema_version": PROFILE_SCHEMA,
        "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
        "runtime_identity_sha256": evidence.runtime_identity.sha256,
        **{flag: True for flag in CONFIG_TRUE_FLAGS},
        **{flag: False for flag in CONFIG_FALSE_FLAGS},
    }
    assert decoded == expected
    assert summary == json.dumps(
        expected, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")
    rendered = repr(evidence) + repr(evidence.config_receipt) + summary.decode("ascii")
    private_values = (
        str(root),
        descriptor.path,
        descriptor.digest,
        str(descriptor.size_bytes),
        *ENVIRONMENT,
        *LABELS,
        *LABELS.values(),
        *DIFF_IDS,
        "synthetic-private-history-command",
    )
    assert all(value not in rendered for value in private_values)

    class EvidenceSubclass(LayaRuntimeOciConfigEvidence):
        pass

    for invalid in (
        SimpleNamespace(schema_version=EVIDENCE_SCHEMA),
        object.__new__(EvidenceSubclass),
    ):
        with pytest.raises((TypeError, ValueError), match="evidence|sealed|valid") as captured:
            module.canonical_laya_runtime_oci_config_summary_bytes(invalid)
        _private_error(captured.value, str(root), descriptor.digest)

    binding_mutations = (
        ("schema_version", "private-schema-binding"),
        ("layout_evidence", "private-layout-binding"),
        ("config_receipt", "private-receipt-binding"),
        ("config", "private-config-binding"),
        ("runtime_identity", "private-runtime-binding"),
    )
    for field_name, marker in binding_mutations:
        forged = forged_dataclass(evidence, **{field_name: marker})
        with pytest.raises(
            (TypeError, ValueError), match="evidence|schema|binding|valid"
        ) as captured:
            module.canonical_laya_runtime_oci_config_summary_bytes(forged)
        _private_error(captured.value, marker, str(root), descriptor.digest)

    for flag in CONFIG_TRUE_FLAGS:
        for invalid in (False, 1, None):
            forged = forged_dataclass(evidence, **{flag: invalid})
            with pytest.raises(
                (TypeError, ValueError), match="evidence|claim|flag|valid"
            ) as captured:
                module.canonical_laya_runtime_oci_config_summary_bytes(forged)
            _private_error(captured.value, str(root), descriptor.digest)
    for flag in CONFIG_FALSE_FLAGS:
        for invalid in (True, 1, None):
            forged = forged_dataclass(evidence, **{flag: invalid})
            with pytest.raises(
                (TypeError, ValueError), match="evidence|claim|flag|valid"
            ) as captured:
                module.canonical_laya_runtime_oci_config_summary_bytes(forged)
            _private_error(captured.value, str(root), descriptor.digest)

    parsed_projections.clear()
    mutations = (
        payload[:-1],
        payload + b"x",
        bytes([payload[0] ^ 1]) + payload[1:],
        bytearray(payload),
        memoryview(payload),
    )
    for mutation in mutations:
        with pytest.raises((TypeError, ValueError), match="bytes|size|digest|config") as captured:
            module.validate_laya_runtime_oci_config_semantics(layout_evidence, mutation)
        _private_error(captured.value, str(root), descriptor.digest)
    assert parsed_projections == []

    corrupt_layouts = (
        forged_dataclass(layout_evidence, oci_bytes_verified=False),
        forged_dataclass(layout_evidence, oci_config_semantics_verified=True),
        forged_dataclass(layout_evidence, receipts=tuple(reversed(layout_evidence.receipts))),
        forged_dataclass(layout_evidence, runtime_identity=object()),
    )
    for corrupt in corrupt_layouts:
        with pytest.raises((TypeError, ValueError), match="layout|evidence|claim|receipt|valid"):
            module.validate_laya_runtime_oci_config_semantics(corrupt, payload)
    assert parsed_projections == []

    for flag in LAYOUT_TRUE_FLAGS:
        for invalid in (False, 1, None):
            corrupt = forged_dataclass(layout_evidence, **{flag: invalid})
            with pytest.raises(
                (TypeError, ValueError), match="layout|evidence|claim|flag|valid"
            ) as captured:
                module.validate_laya_runtime_oci_config_semantics(corrupt, payload)
            _private_error(captured.value, str(root), descriptor.digest)
            with pytest.raises(
                (TypeError, ValueError), match="layout|evidence|claim|flag|binding|valid"
            ) as summary_captured:
                module.canonical_laya_runtime_oci_config_summary_bytes(
                    forged_dataclass(evidence, layout_evidence=corrupt)
                )
            _private_error(summary_captured.value, str(root), descriptor.digest)
    for flag in LAYOUT_FALSE_FLAGS:
        for invalid in (True, 1, None):
            corrupt = forged_dataclass(layout_evidence, **{flag: invalid})
            with pytest.raises(
                (TypeError, ValueError), match="layout|evidence|claim|flag|valid"
            ) as captured:
                module.validate_laya_runtime_oci_config_semantics(corrupt, payload)
            _private_error(captured.value, str(root), descriptor.digest)
            with pytest.raises(
                (TypeError, ValueError), match="layout|evidence|claim|flag|binding|valid"
            ) as summary_captured:
                module.canonical_laya_runtime_oci_config_summary_bytes(
                    forged_dataclass(evidence, layout_evidence=corrupt)
                )
            _private_error(summary_captured.value, str(root), descriptor.digest)
    assert parsed_projections == []

    def forged_graph(*, blob_position=position, **blob_changes):
        blobs = list(layout_evidence.plan.blobs)
        original_blob = blobs[blob_position]
        if "digest" in blob_changes and "path" not in blob_changes:
            blob_changes["path"] = "blobs/sha256/" + blob_changes["digest"].removeprefix("sha256:")
        blobs[blob_position] = forged_dataclass(original_blob, **blob_changes)
        blob_total = sum(blob.size_bytes for blob in blobs)
        plan = forged_dataclass(
            layout_evidence.plan,
            blobs=tuple(blobs),
            index_manifest=blobs[0],
            blob_total_size_bytes=blob_total,
            total_size_bytes=(
                layout_evidence.plan.total_size_bytes
                + blob_total
                - layout_evidence.plan.blob_total_size_bytes
            ),
        )
        receipts = tuple(
            forged_dataclass(
                layout_evidence.receipts[index],
                plan=plan,
                blob=blob,
            )
            for index, blob in enumerate(blobs)
        )
        return forged_dataclass(layout_evidence, plan=plan, receipts=receipts)

    graph_mutations = (
        (forged_graph(role="private-not-config"), "private-not-config"),
        (forged_graph(blob_position=2, role="config"),),
        (
            forged_graph(media_type="application/vnd.oci.image.config.v1+private"),
            "application/vnd.oci.image.config.v1+private",
        ),
        (forged_graph(digest="sha256:" + "a" * 64), "sha256:" + "a" * 64),
        (forged_graph(size_bytes=REAL_CONFIG_SIZE_BYTES + 1),),
        (
            forged_graph(blob_position=2, media_type="private-nonconfig-media"),
            "private-nonconfig-media",
        ),
    )
    for corrupt, *markers in graph_mutations:
        with pytest.raises(
            (TypeError, ValueError), match="config|descriptor|blob|layout|valid"
        ) as captured:
            module.validate_laya_runtime_oci_config_semantics(corrupt, payload)
        _private_error(captured.value, *markers, str(root))
        with pytest.raises(
            (TypeError, ValueError),
            match="config|descriptor|blob|layout|plan|receipt|evidence|valid",
        ) as summary_captured:
            module.canonical_laya_runtime_oci_config_summary_bytes(evidence_with_layout(corrupt))
        _private_error(summary_captured.value, *markers, str(root), descriptor.digest)
    assert parsed_projections == []

    def forged_plan_layout(**plan_changes):
        plan = forged_dataclass(layout_evidence.plan, **plan_changes)
        receipts = tuple(
            forged_dataclass(receipt_item, plan=plan) for receipt_item in layout_evidence.receipts
        )
        return forged_dataclass(
            layout_evidence,
            plan=plan,
            receipts=receipts,
            runtime_identity=plan.runtime_identity,
        )

    plan_mutations = (
        (forged_plan_layout(schema_version="private-plan-schema"), "private-plan-schema"),
        (forged_plan_layout(oci_evidence="private-plan-oci-evidence"), "private-plan-oci-evidence"),
        (
            forged_plan_layout(control_paths=("private-control-path", "index.json")),
            "private-control-path",
        ),
        (forged_plan_layout(control_file_count=3),),
        (forged_plan_layout(index_manifest=layout_evidence.plan.blobs[1]),),
        (forged_plan_layout(blob_count=11),),
        (forged_plan_layout(logical_file_count=13),),
        (
            forged_plan_layout(
                blob_total_size_bytes=layout_evidence.plan.blob_total_size_bytes + 1,
                total_size_bytes=layout_evidence.plan.total_size_bytes + 1,
            ),
        ),
        (forged_plan_layout(total_size_bytes=layout_evidence.plan.total_size_bytes + 1),),
        (
            forged_plan_layout(runtime_identity="private-plan-runtime-identity"),
            "private-plan-runtime-identity",
        ),
    )
    for corrupt, *markers in plan_mutations:
        with pytest.raises(
            (TypeError, ValueError),
            match="plan|layout|evidence|control|index|count|total|identity|valid",
        ) as captured:
            module.validate_laya_runtime_oci_config_semantics(corrupt, payload)
        _private_error(captured.value, *markers, str(root))
    assert parsed_projections == []

    nested_layout_mutations = (
        (forged_dataclass(layout_evidence, **{LAYOUT_TRUE_FLAGS[0]: False}),),
        (forged_dataclass(layout_evidence, **{LAYOUT_FALSE_FLAGS[0]: True}),),
        *plan_mutations,
    )
    for corrupt_layout, *markers in nested_layout_mutations:
        corrupt_evidence = evidence_with_layout(corrupt_layout)
        with pytest.raises(
            (TypeError, ValueError), match="layout|plan|evidence|claim|binding|valid"
        ) as captured:
            module.canonical_laya_runtime_oci_config_summary_bytes(corrupt_evidence)
        _private_error(captured.value, *markers, str(root), descriptor.digest)

    nonconfig_position = position + 1
    nonconfig_receipt = layout_evidence.receipts[nonconfig_position]
    receipt_mutations = (
        (
            position,
            SimpleNamespace(plan=layout_evidence.plan, blob=descriptor, blob_bytes_verified=True),
        ),
        (position, forged_dataclass(receipt, blob=layout_evidence.plan.blobs[position + 1])),
        (position, forged_dataclass(receipt, blob_bytes_verified=False)),
        (
            position,
            forged_dataclass(
                receipt,
                plan=forged_dataclass(
                    layout_evidence.plan,
                    schema_version="private-receipt-plan-schema",
                ),
            ),
        ),
        (
            nonconfig_position,
            SimpleNamespace(
                plan=layout_evidence.plan,
                blob=nonconfig_receipt.blob,
                blob_bytes_verified=True,
                marker="private-nonconfig-receipt",
            ),
        ),
        (
            nonconfig_position,
            forged_dataclass(
                nonconfig_receipt,
                blob=layout_evidence.plan.blobs[nonconfig_position + 1],
            ),
        ),
        (nonconfig_position, forged_dataclass(nonconfig_receipt, blob_bytes_verified=False)),
    )
    for receipt_position, corrupt_receipt in receipt_mutations:
        receipts = list(layout_evidence.receipts)
        receipts[receipt_position] = corrupt_receipt
        corrupt = forged_dataclass(layout_evidence, receipts=tuple(receipts))
        with pytest.raises((TypeError, ValueError), match="receipt|blob|layout|valid") as captured:
            module.validate_laya_runtime_oci_config_semantics(corrupt, payload)
        _private_error(
            captured.value,
            "private-nonconfig-receipt",
            "private-receipt-plan-schema",
            str(root),
        )
        with pytest.raises(
            (TypeError, ValueError), match="receipt|blob|plan|binding|layout|evidence|valid"
        ) as summary_captured:
            module.canonical_laya_runtime_oci_config_summary_bytes(evidence_with_layout(corrupt))
        _private_error(
            summary_captured.value,
            "private-nonconfig-receipt",
            "private-receipt-plan-schema",
            str(root),
            descriptor.digest,
        )

    reordered = list(layout_evidence.receipts)
    reordered[nonconfig_position], reordered[nonconfig_position + 1] = (
        reordered[nonconfig_position + 1],
        reordered[nonconfig_position],
    )
    reordered_layout = forged_dataclass(layout_evidence, receipts=tuple(reordered))
    with pytest.raises((TypeError, ValueError), match="receipt|order|blob|layout|valid"):
        module.validate_laya_runtime_oci_config_semantics(reordered_layout, payload)
    with pytest.raises(
        (TypeError, ValueError), match="receipt|order|blob|layout|evidence|valid"
    ) as captured:
        module.canonical_laya_runtime_oci_config_summary_bytes(
            evidence_with_layout(reordered_layout)
        )
    _private_error(captured.value, str(root), descriptor.digest)
    assert parsed_projections == []

    projection_mutations = {
        "schema_version": "private-projection-schema",
        "architecture": "private-projection-architecture",
        "operating_system": "private-projection-os",
        "created": "private-projection-created",
        "user": "private-projection-user",
        "entrypoint": ("private-projection-entrypoint",),
        "working_directory": "private-projection-workdir",
        "environment_count": evidence.config.environment_count + 1,
        "label_count": evidence.config.label_count + 1,
        "diff_id_count": evidence.config.diff_id_count + 1,
        "history_count": evidence.config.history_count + 1,
        "non_empty_history_count": evidence.config.non_empty_history_count + 1,
    }
    for field_name, invalid in projection_mutations.items():
        corrupt_projection = forged_dataclass(evidence.config, **{field_name: invalid})
        corrupt_evidence = forged_dataclass(evidence, config=corrupt_projection)
        with pytest.raises(
            (TypeError, ValueError), match="config|projection|schema|binding|evidence|valid"
        ) as captured:
            module.canonical_laya_runtime_oci_config_summary_bytes(corrupt_evidence)
        markers = private_strings(invalid)
        _private_error(captured.value, *markers, str(root), descriptor.digest)

    alternate_runtime_identity = type(evidence.runtime_identity)(
        schema_version=evidence.runtime_identity.schema_version,
        sha256="a" * 64,
    )
    with pytest.raises(
        (TypeError, ValueError), match="identity|binding|evidence|valid"
    ) as captured:
        module.canonical_laya_runtime_oci_config_summary_bytes(
            forged_dataclass(evidence, runtime_identity=alternate_runtime_identity)
        )
    _private_error(captured.value, str(root), descriptor.digest)

    for field in fields(evidence):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(evidence, field.name, getattr(evidence, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
            replace(evidence, **{field.name: getattr(evidence, field.name)})
    assert _tree_fingerprint(root) == before
