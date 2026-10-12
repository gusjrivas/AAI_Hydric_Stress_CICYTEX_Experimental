import hashlib
import json
import math
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

CATEGORIES = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)
REQUIRED_SITES = ("cicytex", "melchor-romero", "pergamino")
CORPUS_SCHEMA_VERSION = "laya-human-evaluation-corpus-v1"
EXECUTION_SCHEMA_VERSION = "laya-loso-execution-contract-v1"
RUNTIME_SCHEMA_VERSION = "laya-runtime-identity-v1"
PROTOCOL_DIGEST = "a" * 64
RUNTIME_DIGEST = "f" * 64
MODEL_REVISION = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
PROVIDER = "laya-http"


def _records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for site_index, site_id in enumerate(REQUIRED_SITES):
        for group_index in range(3):
            group_id = f"private-group-{site_id}-{group_index}"
            for example_index in range(2):
                category = CATEGORIES[(site_index + group_index + example_index) % len(CATEGORIES)]
                records.append(
                    {
                        "example_id": f"private-example-{site_id}-{group_index}-{example_index}",
                        "site_id": site_id,
                        "group_id": group_id,
                        "comment": (
                            f"Private field observation {site_index}-{group_index}-"
                            f"{example_index}."
                        ),
                        "annotations": [
                            {
                                "annotator_id": f"private-reviewer-{site_index}-{group_index}-a",
                                "category": category,
                            },
                            {
                                "annotator_id": f"private-reviewer-{site_index}-{group_index}-b",
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


def _plan(tmp_path: Path):
    from human_feedback.evaluation_corpus import load_evaluation_corpus
    from human_feedback.evaluation_split import build_loso_evaluation_plan

    records = _records()
    manifest_path = tmp_path / "private-manifest.json"
    records_path = tmp_path / "private-records.json"
    manifest_path.write_text(json.dumps(_manifest(records)), encoding="utf-8")
    records_path.write_text(json.dumps(records), encoding="utf-8")
    corpus = load_evaluation_corpus(manifest_path, records_path)
    return build_loso_evaluation_plan(corpus), records


def _contract(tmp_path: Path):
    from human_feedback.evaluation_execution import (
        RuntimeIdentityRef,
        build_loso_execution_contract,
    )

    plan, records = _plan(tmp_path)
    runtime = RuntimeIdentityRef(
        schema_version=RUNTIME_SCHEMA_VERSION,
        sha256=RUNTIME_DIGEST,
    )
    contract = build_loso_execution_contract(
        plan,
        runtime_identity=runtime,
        execution_protocol_id="laya-loso-execution-v1",
        execution_protocol_sha256=PROTOCOL_DIGEST,
        model_revision=MODEL_REVISION,
        provider=PROVIDER,
    )
    return contract, records


def _prediction(record, held_out_site: str, *, latency_ms: float = 12.5):
    from human_feedback.evaluation_execution import RawLosoPrediction

    probabilities = tuple(
        (category, 1.0 if category == record.gold_category else 0.0) for category in CATEGORIES
    )
    return RawLosoPrediction(
        held_out_site=held_out_site,
        example_id=record.example_id,
        category=record.gold_category,
        probabilities=probabilities,
        answer_confidence=1.0,
        latency_ms=latency_ms,
        provider=PROVIDER,
        model_revision=MODEL_REVISION,
    )


def _predictions(contract):
    return tuple(
        _prediction(record, fold.held_out_site)
        for fold in contract.plan.folds
        for record in fold.test_records
    )


def _private_prediction_content_sha256(predictions) -> str:
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
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


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


def test_execution_contract_binds_plan_corpus_runtime_protocol_and_model(tmp_path: Path):
    from human_feedback.evaluation_corpus import evaluation_corpus_digest
    from human_feedback.evaluation_split import loso_evaluation_plan_digest

    contract, _ = _contract(tmp_path)

    assert contract.schema_version == EXECUTION_SCHEMA_VERSION
    assert contract.loso_plan_sha256 == loso_evaluation_plan_digest(contract.plan)
    assert contract.evaluation_corpus_sha256 == evaluation_corpus_digest(contract.plan.corpus)
    assert contract.runtime_identity.schema_version == RUNTIME_SCHEMA_VERSION
    assert contract.runtime_identity.sha256 == RUNTIME_DIGEST
    assert contract.execution_protocol_id == "laya-loso-execution-v1"
    assert contract.execution_protocol_sha256 == PROTOCOL_DIGEST
    assert contract.model_revision == MODEL_REVISION
    assert contract.provider == PROVIDER


def test_runtime_and_contract_are_frozen_slotted_and_fail_closed_on_replace(tmp_path: Path):
    from human_feedback.evaluation_execution import RuntimeIdentityRef

    contract, _ = _contract(tmp_path)
    assert not hasattr(contract, "__dict__")
    assert not hasattr(contract.runtime_identity, "__dict__")
    with pytest.raises(FrozenInstanceError):
        contract.provider = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="runtime|digest"):
        RuntimeIdentityRef(schema_version=RUNTIME_SCHEMA_VERSION, sha256="not-a-digest")
    with pytest.raises(ValueError, match="plan|digest"):
        replace(contract, loso_plan_sha256="0" * 64)
    with pytest.raises(ValueError, match="protocol|digest"):
        replace(contract, execution_protocol_sha256="0" * 64)


def test_validated_predictions_cover_every_outer_test_record_exactly_once(tmp_path: Path):
    from human_feedback.evaluation_execution import validate_loso_prediction_set

    contract, _ = _contract(tmp_path)
    raw = _predictions(contract)
    validated = validate_loso_prediction_set(contract, raw)

    expected = {
        (fold.held_out_site, record.example_id)
        for fold in contract.plan.folds
        for record in fold.test_records
    }
    assert {(item.held_out_site, item.example_id) for item in validated.predictions} == expected
    assert len(validated.predictions) == len(expected) == contract.plan.corpus.records_count
    assert validated.execution_evidence_validated is True


@pytest.mark.parametrize("case", ["missing", "extra", "duplicate", "wrong-fold", "fit-cal"])
def test_prediction_coverage_rejects_missing_extra_duplicate_and_non_test_records(
    tmp_path: Path,
    case: str,
):
    from human_feedback.evaluation_execution import RawLosoPrediction, validate_loso_prediction_set

    contract, records = _contract(tmp_path)
    raw = list(_predictions(contract))
    if case == "missing":
        raw.pop()
    elif case == "extra":
        raw.append(replace(raw[0], example_id="private-unknown-example"))
    elif case == "duplicate":
        raw.append(raw[0])
    elif case == "wrong-fold":
        other_site = next(site for site in REQUIRED_SITES if site != raw[0].held_out_site)
        raw[0] = replace(raw[0], held_out_site=other_site)
    else:
        fold = contract.plan.folds[0]
        training_record = (fold.fit_records + fold.calibration_records)[0]
        raw[0] = RawLosoPrediction(
            held_out_site=fold.held_out_site,
            example_id=training_record.example_id,
            category=training_record.gold_category,
            probabilities=tuple(
                (category, 1.0 if category == training_record.gold_category else 0.0)
                for category in CATEGORIES
            ),
            answer_confidence=1.0,
            latency_ms=1.0,
            provider=PROVIDER,
            model_revision=MODEL_REVISION,
        )

    with pytest.raises(ValueError, match="prediction|coverage|fold|test") as error:
        validate_loso_prediction_set(contract, tuple(raw))

    rendered = str(error.value)
    assert all(value not in rendered for value in _private_values(records))
    assert "private-unknown-example" not in rendered


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("probabilities", (1.1, -0.1, 0.0, 0.0, 0.0)),
        ("probabilities", (0.7, 0.1, 0.1, 0.1, 0.1)),
        ("probabilities", (0.5, 0.5, 0.0, 0.0, 0.0)),
        ("probabilities", (True, 0.0, 0.0, 0.0, 0.0)),
        ("probabilities", (math.nan, 0.0, 0.0, 0.0, 0.0)),
        ("answer_confidence", True),
        ("answer_confidence", -0.01),
        ("answer_confidence", 1.01),
        ("answer_confidence", math.inf),
        ("latency_ms", True),
        ("latency_ms", -0.01),
        ("latency_ms", math.inf),
    ],
)
def test_raw_prediction_rejects_invalid_numeric_and_ambiguous_states(
    tmp_path: Path,
    field: str,
    value: object,
):
    contract, _ = _contract(tmp_path)
    valid = _predictions(contract)[0]
    changes: dict[str, object]
    if field == "probabilities":
        assert isinstance(value, tuple)
        changes = {field: tuple(zip(CATEGORIES, value, strict=True))}
    else:
        changes = {field: value}

    with pytest.raises(ValueError, match="probabilit|argmax|confidence|latency|numeric|finite"):
        replace(valid, **changes)


def test_prediction_requires_ordered_categories_argmax_and_contract_identity(tmp_path: Path):
    from human_feedback.evaluation_execution import validate_loso_prediction_set

    contract, _ = _contract(tmp_path)
    valid = _predictions(contract)[0]
    with pytest.raises(ValueError, match="categor|order|probabilit"):
        replace(valid, probabilities=tuple(reversed(valid.probabilities)))
    with pytest.raises(ValueError, match="categor|unclassified"):
        replace(valid, category="unclassified")
    with pytest.raises(ValueError, match="argmax|categor"):
        replace(
            valid, category=next(category for category in CATEGORIES if category != valid.category)
        )
    changed = list(_predictions(contract))
    changed[0] = replace(changed[0], model_revision="a" * 40)
    assert changed[0].model_revision == "a" * 40
    with pytest.raises(ValueError, match="model|contract"):
        validate_loso_prediction_set(contract, tuple(changed))


def test_answer_confidence_is_optional_but_when_present_is_validated(tmp_path: Path):
    from human_feedback.evaluation_execution import validate_loso_prediction_set

    contract, _ = _contract(tmp_path)
    raw = list(_predictions(contract))
    raw[0] = replace(raw[0], answer_confidence=None)

    validated = validate_loso_prediction_set(contract, tuple(raw))

    assert validated.predictions[0].answer_confidence is None


def test_prediction_validation_and_public_digest_are_order_invariant(tmp_path: Path):
    from human_feedback.evaluation_execution import (
        canonical_loso_execution_summary_bytes,
        loso_execution_evidence_digest,
        validate_loso_prediction_set,
    )

    contract, _ = _contract(tmp_path)
    forward = validate_loso_prediction_set(contract, _predictions(contract))
    reverse = validate_loso_prediction_set(contract, tuple(reversed(_predictions(contract))))

    assert forward.predictions == reverse.predictions
    assert canonical_loso_execution_summary_bytes(
        forward
    ) == canonical_loso_execution_summary_bytes(reverse)
    assert loso_execution_evidence_digest(forward) == loso_execution_evidence_digest(reverse)


def test_public_summary_is_sensitive_to_predictions_without_disclosing_rows(tmp_path: Path):
    from human_feedback.evaluation_execution import (
        canonical_loso_execution_summary_bytes,
        loso_execution_evidence_digest,
        validate_loso_prediction_set,
    )

    contract, records = _contract(tmp_path)
    raw_a = list(_predictions(contract))
    raw_b = list(raw_a)
    raw_b[0] = replace(raw_b[0], latency_ms=raw_b[0].latency_ms + 1.0)
    validated_a = validate_loso_prediction_set(contract, tuple(raw_a))
    validated_b = validate_loso_prediction_set(contract, tuple(raw_b))
    summary = canonical_loso_execution_summary_bytes(validated_a)
    decoded = json.loads(summary)

    assert loso_execution_evidence_digest(validated_a) != loso_execution_evidence_digest(
        validated_b
    )
    assert summary != canonical_loso_execution_summary_bytes(validated_b)
    assert decoded["schema_version"] == EXECUTION_SCHEMA_VERSION
    assert decoded["execution_evidence_validated"] is True
    assert decoded["structurally_valid"] is True
    assert decoded["execution_completed"] is False
    assert decoded["scientifically_sufficient"] is False
    assert decoded["eligible_for_shadow_review"] is False
    assert decoded["production_enablement_authorized"] is False
    forbidden_keys = {
        "example_id",
        "comment",
        "group_id",
        "annotator_id",
        "adjudicator_id",
        "adjudication",
        "probabilities",
        "records_sha256",
        "row_sha256",
        "loso_plan_sha256",
        "evaluation_corpus_sha256",
    }

    def all_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {
                nested_key for nested in value.values() for nested_key in all_keys(nested)
            }
        if isinstance(value, list):
            return {nested_key for nested in value for nested_key in all_keys(nested)}
        return set()

    assert forbidden_keys.isdisjoint(all_keys(decoded))
    assert contract.loso_plan_sha256.encode("ascii") not in summary
    assert contract.evaluation_corpus_sha256.encode("ascii") not in summary
    assert all(value.encode("utf-8") not in summary for value in _private_values(records))
    assert loso_execution_evidence_digest(validated_a) == hashlib.sha256(summary).hexdigest()


def test_execution_objects_repr_and_errors_do_not_disclose_private_inputs(tmp_path: Path):
    from human_feedback.evaluation_execution import validate_loso_prediction_set

    contract, records = _contract(tmp_path)
    raw = _predictions(contract)
    validated = validate_loso_prediction_set(contract, raw)
    contract_repr = repr(contract)
    evidence_repr = repr(validated)
    rendered_objects = (repr(raw[0]), repr(raw), contract_repr, evidence_repr)
    rendered = "".join(rendered_objects)

    assert all(value not in rendered for value in _private_values(records))
    for representation in rendered_objects:
        assert all(prediction.held_out_site not in representation for prediction in raw)
        assert all(prediction.category not in representation for prediction in raw)
    assert "probabilities" not in rendered
    assert contract.plan.corpus.records_sha256 not in rendered
    for representation in (contract_repr, evidence_repr):
        assert "loso_plan_sha256" not in representation
        assert "evaluation_corpus_sha256" not in representation
        assert contract.loso_plan_sha256 not in representation
        assert contract.evaluation_corpus_sha256 not in representation


def test_runtime_identity_rejects_null_digest_sentinel():
    from human_feedback.evaluation_execution import RuntimeIdentityRef

    with pytest.raises(ValueError, match="runtime|digest|null|sentinel"):
        RuntimeIdentityRef(schema_version=RUNTIME_SCHEMA_VERSION, sha256="0" * 64)


def test_canonical_summary_normalizes_equivalent_numeric_representations(tmp_path: Path):
    from human_feedback.evaluation_execution import (
        canonical_loso_execution_summary_bytes,
        loso_execution_evidence_digest,
        validate_loso_prediction_set,
    )

    contract, _ = _contract(tmp_path)
    float_rows = _predictions(contract)
    integer_rows = tuple(
        replace(
            prediction,
            probabilities=tuple(
                (category, int(probability)) for category, probability in prediction.probabilities
            ),
            answer_confidence=1,
            latency_ms=12,
        )
        for prediction in float_rows
    )
    float_rows = tuple(
        replace(prediction, answer_confidence=1.0, latency_ms=12.0) for prediction in float_rows
    )
    integer_evidence = validate_loso_prediction_set(contract, integer_rows)
    float_evidence = validate_loso_prediction_set(contract, float_rows)

    assert canonical_loso_execution_summary_bytes(
        integer_evidence
    ) == canonical_loso_execution_summary_bytes(float_evidence)
    assert loso_execution_evidence_digest(integer_evidence) == loso_execution_evidence_digest(
        float_evidence
    )
    assert integer_evidence.prediction_content_sha256 == float_evidence.prediction_content_sha256


def test_canonical_summary_normalizes_negative_zero(tmp_path: Path):
    from human_feedback.evaluation_execution import (
        canonical_loso_execution_summary_bytes,
        loso_execution_evidence_digest,
        validate_loso_prediction_set,
    )

    contract, _ = _contract(tmp_path)
    positive_rows = _predictions(contract)
    negative_rows = tuple(
        replace(
            prediction,
            probabilities=tuple(
                (category, -0.0 if probability == 0.0 else probability)
                for category, probability in prediction.probabilities
            ),
            latency_ms=-0.0 if prediction is positive_rows[0] else prediction.latency_ms,
        )
        for prediction in positive_rows
    )
    positive_rows = tuple(
        replace(prediction, latency_ms=0.0 if prediction is positive_rows[0] else 12.5)
        for prediction in positive_rows
    )
    positive_evidence = validate_loso_prediction_set(contract, positive_rows)
    negative_evidence = validate_loso_prediction_set(contract, negative_rows)

    assert canonical_loso_execution_summary_bytes(
        positive_evidence
    ) == canonical_loso_execution_summary_bytes(negative_evidence)
    assert loso_execution_evidence_digest(positive_evidence) == loso_execution_evidence_digest(
        negative_evidence
    )
    assert (
        positive_evidence.prediction_content_sha256 == negative_evidence.prediction_content_sha256
    )


def test_private_prediction_commitment_covers_complete_canonical_batch(tmp_path: Path):
    from human_feedback.evaluation_execution import validate_loso_prediction_set

    contract, _ = _contract(tmp_path)
    evidence = validate_loso_prediction_set(contract, _predictions(contract))

    assert evidence.prediction_content_sha256 == _private_prediction_content_sha256(
        evidence.predictions
    )
    assert not hasattr(evidence, "__dict__")


def test_private_commitment_detects_content_hidden_from_public_summary(tmp_path: Path):
    from human_feedback.evaluation_execution import (
        canonical_loso_execution_summary_bytes,
        loso_execution_evidence_digest,
        validate_loso_prediction_set,
    )

    contract, _ = _contract(tmp_path)
    rows_a = _predictions(contract)
    rows_b = list(rows_a)
    original = rows_b[0]
    alternate_category = next(category for category in CATEGORIES if category != original.category)
    rows_b[0] = replace(
        original,
        category=alternate_category,
        probabilities=tuple(
            (category, 1.0 if category == alternate_category else 0.0) for category in CATEGORIES
        ),
    )
    evidence_a = validate_loso_prediction_set(contract, rows_a)
    evidence_b = validate_loso_prediction_set(contract, tuple(rows_b))
    summary_a = canonical_loso_execution_summary_bytes(evidence_a)
    summary_b = canonical_loso_execution_summary_bytes(evidence_b)

    assert [row.latency_ms for row in evidence_a.predictions] == [
        row.latency_ms for row in evidence_b.predictions
    ]
    assert summary_a == summary_b
    assert loso_execution_evidence_digest(evidence_a) == loso_execution_evidence_digest(evidence_b)
    assert evidence_a.prediction_content_sha256 != evidence_b.prediction_content_sha256
    assert "prediction_content_sha256" not in json.loads(summary_a)
    assert evidence_a.prediction_content_sha256.encode("ascii") not in summary_a
    assert evidence_a.prediction_content_sha256 not in repr(evidence_a)
    assert evidence_b.prediction_content_sha256 not in repr(evidence_b)


def test_validated_prediction_commitment_rejects_tampering_and_null_sentinel(tmp_path: Path):
    from human_feedback.evaluation_execution import validate_loso_prediction_set

    contract, _ = _contract(tmp_path)
    evidence = validate_loso_prediction_set(contract, _predictions(contract))
    changed_rows = list(evidence.predictions)
    changed_rows[0] = replace(changed_rows[0], latency_ms=changed_rows[0].latency_ms + 1.0)

    with pytest.raises(ValueError, match="prediction|content|commitment|digest|null|sentinel"):
        replace(evidence, prediction_content_sha256="0" * 64)
    with pytest.raises(ValueError, match="prediction|content|commitment|digest"):
        replace(evidence, predictions=tuple(changed_rows))


def test_public_summary_uses_safe_latency_aggregates_not_prediction_content_commitments(
    tmp_path: Path,
):
    from human_feedback.evaluation_execution import (
        canonical_loso_execution_summary_bytes,
        validate_loso_prediction_set,
    )

    contract, _ = _contract(tmp_path)
    rows_a = _predictions(contract)
    rows_b = list(rows_a)
    rows_b[0] = replace(rows_b[0], latency_ms=rows_b[0].latency_ms + 1.0)
    summary_a = canonical_loso_execution_summary_bytes(
        validate_loso_prediction_set(contract, rows_a)
    )
    summary_b = canonical_loso_execution_summary_bytes(
        validate_loso_prediction_set(contract, tuple(rows_b))
    )
    decoded = json.loads(summary_a)
    decoded_b = json.loads(summary_b)
    serialized_keys = json.dumps(decoded, sort_keys=True).lower()

    assert summary_a != summary_b
    assert "latency_ms_summary" in decoded
    assert set(decoded["latency_ms_summary"]) == {"count", "minimum", "maximum", "mean"}
    assert decoded["latency_ms_summary"]["count"] == len(rows_a)
    assert decoded["latency_ms_summary"] != decoded_b["latency_ms_summary"]
    assert {key for key in decoded if "latency" in key.lower()} == {"latency_ms_summary"}
    assert "prediction_content_sha256" not in decoded
    assert "probabilit" not in serialized_keys
    assert "score" not in serialized_keys
    assert "categor" not in serialized_keys
    assert "prediction_content" not in serialized_keys


def test_contract_evidence_and_summary_keep_unverified_attestations_false(tmp_path: Path):
    from human_feedback.evaluation_execution import (
        canonical_loso_execution_summary_bytes,
        validate_loso_prediction_set,
    )

    contract, _ = _contract(tmp_path)
    evidence = validate_loso_prediction_set(contract, _predictions(contract))
    summary = json.loads(canonical_loso_execution_summary_bytes(evidence))
    expected = {
        "runtime_identity_verified": False,
        "origin_verified": False,
        "gold_blind_execution_attested": False,
        "supply_identity_verified": False,
    }

    for field, value in expected.items():
        assert getattr(contract, field) is value
        assert getattr(evidence, field) is value
        assert summary[field] is value


@pytest.mark.parametrize("provider", ["other-provider", "Laya-http", "laya_http"])
def test_execution_contract_and_raw_prediction_reject_non_laya_provider(
    tmp_path: Path,
    provider: str,
):
    contract, _ = _contract(tmp_path)
    prediction = _predictions(contract)[0]

    with pytest.raises(ValueError, match="provider|laya-http"):
        replace(contract, provider=provider)
    with pytest.raises(ValueError, match="provider|laya-http"):
        replace(prediction, provider=provider)


@pytest.mark.parametrize(
    "revision",
    [
        "0" * 40,
        "55cf4c4",
        "55CF4C4EBB4EBE31B2550E8BDF3BD21B99753851",
        "g" * 40,
        "55cf4c4ebb4ebe31b2550e8bdf3bd21b997538510",
    ],
)
def test_execution_contract_and_raw_prediction_require_non_null_lowercase_sha1_revision(
    tmp_path: Path,
    revision: str,
):
    contract, _ = _contract(tmp_path)
    prediction = _predictions(contract)[0]

    with pytest.raises(ValueError, match="model|revision|SHA-1|null|sentinel"):
        replace(contract, model_revision=revision)
    with pytest.raises(ValueError, match="model|revision|SHA-1|null|sentinel"):
        replace(prediction, model_revision=revision)


def test_validated_evidence_does_not_claim_execution_or_scientific_authorization(tmp_path: Path):
    from human_feedback.evaluation_execution import validate_loso_prediction_set

    contract, _ = _contract(tmp_path)
    validated = validate_loso_prediction_set(contract, _predictions(contract))

    assert contract.structurally_valid is True
    assert contract.execution_completed is False
    assert contract.scientifically_sufficient is False
    assert contract.eligible_for_shadow_review is False
    assert contract.production_enablement_authorized is False
    assert validated.execution_evidence_validated is True
    assert validated.execution_completed is False
    assert validated.scientifically_sufficient is False
    assert validated.eligible_for_shadow_review is False
    assert validated.production_enablement_authorized is False
    assert not hasattr(validated, "__dict__")
    with pytest.raises(FrozenInstanceError):
        validated.execution_evidence_validated = False  # type: ignore[misc]
    with pytest.raises(ValueError, match="prediction|evidence|digest|contract"):
        replace(validated, predictions=validated.predictions[:-1])


def test_evaluation_execution_is_isolated_from_operational_and_scientific_flows():
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
            if "human_feedback.evaluation_execution" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(repository).as_posix())
    for path in forbidden_files:
        if "human_feedback.evaluation_execution" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []
