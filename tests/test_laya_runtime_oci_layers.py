import ast
import gzip
import os
import traceback
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

PLAN_SCHEMA = "laya-oci-layer-diff-id-plan-v1"
REAL_LAYOUT_GATE_ENV = "LAYA_RUNTIME_OCI_LAYOUT_ROOT"
EXPECTED_LAYER_ROLES = tuple(f"layer-{index:02d}" for index in range(10))
FALSE_CLAIMS = (
    "oci_layer_diff_ids_verified",
    "oci_rootfs_verified",
    "origin_verified",
)
MAX_LAYER_CHUNK_BYTES = 1024 * 1024
MAX_LAYER_CHUNKS = 1024
MAX_LAYER_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_ROOTFS_UNCOMPRESSED_BYTES = 3 * 1024 * 1024 * 1024


def _private_error(error: BaseException, *markers: str) -> None:
    rendered = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    for marker in markers:
        assert marker not in str(error)
        assert marker not in rendered
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True


def _forged_dataclass(value, **changes):
    forged = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            forged,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return forged


def test_layer_diff_id_plan_module_has_a_pure_minimal_public_surface():
    from human_feedback import runtime_oci_layers as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imports & {
        "gzip",
        "io",
        "os",
        "pathlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    forbidden_calls = {
        "open",
        "read_bytes",
        "read_text",
        "write_bytes",
        "write_text",
        "system",
        "popen",
        "run",
        "__import__",
        "eval",
        "exec",
        "BytesIO",
        "seek",
        "join",
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
    assert calls.isdisjoint(forbidden_calls)
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
        "prepare_laya_oci_layer_diff_id_plan",
        "verify_laya_oci_layer_diff_id_chunks",
    }
    assert public_classes == {
        "LayaOciLayerDiffIdPlan",
        "VerifiedLayaOciLayerDiffId",
    }
    assert public_constants == {
        "OCI_LAYER_DIFF_ID_PLAN_SCHEMA",
        "MAX_OCI_LAYER_CHUNK_BYTES",
        "MAX_OCI_LAYER_CHUNKS",
        "MAX_OCI_LAYER_UNCOMPRESSED_BYTES",
        "MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES",
    }


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        SimpleNamespace(oci_config_semantics_verified=True),
        "private-config-evidence-proxy",
    ],
)
def test_layer_diff_id_plan_rejects_non_exact_config_evidence_privately(invalid):
    from human_feedback.runtime_oci_layers import prepare_laya_oci_layer_diff_id_plan

    with pytest.raises((TypeError, ValueError), match="config|evidence|exact|valid") as captured:
        prepare_laya_oci_layer_diff_id_plan(invalid)
    _private_error(captured.value, "private-config-evidence-proxy")


def test_no_product_module_imports_or_calls_layer_diff_id_plan():
    repository = Path(__file__).parents[1]
    owner = repository / "src" / "human_feedback" / "runtime_oci_layers.py"
    symbols = {
        "LayaOciLayerDiffIdPlan",
        "prepare_laya_oci_layer_diff_id_plan",
        "VerifiedLayaOciLayerDiffId",
        "verify_laya_oci_layer_diff_id_chunks",
        "human_feedback.runtime_oci_layers",
    }
    offenders = []
    for relative_root in ("backend", "src", "scripts"):
        root = repository / relative_root
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if path == owner:
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            if any(
                (
                    isinstance(node, ast.Import)
                    and any(
                        alias.name == "human_feedback.runtime_oci_layers" for alias in node.names
                    )
                )
                or (
                    isinstance(node, ast.ImportFrom)
                    and (
                        node.module == "human_feedback.runtime_oci_layers"
                        or (
                            node.level > 0
                            and node.module in {None, "", "runtime_oci_layers"}
                            and any(
                                alias.name == "runtime_oci_layers" or alias.name in symbols
                                for alias in node.names
                            )
                        )
                    )
                )
                or (isinstance(node, ast.Name) and node.id in symbols)
                or (isinstance(node, ast.Attribute) and node.attr in symbols)
                or (isinstance(node, ast.Constant) and node.value in symbols)
                for node in ast.walk(tree)
            ):
                offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []


def test_layer_streaming_caps_are_public_positive_plain_integers():
    from human_feedback import runtime_oci_layers as module

    assert module.MAX_OCI_LAYER_CHUNK_BYTES == MAX_LAYER_CHUNK_BYTES
    assert module.MAX_OCI_LAYER_CHUNKS == MAX_LAYER_CHUNKS
    assert module.MAX_OCI_LAYER_UNCOMPRESSED_BYTES == MAX_LAYER_UNCOMPRESSED_BYTES
    assert module.MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES == MAX_ROOTFS_UNCOMPRESSED_BYTES


def test_incremental_decompression_bounds_each_output_call():
    from human_feedback import runtime_oci_layers as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    decompress_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "decompress"
    ]
    assert decompress_calls
    assert all(
        len(call.args) >= 2 or any(keyword.arg == "max_length" for keyword in call.keywords)
        for call in decompress_calls
    )
    assert "unconsumed_tail" in Path(module.__file__).read_text(encoding="utf-8")


@pytest.mark.skipif(
    not os.environ.get(REAL_LAYOUT_GATE_ENV),
    reason="requires opt-in exact external OCI layout",
)
def test_exact_config_evidence_prepares_identity_bound_private_layer_plan():
    from human_feedback.adapters.filesystem_oci_layout import (
        capture_and_verify_laya_oci_layout,
    )
    from human_feedback.runtime_oci_config import (
        validate_laya_runtime_oci_config_semantics,
    )
    from human_feedback.runtime_oci_layers import (
        LayaOciLayerDiffIdPlan,
        prepare_laya_oci_layer_diff_id_plan,
    )
    from tests.test_laya_runtime_oci_layout import _oci_evidence

    root = Path(os.environ[REAL_LAYOUT_GATE_ENV])
    layout_evidence = capture_and_verify_laya_oci_layout(_oci_evidence(), root)
    config_blob = layout_evidence.plan.blobs[1]
    config_bytes = (root / config_blob.path).read_bytes()
    config_evidence = validate_laya_runtime_oci_config_semantics(
        layout_evidence,
        config_bytes,
    )

    plan = prepare_laya_oci_layer_diff_id_plan(config_evidence)

    assert type(plan) is LayaOciLayerDiffIdPlan
    assert plan.schema_version == PLAN_SCHEMA
    assert plan.config_evidence is config_evidence
    assert plan.layout_evidence is layout_evidence
    assert plan.layout_plan is layout_evidence.plan
    assert plan.runtime_identity is config_evidence.runtime_identity
    assert type(plan.layer_blobs) is tuple
    assert type(plan.layer_receipts) is tuple
    assert len(plan.layer_blobs) == len(plan.layer_receipts) == 10
    assert tuple(blob.role for blob in plan.layer_blobs) == EXPECTED_LAYER_ROLES
    assert all(
        blob is layout_evidence.plan.blobs[index + 2] for index, blob in enumerate(plan.layer_blobs)
    )
    assert all(
        receipt is layout_evidence.receipts[index + 2]
        and receipt.plan is layout_evidence.plan
        and receipt.blob is plan.layer_blobs[index]
        for index, receipt in enumerate(plan.layer_receipts)
    )
    assert plan.declared_diff_ids is config_evidence.config.declared_diff_ids
    assert len(plan.declared_diff_ids) == 10
    for claim in FALSE_CLAIMS:
        assert getattr(plan, claim) is False
    rendered = repr(plan)
    private_values = (
        *(blob.path for blob in plan.layer_blobs),
        *(blob.digest for blob in plan.layer_blobs),
        *plan.declared_diff_ids,
    )
    assert all(value not in rendered for value in private_values)

    for field in fields(plan):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(plan, field.name, getattr(plan, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
            replace(plan, **{field.name: getattr(plan, field.name)})
    with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
        LayaOciLayerDiffIdPlan(
            schema_version=PLAN_SCHEMA,
            config_evidence=config_evidence,
            layout_evidence=layout_evidence,
            layout_plan=layout_evidence.plan,
            runtime_identity=config_evidence.runtime_identity,
            layer_blobs=layout_evidence.plan.blobs[2:],
            layer_receipts=layout_evidence.receipts[2:],
            declared_diff_ids=config_evidence.config.declared_diff_ids,
        )


@pytest.mark.skipif(
    not os.environ.get(REAL_LAYOUT_GATE_ENV),
    reason="requires opt-in exact external OCI layout",
)
def test_layer_plan_rejects_foreign_and_deeply_mutated_config_graph():
    from human_feedback.adapters.filesystem_oci_layout import (
        capture_and_verify_laya_oci_layout,
    )
    from human_feedback.runtime_oci_config import (
        LayaRuntimeOciConfigEvidence,
        validate_laya_runtime_oci_config_semantics,
    )
    from human_feedback.runtime_oci_layers import prepare_laya_oci_layer_diff_id_plan
    from tests.test_laya_runtime_oci_layout import _oci_evidence

    root = Path(os.environ[REAL_LAYOUT_GATE_ENV])
    layout = capture_and_verify_laya_oci_layout(_oci_evidence(), root)
    config_bytes = (root / layout.plan.blobs[1].path).read_bytes()
    evidence = validate_laya_runtime_oci_config_semantics(layout, config_bytes)

    class ConfigEvidenceSubclass(LayaRuntimeOciConfigEvidence):
        pass

    invalid_values = [
        SimpleNamespace(config=evidence.config),
        object.__new__(ConfigEvidenceSubclass),
    ]
    mutated_projection = _forged_dataclass(
        evidence.config,
        declared_diff_ids=tuple(reversed(evidence.config.declared_diff_ids)),
    )
    invalid_values.append(_forged_dataclass(evidence, config=mutated_projection))
    foreign_layout = _forged_dataclass(
        evidence.layout_evidence,
        receipts=tuple(reversed(evidence.layout_evidence.receipts)),
    )
    invalid_values.append(_forged_dataclass(evidence, layout_evidence=foreign_layout))

    for invalid in invalid_values:
        with pytest.raises(
            (TypeError, ValueError), match="config|evidence|layout|diff|valid"
        ) as captured:
            prepare_laya_oci_layer_diff_id_plan(invalid)
        _private_error(captured.value, *evidence.config.declared_diff_ids)


@pytest.mark.skipif(
    not os.environ.get(REAL_LAYOUT_GATE_ENV),
    reason="requires opt-in exact external OCI layout",
)
def test_real_single_member_layer_streams_to_an_identity_bound_diff_id_receipt(monkeypatch):
    from human_feedback import runtime_oci_layers as module
    from human_feedback.adapters.filesystem_oci_layout import (
        capture_and_verify_laya_oci_layout,
    )
    from human_feedback.runtime_oci_config import validate_laya_runtime_oci_config_semantics
    from human_feedback.runtime_oci_layers import (
        VerifiedLayaOciLayerDiffId,
        prepare_laya_oci_layer_diff_id_plan,
        verify_laya_oci_layer_diff_id_chunks,
    )
    from tests.test_laya_runtime_oci_layout import _oci_evidence

    root = Path(os.environ[REAL_LAYOUT_GATE_ENV])
    layout = capture_and_verify_laya_oci_layout(_oci_evidence(), root)
    config_bytes = (root / layout.plan.blobs[1].path).read_bytes()
    config_evidence = validate_laya_runtime_oci_config_semantics(layout, config_bytes)
    plan = prepare_laya_oci_layer_diff_id_plan(config_evidence)
    position = min(range(10), key=lambda index: plan.layer_blobs[index].size_bytes)
    blob = plan.layer_blobs[position]
    compressed = (root / blob.path).read_bytes()

    chunkings = (
        (compressed,),
        tuple(compressed[index : index + 1] for index in range(len(compressed))),
        tuple(compressed[index : index + 17] for index in range(0, len(compressed), 17)),
    )
    receipts = []
    for chunks in chunkings:
        receipt = verify_laya_oci_layer_diff_id_chunks(plan, blob.digest, iter(chunks))
        receipts.append(receipt)
        assert type(receipt) is VerifiedLayaOciLayerDiffId
        assert receipt.plan is plan
        assert receipt.layer_blob is blob
        # The PR20 receipt remains the same-root authority. The verifier's fresh
        # compressed-byte rehash is deliberately transient and cannot mint authority.
        assert receipt.compressed_receipt is plan.layer_receipts[position]
        assert receipt.layer_position == position
        assert receipt.declared_diff_id == plan.declared_diff_ids[position]
        assert receipt.computed_diff_id == receipt.declared_diff_id
        assert receipt.compressed_blob_bytes_verified is True
        assert receipt.layer_diff_id_verified is True
        assert receipt.tar_semantics_verified is False
        assert receipt.rootfs_verified is False
        assert receipt.origin_verified is False
        rendered = repr(receipt)
        assert blob.path not in rendered
        assert blob.digest not in rendered
        assert receipt.declared_diff_id not in rendered
        for field in fields(receipt):
            if field.name.startswith("_"):
                continue
            with pytest.raises(FrozenInstanceError):
                setattr(receipt, field.name, getattr(receipt, field.name))
            with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
                replace(receipt, **{field.name: getattr(receipt, field.name)})
    assert all(receipt is not receipts[0] for receipt in receipts[1:])

    consumed = 0

    def hostile_unknown():
        nonlocal consumed
        consumed += 1
        raise AssertionError("private-unknown-layer-consumed")
        yield b"unreachable"

    for invalid_digest in ("sha512:" + "a" * 64, "sha256:" + "a" * 64, blob.digest.upper()):
        with pytest.raises(
            (TypeError, ValueError), match="digest|layer|authorized|plan"
        ) as captured:
            verify_laya_oci_layer_diff_id_chunks(plan, invalid_digest, hostile_unknown())
        _private_error(captured.value, "private-unknown-layer-consumed")
    assert consumed == 0

    for invalid_chunks in (compressed, "not-chunks", [compressed, b""], [compressed, "x"]):
        with pytest.raises((TypeError, ValueError), match="chunk|bytes|stream|layer"):
            verify_laya_oci_layer_diff_id_chunks(plan, blob.digest, invalid_chunks)

    class HostileChunks:
        def __iter__(self):
            yield compressed[:1]
            raise RuntimeError("private-layer-iterator-marker")

    with pytest.raises((TypeError, ValueError), match="chunk|stream|layer") as captured:
        verify_laya_oci_layer_diff_id_chunks(plan, blob.digest, HostileChunks())
    _private_error(captured.value, "private-layer-iterator-marker")

    too_many_consumed = 0

    original_compressed_verifier = module.runtime_oci_layout.verify_laya_oci_blob_chunks

    def consume_delegated_chunks(_layout_plan, _digest, delegated_chunks):
        for _chunk in delegated_chunks:
            pass
        return plan.layer_receipts[position]

    monkeypatch.setattr(
        module.runtime_oci_layout,
        "verify_laya_oci_blob_chunks",
        consume_delegated_chunks,
    )

    def too_many_chunks():
        nonlocal too_many_consumed
        for _ in range(module.MAX_OCI_LAYER_CHUNKS + 1):
            too_many_consumed += 1
            yield b"x"
        raise AssertionError("private-layer-count-sentinel")

    with pytest.raises((TypeError, ValueError), match="chunk|count|limit|layer") as captured:
        verify_laya_oci_layer_diff_id_chunks(plan, blob.digest, too_many_chunks())
    assert too_many_consumed == module.MAX_OCI_LAYER_CHUNKS + 1
    _private_error(captured.value, "private-layer-count-sentinel")
    monkeypatch.setattr(
        module.runtime_oci_layout,
        "verify_laya_oci_blob_chunks",
        original_compressed_verifier,
    )

    oversized = b"x" * (module.MAX_OCI_LAYER_CHUNK_BYTES + 1)
    with pytest.raises((TypeError, ValueError), match="chunk|size|limit|layer"):
        verify_laya_oci_layer_diff_id_chunks(plan, blob.digest, iter((oversized,)))

    for invalid_compressed in (
        compressed[:-1],
        compressed + b"x",
        bytes([compressed[0] ^ 1]) + compressed[1:],
    ):
        with pytest.raises((TypeError, ValueError), match="compressed|digest|size|blob|layer"):
            verify_laya_oci_layer_diff_id_chunks(
                plan,
                blob.digest,
                iter((invalid_compressed,)),
            )

    def accept_compressed(_layout_plan, _digest, _chunks):
        return plan.layer_receipts[position]

    monkeypatch.setattr(
        module.runtime_oci_layout,
        "verify_laya_oci_blob_chunks",
        accept_compressed,
    )
    payload = b"synthetic-layer-content"
    member = gzip.compress(payload, mtime=0)
    with pytest.raises((TypeError, ValueError), match="diff|digest|declared|layer"):
        verify_laya_oci_layer_diff_id_chunks(plan, blob.digest, iter((member,)))
    invalid_members = (
        member[:-1],
        member + b"private-trailing-garbage",
        member + gzip.compress(b"second-member", mtime=0),
        member[:-8] + bytes([member[-8] ^ 1]) + member[-7:],
        member[:-4] + bytes([member[-4] ^ 1]) + member[-3:],
        b"not-a-gzip-member",
    )
    for invalid_member in invalid_members:
        with pytest.raises(
            (TypeError, ValueError), match="gzip|member|CRC|size|diff|layer"
        ) as captured:
            verify_laya_oci_layer_diff_id_chunks(plan, blob.digest, iter((invalid_member,)))
        _private_error(captured.value, "private-trailing-garbage", "second-member")

    monkeypatch.setattr(module, "MAX_OCI_LAYER_UNCOMPRESSED_BYTES", 64)
    monkeypatch.setattr(module, "MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES", 64)
    expansion_bomb = gzip.compress(b"x" * 65, mtime=0)
    with pytest.raises((TypeError, ValueError), match="expand|uncompressed|size|limit|layer"):
        verify_laya_oci_layer_diff_id_chunks(plan, blob.digest, iter((expansion_bomb,)))
    monkeypatch.setattr(
        module.runtime_oci_layout,
        "verify_laya_oci_blob_chunks",
        original_compressed_verifier,
    )


def test_layer_module_exports_no_aggregate_evidence_or_finalizer():
    from human_feedback import runtime_oci_layers as module

    forbidden = {
        "LayaRuntimeOciLayerEvidence",
        "finalize_laya_oci_layer_evidence",
        "canonical_laya_runtime_oci_layer_summary_bytes",
        "capture_and_verify_laya_oci_layers",
    }
    assert all(not hasattr(module, name) for name in forbidden)
