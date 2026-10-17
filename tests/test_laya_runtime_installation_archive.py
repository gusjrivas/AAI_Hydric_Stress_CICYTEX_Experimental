"""A bounded archive combines one issued rootfs with five exact checkpoint files."""

from __future__ import annotations

import io
import os
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_laya_runtime_rootfs_materialization_integration import (
    _issued_materialization_plan,
)

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="requires non-root Linux descriptor-relative filesystem access",
)


def _write_checkpoint(root: Path, evidence, payloads: tuple[bytes, ...]) -> None:
    for descriptor, payload in zip(evidence.plan.files, payloads, strict=True):
        target = root / descriptor.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def _issued_sources(monkeypatch, tmp_path):
    from human_feedback.adapters import filesystem_rootfs_materialization as filesystem

    chain, oci_source, rootfs_plan = _issued_materialization_plan(monkeypatch, tmp_path)
    parent = tmp_path / "private-output"
    parent.mkdir(mode=0o700)
    rootfs_evidence = filesystem.materialize_laya_runtime_rootfs(
        rootfs_plan, str(oci_source), str(parent), "rootfs"
    )
    checkpoint_evidence = chain.provenance_evidence.checkpoint_evidence
    checkpoint_root = tmp_path / "checkpoint"
    checkpoint_root.mkdir(mode=0o700)
    _write_checkpoint(checkpoint_root, checkpoint_evidence, chain.checkpoint_payloads)
    root_fd = os.open(
        parent / "rootfs", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    return filesystem, rootfs_evidence, checkpoint_evidence, checkpoint_root, root_fd


def _emit(module, rootfs_evidence, checkpoint_evidence, checkpoint_root, root_fd):
    output = io.BytesIO()
    written = module._write_laya_runtime_installation_archive(
        output,
        lease_root_fd=root_fd,
        rootfs_evidence=rootfs_evidence,
        checkpoint_evidence=checkpoint_evidence,
        checkpoint_source_root=str(checkpoint_root),
    )
    return output, written


def test_archive_is_reproducible_bounded_and_has_exact_normalized_topology(monkeypatch, tmp_path):
    from human_feedback.adapters import runtime_installation_archive as module

    filesystem, rootfs, checkpoint, checkpoint_root, root_fd = _issued_sources(
        monkeypatch, tmp_path
    )
    try:
        first, first_size = _emit(module, rootfs, checkpoint, checkpoint_root, root_fd)
        second, second_size = _emit(module, rootfs, checkpoint, checkpoint_root, root_fd)
        assert first.getvalue() == second.getvalue()
        assert first_size == second_size == len(first.getvalue())
        assert first_size <= module.MAX_INSTALLATION_ARCHIVE_BYTES

        with tarfile.open(fileobj=io.BytesIO(first.getvalue()), mode="r:") as archive:
            members = archive.getmembers()
            by_name = {item.name: item for item in members}
            assert len(by_name) == len(members)
            assert "app/old.txt" not in by_name
            assert archive.extractfile("app/target.txt").read() == b"version-two\n"
            assert by_name["app/hard.txt"].islnk()
            assert by_name["app/hard.txt"].linkname == "app/target.txt"
            assert by_name["app/link.txt"].issym()
            assert by_name["app/link.txt"].linkname == "target.txt"
            for item in members:
                assert (item.uid, item.gid, item.mtime) == (65532, 65532, 0)
            for node in rootfs._plan._rootfs_evidence.nodes:
                item = by_name[node.path]
                if node.typeflag == "5":
                    assert item.mode == 0o700
                elif node.typeflag == "0":
                    assert item.mode == 0o600 | (node.mode & 0o100)
            prefix = "opt/laya-runtime/checkpoints/multilingual"
            expected_paths = {
                f"{prefix}/{item.path}": payload
                for item, payload in zip(checkpoint.plan.files, checkpoint.receipts, strict=True)
            }
            assert set(expected_paths) <= set(by_name)
            for path, receipt in expected_paths.items():
                assert by_name[path].mode == 0o444
                assert by_name[path].size == receipt.file.size_bytes
                assert (
                    archive.extractfile(path).read()
                    == (checkpoint_root / receipt.file.path).read_bytes()
                )
            for path in (
                "opt/laya-runtime/checkpoints",
                prefix,
                f"{prefix}/encoder",
                f"{prefix}/tokenizer",
            ):
                assert by_name[path].isdir()
                assert by_name[path].mode == 0o555
    finally:
        os.close(root_fd)
        filesystem.dispose_laya_runtime_rootfs(rootfs)


@pytest.mark.parametrize("fault", ["missing", "extra", "symlink-parent"])
def test_checkpoint_namespace_faults_fail_before_first_archive_byte(monkeypatch, tmp_path, fault):
    from human_feedback.adapters import runtime_installation_archive as module

    filesystem, rootfs, checkpoint, checkpoint_root, root_fd = _issued_sources(
        monkeypatch, tmp_path
    )
    try:
        if fault == "missing":
            (checkpoint_root / checkpoint.plan.files[-1].path).unlink()
        elif fault == "extra":
            (checkpoint_root / "extra.txt").write_bytes(b"not authorized")
        else:
            tokenizer = checkpoint_root / "tokenizer"
            for child in tokenizer.iterdir():
                child.unlink()
            tokenizer.rmdir()
            tokenizer.symlink_to(tmp_path, target_is_directory=True)
        output = io.BytesIO()
        with pytest.raises(module.RuntimeInstallationArchiveError):
            module._write_laya_runtime_installation_archive(
                output,
                lease_root_fd=root_fd,
                rootfs_evidence=rootfs,
                checkpoint_evidence=checkpoint,
                checkpoint_source_root=str(checkpoint_root),
            )
        assert output.getvalue() == b""
    finally:
        os.close(root_fd)
        filesystem.dispose_laya_runtime_rootfs(rootfs)


def test_checkpoint_mapping_rejects_collision_and_symlink_parent_without_io():
    from human_feedback.adapters import runtime_installation_archive as module

    plan = SimpleNamespace(
        files=(SimpleNamespace(role="weights", path="model.safetensors", size_bytes=1),)
    )
    collision = (SimpleNamespace(path="opt/laya-runtime/checkpoints", typeflag="0"),)
    symlink_parent = (SimpleNamespace(path="opt/laya-runtime", typeflag="2"),)
    with pytest.raises(module.RuntimeInstallationArchiveError):
        module._checkpoint_installation_entries(collision, plan)
    with pytest.raises(module.RuntimeInstallationArchiveError):
        module._checkpoint_installation_entries(symlink_parent, plan)


def test_hardlink_archive_mode_preserves_terminal_owner_execute_bit():
    from human_feedback.adapters import runtime_installation_archive as module

    regular = SimpleNamespace(
        path="bin/tool",
        typeflag="0",
        mode=0o755,
        size_bytes=1,
        link_target=None,
    )
    hardlink = SimpleNamespace(
        path="bin/tool-alias",
        typeflag="1",
        mode=0o600,
        size_bytes=0,
        link_target="bin/tool",
    )
    entries = {entry.path: entry for entry in module._rootfs_entries((regular, hardlink))}
    assert entries["bin/tool"].mode == 0o700
    assert entries["bin/tool-alias"].mode == 0o700


def test_payload_bound_fails_before_first_archive_byte(monkeypatch, tmp_path):
    from human_feedback.adapters import runtime_installation_archive as module

    filesystem, rootfs, checkpoint, checkpoint_root, root_fd = _issued_sources(
        monkeypatch, tmp_path
    )
    try:
        monkeypatch.setattr(module, "MAX_INSTALLATION_PAYLOAD_BYTES", 1)
        output = io.BytesIO()
        with pytest.raises(module.RuntimeInstallationArchiveError):
            module._write_laya_runtime_installation_archive(
                output,
                lease_root_fd=root_fd,
                rootfs_evidence=rootfs,
                checkpoint_evidence=checkpoint,
                checkpoint_source_root=str(checkpoint_root),
            )
        assert output.getvalue() == b""
    finally:
        os.close(root_fd)
        filesystem.dispose_laya_runtime_rootfs(rootfs)


def test_checkpoint_mutation_during_stream_fails_without_closing_writer(monkeypatch, tmp_path):
    from human_feedback.adapters import runtime_installation_archive as module

    filesystem, rootfs, checkpoint, checkpoint_root, root_fd = _issued_sources(
        monkeypatch, tmp_path
    )
    original = module._stream_file_payload
    mutated = False

    def mutate_after_stream(*args, **kwargs):
        nonlocal mutated
        result = original(*args, **kwargs)
        if not mutated and kwargs.get("checkpoint_path") is not None:
            target = checkpoint_root / checkpoint.plan.files[0].path
            target.write_bytes(target.read_bytes())
            mutated = True
        return result

    monkeypatch.setattr(module, "_stream_file_payload", mutate_after_stream)
    output = io.BytesIO()
    try:
        with pytest.raises(module.RuntimeInstallationArchiveError):
            module._write_laya_runtime_installation_archive(
                output,
                lease_root_fd=root_fd,
                rootfs_evidence=rootfs,
                checkpoint_evidence=checkpoint,
                checkpoint_source_root=str(checkpoint_root),
            )
        assert not output.closed
    finally:
        os.close(root_fd)
        filesystem.dispose_laya_runtime_rootfs(rootfs)
