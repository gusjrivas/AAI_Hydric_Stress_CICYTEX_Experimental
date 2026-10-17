"""RED-only contract for a descriptor-free lease over one exact PR40 image.

This preparation remains blocked on OpenSpec dependency 1.5.  It uses only
synthetically issued unit authority and never contacts Docker or runs inference.
"""

from __future__ import annotations

import threading
import weakref

import pytest

from tests.test_laya_runtime_execution import _issued_runtime
from tests.test_laya_runtime_rootfs_materialization import _clone_exact


class _Engine:
    def __init__(self) -> None:
        self.removed: list[str] = []
        self.remove_entered = threading.Event()

    def remove_owned_image(self, image_id: str) -> None:
        self.remove_entered.set()
        self.removed.append(image_id)


def _registered_runtime(monkeypatch, *, marker: str):
    from human_feedback.adapters import docker_runtime_materialization as adapter

    chain, supply, runtime, image_id, installation = _issued_runtime(monkeypatch, marker=marker)
    engine = _Engine()
    resource = adapter._RuntimeResource(weakref.ref(runtime), engine, image_id)
    monkeypatch.setitem(adapter._RESOURCES, id(runtime), resource)
    return adapter, runtime, resource, engine, image_id, installation, chain, supply


def _wait_until_disposing(resource) -> None:
    with resource.condition:
        assert resource.condition.wait_for(lambda: resource.disposing, timeout=2)


def _start_disposer(adapter, runtime):
    entered = threading.Event()
    errors: list[BaseException] = []

    def dispose() -> None:
        entered.set()
        try:
            adapter.dispose_laya_runtime(runtime)
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=dispose, daemon=False)
    thread.start()
    assert entered.wait(2)
    return thread, errors


def test_image_lease_is_descriptor_free_and_exactly_bound(monkeypatch):
    from human_feedback import runtime_materialization

    adapter, runtime, resource, engine, image_id, installation, *_ = _registered_runtime(
        monkeypatch, marker="1"
    )
    owner = threading.get_ident()

    with adapter._lease_laya_runtime_image(runtime) as lease:
        assert lease.engine is engine
        assert lease.image_id is runtime._image_id
        assert lease.image_id == image_id
        assert not hasattr(lease, "fileno")
        assert not hasattr(lease, "descriptor")
        assert image_id not in repr(lease)
        assert installation not in repr(lease)
        with resource.condition:
            assert resource.leases == 1
            assert resource.lease_owners == {owner: 1}
        runtime_materialization.canonical_laya_runtime_materialization_summary_bytes(runtime)

    with resource.condition:
        assert resource.leases == 0
        assert resource.lease_owners == {}
    assert engine.removed == []


def test_image_lease_rejects_clone_and_revoked_runtime_before_exposure(monkeypatch):
    from human_feedback import runtime_materialization

    adapter, runtime, _resource, engine, image_id, installation, *_ = _registered_runtime(
        monkeypatch, marker="3"
    )
    for invalid in (_clone_exact(runtime), object()):
        with pytest.raises(ValueError) as captured:
            with adapter._lease_laya_runtime_image(invalid):
                pytest.fail("invalid runtime exposed an image lease")
        assert image_id not in str(captured.value)
        assert installation not in str(captured.value)

    runtime_materialization._revoke_evidence(runtime)
    with pytest.raises(ValueError):
        with adapter._lease_laya_runtime_image(runtime):
            pytest.fail("revoked runtime exposed an image lease")
    assert engine.removed == []


def test_foreign_disposer_waits_for_its_runtime_lease(monkeypatch):
    from human_feedback import runtime_materialization

    adapter, runtime, resource, engine, image_id, *_ = _registered_runtime(monkeypatch, marker="5")
    thread = None
    errors = []
    try:
        with adapter._lease_laya_runtime_image(runtime):
            thread, errors = _start_disposer(adapter, runtime)
            _wait_until_disposing(resource)
            assert thread.is_alive()
            assert not engine.remove_entered.is_set()
            assert resource.revoked is False
            runtime_materialization.canonical_laya_runtime_materialization_summary_bytes(runtime)
        thread.join(5)
        assert not thread.is_alive()
        assert errors == []
        assert engine.removed == [image_id]
        with pytest.raises(ValueError):
            runtime_materialization.canonical_laya_runtime_materialization_summary_bytes(runtime)
    finally:
        if thread is not None:
            thread.join(5)
            assert not thread.is_alive()


def test_same_thread_dispose_fails_without_revoke(monkeypatch):
    from human_feedback import runtime_materialization

    adapter, runtime, resource, engine, image_id, *_ = _registered_runtime(monkeypatch, marker="7")

    with adapter._lease_laya_runtime_image(runtime):
        with pytest.raises(ValueError):
            adapter.dispose_laya_runtime(runtime)
        assert resource.revoked is False
        assert resource.disposed is False
        assert engine.removed == []
        runtime_materialization.canonical_laya_runtime_materialization_summary_bytes(runtime)

    adapter.dispose_laya_runtime(runtime)
    assert engine.removed == [image_id]


def test_independent_runtime_disposal_does_not_wait_on_other_lease(monkeypatch):
    adapter, first, first_resource, first_engine, first_image, *_ = _registered_runtime(
        monkeypatch, marker="a"
    )
    (
        _adapter,
        second,
        second_resource,
        second_engine,
        second_image,
        *_,
    ) = _registered_runtime(monkeypatch, marker="c")
    first_thread = second_thread = None
    first_errors = second_errors = []
    try:
        with adapter._lease_laya_runtime_image(first):
            first_thread, first_errors = _start_disposer(adapter, first)
            _wait_until_disposing(first_resource)
            second_thread, second_errors = _start_disposer(adapter, second)
            second_thread.join(2)
            assert not second_thread.is_alive(), "independent disposal used a global wait"
            assert second_errors == []
            assert second_engine.removed == [second_image]
            assert second_resource.disposed is True
            assert first_engine.removed == []
        first_thread.join(5)
        assert not first_thread.is_alive()
        assert first_errors == []
        assert first_engine.removed == [first_image]
    finally:
        for thread in (second_thread, first_thread):
            if thread is not None:
                thread.join(5)
                assert not thread.is_alive()


def test_image_lease_finally_balances_counters_after_body_failure(monkeypatch):
    adapter, runtime, resource, engine, image_id, *_ = _registered_runtime(monkeypatch, marker="d")

    with pytest.raises(RuntimeError, match="synthetic body failure"):
        with adapter._lease_laya_runtime_image(runtime):
            raise RuntimeError("synthetic body failure")

    with resource.condition:
        assert resource.leases == 0
        assert resource.lease_owners == {}
        assert resource.disposing is False
    adapter.dispose_laya_runtime(runtime)
    assert engine.removed == [image_id]
