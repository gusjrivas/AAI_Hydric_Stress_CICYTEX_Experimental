"""RED contract for the blocked, gold-blind LOSO mechanical runner.

Only synthetic fixture records are used.  These tests do not authorize a real
corpus, choose a calibration algorithm, call a model, or elevate scientific
claims.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import threading
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
    assert not any(
        record.comment in comments
        for kind, comments in events
        if kind == "predict"
        for record in first_fold.calibration_records
    )
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
