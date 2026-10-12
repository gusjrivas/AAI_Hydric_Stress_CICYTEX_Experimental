import hashlib
import json
import math
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

REQUIRED_SITES = ("cicytex", "melchor-romero", "pergamino")
CORPUS_SCHEMA_VERSION = "laya-human-evaluation-corpus-v1"
PLAN_SCHEMA_VERSION = "laya-loso-evaluation-plan-v1"
CALIBRATION_POLICY_ID = "laya-loso-group-calibration-sha256-v1"
PROTOCOL_DIGEST = "a" * 64


def _records(*, groups_per_site: int = 3) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for site_index, site_id in enumerate(REQUIRED_SITES):
        for group_index in range(groups_per_site):
            group_id = f"private-group-{site_id}-{group_index}"
            for example_index in range(2):
                category = (
                    "data_quality"
                    if (site_index + group_index + example_index) % 2 == 0
                    else "model_behavior"
                )
                records.append(
                    {
                        "example_id": (f"private-example-{site_id}-{group_index}-{example_index}"),
                        "site_id": site_id,
                        "group_id": group_id,
                        "comment": (
                            f"Private field observation {site_index}-{group_index}-"
                            f"{example_index}."
                        ),
                        "annotations": [
                            {
                                "annotator_id": (f"private-reviewer-{site_index}-{group_index}-a"),
                                "category": category,
                            },
                            {
                                "annotator_id": (f"private-reviewer-{site_index}-{group_index}-b"),
                                "category": category,
                            },
                        ],
                        "adjudication": None,
                        "gold_category": category,
                    }
                )
    return records


def _canonical_records_bytes(records: list[dict[str, object]]) -> bytes:
    normalized = deepcopy(records)
    for record in normalized:
        annotations = record["annotations"]
        assert isinstance(annotations, list)
        annotations.sort(key=lambda annotation: annotation["annotator_id"])
    normalized.sort(key=lambda record: record["example_id"])
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _manifest(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "corpus_id": "private-human-cross-site-v1",
        "evidence_role": "human_corpus_candidate",
        "records_count": len(records),
        "records_sha256": hashlib.sha256(_canonical_records_bytes(records)).hexdigest(),
        "required_sites": list(REQUIRED_SITES),
        "minimum_annotators_per_example": 2,
        "adjudication_policy": "agreement_or_explicit_adjudication",
        "rubric_version": "feedback-rubric-v1",
        "sampling_protocol_id": "sampling-cross-site-v1",
        "sampling_protocol_sha256": PROTOCOL_DIGEST,
        "annotation_guide_id": "annotation-guide-v1",
        "annotation_guide_sha256": "b" * 64,
        "adjudication_protocol_id": "adjudication-v1",
        "adjudication_protocol_sha256": "c" * 64,
        "deidentification_protocol_id": "deidentification-v1",
        "deidentification_protocol_sha256": "d" * 64,
        "custody_digest": "e" * 64,
        "frozen_at": "2026-10-12T00:00:00Z",
        "declared_source_kind": "human_field",
        "deidentified": True,
        "privacy_reviewed": True,
    }


def _load_corpus(
    tmp_path: Path,
    records: list[dict[str, object]],
    *,
    stem: str,
):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    manifest_path = tmp_path / f"{stem}-manifest.json"
    records_path = tmp_path / f"{stem}-records.json"
    manifest_path.write_text(json.dumps(_manifest(records)), encoding="utf-8")
    records_path.write_text(json.dumps(records), encoding="utf-8")
    return load_evaluation_corpus(manifest_path, records_path)


def _assignments(plan) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            fold.held_out_site,
            tuple(record.example_id for record in fold.fit_records),
            tuple(record.example_id for record in fold.calibration_records),
            tuple(record.example_id for record in fold.test_records),
        )
        for fold in plan.folds
    )


def _private_values(records: list[dict[str, object]]) -> set[str]:
    return (
        {str(record["example_id"]) for record in records}
        | {str(record["group_id"]) for record in records}
        | {str(record["comment"]) for record in records}
        | {
            str(annotation["annotator_id"])
            for record in records
            for annotation in record["annotations"]
        }
    )


def _expected_calibration_groups(records: list[dict[str, object]], site_id: str) -> set[str]:
    group_ids = {str(record["group_id"]) for record in records if record["site_id"] == site_id}

    def allocation_key(group_id: str) -> tuple[str, str]:
        separated = f"{CALIBRATION_POLICY_ID}\0{site_id}\0{group_id}".encode()
        return hashlib.sha256(separated).hexdigest(), group_id

    ordered = sorted(group_ids, key=allocation_key)
    return set(ordered[: math.ceil(len(ordered) * 0.20)])


def test_loso_plan_has_one_ordered_fold_per_required_site_and_expected_hash_allocation(
    tmp_path: Path,
):
    from human_feedback.evaluation_split import build_loso_evaluation_plan

    records = _records()
    corpus = _load_corpus(tmp_path, records, stem="ordered")

    plan = build_loso_evaluation_plan(corpus)

    assert plan.schema_version == PLAN_SCHEMA_VERSION
    assert plan.calibration_policy_id == CALIBRATION_POLICY_ID
    assert plan.corpus is corpus
    assert tuple(fold.held_out_site for fold in plan.folds) == REQUIRED_SITES
    for fold in plan.folds:
        for training_site in set(REQUIRED_SITES) - {fold.held_out_site}:
            actual = {
                record.group_id
                for record in fold.calibration_records
                if record.site_id == training_site
            }
            assert actual == _expected_calibration_groups(records, training_site)


def test_each_fold_is_exhaustive_disjoint_and_keeps_groups_indivisible(tmp_path: Path):
    from human_feedback.evaluation_split import build_loso_evaluation_plan

    corpus = _load_corpus(tmp_path, _records(), stem="partition")
    plan = build_loso_evaluation_plan(corpus)
    all_ids = {record.example_id for record in corpus.records}

    for fold in plan.folds:
        fit_ids = {record.example_id for record in fold.fit_records}
        calibration_ids = {record.example_id for record in fold.calibration_records}
        test_ids = {record.example_id for record in fold.test_records}
        assert fit_ids | calibration_ids | test_ids == all_ids
        assert fit_ids.isdisjoint(calibration_ids)
        assert fit_ids.isdisjoint(test_ids)
        assert calibration_ids.isdisjoint(test_ids)

        partitions_by_group: dict[str, set[str]] = {}
        for partition_name, partition_records in (
            ("fit", fold.fit_records),
            ("calibration", fold.calibration_records),
            ("test", fold.test_records),
        ):
            for record in partition_records:
                partitions_by_group.setdefault(record.group_id, set()).add(partition_name)
        assert all(len(partitions) == 1 for partitions in partitions_by_group.values())
        assert {record.site_id for record in fold.test_records} == {fold.held_out_site}


def test_both_training_sites_contribute_fit_and_calibration_records(tmp_path: Path):
    from human_feedback.evaluation_split import build_loso_evaluation_plan

    corpus = _load_corpus(tmp_path, _records(), stem="train-sites")

    for fold in build_loso_evaluation_plan(corpus).folds:
        training_sites = set(REQUIRED_SITES) - {fold.held_out_site}
        assert {record.site_id for record in fold.fit_records} == training_sites
        assert {record.site_id for record in fold.calibration_records} == training_sites


def test_plan_is_deterministic_and_independent_of_input_annotation_order(tmp_path: Path):
    from human_feedback.evaluation_split import (
        build_loso_evaluation_plan,
        canonical_loso_plan_summary_bytes,
        loso_evaluation_plan_digest,
    )

    records_a = _records()
    records_b = list(reversed(deepcopy(records_a)))
    for record in records_b:
        record["annotations"] = list(reversed(record["annotations"]))
    plan_a = build_loso_evaluation_plan(_load_corpus(tmp_path, records_a, stem="order-a"))
    plan_b = build_loso_evaluation_plan(_load_corpus(tmp_path, records_b, stem="order-b"))

    assert _assignments(plan_a) == _assignments(plan_b)
    assert canonical_loso_plan_summary_bytes(plan_a) == canonical_loso_plan_summary_bytes(plan_b)
    assert loso_evaluation_plan_digest(plan_a) == loso_evaluation_plan_digest(plan_b)


def test_group_assignment_ignores_comments_annotations_and_gold_labels(tmp_path: Path):
    from human_feedback.evaluation_split import build_loso_evaluation_plan

    records_a = _records()
    records_b = deepcopy(records_a)
    for index, record in enumerate(records_b):
        category = "usability" if index % 2 == 0 else "agronomic_context"
        record["comment"] = f"Different private observation {index}."
        record["annotations"] = [
            {"annotator_id": f"different-reviewer-{index}-a", "category": category},
            {"annotator_id": f"different-reviewer-{index}-b", "category": category},
        ]
        record["gold_category"] = category
    plan_a = build_loso_evaluation_plan(_load_corpus(tmp_path, records_a, stem="label-a"))
    plan_b = build_loso_evaluation_plan(_load_corpus(tmp_path, records_b, stem="label-b"))

    assert _assignments(plan_a) == _assignments(plan_b)
    assert plan_a.assignment_sha256 == plan_b.assignment_sha256


@pytest.mark.parametrize("insufficient_site", REQUIRED_SITES)
def test_plan_fails_closed_when_any_site_has_fewer_than_two_groups(
    tmp_path: Path,
    insufficient_site: str,
):
    from human_feedback.evaluation_split import build_loso_evaluation_plan

    records = _records()
    for record in records:
        if record["site_id"] == insufficient_site:
            record["group_id"] = f"private-only-group-{insufficient_site}"
    corpus = _load_corpus(tmp_path, records, stem=f"insufficient-{insufficient_site}")

    with pytest.raises(ValueError, match="at least two groups per site") as error:
        build_loso_evaluation_plan(corpus)

    assert insufficient_site not in str(error.value)
    assert all(value not in str(error.value) for value in _private_values(records))


def test_fold_and_plan_reject_direct_or_replace_based_invalid_states(tmp_path: Path):
    from human_feedback.evaluation_split import build_loso_evaluation_plan

    plan = build_loso_evaluation_plan(_load_corpus(tmp_path, _records(), stem="replace"))
    fold = plan.folds[0]

    with pytest.raises(ValueError, match="fold|test|partition"):
        replace(fold, test_records=())
    with pytest.raises(ValueError, match="fold|site|partition|overlap"):
        type(fold)(
            held_out_site=fold.held_out_site,
            fit_records=(fold.test_records[0],),
            calibration_records=fold.calibration_records,
            test_records=fold.test_records,
        )
    with pytest.raises(ValueError, match="fold|plan|assignment"):
        replace(plan, folds=())
    with pytest.raises(ValueError, match="digest|assignment"):
        replace(plan, assignment_sha256="0" * 64)


def test_public_summary_and_repr_do_not_expose_private_corpus_values(tmp_path: Path):
    from human_feedback.evaluation_split import (
        build_loso_evaluation_plan,
        canonical_loso_plan_summary_bytes,
    )

    from human_feedback.evaluation_corpus import evaluation_corpus_digest

    records = _records()
    corpus = _load_corpus(tmp_path, records, stem="privacy")
    plan = build_loso_evaluation_plan(corpus)
    summary = canonical_loso_plan_summary_bytes(plan)
    decoded = json.loads(summary)

    assert decoded["schema_version"] == PLAN_SCHEMA_VERSION
    assert decoded["calibration_policy_id"] == CALIBRATION_POLICY_ID
    assert decoded["evaluation_corpus_digest"] == evaluation_corpus_digest(corpus)
    assert decoded["corpus_id"] == corpus.corpus_id
    assert decoded["sampling_protocol_id"] == corpus.sampling_protocol_id
    assert decoded["sampling_protocol_sha256"] == corpus.sampling_protocol_sha256
    assert "assignment_sha256" not in decoded
    assert decoded["structurally_valid"] is True
    assert decoded["evaluation_executed"] is False
    assert decoded["calibration_fitted"] is False
    assert decoded["scientifically_sufficient"] is False
    assert decoded["eligible_for_shadow_review"] is False
    assert decoded["production_enablement_authorized"] is False
    assert [fold["held_out_site"] for fold in decoded["folds"]] == list(REQUIRED_SITES)
    for fold in decoded["folds"]:
        assert set(fold) == {
            "held_out_site",
            "fit_records_count",
            "fit_groups_count",
            "calibration_records_count",
            "calibration_groups_count",
            "test_records_count",
            "test_groups_count",
        }
    rendered = repr(plan) + "".join(repr(fold) for fold in plan.folds)
    assert all(value.encode("utf-8") not in summary for value in _private_values(records))
    assert all(value not in rendered for value in _private_values(records))


def test_assignment_and_plan_digests_change_when_group_assignment_inputs_change(
    tmp_path: Path,
):
    from human_feedback.evaluation_split import (
        build_loso_evaluation_plan,
        canonical_loso_plan_summary_bytes,
        loso_evaluation_plan_digest,
    )

    records_a = _records()
    records_b = deepcopy(records_a)
    records_b[0]["group_id"] = "private-reassigned-group-cicytex-30"
    records_b[1]["group_id"] = "private-reassigned-group-cicytex-30"
    plan_a = build_loso_evaluation_plan(_load_corpus(tmp_path, records_a, stem="digest-a"))
    plan_b = build_loso_evaluation_plan(_load_corpus(tmp_path, records_b, stem="digest-b"))

    assert plan_a.assignment_sha256 != plan_b.assignment_sha256
    assert loso_evaluation_plan_digest(plan_a) != loso_evaluation_plan_digest(plan_b)
    assert (
        loso_evaluation_plan_digest(plan_a)
        == hashlib.sha256(canonical_loso_plan_summary_bytes(plan_a)).hexdigest()
    )


def test_structural_plan_does_not_claim_scientific_sufficiency_or_enablement(
    tmp_path: Path,
):
    from human_feedback.evaluation_split import build_loso_evaluation_plan

    plan = build_loso_evaluation_plan(_load_corpus(tmp_path, _records(), stem="flags"))

    assert plan.structurally_valid is True
    assert plan.evaluation_executed is False
    assert plan.calibration_fitted is False
    assert plan.scientifically_sufficient is False
    assert plan.eligible_for_shadow_review is False
    assert plan.production_enablement_authorized is False


def test_evaluation_split_is_isolated_from_operational_and_scientific_flows():
    repository = Path(__file__).parents[1]
    forbidden_roots = (
        repository / "backend",
        repository / "src" / "data_ingestion",
        repository / "src" / "predictive_modeling",
        repository / "src" / "experiment_runner",
        repository / "src" / "human_feedback" / "adapters",
        repository / "scripts",
    )
    forbidden_files = (repository / "src" / "human_feedback" / "offline_readiness.py",)
    offenders = []
    for root in forbidden_roots:
        for path in root.rglob("*.py"):
            if "human_feedback.evaluation_split" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(repository).as_posix())
    for path in forbidden_files:
        if "human_feedback.evaluation_split" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []
