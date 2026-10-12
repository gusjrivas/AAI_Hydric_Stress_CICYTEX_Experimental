import ast
import json
import traceback
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path

import pytest

REAL_CONFIG_SIZE_BYTES = 10_261
REAL_CONFIG_SHA256 = "bdd27ffe0d14dd637985f09bcdf461e58a64348829a4b3ad3cb7886ff56e20c5"
PROFILE_SCHEMA = "laya-runtime-oci-config-profile-v1"
MAX_CONFIG_BYTES = 64 * 1024
MAX_JSON_DEPTH = 32
MAX_OBJECT_MEMBERS = 64
MAX_LIST_ITEMS = 256
MAX_STRING_LENGTH = 4_096
MAX_JSON_NODES = 2_048
ALLOWED_PARSER_IMPORTS = {"__future__", "dataclasses", "json", "re", "typing"}
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
    assert public_functions == set()
    public_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    assert public_classes == {"ValidatedLayaRuntimeOciConfig"}
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
    }
