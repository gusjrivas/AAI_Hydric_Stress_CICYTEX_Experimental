import ast
import inspect
import traceback
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

PLAN_SCHEMA = "laya-oci-tar-semantics-plan-v1"
MAX_TAR_CHUNK_BYTES = 1024 * 1024
MAX_TAR_ENTRIES = 65536


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
    name_bytes = name.encode("utf-8")
    link_bytes = linkname.encode("utf-8")
    assert len(name_bytes) <= 100 and len(link_bytes) <= 100 and len(typeflag) == 1
    header = bytearray(512)
    header[: len(name_bytes)] = name_bytes
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
    header[148:156] = f"{sum(header):06o}".encode("ascii") + b"\0 "
    return bytes(header)


def _tar_entry(
    name: str,
    payload: bytes = b"",
    *,
    typeflag: bytes = b"0",
    linkname: str = "",
) -> bytes:
    return (
        _tar_header(name, size=len(payload), typeflag=typeflag, linkname=linkname)
        + payload
        + (b"\0" * ((-len(payload)) % 512))
    )


def _archive(*entries: bytes, terminal_blocks: int = 2) -> bytes:
    return b"".join(entries) + (b"\0" * 512 * terminal_blocks)


def _chunks(payload: bytes, width: int):
    for offset in range(0, len(payload), width):
        yield payload[offset : offset + width]


def _forge(cls, **values):
    forged = object.__new__(cls)
    for field in fields(cls):
        assert field.name in values, f"missing synthetic field: {field.name}"
        object.__setattr__(forged, field.name, values[field.name])
    return forged


def _synthetic_pr22_evidence():
    """Use exact PR22 classes; the monkeypatched public summary is its deep oracle."""

    from human_feedback.runtime_oci_layers import (
        LayaOciLayerDiffIdPlan,
        LayaRuntimeOciLayerDiffIdsEvidence,
        VerifiedLayaOciLayerDiffId,
    )

    identity = SimpleNamespace(
        schema_version="laya-runtime-identity-ref-v1", identity_sha256="1" * 64
    )
    config = SimpleNamespace(runtime_identity=identity)
    layout = SimpleNamespace(runtime_identity=identity)
    layout_plan = SimpleNamespace(runtime_identity=identity)
    blobs = tuple(
        SimpleNamespace(
            role=f"layer-{position:02d}",
            digest=f"sha256:{position + 2:064x}",
            path=f"blobs/sha256/{position + 2:064x}",
            media_type="application/vnd.oci.image.layer.v1.tar+gzip",
            size_bytes=128,
        )
        for position in range(10)
    )
    compressed = tuple(SimpleNamespace(blob=blob, blob_bytes_verified=True) for blob in blobs)
    diff_ids = tuple(f"sha256:{position + 20:064x}" for position in range(10))
    plan = _forge(
        LayaOciLayerDiffIdPlan,
        schema_version="laya-oci-layer-diff-id-plan-v1",
        config_evidence=config,
        layout_evidence=layout,
        layout_plan=layout_plan,
        runtime_identity=identity,
        layer_blobs=blobs,
        layer_receipts=compressed,
        declared_diff_ids=diff_ids,
        oci_layer_diff_ids_verified=False,
        oci_rootfs_verified=False,
        origin_verified=False,
    )
    receipts = tuple(
        _forge(
            VerifiedLayaOciLayerDiffId,
            plan=plan,
            layer_blob=blob,
            compressed_receipt=compressed[position],
            layer_position=position,
            declared_diff_id=diff_ids[position],
            computed_diff_id=diff_ids[position],
            uncompressed_size_bytes=1024,
            compressed_blob_bytes_verified=True,
            layer_diff_id_verified=True,
            tar_semantics_verified=False,
            rootfs_verified=False,
            origin_verified=False,
        )
        for position, blob in enumerate(blobs)
    )
    true_claims = {
        "artifact_integrity_verified",
        "oci_manifest_semantics_verified",
        "oci_layout_controls_bytes_verified",
        "oci_blob_inventory_verified",
        "oci_same_root_capture_verified",
        "oci_manifest_blob_bytes_verified",
        "oci_config_blob_bytes_verified",
        "oci_layer_blobs_bytes_verified",
        "oci_bytes_verified",
        "oci_config_semantics_verified",
        "oci_layer_diff_ids_verified",
    }
    values = {
        "schema_version": "laya-runtime-oci-layer-diff-ids-evidence-v1",
        "plan": plan,
        "config_evidence": config,
        "layout_evidence": layout,
        "layout_plan": layout_plan,
        "runtime_identity": identity,
        "receipts": receipts,
    }
    for field in fields(LayaRuntimeOciLayerDiffIdsEvidence):
        values.setdefault(field.name, field.name in true_claims)
    return _forge(LayaRuntimeOciLayerDiffIdsEvidence, **values)


@pytest.fixture
def synthetic_pr22(monkeypatch):
    from human_feedback import runtime_oci_layers

    evidence = _synthetic_pr22_evidence()
    calls = []

    def deep_validate(candidate):
        calls.append(candidate)
        if candidate is not evidence:
            raise ValueError("invalid layer evidence") from None
        return b'{"schema_version":"laya-runtime-oci-layer-diff-ids-evidence-v1"}\n'

    monkeypatch.setattr(
        runtime_oci_layers,
        "canonical_laya_runtime_oci_layer_diff_ids_summary_bytes",
        deep_validate,
    )
    return evidence, calls


def _install_bridge(monkeypatch, module, layer_receipt):
    calls = []

    def bridge(layer_plan, digest, compressed_chunks, consume, **kwargs):
        calls.append((layer_plan, digest, compressed_chunks, kwargs))
        for chunk in compressed_chunks:
            consume(chunk)
        return layer_receipt

    monkeypatch.setattr(
        module.runtime_oci_layers,
        "_verify_laya_oci_layer_diff_id_chunks_with_consumer",
        bridge,
        raising=False,
    )
    return calls


def test_manual_tar_fixture_checksum_padding_and_eof_are_independent_of_tarfile():
    archive = _archive(_tar_entry("data/result.txt", b"science"))
    header = archive[:512]
    checksum_view = bytearray(header)
    checksum_view[148:156] = b"        "
    assert int(header[148:154], 8) == sum(checksum_view)
    assert archive[512:519] == b"science"
    assert archive[519:1024] == b"\0" * 505
    assert archive[-1024:] == b"\0" * 1024


def test_public_surface_matches_openspec_and_has_no_detached_validator():
    from human_feedback import runtime_oci_tar as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_symbols = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "human_feedback.runtime_oci_layers" in imported_modules or (
        "human_feedback" in imported_modules and "runtime_oci_layers" in imported_symbols
    )
    assert not imported_modules & {
        "gzip",
        "io",
        "os",
        "pathlib",
        "subprocess",
        "tarfile",
        "tempfile",
    }
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
    assert public_functions == {
        "canonical_laya_runtime_oci_tar_semantics_summary_bytes",
        "prepare_laya_oci_tar_semantics_plan",
        "verify_laya_oci_tar_semantics_chunks",
    }
    assert public_classes == {
        "LayaOciTarEntry",
        "LayaOciTarSemanticsPlan",
        "LayaRuntimeOciTarSemanticsEvidence",
        "VerifiedLayaOciTarLayer",
    }
    assert not hasattr(module, "validate_laya_oci_tar_chunks")


def test_source_cannot_buffer_payload_or_verify_the_same_stream_twice():
    from human_feedback import runtime_oci_tar as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    forbidden = {
        "BytesIO",
        "TemporaryFile",
        "extract",
        "extractall",
        "open",
        "read_bytes",
        "seek",
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
    assert calls.isdisjoint(forbidden)
    function_tree = ast.parse(inspect.getsource(module.verify_laya_oci_tar_semantics_chunks))
    bridges = [
        node
        for node in ast.walk(function_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_verify_laya_oci_layer_diff_id_chunks_with_consumer"
    ]
    assert len(bridges) == 1
    assert (
        sum(
            isinstance(node, ast.Name) and node.id == "compressed_chunks"
            for node in ast.walk(bridges[0])
        )
        == 1
    )
    assert not any(
        isinstance(node, (ast.For, ast.AsyncFor))
        and isinstance(node.iter, ast.Name)
        and node.iter.id == "compressed_chunks"
        for node in ast.walk(function_tree)
    )


def test_plan_is_sealed_and_identity_bound_to_validated_pr22_evidence(synthetic_pr22):
    from human_feedback.runtime_oci_tar import (
        LayaOciTarSemanticsPlan,
        prepare_laya_oci_tar_semantics_plan,
    )

    evidence, validation_calls = synthetic_pr22
    plan = prepare_laya_oci_tar_semantics_plan(evidence)
    assert validation_calls == [evidence]
    assert type(plan) is LayaOciTarSemanticsPlan
    assert plan.schema_version == PLAN_SCHEMA
    assert plan.layer_evidence is evidence
    assert plan.layer_plan is evidence.plan
    assert plan.layout_plan is evidence.layout_plan
    assert plan.runtime_identity is evidence.runtime_identity
    assert plan.layer_receipts is evidence.receipts
    assert plan.tar_semantics_verified is False
    assert plan.oci_rootfs_verified is False
    assert plan.rootfs_materialized is False
    assert plan.origin_verified is False
    assert all(receipt.computed_diff_id not in repr(plan) for receipt in evidence.receipts)
    for field in fields(plan):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(plan, field.name, getattr(plan, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
            replace(plan, **{field.name: getattr(plan, field.name)})


def test_foreign_or_mutated_pr22_evidence_fails_without_a_stream(synthetic_pr22):
    from human_feedback.runtime_oci_tar import prepare_laya_oci_tar_semantics_plan

    evidence, calls = synthetic_pr22
    reordered = _forge(
        type(evidence),
        **{
            field.name: (
                tuple(reversed(evidence.receipts))
                if field.name == "receipts"
                else getattr(evidence, field.name)
            )
            for field in fields(evidence)
        },
    )
    for invalid in (None, SimpleNamespace(receipts=evidence.receipts), reordered):
        with pytest.raises((TypeError, ValueError), match="layer|evidence|valid") as captured:
            prepare_laya_oci_tar_semantics_plan(invalid)
        _private_error(captured.value, evidence.receipts[0].computed_diff_id)
    assert calls == [reordered]


@pytest.mark.parametrize("width", [1, 17, 511, 512, 4096])
@pytest.mark.parametrize(
    ("archive", "expected_entries", "expected_payload"),
    [
        pytest.param(_archive(), (), 0, id="empty"),
        pytest.param(
            _archive(_tar_entry("data/result.txt", b"science")),
            (("data/result.txt", "0", 7, None),),
            7,
            id="regular",
        ),
    ],
)
def test_empty_and_regular_tar_stream_to_identity_bound_receipts(
    monkeypatch,
    synthetic_pr22,
    archive,
    expected_entries,
    expected_payload,
    width,
):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    layer_receipt = evidence.receipts[0]
    bridge_calls = _install_bridge(monkeypatch, module, layer_receipt)
    receipt = module.verify_laya_oci_tar_semantics_chunks(
        plan, layer_receipt.layer_blob.digest, _chunks(archive, width)
    )
    assert type(receipt) is module.VerifiedLayaOciTarLayer
    assert receipt.plan is plan
    assert receipt.layer_receipt is layer_receipt
    assert receipt.layer_position == 0
    assert type(receipt.entries) is tuple
    assert (
        tuple(
            (entry.path, entry.typeflag, entry.size_bytes, entry.link_target)
            for entry in receipt.entries
        )
        == expected_entries
    )
    assert receipt.payload_size_bytes == expected_payload
    assert receipt.tar_semantics_verified is True
    assert receipt.oci_rootfs_verified is False
    assert receipt.rootfs_materialized is False
    assert receipt.origin_verified is False
    assert len(bridge_calls) == 1 and bridge_calls[0][0] is evidence.plan
    assert "result.txt" not in repr(receipt)
    for value in (*receipt.entries, receipt):
        for field in fields(value):
            if field.name.startswith("_"):
                continue
            with pytest.raises(FrozenInstanceError):
                setattr(value, field.name, getattr(value, field.name))
            with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
                replace(value, **{field.name: getattr(value, field.name)})


@pytest.mark.parametrize("linkname", ["/etc/ssl/certs", "../../shared/target"])
def test_symlink_targets_are_opaque_but_entry_paths_are_root_bound(
    monkeypatch, synthetic_pr22, linkname
):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    _install_bridge(monkeypatch, module, evidence.receipts[0])
    archive = _archive(_tar_entry("safe/link", typeflag=b"2", linkname=linkname))
    receipt = module.verify_laya_oci_tar_semantics_chunks(
        plan, evidence.receipts[0].layer_blob.digest, (archive,)
    )
    assert receipt.entries[0].path == "safe/link"
    assert receipt.entries[0].link_target == linkname
    assert receipt.oci_rootfs_verified is False


@pytest.mark.parametrize(
    ("name", "marker"),
    [
        ("/private/absolute-entry", "private/absolute-entry"),
        ("../private-parent-entry", "private-parent-entry"),
        ("safe/../../private-escape", "private-escape"),
        ("safe\\private-backslash", "private-backslash"),
    ],
)
def test_unsafe_and_duplicate_paths_fail_privately(monkeypatch, synthetic_pr22, name, marker):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    _install_bridge(monkeypatch, module, evidence.receipts[0])
    digest = evidence.receipts[0].layer_blob.digest
    with pytest.raises(ValueError, match="tar|entry|path|valid") as captured:
        module.verify_laya_oci_tar_semantics_chunks(plan, digest, (_archive(_tar_entry(name)),))
    _private_error(captured.value, marker)
    duplicate = _archive(_tar_entry("private/duplicate"), _tar_entry("private/duplicate"))
    with pytest.raises(ValueError, match="tar|entry|duplicate|valid") as captured:
        module.verify_laya_oci_tar_semantics_chunks(plan, digest, (duplicate,))
    _private_error(captured.value, "private/duplicate")


def test_bad_checksum_precedes_size_and_path_and_stops_stream(monkeypatch, synthetic_pr22):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    _install_bridge(monkeypatch, module, evidence.receipts[0])
    corrupt = bytearray(_tar_header("private/checksum-before-path", size=(1 << 32)))
    corrupt[0] ^= 1

    class HostileStream:
        def __init__(self):
            self.requests = 0
            self.sentinel_executed = False

        def __iter__(self):
            return self

        def __next__(self):
            self.requests += 1
            if self.requests == 1:
                return bytes(corrupt)
            self.sentinel_executed = True
            raise AssertionError("private-post-checksum-sentinel")

    stream = HostileStream()
    with pytest.raises(ValueError, match="checksum|tar|valid") as captured:
        module.verify_laya_oci_tar_semantics_chunks(
            plan, evidence.receipts[0].layer_blob.digest, stream
        )
    assert stream.requests == 1 and stream.sentinel_executed is False
    _private_error(captured.value, "private/checksum-before-path", "private-post-checksum-sentinel")


def test_truncation_termination_padding_and_caps_fail_closed(monkeypatch, synthetic_pr22):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    _install_bridge(monkeypatch, module, evidence.receipts[0])
    digest = evidence.receipts[0].layer_blob.digest
    entry = _tar_entry("private/payload", b"x")
    bad_padding = bytearray(_archive(entry))
    bad_padding[513] = 1
    for archive in (
        _archive(entry)[:-1],
        _archive(entry, terminal_blocks=1),
        _archive(entry) + _tar_entry("private/after-eof"),
        bytes(bad_padding),
    ):
        with pytest.raises(ValueError, match="tar|padding|terminat|truncat|valid") as captured:
            module.verify_laya_oci_tar_semantics_chunks(plan, digest, _chunks(archive, 127))
        _private_error(captured.value, "private/payload", "private/after-eof")
    assert module.MAX_OCI_TAR_CHUNK_BYTES == MAX_TAR_CHUNK_BYTES
    assert module.MAX_OCI_TAR_ENTRIES == MAX_TAR_ENTRIES
    for invalid in (False, 0, -1, 1.0, MAX_TAR_ENTRIES + 1):
        with pytest.raises((TypeError, ValueError), match="entry|limit|valid"):
            module.verify_laya_oci_tar_semantics_chunks(plan, digest, (), max_entries=invalid)
    with pytest.raises((TypeError, ValueError), match="chunk|bytes|limit|valid"):
        module.verify_laya_oci_tar_semantics_chunks(
            plan, digest, (b"x" * (MAX_TAR_CHUNK_BYTES + 1),)
        )


def test_invalid_plan_or_digest_fails_before_stream_consumption(synthetic_pr22):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)

    class HostileChunks:
        def __iter__(self):
            raise AssertionError("private-stream-consumed")

    for invalid_plan, invalid_digest in (
        (SimpleNamespace(layer_evidence=evidence), evidence.plan.layer_blobs[0].digest),
        (plan, "sha256:" + ("f" * 64)),
        (plan, evidence.plan.layer_blobs[0].digest.upper()),
    ):
        with pytest.raises((TypeError, ValueError), match="plan|digest|layer|valid") as captured:
            module.verify_laya_oci_tar_semantics_chunks(
                invalid_plan, invalid_digest, HostileChunks()
            )
        _private_error(captured.value, "private-stream-consumed")


def test_summary_rejects_unsealed_evidence_and_no_public_finalizer_exists():
    from human_feedback import runtime_oci_tar as module

    assert not hasattr(module, "finalize_laya_runtime_oci_tar_semantics_evidence")
    assert not hasattr(module, "from_laya_oci_tar_layer_receipts")
    for invalid in (
        None,
        SimpleNamespace(schema_version="private-tar-evidence-proxy"),
        object.__new__(module.LayaRuntimeOciTarSemanticsEvidence),
    ):
        with pytest.raises((TypeError, ValueError), match="evidence|seal|valid") as captured:
            module.canonical_laya_runtime_oci_tar_semantics_summary_bytes(invalid)
        _private_error(captured.value, "private-tar-evidence-proxy")
