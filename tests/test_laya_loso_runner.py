"""RED contract for the blocked, gold-blind LOSO mechanical runner.

Only synthetic fixture records are used.  These tests do not authorize a real
corpus, choose a calibration algorithm, call a model, or elevate scientific
claims.
"""

from __future__ import annotations

import gc
import hashlib
import importlib
import inspect
import json
import re
import threading
import weakref
from collections import Counter
from dataclasses import dataclass

import pytest

from tests.test_laya_human_evaluation_preregistration import _inputs


def _module():
    return importlib.import_module("human_feedback.evaluation_runner")


def _protocol(tmp_path):
    from human_feedback import evaluation_preregistration, evaluation_run_protocol

    raw, corpus, plan, artifacts, _records = _inputs(tmp_path)
    preregistration = evaluation_preregistration.verify_human_evaluation_preregistration(
        raw,
        corpus=corpus,
        plan=plan,
        external_artifacts=artifacts,
    )
    return evaluation_run_protocol.prepare_human_loso_execution_protocol(preregistration)


@dataclass(frozen=True, slots=True)
class _FixtureGrant:
    events: list[tuple[str, object]]
    release_enabled: bool = True
    runtime_identity: object = object()
    model_identity: object = object()

    def authorize_outer_test(self, fold_index: int, calibration_receipts: tuple) -> object:
        self.events.append(("release", fold_index))
        if not self.release_enabled:
            raise ValueError("mechanical fixture release withheld")
        assert calibration_receipts
        return object()


class _FixturePort:
    def __init__(self, events, *, fail_comment: str | None = None) -> None:
        self.events = events
        self.fail_comment = fail_comment
        self.failed = False
        self.calls = []

    def predict(self, canonical_request: bytes) -> bytes:
        assert type(canonical_request) is bytes
        request = json.loads(canonical_request)
        assert set(request) == {"schema_version", "items"}
        assert request["schema_version"] == "laya-gold-blind-offline-request-v2"
        items = request["items"]
        assert items and all(set(item) == {"token", "comment"} for item in items)
        comments = tuple(item["comment"] for item in items)
        self.events.append(("predict", comments))
        self.calls.append(tuple((item["token"], item["comment"]) for item in items))
        if self.fail_comment in comments and not self.failed:
            self.failed = True
            raise ValueError("mechanical fixture transient failure")
        return json.dumps(
            {
                "schema_version": "laya-gold-blind-offline-response-v2",
                "predictions": [
                    {
                        "ordinal": ordinal,
                        "category": "data_quality",
                        "probabilities": {
                            "data_quality": 0.6,
                            "model_behavior": 0.1,
                            "agronomic_context": 0.1,
                            "usability": 0.1,
                            "other": 0.1,
                        },
                        "usage": {
                            "state_tokens": 32,
                            "state_tokens_dropped": 0,
                            "truncated": False,
                        },
                    }
                    for ordinal, _item in enumerate(items)
                ],
            },
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")


def _wire(module, monkeypatch, grant):
    monkeypatch.setattr(module, "_require_mechanical_fixture_authority", lambda _protocol: grant)


def _expected_events(protocol):
    events = []
    for fold_index, fold in enumerate(protocol._plan.folds):
        events.append(("predict", tuple(record.comment for record in fold.calibration_records)))
        events.append(("release", fold_index))
        events.append(("predict", tuple(record.comment for record in fold.test_records)))
    return events


def _assert_non_scientific(result) -> None:
    assert result.mechanical_execution_verified is True
    assert result.scientific_execution_completed is False
    assert result.calibration_fitted is False
    assert result.gold_blind_execution_attested is False
    assert result.scientifically_sufficient is False
    assert result.eligible_for_shadow_review is False
    assert result.production_enablement_authorized is False


def _private_failure(error: BaseException, *private_values: object) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    rendered = repr((error.args, str(error), repr(error)))
    for value in private_values:
        assert str(value) not in rendered


def test_public_preflight_is_blocked_before_protocol_or_port_consumption():
    module = _module()
    calls = []

    class UntouchableProtocol:
        def __getattribute__(self, _name):
            raise AssertionError("blocked preflight consumed protocol state")

    class ForbiddenPort:
        def predict(self, *_args, **_kwargs):
            calls.append("called")
            raise AssertionError("blocked preflight invoked inference")

    preflight = module.preflight_human_loso_runner(UntouchableProtocol(), ForbiddenPort())

    assert preflight.status == "BLOCKED_CORPUS_NOT_PROVIDED"
    assert preflight.ready is False
    assert preflight.comment_consumed is False
    assert preflight.inference_invoked is False
    assert calls == []
    assert tuple(inspect.signature(module.preflight_human_loso_runner).parameters) == (
        "protocol",
        "inference_port",
    )
    assert not any(
        token in inspect.signature(module.preflight_human_loso_runner).parameters
        for token in ("ready", "authorized", "fixture_grant", "bypass")
    )


def test_mechanical_fixture_orders_calibration_release_and_outer_test(monkeypatch, tmp_path):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    grant = _FixtureGrant(events)
    port = _FixturePort(events)
    _wire(module, monkeypatch, grant)

    result = module._run_human_loso_mechanical_fixture(protocol, port)

    assert events == _expected_events(protocol)
    assert sum(len(batch) for batch in port.calls) == sum(
        len(fold.calibration_records) + len(fold.test_records) for fold in protocol._plan.folds
    )
    _assert_non_scientific(result)
    assert "_run_human_loso_mechanical_fixture" not in module.__all__


def test_port_receives_only_opaque_token_and_comment_without_private_labels(monkeypatch, tmp_path):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    grant = _FixtureGrant(events)
    port = _FixturePort(events)
    _wire(module, monkeypatch, grant)

    result = module._run_human_loso_mechanical_fixture(protocol, port)

    records = protocol._corpus.records
    forbidden_values = {
        str(value)
        for record in records
        for value in (
            record.example_id,
            record.group_id,
            record.site_id,
            record.gold_category,
            record.annotations,
            record.adjudication,
        )
    }
    tokens = []
    for batch in port.calls:
        for token, comment in batch:
            assert type(comment) is str
            assert type(token) is str and re.fullmatch(r"[0-9a-f]{64}", token)
            assert all(value not in token for value in forbidden_values)
            tokens.append(token)
    assert len(tokens) == len(set(tokens))
    assert not hasattr(result, "rows")
    assert not hasattr(result, "predictions")
    _assert_non_scientific(result)


def test_missing_release_never_opens_outer_test_and_resume_does_not_replay_calibration(
    monkeypatch, tmp_path
):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    blocked_grant = _FixtureGrant(events, release_enabled=False)
    port = _FixturePort(events)
    _wire(module, monkeypatch, blocked_grant)
    first_fold = protocol._plan.folds[0]

    with pytest.raises(ValueError):
        module._run_human_loso_mechanical_fixture(protocol, port)
    assert [comments for kind, comments in events if kind == "predict"] == [
        tuple(record.comment for record in first_fold.calibration_records)
    ]
    assert not any(
        record.comment in comments
        for kind, comments in events
        if kind == "predict"
        for record in first_fold.test_records
    )

    events.clear()
    _wire(module, monkeypatch, _FixtureGrant(events))
    result = module._run_human_loso_mechanical_fixture(protocol, port)
    assert events[0] == ("release", 0)
    assert events == _expected_events(protocol)[1:]
    _assert_non_scientific(result)


def test_transient_prediction_failure_resumes_exactly_without_duplicate_receipts(
    monkeypatch, tmp_path
):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    grant = _FixtureGrant(events)
    failing_comment = protocol._plan.folds[0].calibration_records[1].comment
    port = _FixturePort(events, fail_comment=failing_comment)
    _wire(module, monkeypatch, grant)

    with pytest.raises(ValueError):
        module._run_human_loso_mechanical_fixture(protocol, port)
    result = module._run_human_loso_mechanical_fixture(protocol, port)

    observed = Counter(comment for batch in port.calls for _token, comment in batch)
    expected = Counter(
        record.comment
        for fold in protocol._plan.folds
        for record in fold.calibration_records + fold.test_records
    )
    failed_batch = protocol._plan.folds[0].calibration_records
    for comment, count in expected.items():
        attempts = 1 if any(record.comment == comment for record in failed_batch) else 0
        assert observed[comment] == count + attempts
    _assert_non_scientific(result)


def test_success_is_identity_stable_under_replay_and_concurrency(monkeypatch, tmp_path):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    grant = _FixtureGrant(events)
    port = _FixturePort(events)
    _wire(module, monkeypatch, grant)
    first = module._run_human_loso_mechanical_fixture(protocol, port)
    calls_after_first = tuple(port.calls)
    barrier = threading.Barrier(3)
    results = []

    def replay() -> None:
        barrier.wait(timeout=5)
        results.append(module._run_human_loso_mechanical_fixture(protocol, port))

    threads = [threading.Thread(target=replay, daemon=False) for _ in range(2)]
    for thread in threads:
        thread.start()
    try:
        barrier.wait(timeout=5)
    finally:
        for thread in threads:
            thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert results == [first, first]
    assert tuple(port.calls) == calls_after_first
    _assert_non_scientific(first)


def test_concurrent_initial_execution_is_single_flight(monkeypatch, tmp_path):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    grant = _FixtureGrant(events)

    class BlockingFirstPort(_FixturePort):
        def __init__(self, observed_events):
            super().__init__(observed_events)
            self.entered = threading.Event()
            self.duplicate_entered = threading.Event()
            self.release = threading.Event()
            self._calls_lock = threading.Lock()
            self._entries = 0

        def predict(self, canonical_request: bytes) -> bytes:
            with self._calls_lock:
                self._entries += 1
                entry = self._entries
            if entry == 1:
                self.entered.set()
                assert self.release.wait(timeout=5)
            else:
                self.duplicate_entered.set()
            return super().predict(canonical_request)

    port = BlockingFirstPort(events)
    _wire(module, monkeypatch, grant)
    start = threading.Barrier(3)
    results = []
    errors = []

    def execute() -> None:
        try:
            start.wait(timeout=5)
            results.append(module._run_human_loso_mechanical_fixture(protocol, port))
        except BaseException as error:  # pragma: no cover - asserted below
            errors.append(error)

    threads = [threading.Thread(target=execute, daemon=False) for _ in range(2)]
    for thread in threads:
        thread.start()
    start.wait(timeout=5)
    assert port.entered.wait(timeout=5)
    duplicate_before_release = port.duplicate_entered.wait(timeout=0.25)
    port.release.set()
    for thread in threads:
        thread.join(timeout=5)

    assert duplicate_before_release is False
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert len(results) == 2 and results[0] is results[1]
    assert events == _expected_events(protocol)


@pytest.mark.parametrize("changed_binding", ("port", "runtime", "model"))
def test_resume_rejects_changed_port_runtime_or_model_before_new_consumption(
    monkeypatch, tmp_path, changed_binding
):
    module = _module()
    case_path = tmp_path / changed_binding
    case_path.mkdir()
    protocol = _protocol(case_path)
    events = []
    runtime_identity = object()
    model_identity = object()
    grant = _FixtureGrant(
        events,
        runtime_identity=runtime_identity,
        model_identity=model_identity,
    )
    failing_comment = protocol._plan.folds[0].calibration_records[0].comment
    original_port = _FixturePort(events, fail_comment=failing_comment)
    _wire(module, monkeypatch, grant)

    with pytest.raises(ValueError):
        module._run_human_loso_mechanical_fixture(protocol, original_port)
    original_call_count = len(original_port.calls)
    candidate_port = original_port
    if changed_binding == "port":
        candidate_port = _FixturePort(events)
    elif changed_binding == "runtime":
        _wire(
            module,
            monkeypatch,
            _FixtureGrant(
                events,
                runtime_identity=object(),
                model_identity=model_identity,
            ),
        )
    else:
        _wire(
            module,
            monkeypatch,
            _FixtureGrant(
                events,
                runtime_identity=runtime_identity,
                model_identity=object(),
            ),
        )

    with pytest.raises(ValueError):
        module._run_human_loso_mechanical_fixture(protocol, candidate_port)
    assert len(original_port.calls) == original_call_count
    if candidate_port is not original_port:
        assert candidate_port.calls == []


def test_invalid_partial_response_does_not_release_and_retry_repeats_whole_batch(
    monkeypatch, tmp_path
):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    grant = _FixtureGrant(events)

    class PartialOncePort(_FixturePort):
        def __init__(self, observed_events):
            super().__init__(observed_events)
            self.invalid_once = True

        def predict(self, canonical_request: bytes) -> bytes:
            response = super().predict(canonical_request)
            if self.invalid_once:
                self.invalid_once = False
                decoded = json.loads(response)
                decoded["predictions"].pop()
                return json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
            return response

    port = PartialOncePort(events)
    _wire(module, monkeypatch, grant)
    first_calibration = tuple(
        record.comment for record in protocol._plan.folds[0].calibration_records
    )

    with pytest.raises(ValueError):
        module._run_human_loso_mechanical_fixture(protocol, port)
    assert events == [("predict", first_calibration)]

    result = module._run_human_loso_mechanical_fixture(protocol, port)
    assert events == [("predict", first_calibration), *_expected_events(protocol)]
    assert tuple(comment for _token, comment in port.calls[0]) == first_calibration
    assert tuple(comment for _token, comment in port.calls[1]) == first_calibration
    _assert_non_scientific(result)


def test_port_failure_does_not_expose_private_request_values(monkeypatch, tmp_path):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    _wire(
        module,
        monkeypatch,
        _FixtureGrant(
            events,
            runtime_identity="PRIVATE-RUNTIME-CANARY",
            model_identity="PRIVATE-MODEL-CANARY",
        ),
    )
    observed = {}

    class LeakingPort:
        def predict(self, canonical_request: bytes) -> bytes:
            item = json.loads(canonical_request)["items"][0]
            observed.update(item)
            raise RuntimeError(f"{item['token']}::{item['comment']}")

    with pytest.raises(ValueError) as caught:
        module._run_human_loso_mechanical_fixture(protocol, LeakingPort())

    _private_failure(
        caught.value,
        observed["token"],
        observed["comment"],
        "PRIVATE-RUNTIME-CANARY",
        "PRIVATE-MODEL-CANARY",
    )


def test_completed_protocol_state_is_weakly_released(monkeypatch, tmp_path):
    module = _module()
    protocol = _protocol(tmp_path)
    key = id(protocol)
    reference = weakref.ref(protocol)
    events = []
    _wire(module, monkeypatch, _FixtureGrant(events))

    module._run_human_loso_mechanical_fixture(protocol, _FixturePort(events))
    assert key in module._STATES
    del protocol
    gc.collect()

    assert reference() is None
    assert key not in module._STATES


def test_sealed_batches_preserve_private_canonical_outputs_without_reexecution(
    monkeypatch, tmp_path
):
    from human_feedback import loso_offline_adapter

    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    port = _FixturePort(events)
    grant = _FixtureGrant(events)
    _wire(module, monkeypatch, grant)

    result = module._run_human_loso_mechanical_fixture(protocol, port)
    calls_after_run = tuple(port.calls)
    receipts = module._sealed_human_loso_mechanical_batches(protocol)

    assert len(receipts) == 2 * len(protocol._plan.folds)
    for fold_index in range(len(protocol._plan.folds)):
        calibration, outer_test = receipts[2 * fold_index : 2 * fold_index + 2]
        assert (calibration.phase, calibration.fold_index) == ("calibration", fold_index)
        assert (outer_test.phase, outer_test.fold_index) == ("test", fold_index)
    for receipt in receipts:
        assert type(receipt.canonical_response) is bytes
        assert hashlib.sha256(receipt.canonical_response).hexdigest() == receipt.response_sha256
        assert (
            loso_offline_adapter.validate_laya_loso_offline_response(
                receipt.canonical_response,
                expected_count=receipt.item_count,
            )
            == receipt.canonical_response
        )
        assert receipt.runtime_identity is grant.runtime_identity
        assert receipt.model_identity is grant.model_identity
        assert receipt.inference_port is port

    assert module._run_human_loso_mechanical_fixture(protocol, port) is result
    assert module._sealed_human_loso_mechanical_batches(protocol) == receipts
    assert tuple(port.calls) == calls_after_run


def test_sealed_batch_getter_rejects_mutated_bytes_or_commitment_privately(monkeypatch, tmp_path):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    port = _FixturePort(events)
    _wire(module, monkeypatch, _FixtureGrant(events))
    module._run_human_loso_mechanical_fixture(protocol, port)
    receipt = module._sealed_human_loso_mechanical_batches(protocol)[0]
    private_comment = protocol._plan.folds[0].calibration_records[0].comment

    mutations = (
        ("canonical_response", receipt.canonical_response + b" "),
        ("response_sha256", "0" * 64),
    )
    for name, invalid in mutations:
        original = getattr(receipt, name)
        object.__setattr__(receipt, name, invalid)
        try:
            with pytest.raises((TypeError, ValueError)) as caught:
                module._sealed_human_loso_mechanical_batches(protocol)
            _private_failure(caught.value, private_comment, invalid)
        finally:
            object.__setattr__(receipt, name, original)


def test_waiter_revalidates_protocol_after_owner_failure_before_new_consumption(
    monkeypatch, tmp_path
):
    module = _module()
    protocol = _protocol(tmp_path)
    events = []
    grant = _FixtureGrant(events)
    _wire(module, monkeypatch, grant)
    owner_entered = threading.Event()
    release_owner = threading.Event()

    class FailFirstOwnerPort(_FixturePort):
        def __init__(self, observed_events):
            super().__init__(observed_events)
            self.attempts = 0

        def predict(self, canonical_request: bytes) -> bytes:
            self.attempts += 1
            response = super().predict(canonical_request)
            if self.attempts == 1:
                owner_entered.set()
                assert release_owner.wait(timeout=5)
                raise RuntimeError("PRIVATE-OWNER-FAILURE")
            return response

    port = FailFirstOwnerPort(events)
    results = []
    errors = []

    def execute() -> None:
        try:
            results.append(module._run_human_loso_mechanical_fixture(protocol, port))
        except BaseException as error:  # pragma: no cover - asserted below
            errors.append(error)

    owner = threading.Thread(target=execute, daemon=False)
    owner.start()
    assert owner_entered.wait(timeout=5)
    state = module._STATES[id(protocol)]
    waiter_inside_condition = threading.Event()
    original_wait = state.condition.wait

    def observed_wait(timeout=None):
        waiter_inside_condition.set()
        return original_wait(timeout)

    monkeypatch.setattr(state.condition, "wait", observed_wait)
    waiter = threading.Thread(target=execute, daemon=False)
    waiter.start()
    assert waiter_inside_condition.wait(timeout=5)

    record = protocol._plan.folds[0].calibration_records[0]
    original_comment = record.comment
    private_canary = "PRIVATE-WAITER-MUTATION-CANARY"
    object.__setattr__(record, "comment", private_canary)
    try:
        release_owner.set()
        owner.join(timeout=5)
        waiter.join(timeout=5)
        assert not owner.is_alive() and not waiter.is_alive()
        assert results == []
        assert len(errors) == 2
        assert port.attempts == 1
        assert all(
            private_canary not in comment for batch in port.calls for _token, comment in batch
        )
        for error in errors:
            _private_failure(error, private_canary, "PRIVATE-OWNER-FAILURE")
    finally:
        object.__setattr__(record, "comment", original_comment)
        release_owner.set()
