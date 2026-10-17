"""RED unit contract for the concrete gold-blind local-Docker port.

The fakes exercise orchestration only.  They do not contact Docker, load a
model, inspect a corpus, or grant scientific authority.
"""

from __future__ import annotations

import copy
import inspect
import pickle
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from human_feedback.loso_offline_adapter import (
    GoldBlindOfflineInput,
    canonical_laya_loso_offline_request_bytes,
    validate_laya_loso_offline_response,
)
from tests.test_laya_runtime_execution_image_lease import _registered_runtime
from tests.test_laya_runtime_rootfs_materialization import _clone_exact

_REQUEST = canonical_laya_loso_offline_request_bytes(
    (GoldBlindOfflineInput(opaque_token="a" * 64, comment="private feedback"),)
)
_RESPONSE = (
    b'{"predictions":[{"category":"data_quality","ordinal":0,'
    b'"probabilities":{"agronomic_context":0.1,"data_quality":0.6,'
    b'"model_behavior":0.1,"other":0.1,"usability":0.1},'
    b'"usage":{"state_tokens":7,"state_tokens_dropped":0,"truncated":false}}],'
    b'"schema_version":"laya-gold-blind-offline-response-v2"}'
)
_PRIVATE_CANARY = "DO_NOT_DISCLOSE_loso_child_7481"


class _FakeOfflineEngine:
    def __init__(self, nonce, events, *, failure=None, cleanup_failures=0):
        self.nonce = nonce
        self.events = events
        self.failure = failure
        self.cleanup_failures = cleanup_failures
        self.container_id = "c" * 64
        self.child_owned = False
        self.image_operations = []

    def _event(self, name):
        self.events.append(name)
        if self.failure == name:
            raise RuntimeError(_PRIVATE_CANARY)

    def create_closed_loso_offline_container(self, image_id):
        self._event("create")
        self.events.append(("create-image", image_id))
        self.child_owned = True
        return self.container_id

    def inspect_closed_loso_offline_container(self, container_id, *, expected_image_id):
        assert container_id == self.container_id
        self._event("inspect")
        self.events.append(("inspect-image", expected_image_id))
        return {"Id": container_id}

    def run_closed_loso_offline(self, container_id, *, expected_image_id, canonical_request):
        assert container_id == self.container_id
        assert canonical_request == _REQUEST
        self._event("run")
        self.events.append(("run-image", expected_image_id))
        if self.failure == "invalid-response":
            return b'{"private":"' + _PRIVATE_CANARY.encode() + b'"}'
        return _RESPONSE

    def cleanup_owned_resources(self):
        self.events.append("cleanup")
        if self.cleanup_failures:
            self.cleanup_failures -= 1
            raise RuntimeError(_PRIVATE_CANARY)
        self.child_owned = False

    def remove_owned_image(self, image_id):
        self.image_operations.append(("remove", image_id))
        raise AssertionError("the borrowed runtime image is not child-owned")

    def import_normalized_image(self, _producer):
        self.image_operations.append(("import", ""))
        raise AssertionError("an offline prediction must not create an image")


def _wire(
    monkeypatch,
    *,
    marker="1",
    failure=None,
    cleanup_failures=0,
    lease_exit_failure=False,
):
    from human_feedback.adapters import laya_loso_docker_adapter as adapter

    _materialization, runtime, _resource, parent_engine, image_id, installation, *_ = (
        _registered_runtime(monkeypatch, marker=marker)
    )
    events = []
    engines = []
    nonces = iter(("1" * 64, "2" * 64, "3" * 64))

    @contextmanager
    def lease(value):
        assert value is runtime
        events.append("lease-enter")
        try:
            yield SimpleNamespace(engine=parent_engine, image_id=image_id)
        finally:
            events.append("lease-exit")
            if lease_exit_failure:
                raise RuntimeError(_PRIVATE_CANARY)

    def engine_factory(nonce):
        events.append(("engine", nonce))
        engine = _FakeOfflineEngine(
            nonce,
            events,
            failure=failure,
            cleanup_failures=cleanup_failures,
        )
        engines.append(engine)
        return engine

    real_validate = validate_laya_loso_offline_response

    def validate(stdout, *, expected_count):
        events.append(("validate", expected_count))
        return real_validate(stdout, expected_count=expected_count)

    monkeypatch.setattr(adapter, "_lease_laya_runtime_image", lease)
    monkeypatch.setattr(adapter, "LocalDockerEngine", engine_factory)
    monkeypatch.setattr(adapter, "validate_laya_loso_offline_response", validate)
    monkeypatch.setattr(adapter.secrets, "token_hex", lambda _size: next(nonces))
    port = adapter.DockerLayaLosoOfflinePort(runtime)
    return SimpleNamespace(
        adapter=adapter,
        runtime=runtime,
        parent_engine=parent_engine,
        image_id=image_id,
        installation=installation,
        events=events,
        engines=engines,
        port=port,
    )


def _private_failure(error, *private):
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    rendered = repr((error.args, str(error), repr(error)))
    for value in private:
        assert value not in rendered


def test_surface_is_closed_and_runtime_binding_is_private(monkeypatch):
    from human_feedback.adapters.local_docker_engine import LocalDockerEngine

    wired = _wire(monkeypatch)
    adapter = wired.adapter
    assert tuple(inspect.signature(adapter.DockerLayaLosoOfflinePort).parameters) == (
        "runtime_evidence",
    )
    assert tuple(inspect.signature(adapter.DockerLayaLosoOfflinePort.predict).parameters) == (
        "self",
        "canonical_request",
    )
    assert tuple(inspect.signature(adapter.retry_laya_loso_offline_cleanup).parameters) == (
        "error",
    )
    real_parameters = inspect.signature(LocalDockerEngine.run_closed_loso_offline).parameters
    fake_parameters = inspect.signature(_FakeOfflineEngine.run_closed_loso_offline).parameters
    assert tuple(fake_parameters) == tuple(real_parameters)
    assert tuple(item.kind for item in fake_parameters.values()) == tuple(
        item.kind for item in real_parameters.values()
    )
    rendered = repr(wired.port)
    assert wired.image_id not in rendered
    assert wired.installation not in rendered
    assert not hasattr(wired.port, "model")
    assert not hasattr(wired.port, "scientifically_valid")


def test_success_uses_exact_lease_validates_and_cleans_before_return(monkeypatch):
    wired = _wire(monkeypatch)
    result = wired.port.predict(_REQUEST)
    assert result == validate_laya_loso_offline_response(_RESPONSE, expected_count=1)
    names = [event for event in wired.events if type(event) is str]
    assert names == ["lease-enter", "create", "inspect", "run", "cleanup", "lease-exit"]
    assert wired.events.index(("validate", 1)) < wired.events.index("cleanup")
    assert ("create-image", wired.image_id) in wired.events
    assert ("inspect-image", wired.image_id) in wired.events
    assert ("run-image", wired.image_id) in wired.events
    assert wired.engines[0].child_owned is False


@pytest.mark.parametrize(
    "invalid",
    (b"{}", _REQUEST + b"\n", b"x" * (64 * 1024 + 1), object()),
    ids=("open-object", "noncanonical", "oversized", "wrong-type"),
)
def test_request_is_rejected_before_lease_or_engine_io(monkeypatch, invalid):
    wired = _wire(monkeypatch)
    with pytest.raises(wired.adapter.DockerLayaLosoOfflineError):
        wired.port.predict(invalid)
    assert wired.events == []
    assert wired.engines == []


def test_each_prediction_uses_fresh_engine_without_owning_parent_image(monkeypatch):
    wired = _wire(monkeypatch)
    assert wired.port.predict(_REQUEST) == wired.port.predict(_REQUEST)
    assert len(wired.engines) == 2
    assert wired.engines[0] is not wired.engines[1]
    assert wired.engines[0].nonce != wired.engines[1].nonce
    assert all(engine.image_operations == [] for engine in wired.engines)
    assert getattr(wired.parent_engine, "removed", []) == []


@pytest.mark.parametrize("boundary", ("create", "inspect", "run", "invalid-response"))
def test_boundary_failure_cleans_child_inside_lease_and_returns_no_output(monkeypatch, boundary):
    wired = _wire(monkeypatch, failure=boundary)
    with pytest.raises(wired.adapter.DockerLayaLosoOfflineError) as caught:
        wired.port.predict(_REQUEST)
    assert "cleanup" in wired.events
    assert wired.events.index("cleanup") < wired.events.index("lease-exit")
    assert wired.engines[0].child_owned is False
    assert wired.engines[0].image_operations == []
    _private_failure(
        caught.value,
        _PRIVATE_CANARY,
        wired.image_id,
        wired.installation,
        "private feedback",
    )


def test_lease_exit_failure_suppresses_validated_output(monkeypatch):
    wired = _wire(monkeypatch, lease_exit_failure=True)
    with pytest.raises(wired.adapter.DockerLayaLosoOfflineError) as caught:
        wired.port.predict(_REQUEST)
    assert wired.events.index(("validate", 1)) < wired.events.index("cleanup")
    assert wired.events.index("cleanup") < wired.events.index("lease-exit")
    assert caught.value.cleanup_pending is False
    _private_failure(caught.value, _PRIVATE_CANARY, wired.image_id)


def test_cleanup_retry_is_exact_idempotent_and_cannot_be_transferred(monkeypatch):
    wired = _wire(monkeypatch, cleanup_failures=1)
    with pytest.raises(wired.adapter.DockerLayaLosoOfflineError) as caught:
        wired.port.predict(_REQUEST)
    error = caught.value
    assert error.cleanup_pending is True
    copied = copy.copy(error)
    restored = pickle.loads(pickle.dumps(error))
    for forged in (copied, restored, ValueError("forged")):
        with pytest.raises(wired.adapter.DockerLayaLosoOfflineError):
            wired.adapter.retry_laya_loso_offline_cleanup(forged)
    assert error.cleanup_pending is True
    wired.adapter.retry_laya_loso_offline_cleanup(error)
    wired.adapter.retry_laya_loso_offline_cleanup(error)
    assert error.cleanup_pending is False
    assert wired.engines[0].child_owned is False
    assert wired.engines[0].image_operations == []


def test_cloned_or_revoked_runtime_never_reaches_a_lease_or_engine(monkeypatch):
    from human_feedback import runtime_materialization
    from human_feedback.adapters import laya_loso_docker_adapter as adapter

    _materialization, runtime, _resource, parent_engine, image_id, installation, *_ = (
        _registered_runtime(monkeypatch, marker="7")
    )
    for invalid in (_clone_exact(runtime), object()):
        with pytest.raises(adapter.DockerLayaLosoOfflineError) as caught:
            adapter.DockerLayaLosoOfflinePort(invalid)
        _private_failure(caught.value, image_id, installation)
    runtime_materialization._revoke_evidence(runtime)
    with pytest.raises(adapter.DockerLayaLosoOfflineError):
        adapter.DockerLayaLosoOfflinePort(runtime)
    assert getattr(parent_engine, "removed", []) == []
