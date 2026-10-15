import ast
import os
import traceback
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

TAR_VALIDATION_SCHEMA = "laya-oci-tar-validation-v1"
TAR_PLAN_SCHEMA = "laya-oci-tar-plan-v1"
MAX_TAR_CHUNK_BYTES = 1024 * 1024
MAX_TAR_CHUNKS = 4096
MAX_TAR_ENTRIES = 65536
REAL_LAYOUT_GATE_ENV = "LAYA_RUNTIME_OCI_LAYOUT_ROOT"


def _private_error(error: BaseException, *markers: str) -> None:
    rendered = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    for marker in markers:
        assert marker not in str(error)
        assert marker not in rendered
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True


def _octal(value: int, width: int) -> bytes:
    encoded = f"{value:0{width - 1}o}".encode("ascii") + b"\0"
    assert len(encoded) == width
    return encoded


def _tar_header(
    name: str,
    *,
    size: int = 0,
    typeflag: bytes = b"0",
    linkname: str = "",
) -> bytes:
    """Build a small USTAR header without relying on tarfile's parser/writer."""

    name_bytes = name.encode("utf-8")
    link_bytes = linkname.encode("utf-8")
    assert len(name_bytes) <= 100
    assert len(link_bytes) <= 100
    assert len(typeflag) == 1
    header = bytearray(512)
    header[0 : len(name_bytes)] = name_bytes
    header[100:108] = _octal(0o644 if typeflag == b"0" else 0o777, 8)
    header[108:116] = _octal(0, 8)
    header[116:124] = _octal(0, 8)
    header[124:136] = _octal(size, 12)
    header[136:148] = _octal(0, 12)
    header[148:156] = b"        "
    header[156:157] = typeflag
    header[157 : 157 + len(link_bytes)] = link_bytes
    header[257:263] = b"ustar\0"
    header[263:265] = b"00"
    checksum = sum(header)
    header[148:156] = f"{checksum:06o}".encode("ascii") + b"\0 "
    return bytes(header)


def _tar_entry(
    name: str,
    payload: bytes = b"",
    *,
    typeflag: bytes = b"0",
    linkname: str = "",
) -> bytes:
    header = _tar_header(
        name,
        size=len(payload),
        typeflag=typeflag,
        linkname=linkname,
    )
    padding = b"\0" * ((-len(payload)) % 512)
    return header + payload + padding


def _archive(*entries: bytes, trailing_zero_blocks: int = 2) -> bytes:
    return b"".join(entries) + (b"\0" * 512 * trailing_zero_blocks)


def _chunked(payload: bytes, width: int):
    for offset in range(0, len(payload), width):
        yield payload[offset : offset + width]


def test_manual_tar_fixture_helpers_encode_checksum_padding_and_termination():
    payload = b"science"
    archive = _archive(_tar_entry("data/result.txt", payload))

    header = archive[:512]
    expected_checksum = int(header[148:154], 8)
    checksum_view = bytearray(header)
    checksum_view[148:156] = b"        "
    assert sum(checksum_view) == expected_checksum
    assert archive[512 : 512 + len(payload)] == payload
    assert archive[512 + len(payload) : 1024] == b"\0" * (512 - len(payload))
    assert archive[-1024:] == b"\0" * 1024


def test_tar_module_has_a_pure_minimal_public_surface():
    from human_feedback import runtime_oci_tar as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "human_feedback.runtime_oci_layers" in imports
    assert not imports & {
        "gzip",
        "io",
        "os",
        "pathlib",
        "socket",
        "subprocess",
        "tarfile",
        "tempfile",
        "urllib",
    }
    calls = {
        (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert calls.isdisjoint(
        {
            "BytesIO",
            "TemporaryFile",
            "__import__",
            "eval",
            "exec",
            "extract",
            "extractall",
            "join",
            "open",
            "read_bytes",
            "read_text",
            "seek",
            "system",
        }
    )
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    public_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    public_constants = {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
        if isinstance(target, ast.Name) and target.id.isupper() and not target.id.startswith("_")
    }
    assert public_functions == {
        "prepare_laya_oci_tar_plan",
        "validate_laya_oci_tar_chunks",
    }
    assert public_classes == {"LayaOciTarPlan", "ValidatedLayaOciTar"}
    assert public_constants == {
        "LAYER_TAR_PLAN_SCHEMA",
        "MAX_OCI_TAR_CHUNK_BYTES",
        "MAX_OCI_TAR_CHUNKS",
        "MAX_OCI_TAR_ENTRIES",
        "OCI_TAR_VALIDATION_SCHEMA",
    }


@pytest.mark.parametrize("width", [1, 17, 511, 512, 1024 * 1024])
@pytest.mark.parametrize(
    ("archive", "entry_count", "payload_size"),
    [
        pytest.param(_archive(), 0, 0, id="empty"),
        pytest.param(
            _archive(_tar_entry("data/result.txt", b"science")),
            1,
            7,
            id="regular",
        ),
    ],
)
def test_empty_and_regular_tar_are_validated_incrementally(
    archive,
    entry_count,
    payload_size,
    width,
):
    from human_feedback.runtime_oci_tar import (
        ValidatedLayaOciTar,
        validate_laya_oci_tar_chunks,
    )

    validated = validate_laya_oci_tar_chunks(_chunked(archive, width))

    assert type(validated) is ValidatedLayaOciTar
    assert validated.schema_version == TAR_VALIDATION_SCHEMA
    assert validated.entry_count == entry_count
    assert validated.payload_size_bytes == payload_size
    assert validated.tar_semantics_verified is True
    assert validated.oci_rootfs_verified is False
    assert validated.origin_verified is False
    assert validated.rootfs_materialized is False
    assert "result.txt" not in repr(validated)
    for field in fields(validated):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(validated, field.name, getattr(validated, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
            replace(validated, **{field.name: getattr(validated, field.name)})


@pytest.mark.parametrize("linkname", ["/etc/ssl/certs", "../../shared/target"])
def test_oci_symlink_targets_may_be_absolute_or_contain_parent_segments(linkname):
    from human_feedback.runtime_oci_tar import validate_laya_oci_tar_chunks

    archive = _archive(
        _tar_entry(
            "safe/link",
            typeflag=b"2",
            linkname=linkname,
        )
    )
    validated = validate_laya_oci_tar_chunks(_chunked(archive, 73))

    assert validated.entry_count == 1
    assert validated.tar_semantics_verified is True
    assert validated.oci_rootfs_verified is False


@pytest.mark.parametrize(
    ("name", "marker"),
    [
        ("/private/absolute-entry", "private/absolute-entry"),
        ("../private-parent-entry", "private-parent-entry"),
        ("safe/../../private-escape", "private-escape"),
        ("safe\\private-backslash", "private-backslash"),
    ],
)
def test_entry_paths_must_be_canonical_relative_and_remain_below_root(name, marker):
    from human_feedback.runtime_oci_tar import validate_laya_oci_tar_chunks

    with pytest.raises(ValueError, match="tar|entry|path|valid") as captured:
        validate_laya_oci_tar_chunks((_archive(_tar_entry(name)),))
    _private_error(captured.value, marker)


def test_duplicate_entry_paths_are_rejected_privately():
    from human_feedback.runtime_oci_tar import validate_laya_oci_tar_chunks

    archive = _archive(
        _tar_entry("private/duplicate", b"first"),
        _tar_entry("private/duplicate", b"second"),
    )
    with pytest.raises(ValueError, match="tar|entry|duplicate|valid") as captured:
        validate_laya_oci_tar_chunks((archive,))
    _private_error(captured.value, "private/duplicate", "first", "second")


def test_tar_checksum_truncation_termination_and_padding_fail_closed_privately():
    from human_feedback.runtime_oci_tar import validate_laya_oci_tar_chunks

    valid_entry = _tar_entry("private/payload", b"x")
    bad_checksum = bytearray(_archive(valid_entry))
    bad_checksum[100] ^= 1
    bad_padding = bytearray(_archive(valid_entry))
    bad_padding[513] = 1
    cases = (
        (bytes(bad_checksum), "checksum"),
        (_archive(valid_entry)[:-1], "truncated"),
        (_archive(valid_entry, trailing_zero_blocks=1), "termination"),
        (_archive(valid_entry) + _tar_entry("private/after-eof"), "after-eof"),
        (bytes(bad_padding), "padding"),
    )
    for archive, reason in cases:
        with pytest.raises(ValueError, match="tar|checksum|padding|terminat|valid") as captured:
            validate_laya_oci_tar_chunks(_chunked(archive, 127))
        _private_error(captured.value, "private/payload", "private/after-eof", reason)


def test_tar_stream_caps_are_public_and_enforced_without_consuming_a_sentinel(monkeypatch):
    from human_feedback import runtime_oci_tar as module

    assert module.MAX_OCI_TAR_CHUNK_BYTES == MAX_TAR_CHUNK_BYTES
    assert module.MAX_OCI_TAR_CHUNKS == MAX_TAR_CHUNKS
    assert module.MAX_OCI_TAR_ENTRIES == MAX_TAR_ENTRIES

    class HostileChunks:
        def __init__(self):
            self.requests = 0
            self.sentinel_executed = False

        def __iter__(self):
            return self

        def __next__(self):
            self.requests += 1
            if self.requests <= 3:
                return _tar_header(f"entry-{self.requests}")
            self.sentinel_executed = True
            raise AssertionError("private-entry-cap-sentinel")

    monkeypatch.setattr(module, "MAX_OCI_TAR_ENTRIES", 2)
    chunks = HostileChunks()
    with pytest.raises(ValueError, match="tar|entry|limit|valid") as captured:
        module.validate_laya_oci_tar_chunks(chunks)
    assert chunks.requests == 3
    assert chunks.sentinel_executed is False
    _private_error(captured.value, "private-entry-cap-sentinel")

    with pytest.raises((TypeError, ValueError), match="chunk|bytes|limit|valid"):
        module.validate_laya_oci_tar_chunks((b"",))
    with pytest.raises((TypeError, ValueError), match="chunk|bytes|limit|valid"):
        module.validate_laya_oci_tar_chunks(("not-bytes",))
    with pytest.raises((TypeError, ValueError), match="chunk|bytes|limit|valid"):
        module.validate_laya_oci_tar_chunks((b"x" * (MAX_TAR_CHUNK_BYTES + 1),))


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        SimpleNamespace(oci_layer_diff_ids_verified=True),
        "private-layer-evidence-proxy",
    ],
)
def test_tar_plan_rejects_non_exact_pr22_evidence_before_streaming(invalid):
    from human_feedback.runtime_oci_tar import prepare_laya_oci_tar_plan

    with pytest.raises((TypeError, ValueError), match="layer|evidence|exact|valid") as captured:
        prepare_laya_oci_tar_plan(invalid)
    _private_error(captured.value, "private-layer-evidence-proxy")


@pytest.mark.skipif(
    not os.environ.get(REAL_LAYOUT_GATE_ENV),
    reason="requires opt-in exact external OCI layout",
)
def test_tar_plan_is_sealed_identity_bound_to_exact_pr22_evidence():
    from human_feedback.runtime_oci_tar import LayaOciTarPlan, prepare_laya_oci_tar_plan

    from human_feedback.adapters.filesystem_oci_layout import (
        capture_and_verify_laya_oci_layer_diff_ids,
        capture_and_verify_laya_oci_layout,
    )
    from human_feedback.runtime_oci_config import validate_laya_runtime_oci_config_semantics
    from tests.test_laya_runtime_oci_layout import _oci_evidence

    root = Path(os.environ[REAL_LAYOUT_GATE_ENV])
    layout_evidence = capture_and_verify_laya_oci_layout(_oci_evidence(), root)
    config_blob = layout_evidence.plan.blobs[1]
    config_evidence = validate_laya_runtime_oci_config_semantics(
        layout_evidence,
        (root / config_blob.path).read_bytes(),
    )
    layer_evidence = capture_and_verify_laya_oci_layer_diff_ids(config_evidence, root)

    plan = prepare_laya_oci_tar_plan(layer_evidence)

    assert type(plan) is LayaOciTarPlan
    assert plan.schema_version == TAR_PLAN_SCHEMA
    assert plan.layer_evidence is layer_evidence
    assert plan.layer_plan is layer_evidence.plan
    assert plan.runtime_identity is layer_evidence.runtime_identity
    assert plan.layer_receipts is layer_evidence.receipts
    assert len(plan.layer_receipts) == 10
    assert plan.tar_semantics_verified is False
    assert plan.oci_rootfs_verified is False
    assert plan.origin_verified is False
    assert plan.rootfs_materialized is False
    rendered = repr(plan)
    assert all(receipt.computed_diff_id not in rendered for receipt in plan.layer_receipts)
    for field in fields(plan):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(plan, field.name, getattr(plan, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
            replace(plan, **{field.name: getattr(plan, field.name)})
