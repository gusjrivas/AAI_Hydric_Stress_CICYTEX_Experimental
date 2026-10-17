"""Adversarial REDs for bounded mechanical statistics inputs."""

from __future__ import annotations

import math

import pytest

from human_feedback.evaluation_corpus import CATEGORIES, REQUIRED_SITES
from human_feedback.evaluation_statistics import (
    _BootstrapSummary,
    _holm_step_down,
    _MechanicalPair,
    _nearest_rank_95,
    _paired_group_bootstrap,
    _raw_metrics,
)


def _probabilities(value: float = 0.2):
    return tuple((category, value) for category in CATEGORIES)


def _pair(**overrides):
    values = {
        "site_id": REQUIRED_SITES[0],
        "group_id": "group-1",
        "gold_category": CATEGORIES[0],
        "laya_category": CATEGORIES[0],
        "laya_probabilities": _probabilities(),
        "baseline_category": CATEGORIES[0],
        "baseline_probabilities": _probabilities(),
    }
    values.update(overrides)
    return _MechanicalPair(**values)


@pytest.mark.parametrize("source", ("", "caller", True, None))
def test_metric_source_is_closed(source):
    with pytest.raises(ValueError):
        _raw_metrics((_pair(),), source=source)


@pytest.mark.parametrize(
    "overrides",
    (
        {"site_id": "foreign"},
        {"group_id": ""},
        {"gold_category": "unclassified"},
        {"laya_category": "unclassified"},
        {"baseline_category": "foreign"},
        {"laya_probabilities": tuple(reversed(_probabilities()))},
        {"laya_probabilities": _probabilities(True)},
        {"laya_probabilities": _probabilities(math.nan)},
        {"laya_probabilities": _probabilities(-0.1)},
        {"laya_probabilities": _probabilities(0.2002)},
    ),
)
def test_pair_rejects_open_categories_and_invalid_v2_probabilities(overrides):
    with pytest.raises(ValueError):
        _pair(**overrides)


def test_pair_accepts_v2_rounded_mass_and_selected_argmax_tie():
    probabilities = (
        (CATEGORIES[0], 0.3),
        (CATEGORIES[1], 0.3),
        *((category, 0.1334) for category in CATEGORIES[2:]),
    )
    pair = _pair(laya_category=CATEGORIES[1], laya_probabilities=probabilities)
    assert pair.laya_probabilities is probabilities


@pytest.mark.parametrize(
    "values",
    ((), (True,), (math.nan,), (math.inf,), ("private",)),
)
def test_nearest_rank_rejects_empty_boolean_nonfinite_or_non_numeric(values):
    with pytest.raises(ValueError):
        _nearest_rank_95(values)


def test_bootstrap_rejects_missing_sites_and_bounds_rows_and_groups_before_sampling():
    with pytest.raises(ValueError):
        _paired_group_bootstrap((_pair(),))

    too_many_rows = tuple(_pair(group_id=f"g-{index % 512}") for index in range(1537))
    with pytest.raises(ValueError):
        _paired_group_bootstrap(too_many_rows)

    too_many_groups = tuple(
        _pair(site_id=site, group_id=f"g-{index}")
        for site in REQUIRED_SITES
        for index in range(513)
    )
    with pytest.raises(ValueError):
        _paired_group_bootstrap(too_many_groups)


def _summary(hypothesis, p_value=0.01, replicates=10_000):
    return _BootstrapSummary(
        hypothesis=hypothesis,
        observed_delta=0.0,
        lower=-0.1,
        upper=0.1,
        tail_probability=p_value,
        replicate_count=replicates,
    )


def test_holm_rejects_open_family_boolean_nonfinite_and_wrong_replicate_count():
    family = (
        "global_equal_site_macro_f1_superiority",
        "cicytex_macro_f1_noninferiority",
        "melchor-romero_macro_f1_noninferiority",
        "pergamino_macro_f1_noninferiority",
    )
    invalid_families = (
        tuple(_summary(name) for name in family[:-1]),
        tuple(_summary(name) for name in (*family[:-1], family[0])),
        tuple(_summary(name, True) for name in family),
        tuple(_summary(name, math.nan) for name in family),
        tuple(_summary(name, replicates=9_999) for name in family),
    )
    for invalid in invalid_families:
        with pytest.raises(ValueError):
            _holm_step_down(invalid)


def test_issued_evidence_rechecks_binding_after_deep_receipt_validation(monkeypatch, tmp_path):
    from human_feedback import evaluation_runner as runner
    from human_feedback import evaluation_statistics as module
    from tests.test_laya_statistics_boundary import _authorize, _executed_protocol

    _runner, protocol, receipts = _executed_protocol(monkeypatch, tmp_path)
    _authorize(module, monkeypatch)
    evidence = module._run_laya_mechanical_statistics_fixture(protocol)
    original = evidence.raw_laya.macro_f1

    def mutate_after_precheck(_protocol):
        object.__setattr__(evidence.raw_laya, "macro_f1", original + 0.25)
        return receipts

    monkeypatch.setattr(runner, "_sealed_human_loso_mechanical_batches", mutate_after_precheck)
    try:
        with pytest.raises(ValueError):
            module._require_issued_mechanical_statistics(evidence)
    finally:
        object.__setattr__(evidence.raw_laya, "macro_f1", original)
