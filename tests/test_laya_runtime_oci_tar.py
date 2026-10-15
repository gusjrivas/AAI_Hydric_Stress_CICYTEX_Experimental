import ast
import gzip
import hashlib
import inspect
import json
import traceback
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

PLAN_SCHEMA = "laya-oci-tar-semantics-plan-v1"
MAX_TAR_CHUNK_BYTES = 1024 * 1024
MAX_TAR_ENTRIES = 65536
MAX_TAR_PATH_BYTES = 4096
MAX_TAR_LINK_BYTES = 4096
MAX_TAR_PAX_RECORD_BYTES = 64 * 1024
MAX_TAR_PAX_BYTES = 1024 * 1024
MAX_TAR_ENTRY_PAYLOAD_BYTES = 2 * 1024 * 1024 * 1024
MAX_TAR_PAYLOAD_BYTES = 3 * 1024 * 1024 * 1024
MAX_TAR_BYTES = MAX_TAR_PAYLOAD_BYTES + (MAX_TAR_ENTRIES + 2) * 512


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
    magic: bytes = b"ustar\0",
    version: bytes = b"00",
) -> bytes:
    name_bytes = name.encode("utf-8")
    link_bytes = linkname.encode("utf-8")
    assert (
        len(name_bytes) <= 100
        and len(link_bytes) <= 100
        and len(typeflag) == 1
        and len(magic) == 6
        and len(version) == 2
    )
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
    header[257:263] = magic
    header[263:265] = version
    header[148:156] = f"{sum(header):06o}".encode("ascii") + b"\0 "
    return bytes(header)


def _tar_entry(
    name: str,
    payload: bytes = b"",
    *,
    typeflag: bytes = b"0",
    linkname: str = "",
    gnu: bool = False,
) -> bytes:
    return (
        _tar_header(
            name,
            size=len(payload),
            typeflag=typeflag,
            linkname=linkname,
            magic=b"ustar " if gnu else b"ustar\0",
            version=b" \0" if gnu else b"00",
        )
        + payload
        + (b"\0" * ((-len(payload)) % 512))
    )


def _archive(*entries: bytes, terminal_blocks: int = 2) -> bytes:
    return b"".join(entries) + (b"\0" * 512 * terminal_blocks)


def _pax_record(key: str, value: str) -> bytes:
    body = f" {key}={value}\n".encode()
    length = len(body) + 1
    while True:
        record = str(length).encode("ascii") + body
        if len(record) == length:
            return record
        length = len(record)


def _pax_entry(records: tuple[tuple[str, str], ...], *, global_: bool = False) -> bytes:
    payload = b"".join(_pax_record(key, value) for key, value in records)
    return _tar_entry(
        "PaxHeaders/profile",
        payload,
        typeflag=b"g" if global_ else b"x",
    )


def _gnu_extension(value: str, *, link: bool = False) -> bytes:
    return _tar_entry(
        "././@LongLink",
        value.encode("utf-8") + b"\0",
        typeflag=b"K" if link else b"L",
        gnu=True,
    )


def _tar_entry_with_effective_size(
    name: str,
    payload: bytes,
    *,
    header_size: int,
) -> bytes:
    return _tar_header(name, size=header_size) + payload + (b"\0" * ((-len(payload)) % 512))


def _header_with_recomputed_checksum(header: bytes, start: int, value: bytes) -> bytes:
    mutated = bytearray(header)
    mutated[start : start + len(value)] = value
    mutated[148:156] = b"        "
    mutated[148:156] = f"{sum(mutated):06o}".encode("ascii") + b"\0 "
    return bytes(mutated)


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

    identity = SimpleNamespace(schema_version="laya-runtime-identity-ref-v1", sha256="1" * 64)
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


def _install_bridge(monkeypatch, module, historical_receipt):
    calls = []

    def bridge(layer_plan, digest, compressed_chunks, consume, **kwargs):
        uncompressed_size = 0
        for chunk in compressed_chunks:
            consume(chunk)
            uncompressed_size += len(chunk)
        fresh = _forge(
            type(historical_receipt),
            **{
                field.name: (
                    uncompressed_size
                    if field.name == "uncompressed_size_bytes"
                    else getattr(historical_receipt, field.name)
                )
                for field in fields(historical_receipt)
            },
        )
        calls.append((layer_plan, digest, compressed_chunks, kwargs, fresh))
        return fresh

    monkeypatch.setattr(
        module.runtime_oci_layers,
        "_verify_laya_oci_layer_diff_id_chunks_with_consumer",
        bridge,
        raising=False,
    )
    return calls


def _verify_archive(monkeypatch, synthetic_pr22, archive: bytes):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    historical = evidence.receipts[0]
    object.__setattr__(historical, "uncompressed_size_bytes", len(archive))
    _install_bridge(monkeypatch, module, historical)
    return module.verify_laya_oci_tar_semantics_chunks(
        plan,
        historical.layer_blob.digest,
        _chunks(archive, 173),
    )


def _empty_tar_receipts(module, plan, layer_evidence):
    receipts = []
    for position, historical in enumerate(layer_evidence.receipts):
        fresh = _forge(
            type(historical),
            **{field.name: getattr(historical, field.name) for field in fields(historical)},
        )
        receipts.append(
            module.VerifiedLayaOciTarLayer(
                plan=plan,
                layer_receipt=fresh,
                layer_position=position,
                entries=(),
                payload_size_bytes=0,
                tar_size_bytes=fresh.uncompressed_size_bytes,
                _factory_token=module._FACTORY_TOKEN,
            )
        )
    return tuple(receipts)


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
    summary_tree = ast.parse(
        inspect.getsource(module.canonical_laya_runtime_oci_tar_semantics_summary_bytes)
    )
    summary_attributes = {
        node.attr for node in ast.walk(summary_tree) if isinstance(node, ast.Attribute)
    }
    assert "sha256" in summary_attributes
    assert "identity_sha256" not in summary_attributes


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
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
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
    object.__setattr__(layer_receipt, "uncompressed_size_bytes", len(archive))
    bridge_calls = _install_bridge(monkeypatch, module, layer_receipt)
    receipt = module.verify_laya_oci_tar_semantics_chunks(
        plan, layer_receipt.layer_blob.digest, _chunks(archive, width)
    )
    assert type(receipt) is module.VerifiedLayaOciTarLayer
    assert receipt.plan is plan
    assert receipt.layer_receipt is bridge_calls[0][4]
    assert receipt.layer_receipt is not layer_receipt
    assert receipt.layer_receipt.layer_position == layer_receipt.layer_position
    assert receipt.layer_receipt.layer_blob is layer_receipt.layer_blob
    assert receipt.layer_receipt.computed_diff_id == layer_receipt.computed_diff_id
    assert receipt.layer_receipt.uncompressed_size_bytes == len(archive)
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
    assert receipt.tar_size_bytes == receipt.layer_receipt.uncompressed_size_bytes
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


def test_real_pr22_bridge_verifies_gzip_diff_id_and_tar_end_to_end(
    monkeypatch,
    synthetic_pr22,
):
    from human_feedback import runtime_oci_layers, runtime_oci_tar

    layer_evidence, _ = synthetic_pr22
    tar_bytes = _archive(_tar_entry("science/result.txt", b"validated"))
    compressed = gzip.compress(tar_bytes, mtime=0)
    blob_digest = "sha256:" + hashlib.sha256(compressed).hexdigest()
    diff_id = "sha256:" + hashlib.sha256(tar_bytes).hexdigest()
    layer_plan = layer_evidence.plan
    blob = layer_plan.layer_blobs[0]
    blob.digest = blob_digest
    blob.size_bytes = len(compressed)
    object.__setattr__(
        layer_plan,
        "declared_diff_ids",
        (diff_id, *layer_plan.declared_diff_ids[1:]),
    )
    historical = layer_evidence.receipts[0]
    object.__setattr__(historical, "declared_diff_id", layer_plan.declared_diff_ids[0])
    object.__setattr__(historical, "computed_diff_id", layer_plan.declared_diff_ids[0])
    object.__setattr__(historical, "uncompressed_size_bytes", len(tar_bytes))
    monkeypatch.setattr(
        runtime_oci_layers,
        "_authorize_layer",
        lambda candidate, digest: (layer_plan, 0),
    )
    compressed_calls = []

    def verify_compressed(layout_plan, digest, chunks):
        captured = bytearray()
        for chunk in chunks:
            captured.extend(chunk)
        compressed_calls.append((layout_plan, digest, bytes(captured)))
        assert digest == blob_digest
        assert len(captured) == blob.size_bytes
        assert "sha256:" + hashlib.sha256(captured).hexdigest() == blob_digest
        return layer_plan.layer_receipts[0]

    monkeypatch.setattr(
        runtime_oci_layers.runtime_oci_layout,
        "verify_laya_oci_blob_chunks",
        verify_compressed,
    )
    plan = runtime_oci_tar.prepare_laya_oci_tar_semantics_plan(layer_evidence)

    receipt = runtime_oci_tar.verify_laya_oci_tar_semantics_chunks(
        plan,
        blob_digest,
        _chunks(compressed, 7),
    )

    assert len(compressed_calls) == 1
    assert compressed_calls[0][2] == compressed
    assert receipt.layer_receipt is not historical
    assert receipt.layer_receipt.layer_blob is historical.layer_blob
    assert receipt.layer_receipt.computed_diff_id == diff_id
    assert receipt.layer_receipt.uncompressed_size_bytes == len(tar_bytes)
    assert receipt.tar_size_bytes == len(tar_bytes)
    assert receipt.payload_size_bytes == len(b"validated")
    assert len(receipt.entries) == 1
    assert receipt.entries[0].path == "science/result.txt"
    assert receipt.entries[0].typeflag == "0"
    assert receipt.entries[0].size_bytes == len(b"validated")
    assert receipt.tar_semantics_verified is True
    assert receipt.oci_rootfs_verified is False


@pytest.mark.parametrize("linkname", ["/etc/ssl/certs", "../../shared/target"])
def test_symlink_targets_are_opaque_but_entry_paths_are_root_bound(
    monkeypatch, synthetic_pr22, linkname
):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    archive = _archive(_tar_entry("safe/link", typeflag=b"2", linkname=linkname))
    object.__setattr__(evidence.receipts[0], "uncompressed_size_bytes", len(archive))
    _install_bridge(monkeypatch, module, evidence.receipts[0])
    receipt = module.verify_laya_oci_tar_semantics_chunks(
        plan, evidence.receipts[0].layer_blob.digest, (archive,)
    )
    assert receipt.entries[0].path == "safe/link"
    assert receipt.entries[0].link_target == linkname
    assert receipt.oci_rootfs_verified is False


def test_pax_local_overrides_global_and_produces_only_effective_entries(
    monkeypatch,
    synthetic_pr22,
):
    long_global = "global/" + ("g" * 120)
    long_local = "local/" + ("p" * 120)
    archive = _archive(
        _pax_entry((("path", long_global),), global_=True),
        _pax_entry((("path", long_local), ("size", "7"))),
        _tar_entry_with_effective_size("raw-name", b"science", header_size=1),
    )

    receipt = _verify_archive(monkeypatch, synthetic_pr22, archive)

    assert tuple((entry.path, entry.size_bytes) for entry in receipt.entries) == ((long_local, 7),)
    assert receipt.payload_size_bytes == 7


@pytest.mark.parametrize("typeflag", ["1", "2"], ids=("hardlink", "symlink"))
@pytest.mark.parametrize("target", ["/opaque/absolute", "../../opaque/parent"])
def test_pax_and_gnu_long_links_remain_opaque_metadata(
    monkeypatch,
    synthetic_pr22,
    typeflag,
    target,
):
    pax_path = "links/" + ("p" * 120)
    archive = _archive(
        _pax_entry((("path", pax_path), ("linkpath", target))),
        _tar_entry("raw-link", typeflag=typeflag.encode("ascii"), linkname="raw-target"),
    )

    receipt = _verify_archive(monkeypatch, synthetic_pr22, archive)

    assert len(receipt.entries) == 1
    assert receipt.entries[0].path == pax_path
    assert receipt.entries[0].link_target == target
    assert receipt.entries[0].size_bytes == 0


def test_gnu_longname_and_longlink_apply_once_without_becoming_entries(
    monkeypatch,
    synthetic_pr22,
):
    long_name = "gnu/" + ("n" * 150)
    long_link = "../" + ("target/" * 20)
    archive = _archive(
        _gnu_extension(long_name),
        _tar_entry("raw-file", b"x", gnu=True),
        _gnu_extension(long_link, link=True),
        _tar_entry("safe/link", typeflag=b"2", linkname="raw-target", gnu=True),
    )

    receipt = _verify_archive(monkeypatch, synthetic_pr22, archive)

    assert tuple(entry.path for entry in receipt.entries) == (long_name, "safe/link")
    assert receipt.entries[1].link_target == long_link


@pytest.mark.parametrize(
    "archive",
    [
        pytest.param(
            _archive(
                _tar_entry("././@LongLink", b"gnu/name\0", typeflag=b"L"),
                _tar_entry("raw-name"),
            ),
            id="posix-longname",
        ),
        pytest.param(
            _archive(_gnu_extension("gnu/name"), _tar_entry("raw-name")),
            id="gnu-extension-posix-target",
        ),
        pytest.param(
            _archive(
                _pax_entry((("path", "pax/name"),)),
                _tar_entry("raw-name", gnu=True),
            ),
            id="posix-pax-gnu-target",
        ),
        pytest.param(
            _archive(
                _tar_entry(
                    "PaxHeaders/profile",
                    _pax_record("path", "pax/name"),
                    typeflag=b"x",
                    gnu=True,
                ),
                _tar_entry("raw-name", gnu=True),
            ),
            id="gnu-pax",
        ),
        pytest.param(
            _archive(
                _tar_header(
                    "././@LongLink",
                    size=9,
                    typeflag=b"L",
                    magic=b"ustar ",
                    version=b"00",
                )
                + b"gnu/name\0"
                + (b"\0" * 503),
                _tar_entry("raw-name", gnu=True),
            ),
            id="gnu-magic-posix-version",
        ),
        pytest.param(
            _archive(
                _tar_header(
                    "././@LongLink",
                    size=9,
                    typeflag=b"L",
                    magic=b"ustar\0",
                    version=b" \0",
                )
                + b"gnu/name\0"
                + (b"\0" * 503),
                _tar_entry("raw-name", gnu=True),
            ),
            id="posix-magic-gnu-version",
        ),
    ],
)
def test_posix_and_gnu_header_profiles_cannot_be_crossed(
    monkeypatch,
    synthetic_pr22,
    archive,
):
    with pytest.raises(ValueError, match="tar|gnu|pax|profile|metadata|valid"):
        _verify_archive(monkeypatch, synthetic_pr22, archive)


def test_posix_ustar_prefix_is_composed_into_the_effective_path(
    monkeypatch,
    synthetic_pr22,
):
    header = _header_with_recomputed_checksum(
        _tar_header("result.txt"),
        345,
        b"safe/prefix",
    )

    receipt = _verify_archive(monkeypatch, synthetic_pr22, _archive(header))

    assert len(receipt.entries) == 1
    assert receipt.entries[0].path == "safe/prefix/result.txt"


@pytest.mark.parametrize(
    ("offset", "value"),
    [
        pytest.param(345, b"00000000001\0", id="oldgnu-atime"),
        pytest.param(357, b"00000000001\0", id="oldgnu-ctime"),
        pytest.param(369, b"00000000001\0", id="oldgnu-offset"),
        pytest.param(386, b"00000000001\0", id="oldgnu-sparse-map"),
        pytest.param(482, b"1", id="oldgnu-sparse-extended"),
        pytest.param(483, b"00000000001\0", id="oldgnu-real-size"),
    ],
)
def test_gnu_headers_reject_oldgnu_extra_and_sparse_fields_before_path_use(
    monkeypatch,
    synthetic_pr22,
    offset,
    value,
):
    header = _header_with_recomputed_checksum(
        _tar_header(
            "safe/result.txt",
            magic=b"ustar ",
            version=b" \0",
        ),
        offset,
        value,
    )

    with pytest.raises(ValueError, match="tar|gnu|sparse|profile|metadata|valid") as captured:
        _verify_archive(monkeypatch, synthetic_pr22, _archive(header))
    _private_error(captured.value, "safe/result.txt")


@pytest.mark.parametrize(
    "extension",
    [
        pytest.param(_tar_entry("PaxHeaders/dangling", b"bad", typeflag=b"x"), id="length"),
        pytest.param(
            _tar_entry("PaxHeaders/utf8", b"12 path=bad\xff\n", typeflag=b"x"),
            id="utf8",
        ),
        pytest.param(
            _pax_entry((("path", "one"), ("path", "two"))),
            id="duplicate-path",
        ),
        pytest.param(_pax_entry((("size", "1"), ("size", "2"))), id="duplicate-size"),
        pytest.param(_gnu_extension("private/dangling"), id="dangling-gnu"),
    ],
)
def test_invalid_or_dangling_extended_metadata_fails_privately(
    monkeypatch,
    synthetic_pr22,
    extension,
):
    archive = _archive(extension)
    with pytest.raises(ValueError, match="tar|pax|gnu|metadata|record|valid") as captured:
        _verify_archive(monkeypatch, synthetic_pr22, archive)
    _private_error(captured.value, "private/dangling", "bad")


@pytest.mark.parametrize(
    "archive",
    [
        pytest.param(
            _archive(_tar_entry("same/path"), _tar_entry("./same/path")),
            id="normalized",
        ),
        pytest.param(
            _archive(
                _tar_entry("same/path"),
                _pax_entry((("path", "same/path"),)),
                _tar_entry("other/path"),
            ),
            id="pax",
        ),
        pytest.param(
            _archive(
                _tar_entry("same/path"),
                _gnu_extension("same/path"),
                _tar_entry("other/path", gnu=True),
            ),
            id="gnu",
        ),
    ],
)
def test_effective_paths_are_unique_after_normalization_and_extensions(
    monkeypatch,
    synthetic_pr22,
    archive,
):
    with pytest.raises(ValueError, match="tar|entry|path|duplicate|valid"):
        _verify_archive(monkeypatch, synthetic_pr22, archive)


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param(_tar_entry("private/sparse", typeflag=b"S"), id="gnu-sparse"),
        pytest.param(
            _pax_entry((("GNU.sparse.map", "0,1"),)),
            id="pax-sparse",
        ),
        pytest.param(_tar_entry("private/char", typeflag=b"3"), id="char-device"),
        pytest.param(_tar_entry("private/block", typeflag=b"4"), id="block-device"),
        pytest.param(_tar_entry("private/fifo", typeflag=b"6"), id="fifo"),
        pytest.param(_tar_entry("private/unknown", typeflag=b"9"), id="unknown"),
    ],
)
def test_sparse_devices_fifo_and_unknown_types_are_rejected(
    monkeypatch,
    synthetic_pr22,
    entry,
):
    with pytest.raises(ValueError, match="tar|pax|sparse|type|valid") as captured:
        _verify_archive(monkeypatch, synthetic_pr22, _archive(entry))
    _private_error(captured.value, "private/sparse", "private/char", "private/block")


def test_hardlinks_and_oci_whiteout_names_are_valid_but_not_applied(
    monkeypatch,
    synthetic_pr22,
):
    archive = _archive(
        _tar_entry("data/source", b"x"),
        _tar_entry("data/hard", typeflag=b"1", linkname="data/source"),
        _tar_entry("data/.wh.deleted"),
        _tar_entry("data/.wh..wh..opq"),
    )

    receipt = _verify_archive(monkeypatch, synthetic_pr22, archive)

    assert tuple((entry.path, entry.typeflag) for entry in receipt.entries) == (
        ("data/source", "0"),
        ("data/hard", "1"),
        ("data/.wh.deleted", "0"),
        ("data/.wh..wh..opq", "0"),
    )
    assert receipt.entries[1].link_target == "data/source"
    assert receipt.oci_rootfs_verified is False


def test_public_extended_metadata_caps_and_oversized_record_fail_fast(
    monkeypatch,
    synthetic_pr22,
):
    from human_feedback import runtime_oci_tar as module

    assert module.MAX_OCI_TAR_PATH_BYTES == MAX_TAR_PATH_BYTES
    assert module.MAX_OCI_TAR_LINK_BYTES == MAX_TAR_LINK_BYTES
    assert module.MAX_OCI_TAR_PAX_RECORD_BYTES == MAX_TAR_PAX_RECORD_BYTES
    assert module.MAX_OCI_TAR_PAX_BYTES == MAX_TAR_PAX_BYTES
    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    _install_bridge(monkeypatch, module, evidence.receipts[0])
    oversized_header = _tar_header(
        "PaxHeaders/oversized",
        size=MAX_TAR_PAX_RECORD_BYTES + 1,
        typeflag=b"x",
    )

    class HostileChunks:
        def __init__(self):
            self.requests = 0
            self.sentinel_executed = False

        def __iter__(self):
            return self

        def __next__(self):
            self.requests += 1
            if self.requests == 1:
                return oversized_header
            self.sentinel_executed = True
            raise AssertionError("private-pax-limit-sentinel")

    chunks = HostileChunks()
    with pytest.raises(ValueError, match="pax|record|limit|valid") as captured:
        module.verify_laya_oci_tar_semantics_chunks(
            plan,
            evidence.receipts[0].layer_blob.digest,
            chunks,
        )
    assert chunks.requests == 1 and chunks.sentinel_executed is False
    _private_error(captured.value, "private-pax-limit-sentinel")


def test_public_payload_and_tar_caps_are_exact_and_enforced_incrementally(
    monkeypatch,
    synthetic_pr22,
):
    from human_feedback import runtime_oci_tar as module

    assert module.MAX_OCI_TAR_ENTRY_PAYLOAD_BYTES == MAX_TAR_ENTRY_PAYLOAD_BYTES
    assert module.MAX_OCI_TAR_PAYLOAD_BYTES == MAX_TAR_PAYLOAD_BYTES
    assert module.MAX_OCI_TAR_BYTES == MAX_TAR_BYTES
    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    _install_bridge(monkeypatch, module, evidence.receipts[0])
    oversized_header = _tar_header(
        "private/oversized-entry",
        size=MAX_TAR_ENTRY_PAYLOAD_BYTES + 1,
    )

    class HostileChunks:
        def __init__(self):
            self.requests = 0
            self.sentinel_executed = False

        def __iter__(self):
            return self

        def __next__(self):
            self.requests += 1
            if self.requests == 1:
                return oversized_header
            self.sentinel_executed = True
            raise AssertionError("private-payload-limit-sentinel")

    chunks = HostileChunks()
    with pytest.raises(ValueError, match="tar|entry|payload|limit|valid") as captured:
        module.verify_laya_oci_tar_semantics_chunks(
            plan,
            evidence.receipts[0].layer_blob.digest,
            chunks,
        )
    assert chunks.requests == 1 and chunks.sentinel_executed is False
    _private_error(
        captured.value,
        "private/oversized-entry",
        "private-payload-limit-sentinel",
    )

    monkeypatch.setattr(module, "MAX_OCI_TAR_PAYLOAD_BYTES", 1)
    with pytest.raises(ValueError, match="tar|payload|limit|valid"):
        _verify_archive(
            monkeypatch,
            synthetic_pr22,
            _archive(_tar_entry("one", b"x"), _tar_entry("two", b"y")),
        )
    monkeypatch.setattr(module, "MAX_OCI_TAR_PAYLOAD_BYTES", MAX_TAR_PAYLOAD_BYTES)
    archive = _archive(_tar_entry("small", b"x"))
    monkeypatch.setattr(module, "MAX_OCI_TAR_BYTES", len(archive) - 1)
    with pytest.raises(ValueError, match="tar|aggregate|limit|valid"):
        _verify_archive(monkeypatch, synthetic_pr22, archive)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("path", "p" * (MAX_TAR_PATH_BYTES + 1)),
        ("linkpath", "l" * (MAX_TAR_LINK_BYTES + 1)),
    ],
)
def test_pax_effective_path_and_link_caps_are_enforced(
    monkeypatch,
    synthetic_pr22,
    key,
    value,
):
    target = _tar_entry("safe/link", typeflag=b"2", linkname="safe")
    archive = _archive(_pax_entry(((key, value),)), target)
    with pytest.raises(ValueError, match="pax|path|link|limit|valid"):
        _verify_archive(monkeypatch, synthetic_pr22, archive)


@pytest.mark.parametrize(
    "archive",
    [
        pytest.param(
            _archive(
                _pax_entry((("size", "1"),)),
                _tar_entry("safe/link", typeflag=b"2", linkname="target"),
            ),
            id="size-on-link",
        ),
        pytest.param(
            _archive(
                _pax_entry((("linkpath", "target"),)),
                _tar_entry("safe/regular"),
            ),
            id="linkpath-on-regular",
        ),
    ],
)
def test_conflicting_extended_metadata_and_target_type_fail_closed(
    monkeypatch,
    synthetic_pr22,
    archive,
):
    with pytest.raises(ValueError, match="tar|pax|metadata|type|size|link|valid"):
        _verify_archive(monkeypatch, synthetic_pr22, archive)


def test_aggregate_pax_payload_cap_is_public_and_enforced(
    monkeypatch,
    synthetic_pr22,
):
    entries = []
    for index in range(260):
        path = f"bulk-{index:03d}/" + ("p" * 4070)
        entries.extend((_pax_entry((("path", path),)), _tar_entry(f"raw-{index}")))
    archive = _archive(*entries)
    assert (
        sum(len(_pax_record("path", f"bulk-{index:03d}/" + ("p" * 4070))) for index in range(260))
        > MAX_TAR_PAX_BYTES
    )

    with pytest.raises(ValueError, match="pax|aggregate|limit|valid"):
        _verify_archive(monkeypatch, synthetic_pr22, archive)


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


@pytest.mark.parametrize(
    ("offset", "invalid_octal"),
    [
        (100, b"0000008\0"),
        (108, b"0000008\0"),
        (116, b"0000008\0"),
        (136, b"00000000008\0"),
    ],
    ids=("mode", "uid", "gid", "mtime"),
)
def test_all_numeric_header_fields_require_valid_octal_after_checksum(
    monkeypatch,
    synthetic_pr22,
    offset,
    invalid_octal,
):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    digest = evidence.receipts[0].layer_blob.digest
    invalid_header = _header_with_recomputed_checksum(
        _tar_header("private/numeric-field"), offset, invalid_octal
    )
    archive = _archive(invalid_header)
    object.__setattr__(evidence.receipts[0], "uncompressed_size_bytes", len(archive))
    _install_bridge(monkeypatch, module, evidence.receipts[0])
    with pytest.raises(ValueError, match="tar|numeric|octal|header|valid") as captured:
        module.verify_laya_oci_tar_semantics_chunks(plan, digest, (archive,))
    _private_error(captured.value, "private/numeric-field")


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


def test_entry_and_receipt_deep_seals_reject_forged_paths_duplicates_and_totals(
    synthetic_pr22,
):
    from human_feedback import runtime_oci_tar as module

    evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(evidence)
    entry = module.LayaOciTarEntry(
        path="data/result.txt",
        typeflag="0",
        size_bytes=7,
        link_target=None,
        _factory_token=module._FACTORY_TOKEN,
    )
    historical = evidence.receipts[0]
    object.__setattr__(historical, "uncompressed_size_bytes", 2048)
    fresh = _forge(
        type(historical),
        **{field.name: getattr(historical, field.name) for field in fields(historical)},
    )
    receipt = module.VerifiedLayaOciTarLayer(
        plan=plan,
        layer_receipt=fresh,
        layer_position=0,
        entries=(entry,),
        payload_size_bytes=7,
        tar_size_bytes=2048,
        _factory_token=module._FACTORY_TOKEN,
    )
    receipt.__post_init__(module._FACTORY_TOKEN)

    invalid_entries = (
        _forge(
            type(entry),
            path="../private-forged-entry",
            typeflag="0",
            size_bytes=7,
            link_target=None,
        ),
        _forge(
            type(entry),
            path="data/result.txt",
            typeflag="0",
            size_bytes=7,
            link_target="private-forged-link",
        ),
    )
    for invalid in invalid_entries:
        with pytest.raises((TypeError, ValueError), match="entry|path|link|size|valid"):
            invalid.__post_init__(module._FACTORY_TOKEN)

    receipt_values = {field.name: getattr(receipt, field.name) for field in fields(receipt)}
    mutations = (
        {"entries": (entry, entry)},
        {"payload_size_bytes": 8},
        {"tar_size_bytes": 1024},
        {"entries": (invalid_entries[0],)},
    )
    for changes in mutations:
        forged = _forge(type(receipt), **(receipt_values | changes))
        with pytest.raises(
            (TypeError, ValueError), match="receipt|entry|duplicate|payload|size|valid"
        ):
            forged.__post_init__(module._FACTORY_TOKEN)

    forged_fresh = _forge(
        type(fresh),
        **{
            field.name: (
                1024 if field.name == "uncompressed_size_bytes" else getattr(fresh, field.name)
            )
            for field in fields(fresh)
        },
    )
    forged_receipt = _forge(
        type(receipt),
        **(
            receipt_values
            | {
                "layer_receipt": forged_fresh,
                "tar_size_bytes": 1024,
            }
        ),
    )
    with pytest.raises((TypeError, ValueError), match="receipt|historical|uncompressed|size|valid"):
        forged_receipt.__post_init__(module._FACTORY_TOKEN)


@pytest.mark.parametrize(
    ("typeflag", "link_target"),
    [("1", "data/target"), ("2", "../target"), ("5", None)],
    ids=("hardlink", "symlink", "directory"),
)
def test_non_regular_entry_deep_seal_rejects_nonzero_size(
    synthetic_pr22,
    typeflag,
    link_target,
):
    from human_feedback import runtime_oci_tar as module

    forged = _forge(
        module.LayaOciTarEntry,
        path="data/private-nonregular",
        typeflag=typeflag,
        size_bytes=1,
        link_target=link_target,
    )
    with pytest.raises((TypeError, ValueError), match="entry|size|valid"):
        forged.__post_init__(module._FACTORY_TOKEN)


def test_tar_evidence_and_summary_inherit_every_pr22_claim_and_only_elevate_tar(
    synthetic_pr22,
):
    from human_feedback import runtime_oci_tar as module

    layer_evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(layer_evidence)
    receipts = []
    for position, historical in enumerate(layer_evidence.receipts):
        fresh = _forge(
            type(historical),
            **{
                field.name: (
                    1024
                    if field.name == "uncompressed_size_bytes"
                    else getattr(historical, field.name)
                )
                for field in fields(historical)
            },
        )
        receipts.append(
            module.VerifiedLayaOciTarLayer(
                plan=plan,
                layer_receipt=fresh,
                layer_position=position,
                entries=(),
                payload_size_bytes=0,
                tar_size_bytes=1024,
                _factory_token=module._FACTORY_TOKEN,
            )
        )
    evidence = module.LayaRuntimeOciTarSemanticsEvidence(
        schema_version="laya-runtime-oci-tar-semantics-evidence-v1",
        plan=plan,
        runtime_identity=layer_evidence.runtime_identity,
        receipts=tuple(receipts),
        _factory_token=module._FACTORY_TOKEN,
    )

    pr22_bindings = {
        "schema_version",
        "plan",
        "config_evidence",
        "layout_evidence",
        "layout_plan",
        "runtime_identity",
        "receipts",
    }
    inherited_claims = {
        field.name for field in fields(layer_evidence) if field.name not in pr22_bindings
    }
    tar_bindings = {"schema_version", "plan", "runtime_identity", "receipts"}
    assert {field.name for field in fields(evidence)} - tar_bindings == inherited_claims
    expected_claims = {
        claim: (True if claim == "tar_semantics_verified" else getattr(layer_evidence, claim))
        for claim in inherited_claims
    }
    assert (
        sum(value is True for value in expected_claims.values())
        == sum(getattr(layer_evidence, claim) is True for claim in inherited_claims) + 1
    )
    for claim, expected in expected_claims.items():
        assert getattr(evidence, claim) is expected

    summary = json.loads(module.canonical_laya_runtime_oci_tar_semantics_summary_bytes(evidence))
    assert summary == {
        "schema_version": evidence.schema_version,
        "plan_schema_version": plan.schema_version,
        "runtime_identity_sha256": layer_evidence.runtime_identity.sha256,
        **expected_claims,
    }
    rendered = repr(evidence)
    assert all(receipt.layer_blob.digest not in rendered for receipt in layer_evidence.receipts)

    evidence_values = {field.name: getattr(evidence, field.name) for field in fields(evidence)}
    for claim, expected in expected_claims.items():
        forged = _forge(type(evidence), **(evidence_values | {claim: not expected}))
        with pytest.raises((TypeError, ValueError), match="evidence|claim|valid") as captured:
            module.canonical_laya_runtime_oci_tar_semantics_summary_bytes(forged)
        _private_error(captured.value)


def test_private_tar_capture_authority_is_all_or_nothing_and_seals_evidence(
    synthetic_pr22,
):
    from human_feedback import runtime_oci_tar as module

    layer_evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(layer_evidence)
    receipts = _empty_tar_receipts(module, plan, layer_evidence)
    assert callable(module._seal_laya_oci_tar_semantics_capture_authority)
    assert callable(module._seal_laya_runtime_oci_tar_semantics_evidence)
    authority = module._seal_laya_oci_tar_semantics_capture_authority(
        plan,
        receipts,
        controls_captured_from_same_root=True,
        blobs_captured_from_same_root=True,
        inventory_captured_from_same_root=True,
        final_fd_sweep_verified=True,
        descriptors_closed_before_seal=True,
    )
    assert type(authority) is module._LayaOciTarSemanticsCaptureAuthority
    assert authority.plan is plan
    assert authority.receipts is receipts
    evidence = module._seal_laya_runtime_oci_tar_semantics_evidence(authority)
    assert type(evidence) is module.LayaRuntimeOciTarSemanticsEvidence
    assert evidence.plan is plan
    assert evidence.receipts is receipts
    assert evidence.runtime_identity is layer_evidence.runtime_identity
    assert evidence.tar_semantics_verified is True
    assert evidence.oci_rootfs_verified is False
    module.canonical_laya_runtime_oci_tar_semantics_summary_bytes(evidence)

    keyword_flags = {
        "controls_captured_from_same_root": True,
        "blobs_captured_from_same_root": True,
        "inventory_captured_from_same_root": True,
        "final_fd_sweep_verified": True,
        "descriptors_closed_before_seal": True,
    }
    for flag in keyword_flags:
        for invalid in (False, 1, None):
            with pytest.raises((TypeError, ValueError), match="authority|capture|seal|valid"):
                module._seal_laya_oci_tar_semantics_capture_authority(
                    plan,
                    receipts,
                    **(keyword_flags | {flag: invalid}),
                )
    for invalid_receipts in (
        list(receipts),
        receipts[:-1],
        receipts + (receipts[-1],),
        tuple(reversed(receipts)),
        (receipts[0],) * 10,
    ):
        with pytest.raises((TypeError, ValueError), match="authority|receipt|order|valid"):
            module._seal_laya_oci_tar_semantics_capture_authority(
                plan,
                invalid_receipts,
                **keyword_flags,
            )


def test_private_tar_stream_budget_bridge_is_adapter_only_and_bounded():
    from human_feedback import runtime_oci_tar as module

    bridge = module._verify_laya_oci_tar_semantics_chunks_with_budget
    parameters = inspect.signature(bridge).parameters
    assert tuple(parameters) == (
        "plan",
        "digest",
        "compressed_chunks",
        "max_uncompressed_bytes",
    )
    assert parameters["max_uncompressed_bytes"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["max_uncompressed_bytes"].default is inspect.Parameter.empty


def test_tar_evidence_sealer_rejects_raw_receipts_proxy_and_foreign_authority(
    synthetic_pr22,
):
    from human_feedback import runtime_oci_tar as module

    layer_evidence, _ = synthetic_pr22
    plan = module.prepare_laya_oci_tar_semantics_plan(layer_evidence)
    receipts = _empty_tar_receipts(module, plan, layer_evidence)
    for invalid in (
        receipts,
        SimpleNamespace(plan=plan, receipts=receipts),
        object.__new__(module._LayaOciTarSemanticsCaptureAuthority),
        None,
    ):
        with pytest.raises((TypeError, ValueError), match="authority|evidence|seal|valid"):
            module._seal_laya_runtime_oci_tar_semantics_evidence(invalid)


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
