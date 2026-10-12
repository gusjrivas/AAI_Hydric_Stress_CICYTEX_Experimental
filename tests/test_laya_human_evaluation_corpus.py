import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

SCHEMA_VERSION = "laya-human-evaluation-corpus-v1"
REQUIRED_SITES = ("cicytex", "melchor-romero", "pergamino")
PROTOCOL_DIGEST = "a" * 64


def _records() -> list[dict[str, object]]:
    return [
        {
            "example_id": "private-example-cicytex",
            "site_id": "cicytex",
            "group_id": "private-group-cicytex",
            "comment": "La sonda presenta un salto imposible.",
            "annotations": [
                {"annotator_id": "private-reviewer-a", "category": "data_quality"},
                {"annotator_id": "private-reviewer-b", "category": "data_quality"},
            ],
            "adjudication": None,
            "gold_category": "data_quality",
        },
        {
            "example_id": "private-example-pergamino",
            "site_id": "pergamino",
            "group_id": "private-group-pergamino",
            "comment": "La prediccion del modelo requiere revision.",
            "annotations": [
                {"annotator_id": "private-reviewer-c", "category": "model_behavior"},
                {"annotator_id": "private-reviewer-d", "category": "model_behavior"},
            ],
            "adjudication": None,
            "gold_category": "model_behavior",
        },
        {
            "example_id": "private-example-melchor",
            "site_id": "melchor-romero",
            "group_id": "private-group-melchor",
            "comment": "El riego reciente explica el cambio observado.",
            "annotations": [
                {"annotator_id": "private-reviewer-e", "category": "agronomic_context"},
                {"annotator_id": "private-reviewer-f", "category": "other"},
            ],
            "adjudication": {
                "adjudicator_id": "private-reviewer-g",
                "category": "agronomic_context",
                "decision_ref": "private-adjudication-ref-003",
            },
            "gold_category": "agronomic_context",
        },
    ]


def _private_values(records: list[dict[str, object]]) -> set[str]:
    values = (
        {record["example_id"] for record in records}
        | {record["group_id"] for record in records}
        | {record["comment"] for record in records}
        | {annotation["annotator_id"] for record in records for annotation in record["annotations"]}
    )
    for record in records:
        adjudication = record["adjudication"]
        if adjudication is not None:
            values.add(adjudication["adjudicator_id"])
            values.add(adjudication["decision_ref"])
    return values


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
        "schema_version": SCHEMA_VERSION,
        "corpus_id": "human-cross-site-v1",
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
        "frozen_at": "2026-10-11T12:00:00Z",
        "declared_source_kind": "human_field",
        "deidentified": True,
        "privacy_reviewed": True,
    }


def _write_contract(
    tmp_path: Path,
    records: list[dict[str, object]],
    *,
    manifest: dict[str, object] | None = None,
    stem: str = "corpus",
) -> tuple[Path, Path]:
    manifest_path = tmp_path / f"{stem}-manifest.json"
    records_path = tmp_path / f"{stem}-records.json"
    manifest_path.write_text(
        json.dumps(manifest if manifest is not None else _manifest(records)),
        encoding="utf-8",
    )
    records_path.write_text(json.dumps(records), encoding="utf-8")
    return manifest_path, records_path


def _load(tmp_path: Path, records: list[dict[str, object]], *, stem: str = "corpus"):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    manifest_path, records_path = _write_contract(tmp_path, records, stem=stem)
    return load_evaluation_corpus(manifest_path, records_path)


def test_sealed_human_corpus_has_deterministic_digest_independent_of_input_order(
    tmp_path: Path,
):
    from human_feedback.evaluation_corpus import (
        canonical_corpus_summary_bytes,
        evaluation_corpus_digest,
        load_evaluation_corpus,
    )

    records_a = _records()
    records_b = list(reversed(deepcopy(records_a)))
    for record in records_b:
        record["annotations"] = list(reversed(record["annotations"]))
    manifest_a, records_path_a = _write_contract(tmp_path, records_a, stem="a")
    manifest_b, records_path_b = _write_contract(tmp_path, records_b, stem="b")

    corpus_a = load_evaluation_corpus(manifest_a, records_path_a)
    corpus_b = load_evaluation_corpus(manifest_b, records_path_b)

    assert corpus_a.schema_version == SCHEMA_VERSION
    assert corpus_a.corpus_id == "human-cross-site-v1"
    assert corpus_a.evidence_role == "human_corpus_candidate"
    assert corpus_a.records_count == 3
    assert corpus_a.records_sha256 == _manifest(records_a)["records_sha256"]
    assert tuple(record.site_id for record in corpus_a.records) == REQUIRED_SITES
    assert corpus_a.rubric_version == "feedback-rubric-v1"
    assert corpus_a.sampling_protocol_id == "sampling-cross-site-v1"
    assert corpus_a.sampling_protocol_sha256 == PROTOCOL_DIGEST
    assert corpus_a.annotation_guide_id == "annotation-guide-v1"
    assert corpus_a.annotation_guide_sha256 == "b" * 64
    assert corpus_a.adjudication_protocol_id == "adjudication-v1"
    assert corpus_a.adjudication_protocol_sha256 == "c" * 64
    assert corpus_a.deidentification_protocol_id == "deidentification-v1"
    assert corpus_a.deidentification_protocol_sha256 == "d" * 64
    assert corpus_a.custody_digest == "e" * 64
    assert corpus_a.frozen_at == "2026-10-11T12:00:00Z"
    assert corpus_a.declared_source_kind == "human_field"
    assert corpus_a.deidentified is True
    assert corpus_a.privacy_reviewed is True
    assert canonical_corpus_summary_bytes(corpus_a) == canonical_corpus_summary_bytes(corpus_b)
    assert evaluation_corpus_digest(corpus_a) == evaluation_corpus_digest(corpus_b)


def test_corpus_and_nested_records_are_immutable(tmp_path: Path):
    corpus = _load(tmp_path, _records())

    with pytest.raises((AttributeError, TypeError)):
        corpus.corpus_id = "rewritten"
    with pytest.raises((AttributeError, TypeError)):
        corpus.records[0].gold_category = "other"
    with pytest.raises((AttributeError, TypeError)):
        corpus.records[0].annotations[0].category = "other"
    assert isinstance(corpus.records, tuple)
    assert isinstance(corpus.records[0].annotations, tuple)


def test_public_summary_is_canonical_but_private_content_only_affects_identity(
    tmp_path: Path,
):
    import human_feedback.evaluation_corpus as corpus_module
    from human_feedback.evaluation_corpus import (
        canonical_corpus_summary_bytes,
        evaluation_corpus_digest,
    )

    records_a = _records()
    records_b = deepcopy(records_a)
    records_b[0]["comment"] = "Contenido humano privado corregido."
    corpus_a = _load(tmp_path, records_a, stem="private-a")
    corpus_b = _load(tmp_path, records_b, stem="private-b")

    assert not hasattr(corpus_module, "canonical_corpus_bytes")
    assert evaluation_corpus_digest(corpus_a) != evaluation_corpus_digest(corpus_b)
    for corpus, records in ((corpus_a, records_a), (corpus_b, records_b)):
        summary = canonical_corpus_summary_bytes(corpus)
        decoded = json.loads(summary)
        assert decoded["records_count"] == 3
        private_values = _private_values(records)
        assert all(value.encode("utf-8") not in summary for value in private_values)


def test_duplicate_example_is_rejected_without_leaking_private_ids(tmp_path: Path):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    records.append(deepcopy(records[0]))
    manifest_path, records_path = _write_contract(tmp_path, records)

    with pytest.raises(ValueError, match="duplicate example") as error:
        load_evaluation_corpus(manifest_path, records_path)

    assert records[0]["example_id"] not in str(error.value)


def test_group_cannot_cross_site_boundaries(tmp_path: Path):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    records[1]["group_id"] = records[0]["group_id"]
    manifest_path, records_path = _write_contract(tmp_path, records)

    with pytest.raises(ValueError, match="group.*site") as error:
        load_evaluation_corpus(manifest_path, records_path)

    assert records[0]["group_id"] not in str(error.value)


@pytest.mark.parametrize("invalid_case", ("laboratory_mock", "missing_site"))
def test_only_the_complete_real_cross_site_cohort_is_accepted(
    tmp_path: Path,
    invalid_case: str,
):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    if invalid_case == "laboratory_mock":
        records[0]["site_id"] = "laboratorio-mock"
    else:
        records = records[:-1]
    manifest_path, records_path = _write_contract(tmp_path, records)

    with pytest.raises(ValueError, match="required sites"):
        load_evaluation_corpus(manifest_path, records_path)


def test_every_example_requires_two_distinct_annotators(tmp_path: Path):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    records[0]["annotations"] = records[0]["annotations"][:1]
    manifest_path, records_path = _write_contract(tmp_path, records)

    with pytest.raises(ValueError, match="at least two distinct annotators"):
        load_evaluation_corpus(manifest_path, records_path)


def test_disagreement_requires_explicit_adjudication(tmp_path: Path):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    records[2]["adjudication"] = None
    manifest_path, records_path = _write_contract(tmp_path, records)

    with pytest.raises(ValueError, match="disagreement.*adjudication"):
        load_evaluation_corpus(manifest_path, records_path)


@pytest.mark.parametrize("invalid_case", ("annotator_reused", "empty_decision_ref"))
def test_disagreement_requires_independent_traceable_adjudication(
    tmp_path: Path,
    invalid_case: str,
):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    adjudication = records[2]["adjudication"]
    assert isinstance(adjudication, dict)
    if invalid_case == "annotator_reused":
        adjudication["adjudicator_id"] = records[2]["annotations"][0]["annotator_id"]
    else:
        adjudication["decision_ref"] = ""
    manifest_path, records_path = _write_contract(tmp_path, records)

    with pytest.raises(ValueError, match="adjudicat.*(?:third|distinct|decision ref)"):
        load_evaluation_corpus(manifest_path, records_path)


def test_consensus_forbids_redundant_adjudication(tmp_path: Path):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    records[0]["adjudication"] = {
        "adjudicator_id": "private-reviewer-h",
        "category": "data_quality",
        "decision_ref": "private-adjudication-ref-001",
    }
    manifest_path, records_path = _write_contract(tmp_path, records)

    with pytest.raises(ValueError, match="adjudication.*annotations agree"):
        load_evaluation_corpus(manifest_path, records_path)


@pytest.mark.parametrize("record_index", (0, 2))
def test_gold_must_match_consensus_or_explicit_adjudication(
    tmp_path: Path,
    record_index: int,
):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    records[record_index]["gold_category"] = "usability"
    manifest_path, records_path = _write_contract(tmp_path, records)

    with pytest.raises(ValueError, match="gold.*(?:consensus|adjudicat)"):
        load_evaluation_corpus(manifest_path, records_path)


@pytest.mark.parametrize("tampering", ("count", "digest"))
def test_manifest_count_and_digest_are_verified_before_acceptance(
    tmp_path: Path,
    tampering: str,
):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    manifest = _manifest(records)
    if tampering == "count":
        manifest["records_count"] = len(records) + 1
    else:
        manifest["records_sha256"] = "0" * 64
    manifest_path, records_path = _write_contract(
        tmp_path,
        records,
        manifest=manifest,
    )

    with pytest.raises(ValueError, match=f"records {tampering} mismatch"):
        load_evaluation_corpus(manifest_path, records_path)


@pytest.mark.parametrize(
    ("field", "invalid_value", "message"),
    (
        ("evidence_role", "human_cross_site", "evidence role"),
        ("rubric_version", "", "rubric version"),
        ("sampling_protocol_id", "", "sampling protocol id"),
        ("annotation_guide_id", "", "annotation guide id"),
        ("adjudication_protocol_id", "", "adjudication protocol id"),
        ("deidentification_protocol_id", "", "deidentification protocol id"),
        ("sampling_protocol_sha256", "A" * 64, "sampling protocol digest"),
        ("annotation_guide_sha256", "short", "annotation guide digest"),
        ("adjudication_protocol_sha256", "g" * 64, "adjudication protocol digest"),
        ("deidentification_protocol_sha256", 7, "deidentification protocol digest"),
        ("custody_digest", "E" * 64, "custody digest"),
        ("frozen_at", "2026-10-11T12:00:00+00:00", "frozen at.*UTC"),
        ("declared_source_kind", "synthetic", "source kind"),
        ("deidentified", False, "deidentified"),
        ("privacy_reviewed", False, "privacy reviewed"),
    ),
)
def test_candidate_manifest_provenance_and_privacy_attestations_fail_closed(
    tmp_path: Path,
    field: str,
    invalid_value: object,
    message: str,
):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    manifest = _manifest(records)
    manifest[field] = invalid_value
    manifest_path, records_path = _write_contract(tmp_path, records, manifest=manifest)

    with pytest.raises(ValueError, match=message):
        load_evaluation_corpus(manifest_path, records_path)


def test_errors_and_repr_never_expose_comments_or_private_identifiers(tmp_path: Path):
    from human_feedback.evaluation_corpus import load_evaluation_corpus

    records = _records()
    corpus = _load(tmp_path, records, stem="valid")
    private_values = _private_values(records)
    rendered = repr(corpus)
    assert all(value not in rendered for value in private_values)

    records[0]["annotations"] = records[0]["annotations"][:1]
    manifest_path, records_path = _write_contract(tmp_path, records, stem="invalid")
    with pytest.raises(ValueError) as error:
        load_evaluation_corpus(manifest_path, records_path)
    assert all(value not in str(error.value) for value in private_values)


def test_structural_validity_is_not_scientific_sufficiency_or_readiness_authority(
    tmp_path: Path,
):
    corpus = _load(tmp_path, _records())

    assert corpus.structurally_valid is True
    assert corpus.scientifically_sufficient is False
    assert corpus.production_enablement_authorized is False


def test_direct_construction_cannot_auto_attest_invalid_corpus_as_structurally_valid(
    tmp_path: Path,
):
    corpus = _load(tmp_path, _records())

    with pytest.raises(ValueError, match="validated loader|structurally valid|records"):
        replace(corpus, records=())


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("records_count", 3.0),
        ("minimum_annotators_per_example", 2.0),
    ),
)
def test_direct_construction_rejects_numeric_type_coercion(
    tmp_path: Path,
    field: str,
    invalid_value: float,
):
    corpus = _load(tmp_path, _records())

    with pytest.raises(ValueError, match="integer"):
        replace(corpus, **{field: invalid_value})


def test_evaluation_corpus_is_not_imported_by_operational_or_scientific_flows():
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
            if "human_feedback.evaluation_corpus" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(repository).as_posix())
    for path in forbidden_files:
        if "human_feedback.evaluation_corpus" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []
