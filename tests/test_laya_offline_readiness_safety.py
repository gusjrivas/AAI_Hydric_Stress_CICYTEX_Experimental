import math
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_laya_offline_readiness import (
    CATEGORIES,
    FIXTURE,
    _perfect_predictions,
    _supply_verification,
)


def test_production_contract_exposes_no_fixture_promotion_or_perfect_prediction_helpers():
    from human_feedback.offline_readiness import OfflinePrediction, ReadinessContract

    assert not hasattr(ReadinessContract, "as_human_evidence_for_test")
    assert not hasattr(ReadinessContract, "perfect_predictions")
    assert not hasattr(OfflinePrediction, "perfect_for")


def test_gate_rejects_caller_asserted_supply_boolean():
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    with pytest.raises(TypeError, match="SupplyVerification"):
        evaluate_readiness(
            contract,
            _perfect_predictions(contract),
            supply_verification=True,
        )


def test_gate_rejects_predictions_not_bound_to_the_pinned_checkpoint():
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    predictions = _perfect_predictions(contract)
    predictions = (replace(predictions[0], model_revision="different-checkpoint"), *predictions[1:])

    with pytest.raises(ValueError, match="model revision"):
        evaluate_readiness(
            contract,
            predictions,
            supply_verification=_supply_verification(contract),
        )


def test_gate_rejects_extra_predictions_before_scientific_site_filtering():
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    predictions = _perfect_predictions(contract)
    extra = replace(predictions[0], example_id="unknown-extra")

    with pytest.raises(ValueError, match="prediction ids"):
        evaluate_readiness(
            contract,
            (*predictions, extra),
            supply_verification=_supply_verification(contract),
        )


def test_quality_targets_cannot_claim_shadow_readiness_before_scientific_protocol():
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    promoted = replace(
        contract,
        corpus=replace(contract.corpus, evidence_role="human_cross_site", adjudicated=True),
    )

    report = evaluate_readiness(
        promoted,
        _perfect_predictions(promoted),
        supply_verification=_supply_verification(promoted),
    )

    assert report.decision == "BLOCKED_SCIENTIFIC_METHOD_PENDING"
    assert "human_cross_site_protocol_not_implemented" in report.failed_gates
    assert report.production_enablement_authorized is False


def test_non_finite_policy_thresholds_are_rejected():
    from human_feedback.offline_readiness import ReadinessPolicy

    with pytest.raises(ValueError, match="finite"):
        ReadinessPolicy(
            policy_id="invalid",
            minimum_coverage=0.6,
            minimum_accuracy=0.7,
            minimum_selective_accuracy=0.8,
            minimum_macro_f1=0.65,
            maximum_brier=math.nan,
            maximum_ece=0.1,
            maximum_mean_cost=1.0,
            minimum_site_macro_f1=0.55,
            maximum_p95_latency_ms=640.0,
        )


def test_empty_supply_artifact_set_never_verifies(tmp_path: Path):
    from human_feedback.offline_readiness import verify_supply_artifacts

    result = verify_supply_artifacts((), tmp_path)

    assert result.verified is False
    assert result.failures == ("supply_manifest_has_no_artifacts",)


def test_declared_choice_must_match_unique_probability_argmax():
    from human_feedback.offline_readiness import OfflinePrediction

    with pytest.raises(ValueError, match="argmax"):
        OfflinePrediction(
            example_id="e1",
            category="model_behavior",
            probabilities=tuple(zip(CATEGORIES, (0.9, 0.025, 0.025, 0.025, 0.025), strict=True)),
            latency_ms=1.0,
            provider="laya-http",
            model_revision="revision",
        )
