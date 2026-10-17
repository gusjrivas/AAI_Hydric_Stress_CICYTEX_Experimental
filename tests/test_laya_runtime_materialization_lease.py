"""A runtime assembler borrows an exact live rootfs without racing disposal."""

import os
import sys
import threading

import pytest

from human_feedback import runtime_rootfs_materialization as authority
from human_feedback.adapters import filesystem_rootfs_materialization as filesystem
from tests.test_laya_runtime_rootfs_materialization import _clone_exact
from tests.test_laya_runtime_rootfs_materialization_integration import _issued_materialization_plan

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="requires non-root Linux rootfs resource",
)


def _materialized(monkeypatch, tmp_path):
    _chain, source, plan = _issued_materialization_plan(monkeypatch, tmp_path)
    parent = tmp_path / "output"
    parent.mkdir(mode=0o700)
    evidence = filesystem.materialize_laya_runtime_rootfs(plan, str(source), str(parent), "rootfs")
    return evidence, parent


def test_lease_borrows_exact_inode_and_blocks_same_thread_disposal(monkeypatch, tmp_path):
    evidence, parent = _materialized(monkeypatch, tmp_path)
    descriptors_before = len(os.listdir("/proc/self/fd"))
    try:
        with filesystem._lease_laya_runtime_rootfs(evidence) as descriptor:
            expected = (parent / "rootfs").stat()
            observed = os.fstat(descriptor)
            assert (observed.st_dev, observed.st_ino) == (expected.st_dev, expected.st_ino)
            with pytest.raises(filesystem.RootfsMaterializationError):
                filesystem.dispose_laya_runtime_rootfs(evidence)
            authority.canonical_laya_runtime_rootfs_materialization_summary_bytes(evidence)
        assert len(os.listdir("/proc/self/fd")) == descriptors_before
    finally:
        filesystem.dispose_laya_runtime_rootfs(evidence)
    assert not (parent / "rootfs").exists()


def test_lease_rejects_clones_and_disposed_authority_without_leaking_handles(monkeypatch, tmp_path):
    evidence, _parent = _materialized(monkeypatch, tmp_path)
    try:
        before = len(os.listdir("/proc/self/fd"))
        with pytest.raises(filesystem.RootfsMaterializationError):
            with filesystem._lease_laya_runtime_rootfs(_clone_exact(evidence)):
                pytest.fail("clone acquired resource")
        assert len(os.listdir("/proc/self/fd")) == before
    finally:
        filesystem.dispose_laya_runtime_rootfs(evidence)
    with pytest.raises(filesystem.RootfsMaterializationError):
        with filesystem._lease_laya_runtime_rootfs(evidence):
            pytest.fail("disposed authority acquired resource")


def test_lease_releases_on_consumer_failure_and_serializes_other_thread_disposal(monkeypatch, tmp_path):
    evidence, parent = _materialized(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="consumer failure"):
        with filesystem._lease_laya_runtime_rootfs(evidence):
            raise RuntimeError("consumer failure")
    started = threading.Event()
    done = threading.Event()
    errors = []
    def dispose():
        started.set()
        try:
            filesystem.dispose_laya_runtime_rootfs(evidence)
        except Exception as error:
            errors.append(type(error).__name__)
        finally:
            done.set()
    with filesystem._lease_laya_runtime_rootfs(evidence) as descriptor:
        thread = threading.Thread(target=dispose)
        thread.start()
        assert started.wait(2)
        assert not done.wait(0.1)
        assert os.fstat(descriptor).st_ino == (parent / "rootfs").stat().st_ino
    thread.join(5)
    assert done.is_set()
    assert errors == []
    assert not (parent / "rootfs").exists()
