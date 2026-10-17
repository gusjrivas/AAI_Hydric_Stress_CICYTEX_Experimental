"""RED authority and privacy boundary for mechanical statistical fixtures.

These tests use only synthetic fixture authorities.  They do not admit a real
corpus, baseline producer, analysis profile, calibration method, latency input,
scientific result, shadow review, or production enablement.
"""

from __future__ import annotations

import copy
import importlib
import inspect

import pytest

from tests.test_laya_loso_runner import (
    _FixtureGrant,
    _FixturePort,
    _protocol,
    _wire,
)


def _module():
    return importlib.import_module("human_feedback.evaluation_statistics")


def _executed_protocol(monkeypatch, tmp_path):
    runner = importlib.import_module("human_feedback.evaluation_runner")
    protocol = _protocol(tmp_path)
    events = []
    _wire(runner, monkeypatch, _FixtureGrant(events))
    port = _FixturePort(events)
    runner._run_human_loso_mechanical_fixture(protocol, port)
    receipts = runner._sealed_human_loso_mechanical_batches(protocol)
    return runner, protocol, receipts


def _authorize(module, monkeypatch):
    monkeypatch.setattr(
        module,
        "_require_mechanical_statistics_fixture_authority",
        lambda _protocol: module._FIXTURE_AUTHORIZED,
    )


def _assert_private_failure(error: BaseException, *private_values: object) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    rendered = repr((error.args, str(error), repr(error)))
    for value in private_values:
        assert str(value) not in rendered


def _assert_no_scientific_claims(value) -> None:
    assert value.scientific_execution_completed is False
    assert value.calibration_fitted is False
    assert value.scientifically_sufficient is False
    assert value.eligible_for_shadow_review is False
    assert value.production_enablement_authorized is False


def test_public_preflight_is_closed_blocked_and_consumes_nothing(monkeypatch):
    module = _module()
    calls = []

    class UntouchableProtocol:
        def __getattribute__(self, _name):
            raise AssertionError("blocked preflight consumed protocol state")

    def forbidden_sealed_batches(_protocol):
        calls.append("receipts")
        raise AssertionError("blocked preflight consumed private receipts")

    class ForbiddenBaseline:
        def __init__(self, *_args, **_kwargs):
            calls.append("baseline")
            raise AssertionError("blocked preflight invoked fixture baseline")

    runner = importlib.import_module("human_feedback.evaluation_runner")
    monkeypatch.setattr(runner, "_sealed_human_loso_mechanical_batches", forbidden_sealed_batches)
    monkeypatch.setattr(module, "DeterministicRuleBaseline", ForbiddenBaseline)

    result = module.preflight_laya_mechanical_statistics(UntouchableProtocol())

    assert tuple(module.__all__) == (
        "MechanicalStatisticsPreflight",
        "preflight_laya_mechanical_statistics",
    )
    assert tuple(inspect.signature(module.preflight_laya_mechanical_statistics).parameters) == (
        "protocol",
    )
    assert result.schema_version == "laya-mechanical-statistics-preflight-v1"
    assert result.status == "BLOCKED_EXTERNAL_SCIENTIFIC_ADMISSIONS"
    assert result.missing_requirements == (
        "real_corpus_and_custody_admission",
        "real_baseline_producer_admission",
        "real_analysis_profile_admission",
        "calibration_evidence",
        "latency_inputs",
    )
    assert result.ready is False
    assert result.private_rows_consumed is False
    assert result.fixture_baseline_invoked is False
    _assert_no_scientific_claims(result)
    assert calls == []


def test_private_fixture_authority_defaults_to_failure_before_consumption(monkeypatch):
    module = _module()
    calls = []

    class UntouchableProtocol:
        def __getattribute__(self, _name):
            calls.append("protocol")
            raise AssertionError("default-deny fixture touched protocol")

    with pytest.raises(ValueError) as caught:
        module._run_laya_mechanical_statistics_fixture(UntouchableProtocol())

    _assert_private_failure(caught.value)
    assert calls == []
    assert "_run_laya_mechanical_statistics_fixture" not in module.__all__
    assert "_require_issued_mechanical_statistics" not in module.__all__


def test_fixture_consumes_exact_sealed_batches_but_baseline_only_outer_test(monkeypatch, tmp_path):
    from human_feedback.offline_readiness import BaselineSuggestion

    runner, protocol, receipts = _executed_protocol(monkeypatch, tmp_path)
    module = _module()
    _authorize(module, monkeypatch)
    calls = []

    class ObservedBaseline:
        def classify(self, site_id, comment):
            calls.append((site_id, comment))
            return BaselineSuggestion(
                category="other",
                probabilities=(
                    ("data_quality", 0.1),
                    ("model_behavior", 0.1),
                    ("agronomic_context", 0.1),
                    ("usability", 0.1),
                    ("other", 0.6),
                ),
                abstained=False,
            )

    monkeypatch.setattr(module, "DeterministicRuleBaseline", ObservedBaseline)
    evidence = module._run_laya_mechanical_statistics_fixture(protocol)

    expected_outer = [
        (record.site_id, record.comment)
        for fold in protocol._plan.folds
        for record in fold.test_records
    ]
    assert calls == expected_outer
    assert evidence._protocol is protocol
    assert tuple(item is expected for item, expected in zip(evidence._receipts, receipts)) == (
        True,
    ) * len(receipts)
    assert module._require_issued_mechanical_statistics(evidence) is evidence
    assert evidence.schema_version == "laya-mechanical-statistics-v1"
    assert evidence.status == "MECHANICAL_FIXTURE_ONLY_BLOCKED"
    assert evidence.fixture_profile_id == "python-mt19937-randrange-nearest-rank-v1"
    assert evidence.baseline_fixture_id == "deterministic-rule-baseline-v1-mechanical-fixture"
    assert evidence.mechanical_fixture_calculated is True
    assert type(evidence.mechanical_holm_all_rejected) is bool
    _assert_no_scientific_claims(evidence)
    assert runner._sealed_human_loso_mechanical_batches(protocol) == receipts


def test_availability_is_explicit_and_missing_measurements_are_never_synthesized(
    monkeypatch, tmp_path
):
    _runner, protocol, _receipts = _executed_protocol(monkeypatch, tmp_path)
    module = _module()
    _authorize(module, monkeypatch)
    evidence = module._run_laya_mechanical_statistics_fixture(protocol)
    availability = evidence.availability

    assert availability.raw_metrics == "AVAILABLE_MECHANICAL_FIXTURE"
    assert (
        availability.legacy_policy_diagnostics
        == "AVAILABLE_UNCALIBRATED_SELECTED_PROBABILITY_FALLBACK"
    )
    assert availability.calibrated_metrics == "UNAVAILABLE_CALIBRATION_NOT_FITTED"
    assert availability.latency == "UNAVAILABLE_INPUT_NOT_CAPTURED"
    assert availability.p50_latency_ms is None
    assert availability.p95_latency_ms is None
    assert availability.real_baseline == "UNAVAILABLE_EXTERNAL_ADMISSION_REQUIRED"
    assert availability.real_analysis_profile == "UNAVAILABLE_EXTERNAL_ADMISSION_REQUIRED"
    assert availability.scientific_verdict == "BLOCKED"
    for name in ("raw_laya", "raw_baseline", "policy_laya", "policy_baseline"):
        assert getattr(evidence, name) is not None
    assert evidence.raw_by_site is not None
    assert evidence.policy_by_site is not None
    assert evidence.bootstrap is not None
    assert evidence.holm is not None
    _assert_no_scientific_claims(evidence)


def test_evidence_is_private_exact_and_rejects_clone_or_receipt_tamper(monkeypatch, tmp_path):
    _runner, protocol, receipts = _executed_protocol(monkeypatch, tmp_path)
    module = _module()
    _authorize(module, monkeypatch)
    evidence = module._run_laya_mechanical_statistics_fixture(protocol)
    clone = copy.copy(evidence)

    with pytest.raises(ValueError) as cloned:
        module._require_issued_mechanical_statistics(clone)
    _assert_private_failure(cloned.value)

    private_values = tuple(
        value
        for fold in protocol._plan.folds
        for record in fold.calibration_records + fold.test_records
        for value in (
            record.comment,
            record.example_id,
            record.group_id,
            record.gold_category,
        )
    )
    rendered = repr(evidence)
    assert not hasattr(evidence, "rows")
    assert not hasattr(evidence, "predictions")
    assert not hasattr(evidence, "comments")
    assert not hasattr(evidence, "gold_labels")
    assert all(str(value) not in rendered for value in private_values)

    original = receipts[-1].response_sha256
    object.__setattr__(receipts[-1], "response_sha256", "0" * 64)
    try:
        with pytest.raises(ValueError) as tampered:
            module._require_issued_mechanical_statistics(evidence)
        _assert_private_failure(tampered.value, original, *private_values)
    finally:
        object.__setattr__(receipts[-1], "response_sha256", original)


def test_cloned_protocol_never_invokes_fixture_baseline(monkeypatch, tmp_path):
    protocol = _protocol(tmp_path)
    module = _module()
    _authorize(module, monkeypatch)
    calls = []

    class ForbiddenBaseline:
        def __init__(self):
            calls.append("baseline")

    monkeypatch.setattr(module, "DeterministicRuleBaseline", ForbiddenBaseline)
    clone = copy.copy(protocol)

    with pytest.raises(ValueError) as caught:
        module._run_laya_mechanical_statistics_fixture(clone)

    _assert_private_failure(caught.value)
    assert calls == []


def test_issued_evidence_snapshot_rejects_nested_aggregate_and_profile_tamper(
    monkeypatch, tmp_path
):
    _runner, protocol, _receipts = _executed_protocol(monkeypatch, tmp_path)
    module = _module()
    _authorize(module, monkeypatch)
    evidence = module._run_laya_mechanical_statistics_fixture(protocol)

    mutations = (
        (evidence.raw_laya, "macro_f1", 1.25),
        (evidence.raw_by_site[0].laya, "accuracy", 1.25),
        (evidence.policy_laya, "mean_cost", -1.0),
        (evidence.bootstrap[0], "tail_probability", 1.25),
        (evidence.holm[0], "rejected", not evidence.holm[0].rejected),
        (evidence.availability, "scientific_verdict", "FORGED_READY"),
        (evidence, "fixture_profile_id", "forged-profile"),
    )
    for target, field, forged in mutations:
        original = getattr(target, field)
        object.__setattr__(target, field, forged)
        try:
            with pytest.raises(ValueError) as caught:
                module._require_issued_mechanical_statistics(evidence)
            _assert_private_failure(caught.value, forged)
        finally:
            object.__setattr__(target, field, original)
        assert module._require_issued_mechanical_statistics(evidence) is evidence
