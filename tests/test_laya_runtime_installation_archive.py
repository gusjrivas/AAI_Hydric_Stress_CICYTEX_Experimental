"""A bounded archive combines one issued rootfs with five exact checkpoint files."""

from __future__ import annotations

import hashlib
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
            projected_paths = {"etc/hostname", "etc/hosts", "etc/resolv.conf"}
            assert len(by_name) == len(members)
            assert "app/old.txt" not in by_name
            assert archive.extractfile("app/target.txt").read() == b"version-two\n"
            assert by_name["app/hard.txt"].islnk()
            assert by_name["app/hard.txt"].linkname == "app/target.txt"
            assert by_name["app/link.txt"].issym()
            assert by_name["app/link.txt"].linkname == "target.txt"
            for item in members:
                expected_owner = (0, 0) if item.name in projected_paths else (65532, 65532)
                assert (item.uid, item.gid) == expected_owner
                assert item.mtime == 0
            assert by_name["etc"].isdir()
            assert (by_name["etc"].mode, by_name["etc"].uid, by_name["etc"].gid) == (
                0o700,
                65532,
                65532,
            )
            for path in projected_paths:
                assert by_name[path].isreg()
                assert (by_name[path].mode, by_name[path].size) == (0o755, 0)
                assert archive.extractfile(path).read() == b""
            for node in rootfs._plan._rootfs_evidence.nodes:
                item = by_name[node.path]
                if node.path in projected_paths:
                    continue
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


def test_docker_managed_files_are_explicit_empty_root_owned_projection():
    from human_feedback.adapters import runtime_installation_archive as module

    etc = SimpleNamespace(path="etc", typeflag="5", mode=0o755, size_bytes=0, link_target=None)
    hostname = SimpleNamespace(
        path="etc/hostname",
        typeflag="0",
        mode=0o644,
        size_bytes=14,
        link_target=None,
    )
    resolv = SimpleNamespace(
        path="etc/resolv.conf",
        typeflag="0",
        mode=0o640,
        size_bytes=104,
        link_target=None,
    )

    entries = {entry.path: entry for entry in module._rootfs_entries((etc, hostname, resolv))}

    assert set(("etc/hostname", "etc/hosts", "etc/resolv.conf")) <= set(entries)
    assert entries["etc/hostname"].source is hostname
    assert entries["etc/resolv.conf"].source is resolv
    assert entries["etc/hosts"].source is None
    for path in ("etc/hostname", "etc/hosts", "etc/resolv.conf"):
        entry = entries[path]
        assert entry.kind == "regular"
        assert entry.projected_empty is True
        assert (entry.mode, entry.size_bytes, entry.uid, entry.gid, entry.mtime) == (
            0o755,
            0,
            0,
            0,
            0,
        )
        info = module._tar_info(entry)
        assert (info.type, info.mode, info.size, info.uid, info.gid, info.mtime) == (
            tarfile.REGTYPE,
            0o755,
            0,
            0,
            0,
            0,
        )


def test_docker_managed_projection_adds_safe_etc_parent_when_absent():
    from human_feedback.adapters import runtime_installation_archive as module

    app = SimpleNamespace(path="app", typeflag="5", mode=0o755, size_bytes=0, link_target=None)
    entries = {entry.path: entry for entry in module._rootfs_entries((app,))}

    assert entries["etc"].kind == "directory"
    assert (entries["etc"].mode, entries["etc"].uid, entries["etc"].gid) == (
        0o700,
        65532,
        65532,
    )
    assert all(
        entries[path].projected_empty for path in ("etc/hostname", "etc/hosts", "etc/resolv.conf")
    )


@pytest.mark.parametrize(
    "nodes",
    [
        (SimpleNamespace(path="etc", typeflag="0", mode=0o644, size_bytes=1, link_target=None),),
        (
            SimpleNamespace(path="etc", typeflag="5", mode=0o755, size_bytes=0, link_target=None),
            SimpleNamespace(
                path="etc/hostname",
                typeflag="2",
                mode=0o777,
                size_bytes=0,
                link_target="elsewhere",
            ),
        ),
        (
            SimpleNamespace(path="etc", typeflag="5", mode=0o755, size_bytes=0, link_target=None),
            SimpleNamespace(
                path="source",
                typeflag="0",
                mode=0o600,
                size_bytes=1,
                link_target=None,
            ),
            SimpleNamespace(
                path="etc/hosts",
                typeflag="1",
                mode=0o600,
                size_bytes=0,
                link_target="source",
            ),
        ),
        (
            SimpleNamespace(path="etc", typeflag="5", mode=0o755, size_bytes=0, link_target=None),
            SimpleNamespace(
                path="etc/hostname",
                typeflag="0",
                mode=0o644,
                size_bytes=1,
                link_target=None,
            ),
            SimpleNamespace(
                path="alias",
                typeflag="1",
                mode=0o644,
                size_bytes=0,
                link_target="etc/hostname",
            ),
        ),
        (
            SimpleNamespace(path="etc", typeflag="5", mode=0o755, size_bytes=0, link_target=None),
            SimpleNamespace(
                path="etc/resolv.conf",
                typeflag="0",
                mode=0o644,
                size_bytes=1,
                link_target=None,
            ),
            SimpleNamespace(
                path="alias",
                typeflag="2",
                mode=0o777,
                size_bytes=0,
                link_target="etc/resolv.conf",
            ),
        ),
        (
            SimpleNamespace(path="a", typeflag="2", mode=0o777, size_bytes=0, link_target="etc"),
            SimpleNamespace(
                path="b",
                typeflag="2",
                mode=0o777,
                size_bytes=0,
                link_target="a/hostname",
            ),
        ),
        (
            SimpleNamespace(path="a", typeflag="2", mode=0o777, size_bytes=0, link_target="/"),
            SimpleNamespace(
                path="b",
                typeflag="2",
                mode=0o777,
                size_bytes=0,
                link_target="a/etc/hostname",
            ),
        ),
        (
            SimpleNamespace(path="a", typeflag="2", mode=0o777, size_bytes=0, link_target="b"),
            SimpleNamespace(path="b", typeflag="2", mode=0o777, size_bytes=0, link_target="a"),
        ),
        tuple(
            SimpleNamespace(
                path=f"link-{position}",
                typeflag="2",
                mode=0o777,
                size_bytes=0,
                link_target=(f"link-{position + 1}" if position < 16 else "outside"),
            )
            for position in range(17)
        ),
    ],
    ids=(
        "etc-not-directory",
        "managed-symlink",
        "managed-hardlink",
        "hardlink-alias",
        "symlink-alias",
        "component-alias-via-etc",
        "component-alias-via-root",
        "symlink-cycle",
        "symlink-hop-budget",
    ),
)
def test_docker_managed_projection_rejects_unsafe_source_topology(nodes):
    from human_feedback.adapters import runtime_installation_archive as module

    with pytest.raises(module.RuntimeInstallationArchiveError):
        module._rootfs_entries(nodes)


def test_source_bytes_replaced_by_projection_are_still_hashed_read_only(tmp_path):
    from human_feedback.adapters import runtime_installation_archive as module

    etc = tmp_path / "etc"
    etc.mkdir(mode=0o700)
    payloads = {
        "etc/hostname": b"source-hostname\n",
        "etc/resolv.conf": b"source-resolver\n",
    }
    nodes = []
    for path, payload in payloads.items():
        target = tmp_path / path
        target.write_bytes(payload)
        target.chmod(0o600)
        nodes.append(
            SimpleNamespace(
                path=path,
                typeflag="0",
                mode=0o600,
                size_bytes=len(payload),
                link_target=None,
            )
        )
    root_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        hashes = module._rootfs_hashes(root_fd, tuple(nodes))
    finally:
        os.close(root_fd)

    assert hashes == {
        path: hashlib.sha256(payload).hexdigest() for path, payload in payloads.items()
    }
    entries = {entry.path: entry for entry in module._rootfs_entries(tuple(nodes))}
    for path in payloads:
        assert entries[path].projected_empty is True
        assert entries[path].size_bytes == 0
        assert (tmp_path / path).read_bytes() == payloads[path]


def test_ustar_splittable_long_path_uses_one_readable_header():
    from human_feedback.adapters import runtime_installation_archive as module

    parent = "a" * 80
    path = parent + "/" + "b" * 40
    entry = module._InstallationEntry(path, "directory", 0o700)
    encoded, header_count = module._encoded_header(entry)
    parent_encoded, parent_header_count = module._encoded_header(
        module._InstallationEntry(parent, "directory", 0o700)
    )

    assert len(path.encode("utf-8")) > 100
    assert len(encoded) == 512
    assert header_count == 1
    assert parent_header_count == 1
    with tarfile.open(
        fileobj=io.BytesIO(parent_encoded + encoded + b"\0" * 1024), mode="r:"
    ) as archive:
        assert tuple(
            (item.name, item.type, item.mode, item.uid, item.gid, item.mtime)
            for item in archive.getmembers()
        ) == (
            (parent, tarfile.DIRTYPE, 0o700, 65532, 65532, 0),
            (path, tarfile.DIRTYPE, 0o700, 65532, 65532, 0),
        )


def test_gnu_fallback_is_bounded_and_counts_longname_and_longlink_headers():
    from human_feedback import runtime_oci_tar
    from human_feedback.adapters import runtime_installation_archive as module

    long_path = "p" * 513
    long_target = "t" * 513
    entry = module._InstallationEntry(
        long_path,
        "symlink",
        0o600,
        link_target=long_target,
    )
    encoded, header_count = module._encoded_header(entry)

    assert header_count == 3
    with tarfile.open(fileobj=io.BytesIO(encoded + b"\0" * 1024), mode="r:") as archive:
        observed = archive.getmembers()
        assert tuple(
            (item.name, item.type, item.linkname, item.mode, item.uid, item.gid, item.mtime)
            for item in observed
        ) == (
            (long_path, tarfile.SYMTYPE, long_target, 0o600, 65532, 65532, 0),
        )

    bounded = module._InstallationEntry(
        "p" * runtime_oci_tar.MAX_OCI_TAR_PATH_BYTES,
        "symlink",
        0o600,
        link_target="t" * runtime_oci_tar.MAX_OCI_TAR_LINK_BYTES,
    )
    _, bounded_header_count = module._encoded_header(bounded)
    assert bounded_header_count == 3

    oversized_path = module._InstallationEntry(
        "p" * (runtime_oci_tar.MAX_OCI_TAR_PATH_BYTES + 1),
        "symlink",
        0o600,
        link_target="target",
    )
    oversized_link = module._InstallationEntry(
        "path",
        "symlink",
        0o600,
        link_target="t" * (runtime_oci_tar.MAX_OCI_TAR_LINK_BYTES + 1),
    )
    for oversized in (oversized_path, oversized_link):
        with pytest.raises(module.RuntimeInstallationArchiveError):
            module._encoded_header(oversized)


def test_physical_header_budget_counts_gnu_extensions_before_writing(monkeypatch):
    from human_feedback.adapters import runtime_installation_archive as module

    entries = (
        module._InstallationEntry("short", "directory", 0o700),
        module._InstallationEntry("x" * 513, "directory", 0o700),
    )
    monkeypatch.setattr(module, "MAX_INSTALLATION_ENTRIES", len(entries))
    with pytest.raises(module.RuntimeInstallationArchiveError):
        module._archive_size(entries)


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


def test_entry_bound_matches_parser_and_fails_before_first_archive_byte(monkeypatch, tmp_path):
    from human_feedback import runtime_oci_tar
    from human_feedback.adapters import runtime_installation_archive as module

    assert module.MAX_INSTALLATION_ENTRIES == runtime_oci_tar.MAX_OCI_TAR_ENTRIES
    filesystem, rootfs, checkpoint, checkpoint_root, root_fd = _issued_sources(
        monkeypatch, tmp_path
    )
    try:
        monkeypatch.setattr(module, "MAX_INSTALLATION_ENTRIES", 1)
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
