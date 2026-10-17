"""DRAFT RED contract for the future PR41 Docker execution orchestrator.

This file intentionally lives outside the repository.  Do not import it into the
test suite until OpenSpec dependency 1.5 and the PR40 acceptance gate are closed.
It uses synthetic authorities and fake engines only: no daemon, model, network,
scientific corpus, or inference is touched.
"""

from __future__ import annotations

import copy
import inspect
import pickle
import re
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from tests.test_laya_runtime_execution_image_lease import _registered_runtime
from tests.test_laya_runtime_rootfs_materialization import _clone_exact

_CANONICAL_OBSERVATION = (
    b'{"predictions":[{"answer_confidence":0.6,"choice":"data_quality",'
    b'"confidence":0.4,"probabilities":{"agronomic_context":0.1,'
    b'"data_quality":0.6,"model_behavior":0.1,"other":0.1,"usability":0.1}},'
    b'{"answer_confidence":0.6,"choice":"data_quality","confidence":0.4,'
    b'"probabilities":{"agronomic_context":0.1,"data_quality":0.6,'
    b'"model_behavior":0.1,"other":0.1,"usability":0.1}}],'
    b'"schema_version":"laya-synthetic-execution-probe-v1"}'
)
_PRIVATE_CANARY = "DO_NOT_DISCLOSE_execution_91d7"


class FakeExecutionEngine:
    """One-attempt engine spy which owns a child but never owns the leased image."""

    def __init__(
        self,
        nonce: str,
        events: list[object],
        *,
        failure: str | None = None,
        cleanup_failures: int = 0,
    ) -> None:
        self.nonce = nonce
        self.events = events
        self.failure = failure
        self.cleanup_failures = cleanup_failures
        self.container_id = "c" * 64
        self.child_owned = False
        self.image_operations: list[tuple[str, str]] = []

    def _event(self, name: str) -> None:
        self.events.append(name)
        if self.failure == name:
            raise RuntimeError(_PRIVATE_CANARY)

    def create_closed_synthetic_probe_container(self, image_id: str) -> str:
        self._event("create")
        self.events.append(("create-image", image_id))
        self.child_owned = True
        return self.container_id

    def inspect_closed_synthetic_probe_container(
        self, container_id: str, *, expected_image_id: str
    ) -> dict[str, object]:
        assert container_id == self.container_id
        self._event("inspect")
        self.events.append(("inspect-image", expected_image_id))
        return {"Id": container_id}

    def run_closed_synthetic_probe(self, container_id: str, *, expected_image_id: str) -> bytes:
        assert container_id == self.container_id
        self._event("run")
        self.events.append(("run-image", expected_image_id))
        return _CANONICAL_OBSERVATION

    def cleanup_owned_resources(self) -> None:
        self.events.append("cleanup")
        if self.cleanup_failures:
            self.cleanup_failures -= 1
            raise RuntimeError(_PRIVATE_CANARY)
        self.child_owned = False

    # Any call is a contract violation: the leased image remains PR40-owned.
    def remove_owned_image(self, image_id: str) -> None:
        self.image_operations.append(("remove", image_id))
        raise AssertionError("execution engine must not clean the parent image")

    def import_normalized_image(self, _producer) -> str:
        self.image_operations.append(("import", ""))
        raise AssertionError("execution engine must not create an image")


def _private_failure(error: BaseException, *private: str) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    rendered = repr((error.args, str(error), repr(error)))
    for value in private:
        assert value not in rendered
    stage = getattr(error, "failure_stage", None)
    if stage is not None:
        safe = getattr(stage, "value", stage)
        assert type(safe) is str
        assert re.fullmatch(r"[a-z_/-]+", safe)
        assert safe not in rendered


def _wire(
    monkeypatch,
    *,
    marker: str = "1",
    failure: str | None = None,
    cleanup_failures: int = 0,
    issue_failure: bool = False,
    seal_failure: bool = False,
    lease_exit_failure: bool = False,
):
    """Install only explicit seams; production authority validation remains real."""

    import human_feedback.adapters.docker_runtime_execution as adapter

    from human_feedback import runtime_execution as authority

    materialization, runtime, resource, parent_engine, image_id, installation, *_ = (
        _registered_runtime(monkeypatch, marker=marker)
    )
    plan = authority.prepare_laya_runtime_execution_plan(runtime)
    events: list[object] = []
    engines: list[FakeExecutionEngine] = []
    nonces = iter(("a" * 64, "b" * 64, "d" * 64))
    receipts: list[object] = []
    evidence = object()

    original_revalidate = authority._revalidate_plan

    def revalidate(value):
        events.append("revalidate")
        return original_revalidate(value)

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

    def engine_factory(nonce: str):
        events.append(("engine", nonce))
        engine = FakeExecutionEngine(
            nonce,
            events,
            failure=failure,
            cleanup_failures=cleanup_failures,
        )
        engines.append(engine)
        return engine

    def issue(value, observation: bytes):
        events.append("receipt")
        assert value is plan
        assert observation is _CANONICAL_OBSERVATION
        if issue_failure:
            raise RuntimeError(_PRIVATE_CANARY)
        receipt = object()
        receipts.append(receipt)
        return receipt

    def seal(value, issued_receipt):
        events.append("seal")
        assert value is plan
        assert issued_receipt is receipts[-1]
        if seal_failure:
            raise RuntimeError(_PRIVATE_CANARY)
        return evidence

    revoked: list[object] = []
    monkeypatch.setattr(authority, "_revalidate_plan", revalidate)
    monkeypatch.setattr(authority, "_issue_laya_runtime_execution_receipt", issue)
    monkeypatch.setattr(authority, "_seal_laya_runtime_execution_evidence", seal)
    monkeypatch.setattr(authority, "_revoke_evidence", revoked.append)
    monkeypatch.setattr(adapter, "_lease_laya_runtime_image", lease)
    monkeypatch.setattr(adapter, "LocalDockerEngine", engine_factory)
    monkeypatch.setattr(adapter.secrets, "token_hex", lambda _size: next(nonces))
    return SimpleNamespace(
        authority=authority,
        adapter=adapter,
        materialization=materialization,
        runtime=runtime,
        resource=resource,
        parent_engine=parent_engine,
        image_id=image_id,
        installation=installation,
        plan=plan,
        events=events,
        engines=engines,
        receipts=receipts,
        evidence=evidence,
        revoked=revoked,
    )


def test_public_orchestrator_surface_is_closed(monkeypatch):
    wired = _wire(monkeypatch)
    assert tuple(inspect.signature(wired.adapter.execute_laya_runtime).parameters) == ("plan",)
    assert tuple(
        inspect.signature(wired.adapter.retry_laya_runtime_execution_cleanup).parameters
    ) == ("error",)


def test_success_orders_cleanup_receipt_seal_inside_image_lease(monkeypatch):
    wired = _wire(monkeypatch)
    result = wired.adapter.execute_laya_runtime(wired.plan)
    assert result is wired.evidence
    names = [event for event in wired.events if type(event) is str]
    assert names == [
        "revalidate",
        "lease-enter",
        "create",
        "inspect",
        "run",
        "cleanup",
        "receipt",
        "seal",
        "lease-exit",
    ]
    assert names.index("cleanup") < names.index("receipt") < names.index("seal")
    assert names.index("seal") < names.index("lease-exit")


def test_attempt_uses_exact_leased_image_but_never_parent_engine(monkeypatch):
    wired = _wire(monkeypatch)
    wired.adapter.execute_laya_runtime(wired.plan)
    assert len(wired.engines) == 1
    engine = wired.engines[0]
    assert engine is not wired.parent_engine
    assert engine.image_operations == []
    assert ("create-image", wired.image_id) in wired.events
    assert ("inspect-image", wired.image_id) in wired.events
    assert ("run-image", wired.image_id) in wired.events
    assert getattr(wired.parent_engine, "removed", []) == []


def test_each_attempt_constructs_a_fresh_engine_with_a_fresh_secret_nonce(monkeypatch):
    wired = _wire(monkeypatch)
    assert wired.adapter.execute_laya_runtime(wired.plan) is wired.evidence
    assert wired.adapter.execute_laya_runtime(wired.plan) is wired.evidence
    assert len(wired.engines) == 2
    assert wired.engines[0] is not wired.engines[1]
    assert wired.engines[0].nonce != wired.engines[1].nonce
    assert all(re.fullmatch(r"[0-9a-f]{64}", item.nonce) for item in wired.engines)


@pytest.mark.parametrize("invalid", [object(), "clone"])
def test_invalid_or_cloned_plan_fails_before_lease_or_engine(monkeypatch, invalid):
    wired = _wire(monkeypatch)
    if invalid == "clone":
        invalid = _clone_exact(wired.plan)
    with pytest.raises(ValueError):
        wired.adapter.execute_laya_runtime(invalid)
    assert "lease-enter" not in wired.events
    assert wired.engines == []
    assert "receipt" not in wired.events and "seal" not in wired.events


@pytest.mark.parametrize("boundary", ["create", "inspect", "run"])
def test_engine_boundary_failure_cleans_child_and_never_issues(monkeypatch, boundary):
    wired = _wire(monkeypatch, failure=boundary)
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError) as caught:
        wired.adapter.execute_laya_runtime(wired.plan)
    assert "cleanup" in wired.events
    assert "receipt" not in wired.events and "seal" not in wired.events
    assert wired.engines[0].child_owned is False
    assert wired.engines[0].image_operations == []
    _private_failure(caught.value, _PRIVATE_CANARY, wired.image_id, wired.installation)


def test_failed_execution_cleans_child_before_releasing_image_lease(monkeypatch):
    wired = _wire(monkeypatch, failure="run")
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError):
        wired.adapter.execute_laya_runtime(wired.plan)
    assert wired.events.index("run") < wired.events.index("cleanup")
    assert wired.events.index("cleanup") < wired.events.index("lease-exit")


def test_cleanup_failure_never_issues_and_returns_only_an_opaque_retry_handle(monkeypatch):
    wired = _wire(monkeypatch, cleanup_failures=1)
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError) as caught:
        wired.adapter.execute_laya_runtime(wired.plan)
    error = caught.value
    assert error.cleanup_pending is True
    assert "receipt" not in wired.events and "seal" not in wired.events
    assert wired.engines[0].image_operations == []
    _private_failure(error, _PRIVATE_CANARY, wired.image_id, wired.installation)


@pytest.mark.parametrize("boundary", ["receipt", "seal"])
def test_authority_boundary_failure_occurs_only_after_cleanup(monkeypatch, boundary):
    wired = _wire(
        monkeypatch,
        issue_failure=boundary == "receipt",
        seal_failure=boundary == "seal",
    )
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError):
        wired.adapter.execute_laya_runtime(wired.plan)
    assert wired.events.index("cleanup") < wired.events.index(boundary)
    assert wired.engines[0].child_owned is False
    assert ("seal" in wired.events) is (boundary == "seal")
    assert wired.engines[0].image_operations == []


def test_lease_exit_failure_revokes_partial_evidence_and_returns_none(monkeypatch):
    wired = _wire(monkeypatch, lease_exit_failure=True)
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError) as caught:
        wired.adapter.execute_laya_runtime(wired.plan)
    assert wired.events.index("seal") < wired.events.index("lease-exit")
    assert wired.revoked == [wired.evidence]
    assert caught.value.cleanup_pending is False


def test_retry_is_exact_idempotent_and_never_touches_parent_image(monkeypatch):
    wired = _wire(monkeypatch, cleanup_failures=1)
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError) as caught:
        wired.adapter.execute_laya_runtime(wired.plan)
    error = caught.value
    wired.adapter.retry_laya_runtime_execution_cleanup(error)
    wired.adapter.retry_laya_runtime_execution_cleanup(error)
    assert error.cleanup_pending is False
    assert wired.engines[0].child_owned is False
    assert wired.engines[0].image_operations == []
    assert getattr(wired.parent_engine, "removed", []) == []


def test_failed_retry_stays_pending_until_exact_cleanup_succeeds(monkeypatch):
    wired = _wire(monkeypatch, cleanup_failures=2)
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError) as caught:
        wired.adapter.execute_laya_runtime(wired.plan)
    error = caught.value
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError):
        wired.adapter.retry_laya_runtime_execution_cleanup(error)
    assert error.cleanup_pending is True
    wired.adapter.retry_laya_runtime_execution_cleanup(error)
    assert error.cleanup_pending is False


@pytest.mark.parametrize("forged", [ValueError("forged"), "copy"])
def test_forged_or_copied_cleanup_handle_has_no_authority(monkeypatch, forged):
    wired = _wire(monkeypatch, cleanup_failures=1)
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError) as caught:
        wired.adapter.execute_laya_runtime(wired.plan)
    if forged == "copy":
        forged = copy.copy(caught.value)
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError):
        wired.adapter.retry_laya_runtime_execution_cleanup(forged)
    assert caught.value.cleanup_pending is True


def test_pickled_error_cannot_transfer_cleanup_authority_or_private_state(monkeypatch):
    wired = _wire(monkeypatch, cleanup_failures=1)
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError) as caught:
        wired.adapter.execute_laya_runtime(wired.plan)
    encoded = pickle.dumps(caught.value)
    restored = pickle.loads(encoded)
    assert restored.cleanup_pending is False
    assert wired.image_id.encode() not in encoded
    assert wired.installation.encode() not in encoded
    assert _PRIVATE_CANARY.encode() not in encoded
    with pytest.raises(wired.adapter.DockerRuntimeExecutionError):
        wired.adapter.retry_laya_runtime_execution_cleanup(restored)


def test_success_has_no_cleanup_handle_and_no_child_left(monkeypatch):
    wired = _wire(monkeypatch)
    evidence = wired.adapter.execute_laya_runtime(wired.plan)
    assert evidence is wired.evidence
    assert wired.engines[0].child_owned is False
    assert wired.engines[0].image_operations == []
    assert wired.revoked == []


def test_receipt_identity_not_json_digest_or_clone_reaches_sealer(monkeypatch):
    wired = _wire(monkeypatch)
    wired.adapter.execute_laya_runtime(wired.plan)
    # The spy in _wire asserts object identity at seal time.  This explicit check
    # guards a future weakening where the adapter serializes the receipt first.
    assert len(wired.receipts) == 1
    assert type(wired.receipts[0]) is object
    assert wired.events.count("receipt") == 1
    assert wired.events.count("seal") == 1
