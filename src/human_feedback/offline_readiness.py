from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

from human_feedback.decision_policy import FeedbackCategory

EvaluationCategory = Literal[
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
]
EvidenceRole = Literal["characterization_only", "human_cross_site"]
ReadinessDecision = Literal[
    "CHARACTERIZATION_ONLY",
    "BLOCKED_INSUFFICIENT_EVIDENCE",
    "FAIL_SUPPLY",
    "FAIL_QUALITY",
    "ELIGIBLE_FOR_SHADOW_REVIEW",
]

CATEGORIES: tuple[EvaluationCategory, ...] = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)
SCIENTIFIC_SITES = frozenset({"cicytex", "pergamino", "melchor-romero"})
GIT_LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"


@dataclass(frozen=True, slots=True)
class SupplyArtifact:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.path or Path(self.path).is_absolute() or ".." in Path(self.path).parts:
            raise ValueError("artifact path must be safe and relative")
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ValueError("artifact sha256 must be a lowercase hexadecimal digest")
        if self.size_bytes < 0:
            raise ValueError("artifact size must not be negative")


@dataclass(frozen=True, slots=True)
class SupplyVerification:
    verified: bool
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SupplyIdentity:
    engine_package: str
    engine_version: str
    source_commit: str
    license: str
    checkpoint_repository: str
    checkpoint_revision: str
    artifacts: tuple[SupplyArtifact, ...]


@dataclass(frozen=True, slots=True)
class OfflineExample:
    example_id: str
    site_id: str
    group_id: str
    comment: str
    gold_category: EvaluationCategory

    def __post_init__(self) -> None:
        for name, value in (
            ("example_id", self.example_id),
            ("site_id", self.site_id),
            ("group_id", self.group_id),
            ("comment", self.comment),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.gold_category not in CATEGORIES:
            raise ValueError("gold category is invalid")


@dataclass(frozen=True, slots=True)
class CorpusEvidence:
    corpus_id: str
    evidence_role: EvidenceRole
    adjudicated: bool
    examples: tuple[OfflineExample, ...]

    def __post_init__(self) -> None:
        identifiers = [example.example_id for example in self.examples]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate example id")
        if self.evidence_role == "characterization_only" and self.adjudicated:
            raise ValueError("characterization corpus cannot claim adjudication")


@dataclass(frozen=True, slots=True)
class ReadinessPolicy:
    policy_id: str
    minimum_coverage: float
    minimum_accuracy: float
    minimum_selective_accuracy: float
    minimum_macro_f1: float
    maximum_brier: float
    maximum_ece: float
    maximum_mean_cost: float
    minimum_site_macro_f1: float
    maximum_p95_latency_ms: float

    def __post_init__(self) -> None:
        bounded = (
            self.minimum_coverage,
            self.minimum_accuracy,
            self.minimum_selective_accuracy,
            self.minimum_macro_f1,
            self.maximum_ece,
            self.minimum_site_macro_f1,
        )
        if any(not 0.0 <= value <= 1.0 for value in bounded):
            raise ValueError("rate thresholds must be between 0 and 1")
        if self.maximum_brier < 0 or self.maximum_mean_cost < 0:
            raise ValueError("loss thresholds must not be negative")
        if self.maximum_p95_latency_ms <= 0:
            raise ValueError("latency threshold must be positive")


@dataclass(frozen=True, slots=True)
class ReadinessContract:
    schema_version: str
    supply: SupplyIdentity
    corpus: CorpusEvidence
    policy: ReadinessPolicy

    def as_human_evidence_for_test(self) -> ReadinessContract:
        """Return an adjudicated variant for deterministic gate verification."""
        return replace(
            self,
            corpus=replace(self.corpus, evidence_role="human_cross_site", adjudicated=True),
        )

    def perfect_predictions(self) -> tuple[OfflinePrediction, ...]:
        return tuple(
            OfflinePrediction.perfect_for(
                example,
                model_revision=self.supply.checkpoint_revision,
            )
            for example in self.corpus.examples
        )


@dataclass(frozen=True, slots=True)
class OfflinePrediction:
    example_id: str
    category: FeedbackCategory
    probabilities: tuple[tuple[str, float], ...]
    latency_ms: float
    provider: str
    model_revision: str

    def __post_init__(self) -> None:
        if not self.example_id:
            raise ValueError("prediction example id must not be empty")
        if self.category not in (*CATEGORIES, "unclassified"):
            raise ValueError("prediction category is invalid")
        names = tuple(name for name, _ in self.probabilities)
        if names != CATEGORIES:
            raise ValueError("probabilities must follow the fixed category order")
        values = tuple(value for _, value in self.probabilities)
        if any(
            isinstance(value, bool) or not math.isfinite(value) or value < 0 for value in values
        ):
            raise ValueError("probabilities must be finite and non-negative")
        if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("probabilities must sum to 1")
        if not math.isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("latency must be finite and non-negative")
        if not self.provider or not self.model_revision:
            raise ValueError("provider and model revision are required")

    @property
    def abstained(self) -> bool:
        return self.category == "unclassified"

    @classmethod
    def perfect_for(
        cls,
        example: OfflineExample,
        *,
        model_revision: str,
    ) -> OfflinePrediction:
        return cls(
            example_id=example.example_id,
            category=example.gold_category,
            probabilities=tuple(
                (category, 1.0 if category == example.gold_category else 0.0)
                for category in CATEGORIES
            ),
            latency_ms=0.0,
            provider="recorded-contract-fixture",
            model_revision=model_revision,
        )


@dataclass(frozen=True, slots=True)
class BaselineSuggestion:
    category: FeedbackCategory
    probabilities: tuple[tuple[str, float], ...]
    abstained: bool


@dataclass(frozen=True, slots=True)
class ReadinessMetrics:
    total: int
    coverage: float
    accuracy: float
    selective_accuracy: float
    macro_f1: float
    brier: float
    ece: float
    mean_abstention_cost: float
    p50_latency_ms: float
    p95_latency_ms: float


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    schema_version: str
    decision: ReadinessDecision
    corpus_id: str
    corpus_digest: str
    policy_id: str
    policy_digest: str
    supply_verified: bool
    model_revision: str
    metrics: ReadinessMetrics
    metrics_by_site: tuple[tuple[str, ReadinessMetrics], ...]
    failed_gates: tuple[str, ...]
    production_enablement_authorized: bool = False
    human_review_required: bool = True


class DeterministicRuleBaseline:
    """Frozen, provider-independent comparator for offline evaluation."""

    _LEXICON: tuple[tuple[EvaluationCategory, tuple[str, ...]], ...] = (
        ("data_quality", ("sensor", "sonda", "salto", "faltante", "deriva", "pico")),
        ("model_behavior", ("modelo", "pronostico", "probabilidad", "prediccion")),
        ("agronomic_context", ("riego", "lluvia", "labor", "cultivo", "lote")),
        ("usability", ("pantalla", "interfaz", "flujo", "explicacion", "boton")),
        ("other", ("general", "adicional", "otro")),
    )

    def classify(self, site_id: str, comment: str) -> BaselineSuggestion:
        del site_id
        normalized = " ".join(unicodedata.normalize("NFKC", comment).casefold().split())
        scores = tuple(sum(1 for term in terms if term in normalized) for _, terms in self._LEXICON)
        denominator = sum(scores) + len(CATEGORIES)
        probabilities = tuple(
            (category, (score + 1) / denominator)
            for category, score in zip(CATEGORIES, scores, strict=True)
        )
        maximum = max(scores)
        winners = [index for index, score in enumerate(scores) if score == maximum]
        abstained = maximum == 0 or len(winners) != 1
        category: FeedbackCategory = "unclassified" if abstained else CATEGORIES[winners[0]]
        return BaselineSuggestion(
            category=category,
            probabilities=probabilities,
            abstained=abstained,
        )


def verify_supply_artifacts(
    artifacts: tuple[SupplyArtifact, ...],
    root: Path,
) -> SupplyVerification:
    failures: list[str] = []
    resolved_root = root.resolve()
    for expected in sorted(artifacts, key=lambda artifact: artifact.path):
        path = (resolved_root / expected.path).resolve()
        if resolved_root not in path.parents:
            failures.append(f"artifact_outside_root:{expected.path}")
            continue
        if not path.is_file():
            failures.append(f"artifact_missing:{expected.path}")
            continue
        payload = path.read_bytes()
        if payload.startswith(GIT_LFS_HEADER):
            failures.append(f"artifact_is_git_lfs_pointer:{expected.path}")
            continue
        if len(payload) != expected.size_bytes:
            failures.append(f"artifact_size_mismatch:{expected.path}")
        if hashlib.sha256(payload).hexdigest() != expected.sha256:
            failures.append(f"artifact_digest_mismatch:{expected.path}")
    return SupplyVerification(verified=not failures, failures=tuple(failures))


def compute_metrics(
    examples: tuple[OfflineExample, ...],
    predictions: tuple[OfflinePrediction, ...],
) -> ReadinessMetrics:
    if not examples:
        raise ValueError("evaluation requires at least one example")
    prediction_ids = [prediction.example_id for prediction in predictions]
    if len(prediction_ids) != len(set(prediction_ids)):
        raise ValueError("duplicate prediction id")
    example_ids = {example.example_id for example in examples}
    if set(prediction_ids) != example_ids:
        raise ValueError("prediction ids must match example ids exactly")
    by_id = {prediction.example_id: prediction for prediction in predictions}
    ordered_pairs = tuple((example, by_id[example.example_id]) for example in examples)

    total = len(ordered_pairs)
    answered = sum(not prediction.abstained for _, prediction in ordered_pairs)
    correct = sum(
        prediction.category == example.gold_category for example, prediction in ordered_pairs
    )
    answered_correct = sum(
        not prediction.abstained and prediction.category == example.gold_category
        for example, prediction in ordered_pairs
    )

    f1_values: list[float] = []
    for category in CATEGORIES:
        true_positive = sum(
            example.gold_category == category and prediction.category == category
            for example, prediction in ordered_pairs
        )
        false_positive = sum(
            example.gold_category != category and prediction.category == category
            for example, prediction in ordered_pairs
        )
        false_negative = sum(
            example.gold_category == category and prediction.category != category
            for example, prediction in ordered_pairs
        )
        denominator = 2 * true_positive + false_positive + false_negative
        f1_values.append(0.0 if denominator == 0 else 2 * true_positive / denominator)

    brier_total = 0.0
    ece_bins: list[list[tuple[float, float]]] = [[] for _ in range(10)]
    costs: list[float] = []
    latencies: list[float] = []
    for example, prediction in ordered_pairs:
        probabilities = dict(prediction.probabilities)
        brier_total += sum(
            (probabilities[category] - float(example.gold_category == category)) ** 2
            for category in CATEGORIES
        )
        confidence = max(probabilities.values())
        bin_index = min(int(confidence * 10), 9)
        ece_bins[bin_index].append(
            (confidence, float(prediction.category == example.gold_category))
        )
        costs.append(
            1.0
            if prediction.abstained
            else (0.0 if prediction.category == example.gold_category else 5.0)
        )
        latencies.append(prediction.latency_ms)

    ece = sum(
        len(values)
        / total
        * abs(
            sum(confidence for confidence, _ in values) / len(values)
            - sum(outcome for _, outcome in values) / len(values)
        )
        for values in ece_bins
        if values
    )
    latencies.sort()
    return ReadinessMetrics(
        total=total,
        coverage=answered / total,
        accuracy=correct / total,
        selective_accuracy=answered_correct / answered if answered else 0.0,
        macro_f1=sum(f1_values) / len(CATEGORIES),
        brier=brier_total / total,
        ece=ece,
        mean_abstention_cost=sum(costs) / total,
        p50_latency_ms=_nearest_rank(latencies, 0.50),
        p95_latency_ms=_nearest_rank(latencies, 0.95),
    )


def evaluate_readiness(
    contract: ReadinessContract,
    predictions: tuple[OfflinePrediction, ...],
    *,
    supply_verified: bool,
) -> ReadinessReport:
    scientific_examples = tuple(
        example for example in contract.corpus.examples if example.site_id in SCIENTIFIC_SITES
    )
    scientific_ids = {example.example_id for example in scientific_examples}
    scientific_predictions = tuple(
        prediction for prediction in predictions if prediction.example_id in scientific_ids
    )
    metrics = compute_metrics(scientific_examples, scientific_predictions)
    metrics_by_site = tuple(
        (
            site,
            compute_metrics(
                tuple(example for example in scientific_examples if example.site_id == site),
                tuple(
                    prediction
                    for prediction in scientific_predictions
                    if prediction.example_id
                    in {
                        example.example_id
                        for example in scientific_examples
                        if example.site_id == site
                    }
                ),
            ),
        )
        for site in sorted({example.site_id for example in scientific_examples})
    )
    failed_gates = _failed_quality_gates(metrics, metrics_by_site, contract.policy)

    if contract.corpus.evidence_role == "characterization_only":
        decision: ReadinessDecision = "CHARACTERIZATION_ONLY"
    elif (
        not contract.corpus.adjudicated
        or set(site for site, _ in metrics_by_site) != SCIENTIFIC_SITES
    ):
        decision = "BLOCKED_INSUFFICIENT_EVIDENCE"
    elif not supply_verified:
        decision = "FAIL_SUPPLY"
    elif failed_gates:
        decision = "FAIL_QUALITY"
    else:
        decision = "ELIGIBLE_FOR_SHADOW_REVIEW"

    return ReadinessReport(
        schema_version=contract.schema_version,
        decision=decision,
        corpus_id=contract.corpus.corpus_id,
        corpus_digest=_digest(contract.corpus),
        policy_id=contract.policy.policy_id,
        policy_digest=_digest(contract.policy),
        supply_verified=supply_verified,
        model_revision=contract.supply.checkpoint_revision,
        metrics=metrics,
        metrics_by_site=metrics_by_site,
        failed_gates=failed_gates,
    )


def canonical_report_bytes(report: ReadinessReport) -> bytes:
    return _canonical_bytes(asdict(report)) + b"\n"


def load_contract(path: Path) -> ReadinessContract:
    raw = json.loads(path.read_text(encoding="utf-8"))
    supply_raw = raw["supply"]
    engine = supply_raw["engine"]
    checkpoint = supply_raw["checkpoint"]
    supply = SupplyIdentity(
        engine_package=engine["package"],
        engine_version=engine["version"],
        source_commit=engine["source_commit"],
        license=engine["license"],
        checkpoint_repository=checkpoint["repository"],
        checkpoint_revision=checkpoint["revision"],
        artifacts=tuple(SupplyArtifact(**artifact) for artifact in checkpoint["files"]),
    )
    corpus_raw = raw["corpus"]
    corpus = CorpusEvidence(
        corpus_id=corpus_raw["corpus_id"],
        evidence_role=corpus_raw["evidence_role"],
        adjudicated=corpus_raw["adjudicated"],
        examples=tuple(OfflineExample(**example) for example in corpus_raw["examples"]),
    )
    return ReadinessContract(
        schema_version=raw["schema_version"],
        supply=supply,
        corpus=corpus,
        policy=ReadinessPolicy(**raw["policy"]),
    )


def _failed_quality_gates(
    metrics: ReadinessMetrics,
    metrics_by_site: tuple[tuple[str, ReadinessMetrics], ...],
    policy: ReadinessPolicy,
) -> tuple[str, ...]:
    failures: list[str] = []
    minimums = (
        ("minimum_coverage", metrics.coverage, policy.minimum_coverage),
        ("minimum_accuracy", metrics.accuracy, policy.minimum_accuracy),
        (
            "minimum_selective_accuracy",
            metrics.selective_accuracy,
            policy.minimum_selective_accuracy,
        ),
        ("minimum_macro_f1", metrics.macro_f1, policy.minimum_macro_f1),
    )
    failures.extend(name for name, observed, threshold in minimums if observed < threshold)
    maximums = (
        ("maximum_brier", metrics.brier, policy.maximum_brier),
        ("maximum_ece", metrics.ece, policy.maximum_ece),
        ("maximum_mean_cost", metrics.mean_abstention_cost, policy.maximum_mean_cost),
        (
            "maximum_p95_latency_ms",
            metrics.p95_latency_ms,
            policy.maximum_p95_latency_ms,
        ),
    )
    failures.extend(name for name, observed, threshold in maximums if observed > threshold)
    failures.extend(
        f"minimum_site_macro_f1:{site}"
        for site, site_metrics in metrics_by_site
        if site_metrics.macro_f1 < policy.minimum_site_macro_f1
    )
    return tuple(sorted(failures))


def _nearest_rank(values: list[float], quantile: float) -> float:
    rank = max(1, math.ceil(quantile * len(values)))
    return values[rank - 1]


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(asdict(value))).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
