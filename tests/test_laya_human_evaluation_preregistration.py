import hashlib
import inspect
import json
from copy import deepcopy
from dataclasses import fields, replace
from pathlib import Path

import pytest

from human_feedback.evaluation_preregistration import (
    ExternalArtifact,
    canonical_human_evaluation_preregistration_summary_bytes,
    human_evaluation_preregistration_evidence_digest,
    verify_human_evaluation_preregistration,
)

SITES = ("cicytex", "melchor-romero", "pergamino")
CATEGORIES = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)
ROLES = (
    "sampling_protocol",
    "annotation_guide",
    "adjudication_protocol",
    "deidentification_protocol",
    "custody_record",
)
LEGACY_THRESHOLDS = {
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


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _artifact_payloads() -> dict[str, bytes]:
    return {role: f"synthetic-{role}-v1\n".encode() for role in ROLES}


def _records(*, disagree: bool = False) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for site_index, site in enumerate(SITES):
        for index in range(20):
            category = CATEGORIES[index % len(CATEGORIES)]
            second = CATEGORIES[(index + 1) % len(CATEGORIES)] if disagree else category
            annotations = [
                {"annotator_id": f"reviewer-{site_index}-{index}-a", "category": category},
                {"annotator_id": f"reviewer-{site_index}-{index}-b", "category": second},
            ]
            records.append(
                {
                    "example_id": f"private-example-{site}-{index}",
                    "site_id": site,
                    "group_id": f"private-group-{site}-{index // 5}",
                    "comment": f"Private human observation {site_index}-{index}",
                    "annotations": annotations,
                    "adjudication": (
                        {
                            "adjudicator_id": f"private-adjudicator-{site_index}-{index}",
                            "category": category,
                            "decision_ref": f"private-decision-{site_index}-{index}",
                        }
                        if disagree
                        else None
                    ),
                    "gold_category": category,
                }
            )
    return records


def _corpus_manifest(records: list[dict[str, object]], payloads: dict[str, bytes]):
    normalized = deepcopy(records)
    for record in normalized:
        record["annotations"].sort(key=lambda item: item["annotator_id"])
    normalized.sort(key=lambda item: item["example_id"])

    def digest(role: str) -> str:
        return hashlib.sha256(payloads[role]).hexdigest()

    return {
        "schema_version": "laya-human-evaluation-corpus-v1",
        "corpus_id": "private-human-cross-site-v1",
        "evidence_role": "human_corpus_candidate",
        "records_count": len(records),
        "records_sha256": hashlib.sha256(_canonical(normalized)).hexdigest(),
        "required_sites": list(SITES),
        "minimum_annotators_per_example": 2,
        "adjudication_policy": "agreement_or_explicit_adjudication",
        "rubric_version": "feedback-rubric-v1",
        "sampling_protocol_id": "sampling-cross-site-v1",
        "sampling_protocol_sha256": digest("sampling_protocol"),
        "annotation_guide_id": "annotation-guide-v1",
        "annotation_guide_sha256": digest("annotation_guide"),
        "adjudication_protocol_id": "adjudication-v1",
        "adjudication_protocol_sha256": digest("adjudication_protocol"),
        "deidentification_protocol_id": "deidentification-v1",
        "deidentification_protocol_sha256": digest("deidentification_protocol"),
        "custody_digest": digest("custody_record"),
        "frozen_at": "2026-10-17T00:00:00Z",
        "declared_source_kind": "human_field",
        "deidentified": True,
        "privacy_reviewed": True,
    }


def _inputs(tmp_path: Path, *, records=None, mutate=None):
    from human_feedback.evaluation_corpus import evaluation_corpus_digest, load_evaluation_corpus
    from human_feedback.evaluation_split import (
        build_loso_evaluation_plan,
        loso_evaluation_plan_digest,
    )

    payloads = _artifact_payloads()
    records = _records() if records is None else records
    manifest_path = tmp_path / "manifest.json"
    records_path = tmp_path / "records.json"
    manifest_path.write_text(json.dumps(_corpus_manifest(records, payloads)), encoding="utf-8")
    records_path.write_text(json.dumps(records), encoding="utf-8")
    corpus = load_evaluation_corpus(manifest_path, records_path)
    plan = build_loso_evaluation_plan(corpus)
    artifact_ids = {
        "sampling_protocol": corpus.sampling_protocol_id,
        "annotation_guide": corpus.annotation_guide_id,
        "adjudication_protocol": corpus.adjudication_protocol_id,
        "deidentification_protocol": corpus.deidentification_protocol_id,
        "custody_record": "custody-record-v1",
    }
    preregistration = {
        "schema_version": "laya-human-evaluation-preregistration-v1",
        "protocol_id": "laya-human-cross-site-preregistered-v1",
        "frozen_at": "2026-10-17T00:00:00Z",
        "corpus_id": corpus.corpus_id,
        "evaluation_corpus_sha256": evaluation_corpus_digest(corpus),
        "loso_plan_sha256": loso_evaluation_plan_digest(plan),
        "required_sites": list(SITES),
        "cohort": {
            "minimum_total_examples": 60,
            "minimum_examples_per_site": 20,
            "minimum_groups_per_site": 4,
            "minimum_examples_per_site_category": 4,
            "maximum_site_imbalance_ratio": 1.25,
            "minimum_pre_adjudication_alpha_nominal": 0.8,
        },
        "analysis": {
            "primary_metric": "macro_f1",
            "baseline_id": "deterministic-rule-baseline-v1",
            "comparison_design": "same_loso_folds_paired_delta",
            "minimum_paired_macro_f1_delta": 0.05,
            "bootstrap_method": "stratified_cluster_percentile",
            "bootstrap_unit": "group_within_site",
            "bootstrap_replicates": 10000,
            "bootstrap_confidence_level": 0.95,
            "bootstrap_seed": 20261017,
            "multiplicity_correction": "holm",
            "familywise_alpha": 0.05,
            "legacy_policy_id": "laya-readiness-policy-v1",
            "legacy_thresholds": LEGACY_THRESHOLDS,
        },
        "external_artifacts": [
            {
                "role": role,
                "artifact_id": artifact_ids[role],
                "size_bytes": len(payloads[role]),
                "sha256": hashlib.sha256(payloads[role]).hexdigest(),
            }
            for role in ROLES
        ],
    }
    if mutate is not None:
        mutate(preregistration)
    artifacts = tuple(ExternalArtifact(role=role, content=payloads[role]) for role in ROLES)
    return _canonical(preregistration), corpus, plan, artifacts, records


def test_verified_protocol_binds_corpus_plan_artifacts_cohort_and_analysis(tmp_path: Path):
    raw, corpus, plan, artifacts, _ = _inputs(tmp_path)

    protocol = verify_human_evaluation_preregistration(
        raw, corpus=corpus, plan=plan, external_artifacts=artifacts
    )

    assert protocol.schema_version == "laya-human-evaluation-preregistration-v1"
    assert protocol.corpus is corpus
    assert protocol.plan is plan
    assert protocol.external_artifacts_verified is True
    assert protocol.cohort_constraints_satisfied is True
    assert protocol.pre_adjudication_alpha_nominal == pytest.approx(1.0)
    assert protocol.evaluation_executed is False
    assert protocol.scientifically_sufficient is False
    assert protocol.eligible_for_shadow_review is False
    assert protocol.production_enablement_authorized is False


def test_summary_and_evidence_digest_are_canonical_public_and_deterministic(tmp_path: Path):
    raw, corpus, plan, artifacts, records = _inputs(tmp_path)
    protocol = verify_human_evaluation_preregistration(
        raw, corpus=corpus, plan=plan, external_artifacts=tuple(reversed(artifacts))
    )
    summary = canonical_human_evaluation_preregistration_summary_bytes(protocol)
    decoded = json.loads(summary)

    assert decoded["analysis"]["legacy_thresholds"] == LEGACY_THRESHOLDS
    assert decoded["analysis"]["bootstrap_replicates"] == 10000
    assert decoded["analysis"]["minimum_paired_macro_f1_delta"] == 0.05
    assert decoded["analysis"]["bootstrap_method"] == "stratified_cluster_percentile"
    assert decoded["analysis"]["bootstrap_unit"] == "group_within_site"
    assert decoded["analysis"]["multiplicity_correction"] == "holm"
    assert decoded["scientifically_sufficient"] is False
    assert (
        human_evaluation_preregistration_evidence_digest(protocol)
        == hashlib.sha256(summary).hexdigest()
    )
    private = {
        str(value)
        for record in records
        for value in (
            record["example_id"],
            record["group_id"],
            record["comment"],
            *(item["annotator_id"] for item in record["annotations"]),
        )
    }
    assert all(value.encode() not in summary for value in private)
    assert all(value not in repr(protocol) for value in private)


@pytest.mark.parametrize(
    "mutation, message",
    (
        (lambda raw: raw.update({"unexpected": True}), "fields|schema"),
        (lambda raw: raw.__delitem__("analysis"), "fields|schema"),
        (lambda raw: raw.update({"evaluation_corpus_sha256": "0" * 64}), "corpus|digest"),
        (lambda raw: raw.update({"loso_plan_sha256": "0" * 64}), "plan|digest"),
        (
            lambda raw: raw.update({"frozen_at": "2026-10-16T23:59:59Z"}),
            "frozen|corpus|time",
        ),
        (
            lambda raw: raw["external_artifacts"][0].update({"size_bytes": 1}),
            "artifact|size",
        ),
        (
            lambda raw: raw["external_artifacts"][0].update({"sha256": "0" * 64}),
            "artifact|digest",
        ),
        (
            lambda raw: raw["cohort"].update({"minimum_total_examples": 61}),
            "cohort|total|example",
        ),
        (
            lambda raw: raw["cohort"].update({"minimum_examples_per_site": 21}),
            "cohort|site|example",
        ),
        (
            lambda raw: raw["cohort"].update({"minimum_groups_per_site": 5}),
            "cohort|group",
        ),
        (
            lambda raw: raw["cohort"].update({"minimum_examples_per_site_category": 5}),
            "cohort|category|cell",
        ),
        (
            lambda raw: raw["analysis"].update({"bootstrap_method": "post_hoc_method"}),
            "bootstrap|method",
        ),
        (
            lambda raw: raw["analysis"].update({"bootstrap_unit": "individual_example"}),
            "bootstrap|unit",
        ),
    ),
)
def test_manifest_and_cohort_fail_closed(tmp_path: Path, mutation, message: str):
    raw, corpus, plan, artifacts, records = _inputs(tmp_path, mutate=mutation)
    with pytest.raises(ValueError, match=message) as error:
        verify_human_evaluation_preregistration(
            raw, corpus=corpus, plan=plan, external_artifacts=artifacts
        )
    assert all(str(record["comment"]) not in str(error.value) for record in records)


def test_pre_adjudication_nominal_alpha_is_enforced(tmp_path: Path):
    raw, corpus, plan, artifacts, _ = _inputs(tmp_path, records=_records(disagree=True))
    with pytest.raises(ValueError, match="alpha|agreement"):
        verify_human_evaluation_preregistration(
            raw, corpus=corpus, plan=plan, external_artifacts=artifacts
        )


def test_external_roles_are_exact_and_bytes_never_appear_in_repr_or_errors(tmp_path: Path):
    raw, corpus, plan, artifacts, _ = _inputs(tmp_path)
    secret = b"private-external-protocol-payload"
    altered = (ExternalArtifact(role=artifacts[0].role, content=secret), *artifacts[1:])
    with pytest.raises(ValueError, match="artifact|digest|size") as error:
        verify_human_evaluation_preregistration(
            raw, corpus=corpus, plan=plan, external_artifacts=altered
        )
    assert secret.decode() not in repr(altered[0])
    assert secret.decode() not in str(error.value)


def test_verified_authority_cannot_be_directly_constructed_or_replaced(tmp_path: Path):
    raw, corpus, plan, artifacts, _ = _inputs(tmp_path)
    protocol = verify_human_evaluation_preregistration(
        raw, corpus=corpus, plan=plan, external_artifacts=artifacts
    )
    rendered = repr(protocol)
    assert protocol.evaluation_corpus_sha256 not in rendered
    assert protocol.loso_plan_sha256 not in rendered
    assert all(artifact.sha256 not in rendered for artifact in protocol.artifacts)
    constructor_values = {
        item.name: getattr(protocol, item.name) for item in fields(protocol) if item.init
    }

    with pytest.raises((TypeError, ValueError), match="seal|verif|InitVar|required"):
        type(protocol)(**constructor_values)
    with pytest.raises((TypeError, ValueError), match="seal|verif|InitVar|required"):
        replace(protocol, protocol_id="post-hoc-protocol")


def test_parser_is_bytes_only_and_module_remains_isolated():
    signature = inspect.signature(verify_human_evaluation_preregistration)
    assert tuple(signature.parameters) == (
        "preregistration_bytes",
        "corpus",
        "plan",
        "external_artifacts",
    )
    repository = Path(__file__).parents[1]
    forbidden = (
        repository / "backend",
        repository / "scripts",
        repository / "src" / "data_ingestion",
        repository / "src" / "predictive_modeling",
        repository / "src" / "experiment_runner",
        repository / "src" / "human_feedback" / "adapters",
        repository / "src" / "human_feedback" / "offline_readiness.py",
    )
    offenders = []
    for candidate in forbidden:
        paths = candidate.rglob("*.py") if candidate.is_dir() else (candidate,)
        for path in paths:
            if "human_feedback.evaluation_preregistration" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []
