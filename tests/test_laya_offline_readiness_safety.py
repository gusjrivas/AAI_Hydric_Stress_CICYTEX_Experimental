import math
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_laya_offline_readiness import (
    CATEGORIES,
    FIXTURE,
    _materialize_supply,
    _perfect_predictions,
)


def test_production_contract_exposes_no_fixture_promotion_or_perfect_prediction_helpers():
    from human_feedback.offline_readiness import OfflinePrediction, ReadinessContract

    assert not hasattr(ReadinessContract, "as_human_evidence_for_test")
    assert not hasattr(ReadinessContract, "perfect_predictions")
    assert not hasattr(OfflinePrediction, "perfect_for")


def test_gate_rejects_caller_asserted_supply_boolean():
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    with pytest.raises(TypeError, match="unexpected keyword"):
        evaluate_readiness(
            contract,
            _perfect_predictions(contract),
            supply_verified=True,
        )


def test_gate_rejects_predictions_not_bound_to_the_pinned_checkpoint(tmp_path: Path):
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    contract, artifact_root = _materialize_supply(contract, tmp_path)
    predictions = _perfect_predictions(contract)
    predictions = (replace(predictions[0], model_revision="different-checkpoint"), *predictions[1:])

    with pytest.raises(ValueError, match="model revision"):
        evaluate_readiness(
            contract,
            predictions,
            artifact_root=artifact_root,
        )


def test_gate_rejects_extra_predictions_before_scientific_site_filtering(tmp_path: Path):
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    contract, artifact_root = _materialize_supply(contract, tmp_path)
    predictions = _perfect_predictions(contract)
    extra = replace(predictions[0], example_id="unknown-extra")

    with pytest.raises(ValueError, match="prediction ids"):
        evaluate_readiness(
            contract,
            (*predictions, extra),
            artifact_root=artifact_root,
        )


def test_quality_targets_cannot_claim_shadow_readiness_before_scientific_protocol(
    tmp_path: Path,
):
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    promoted = replace(
        contract,
        corpus=replace(contract.corpus, evidence_role="human_cross_site", adjudicated=True),
    )
    promoted, artifact_root = _materialize_supply(promoted, tmp_path)

    report = evaluate_readiness(
        promoted,
        _perfect_predictions(promoted),
        artifact_root=artifact_root,
    )

    assert report.decision == "BLOCKED_SCIENTIFIC_METHOD_PENDING"
    assert "human_cross_site_protocol_not_implemented" in report.failed_gates
    assert report.production_enablement_authorized is False


def test_non_finite_policy_thresholds_are_rejected():
    from human_feedback.offline_readiness import ReadinessPolicy

    with pytest.raises(ValueError, match="finite"):
        ReadinessPolicy(
            policy_id="invalid",
            minimum_decision_confidence=0.85,
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
            answer_confidence=0.9,
            latency_ms=1.0,
            provider="laya-http",
            model_revision="revision",
        )


def test_gate_applies_the_same_exact_confidence_boundary_as_production(
    tmp_path: Path,
):
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    contract, artifact_root = _materialize_supply(contract, tmp_path)
    predictions = list(_perfect_predictions(contract))
    predictions[0] = replace(
        predictions[0],
        probabilities=tuple(zip(CATEGORIES, (0.9, 0.025, 0.025, 0.025, 0.025), strict=True)),
        answer_confidence=0.84,
    )
    predictions[1] = replace(
        predictions[1],
        probabilities=tuple(zip(CATEGORIES, (0.05, 0.8, 0.05, 0.05, 0.05), strict=True)),
        answer_confidence=0.85,
    )

    report = evaluate_readiness(
        contract,
        tuple(predictions),
        artifact_root=artifact_root,
    )

    assert report.metrics.coverage == pytest.approx(14 / 15)


def test_report_digest_changes_when_verified_supply_identity_changes(tmp_path: Path):
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    original = load_contract(FIXTURE)
    contract_a, root_a = _materialize_supply(original, tmp_path / "a", marker="a")
    contract_b, root_b = _materialize_supply(original, tmp_path / "b", marker="b")

    report_a = evaluate_readiness(
        contract_a,
        _perfect_predictions(contract_a),
        artifact_root=root_a,
    )
    report_b = evaluate_readiness(
        contract_b,
        _perfect_predictions(contract_b),
        artifact_root=root_b,
    )

    assert report_a.supply_digest != report_b.supply_digest


def test_offline_confidence_uses_answer_confidence_before_choice_probability(
    tmp_path: Path,
):
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    contract, artifact_root = _materialize_supply(contract, tmp_path)
    predictions = list(_perfect_predictions(contract))
    predictions[0] = replace(
        predictions[0],
        probabilities=tuple(zip(CATEGORIES, (0.9, 0.025, 0.025, 0.025, 0.025), strict=True)),
        answer_confidence=0.84,
    )
    predictions[1] = replace(
        predictions[1],
        probabilities=tuple(zip(CATEGORIES, (0.04, 0.84, 0.04, 0.04, 0.04), strict=True)),
        answer_confidence=0.90,
    )

    report = evaluate_readiness(
        contract,
        tuple(predictions),
        artifact_root=artifact_root,
    )

    assert report.metrics.coverage == pytest.approx(14 / 15)


def test_shared_confidence_resolver_matches_laya_response_precedence():
    from human_feedback.decision_confidence import resolve_choice_confidence

    assert (
        resolve_choice_confidence(
            answer_confidence=0.84,
            probabilities={"data_quality": 0.90},
            choice="data_quality",
        )
        == 0.84
    )
    assert (
        resolve_choice_confidence(
            answer_confidence=None,
            probabilities={"data_quality": 0.90},
            choice="data_quality",
        )
        == 0.90
    )
