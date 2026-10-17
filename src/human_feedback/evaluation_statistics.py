"""Bounded mechanical statistics for synthetic, sealed LOSO fixtures only."""

from __future__ import annotations

import json
import math
import random
import threading
import weakref
from dataclasses import dataclass, field

from human_feedback.evaluation_corpus import CATEGORIES, REQUIRED_SITES
from human_feedback.offline_readiness import DeterministicRuleBaseline

__all__ = (
    "MechanicalStatisticsPreflight",
    "preflight_laya_mechanical_statistics",
)

_PREFLIGHT_SCHEMA = "laya-mechanical-statistics-preflight-v1"
_EVIDENCE_SCHEMA = "laya-mechanical-statistics-v1"
_FIXTURE_PROFILE_ID = "python-mt19937-randrange-nearest-rank-v1"
_BASELINE_FIXTURE_ID = "deterministic-rule-baseline-v1-mechanical-fixture"
_HYPOTHESES = (
    "global_equal_site_macro_f1_superiority",
    "cicytex_macro_f1_noninferiority",
    "melchor-romero_macro_f1_noninferiority",
    "pergamino_macro_f1_noninferiority",
)
_SITE_HYPOTHESES = dict(zip(REQUIRED_SITES, _HYPOTHESES[1:], strict=True))
_MARGINS = dict(zip(_HYPOTHESES, (0.05, -0.02, -0.02, -0.02), strict=True))
_REPLICATES = 10_000
_SEED = 20_261_017
_MAX_ROWS = 512 * len(REQUIRED_SITES)
_MAX_GROUPS_PER_SITE = 512
_PROBABILITY_MASS_TOLERANCE = 5 * 0.5e-4 + 1e-12
_FIXTURE_AUTHORIZED = object()
_LOCK = threading.RLock()
_ISSUED: dict[int, _IssuedRecord] = {}


def _fail() -> None:
    error = ValueError("mechanical statistical qualification is unavailable")
    error.__suppress_context__ = True
    raise error from None


@dataclass(frozen=True, slots=True, repr=False, init=False)
class MechanicalStatisticsPreflight:
    schema_version: str = _PREFLIGHT_SCHEMA
    status: str = "BLOCKED_EXTERNAL_SCIENTIFIC_ADMISSIONS"
    missing_requirements: tuple[str, ...] = (
        "real_corpus_and_custody_admission",
        "real_baseline_producer_admission",
        "real_analysis_profile_admission",
        "calibration_evidence",
        "latency_inputs",
    )
    ready: bool = False
    private_rows_consumed: bool = False
    fixture_baseline_invoked: bool = False
    scientific_execution_completed: bool = False
    calibration_fitted: bool = False
    scientifically_sufficient: bool = False
    eligible_for_shadow_review: bool = False
    production_enablement_authorized: bool = False

    def __init__(self) -> None:
        for item in self.__dataclass_fields__.values():
            object.__setattr__(self, item.name, item.default)


def preflight_laya_mechanical_statistics(protocol: object) -> MechanicalStatisticsPreflight:
    """Report the real analysis as blocked without consuming its argument."""

    del protocol
    return MechanicalStatisticsPreflight()


def _valid_probability_items(value: object) -> bool:
    if type(value) is not tuple or len(value) != len(CATEGORIES):
        return False
    if tuple(item[0] for item in value if type(item) is tuple and len(item) == 2) != CATEGORIES:
        return False
    if any(type(item) is not tuple or len(item) != 2 for item in value):
        return False
    amounts = tuple(item[1] for item in value)
    return all(
        type(amount) in {int, float} and math.isfinite(amount) and 0.0 <= amount <= 1.0
        for amount in amounts
    ) and math.isclose(
        sum(amounts),
        1.0,
        rel_tol=0.0,
        abs_tol=_PROBABILITY_MASS_TOLERANCE,
    )


@dataclass(frozen=True, slots=True, repr=False)
class _MechanicalPair:
    site_id: str = field(repr=False)
    group_id: str = field(repr=False)
    gold_category: str = field(repr=False)
    laya_category: str = field(repr=False)
    laya_probabilities: tuple[tuple[str, float], ...] = field(repr=False)
    baseline_category: str = field(repr=False)
    baseline_probabilities: tuple[tuple[str, float], ...] = field(repr=False)

    def __post_init__(self) -> None:
        valid = (
            type(self.site_id) is str
            and self.site_id in REQUIRED_SITES
            and type(self.group_id) is str
            and bool(self.group_id)
            and self.group_id == self.group_id.strip()
            and type(self.gold_category) is str
            and self.gold_category in CATEGORIES
            and type(self.laya_category) is str
            and self.laya_category in CATEGORIES
            and type(self.baseline_category) is str
            and self.baseline_category in (*CATEGORIES, "unclassified")
            and _valid_probability_items(self.laya_probabilities)
            and _valid_probability_items(self.baseline_probabilities)
        )
        if valid:
            laya = dict(self.laya_probabilities)
            valid = laya[self.laya_category] == max(laya.values())
        if valid and self.baseline_category != "unclassified":
            baseline = dict(self.baseline_probabilities)
            valid = baseline[self.baseline_category] == max(baseline.values())
        if not valid:
            _fail()


@dataclass(frozen=True, slots=True)
class _RawMetrics:
    total: int
    accuracy: float
    macro_f1: float
    brier: float
    ece: float


@dataclass(frozen=True, slots=True)
class _PolicyDiagnostics:
    total: int
    coverage: float
    selective_accuracy: float
    accuracy: float
    macro_f1: float
    mean_cost: float
    confidence_source: str = "selected_probability_fallback"
    calibrated: bool = False


@dataclass(frozen=True, slots=True)
class _BootstrapSummary:
    hypothesis: str
    observed_delta: float
    lower: float
    upper: float
    tail_probability: float
    replicate_count: int


@dataclass(frozen=True, slots=True)
class _HolmDecision:
    hypothesis: str
    p_value: float
    threshold: float
    rejected: bool


@dataclass(frozen=True, slots=True)
class _SiteMetricPair:
    site_id: str
    laya: object
    baseline: object


def _validated_rows(rows: object) -> tuple[_MechanicalPair, ...]:
    if type(rows) is not tuple or not 0 < len(rows) <= _MAX_ROWS:
        _fail()
    for row in rows:
        if type(row) is not _MechanicalPair:
            _fail()
        try:
            row.__post_init__()
        except Exception:
            _fail()
    return rows


def _projection(row: _MechanicalPair, source: str) -> tuple[str, tuple[tuple[str, float], ...]]:
    if source == "laya":
        return row.laya_category, row.laya_probabilities
    if source == "baseline":
        return row.baseline_category, row.baseline_probabilities
    _fail()


def _macro_f1(gold: tuple[str, ...], predicted: tuple[str, ...]) -> float:
    values = []
    for category in CATEGORIES:
        true_positive = sum(
            expected == category and observed == category
            for expected, observed in zip(gold, predicted, strict=True)
        )
        false_positive = sum(
            expected != category and observed == category
            for expected, observed in zip(gold, predicted, strict=True)
        )
        false_negative = sum(
            expected == category and observed != category
            for expected, observed in zip(gold, predicted, strict=True)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        values.append(0.0 if denominator == 0 else 2 * true_positive / denominator)
    return sum(values) / len(CATEGORIES)


def _raw_metrics(rows: tuple[_MechanicalPair, ...], *, source: str) -> _RawMetrics:
    rows = _validated_rows(rows)
    if type(source) is not str or source not in {"laya", "baseline"}:
        _fail()
    gold = tuple(row.gold_category for row in rows)
    projections = tuple(_projection(row, source) for row in rows)
    predicted = tuple(item[0] for item in projections)
    total = len(rows)
    brier = 0.0
    bins: list[list[tuple[float, float]]] = [[] for _ in range(10)]
    for expected, (category, probabilities) in zip(gold, projections, strict=True):
        amounts = dict(probabilities)
        brier += sum((amounts[label] - float(expected == label)) ** 2 for label in CATEGORIES)
        confidence = max(amounts.values())
        bins[min(int(confidence * 10), 9)].append((confidence, float(category == expected)))
    ece = sum(
        len(values)
        / total
        * abs(
            sum(confidence for confidence, _ in values) / len(values)
            - sum(outcome for _, outcome in values) / len(values)
        )
        for values in bins
        if values
    )
    return _RawMetrics(
        total=total,
        accuracy=sum(expected == observed for expected, observed in zip(gold, predicted)) / total,
        macro_f1=_macro_f1(gold, predicted),
        brier=brier / total,
        ece=ece,
    )


def _legacy_policy_diagnostics(
    rows: tuple[_MechanicalPair, ...], *, source: str
) -> _PolicyDiagnostics:
    rows = _validated_rows(rows)
    if type(source) is not str or source not in {"laya", "baseline"}:
        _fail()
    gold = tuple(row.gold_category for row in rows)
    selected = []
    costs = []
    answered_correct = 0
    answered = 0
    for row in rows:
        category, probabilities = _projection(row, source)
        if category == "unclassified":
            retained = "unclassified"
        else:
            retained = category if dict(probabilities)[category] >= 0.85 else "unclassified"
        selected.append(retained)
        if retained == "unclassified":
            costs.append(1.0)
        else:
            answered += 1
            correct = retained == row.gold_category
            answered_correct += int(correct)
            costs.append(0.0 if correct else 5.0)
    predicted = tuple(selected)
    total = len(rows)
    correct = sum(expected == observed for expected, observed in zip(gold, predicted))
    return _PolicyDiagnostics(
        total=total,
        coverage=answered / total,
        selective_accuracy=answered_correct / answered if answered else 0.0,
        accuracy=correct / total,
        macro_f1=_macro_f1(gold, predicted),
        mean_cost=sum(costs) / total,
    )


def _nearest_rank_95(values: tuple[float, ...]) -> tuple[float, float]:
    if type(values) is not tuple or not values:
        _fail()
    if any(type(value) not in {int, float} or not math.isfinite(value) for value in values):
        _fail()
    ordered = sorted(float(value) for value in values)
    lower = max(1, math.ceil(0.025 * len(ordered)))
    upper = max(1, math.ceil(0.975 * len(ordered)))
    return ordered[lower - 1], ordered[upper - 1]


def _empty_matrix() -> list[list[int]]:
    return [[0] * (len(CATEGORIES) + 1) for _ in CATEGORIES]


def _matrix_add(target: list[list[int]], source: tuple[tuple[int, ...], ...]) -> None:
    for row_index, row in enumerate(source):
        for column_index, value in enumerate(row):
            target[row_index][column_index] += value


def _matrix_macro_f1(matrix: list[list[int]] | tuple[tuple[int, ...], ...]) -> float:
    values = []
    for index in range(len(CATEGORIES)):
        true_positive = matrix[index][index]
        false_positive = sum(matrix[row][index] for row in range(len(CATEGORIES)) if row != index)
        false_negative = sum(
            matrix[index][column] for column in range(len(CATEGORIES) + 1) if column != index
        )
        denominator = 2 * true_positive + false_positive + false_negative
        values.append(0.0 if denominator == 0 else 2 * true_positive / denominator)
    return sum(values) / len(CATEGORIES)


def _group_matrices(rows: tuple[_MechanicalPair, ...]):
    grouped = {}
    category_index = {category: index for index, category in enumerate(CATEGORIES)}
    for row in rows:
        key = (row.site_id, row.group_id)
        if key not in grouped:
            grouped[key] = (_empty_matrix(), _empty_matrix())
        gold_index = category_index[row.gold_category]
        for matrix, category in zip(
            grouped[key], (row.laya_category, row.baseline_category), strict=True
        ):
            prediction_index = (
                len(CATEGORIES) if category == "unclassified" else category_index[category]
            )
            matrix[gold_index][prediction_index] += 1
    return {
        key: tuple(tuple(value for value in row) for row in matrix_pair[0])
        for key, matrix_pair in grouped.items()
    }, {
        key: tuple(tuple(value for value in row) for row in matrix_pair[1])
        for key, matrix_pair in grouped.items()
    }


def _paired_group_bootstrap(
    rows: tuple[_MechanicalPair, ...],
) -> tuple[_BootstrapSummary, ...]:
    rows = _validated_rows(rows)
    if {row.site_id for row in rows} != set(REQUIRED_SITES):
        _fail()
    groups_by_site = {
        site: tuple(sorted({row.group_id for row in rows if row.site_id == site}))
        for site in REQUIRED_SITES
    }
    if any(not groups or len(groups) > _MAX_GROUPS_PER_SITE for groups in groups_by_site.values()):
        _fail()
    laya_groups, baseline_groups = _group_matrices(rows)
    observed_by_site = {}
    for site in REQUIRED_SITES:
        laya = _empty_matrix()
        baseline = _empty_matrix()
        for group in groups_by_site[site]:
            _matrix_add(laya, laya_groups[(site, group)])
            _matrix_add(baseline, baseline_groups[(site, group)])
        observed_by_site[site] = _matrix_macro_f1(laya) - _matrix_macro_f1(baseline)
    observed_global = sum(observed_by_site.values()) / len(REQUIRED_SITES)

    rng = random.Random(_SEED)
    replicates = {hypothesis: [] for hypothesis in _HYPOTHESES}
    for _replicate in range(_REPLICATES):
        site_deltas = []
        for site in REQUIRED_SITES:
            groups = groups_by_site[site]
            laya = _empty_matrix()
            baseline = _empty_matrix()
            for _draw in range(len(groups)):
                group = groups[rng.randrange(len(groups))]
                _matrix_add(laya, laya_groups[(site, group)])
                _matrix_add(baseline, baseline_groups[(site, group)])
            delta = _matrix_macro_f1(laya) - _matrix_macro_f1(baseline)
            site_deltas.append(delta)
            replicates[_SITE_HYPOTHESES[site]].append(delta)
        replicates[_HYPOTHESES[0]].append(sum(site_deltas) / len(REQUIRED_SITES))

    observed = {_HYPOTHESES[0]: observed_global}
    observed.update({_SITE_HYPOTHESES[site]: observed_by_site[site] for site in REQUIRED_SITES})
    summaries = []
    for hypothesis in _HYPOTHESES:
        values = tuple(replicates[hypothesis])
        lower, upper = _nearest_rank_95(values)
        tail = (1 + sum(value <= _MARGINS[hypothesis] for value in values)) / (_REPLICATES + 1)
        summaries.append(
            _BootstrapSummary(
                hypothesis=hypothesis,
                observed_delta=observed[hypothesis],
                lower=lower,
                upper=upper,
                tail_probability=tail,
                replicate_count=_REPLICATES,
            )
        )
    return tuple(summaries)


def _holm_step_down(summaries: tuple[_BootstrapSummary, ...]) -> tuple[_HolmDecision, ...]:
    if type(summaries) is not tuple or len(summaries) != len(_HYPOTHESES):
        _fail()
    by_name = {}
    for summary in summaries:
        if type(summary) is not _BootstrapSummary or summary.hypothesis in by_name:
            _fail()
        numeric = (
            summary.observed_delta,
            summary.lower,
            summary.upper,
            summary.tail_probability,
        )
        if (
            summary.hypothesis not in _HYPOTHESES
            or summary.replicate_count != _REPLICATES
            or any(type(value) not in {int, float} or not math.isfinite(value) for value in numeric)
            or not 0.0 <= summary.tail_probability <= 1.0
        ):
            _fail()
        by_name[summary.hypothesis] = summary
    if set(by_name) != set(_HYPOTHESES):
        _fail()
    family_index = {name: index for index, name in enumerate(_HYPOTHESES)}
    ordered = sorted(
        summaries,
        key=lambda summary: (summary.tail_probability, family_index[summary.hypothesis]),
    )
    stopped = False
    decisions = []
    for rank, summary in enumerate(ordered, start=1):
        threshold = 0.05 / (len(_HYPOTHESES) - rank + 1)
        rejected = not stopped and summary.tail_probability <= threshold
        if not rejected:
            stopped = True
        decisions.append(
            _HolmDecision(
                hypothesis=summary.hypothesis,
                p_value=summary.tail_probability,
                threshold=threshold,
                rejected=rejected,
            )
        )
    return tuple(decisions)


@dataclass(frozen=True, slots=True)
class _Availability:
    raw_metrics: str = "AVAILABLE_MECHANICAL_FIXTURE"
    legacy_policy_diagnostics: str = "AVAILABLE_UNCALIBRATED_SELECTED_PROBABILITY_FALLBACK"
    calibrated_metrics: str = "UNAVAILABLE_CALIBRATION_NOT_FITTED"
    latency: str = "UNAVAILABLE_INPUT_NOT_CAPTURED"
    p50_latency_ms: None = None
    p95_latency_ms: None = None
    real_baseline: str = "UNAVAILABLE_EXTERNAL_ADMISSION_REQUIRED"
    real_analysis_profile: str = "UNAVAILABLE_EXTERNAL_ADMISSION_REQUIRED"
    scientific_verdict: str = "BLOCKED"


@dataclass(frozen=True, slots=True, repr=False, weakref_slot=True)
class _MechanicalStatisticsEvidence:
    raw_laya: _RawMetrics
    raw_baseline: _RawMetrics
    raw_by_site: tuple[_SiteMetricPair, ...]
    policy_laya: _PolicyDiagnostics
    policy_baseline: _PolicyDiagnostics
    policy_by_site: tuple[_SiteMetricPair, ...]
    bootstrap: tuple[_BootstrapSummary, ...]
    holm: tuple[_HolmDecision, ...]
    mechanical_holm_all_rejected: bool
    _protocol: object = field(repr=False)
    _receipts: tuple[object, ...] = field(repr=False)
    schema_version: str = _EVIDENCE_SCHEMA
    status: str = "MECHANICAL_FIXTURE_ONLY_BLOCKED"
    fixture_profile_id: str = _FIXTURE_PROFILE_ID
    baseline_fixture_id: str = _BASELINE_FIXTURE_ID
    availability: _Availability = field(default_factory=_Availability)
    mechanical_fixture_calculated: bool = True
    scientific_execution_completed: bool = False
    calibration_fitted: bool = False
    scientifically_sufficient: bool = False
    eligible_for_shadow_review: bool = False
    production_enablement_authorized: bool = False


@dataclass(slots=True, repr=False)
class _IssuedRecord:
    reference: weakref.ReferenceType
    protocol: object
    receipts: tuple[object, ...]
    binding: tuple[object, ...]


def _evidence_binding(value: _MechanicalStatisticsEvidence) -> tuple[object, ...]:
    return (
        _aggregate_snapshot(value.raw_laya),
        _aggregate_snapshot(value.raw_baseline),
        _aggregate_snapshot(value.raw_by_site),
        _aggregate_snapshot(value.policy_laya),
        _aggregate_snapshot(value.policy_baseline),
        _aggregate_snapshot(value.policy_by_site),
        _aggregate_snapshot(value.bootstrap),
        _aggregate_snapshot(value.holm),
        _primitive_snapshot(value.mechanical_holm_all_rejected),
        _primitive_snapshot(value.schema_version),
        _primitive_snapshot(value.status),
        _primitive_snapshot(value.fixture_profile_id),
        _primitive_snapshot(value.baseline_fixture_id),
        _aggregate_snapshot(value.availability),
        _primitive_snapshot(value.mechanical_fixture_calculated),
        _primitive_snapshot(value.scientific_execution_completed),
        _primitive_snapshot(value.calibration_fitted),
        _primitive_snapshot(value.scientifically_sufficient),
        _primitive_snapshot(value.eligible_for_shadow_review),
        _primitive_snapshot(value.production_enablement_authorized),
    )


def _primitive_snapshot(value: object) -> tuple[object, ...]:
    """Commit to both the exact primitive type and its immutable value."""

    if value is None:
        return ("none",)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    if type(value) is float and math.isfinite(value):
        return ("float", value)
    if type(value) is str:
        return ("str", value)
    _fail()


def _aggregate_snapshot(value: object) -> tuple[object, ...]:
    """Copy one closed aggregate into primitives, never retained object refs."""

    if type(value) is tuple:
        return ("tuple", tuple(_aggregate_snapshot(item) for item in value))
    if type(value) is _RawMetrics:
        return (
            "raw",
            _primitive_snapshot(value.total),
            _primitive_snapshot(value.accuracy),
            _primitive_snapshot(value.macro_f1),
            _primitive_snapshot(value.brier),
            _primitive_snapshot(value.ece),
        )
    if type(value) is _PolicyDiagnostics:
        return (
            "policy",
            _primitive_snapshot(value.total),
            _primitive_snapshot(value.coverage),
            _primitive_snapshot(value.selective_accuracy),
            _primitive_snapshot(value.accuracy),
            _primitive_snapshot(value.macro_f1),
            _primitive_snapshot(value.mean_cost),
            _primitive_snapshot(value.confidence_source),
            _primitive_snapshot(value.calibrated),
        )
    if type(value) is _SiteMetricPair:
        return (
            "site",
            _primitive_snapshot(value.site_id),
            _aggregate_snapshot(value.laya),
            _aggregate_snapshot(value.baseline),
        )
    if type(value) is _BootstrapSummary:
        return (
            "bootstrap",
            _primitive_snapshot(value.hypothesis),
            _primitive_snapshot(value.observed_delta),
            _primitive_snapshot(value.lower),
            _primitive_snapshot(value.upper),
            _primitive_snapshot(value.tail_probability),
            _primitive_snapshot(value.replicate_count),
        )
    if type(value) is _HolmDecision:
        return (
            "holm",
            _primitive_snapshot(value.hypothesis),
            _primitive_snapshot(value.p_value),
            _primitive_snapshot(value.threshold),
            _primitive_snapshot(value.rejected),
        )
    if type(value) is _Availability:
        return (
            "availability",
            _primitive_snapshot(value.raw_metrics),
            _primitive_snapshot(value.legacy_policy_diagnostics),
            _primitive_snapshot(value.calibrated_metrics),
            _primitive_snapshot(value.latency),
            _primitive_snapshot(value.p50_latency_ms),
            _primitive_snapshot(value.p95_latency_ms),
            _primitive_snapshot(value.real_baseline),
            _primitive_snapshot(value.real_analysis_profile),
            _primitive_snapshot(value.scientific_verdict),
        )
    _fail()


def _register(value: _MechanicalStatisticsEvidence) -> None:
    identity = id(value)
    record = None

    def cleanup(reference):
        with _LOCK:
            if _ISSUED.get(identity) is record and record.reference is reference:
                _ISSUED.pop(identity, None)

    record = _IssuedRecord(
        weakref.ref(value, cleanup),
        value._protocol,
        value._receipts,
        _evidence_binding(value),
    )
    with _LOCK:
        _ISSUED[identity] = record


def _require_mechanical_statistics_fixture_authority(protocol: object):
    del protocol
    _fail()


def _response_predictions(receipt: object) -> list[dict[str, object]]:
    value = json.loads(receipt.canonical_response.decode("utf-8"))
    predictions = value["predictions"]
    if type(predictions) is not list:
        _fail()
    return predictions


def _run_laya_mechanical_statistics_fixture(protocol: object) -> _MechanicalStatisticsEvidence:
    authorized = False
    try:
        authorized = (
            _require_mechanical_statistics_fixture_authority(protocol) is _FIXTURE_AUTHORIZED
        )
    except Exception:
        authorized = False
    if not authorized:
        _fail()
    try:
        from human_feedback import evaluation_run_protocol as run_protocol
        from human_feedback import evaluation_runner as runner

        issued = run_protocol._require_issued_human_loso_execution_protocol(protocol)
        receipts = runner._sealed_human_loso_mechanical_batches(issued)
        test_receipts = {
            receipt.fold_index: receipt for receipt in receipts if receipt.phase == "test"
        }
        if len(test_receipts) != len(issued._plan.folds):
            raise ValueError
        baseline = DeterministicRuleBaseline()
        rows = []
        for fold_index, fold in enumerate(issued._plan.folds):
            receipt = test_receipts[fold_index]
            predictions = _response_predictions(receipt)
            if len(predictions) != len(fold.test_records):
                raise ValueError
            for record, prediction in zip(fold.test_records, predictions, strict=True):
                suggestion = baseline.classify(record.site_id, record.comment)
                probabilities = prediction["probabilities"]
                rows.append(
                    _MechanicalPair(
                        site_id=record.site_id,
                        group_id=record.group_id,
                        gold_category=record.gold_category,
                        laya_category=prediction["category"],
                        laya_probabilities=tuple(
                            (category, probabilities[category]) for category in CATEGORIES
                        ),
                        baseline_category=suggestion.category,
                        baseline_probabilities=tuple(suggestion.probabilities),
                    )
                )
        pairs = tuple(rows)
        raw_laya = _raw_metrics(pairs, source="laya")
        raw_baseline = _raw_metrics(pairs, source="baseline")
        policy_laya = _legacy_policy_diagnostics(pairs, source="laya")
        policy_baseline = _legacy_policy_diagnostics(pairs, source="baseline")
        raw_by_site = tuple(
            _SiteMetricPair(
                site,
                _raw_metrics(tuple(row for row in pairs if row.site_id == site), source="laya"),
                _raw_metrics(tuple(row for row in pairs if row.site_id == site), source="baseline"),
            )
            for site in REQUIRED_SITES
        )
        policy_by_site = tuple(
            _SiteMetricPair(
                site,
                _legacy_policy_diagnostics(
                    tuple(row for row in pairs if row.site_id == site), source="laya"
                ),
                _legacy_policy_diagnostics(
                    tuple(row for row in pairs if row.site_id == site), source="baseline"
                ),
            )
            for site in REQUIRED_SITES
        )
        bootstrap = _paired_group_bootstrap(pairs)
        holm = _holm_step_down(bootstrap)
        evidence = _MechanicalStatisticsEvidence(
            raw_laya=raw_laya,
            raw_baseline=raw_baseline,
            raw_by_site=raw_by_site,
            policy_laya=policy_laya,
            policy_baseline=policy_baseline,
            policy_by_site=policy_by_site,
            bootstrap=bootstrap,
            holm=holm,
            mechanical_holm_all_rejected=all(item.rejected for item in holm),
            _protocol=issued,
            _receipts=receipts,
        )
        _register(evidence)
        _require_issued_mechanical_statistics(evidence)
        return evidence
    except Exception:
        pass
    _fail()


def _require_issued_mechanical_statistics(value: object) -> _MechanicalStatisticsEvidence:
    valid = False
    try:
        if type(value) is not _MechanicalStatisticsEvidence:
            raise ValueError
        with _LOCK:
            record = _ISSUED.get(id(value))
        if (
            record is None
            or record.reference() is not value
            or value._protocol is not record.protocol
            or len(value._receipts) != len(record.receipts)
            or any(
                observed is not expected
                for observed, expected in zip(value._receipts, record.receipts, strict=True)
            )
            or _evidence_binding(value) != record.binding
        ):
            raise ValueError
        from human_feedback import evaluation_run_protocol as run_protocol
        from human_feedback import evaluation_runner as runner

        issued = run_protocol._require_issued_human_loso_execution_protocol(record.protocol)
        receipts = runner._sealed_human_loso_mechanical_batches(issued)
        if len(receipts) != len(record.receipts) or any(
            observed is not expected
            for observed, expected in zip(receipts, record.receipts, strict=True)
        ):
            raise ValueError
        final_binding = _evidence_binding(value)
        with _LOCK:
            current = _ISSUED.get(id(value))
            valid = (
                current is record
                and current.reference() is value
                and value._protocol is current.protocol
                and len(value._receipts) == len(current.receipts)
                and all(
                    observed is expected
                    for observed, expected in zip(value._receipts, current.receipts, strict=True)
                )
                and final_binding == current.binding
            )
    except Exception:
        valid = False
    if not valid:
        _fail()
    return value
