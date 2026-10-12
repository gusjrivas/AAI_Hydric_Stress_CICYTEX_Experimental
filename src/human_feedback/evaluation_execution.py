"""Fail-closed evidence contract for offline LOSO prediction batches.

The objects in this module validate the shape and provenance of prediction
evidence.  They do not execute a model, attest that an evaluation ran, or make
the evidence eligible for scientific or operational use.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from human_feedback.evaluation_corpus import CATEGORIES, evaluation_corpus_digest
from human_feedback.evaluation_split import (
    LosoEvaluationPlan,
    loso_evaluation_plan_digest,
)

SCHEMA_VERSION = "laya-loso-execution-contract-v1"
RUNTIME_IDENTITY_SCHEMA_VERSION = "laya-runtime-identity-v1"
LAYA_PROVIDER = "laya-http"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _require_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty canonical string")
    return value


def _require_digest(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_finite_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return 0.0 if number == 0.0 else number


def _require_model_revision(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
        or value == "0" * 40
    ):
        raise ValueError("model revision must be a non-null lowercase SHA-1 digest")
    return value


@dataclass(frozen=True, slots=True)
class RuntimeIdentityRef:
    """Opaque reference to a separately validated runtime identity."""

    schema_version: str
    sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != RUNTIME_IDENTITY_SCHEMA_VERSION:
            raise ValueError("runtime identity schema version is invalid")
        _require_digest(self.sha256, label="runtime identity digest")
        if self.sha256 == "0" * 64:
            raise ValueError("runtime identity digest cannot use the null sentinel")


@dataclass(frozen=True, slots=True)
class LosoExecutionContract:
    """Immutable binding between a LOSO plan and execution provenance."""

    schema_version: str
    plan: LosoEvaluationPlan = field(repr=False)
    loso_plan_sha256: str = field(repr=False)
    evaluation_corpus_sha256: str = field(repr=False)
    runtime_identity: RuntimeIdentityRef
    execution_protocol_id: str
    execution_protocol_sha256: str
    model_revision: str
    provider: str
    structurally_valid: bool = field(default=True, init=False)
    execution_completed: bool = field(default=False, init=False)
    scientifically_sufficient: bool = field(default=False, init=False)
    eligible_for_shadow_review: bool = field(default=False, init=False)
    production_enablement_authorized: bool = field(default=False, init=False)
    runtime_identity_verified: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)
    gold_blind_execution_attested: bool = field(default=False, init=False)
    supply_identity_verified: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("execution contract schema version is invalid")
        if not isinstance(self.plan, LosoEvaluationPlan):
            raise ValueError("execution contract plan is invalid")
        if not isinstance(self.runtime_identity, RuntimeIdentityRef):
            raise ValueError("execution contract runtime identity is invalid")

        _require_digest(self.loso_plan_sha256, label="plan digest")
        if self.loso_plan_sha256 != loso_evaluation_plan_digest(self.plan):
            raise ValueError("plan digest does not match evaluation plan")

        _require_digest(self.evaluation_corpus_sha256, label="evaluation corpus digest")
        if self.evaluation_corpus_sha256 != evaluation_corpus_digest(self.plan.corpus):
            raise ValueError("evaluation corpus digest does not match plan")

        _require_string(self.execution_protocol_id, label="execution protocol id")
        _require_digest(self.execution_protocol_sha256, label="execution protocol digest")
        if self.execution_protocol_sha256 == "0" * 64:
            raise ValueError("execution protocol digest cannot use the null sentinel")
        _require_model_revision(self.model_revision)
        if self.provider != LAYA_PROVIDER:
            raise ValueError("execution provider must be laya-http")


def build_loso_execution_contract(
    plan: LosoEvaluationPlan,
    *,
    runtime_identity: RuntimeIdentityRef,
    execution_protocol_id: str,
    execution_protocol_sha256: str,
    model_revision: str,
    provider: str,
) -> LosoExecutionContract:
    """Bind a validated plan to declared, non-executing provenance metadata."""

    if not isinstance(plan, LosoEvaluationPlan):
        raise ValueError("evaluation plan is invalid")
    return LosoExecutionContract(
        schema_version=SCHEMA_VERSION,
        plan=plan,
        loso_plan_sha256=loso_evaluation_plan_digest(plan),
        evaluation_corpus_sha256=evaluation_corpus_digest(plan.corpus),
        runtime_identity=runtime_identity,
        execution_protocol_id=execution_protocol_id,
        execution_protocol_sha256=execution_protocol_sha256,
        model_revision=model_revision,
        provider=provider,
    )


@dataclass(frozen=True, slots=True, repr=False)
class RawLosoPrediction:
    """One private prediction row whose identity and values stay out of repr."""

    held_out_site: str
    example_id: str = field(repr=False)
    category: str
    probabilities: tuple[tuple[str, float], ...] = field(repr=False)
    answer_confidence: float | None = field(repr=False)
    latency_ms: float = field(repr=False)
    provider: str
    model_revision: str

    def __post_init__(self) -> None:
        _require_string(self.held_out_site, label="prediction fold")
        _require_string(self.example_id, label="prediction example")
        if self.category not in CATEGORIES:
            raise ValueError("prediction category is invalid; unclassified is not permitted")
        if not isinstance(self.probabilities, tuple) or len(self.probabilities) != len(CATEGORIES):
            raise ValueError("prediction probabilities must cover every category")

        probability_categories: list[object] = []
        probability_values: list[float] = []
        for item in self.probabilities:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("prediction probabilities must be ordered category pairs")
            category, raw_value = item
            probability_categories.append(category)
            value = _require_finite_number(raw_value, label="prediction probability")
            if value < 0.0 or value > 1.0:
                raise ValueError("prediction probability must be between zero and one")
            probability_values.append(value)

        if tuple(probability_categories) != CATEGORIES:
            raise ValueError("prediction probability category order is invalid")
        if not math.isclose(sum(probability_values), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("prediction probabilities must sum to one")
        maximum = max(probability_values)
        winners = [
            category
            for category, value in zip(CATEGORIES, probability_values, strict=True)
            if value == maximum
        ]
        if len(winners) != 1 or winners[0] != self.category:
            raise ValueError("prediction category must be the unique probability argmax")

        object.__setattr__(
            self,
            "probabilities",
            tuple(zip(CATEGORIES, probability_values, strict=True)),
        )

        if self.answer_confidence is not None:
            confidence = _require_finite_number(
                self.answer_confidence, label="prediction confidence"
            )
            if confidence < 0.0 or confidence > 1.0:
                raise ValueError("prediction confidence must be between zero and one")
            object.__setattr__(self, "answer_confidence", confidence)
        latency = _require_finite_number(self.latency_ms, label="prediction latency")
        if latency < 0.0:
            raise ValueError("prediction latency must not be negative")
        object.__setattr__(self, "latency_ms", latency)
        if self.provider != LAYA_PROVIDER:
            raise ValueError("prediction provider must be laya-http")
        _require_model_revision(self.model_revision)


def _canonical_prediction_order(
    contract: LosoExecutionContract,
    predictions: tuple[RawLosoPrediction, ...],
) -> tuple[RawLosoPrediction, ...]:
    site_order = {fold.held_out_site: index for index, fold in enumerate(contract.plan.folds)}
    return tuple(
        sorted(
            predictions,
            key=lambda prediction: (
                site_order.get(prediction.held_out_site, len(site_order)),
                prediction.example_id,
            ),
        )
    )


def _validate_predictions(
    contract: LosoExecutionContract,
    predictions: object,
) -> tuple[RawLosoPrediction, ...]:
    if not isinstance(contract, LosoExecutionContract):
        raise ValueError("prediction contract is invalid")
    if not isinstance(predictions, tuple) or not predictions:
        raise ValueError("prediction evidence must be a non-empty tuple")
    if any(not isinstance(item, RawLosoPrediction) for item in predictions):
        raise ValueError("prediction evidence contains invalid rows")
    typed_predictions = predictions
    if any(
        prediction.provider != contract.provider
        or prediction.model_revision != contract.model_revision
        for prediction in typed_predictions
    ):
        raise ValueError("prediction provider or model does not match contract")

    expected = {
        (fold.held_out_site, record.example_id)
        for fold in contract.plan.folds
        for record in fold.test_records
    }
    actual = [(prediction.held_out_site, prediction.example_id) for prediction in typed_predictions]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("prediction coverage must match every fold test record exactly once")
    return _canonical_prediction_order(contract, typed_predictions)


def _private_prediction_content_digest(
    predictions: tuple[RawLosoPrediction, ...],
) -> str:
    payload = {
        "domain": "laya-loso-prediction-content-v1",
        "rows": [
            {
                "held_out_site": prediction.held_out_site,
                "example_id": prediction.example_id,
                "category": prediction.category,
                "probabilities": [list(item) for item in prediction.probabilities],
                "answer_confidence": prediction.answer_confidence,
                "latency_ms": prediction.latency_ms,
                "provider": prediction.provider,
                "model_revision": prediction.model_revision,
            }
            for prediction in predictions
        ],
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class ValidatedLosoPredictionSet:
    """Structurally validated evidence that remains fail-closed for all uses."""

    contract: LosoExecutionContract
    predictions: tuple[RawLosoPrediction, ...] = field(repr=False)
    prediction_content_sha256: str = field(repr=False)
    execution_evidence_validated: bool = field(default=True, init=False)
    execution_completed: bool = field(default=False, init=False)
    scientifically_sufficient: bool = field(default=False, init=False)
    eligible_for_shadow_review: bool = field(default=False, init=False)
    production_enablement_authorized: bool = field(default=False, init=False)
    runtime_identity_verified: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)
    gold_blind_execution_attested: bool = field(default=False, init=False)
    supply_identity_verified: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        canonical = _validate_predictions(self.contract, self.predictions)
        if self.predictions != canonical:
            raise ValueError("prediction evidence is not in canonical order")
        _require_digest(self.prediction_content_sha256, label="prediction content commitment")
        if self.prediction_content_sha256 == "0" * 64:
            raise ValueError("prediction content commitment cannot use the null sentinel")
        if self.prediction_content_sha256 != _private_prediction_content_digest(canonical):
            raise ValueError("prediction content commitment does not match evidence")


def validate_loso_prediction_set(
    contract: LosoExecutionContract,
    predictions: tuple[RawLosoPrediction, ...],
) -> ValidatedLosoPredictionSet:
    """Validate exact outer-test coverage and return canonical private evidence."""

    canonical = _validate_predictions(contract, predictions)
    return ValidatedLosoPredictionSet(
        contract=contract,
        predictions=canonical,
        prediction_content_sha256=_private_prediction_content_digest(canonical),
    )


def canonical_loso_execution_summary_bytes(
    evidence: ValidatedLosoPredictionSet,
) -> bytes:
    """Return a deterministic public summary without private corpus rows."""

    if not isinstance(evidence, ValidatedLosoPredictionSet):
        raise ValueError("execution evidence is invalid")
    latencies = [prediction.latency_ms for prediction in evidence.predictions]
    payload = {
        "schema_version": evidence.contract.schema_version,
        "runtime_identity_schema_version": evidence.contract.runtime_identity.schema_version,
        "runtime_identity_sha256": evidence.contract.runtime_identity.sha256,
        "execution_protocol_id": evidence.contract.execution_protocol_id,
        "execution_protocol_sha256": evidence.contract.execution_protocol_sha256,
        "model_revision": evidence.contract.model_revision,
        "provider": evidence.contract.provider,
        "predictions_count": len(evidence.predictions),
        "latency_ms_summary": {
            "count": len(latencies),
            "minimum": min(latencies),
            "maximum": max(latencies),
            "mean": sum(latencies) / len(latencies),
        },
        "structurally_valid": evidence.contract.structurally_valid,
        "execution_evidence_validated": evidence.execution_evidence_validated,
        "execution_completed": evidence.execution_completed,
        "scientifically_sufficient": evidence.scientifically_sufficient,
        "eligible_for_shadow_review": evidence.eligible_for_shadow_review,
        "production_enablement_authorized": evidence.production_enablement_authorized,
        "runtime_identity_verified": evidence.runtime_identity_verified,
        "origin_verified": evidence.origin_verified,
        "gold_blind_execution_attested": evidence.gold_blind_execution_attested,
        "supply_identity_verified": evidence.supply_identity_verified,
    }
    return _canonical_json_bytes(payload)


def loso_execution_evidence_digest(evidence: ValidatedLosoPredictionSet) -> str:
    """Return the SHA-256 identity of the safe public execution summary."""

    return hashlib.sha256(canonical_loso_execution_summary_bytes(evidence)).hexdigest()
