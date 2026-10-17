from __future__ import annotations

import math

import pytest

from human_feedback.evaluation_corpus import CATEGORIES, REQUIRED_SITES
from human_feedback.evaluation_statistics import (
    _BootstrapSummary,
    _holm_step_down,
    _legacy_policy_diagnostics,
    _MechanicalPair,
    _nearest_rank_95,
    _paired_group_bootstrap,
    _raw_metrics,
)


def _probabilities(choice: str, confidence: float) -> tuple[tuple[str, float], ...]:
    remainder = (1.0 - confidence) / (len(CATEGORIES) - 1)
    return tuple(
        (category, confidence if category == choice else remainder) for category in CATEGORIES
    )


def _one_hot(choice: str) -> tuple[tuple[str, float], ...]:
    return tuple((category, float(category == choice)) for category in CATEGORIES)


def _pair(
    *,
    site_id: str,
    group_id: str,
    gold: str,
    laya: str,
    baseline: str,
    laya_probabilities: tuple[tuple[str, float], ...] | None = None,
    baseline_probabilities: tuple[tuple[str, float], ...] | None = None,
) -> _MechanicalPair:
    return _MechanicalPair(
        site_id=site_id,
        group_id=group_id,
        gold_category=gold,
        laya_category=laya,
        laya_probabilities=(_one_hot(laya) if laya_probabilities is None else laya_probabilities),
        baseline_category=baseline,
        baseline_probabilities=(
            _one_hot(baseline)
            if baseline_probabilities is None and baseline in CATEGORIES
            else (
                tuple((category, 0.2) for category in CATEGORIES)
                if baseline_probabilities is None
                else baseline_probabilities
            )
        ),
    )


def test_raw_metrics_keep_five_labels_and_count_abstention_as_false_negative() -> None:
    rows = tuple(
        _pair(
            site_id="cicytex",
            group_id="g-1",
            gold=category,
            laya=category,
            baseline="unclassified",
        )
        for category in CATEGORIES
    )

    laya = _raw_metrics(rows, source="laya")
    baseline = _raw_metrics(rows, source="baseline")

    assert laya.total == 5
    assert (laya.accuracy, laya.macro_f1, laya.brier, laya.ece) == (1.0, 1.0, 0.0, 0.0)
    assert baseline.total == 5
    assert baseline.accuracy == 0.0
    assert baseline.macro_f1 == 0.0
    assert baseline.brier == pytest.approx(0.8)
    assert baseline.ece == pytest.approx(0.2)


def test_raw_macro_f1_uses_fixed_labels_and_zero_for_missing_classes() -> None:
    row = _pair(
        site_id="cicytex",
        group_id="g-1",
        gold=CATEGORIES[0],
        laya=CATEGORIES[0],
        baseline="unclassified",
    )

    metrics = _raw_metrics((row,), source="laya")

    assert metrics.accuracy == 1.0
    assert metrics.macro_f1 == pytest.approx(0.2)


def test_raw_metrics_preserve_rounded_ties_without_renormalizing() -> None:
    tied = (
        (CATEGORIES[0], 0.3),
        (CATEGORIES[1], 0.3),
        *[(item, 0.1333) for item in CATEGORIES[2:]],
    )
    row = _pair(
        site_id="cicytex",
        group_id="g-1",
        gold=CATEGORIES[0],
        laya=CATEGORIES[1],
        baseline=CATEGORIES[0],
        laya_probabilities=tuple(tied),
    )

    metrics = _raw_metrics((row,), source="laya")

    expected_brier = 0.3**2 + (0.3 - 1.0) ** 2 + 3 * 0.1333**2
    assert metrics.accuracy == 0.0
    assert metrics.brier == pytest.approx(expected_brier)
    assert metrics.ece == pytest.approx(0.3)


def test_policy_diagnostics_use_selected_probability_fallback_without_calibration() -> None:
    rows = tuple(
        _pair(
            site_id="cicytex",
            group_id=f"g-{index}",
            gold=category,
            laya=category,
            baseline="unclassified",
            laya_probabilities=_probabilities(category, 0.9 if index < 3 else 0.8),
        )
        for index, category in enumerate(CATEGORIES)
    )

    laya = _legacy_policy_diagnostics(rows, source="laya")
    baseline = _legacy_policy_diagnostics(rows, source="baseline")

    assert laya.total == 5
    assert laya.coverage == pytest.approx(0.6)
    assert laya.selective_accuracy == 1.0
    assert laya.accuracy == pytest.approx(0.6)
    assert laya.macro_f1 == pytest.approx(0.6)
    assert laya.mean_cost == pytest.approx(0.4)
    assert laya.confidence_source == "selected_probability_fallback"
    assert laya.calibrated is False
    assert baseline.coverage == 0.0
    assert baseline.selective_accuracy == 0.0
    assert baseline.accuracy == 0.0
    assert baseline.macro_f1 == 0.0
    assert baseline.mean_cost == 1.0


def test_ece_weights_bins_by_row_count_and_places_confidence_one_in_last_bin() -> None:
    specifications = (
        (CATEGORIES[0], CATEGORIES[0], 1.0),
        (CATEGORIES[1], CATEGORIES[1], 0.9),
        (CATEGORIES[2], CATEGORIES[2], 0.9),
        (CATEGORIES[4], CATEGORIES[3], 0.6),
    )
    rows = tuple(
        _pair(
            site_id="cicytex",
            group_id=f"g-{index}",
            gold=gold,
            laya=choice,
            baseline="unclassified",
            laya_probabilities=_probabilities(choice, confidence),
        )
        for index, (gold, choice, confidence) in enumerate(specifications)
    )

    metrics = _raw_metrics(rows, source="laya")

    # Bin 9 contains confidences 1.0, 0.9 and 0.9, all correct; bin 6
    # contains one incorrect prediction at 0.6.  ECE is row-weighted, not
    # the unweighted average of the two bin errors.
    assert metrics.ece == pytest.approx(0.2)


def test_nearest_rank_interval_has_no_interpolation() -> None:
    values = tuple(float(value) for value in range(1, 41))

    assert _nearest_rank_95(values) == (1.0, 39.0)


def _variable_group_rows() -> tuple[_MechanicalPair, ...]:
    rows: list[_MechanicalPair] = []
    for site in REQUIRED_SITES:
        for group_id, laya_is_good in (("a-good", True), ("b-bad", False)):
            for index, gold in enumerate(CATEGORIES):
                wrong = CATEGORIES[(index + 1) % len(CATEGORIES)]
                rows.append(
                    _pair(
                        site_id=site,
                        group_id=group_id,
                        gold=gold,
                        laya=gold if laya_is_good else wrong,
                        baseline=wrong if laya_is_good else gold,
                    )
                )
    return tuple(rows)


def test_paired_cluster_bootstrap_matches_frozen_mt19937_profile() -> None:
    summaries = _paired_group_bootstrap(_variable_group_rows())
    by_hypothesis = {summary.hypothesis: summary for summary in summaries}

    assert tuple(by_hypothesis) == (
        "global_equal_site_macro_f1_superiority",
        "cicytex_macro_f1_noninferiority",
        "melchor-romero_macro_f1_noninferiority",
        "pergamino_macro_f1_noninferiority",
    )
    global_summary = by_hypothesis["global_equal_site_macro_f1_superiority"]
    assert global_summary.observed_delta == 0.0
    assert global_summary.lower == pytest.approx(-2.0 / 3.0)
    assert global_summary.upper == pytest.approx(2.0 / 3.0)
    assert global_summary.tail_probability == pytest.approx(6528 / 10001)
    assert global_summary.replicate_count == 10_000

    expected_site_tails = {
        "cicytex_macro_f1_noninferiority": 2486 / 10001,
        "melchor-romero_macro_f1_noninferiority": 2496 / 10001,
        "pergamino_macro_f1_noninferiority": 2516 / 10001,
    }
    for hypothesis, expected_tail in expected_site_tails.items():
        summary = by_hypothesis[hypothesis]
        assert summary.observed_delta == 0.0
        assert (summary.lower, summary.upper) == (-1.0, 1.0)
        assert summary.tail_probability == pytest.approx(expected_tail)
        assert summary.replicate_count == 10_000


def test_global_estimand_gives_sites_equal_weight_when_row_counts_differ() -> None:
    rows: list[_MechanicalPair] = []
    for site, repetitions, laya_is_better in (
        ("cicytex", 1, True),
        ("melchor-romero", 20, False),
        ("pergamino", 2, False),
    ):
        for repetition in range(repetitions):
            for index, gold in enumerate(CATEGORIES):
                wrong = CATEGORIES[(index + 1) % len(CATEGORIES)]
                rows.append(
                    _pair(
                        site_id=site,
                        group_id="only-group",
                        gold=gold,
                        laya=gold if laya_is_better else gold,
                        baseline=wrong if laya_is_better else gold,
                    )
                )

    summaries = _paired_group_bootstrap(tuple(rows))

    assert summaries[0].hypothesis == "global_equal_site_macro_f1_superiority"
    assert summaries[0].observed_delta == pytest.approx(1.0 / 3.0)


def test_bootstrap_samples_unequal_groups_as_paired_clusters_not_rows() -> None:
    rows: list[_MechanicalPair] = []
    for site in REQUIRED_SITES:
        if site == "cicytex":
            group_specs = (("small-good", 1, True), ("large-bad", 10, False))
        else:
            group_specs = (("only-neutral", 1, None),)
        for group_id, repetitions, laya_is_better in group_specs:
            for _ in range(repetitions):
                for index, gold in enumerate(CATEGORIES):
                    wrong = CATEGORIES[(index + 1) % len(CATEGORIES)]
                    if laya_is_better is True:
                        laya, baseline = gold, wrong
                    elif laya_is_better is False:
                        laya, baseline = wrong, gold
                    else:
                        laya = baseline = gold
                    rows.append(
                        _pair(
                            site_id=site,
                            group_id=group_id,
                            gold=gold,
                            laya=laya,
                            baseline=baseline,
                        )
                    )

    summaries = _paired_group_bootstrap(tuple(rows))
    by_hypothesis = {summary.hypothesis: summary for summary in summaries}

    global_summary = by_hypothesis["global_equal_site_macro_f1_superiority"]
    site_summary = by_hypothesis["cicytex_macro_f1_noninferiority"]
    assert global_summary.observed_delta == pytest.approx(-3.0 / 11.0)
    assert (global_summary.lower, global_summary.upper) == pytest.approx((-1.0 / 3.0, 1.0 / 3.0))
    assert global_summary.tail_probability == pytest.approx(7531 / 10001)
    assert site_summary.observed_delta == pytest.approx(-9.0 / 11.0)
    assert (site_summary.lower, site_summary.upper) == (-1.0, 1.0)
    assert site_summary.tail_probability == pytest.approx(7531 / 10001)


def test_tail_probability_counts_replicates_exactly_equal_to_site_margin() -> None:
    rows: list[_MechanicalPair] = []
    for site in REQUIRED_SITES:
        for index, gold in enumerate(CATEGORIES):
            wrong = CATEGORIES[(index + 1) % len(CATEGORIES)]
            for repetition in range(50):
                rows.append(
                    _pair(
                        site_id=site,
                        group_id="only-group",
                        gold=gold,
                        laya=wrong,
                        baseline=gold if repetition == 0 else wrong,
                    )
                )

    summaries = _paired_group_bootstrap(tuple(rows))

    for summary in summaries[1:]:
        assert summary.observed_delta == -0.02
        assert summary.tail_probability == 1.0


def _summary(hypothesis: str, p_value: float) -> _BootstrapSummary:
    return _BootstrapSummary(
        hypothesis=hypothesis,
        observed_delta=0.0,
        lower=-0.1,
        upper=0.1,
        tail_probability=p_value,
        replicate_count=10_000,
    )


def test_holm_orders_ties_by_family_index_and_requires_all_four() -> None:
    summaries = (
        _summary("global_equal_site_macro_f1_superiority", 0.01),
        _summary("cicytex_macro_f1_noninferiority", 0.01),
        _summary("melchor-romero_macro_f1_noninferiority", 0.04),
        _summary("pergamino_macro_f1_noninferiority", 0.001),
    )

    decisions = _holm_step_down(summaries)

    assert tuple(item.hypothesis for item in decisions) == (
        "pergamino_macro_f1_noninferiority",
        "global_equal_site_macro_f1_superiority",
        "cicytex_macro_f1_noninferiority",
        "melchor-romero_macro_f1_noninferiority",
    )
    assert tuple(item.threshold for item in decisions) == pytest.approx(
        (0.05 / 4, 0.05 / 3, 0.05 / 2, 0.05)
    )
    assert all(item.rejected for item in decisions)


def test_holm_stops_after_first_non_rejection() -> None:
    summaries = (
        _summary("global_equal_site_macro_f1_superiority", 0.02),
        _summary("cicytex_macro_f1_noninferiority", 0.03),
        _summary("melchor-romero_macro_f1_noninferiority", 0.04),
        _summary("pergamino_macro_f1_noninferiority", 0.001),
    )

    decisions = _holm_step_down(summaries)

    assert tuple(item.rejected for item in decisions) == (True, False, False, False)
    assert all(math.isfinite(item.threshold) for item in decisions)


def test_holm_rejects_when_p_value_equals_step_down_boundary() -> None:
    summaries = (
        _summary("global_equal_site_macro_f1_superiority", 0.0125),
        _summary("cicytex_macro_f1_noninferiority", 0.0125),
        _summary("melchor-romero_macro_f1_noninferiority", 0.0125),
        _summary("pergamino_macro_f1_noninferiority", 0.0125),
    )

    decisions = _holm_step_down(summaries)

    assert decisions[0].threshold == 0.0125
    assert all(item.rejected for item in decisions)
