"""Evidence-bound terminal readiness governance for Laya evaluation."""

from __future__ import annotations

import json
import math
import threading
import weakref
from dataclasses import InitVar, dataclass, field

from human_feedback import evaluation_statistics as _statistics
from human_feedback.evaluation_corpus import REQUIRED_SITES

__all__ = (
    "LayaReadinessReport",
    "evaluate_laya_readiness",
    "canonical_laya_readiness_report_bytes",
)

_SCHEMA_VERSION = "laya-readiness-report-v1"
_POLICY_ID = "laya-readiness-policy-v1"
_PREREQUISITE_NAMES = (
    "statistics_evidence",
    "real_corpus_custody",
    "real_baseline",
    "real_analysis_profile",
    "output_stage_calibration",
)
_CRITERION_NAMES = (
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
_PREREQUISITE_STATES = frozenset(("VERIFIED", "UNAVAILABLE", "FIXTURE_ONLY"))
_SCIENTIFIC_STATES = frozenset(("PASS", "FAIL", "NOT_EVALUATED"))
_MECHANICAL_STATES = frozenset(("PASS", "FAIL", "NOT_EVALUATED"))
_HYPOTHESES = (
    "global_equal_site_macro_f1_superiority",
    "cicytex_macro_f1_noninferiority",
    "melchor-romero_macro_f1_noninferiority",
    "pergamino_macro_f1_noninferiority",
)
_LEGACY_THRESHOLDS = (
    ("minimum_decision_confidence", 0.85),
    ("minimum_coverage", 0.6),
    ("minimum_accuracy", 0.7),
    ("minimum_selective_accuracy", 0.8),
    ("minimum_macro_f1", 0.65),
    ("maximum_brier", 0.6),
    ("maximum_ece", 0.1),
    ("maximum_mean_cost", 1.0),
    ("minimum_site_macro_f1", 0.55),
    ("maximum_p95_latency_ms", 640.0),
)
_CURRENT_PREREQUISITES = (
    ("statistics_evidence", "FIXTURE_ONLY"),
    ("real_corpus_custody", "UNAVAILABLE"),
    ("real_baseline", "UNAVAILABLE"),
    ("real_analysis_profile", "UNAVAILABLE"),
    ("output_stage_calibration", "UNAVAILABLE"),
)
_CURRENT_REASONS = (
    "fixture_statistics_only",
    "real_corpus_custody_unavailable",
    "real_baseline_unavailable",
    "real_analysis_profile_unavailable",
    "output_stage_calibration_unavailable",
    "per_example_latency_unavailable",
    "raw_ece_not_calibrated_policy_ece",
    "scientific_criteria_not_evaluated",
)
_CURRENT_CLAIMS = (
    ("mechanical_diagnostics_evaluated", True),
    ("scientific_evaluation_completed", False),
    ("scientifically_sufficient", False),
    ("eligible_for_independent_shadow_review", False),
    ("production_enablement_authorized", False),
)
_REPORT_TOKEN = object()
_LOCK = threading.RLock()


def _fail() -> None:
    raise ValueError("invalid Laya readiness authority") from None


@dataclass(frozen=True, slots=True)
class _Prerequisite:
    name: str
    state: str

    def __post_init__(self) -> None:
        if (
            type(self.name) is not str
            or self.name not in _PREREQUISITE_NAMES
            or type(self.state) is not str
            or self.state not in _PREREQUISITE_STATES
        ):
            _fail()


@dataclass(frozen=True, slots=True)
class _Criterion:
    name: str
    scientific_state: str
    mechanical_state: str

    def __post_init__(self) -> None:
        if (
            type(self.name) is not str
            or self.name not in _CRITERION_NAMES
            or type(self.scientific_state) is not str
            or self.scientific_state not in _SCIENTIFIC_STATES
            or type(self.mechanical_state) is not str
            or self.mechanical_state not in _MECHANICAL_STATES
        ):
            _fail()


def _decide_readiness(
    prerequisites: tuple[_Prerequisite, ...],
    criteria: tuple[_Criterion, ...],
) -> str:
    if (
        type(prerequisites) is not tuple
        or type(criteria) is not tuple
        or tuple(item.name for item in prerequisites if type(item) is _Prerequisite)
        != _PREREQUISITE_NAMES
        or tuple(item.name for item in criteria if type(item) is _Criterion) != _CRITERION_NAMES
        or any(type(item) is not _Prerequisite for item in prerequisites)
        or any(type(item) is not _Criterion for item in criteria)
    ):
        _fail()
    for item in prerequisites:
        item.__post_init__()
    for item in criteria:
        item.__post_init__()
        if item.scientific_state in {"PASS", "FAIL"} and (
            item.mechanical_state == "NOT_EVALUATED"
            or item.scientific_state != item.mechanical_state
        ):
            _fail()
    if any(item.scientific_state == "FAIL" for item in criteria):
        return "FAIL"
    if any(item.state != "VERIFIED" for item in prerequisites) or any(
        item.scientific_state == "NOT_EVALUATED" for item in criteria
    ):
        return "BLOCKED"
    return "PASS"


def _finite_number(value: object, *, minimum: float, maximum: float | None = None) -> float:
    if type(value) not in {int, float} or not math.isfinite(value):
        _fail()
    number = float(value)
    if number < minimum or (maximum is not None and number > maximum):
        _fail()
    return number


def _validate_raw(value: object) -> None:
    if (
        type(value) is not _statistics._RawMetrics
        or type(value.total) is not int
        or value.total <= 0
    ):
        _fail()
    _finite_number(value.accuracy, minimum=0.0, maximum=1.0)
    _finite_number(value.macro_f1, minimum=0.0, maximum=1.0)
    _finite_number(value.brier, minimum=0.0)
    _finite_number(value.ece, minimum=0.0, maximum=1.0)


def _validate_policy(value: object) -> None:
    if (
        type(value) is not _statistics._PolicyDiagnostics
        or type(value.total) is not int
        or value.total <= 0
        or type(value.confidence_source) is not str
        or value.confidence_source != "selected_probability_fallback"
        or type(value.calibrated) is not bool
        or value.calibrated
    ):
        _fail()
    _finite_number(value.coverage, minimum=0.0, maximum=1.0)
    _finite_number(value.selective_accuracy, minimum=0.0, maximum=1.0)
    _finite_number(value.accuracy, minimum=0.0, maximum=1.0)
    _finite_number(value.macro_f1, minimum=0.0, maximum=1.0)
    _finite_number(value.mean_cost, minimum=0.0)


def _evaluate_mechanical_readiness_criteria(
    statistics: object,
) -> tuple[_Criterion, ...]:
    if type(statistics) is not _statistics._MechanicalStatisticsEvidence:
        _fail()
    _validate_raw(statistics.raw_laya)
    _validate_policy(statistics.policy_laya)
    if type(statistics.policy_by_site) is not tuple or len(statistics.policy_by_site) != len(
        REQUIRED_SITES
    ):
        _fail()
    site_macro_f1 = []
    for observed, site in zip(statistics.policy_by_site, REQUIRED_SITES, strict=True):
        if type(observed) is not _statistics._SiteMetricPair or observed.site_id != site:
            _fail()
        _validate_policy(observed.laya)
        site_macro_f1.append(observed.laya.macro_f1)
    if type(statistics.holm) is not tuple or len(statistics.holm) != len(_HYPOTHESES):
        _fail()
    by_hypothesis = {}
    for item in statistics.holm:
        if (
            type(item) is not _statistics._HolmDecision
            or type(item.hypothesis) is not str
            or item.hypothesis not in _HYPOTHESES
            or item.hypothesis in by_hypothesis
            or type(item.rejected) is not bool
        ):
            _fail()
        _finite_number(item.p_value, minimum=0.0, maximum=1.0)
        _finite_number(item.threshold, minimum=0.0, maximum=1.0)
        by_hypothesis[item.hypothesis] = item
    if (
        set(by_hypothesis) != set(_HYPOTHESES)
        or type(statistics.mechanical_holm_all_rejected) is not bool
    ):
        _fail()
    holm_all = all(item.rejected for item in statistics.holm)
    if statistics.mechanical_holm_all_rejected is not holm_all:
        _fail()
    availability = statistics.availability
    if (
        type(availability) is not _statistics._Availability
        or availability.latency != "UNAVAILABLE_INPUT_NOT_CAPTURED"
        or availability.p50_latency_ms is not None
        or availability.p95_latency_ms is not None
    ):
        _fail()

    threshold = dict(_LEGACY_THRESHOLDS)
    states = (
        statistics.policy_laya.coverage >= threshold["minimum_coverage"],
        statistics.policy_laya.accuracy >= threshold["minimum_accuracy"],
        statistics.policy_laya.selective_accuracy >= threshold["minimum_selective_accuracy"],
        statistics.policy_laya.macro_f1 >= threshold["minimum_macro_f1"],
        statistics.raw_laya.brier <= threshold["maximum_brier"],
        statistics.raw_laya.ece <= threshold["maximum_ece"],
        statistics.policy_laya.mean_cost <= threshold["maximum_mean_cost"],
        all(value >= threshold["minimum_site_macro_f1"] for value in site_macro_f1),
        None,
        holm_all,
    )
    return tuple(
        _Criterion(
            name,
            "NOT_EVALUATED",
            "NOT_EVALUATED" if state is None else ("PASS" if state else "FAIL"),
        )
        for name, state in zip(_CRITERION_NAMES, states, strict=True)
    )


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class LayaReadinessReport:
    schema_version: str
    decision: str
    policy_id: str
    fixture_profile_id: str
    prerequisites: tuple[tuple[str, str], ...]
    criteria: tuple[tuple[str, str, str], ...]
    reason_codes: tuple[str, ...]
    claims: tuple[tuple[str, bool], ...]
    _statistics_parent: object = field(repr=False)
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _REPORT_TOKEN:
            _fail()


@dataclass(slots=True, repr=False)
class _IssuedReportRecord:
    reference: weakref.ReferenceType
    parent: object
    binding: tuple[object, ...]


_ISSUED: dict[int, _IssuedReportRecord] = {}


def _report_binding(report: LayaReadinessReport) -> tuple[object, ...]:
    if type(report) is not LayaReadinessReport:
        _fail()
    if (
        type(report.prerequisites) is not tuple
        or len(report.prerequisites) != len(_PREREQUISITE_NAMES)
        or any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not str
            for item in report.prerequisites
        )
        or type(report.criteria) is not tuple
        or len(report.criteria) != len(_CRITERION_NAMES)
        or any(
            type(item) is not tuple
            or len(item) != 3
            or type(item[0]) is not str
            or type(item[1]) is not str
            or type(item[2]) is not str
            for item in report.criteria
        )
        or type(report.reason_codes) is not tuple
        or len(report.reason_codes) != len(_CURRENT_REASONS)
        or any(type(item) is not str for item in report.reason_codes)
        or type(report.claims) is not tuple
        or len(report.claims) != len(_CURRENT_CLAIMS)
        or any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not bool
            for item in report.claims
        )
    ):
        _fail()
    prerequisites = tuple(_Prerequisite(name, state) for name, state in report.prerequisites)
    criteria = tuple(
        _Criterion(name, scientific, mechanical) for name, scientific, mechanical in report.criteria
    )
    if (
        report.schema_version != _SCHEMA_VERSION
        or type(report.schema_version) is not str
        or type(report.decision) is not str
        or report.decision != _decide_readiness(prerequisites, criteria)
        or type(report.policy_id) is not str
        or report.policy_id != _POLICY_ID
        or type(report.fixture_profile_id) is not str
        or not report.fixture_profile_id
        or report.reason_codes != _CURRENT_REASONS
        or report.claims != _CURRENT_CLAIMS
    ):
        _fail()
    return (
        ("str", report.schema_version),
        ("str", report.decision),
        ("str", report.policy_id),
        ("str", report.fixture_profile_id),
        (
            "prerequisites",
            tuple((str(name), str(state)) for name, state in report.prerequisites),
        ),
        (
            "criteria",
            tuple(
                (str(name), str(scientific), str(mechanical))
                for name, scientific, mechanical in report.criteria
            ),
        ),
        ("reasons", tuple(str(reason) for reason in report.reason_codes)),
        (
            "claims",
            tuple((str(name), ("bool", value)) for name, value in report.claims),
        ),
    )


def _register_report(report: LayaReadinessReport) -> None:
    identity = id(report)

    def discard(reference: weakref.ReferenceType, *, expected: int = identity) -> None:
        with _LOCK:
            current = _ISSUED.get(expected)
            if current is not None and current.reference is reference:
                _ISSUED.pop(expected, None)

    reference = weakref.ref(report, discard)
    record = _IssuedReportRecord(reference, report._statistics_parent, _report_binding(report))
    with _LOCK:
        if identity in _ISSUED:
            _fail()
        _ISSUED[identity] = record


def _require_issued_laya_readiness_report(value: object) -> LayaReadinessReport:
    valid = False
    try:
        if type(value) is not LayaReadinessReport:
            raise ValueError
        with _LOCK:
            record = _ISSUED.get(id(value))
        if (
            record is None
            or record.reference() is not value
            or value._statistics_parent is not record.parent
            or _report_binding(value) != record.binding
        ):
            raise ValueError
        _statistics._require_issued_mechanical_statistics(record.parent)
        final_binding = _report_binding(value)
        with _LOCK:
            current = _ISSUED.get(id(value))
            valid = (
                current is record
                and current.reference() is value
                and value._statistics_parent is current.parent
                and final_binding == current.binding
            )
    except Exception:
        valid = False
    if not valid:
        _fail()
    return value


def _validate_frozen_policy(statistics: _statistics._MechanicalStatisticsEvidence) -> None:
    protocol = statistics._protocol
    preregistration = protocol._preregistration
    analysis = preregistration.analysis
    if (
        analysis.legacy_policy_id != _POLICY_ID
        or type(analysis.legacy_policy_id) is not str
        or analysis.legacy_thresholds != _LEGACY_THRESHOLDS
    ):
        _fail()


def evaluate_laya_readiness(statistics: object) -> LayaReadinessReport:
    report = None
    try:
        issued = _statistics._require_issued_mechanical_statistics(statistics)
        _validate_frozen_policy(issued)
        criteria = _evaluate_mechanical_readiness_criteria(issued)
        prerequisites = tuple(_Prerequisite(*item) for item in _CURRENT_PREREQUISITES)
        decision = _decide_readiness(prerequisites, criteria)
        if decision != "BLOCKED":
            raise ValueError
        report = LayaReadinessReport(
            schema_version=_SCHEMA_VERSION,
            decision=decision,
            policy_id=_POLICY_ID,
            fixture_profile_id=issued.fixture_profile_id,
            prerequisites=tuple((item.name, item.state) for item in prerequisites),
            criteria=tuple(
                (item.name, item.scientific_state, item.mechanical_state) for item in criteria
            ),
            reason_codes=_CURRENT_REASONS,
            claims=_CURRENT_CLAIMS,
            _statistics_parent=issued,
            _factory_token=_REPORT_TOKEN,
        )
        _statistics._require_issued_mechanical_statistics(issued)
        _register_report(report)
        _require_issued_laya_readiness_report(report)
        return report
    except Exception:
        pass
    _fail()


def canonical_laya_readiness_report_bytes(report: object) -> bytes:
    payload = None
    try:
        issued = _require_issued_laya_readiness_report(report)
        payload = {
            "schema_version": issued.schema_version,
            "decision": issued.decision,
            "policy_id": issued.policy_id,
            "fixture_profile_id": issued.fixture_profile_id,
            "prerequisites": issued.prerequisites,
            "criteria": issued.criteria,
            "reason_codes": issued.reason_codes,
            "claims": issued.claims,
        }
        _require_issued_laya_readiness_report(issued)
        return json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except Exception:
        pass
    _fail()
