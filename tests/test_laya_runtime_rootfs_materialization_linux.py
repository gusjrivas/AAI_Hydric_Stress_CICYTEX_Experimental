"""Real descriptor and publication tests for the Linux mutation boundary."""

import os
import stat
import sys

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
