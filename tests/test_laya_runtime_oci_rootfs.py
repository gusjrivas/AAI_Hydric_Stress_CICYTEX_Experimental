import ast
import json
import traceback
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest


def _private_error(error: BaseException, *markers: str) -> None:
    rendered = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    for marker in markers:
        assert marker not in str(error)
        assert marker not in rendered
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True


def _forge(cls, **values):
    forged = object.__new__(cls)
    for field in fields(cls):
        assert field.name in values, f"missing synthetic field: {field.name}"
        object.__setattr__(forged, field.name, values[field.name])
    return forged


def _synthetic_pr22_evidence():
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


def _entry(module, path, typeflag="0", size=0, link_target=None, *, mode=None):
    required = {"mode", "uid", "gid", "mtime"}
    assert required <= {field.name for field in fields(module.LayaOciTarEntry)}
    return module.LayaOciTarEntry(
        path=path,
        typeflag=typeflag,
        size_bytes=size,
        link_target=link_target,
        mode=(0o755 if typeflag == "5" else 0o644) if mode is None else mode,
        uid=0,
        gid=0,
        mtime=0,
        _factory_token=module._FACTORY_TOKEN,
    )


def _tar_evidence(monkeypatch, layer_entries, *, roots=None):
    from human_feedback import runtime_oci_layers, runtime_oci_tar

    layer_evidence = _synthetic_pr22_evidence()
    monkeypatch.setattr(
        runtime_oci_layers,
        "canonical_laya_runtime_oci_layer_diff_ids_summary_bytes",
        lambda candidate: (
            b"{}\n" if candidate is layer_evidence else (_ for _ in ()).throw(ValueError())
        ),
    )
    assert "root_directory" in {
        field.name for field in fields(runtime_oci_tar.VerifiedLayaOciTarLayer)
    }
    plan = runtime_oci_tar.prepare_laya_oci_tar_semantics_plan(layer_evidence)
    roots = {} if roots is None else roots
    receipts = []
    for position, historical in enumerate(layer_evidence.receipts):
        fresh = _forge(
            type(historical),
            **{field.name: getattr(historical, field.name) for field in fields(historical)},
        )
        entries = tuple(layer_entries.get(position, ()))
        receipts.append(
            runtime_oci_tar.VerifiedLayaOciTarLayer(
                plan=plan,
                layer_receipt=fresh,
                layer_position=position,
                root_directory=roots.get(position),
                entries=entries,
                payload_size_bytes=sum(entry.size_bytes for entry in entries),
                tar_size_bytes=fresh.uncompressed_size_bytes,
                _factory_token=runtime_oci_tar._FACTORY_TOKEN,
            )
        )
    return runtime_oci_tar.LayaRuntimeOciTarSemanticsEvidence(
        schema_version="laya-runtime-oci-tar-semantics-evidence-v1",
        plan=plan,
        runtime_identity=layer_evidence.runtime_identity,
        receipts=tuple(receipts),
        _factory_token=runtime_oci_tar._FACTORY_TOKEN,
    )


def _node_map(evidence):
    return {node.path: node for node in evidence.nodes}


def test_rootfs_module_is_pure_and_has_a_closed_public_surface():
    from human_feedback import runtime_oci_rootfs as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "human_feedback.runtime_oci_tar" in imports or "human_feedback" in imports
    assert not imports & {
        "gzip",
        "io",
        "os",
        "pathlib",
        "shutil",
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
        "canonical_laya_runtime_oci_rootfs_summary_bytes",
        "compose_laya_oci_rootfs",
        "prepare_laya_oci_rootfs_plan",
    }
    assert public_classes == {
        "LayaOciRootfsNode",
        "LayaOciRootfsPlan",
        "LayaRuntimeOciRootfsEvidence",
    }


def test_rootfs_plan_binds_exact_deep_validated_tar_evidence(monkeypatch):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    tar_evidence = _tar_evidence(monkeypatch, {})
    plan = runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)

    assert plan.tar_evidence is tar_evidence
    assert plan.tar_plan is tar_evidence.plan
    assert plan.layer_receipts is tar_evidence.receipts
    assert plan.runtime_identity is tar_evidence.runtime_identity
    assert plan.oci_rootfs_verified is False
    with pytest.raises(FrozenInstanceError):
        plan.tar_evidence = None
    with pytest.raises((TypeError, ValueError)):
        replace(plan, tar_evidence=SimpleNamespace())
    for invalid in (
        SimpleNamespace(),
        object.__new__(runtime_oci_tar.LayaRuntimeOciTarSemanticsEvidence),
    ):
        with pytest.raises((TypeError, ValueError), match="tar|evidence|valid"):
            runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(invalid)


def test_layers_compose_base_to_top_with_whiteouts_and_opaque_directories(monkeypatch):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    tar_evidence = _tar_evidence(
        monkeypatch,
        {
            0: (
                _entry(runtime_oci_tar, "app", "5"),
                _entry(runtime_oci_tar, "app/old", size=3),
                _entry(runtime_oci_tar, "app/keep", size=4),
                _entry(runtime_oci_tar, "app/cache", "5"),
                _entry(runtime_oci_tar, "app/cache/lower-a", size=1),
                _entry(runtime_oci_tar, "app/cache/lower-b", size=1),
                _entry(runtime_oci_tar, "opt", "5"),
                _entry(runtime_oci_tar, "opt/lower", size=2),
            ),
            1: (
                _entry(runtime_oci_tar, "opt/lower", size=7),
                _entry(runtime_oci_tar, "app/.wh.old"),
                _entry(runtime_oci_tar, "app/cache/new", size=5),
                _entry(runtime_oci_tar, "app/cache/.wh..wh..opq"),
                _entry(runtime_oci_tar, "opt/.wh.lower"),
            ),
            2: (_entry(runtime_oci_tar, "app/keep", size=9),),
        },
    )

    evidence = runtime_oci_rootfs.compose_laya_oci_rootfs(
        runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)
    )
    nodes = _node_map(evidence)

    assert tuple(nodes) == tuple(sorted(nodes))
    assert set(nodes) == {
        "app",
        "app/cache",
        "app/cache/new",
        "app/keep",
        "opt",
        "opt/lower",
    }
    assert nodes["app/keep"].size_bytes == 9
    assert nodes["opt/lower"].size_bytes == 7
    assert all("/.wh." not in path for path in nodes)


@pytest.mark.parametrize("marker", ["tree/.wh.", "tree/.wh..wh..opq"])
@pytest.mark.parametrize(
    ("typeflag", "size", "target"),
    [("0", 1, None), ("1", 0, "tree/lower"), ("2", 0, "lower"), ("5", 0, None)],
)
def test_whiteout_markers_require_empty_regular_entries(
    monkeypatch,
    marker,
    typeflag,
    size,
    target,
):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    tar_evidence = _tar_evidence(
        monkeypatch,
        {
            0: (_entry(runtime_oci_tar, "tree", "5"),),
            1: (_entry(runtime_oci_tar, marker, typeflag, size, target),),
        },
    )
    with pytest.raises(ValueError, match="whiteout|opaque|rootfs|valid") as captured:
        runtime_oci_rootfs.compose_laya_oci_rootfs(
            runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)
        )
    _private_error(captured.value, marker)


def test_whiteout_removes_only_lower_layers_and_is_independent_of_tar_order(monkeypatch):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    outcomes = []
    for entries in (
        (_entry(runtime_oci_tar, "data/.wh.value"), _entry(runtime_oci_tar, "data/value", size=8)),
        (_entry(runtime_oci_tar, "data/value", size=8), _entry(runtime_oci_tar, "data/.wh.value")),
    ):
        tar_evidence = _tar_evidence(
            monkeypatch,
            {
                0: (
                    _entry(runtime_oci_tar, "data", "5"),
                    _entry(runtime_oci_tar, "data/value", size=1),
                ),
                1: entries,
            },
        )
        evidence = runtime_oci_rootfs.compose_laya_oci_rootfs(
            runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)
        )
        outcomes.append(tuple((node.path, node.size_bytes) for node in evidence.nodes))
    assert outcomes[0] == outcomes[1]
    assert ("data/value", 8) in outcomes[0]


def test_cross_layer_file_directory_replacement_removes_incompatible_descendants(monkeypatch):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    directory_to_file = _tar_evidence(
        monkeypatch,
        {
            0: (
                _entry(runtime_oci_tar, "tree", "5"),
                _entry(runtime_oci_tar, "tree/child", size=1),
            ),
            1: (_entry(runtime_oci_tar, "tree", size=2),),
        },
    )
    result = runtime_oci_rootfs.compose_laya_oci_rootfs(
        runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(directory_to_file)
    )
    assert tuple(node.path for node in result.nodes) == ("tree",)
    assert result.nodes[0].typeflag == "0"


def test_dangling_symlink_leaf_is_preserved_but_cannot_be_traversed_outside_root(monkeypatch):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    leaf = _tar_evidence(
        monkeypatch,
        {
            0: (
                _entry(runtime_oci_tar, "safe", "5"),
                _entry(runtime_oci_tar, "safe/link", "2", 0, "../missing"),
            )
        },
    )
    accepted = runtime_oci_rootfs.compose_laya_oci_rootfs(
        runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(leaf)
    )
    assert _node_map(accepted)["safe/link"].link_target == "../missing"

    traversed = _tar_evidence(
        monkeypatch,
        {
            0: (
                _entry(runtime_oci_tar, "safe", "5"),
                _entry(runtime_oci_tar, "safe/link", "2", 0, "../../outside"),
            ),
            1: (_entry(runtime_oci_tar, "safe/link/child", size=1),),
        },
    )
    with pytest.raises(ValueError, match="link|root|path|valid") as captured:
        runtime_oci_rootfs.compose_laya_oci_rootfs(
            runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(traversed)
        )
    _private_error(captured.value, "../../outside")


@pytest.mark.parametrize("target", ["missing", "directory"])
def test_hardlinks_must_resolve_to_effective_regular_files(monkeypatch, target):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    entries = [_entry(runtime_oci_tar, "directory", "5")]
    entries.append(_entry(runtime_oci_tar, "hard", "1", 0, target))
    tar_evidence = _tar_evidence(monkeypatch, {0: tuple(entries)})
    with pytest.raises(ValueError, match="hardlink|target|rootfs|valid") as captured:
        runtime_oci_rootfs.compose_laya_oci_rootfs(
            runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)
        )
    _private_error(captured.value, target)


def test_root_directory_metadata_is_composed_by_layer_order(monkeypatch):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    first = _entry(runtime_oci_tar, ".", "5", mode=0o755)
    last = _entry(runtime_oci_tar, ".", "5", mode=0o750)
    tar_evidence = _tar_evidence(monkeypatch, {}, roots={0: first, 7: last})
    evidence = runtime_oci_rootfs.compose_laya_oci_rootfs(
        runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)
    )
    assert evidence.root_directory is not first
    assert evidence.root_directory.source_layer_position == 7
    assert evidence.root_directory.mode == 0o750


def test_rootfs_budgets_are_public_positive_and_enforced_all_or_nothing(monkeypatch):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    for name in (
        "MAX_OCI_ROOTFS_ENTRIES",
        "MAX_OCI_ROOTFS_LINK_HOPS",
        "MAX_OCI_ROOTFS_METADATA_BYTES",
        "MAX_OCI_ROOTFS_MUTATIONS",
        "MAX_OCI_ROOTFS_PATH_COMPONENTS",
        "MAX_OCI_ROOTFS_WHITEOUTS",
    ):
        value = getattr(runtime_oci_rootfs, name)
        assert type(value) is int and value > 0

    tar_evidence = _tar_evidence(
        monkeypatch,
        {
            0: (
                _entry(runtime_oci_tar, "data", "5"),
                _entry(runtime_oci_tar, "data/a", size=1),
                _entry(runtime_oci_tar, "data/b", size=1),
            )
        },
    )
    plan = runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)
    monkeypatch.setattr(runtime_oci_rootfs, "MAX_OCI_ROOTFS_ENTRIES", 2)
    sealed = []
    monkeypatch.setattr(
        runtime_oci_rootfs,
        "_seal_laya_runtime_oci_rootfs_evidence",
        lambda *args, **kwargs: sealed.append((args, kwargs)),
    )
    with pytest.raises(ValueError, match="budget|entries|rootfs|limit"):
        runtime_oci_rootfs.compose_laya_oci_rootfs(plan)
    assert sealed == []


def test_rootfs_evidence_is_sealed_private_and_only_elevates_rootfs(monkeypatch):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar

    secret_path = "private/scientific-model.bin"
    tar_evidence = _tar_evidence(
        monkeypatch,
        {
            0: (
                _entry(runtime_oci_tar, "private", "5"),
                _entry(runtime_oci_tar, secret_path, size=9),
            )
        },
    )
    plan = runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)
    evidence = runtime_oci_rootfs.compose_laya_oci_rootfs(plan)

    assert evidence.plan is plan
    assert evidence.tar_evidence is tar_evidence
    assert evidence.runtime_identity is tar_evidence.runtime_identity
    assert evidence.oci_rootfs_verified is True
    assert evidence.tar_semantics_verified is True
    assert evidence.rootfs_materialized is False
    assert evidence.origin_verified is False
    assert evidence.executor_available is False
    assert evidence.inference_executed is False
    assert len(evidence.rootfs_manifest_sha256) == 64
    assert secret_path not in repr(evidence)
    assert secret_path not in repr(evidence.nodes)
    summary_bytes = runtime_oci_rootfs.canonical_laya_runtime_oci_rootfs_summary_bytes(evidence)
    summary = json.loads(summary_bytes)
    assert summary["schema_version"] == "laya-runtime-oci-rootfs-evidence-v1"
    assert summary["oci_rootfs_verified"] is True
    assert secret_path.encode() not in summary_bytes
    assert evidence.rootfs_manifest_sha256.encode() not in summary_bytes
    with pytest.raises((TypeError, ValueError)):
        replace(evidence, rootfs_manifest_sha256="0" * 64)
    with pytest.raises(FrozenInstanceError):
        evidence.nodes = ()


def test_rootfs_module_has_no_productive_callers_or_dataset_dependencies():
    root = Path(__file__).resolve().parents[1]
    owner = root / "src" / "human_feedback" / "runtime_oci_rootfs.py"
    offenders = []
    for search_root in (root / "src", root / "backend", root / "scripts"):
        for path in search_root.rglob("*.py"):
            if path == owner:
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            if any(
                isinstance(node, ast.Import)
                and any(alias.name == "human_feedback.runtime_oci_rootfs" for alias in node.names)
                or isinstance(node, ast.ImportFrom)
                and node.module == "human_feedback.runtime_oci_rootfs"
                or isinstance(node, ast.Constant)
                and node.value == "human_feedback.runtime_oci_rootfs"
                for node in ast.walk(tree)
            ):
                offenders.append(path.relative_to(root).as_posix())
    assert offenders == []
