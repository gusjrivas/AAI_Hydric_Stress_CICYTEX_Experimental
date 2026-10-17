"""Frozen, privacy-preserving preregistration for the human LOSO study.

The verifier in this module is deliberately a pure byte boundary.  It proves
that a closed preregistration binds a validated corpus, its deterministic LOSO
plan, and five supplied protocol artifacts.  It does not run the evaluation or
turn structural evidence into a scientific or operational approval.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import InitVar, dataclass, field
from datetime import datetime
from typing import Any

from human_feedback.evaluation_corpus import (
    CATEGORIES,
    REQUIRED_SITES,
    EvaluationCorpus,
    evaluation_corpus_digest,
)
from human_feedback.evaluation_split import LosoEvaluationPlan, loso_evaluation_plan_digest

SCHEMA_VERSION = "laya-human-evaluation-preregistration-v1"
REQUIRED_ARTIFACT_ROLES = (
    "sampling_protocol",
    "annotation_guide",
    "adjudication_protocol",
    "deidentification_protocol",
    "custody_record",
)

_PRIMARY_METRIC = "macro_f1"
_BASELINE_ID = "deterministic-rule-baseline-v1"
_COMPARISON_DESIGN = "same_loso_folds_paired_delta"
_MINIMUM_PAIRED_DELTA = 0.05
_BOOTSTRAP_METHOD = "stratified_cluster_percentile"
_BOOTSTRAP_UNIT = "group_within_site"
_BOOTSTRAP_REPLICATES = 10_000
_BOOTSTRAP_CONFIDENCE_LEVEL = 0.95
_MULTIPLICITY_CORRECTION = "holm"
_FAMILYWISE_ALPHA = 0.05
_LEGACY_POLICY_ID = "laya-readiness-policy-v1"
_LEGACY_THRESHOLDS: dict[str, float] = {
    "minimum_decision_confidence": 0.85,
    "minimum_coverage": 0.6,
    "minimum_accuracy": 0.7,
    "minimum_selective_accuracy": 0.8,
    "minimum_macro_f1": 0.65,
    "maximum_brier": 0.6,
    "maximum_ece": 0.1,
    "maximum_mean_cost": 1.0,
    "minimum_site_macro_f1": 0.55,
    "maximum_p95_latency_ms": 640.0,
}

_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_ROOT_FIELDS = frozenset(
    {
        "schema_version",
        "protocol_id",
        "frozen_at",
        "corpus_id",
        "evaluation_corpus_sha256",
        "loso_plan_sha256",
        "required_sites",
        "cohort",
        "analysis",
        "external_artifacts",
    }
)
_COHORT_FIELDS = frozenset(
    {
        "minimum_total_examples",
        "minimum_examples_per_site",
        "minimum_groups_per_site",
        "minimum_examples_per_site_category",
        "maximum_site_imbalance_ratio",
        "minimum_pre_adjudication_alpha_nominal",
    }
)
_ANALYSIS_FIELDS = frozenset(
    {
        "primary_metric",
        "baseline_id",
        "comparison_design",
        "minimum_paired_macro_f1_delta",
        "bootstrap_method",
        "bootstrap_unit",
        "bootstrap_replicates",
        "bootstrap_confidence_level",
        "bootstrap_seed",
        "multiplicity_correction",
        "familywise_alpha",
        "legacy_policy_id",
        "legacy_thresholds",
    }
)
_ARTIFACT_FIELDS = frozenset({"role", "artifact_id", "size_bytes", "sha256"})
_VERIFICATION_SEAL = object()


@dataclass(frozen=True, slots=True)
class ExternalArtifact:
    """One caller-supplied artifact; its bytes are always private in repr."""

    role: str
    content: bytes = field(repr=False)

    def __post_init__(self) -> None:
        _require_string(self.role, label="artifact role")
        if type(self.content) is not bytes:
            raise ValueError("artifact content must be bytes")


@dataclass(frozen=True, slots=True)
class VerifiedExternalArtifact:
    role: str
    artifact_id: str
    size_bytes: int
    sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CohortConstraints:
    minimum_total_examples: int
    minimum_examples_per_site: int
    minimum_groups_per_site: int
    minimum_examples_per_site_category: int
    maximum_site_imbalance_ratio: float
    minimum_pre_adjudication_alpha_nominal: float


@dataclass(frozen=True, slots=True)
class AnalysisProtocol:
    primary_metric: str
    baseline_id: str
    comparison_design: str
    minimum_paired_macro_f1_delta: float
    bootstrap_method: str
    bootstrap_unit: str
    bootstrap_replicates: int
    bootstrap_confidence_level: float
    bootstrap_seed: int
    multiplicity_correction: str
    familywise_alpha: float
    legacy_policy_id: str
    legacy_thresholds: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class HumanEvaluationPreregistration:
    """Verified structural authority; never an evaluation result or readiness gate."""

    schema_version: str
    protocol_id: str
    frozen_at: str
    corpus_id: str
    evaluation_corpus_sha256: str = field(repr=False)
    loso_plan_sha256: str = field(repr=False)
    required_sites: tuple[str, ...]
    cohort: CohortConstraints
    analysis: AnalysisProtocol
    artifacts: tuple[VerifiedExternalArtifact, ...] = field(repr=False)
    pre_adjudication_alpha_nominal: float
    corpus: EvaluationCorpus = field(repr=False)
    plan: LosoEvaluationPlan = field(repr=False)
    _verification_seal: InitVar[object]
    external_artifacts_verified: bool = field(default=True, init=False)
    cohort_constraints_satisfied: bool = field(default=True, init=False)
    evaluation_executed: bool = field(default=False, init=False)
    scientifically_sufficient: bool = field(default=False, init=False)
    eligible_for_shadow_review: bool = field(default=False, init=False)
    production_enablement_authorized: bool = field(default=False, init=False)

    def __post_init__(self, _verification_seal: object) -> None:
        if _verification_seal is not _VERIFICATION_SEAL:
            raise ValueError("verified authority requires the internal verification seal")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON object contains duplicate fields")
        result[key] = value
    return result


def _reject_non_finite(_value: str) -> None:
    raise ValueError("JSON non-finite numbers are not permitted")


def _decode_closed_json(payload: bytes) -> dict[str, Any]:
    if type(payload) is not bytes:
        raise ValueError("preregistration must be provided as bytes")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("preregistration JSON is invalid") from error
    return _require_object(value, _ROOT_FIELDS, kind="preregistration schema")


def _require_object(value: Any, fields: frozenset[str], *, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{kind} must contain exactly the contracted fields")
    return value


def _require_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty canonical string")
    return value


def _require_digest(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_positive_integer(value: Any, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _require_integer(value: Any, *, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    return value


def _require_number(value: Any, *, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _parse_utc(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError(f"{label} must be a canonical UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ValueError(f"{label} must be a valid UTC timestamp") from error


def _verify_bindings(
    raw: dict[str, Any], corpus: EvaluationCorpus, plan: LosoEvaluationPlan
) -> tuple[str, str, str, tuple[str, ...]]:
    if not isinstance(corpus, EvaluationCorpus):
        raise ValueError("evaluation corpus is invalid")
    if not isinstance(plan, LosoEvaluationPlan) or plan.corpus is not corpus:
        raise ValueError("LOSO plan must bind the supplied evaluation corpus")
    if raw["schema_version"] != SCHEMA_VERSION:
        raise ValueError("preregistration schema version is invalid")
    protocol_id = _require_string(raw["protocol_id"], label="protocol id")
    corpus_id = _require_string(raw["corpus_id"], label="corpus id")
    if corpus_id != corpus.corpus_id:
        raise ValueError("preregistration corpus id does not match corpus")
    corpus_digest = _require_digest(raw["evaluation_corpus_sha256"], label="corpus digest")
    if corpus_digest != evaluation_corpus_digest(corpus):
        raise ValueError("preregistration corpus digest does not match corpus")
    plan_digest = _require_digest(raw["loso_plan_sha256"], label="plan digest")
    if plan_digest != loso_evaluation_plan_digest(plan):
        raise ValueError("preregistration plan digest does not match plan")
    sites_raw = raw["required_sites"]
    if not isinstance(sites_raw, list) or any(not isinstance(site, str) for site in sites_raw):
        raise ValueError("required sites must be a JSON array of strings")
    sites = tuple(sites_raw)
    if sites != REQUIRED_SITES or sites != corpus.required_sites:
        raise ValueError("required sites do not match the canonical corpus sites")
    frozen_at = _require_string(raw["frozen_at"], label="frozen at")
    if _parse_utc(frozen_at, label="frozen at") < _parse_utc(
        corpus.frozen_at, label="corpus frozen at"
    ):
        raise ValueError("preregistration frozen time predates corpus frozen time")
    return protocol_id, frozen_at, corpus_digest, plan_digest


def _parse_cohort(value: Any) -> CohortConstraints:
    raw = _require_object(value, _COHORT_FIELDS, kind="cohort schema")
    ratio = _require_number(raw["maximum_site_imbalance_ratio"], label="cohort imbalance ratio")
    if ratio < 1.0:
        raise ValueError("cohort imbalance ratio must be at least one")
    alpha = _require_number(
        raw["minimum_pre_adjudication_alpha_nominal"], label="cohort agreement alpha"
    )
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("cohort agreement alpha threshold must be between zero and one")
    return CohortConstraints(
        minimum_total_examples=_require_positive_integer(
            raw["minimum_total_examples"], label="cohort total examples"
        ),
        minimum_examples_per_site=_require_positive_integer(
            raw["minimum_examples_per_site"], label="cohort site examples"
        ),
        minimum_groups_per_site=_require_positive_integer(
            raw["minimum_groups_per_site"], label="cohort groups per site"
        ),
        minimum_examples_per_site_category=_require_positive_integer(
            raw["minimum_examples_per_site_category"], label="cohort site/category cell"
        ),
        maximum_site_imbalance_ratio=ratio,
        minimum_pre_adjudication_alpha_nominal=alpha,
    )


def _parse_analysis(value: Any) -> AnalysisProtocol:
    raw = _require_object(value, _ANALYSIS_FIELDS, kind="analysis schema")
    exact = {
        "primary_metric": _PRIMARY_METRIC,
        "baseline_id": _BASELINE_ID,
        "comparison_design": _COMPARISON_DESIGN,
        "bootstrap_method": _BOOTSTRAP_METHOD,
        "bootstrap_unit": _BOOTSTRAP_UNIT,
        "multiplicity_correction": _MULTIPLICITY_CORRECTION,
        "legacy_policy_id": _LEGACY_POLICY_ID,
    }
    for name, expected in exact.items():
        if raw[name] != expected or not isinstance(raw[name], str):
            raise ValueError(f"analysis {name.replace('_', ' ')} is invalid")
    delta = _require_number(raw["minimum_paired_macro_f1_delta"], label="paired macro F1 delta")
    if delta != _MINIMUM_PAIRED_DELTA:
        raise ValueError("paired macro F1 delta is not the preregistered value")
    replicates = _require_positive_integer(
        raw["bootstrap_replicates"], label="bootstrap replicates"
    )
    if replicates != _BOOTSTRAP_REPLICATES:
        raise ValueError("bootstrap replicates are not the preregistered value")
    confidence = _require_number(
        raw["bootstrap_confidence_level"], label="bootstrap confidence level"
    )
    if confidence != _BOOTSTRAP_CONFIDENCE_LEVEL:
        raise ValueError("bootstrap confidence level is not the preregistered value")
    seed = _require_integer(raw["bootstrap_seed"], label="bootstrap seed")
    if seed < 0:
        raise ValueError("bootstrap seed must be non-negative")
    familywise_alpha = _require_number(raw["familywise_alpha"], label="familywise alpha")
    if familywise_alpha != _FAMILYWISE_ALPHA:
        raise ValueError("familywise alpha is not the preregistered value")

    thresholds_raw = _require_object(
        raw["legacy_thresholds"], frozenset(_LEGACY_THRESHOLDS), kind="legacy thresholds"
    )
    thresholds: list[tuple[str, float]] = []
    for name, expected in _LEGACY_THRESHOLDS.items():
        observed = _require_number(thresholds_raw[name], label=f"legacy threshold {name}")
        if observed != expected:
            raise ValueError(f"legacy threshold {name} is not the preregistered value")
        thresholds.append((name, observed))
    return AnalysisProtocol(
        primary_metric=_PRIMARY_METRIC,
        baseline_id=_BASELINE_ID,
        comparison_design=_COMPARISON_DESIGN,
        minimum_paired_macro_f1_delta=delta,
        bootstrap_method=_BOOTSTRAP_METHOD,
        bootstrap_unit=_BOOTSTRAP_UNIT,
        bootstrap_replicates=replicates,
        bootstrap_confidence_level=confidence,
        bootstrap_seed=seed,
        multiplicity_correction=_MULTIPLICITY_CORRECTION,
        familywise_alpha=familywise_alpha,
        legacy_policy_id=_LEGACY_POLICY_ID,
        legacy_thresholds=tuple(thresholds),
    )


def _artifact_corpus_bindings(corpus: EvaluationCorpus) -> dict[str, tuple[str | None, str]]:
    return {
        "sampling_protocol": (corpus.sampling_protocol_id, corpus.sampling_protocol_sha256),
        "annotation_guide": (corpus.annotation_guide_id, corpus.annotation_guide_sha256),
        "adjudication_protocol": (
            corpus.adjudication_protocol_id,
            corpus.adjudication_protocol_sha256,
        ),
        "deidentification_protocol": (
            corpus.deidentification_protocol_id,
            corpus.deidentification_protocol_sha256,
        ),
        "custody_record": (None, corpus.custody_digest),
    }


def _verify_artifacts(
    value: Any,
    external_artifacts: tuple[ExternalArtifact, ...],
    corpus: EvaluationCorpus,
) -> tuple[VerifiedExternalArtifact, ...]:
    if not isinstance(value, list) or len(value) != len(REQUIRED_ARTIFACT_ROLES):
        raise ValueError("external artifact manifest must contain exactly five roles")
    if not isinstance(external_artifacts, tuple) or any(
        not isinstance(item, ExternalArtifact) for item in external_artifacts
    ):
        raise ValueError("external artifacts must be a tuple of ExternalArtifact values")
    supplied = {item.role: item for item in external_artifacts}
    if len(supplied) != len(external_artifacts) or set(supplied) != set(REQUIRED_ARTIFACT_ROLES):
        raise ValueError("external artifact roles must be exact and unique")

    declared: dict[str, dict[str, Any]] = {}
    for item in value:
        raw = _require_object(item, _ARTIFACT_FIELDS, kind="external artifact schema")
        role = _require_string(raw["role"], label="artifact role")
        if role in declared:
            raise ValueError("external artifact roles must be unique")
        declared[role] = raw
    if set(declared) != set(REQUIRED_ARTIFACT_ROLES):
        raise ValueError("external artifact roles must be exact")

    bindings = _artifact_corpus_bindings(corpus)
    verified: list[VerifiedExternalArtifact] = []
    for role in REQUIRED_ARTIFACT_ROLES:
        raw = declared[role]
        artifact_id = _require_string(raw["artifact_id"], label=f"{role} artifact id")
        size = _require_positive_integer(raw["size_bytes"], label=f"{role} artifact size")
        digest = _require_digest(raw["sha256"], label=f"{role} artifact digest")
        actual = supplied[role].content
        if size != len(actual):
            raise ValueError(f"{role} artifact size does not match supplied bytes")
        if digest != hashlib.sha256(actual).hexdigest():
            raise ValueError(f"{role} artifact digest does not match supplied bytes")
        expected_id, expected_digest = bindings[role]
        if expected_id is not None and artifact_id != expected_id:
            raise ValueError(f"{role} artifact id does not match corpus")
        if digest != expected_digest:
            raise ValueError(f"{role} artifact digest does not match corpus")
        verified.append(
            VerifiedExternalArtifact(
                role=role, artifact_id=artifact_id, size_bytes=size, sha256=digest
            )
        )
    return tuple(verified)


def _krippendorff_alpha_nominal(corpus: EvaluationCorpus) -> float:
    """Return nominal alpha from original annotations using coincidence weights."""

    coincidence: Counter[tuple[str, str]] = Counter()
    marginals: Counter[str] = Counter()
    observations = 0.0
    for record in corpus.records:
        values = [annotation.category for annotation in record.annotations]
        count = len(values)
        if count < 2:
            raise ValueError("agreement alpha requires at least two annotations per example")
        weight = 1.0 / (count - 1)
        for first_index, first in enumerate(values):
            for second_index, second in enumerate(values):
                if first_index != second_index:
                    coincidence[first, second] += weight
                    marginals[first] += weight
                    observations += weight
    if observations <= 1.0:
        raise ValueError("agreement alpha has insufficient annotation support")
    observed_disagreement = (
        sum(amount for (first, second), amount in coincidence.items() if first != second)
        / observations
    )
    expected_disagreement = sum(
        first_count * second_count
        for first, first_count in marginals.items()
        for second, second_count in marginals.items()
        if first != second
    ) / (observations * (observations - 1.0))
    if expected_disagreement == 0.0:
        if observed_disagreement == 0.0:
            return 1.0
        raise ValueError("agreement alpha is undefined")
    return 1.0 - observed_disagreement / expected_disagreement


def _verify_cohort(corpus: EvaluationCorpus, cohort: CohortConstraints) -> float:
    if corpus.records_count < cohort.minimum_total_examples:
        raise ValueError("cohort total examples are below the preregistered minimum")
    site_counts = Counter(record.site_id for record in corpus.records)
    if any(site_counts[site] < cohort.minimum_examples_per_site for site in REQUIRED_SITES):
        raise ValueError("cohort site example count is below the preregistered minimum")
    group_counts = {
        site: len({record.group_id for record in corpus.records if record.site_id == site})
        for site in REQUIRED_SITES
    }
    if any(count < cohort.minimum_groups_per_site for count in group_counts.values()):
        raise ValueError("cohort group count is below the preregistered minimum")
    cell_counts = Counter((record.site_id, record.gold_category) for record in corpus.records)
    if any(
        cell_counts[site, category] < cohort.minimum_examples_per_site_category
        for site in REQUIRED_SITES
        for category in CATEGORIES
    ):
        raise ValueError("cohort site/category cell is below the preregistered minimum")
    if max(site_counts.values()) / min(site_counts.values()) > cohort.maximum_site_imbalance_ratio:
        raise ValueError("cohort site imbalance exceeds the preregistered ratio")
    alpha = _krippendorff_alpha_nominal(corpus)
    if alpha < cohort.minimum_pre_adjudication_alpha_nominal:
        raise ValueError("pre-adjudication agreement alpha is below the preregistered minimum")
    return alpha


def verify_human_evaluation_preregistration(
    preregistration_bytes: bytes,
    corpus: EvaluationCorpus,
    plan: LosoEvaluationPlan,
    external_artifacts: tuple[ExternalArtifact, ...],
) -> HumanEvaluationPreregistration:
    """Verify a frozen manifest against already validated private inputs."""

    raw = _decode_closed_json(preregistration_bytes)
    protocol_id, frozen_at, corpus_digest, plan_digest = _verify_bindings(raw, corpus, plan)
    cohort = _parse_cohort(raw["cohort"])
    analysis = _parse_analysis(raw["analysis"])
    artifacts = _verify_artifacts(raw["external_artifacts"], external_artifacts, corpus)
    alpha = _verify_cohort(corpus, cohort)
    return HumanEvaluationPreregistration(
        schema_version=SCHEMA_VERSION,
        protocol_id=protocol_id,
        frozen_at=frozen_at,
        corpus_id=corpus.corpus_id,
        evaluation_corpus_sha256=corpus_digest,
        loso_plan_sha256=plan_digest,
        required_sites=tuple(raw["required_sites"]),
        cohort=cohort,
        analysis=analysis,
        artifacts=artifacts,
        pre_adjudication_alpha_nominal=alpha,
        corpus=corpus,
        plan=plan,
        _verification_seal=_VERIFICATION_SEAL,
    )


def _summary(protocol: HumanEvaluationPreregistration) -> dict[str, Any]:
    if not isinstance(protocol, HumanEvaluationPreregistration):
        raise ValueError("human evaluation preregistration is invalid")
    return {
        "schema_version": protocol.schema_version,
        "protocol_id": protocol.protocol_id,
        "frozen_at": protocol.frozen_at,
        "corpus_id": protocol.corpus_id,
        "evaluation_corpus_sha256": protocol.evaluation_corpus_sha256,
        "loso_plan_sha256": protocol.loso_plan_sha256,
        "required_sites": list(protocol.required_sites),
        "cohort": {
            "minimum_total_examples": protocol.cohort.minimum_total_examples,
            "minimum_examples_per_site": protocol.cohort.minimum_examples_per_site,
            "minimum_groups_per_site": protocol.cohort.minimum_groups_per_site,
            "minimum_examples_per_site_category": (
                protocol.cohort.minimum_examples_per_site_category
            ),
            "maximum_site_imbalance_ratio": protocol.cohort.maximum_site_imbalance_ratio,
            "minimum_pre_adjudication_alpha_nominal": (
                protocol.cohort.minimum_pre_adjudication_alpha_nominal
            ),
            "observed_total_examples": protocol.corpus.records_count,
            "observed_examples_per_site": {
                site: sum(record.site_id == site for record in protocol.corpus.records)
                for site in protocol.required_sites
            },
            "observed_pre_adjudication_alpha_nominal": (protocol.pre_adjudication_alpha_nominal),
        },
        "analysis": {
            "primary_metric": protocol.analysis.primary_metric,
            "baseline_id": protocol.analysis.baseline_id,
            "comparison_design": protocol.analysis.comparison_design,
            "minimum_paired_macro_f1_delta": (protocol.analysis.minimum_paired_macro_f1_delta),
            "bootstrap_method": protocol.analysis.bootstrap_method,
            "bootstrap_unit": protocol.analysis.bootstrap_unit,
            "bootstrap_replicates": protocol.analysis.bootstrap_replicates,
            "bootstrap_confidence_level": protocol.analysis.bootstrap_confidence_level,
            "bootstrap_seed": protocol.analysis.bootstrap_seed,
            "multiplicity_correction": protocol.analysis.multiplicity_correction,
            "familywise_alpha": protocol.analysis.familywise_alpha,
            "legacy_policy_id": protocol.analysis.legacy_policy_id,
            "legacy_thresholds": dict(protocol.analysis.legacy_thresholds),
        },
        "external_artifacts": [
            {
                "role": artifact.role,
                "artifact_id": artifact.artifact_id,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for artifact in protocol.artifacts
        ],
        "external_artifacts_verified": protocol.external_artifacts_verified,
        "cohort_constraints_satisfied": protocol.cohort_constraints_satisfied,
        "evaluation_executed": protocol.evaluation_executed,
        "scientifically_sufficient": protocol.scientifically_sufficient,
        "eligible_for_shadow_review": protocol.eligible_for_shadow_review,
        "production_enablement_authorized": protocol.production_enablement_authorized,
    }


def canonical_human_evaluation_preregistration_summary_bytes(
    protocol: HumanEvaluationPreregistration,
) -> bytes:
    """Return deterministic public evidence without per-record private data."""

    return json.dumps(
        _summary(protocol),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def human_evaluation_preregistration_evidence_digest(
    protocol: HumanEvaluationPreregistration,
) -> str:
    """Digest the canonical public preregistration evidence."""

    return hashlib.sha256(
        canonical_human_evaluation_preregistration_summary_bytes(protocol)
    ).hexdigest()
