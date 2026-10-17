"""Runtime authority is granted only after trusted recapture and closed load."""

import io
import os
import sys
from contextlib import contextmanager

import pytest

from tests.test_laya_runtime_installation_archive import _issued_sources

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="requires non-root Linux descriptor-relative source capture",
)


class _Engine:
    def __init__(self, nonce, *, failure=None):
        self.events = []
        self.failure = failure
        self.image_id = "sha256:" + "1" * 64
        self.container_id = "2" * 64
        self.image = self.container = False

    def _event(self, event):
        self.events.append(event)
        if self.failure == event:
            raise RuntimeError("private Docker detail")

    def import_normalized_image(self, producer):
        self._event("import")
        target = io.BytesIO()
        assert producer(target) == len(target.getvalue())
        self.archive = target.getvalue()
        self.image = True
        return self.image_id

    def create_closed_probe_container(self, image):
        assert image == self.image_id
        self._event("create")
        self.container = True
        return self.container_id

    @contextmanager
    def export_stopped_container_stream(self, container):
        assert container == self.container_id
        self._event("export")
        payload = self.archive if self.failure != "recapture" else self.archive[:-1024]
        yield iter([payload])

    def run_closed_probe(self, container, *, expected_image_id):
        assert container == self.container_id
        assert expected_image_id == self.image_id
        self._event("load")

    def remove_owned_container(self, container):
        assert container == self.container_id
        self._event("remove-container")
        self.container = False

    def remove_owned_image(self, image):
        assert image == self.image_id
        self._event("remove-image")
        self.image = False


def _setup(monkeypatch, tmp_path, failure=None):
    from human_feedback import runtime_materialization as authority
    from human_feedback.adapters import docker_runtime_materialization as adapter

    filesystem, rootfs, checkpoint, checkpoint_root, descriptor = _issued_sources(
        monkeypatch, tmp_path
    )
    os.close(descriptor)
    plan = authority.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
    engine = _Engine("a" * 32, failure=failure)
    monkeypatch.setattr(adapter, "LocalDockerEngine", lambda nonce: engine)
    return authority, adapter, filesystem, rootfs, plan, checkpoint_root, engine


def test_only_recaptured_loaded_image_produces_runtime_authority(monkeypatch, tmp_path):
    authority, adapter, filesystem, rootfs, plan, source, engine = _setup(monkeypatch, tmp_path)
    baseline = len(os.listdir("/proc/self/fd"))
    evidence = adapter.materialize_laya_runtime(plan, str(source))
    assert engine.events == ["import", "create", "export", "load", "remove-container"]
    assert engine.image and not engine.container
    summary = authority.canonical_laya_runtime_materialization_summary_bytes(evidence)
    assert b'"runtime_materialized":true' in summary
    assert b'"executor_available":false' in summary
    assert b'"inference_executed":false' in summary
    assert engine.image_id.encode() not in summary
    assert len(os.listdir("/proc/self/fd")) == baseline
    filesystem.dispose_laya_runtime_rootfs(rootfs)
    adapter.dispose_laya_runtime(evidence)
    adapter.dispose_laya_runtime(evidence)
    assert not engine.image and not engine.container
    with pytest.raises(ValueError):
        authority.canonical_laya_runtime_materialization_summary_bytes(evidence)


@pytest.mark.parametrize("failure", ["import", "create", "export", "recapture", "load", "remove-container"])
def test_failure_never_issues_runtime_and_cleans_only_owned_resources(monkeypatch, tmp_path, failure):
    _, adapter, filesystem, rootfs, plan, source, engine = _setup(monkeypatch, tmp_path, failure)
    baseline = len(os.listdir("/proc/self/fd"))
    try:
        with pytest.raises(ValueError, match="runtime materialization") as caught:
            adapter.materialize_laya_runtime(plan, str(source))
        assert "private Docker detail" not in str(caught.value)
        assert caught.value.__context__ is None
        assert not engine.image
        if failure != "remove-container":
            assert not engine.container
        if failure in {"export", "recapture"}:
            assert "load" not in engine.events
        assert len(os.listdir("/proc/self/fd")) == baseline
    finally:
        filesystem.dispose_laya_runtime_rootfs(rootfs)


def test_dispose_failure_revokes_and_can_retry_after_parent_disposal(monkeypatch, tmp_path):
    authority, adapter, filesystem, rootfs, plan, source, engine = _setup(monkeypatch, tmp_path)
    evidence = adapter.materialize_laya_runtime(plan, str(source))
    filesystem.dispose_laya_runtime_rootfs(rootfs)
    engine.failure = "remove-image"
    with pytest.raises(ValueError):
        adapter.dispose_laya_runtime(evidence)
    with pytest.raises(ValueError):
        authority.canonical_laya_runtime_materialization_summary_bytes(evidence)
    engine.failure = None
    adapter.dispose_laya_runtime(evidence)
    assert not engine.image
