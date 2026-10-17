"""Runtime authority is granted only after trusted recapture and closed load."""

import io
import os
import pickle
import sys
import threading
import weakref
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
        assert "inspect" in self.events
        self._event("export")
        payload = self.archive if self.failure != "recapture" else self.archive[:-1024]
        yield iter([payload])

    def inspect_closed_probe_container(self, container, *, expected_image_id):
        assert container == self.container_id and expected_image_id == self.image_id
        self._event("inspect")

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

    def cleanup_owned_resources(self):
        errors = []
        for present, remove, identity in (
            (self.container, self.remove_owned_container, self.container_id),
            (self.image, self.remove_owned_image, self.image_id),
        ):
            if present:
                try:
                    remove(identity)
                except Exception as error:
                    errors.append(error)
        if errors:
            raise RuntimeError("private cleanup failure")


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
    assert engine.events == ["import", "create", "inspect", "export", "load", "remove-container"]
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


def test_failure_stage_is_closed_readonly_and_pickle_safe_without_changing_error_surface():
    from human_feedback.adapters import docker_runtime_materialization as adapter

    expected = {
        "unknown",
        "predecessor_validation",
        "rootfs_lease",
        "engine_initialization",
        "archive_assembly",
        "image_import",
        "container_create",
        "isolation_inspection",
        "content_recapture",
        "model_load",
        "container_cleanup",
        "evidence_issuance/resource_registration",
        "resource_cleanup",
    }
    assert {stage.value for stage in adapter.RuntimeMaterializationFailureStage} == expected
    with pytest.raises(ValueError):
        adapter.RuntimeMaterializationFailureStage("private stage")
    with pytest.raises(adapter.LayaRuntimeMaterializationError) as caught:
        adapter._fail(adapter.RuntimeMaterializationFailureStage.UNKNOWN)
    error = caught.value
    assert error.failure_stage is adapter.RuntimeMaterializationFailureStage.UNKNOWN
    assert error.args == ("secure runtime materialization failed",)
    assert str(error) == "secure runtime materialization failed"
    assert repr(error) == (
        "LayaRuntimeMaterializationError('secure runtime materialization failed')"
    )
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    with pytest.raises(AttributeError):
        error.failure_stage = adapter.RuntimeMaterializationFailureStage.MODEL_LOAD

    encoded = pickle.dumps(error)
    restored = pickle.loads(encoded)
    assert type(restored) is adapter.LayaRuntimeMaterializationError
    assert restored.args == error.args
    assert restored.failure_stage is adapter.RuntimeMaterializationFailureStage.UNKNOWN
    assert restored.cleanup_pending is False
    assert b"private" not in encoded


@pytest.mark.parametrize(
    ("failure", "expected_stage"),
    (
        ("import", "image_import"),
        ("create", "container_create"),
        ("inspect", "isolation_inspection"),
        ("export", "content_recapture"),
        ("recapture", "content_recapture"),
        ("load", "model_load"),
        ("remove-container", "container_cleanup"),
    ),
)
def test_failure_never_issues_runtime_and_cleans_only_owned_resources(
    monkeypatch, tmp_path, failure, expected_stage
):
    _, adapter, filesystem, rootfs, plan, source, engine = _setup(monkeypatch, tmp_path, failure)
    baseline = len(os.listdir("/proc/self/fd"))
    try:
        with pytest.raises(ValueError, match="runtime materialization") as caught:
            adapter.materialize_laya_runtime(plan, str(source))
        assert caught.value.failure_stage.value == expected_stage
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


@pytest.mark.parametrize(
    ("failure_stage", "patch_target"),
    (
        ("predecessor_validation", "predecessor"),
        ("rootfs_lease", "lease"),
        ("engine_initialization", "engine"),
        ("archive_assembly", "archive"),
        ("evidence_issuance/resource_registration", "issuance"),
    ),
)
def test_closed_failure_stage_covers_non_engine_materialization_boundaries(
    monkeypatch, tmp_path, failure_stage, patch_target
):
    _, adapter, filesystem, rootfs, plan, source, engine = _setup(monkeypatch, tmp_path)

    @contextmanager
    def unavailable_lease(_evidence):
        raise RuntimeError("private lease detail")
        yield  # pragma: no cover - keeps this a context manager

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("private boundary detail")

    if patch_target == "predecessor":
        monkeypatch.setattr(adapter._authority, "_revalidate_plan", unavailable)
    elif patch_target == "lease":
        monkeypatch.setattr(adapter, "_lease_laya_runtime_rootfs", unavailable_lease)
    elif patch_target == "engine":
        monkeypatch.setattr(adapter, "LocalDockerEngine", unavailable)
    elif patch_target == "archive":
        monkeypatch.setattr(adapter, "_write_laya_runtime_installation_archive", unavailable)
    else:
        monkeypatch.setattr(
            adapter._authority, "_seal_laya_runtime_materialization_evidence", unavailable
        )

    try:
        with pytest.raises(adapter.LayaRuntimeMaterializationError) as caught:
            adapter.materialize_laya_runtime(plan, str(source))
        error = caught.value
        assert error.failure_stage.value == failure_stage
        assert str(error) == "secure runtime materialization failed"
        assert "private" not in str(error)
        assert failure_stage not in str(error)
        assert failure_stage not in repr(error)
        with pytest.raises(AttributeError):
            error.failure_stage = adapter.RuntimeMaterializationFailureStage.MODEL_LOAD
        assert error.__context__ is None
        assert error.__suppress_context__ is True
        assert not engine.image and not engine.container
    finally:
        filesystem.dispose_laya_runtime_rootfs(rootfs)


def test_rootfs_lease_release_failure_uses_unknown_instead_of_false_boundary(monkeypatch, tmp_path):
    _, adapter, filesystem, rootfs, plan, source, engine = _setup(monkeypatch, tmp_path)
    original_lease = adapter._lease_laya_runtime_rootfs

    @contextmanager
    def fail_on_release(evidence):
        with original_lease(evidence) as descriptor:
            yield descriptor
        raise RuntimeError("private release detail")

    monkeypatch.setattr(adapter, "_lease_laya_runtime_rootfs", fail_on_release)
    try:
        with pytest.raises(adapter.LayaRuntimeMaterializationError) as caught:
            adapter.materialize_laya_runtime(plan, str(source))
        assert caught.value.failure_stage.value == "unknown"
        assert "private release detail" not in str(caught.value)
        assert not engine.image and not engine.container
    finally:
        filesystem.dispose_laya_runtime_rootfs(rootfs)


def test_dispose_failure_revokes_and_can_retry_after_parent_disposal(monkeypatch, tmp_path):
    authority, adapter, filesystem, rootfs, plan, source, engine = _setup(monkeypatch, tmp_path)
    evidence = adapter.materialize_laya_runtime(plan, str(source))
    filesystem.dispose_laya_runtime_rootfs(rootfs)
    engine.failure = "remove-image"
    with pytest.raises(ValueError) as caught:
        adapter.dispose_laya_runtime(evidence)
    assert caught.value.failure_stage.value == "resource_cleanup"
    with pytest.raises(ValueError):
        authority.canonical_laya_runtime_materialization_summary_bytes(evidence)
    engine.failure = None
    adapter.dispose_laya_runtime(evidence)
    assert not engine.image


def test_failed_attempt_retains_private_retry_handle_not_runtime_authority(monkeypatch, tmp_path):
    _, adapter, filesystem, rootfs, plan, source, engine = _setup(monkeypatch, tmp_path, "load")
    remove = engine.remove_owned_image

    def unavailable(_identity):
        raise RuntimeError("daemon temporarily unavailable")

    engine.remove_owned_image = unavailable
    try:
        with pytest.raises(ValueError) as caught:
            adapter.materialize_laya_runtime(plan, str(source))
        error = caught.value
        assert error.cleanup_pending is True
        encoded = pickle.dumps(error)
        restored = pickle.loads(encoded)
        assert restored.failure_stage.value == "model_load"
        assert restored.cleanup_pending is False
        assert engine.image_id.encode() not in encoded
        assert engine.image_id not in str(error)
        assert engine.image_id not in repr(error)
        with pytest.raises(ValueError) as retry_failure:
            adapter.retry_laya_runtime_materialization_cleanup(error)
        assert retry_failure.value.failure_stage.value == "resource_cleanup"
        assert error.failure_stage.value == "model_load"
        engine.remove_owned_image = remove
        engine.failure = None
        adapter.retry_laya_runtime_materialization_cleanup(error)
        adapter.retry_laya_runtime_materialization_cleanup(error)
        assert error.cleanup_pending is False
        assert not engine.image and not engine.container
        with pytest.raises(ValueError) as forged:
            adapter.retry_laya_runtime_materialization_cleanup(ValueError("forged"))
        assert forged.value.failure_stage.value == "resource_cleanup"
    finally:
        filesystem.dispose_laya_runtime_rootfs(rootfs)


def test_disposing_one_runtime_does_not_block_an_independent_runtime(monkeypatch):
    from human_feedback.adapters import docker_runtime_materialization as adapter

    class Evidence:
        pass

    first, second = Evidence(), Evidence()
    entered, release, independent = threading.Event(), threading.Event(), threading.Event()
    errors = []

    class Engine:
        def __init__(self, blocked):
            self.blocked = blocked

        def remove_owned_image(self, _identity):
            if self.blocked:
                entered.set()
                assert release.wait(5)
            else:
                independent.set()

    monkeypatch.setattr(adapter._authority, "_revoke_evidence", lambda value: None)
    for token, blocked in ((first, True), (second, False)):
        resource = adapter._RuntimeResource(
            weakref.ref(token), Engine(blocked), "sha256:" + "a" * 64
        )
        monkeypatch.setitem(adapter._RESOURCES, id(token), resource)

    def dispose(token):
        try:
            adapter.dispose_laya_runtime(token)
        except Exception as error:
            errors.append(error)

    one = threading.Thread(target=dispose, args=(first,))
    two = threading.Thread(target=dispose, args=(second,))
    one.start()
    try:
        assert entered.wait(2)
        two.start()
        assert independent.wait(2), "unrelated runtime cleanup blocked by global I/O lock"
    finally:
        release.set()
        one.join(5)
        if two.ident is not None:
            two.join(5)
    assert not one.is_alive() and not two.is_alive()
    assert not errors
