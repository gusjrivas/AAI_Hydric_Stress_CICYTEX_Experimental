"""RED terminal authority and privacy boundary for Laya readiness governance.

Only already-issued synthetic PR43 fixture statistics are consumed.  These tests
do not admit a corpus, baseline, analysis profile, calibration, latency, shadow
review, scientific sufficiency, or production enablement.
"""

from __future__ import annotations

import copy
import importlib
import inspect
import json

import pytest

from tests.test_laya_statistics_boundary import _authorize, _executed_protocol

_PREREQUISITES = (
    ("statistics_evidence", "FIXTURE_ONLY"),
    ("real_corpus_custody", "UNAVAILABLE"),
    ("real_baseline", "UNAVAILABLE"),
    ("real_analysis_profile", "UNAVAILABLE"),
    ("output_stage_calibration", "UNAVAILABLE"),
)
_CRITERIA = (
    "minimum_coverage",
    "minimum_accuracy",
    "minimum_selective_accuracy",
    "minimum_macro_f1",
    "maximum_brier",
    "maximum_raw_ece_diagnostic",
    "maximum_mean_cost",
    "minimum_site_macro_f1",
    "maximum_p95_latency_ms",
    "holm_all_four_rejected",
)
_REASONS = (
    "fixture_statistics_only",
    "real_corpus_custody_unavailable",
    "real_baseline_unavailable",
    "real_analysis_profile_unavailable",
    "output_stage_calibration_unavailable",
    "per_example_latency_unavailable",
    "raw_ece_not_calibrated_policy_ece",
    "scientific_criteria_not_evaluated",
)
_CLAIMS = (
    ("mechanical_diagnostics_evaluated", True),
    ("scientific_evaluation_completed", False),
    ("scientifically_sufficient", False),
    ("eligible_for_independent_shadow_review", False),
    ("production_enablement_authorized", False),
)


def _module():
    return importlib.import_module("human_feedback.evaluation_readiness")


def _issued_statistics(monkeypatch, tmp_path):
    _runner, protocol, _receipts = _executed_protocol(monkeypatch, tmp_path)
    statistics = importlib.import_module("human_feedback.evaluation_statistics")
    _authorize(statistics, monkeypatch)
    evidence = statistics._run_laya_mechanical_statistics_fixture(protocol)
    return statistics, protocol, evidence


def _private_failure(error: BaseException, *private_values: object) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    rendered = repr((error.args, str(error), repr(error)))
    for value in private_values:
        assert str(value) not in rendered


def test_public_surface_accepts_only_one_exact_statistics_parent(monkeypatch, tmp_path):
    _statistics, _protocol, evidence = _issued_statistics(monkeypatch, tmp_path)
    module = _module()

    assert tuple(module.__all__) == (
        "LayaReadinessReport",
        "evaluate_laya_readiness",
        "canonical_laya_readiness_report_bytes",
    )
    assert tuple(inspect.signature(module.evaluate_laya_readiness).parameters) == ("statistics",)
    assert tuple(inspect.signature(module.canonical_laya_readiness_report_bytes).parameters) == (
        "report",
    )
    assert not {
        "override",
        "ready",
        "authorized",
        "thresholds",
        "fixture_grant",
        "bypass",
    }.intersection(inspect.signature(module.evaluate_laya_readiness).parameters)

    report = module.evaluate_laya_readiness(evidence)
    assert module._require_issued_laya_readiness_report(report) is report


def test_fixture_report_is_complete_but_scientifically_blocked(monkeypatch, tmp_path):
    _statistics, _protocol, evidence = _issued_statistics(monkeypatch, tmp_path)
    module = _module()
    report = module.evaluate_laya_readiness(evidence)

    assert report.schema_version == "laya-readiness-report-v1"
    assert report.decision == "BLOCKED"
    assert report.policy_id == "laya-readiness-policy-v1"
    assert report.fixture_profile_id == evidence.fixture_profile_id
    assert report.prerequisites == _PREREQUISITES
    assert tuple(name for name, _scientific, _mechanical in report.criteria) == _CRITERIA
    assert all(scientific == "NOT_EVALUATED" for _name, scientific, _mechanical in report.criteria)
    mechanical = dict((name, state) for name, _scientific, state in report.criteria)
    assert set(mechanical.values()) <= {"PASS", "FAIL", "NOT_EVALUATED"}
    assert mechanical["maximum_p95_latency_ms"] == "NOT_EVALUATED"
    assert report.reason_codes == _REASONS
    assert report.claims == _CLAIMS
    assert dict(report.claims)["production_enablement_authorized"] is False


def test_evaluation_revalidates_parent_and_performs_no_extra_execution(monkeypatch, tmp_path):
    statistics, _protocol, evidence = _issued_statistics(monkeypatch, tmp_path)
    module = _module()
    calls = []
    real_require = statistics._require_issued_mechanical_statistics

    def observed_require(value):
        calls.append(value)
        return real_require(value)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("readiness repeated statistics, inference, baseline, or fitting")

    monkeypatch.setattr(statistics, "_require_issued_mechanical_statistics", observed_require)
    monkeypatch.setattr(statistics, "_paired_group_bootstrap", forbidden)
    monkeypatch.setattr(statistics, "_holm_step_down", forbidden)
    monkeypatch.setattr(statistics, "DeterministicRuleBaseline", forbidden)
    report = module.evaluate_laya_readiness(evidence)

    assert len(calls) >= 2
    assert all(value is evidence for value in calls)
    assert report.decision == "BLOCKED"


def test_canonical_report_is_closed_deterministic_and_private(monkeypatch, tmp_path):
    _statistics, protocol, evidence = _issued_statistics(monkeypatch, tmp_path)
    module = _module()
    report = module.evaluate_laya_readiness(evidence)
    payload = module.canonical_laya_readiness_report_bytes(report)
    decoded = json.loads(payload)

    assert payload == json.dumps(
        decoded,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert set(decoded) == {
        "schema_version",
        "decision",
        "policy_id",
        "fixture_profile_id",
        "prerequisites",
        "criteria",
        "reason_codes",
        "claims",
    }
    forbidden_names = {
        "metrics",
        "probabilities",
        "digests",
        "rows",
        "predictions",
        "receipts",
        "protocol",
    }
    assert forbidden_names.isdisjoint(decoded)
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
    assert all(str(value).encode("utf-8") not in payload for value in private_values)
    assert all(str(value) not in repr(report) for value in private_values)


def test_terminal_authority_rejects_clone_tamper_types_and_parent_mutation(monkeypatch, tmp_path):
    _statistics, _protocol, evidence = _issued_statistics(monkeypatch, tmp_path)
    module = _module()
    report = module.evaluate_laya_readiness(evidence)

    with pytest.raises(ValueError) as cloned:
        module._require_issued_laya_readiness_report(copy.copy(report))
    _private_failure(cloned.value)

    mutations = (
        (report, "decision", "PASS"),
        (
            report,
            "claims",
            tuple(
                (name, 0 if name == "production_enablement_authorized" else value)
                for name, value in report.claims
            ),
        ),
        (report, "fixture_profile_id", "forged-profile"),
    )
    for target, field, forged in mutations:
        original = getattr(target, field)
        object.__setattr__(target, field, forged)
        try:
            with pytest.raises(ValueError) as tampered:
                module.canonical_laya_readiness_report_bytes(report)
            _private_failure(tampered.value, forged)
        finally:
            object.__setattr__(target, field, original)
        assert module._require_issued_laya_readiness_report(report) is report

    original_metric = evidence.raw_laya.macro_f1
    object.__setattr__(evidence.raw_laya, "macro_f1", 1.25)
    try:
        with pytest.raises(ValueError) as parent_tampered:
            module.canonical_laya_readiness_report_bytes(report)
        _private_failure(parent_tampered.value, original_metric)
    finally:
        object.__setattr__(evidence.raw_laya, "macro_f1", original_metric)


def test_evaluate_and_summary_recheck_after_parent_validation(monkeypatch, tmp_path):
    statistics, _protocol, evidence = _issued_statistics(monkeypatch, tmp_path)
    module = _module()
    real_require = statistics._require_issued_mechanical_statistics
    calls = []
    original_statistics_profile = evidence.fixture_profile_id

    def mutate_statistics_after_first_validation(value):
        result = real_require(value)
        calls.append(value)
        if len(calls) == 1:
            object.__setattr__(value, "fixture_profile_id", "forged-during-evaluate")
        return result

    monkeypatch.setattr(
        statistics,
        "_require_issued_mechanical_statistics",
        mutate_statistics_after_first_validation,
    )
    try:
        with pytest.raises(ValueError) as evaluate_failed:
            module.evaluate_laya_readiness(evidence)
        _private_failure(evaluate_failed.value, "forged-during-evaluate")
    finally:
        object.__setattr__(evidence, "fixture_profile_id", original_statistics_profile)

    monkeypatch.setattr(statistics, "_require_issued_mechanical_statistics", real_require)
    report = module.evaluate_laya_readiness(evidence)
    report_profile = report.fixture_profile_id

    def mutate_report_during_parent_validation(value):
        result = real_require(value)
        object.__setattr__(report, "fixture_profile_id", "forged-during-summary")
        return result

    monkeypatch.setattr(
        statistics,
        "_require_issued_mechanical_statistics",
        mutate_report_during_parent_validation,
    )
    try:
        with pytest.raises(ValueError) as summary_failed:
            module.canonical_laya_readiness_report_bytes(report)
        _private_failure(summary_failed.value, "forged-during-summary")
    finally:
        object.__setattr__(report, "fixture_profile_id", report_profile)


def test_report_rejects_equal_string_subclasses_before_private_serialization(monkeypatch, tmp_path):
    _statistics, _protocol, evidence = _issued_statistics(monkeypatch, tmp_path)
    module = _module()
    report = module.evaluate_laya_readiness(evidence)

    class EqualPrivateString(str):
        def __eq__(self, _other):
            return True

        __hash__ = str.__hash__

    private_reason = EqualPrivateString("PRIVATE-READINESS-REASON-CANARY")
    private_claim = EqualPrivateString("PRIVATE-READINESS-CLAIM-CANARY")
    mutations = (
        (
            "reason_codes",
            (private_reason, *report.reason_codes[1:]),
            str(private_reason),
        ),
        (
            "claims",
            ((private_claim, report.claims[0][1]), *report.claims[1:]),
            str(private_claim),
        ),
    )
    for field, forged, canary in mutations:
        original = getattr(report, field)
        object.__setattr__(report, field, forged)
        try:
            with pytest.raises(ValueError) as caught:
                module.canonical_laya_readiness_report_bytes(report)
            _private_failure(caught.value, canary)
        finally:
            object.__setattr__(report, field, original)
        assert module._require_issued_laya_readiness_report(report) is report
