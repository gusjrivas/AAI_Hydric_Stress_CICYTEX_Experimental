"""RED39-C: real issued supply graph through disposable rootfs publication."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from tests.laya_runtime_supply_convergence_fixtures import issue_laya_supply_chain
from tests.test_laya_runtime_oci_tar import _archive, _tar_entry

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="secure rootfs materialization requires non-root Linux",
)


def _layers() -> tuple[bytes, ...]:
    base = _archive(
        _tar_entry("./", typeflag=b"5", mode=0o755),
        _tar_entry("app", typeflag=b"5", mode=0o755),
        _tar_entry("app/old.txt", b"removed\n", mode=0o640),
        _tar_entry("app/target.txt", b"version-one\n", mode=0o640),
        _tar_entry(
            "app/hard.txt",
            typeflag=b"1",
            linkname="app/target.txt",
            mode=0o640,
        ),
        _tar_entry(
            "app/link.txt",
            typeflag=b"2",
            linkname="target.txt",
            mode=0o777,
        ),
    )
    replacement = _archive(
        _tar_entry("app/.wh.old.txt"),
        _tar_entry("app/target.txt", b"version-two\n", mode=0o640),
        _tar_entry("empty.txt", b"", mode=0o600),
    )
    distinct_tail = tuple(
        _archive(_tar_entry(f"layer-{position:02d}", typeflag=b"5", mode=0o755))
        for position in range(2, 10)
    )
    return (base, replacement, *distinct_tail)


def _write_layout(source: Path, chain) -> None:
    digest_root = source / "blobs" / "sha256"
    digest_root.mkdir(parents=True)
    (source / "oci-layout").write_bytes(chain.control_payloads[0])
    (source / "index.json").write_bytes(chain.control_payloads[1])
    for blob, payload in zip(
        chain.layer_evidence.layout_plan.blobs,
        chain.blob_payloads,
        strict=True,
    ):
        (digest_root / blob.digest.removeprefix("sha256:")).write_bytes(payload)


def _fingerprint(root: Path) -> tuple[tuple[object, ...], ...]:
    captured = []
    for path in sorted((root, *root.rglob("*")), key=lambda item: item.as_posix()):
        relative = "." if path == root else path.relative_to(root).as_posix()
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            captured.append((relative, "directory"))
        elif stat.S_ISREG(metadata.st_mode):
            captured.append(
                (
                    relative,
                    "regular",
                    metadata.st_size,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
        elif stat.S_ISLNK(metadata.st_mode):
            captured.append((relative, "symlink", os.readlink(path)))
        else:
            captured.append((relative, "special", stat.S_IFMT(metadata.st_mode)))
    return tuple(captured)


def _issued_materialization_plan(monkeypatch, tmp_path: Path):
    from human_feedback import (
        runtime_oci_rootfs,
        runtime_rootfs_materialization,
        runtime_supply_convergence,
    )
    from human_feedback.adapters.filesystem_oci_layout import (
        capture_and_verify_laya_oci_tar_semantics,
    )

    chain = issue_laya_supply_chain(monkeypatch, raw_layer_payloads=_layers())
    source = tmp_path / "source"
    _write_layout(source, chain)
    tar_evidence = capture_and_verify_laya_oci_tar_semantics(chain.layer_evidence, str(source))
    assert tuple(receipt.entries for receipt in tar_evidence.receipts) != ((),) * 10
    rootfs = runtime_oci_rootfs.compose_laya_oci_rootfs(
        runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)
    )
    supply = runtime_supply_convergence.verify_laya_runtime_supply_convergence(
        chain.layer_evidence,
        chain.provenance_evidence,
        chain.base_ancestry_evidence,
    )
    plan = runtime_rootfs_materialization.prepare_laya_runtime_rootfs_materialization_plan(
        rootfs,
        supply,
    )
    assert plan._rootfs_evidence.tar_evidence.plan is tar_evidence.plan
    return chain, source, plan


def test_materializes_exact_final_bytes_topology_and_only_rootfs_claim(monkeypatch, tmp_path):
    from human_feedback import runtime_rootfs_materialization
    from human_feedback.adapters import filesystem_rootfs_materialization as filesystem

    _chain, source, plan = _issued_materialization_plan(monkeypatch, tmp_path)
    source_before = _fingerprint(source)
    parent = tmp_path / "private-output"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)

    evidence = filesystem.materialize_laya_runtime_rootfs(
        plan,
        str(source),
        str(parent),
        "rootfs",
    )

    destination = parent / "rootfs"
    assert (destination / "app" / "target.txt").read_bytes() == b"version-two\n"
    assert not (destination / "app" / "old.txt").exists()
    assert (destination / "empty.txt").read_bytes() == b""
    assert os.readlink(destination / "app" / "link.txt") == "target.txt"
    target_stat = (destination / "app" / "target.txt").stat()
    hardlink_stat = (destination / "app" / "hard.txt").stat()
    assert (hardlink_stat.st_dev, hardlink_stat.st_ino) == (
        target_stat.st_dev,
        target_stat.st_ino,
    )
    assert target_stat.st_nlink == 2
    summary = json.loads(
        runtime_rootfs_materialization.canonical_laya_runtime_rootfs_materialization_summary_bytes(
            evidence
        )
    )
    assert summary["rootfs_materialized"] is True
    assert summary["runtime_materialized"] is False
    assert summary["executor_available"] is False
    assert summary["inference_executed"] is False
    assert _fingerprint(source) == source_before

    destination_before = _fingerprint(destination)
    with pytest.raises(filesystem.RootfsMaterializationError):
        filesystem.materialize_laya_runtime_rootfs(
            plan,
            str(source),
            str(parent),
            "rootfs",
        )
    assert _fingerprint(destination) == destination_before
    assert _fingerprint(source) == source_before


def test_source_destination_overlap_fails_without_mutation(monkeypatch, tmp_path):
    from human_feedback.adapters import filesystem_rootfs_materialization as filesystem

    _chain, source, plan = _issued_materialization_plan(monkeypatch, tmp_path)
    source.chmod(0o700)
    before = _fingerprint(source)

    with pytest.raises(filesystem.RootfsMaterializationError):
        filesystem.materialize_laya_runtime_rootfs(
            plan,
            str(source),
            str(source),
            "rootfs",
        )

    assert _fingerprint(source) == before
    assert not (source / "rootfs").exists()


def test_changed_source_layer_fails_without_destination_or_staging(monkeypatch, tmp_path):
    from human_feedback.adapters import filesystem_rootfs_materialization as filesystem

    chain, source, plan = _issued_materialization_plan(monkeypatch, tmp_path)
    layer = chain.layer_evidence.plan.layer_blobs[0]
    layer_path = source / "blobs" / "sha256" / layer.digest.removeprefix("sha256:")
    layer_path.write_bytes(layer_path.read_bytes() + b"changed-after-authority")
    changed_source = _fingerprint(source)
    parent = tmp_path / "private-output"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)

    with pytest.raises(filesystem.RootfsMaterializationError):
        filesystem.materialize_laya_runtime_rootfs(
            plan,
            str(source),
            str(parent),
            "rootfs",
        )

    assert tuple(parent.iterdir()) == ()
    assert _fingerprint(source) == changed_source


def _open_descriptor_count() -> int:
    return len(os.listdir("/proc/self/fd"))


@pytest.mark.parametrize(
    "fault",
    ("writer-chunk", "create-links", "verify-tree", "publish", "seal"),
)
def test_fault_injection_never_leaks_staging_destination_source_or_descriptors(
    monkeypatch,
    tmp_path,
    fault,
):
    from human_feedback import runtime_rootfs_materialization
    from human_feedback.adapters import filesystem_rootfs_materialization as filesystem

    _chain, source, plan = _issued_materialization_plan(monkeypatch, tmp_path)
    source_before = _fingerprint(source)
    parent = tmp_path / "private-output"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)

    def fail(*_args, **_kwargs):
        raise filesystem.RootfsMaterializationError("injected rootfs failure")

    if fault == "writer-chunk":
        monkeypatch.setattr(filesystem._RegularPayloadSink, "chunk", fail)
    elif fault == "create-links":
        monkeypatch.setattr(filesystem, "_create_final_links", fail)
    elif fault == "verify-tree":
        monkeypatch.setattr(filesystem, "_verify_staged_tree", fail)
    elif fault == "publish":
        monkeypatch.setattr(filesystem, "_publish_noreplace", fail)
    else:
        monkeypatch.setattr(
            runtime_rootfs_materialization,
            "_seal_laya_runtime_rootfs_materialization_evidence",
            fail,
        )

    descriptors_before = _open_descriptor_count()
    with pytest.raises(filesystem.RootfsMaterializationError) as captured:
        filesystem.materialize_laya_runtime_rootfs(
            plan,
            str(source),
            str(parent),
            "rootfs",
        )

    assert str(source) not in str(captured.value)
    assert str(parent) not in str(captured.value)
    assert tuple(parent.iterdir()) == ()
    assert _fingerprint(source) == source_before
    assert _open_descriptor_count() == descriptors_before


def test_dispose_is_idempotent_removes_exact_tree_and_revokes_summary(monkeypatch, tmp_path):
    from human_feedback import runtime_rootfs_materialization
    from human_feedback.adapters import filesystem_rootfs_materialization as filesystem

    _chain, source, plan = _issued_materialization_plan(monkeypatch, tmp_path)
    source_before = _fingerprint(source)
    parent = tmp_path / "private-output"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    evidence = filesystem.materialize_laya_runtime_rootfs(
        plan,
        str(source),
        str(parent),
        "rootfs",
    )
    runtime_rootfs_materialization.canonical_laya_runtime_rootfs_materialization_summary_bytes(
        evidence
    )

    assert filesystem.dispose_laya_runtime_rootfs(evidence) is None
    assert filesystem.dispose_laya_runtime_rootfs(evidence) is None

    assert tuple(parent.iterdir()) == ()
    assert _fingerprint(source) == source_before
    with pytest.raises((TypeError, ValueError)):
        runtime_rootfs_materialization.canonical_laya_runtime_rootfs_materialization_summary_bytes(
            evidence
        )


def test_dispose_refuses_rebound_destination_inode_without_deleting_either_tree(
    monkeypatch,
    tmp_path,
):
    from human_feedback.adapters import filesystem_rootfs_materialization as filesystem

    _chain, source, plan = _issued_materialization_plan(monkeypatch, tmp_path)
    parent = tmp_path / "private-output"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    evidence = filesystem.materialize_laya_runtime_rootfs(
        plan,
        str(source),
        str(parent),
        "rootfs",
    )
    original = parent / "original-rootfs"
    (parent / "rootfs").rename(original)
    replacement = parent / "rootfs"
    replacement.mkdir(mode=0o700)
    marker = replacement / "must-survive.txt"
    marker.write_bytes(b"replacement sentinel")
    original_before = _fingerprint(original)

    with pytest.raises(filesystem.RootfsMaterializationError):
        filesystem.dispose_laya_runtime_rootfs(evidence)

    assert marker.read_bytes() == b"replacement sentinel"
    assert _fingerprint(original) == original_before


def test_dispose_retries_cleanup_after_transient_failure_even_when_authority_is_revoked(
    monkeypatch,
    tmp_path,
):
    from human_feedback import runtime_rootfs_materialization
    from human_feedback.adapters import filesystem_rootfs_materialization as filesystem

    _chain, source, plan = _issued_materialization_plan(monkeypatch, tmp_path)
    parent = tmp_path / "private-output"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    descriptors_before = _open_descriptor_count()
    evidence = filesystem.materialize_laya_runtime_rootfs(
        plan,
        str(source),
        str(parent),
        "rootfs",
    )
    native_remove = filesystem._remove_owned_tree
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("private-transient-cleanup-failure")
        return native_remove(*args, **kwargs)

    monkeypatch.setattr(filesystem, "_remove_owned_tree", fail_once)

    with pytest.raises(filesystem.RootfsMaterializationError) as captured:
        filesystem.dispose_laya_runtime_rootfs(evidence)
    assert "private-transient-cleanup-failure" not in str(captured.value)
    assert (parent / "rootfs").is_dir()
    with pytest.raises((TypeError, ValueError)):
        runtime_rootfs_materialization.canonical_laya_runtime_rootfs_materialization_summary_bytes(
            evidence
        )

    assert filesystem.dispose_laya_runtime_rootfs(evidence) is None
    assert filesystem.dispose_laya_runtime_rootfs(evidence) is None
    assert tuple(parent.iterdir()) == ()
    assert calls == 2
    assert _open_descriptor_count() == descriptors_before
