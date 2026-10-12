import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "laya" / "readiness_contract_v1.json"
CATEGORIES = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)


def _supply_verification(contract):
    from human_feedback.offline_readiness import SupplyVerification, supply_identity_digest

    return SupplyVerification(
        verified=True,
        failures=(),
        supply_digest=supply_identity_digest(contract.supply),
    )


def _perfect_predictions(contract):
    from human_feedback.offline_readiness import OfflinePrediction

    return tuple(
        OfflinePrediction(
            example_id=example.example_id,
            category=example.gold_category,
            probabilities=tuple(
                (category, 1.0 if category == example.gold_category else 0.0)
                for category in CATEGORIES
            ),
            latency_ms=1.0,
            provider="laya-http",
            model_revision=contract.supply.checkpoint_revision,
        )
        for example in contract.corpus.examples
    )


def _example(example_id: str, gold: str, site: str = "cicytex"):
    from human_feedback.offline_readiness import OfflineExample

    return OfflineExample(
        example_id=example_id,
        site_id=site,
        group_id=example_id,
        comment=f"comment-{example_id}",
        gold_category=gold,
    )


def _prediction(
    example_id: str,
    category: str,
    probabilities: tuple[float, ...],
    latency_ms: float,
):
    from human_feedback.offline_readiness import OfflinePrediction

    return OfflinePrediction(
        example_id=example_id,
        category=category,
        probabilities=tuple(zip(CATEGORIES, probabilities, strict=True)),
        latency_ms=latency_ms,
        provider="laya-http",
        model_revision="55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851",
    )


def test_contract_fixture_is_versioned_complete_and_never_scientific_evidence():
    from human_feedback.offline_readiness import load_contract

    contract = load_contract(FIXTURE)

    assert contract.schema_version == "laya-offline-readiness-v1"
    assert contract.corpus.evidence_role == "characterization_only"
    assert contract.corpus.adjudicated is False
    assert {example.site_id for example in contract.corpus.examples} == {
        "cicytex",
        "pergamino",
        "melchor-romero",
        "laboratorio-mock",
    }
    for site in {example.site_id for example in contract.corpus.examples}:
        assert {
            example.gold_category for example in contract.corpus.examples if example.site_id == site
        } == set(CATEGORIES)
    assert len({example.example_id for example in contract.corpus.examples}) == len(
        contract.corpus.examples
    )


def test_supply_verification_accepts_real_bytes_and_rejects_lfs_pointers(tmp_path: Path):
    from human_feedback.offline_readiness import SupplyArtifact, verify_supply_artifacts

    payload = b"real-model-bytes"
    artifact = tmp_path / "model.safetensors"
    artifact.write_bytes(payload)
    expected = SupplyArtifact(
        path="model.safetensors",
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )

    assert verify_supply_artifacts((expected,), tmp_path).verified is True

    artifact.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204\n"
        "size 643835514\n",
        encoding="utf-8",
    )
    result = verify_supply_artifacts(
        (replace(expected, size_bytes=artifact.stat().st_size),), tmp_path
    )
    assert result.verified is False
    assert result.failures == ("artifact_is_git_lfs_pointer:model.safetensors",)


def test_rule_baseline_is_deterministic_site_agnostic_and_abstains_on_ties():
    from human_feedback.offline_readiness import DeterministicRuleBaseline

    baseline = DeterministicRuleBaseline()
    first = baseline.classify("cicytex", "La SONDA tiene un salto imposible")
    second = baseline.classify("pergamino", "  la sonda tiene un salto imposible  ")
    tied = baseline.classify("cicytex", "sensor modelo")

    assert first == second
    assert first.category == "data_quality"
    assert pytest.approx(sum(value for _, value in first.probabilities)) == 1.0
    assert tied.category == "unclassified"
    assert tied.abstained is True


def test_metric_vector_matches_a_hand_calculated_multiclass_example():
    from human_feedback.offline_readiness import compute_metrics

    examples = tuple(_example(f"e{i}", category) for i, category in enumerate(CATEGORIES))
    predictions = (
        _prediction("e0", "data_quality", (0.9, 0.025, 0.025, 0.025, 0.025), 10),
        _prediction("e1", "usability", (0.05, 0.05, 0.05, 0.8, 0.05), 20),
        _prediction("e2", "unclassified", (0.2, 0.2, 0.2, 0.2, 0.2), 30),
        _prediction("e3", "usability", (0.1, 0.1, 0.1, 0.6, 0.1), 40),
        _prediction("e4", "other", (0.075, 0.075, 0.075, 0.075, 0.7), 50),
    )

    metrics = compute_metrics(examples, predictions)

    assert metrics.total == 5
    assert metrics.coverage == pytest.approx(0.8)
    assert metrics.accuracy == pytest.approx(0.6)
    assert metrics.selective_accuracy == pytest.approx(0.75)
    assert metrics.macro_f1 == pytest.approx(0.5333333333333333)
    assert metrics.brier == pytest.approx(0.535)
    assert metrics.ece == pytest.approx(0.36)
    assert metrics.mean_abstention_cost == pytest.approx(1.2)
    assert metrics.p50_latency_ms == pytest.approx(30.0)
    assert metrics.p95_latency_ms == pytest.approx(50.0)


def test_predictions_fail_closed_on_missing_extra_duplicate_or_invalid_probability():
    from human_feedback.offline_readiness import compute_metrics

    examples = (_example("e0", "data_quality"),)
    valid = _prediction("e0", "data_quality", (0.9, 0.025, 0.025, 0.025, 0.025), 1)

    with pytest.raises(ValueError, match="prediction ids"):
        compute_metrics(examples, ())
    with pytest.raises(ValueError, match="prediction ids"):
        compute_metrics(examples, (valid, replace(valid, example_id="extra")))
    with pytest.raises(ValueError, match="duplicate prediction"):
        compute_metrics(examples, (valid, valid))
    with pytest.raises(ValueError, match="sum to 1"):
        replace(valid, probabilities=tuple(zip(CATEGORIES, (0.9, 0.1, 0.1, 0.1, 0.1))))


def test_synthetic_contract_is_only_characterization_and_report_is_canonical():
    from human_feedback.offline_readiness import (
        canonical_report_bytes,
        evaluate_readiness,
        load_contract,
    )

    contract = load_contract(FIXTURE)
    predictions = _perfect_predictions(contract)
    verification = _supply_verification(contract)

    report_a = evaluate_readiness(contract, predictions, supply_verification=verification)
    report_b = evaluate_readiness(
        contract,
        tuple(reversed(predictions)),
        supply_verification=verification,
    )

    assert report_a.decision == "CHARACTERIZATION_ONLY"
    assert report_a.production_enablement_authorized is False
    assert report_a.human_review_required is True
    assert canonical_report_bytes(report_a) == canonical_report_bytes(report_b)
    decoded = json.loads(canonical_report_bytes(report_a))
    assert "comment" not in canonical_report_bytes(report_a).decode("utf-8")
    assert decoded["production_enablement_authorized"] is False


def test_human_evidence_cannot_hide_a_failed_site_behind_the_global_average():
    from human_feedback.offline_readiness import evaluate_readiness, load_contract

    contract = load_contract(FIXTURE)
    contract = replace(
        contract,
        corpus=replace(contract.corpus, evidence_role="human_cross_site", adjudicated=True),
    )
    predictions = _perfect_predictions(contract)
    predictions = tuple(
        (
            replace(
                prediction,
                category="other",
                probabilities=tuple(
                    (category, 1.0 if category == "other" else 0.0) for category in CATEGORIES
                ),
            )
            if prediction.example_id.startswith("m-")
            else prediction
        )
        for prediction in predictions
    )

    report = evaluate_readiness(
        contract,
        predictions,
        supply_verification=_supply_verification(contract),
    )

    assert report.decision == "BLOCKED_SCIENTIFIC_METHOD_PENDING"
    assert "minimum_site_macro_f1:melchor-romero" in report.failed_gates
    assert report.production_enablement_authorized is False


def test_readiness_module_is_not_imported_by_operational_or_scientific_flows():
    repository = Path(__file__).parents[1]
    forbidden_roots = (
        repository / "backend",
        repository / "src" / "data_ingestion",
        repository / "src" / "predictive_modeling",
        repository / "src" / "experiment_runner",
    )
    offenders = []
    for root in forbidden_roots:
        for path in root.rglob("*.py"):
            if "human_feedback.offline_readiness" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []
