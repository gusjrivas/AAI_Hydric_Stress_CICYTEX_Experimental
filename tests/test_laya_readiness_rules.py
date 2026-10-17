from __future__ import annotations

import inspect
import math
from dataclasses import replace

import pytest

from human_feedback.evaluation_corpus import REQUIRED_SITES
from human_feedback.evaluation_readiness import (
    _Criterion,
    _decide_readiness,
    _evaluate_mechanical_readiness_criteria,
    _Prerequisite,
)
from human_feedback.evaluation_statistics import (
    _Availability,
    _BootstrapSummary,
    _HolmDecision,
    _MechanicalStatisticsEvidence,
    _PolicyDiagnostics,
    _RawMetrics,
    _SiteMetricPair,
)

PREREQUISITES = (
    "statistics_evidence",
    "real_corpus_custody",
    "real_baseline",
    "real_analysis_profile",
    "output_stage_calibration",
)
CRITERIA = (
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
HYPOTHESES = (
    "global_equal_site_macro_f1_superiority",
    "cicytex_macro_f1_noninferiority",
    "melchor-romero_macro_f1_noninferiority",
    "pergamino_macro_f1_noninferiority",
)


def _prerequisites(state: str = "VERIFIED") -> tuple[_Prerequisite, ...]:
    return tuple(_Prerequisite(name, state) for name in PREREQUISITES)


def _criteria(
    scientific_state: str = "PASS",
    mechanical_state: str = "PASS",
) -> tuple[_Criterion, ...]:
    return tuple(_Criterion(name, scientific_state, mechanical_state) for name in CRITERIA)


def _raw(*, brier: float = 0.6, ece: float = 0.1) -> _RawMetrics:
    return _RawMetrics(total=30, accuracy=0.7, macro_f1=0.65, brier=brier, ece=ece)


def _policy(
    *,
    coverage: float = 0.6,
    accuracy: float = 0.7,
    selective_accuracy: float = 0.8,
    macro_f1: float = 0.65,
    mean_cost: float = 1.0,
) -> _PolicyDiagnostics:
    return _PolicyDiagnostics(
        total=30,
        coverage=coverage,
        selective_accuracy=selective_accuracy,
        accuracy=accuracy,
        macro_f1=macro_f1,
        mean_cost=mean_cost,
    )


def _statistics(
    *,
    raw_laya: _RawMetrics | None = None,
    policy_laya: _PolicyDiagnostics | None = None,
    policy_by_site: tuple[_SiteMetricPair, ...] | None = None,
    holm: tuple[_HolmDecision, ...] | None = None,
    holm_all: bool = True,
    availability: _Availability | None = None,
) -> _MechanicalStatisticsEvidence:
    raw_laya = _raw() if raw_laya is None else raw_laya
    raw_baseline = _RawMetrics(30, 0.5, 0.5, 0.8, 0.2)
    policy_laya = _policy() if policy_laya is None else policy_laya
    policy_baseline = _PolicyDiagnostics(30, 0.5, 0.5, 0.5, 0.5, 1.5)
    raw_by_site = tuple(_SiteMetricPair(site, raw_laya, raw_baseline) for site in REQUIRED_SITES)
    if policy_by_site is None:
        site_policy = _policy(macro_f1=0.55)
        policy_by_site = tuple(
            _SiteMetricPair(site, site_policy, policy_baseline) for site in REQUIRED_SITES
        )
    bootstrap = tuple(_BootstrapSummary(name, 0.1, -0.1, 0.2, 0.01, 10_000) for name in HYPOTHESES)
    if holm is None:
        holm = tuple(
            _HolmDecision(name, 0.01, 0.05 / (4 - index), True)
            for index, name in enumerate(HYPOTHESES)
        )
    return _MechanicalStatisticsEvidence(
        raw_laya=raw_laya,
        raw_baseline=raw_baseline,
        raw_by_site=raw_by_site,
        policy_laya=policy_laya,
        policy_baseline=policy_baseline,
        policy_by_site=policy_by_site,
        bootstrap=bootstrap,
        holm=holm,
        mechanical_holm_all_rejected=holm_all,
        _protocol=object(),
        _receipts=(),
        availability=_Availability() if availability is None else availability,
    )


@pytest.mark.parametrize(
    ("prerequisites", "criteria", "expected"),
    (
        (_prerequisites(), _criteria(), "PASS"),
        (
            tuple(
                _Prerequisite(name, "UNAVAILABLE" if index == 1 else "VERIFIED")
                for index, name in enumerate(PREREQUISITES)
            ),
            tuple(
                _Criterion(name, "FAIL" if index == 0 else "PASS", "FAIL" if index == 0 else "PASS")
                for index, name in enumerate(CRITERIA)
            ),
            "FAIL",
        ),
        (
            tuple(
                _Prerequisite(name, "UNAVAILABLE" if index == 1 else "VERIFIED")
                for index, name in enumerate(PREREQUISITES)
            ),
            _criteria(),
            "BLOCKED",
        ),
        (
            tuple(
                _Prerequisite(
                    name,
                    "FIXTURE_ONLY" if index == 0 else "UNAVAILABLE",
                )
                for index, name in enumerate(PREREQUISITES)
            ),
            tuple(
                _Criterion(
                    name,
                    "NOT_EVALUATED",
                    "FAIL" if index == 0 else "PASS",
                )
                for index, name in enumerate(CRITERIA)
            ),
            "BLOCKED",
        ),
        (
            _prerequisites(),
            tuple(
                _Criterion(
                    name,
                    "NOT_EVALUATED" if index == 0 else "PASS",
                    "PASS",
                )
                for index, name in enumerate(CRITERIA)
            ),
            "BLOCKED",
        ),
    ),
)
def test_complete_decision_table_distinguishes_pass_fail_blocked(
    prerequisites, criteria, expected
) -> None:
    assert _decide_readiness(prerequisites, criteria) == expected


def test_decision_rejects_empty_partial_duplicate_reordered_or_non_tuple_inputs() -> None:
    complete_prerequisites = _prerequisites()
    complete_criteria = _criteria()
    invalid = (
        ((), complete_criteria),
        (complete_prerequisites, ()),
        (list(complete_prerequisites), complete_criteria),
        (complete_prerequisites, list(complete_criteria)),
        (complete_prerequisites[:-1], complete_criteria),
        (complete_prerequisites, complete_criteria[:-1]),
        (tuple(reversed(complete_prerequisites)), complete_criteria),
        (complete_prerequisites, tuple(reversed(complete_criteria))),
        (
            (*complete_prerequisites[:-1], complete_prerequisites[0]),
            complete_criteria,
        ),
        (
            complete_prerequisites,
            (*complete_criteria[:-1], complete_criteria[0]),
        ),
    )
    for prerequisites, criteria in invalid:
        with pytest.raises(ValueError):
            _decide_readiness(prerequisites, criteria)


@pytest.mark.parametrize(
    ("scientific", "mechanical"),
    (
        ("PASS", "FAIL"),
        ("FAIL", "PASS"),
        ("PASS", "NOT_EVALUATED"),
        ("FAIL", "NOT_EVALUATED"),
    ),
)
def test_decision_rejects_contradictory_authoritative_and_mechanical_states(
    scientific, mechanical
) -> None:
    criteria = list(_criteria())
    criteria[0] = _Criterion(CRITERIA[0], scientific, mechanical)
    with pytest.raises(ValueError):
        _decide_readiness(_prerequisites(), tuple(criteria))


@pytest.mark.parametrize(
    "constructor",
    (
        lambda: _Prerequisite("foreign", "VERIFIED"),
        lambda: _Prerequisite(PREREQUISITES[0], "PASS"),
        lambda: _Criterion("foreign", "PASS", "PASS"),
        lambda: _Criterion(CRITERIA[0], "VERIFIED", "PASS"),
        lambda: _Criterion(CRITERIA[0], "PASS", True),
    ),
)
def test_state_objects_reject_open_names_states_and_boolean_confusion(constructor) -> None:
    with pytest.raises(ValueError):
        constructor()


def test_mechanical_diagnostics_use_frozen_inclusive_thresholds_and_no_overrides() -> None:
    signature = inspect.signature(_evaluate_mechanical_readiness_criteria)
    assert tuple(signature.parameters) == ("statistics",)

    criteria = _evaluate_mechanical_readiness_criteria(_statistics())

    assert tuple(item.name for item in criteria) == CRITERIA
    assert tuple(item.scientific_state for item in criteria) == ("NOT_EVALUATED",) * 10
    assert tuple(item.mechanical_state for item in criteria) == (
        "PASS",
        "PASS",
        "PASS",
        "PASS",
        "PASS",
        "PASS",
        "PASS",
        "PASS",
        "NOT_EVALUATED",
        "PASS",
    )
    assert all("confidence" not in item.name for item in criteria)


@pytest.mark.parametrize(
    ("criterion", "statistics"),
    (
        ("minimum_coverage", _statistics(policy_laya=_policy(coverage=0.5999))),
        ("minimum_accuracy", _statistics(policy_laya=_policy(accuracy=0.6999))),
        (
            "minimum_selective_accuracy",
            _statistics(policy_laya=_policy(selective_accuracy=0.7999)),
        ),
        ("minimum_macro_f1", _statistics(policy_laya=_policy(macro_f1=0.6499))),
        ("maximum_brier", _statistics(raw_laya=_raw(brier=0.6001))),
        (
            "maximum_raw_ece_diagnostic",
            _statistics(raw_laya=_raw(ece=0.1001)),
        ),
        ("maximum_mean_cost", _statistics(policy_laya=_policy(mean_cost=1.0001))),
        (
            "minimum_site_macro_f1",
            _statistics(
                policy_by_site=tuple(
                    _SiteMetricPair(
                        site,
                        _policy(macro_f1=0.5499 if index == 1 else 0.55),
                        _policy(),
                    )
                    for index, site in enumerate(REQUIRED_SITES)
                )
            ),
        ),
        (
            "holm_all_four_rejected",
            _statistics(
                holm=tuple(
                    _HolmDecision(name, 0.01, 0.05 / (4 - index), index != 2)
                    for index, name in enumerate(HYPOTHESES)
                ),
                holm_all=False,
            ),
        ),
    ),
)
def test_each_available_frozen_gate_fails_beyond_its_exact_boundary(criterion, statistics) -> None:
    by_name = {item.name: item for item in _evaluate_mechanical_readiness_criteria(statistics)}
    assert by_name[criterion].mechanical_state == "FAIL"
    assert by_name[criterion].scientific_state == "NOT_EVALUATED"


def test_latency_stays_not_evaluated_and_raw_ece_is_only_a_diagnostic() -> None:
    criteria = {item.name: item for item in _evaluate_mechanical_readiness_criteria(_statistics())}

    assert criteria["maximum_p95_latency_ms"].mechanical_state == "NOT_EVALUATED"
    assert criteria["maximum_p95_latency_ms"].scientific_state == "NOT_EVALUATED"
    assert criteria["maximum_raw_ece_diagnostic"].mechanical_state == "PASS"
    assert criteria["maximum_raw_ece_diagnostic"].scientific_state == "NOT_EVALUATED"
    assert "maximum_ece" not in criteria


@pytest.mark.parametrize(
    "statistics",
    (
        _statistics(raw_laya=replace(_raw(), brier=True)),
        _statistics(raw_laya=replace(_raw(), ece=math.nan)),
        _statistics(policy_laya=replace(_policy(), coverage=1.1)),
        _statistics(policy_laya=replace(_policy(), mean_cost=-0.1)),
        _statistics(
            policy_by_site=tuple(
                _SiteMetricPair(site, _policy(), _policy()) for site in REQUIRED_SITES[:-1]
            )
        ),
        _statistics(
            policy_by_site=tuple(
                _SiteMetricPair(REQUIRED_SITES[0], _policy(), _policy()) for _ in REQUIRED_SITES
            )
        ),
        _statistics(holm_all=True, holm=()),
        _statistics(
            availability=replace(
                _Availability(),
                p95_latency_ms=0.0,
            )
        ),
    ),
)
def test_mechanical_diagnostics_reject_invalid_bounds_coverage_and_contradictions(
    statistics,
) -> None:
    with pytest.raises(ValueError):
        _evaluate_mechanical_readiness_criteria(statistics)
