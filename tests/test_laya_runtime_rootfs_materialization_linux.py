"""Real descriptor and publication tests for the Linux mutation boundary."""

import os
import stat
import sys
import hashlib
from types import SimpleNamespace

import pytest

from human_feedback.adapters import filesystem_rootfs_materialization as adapter

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="requires Linux descriptor semantics"
)


def test_directory_chain_rejects_symlink_ancestor_and_closes_partial_descriptors(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "alias").symlink_to(real, target_is_directory=True)
    before = len(os.listdir("/proc/self/fd"))
    with pytest.raises(adapter.RootfsMaterializationError):
        adapter._open_directory_chain(tuple(str(tmp_path / "alias").split("/")[1:]))
    assert len(os.listdir("/proc/self/fd")) == before


def test_staging_is_private_unique_and_owned_cleanup_preserves_siblings(tmp_path):
    parent_fd = adapter._open_directory_chain(tuple(str(tmp_path).split("/")[1:]))
    (tmp_path / "keep").write_bytes(b"keep")
    try:
        name, descriptor, identity = adapter._create_staging(parent_fd)
        assert stat.S_IMODE(os.fstat(descriptor).st_mode) == 0o700
        os.mkdir("child", mode=0o700, dir_fd=descriptor)
        child = os.open("child", os.O_RDONLY | os.O_DIRECTORY, dir_fd=descriptor)
        try:
            file_fd = os.open("payload", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=child)
            os.write(file_fd, b"payload")
            os.close(file_fd)
            os.symlink(str(tmp_path / "keep"), "outside", dir_fd=child)
        finally:
            os.close(child)
        adapter._remove_owned_tree(parent_fd, name, descriptor, identity)
        assert not (tmp_path / name).exists()
        assert (tmp_path / "keep").read_bytes() == b"keep"
        os.close(descriptor)
    finally:
        os.close(parent_fd)


def test_cleanup_refuses_replaced_staging_name(tmp_path):
    parent_fd = adapter._open_directory_chain(tuple(str(tmp_path).split("/")[1:]))
    name, descriptor, identity = adapter._create_staging(parent_fd)
    try:
        os.rename(name, name + "-moved", src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        with pytest.raises(adapter.RootfsMaterializationError):
            adapter._remove_owned_tree(parent_fd, name, descriptor, identity)
        assert (tmp_path / name).is_dir()
        assert (tmp_path / (name + "-moved")).is_dir()
    finally:
        os.close(descriptor)
        os.close(parent_fd)


def test_atomic_publication_never_replaces_existing_winner(tmp_path):
    parent_fd = adapter._open_directory_chain(tuple(str(tmp_path).split("/")[1:]))
    name, descriptor, identity = adapter._create_staging(parent_fd)
    winner = tmp_path / "winner"
    winner.mkdir()
    (winner / "marker").write_bytes(b"winner")
    try:
        with pytest.raises(adapter.RootfsMaterializationError):
            adapter._publish_noreplace(parent_fd, name, "winner")
        assert (winner / "marker").read_bytes() == b"winner"
        assert (tmp_path / name).is_dir()
        adapter._remove_owned_tree(parent_fd, name, descriptor, identity)
    finally:
        os.close(descriptor)
        os.close(parent_fd)


def test_atomic_publication_preserves_staging_inode(tmp_path):
    parent_fd = adapter._open_directory_chain(tuple(str(tmp_path).split("/")[1:]))
    name, descriptor, identity = adapter._create_staging(parent_fd)
    try:
        adapter._publish_noreplace(parent_fd, name, "published")
        published = os.stat("published", dir_fd=parent_fd, follow_symlinks=False)
        assert (published.st_dev, published.st_ino) == identity
        assert not (tmp_path / name).exists()
        adapter._remove_owned_tree(parent_fd, "published", descriptor, identity)
    finally:
        os.close(descriptor)
        os.close(parent_fd)


def _node(path, *, kind="0", size=0, layer=0, target=None):
    return SimpleNamespace(
        path=path,
        typeflag=kind,
        size_bytes=size,
        source_layer_position=layer,
        link_target=target,
        mode=0o644,
        uid=0,
        gid=0,
        mtime=0,
    )


def test_writer_only_keeps_final_regular_payloads_and_handles_short_writes(tmp_path, monkeypatch):
    descriptor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    nodes = (_node("data", kind="5"), _node("data/value", size=6, layer=1), _node("empty"))
    writer = adapter._RootfsWriter(descriptor, nodes)
    native_write = os.write
    monkeypatch.setattr(adapter.os, "write", lambda fd, data: native_write(fd, data[:2]))
    try:
        obsolete = writer.sink(0)
        obsolete.start(_node("data/value", size=3))
        obsolete.chunk(b"old")
        obsolete.end()
        obsolete.start(nodes[2])
        obsolete.end()
        final = writer.sink(1)
        final.start(nodes[1])
        final.chunk(b"abcdef")
        final.end()
        assert writer.finish_regulars() == {
            "data/value": hashlib.sha256(b"abcdef").hexdigest(),
            "empty": hashlib.sha256(b"").hexdigest(),
        }
        assert (tmp_path / "data/value").read_bytes() == b"abcdef"
        assert stat.S_IMODE((tmp_path / "data/value").stat().st_mode) == 0o600
    finally:
        writer.close()
        os.close(descriptor)


@pytest.mark.parametrize("case", ("missing", "truncated", "overflow", "duplicate", "zero-write"))
def test_writer_refuses_incomplete_or_invalid_payloads(tmp_path, monkeypatch, case):
    descriptor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    node = _node("value", size=3)
    writer = adapter._RootfsWriter(descriptor, (node,))
    sink = writer.sink(0)
    try:
        with pytest.raises(adapter.RootfsMaterializationError):
            if case == "missing":
                writer.finish_regulars()
            else:
                sink.start(node)
                if case == "zero-write":
                    monkeypatch.setattr(adapter.os, "write", lambda *_args: 0)
                sink.chunk(
                    b"abcd" if case == "overflow" else b"ab" if case == "truncated" else b"abc"
                )
                sink.end()
                if case == "duplicate":
                    sink.start(node)
    finally:
        writer.close()
        os.close(descriptor)


def _written_tree(tmp_path):
    descriptor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    nodes = (
        _node("value", size=3, layer=1),
        _node("alias", kind="1", target="value"),
        _node("chain", kind="1", target="alias"),
        _node("symlink", kind="2", target="/value"),
    )
    writer = adapter._RootfsWriter(descriptor, nodes)
    sink = writer.sink(1)
    sink.start(nodes[0])
    sink.chunk(b"new")
    sink.end()
    hashes = writer.finish_regulars()
    writer.close()
    return descriptor, nodes, hashes


def test_final_links_resolve_to_replaced_terminal_and_commitment_is_repeatable(tmp_path):
    commitments = []
    for name in ("first", "second"):
        root = tmp_path / name
        root.mkdir(mode=0o700)
        descriptor, nodes, hashes = _written_tree(root)
        try:
            adapter._create_final_links(descriptor, nodes)
            assert (root / "alias").read_bytes() == b"new"
            assert (root / "chain").stat().st_ino == (root / "value").stat().st_ino
            assert (root / "value").stat().st_nlink == 3
            assert os.readlink(root / "symlink") == "/value"
            commitments.append(adapter._verify_staged_tree(descriptor, nodes, hashes, "a" * 64))
        finally:
            os.close(descriptor)
    assert commitments[0] == commitments[1]
    assert len(commitments[0]) == 64


@pytest.mark.parametrize("corruption", ("content", "extra", "hardlink", "symlink", "mode"))
def test_staged_verification_detects_content_topology_and_permission_drift(tmp_path, corruption):
    descriptor, nodes, hashes = _written_tree(tmp_path)
    try:
        adapter._create_final_links(descriptor, nodes)
        if corruption == "content":
            (tmp_path / "value").write_bytes(b"bad")
        elif corruption == "extra":
            (tmp_path / "extra").write_bytes(b"extra")
        elif corruption == "hardlink":
            (tmp_path / "chain").unlink()
            (tmp_path / "chain").write_bytes(b"new")
        elif corruption == "symlink":
            (tmp_path / "symlink").unlink()
            (tmp_path / "symlink").symlink_to("/wrong")
        else:
            (tmp_path / "value").chmod(0o666)
        with pytest.raises(adapter.RootfsMaterializationError):
            adapter._verify_staged_tree(descriptor, nodes, hashes, "a" * 64)
    finally:
        os.close(descriptor)
