"""Sealed contract for an independently adjudicated human evaluation corpus.

This module deliberately has no connection to readiness or operational flows.  It
only verifies and materializes a private corpus contract; scientific sufficiency
is established by a later protocol.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

EvaluationCategory = Literal[
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
]

SCHEMA_VERSION = "laya-human-evaluation-corpus-v1"
EVIDENCE_ROLE = "human_cross_site"
REQUIRED_SITES = ("cicytex", "melchor-romero", "pergamino")
CATEGORIES: tuple[EvaluationCategory, ...] = (
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
)
MINIMUM_ANNOTATORS_PER_EXAMPLE = 2
ADJUDICATION_POLICY = "agreement_or_explicit_adjudication"

_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "corpus_id",
        "evidence_role",
        "records_count",
        "records_sha256",
        "required_sites",
        "minimum_annotators_per_example",
        "adjudication_policy",
    }
)
_RECORD_FIELDS = frozenset(
    {
        "example_id",
        "site_id",
        "group_id",
        "comment",
        "annotations",
        "adjudicated_category",
        "gold_category",
    }
)
_ANNOTATION_FIELDS = frozenset({"annotator_id", "category"})


@dataclass(frozen=True, slots=True)
class HumanAnnotation:
    annotator_id: str = field(repr=False)
    category: EvaluationCategory


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    example_id: str = field(repr=False)
    site_id: str
    group_id: str = field(repr=False)
    comment: str = field(repr=False)
    annotations: tuple[HumanAnnotation, ...] = field(repr=False)
    adjudicated_category: EvaluationCategory | None
    gold_category: EvaluationCategory


@dataclass(frozen=True, slots=True)
class EvaluationCorpus:
    schema_version: str
    corpus_id: str
    evidence_role: str
    records_count: int
    records_sha256: str
    required_sites: tuple[str, ...]
    minimum_annotators_per_example: int
    adjudication_policy: str
    records: tuple[EvaluationRecord, ...] = field(repr=False)
    structurally_valid: bool = field(default=True, init=False)
    scientifically_sufficient: bool = field(default=False, init=False)
    production_enablement_authorized: bool = field(default=False, init=False)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON object contains duplicate fields")
        result[key] = value
    return result


def _load_json(path: Path, *, expected: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("JSON non-finite numbers are not permitted")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{expected} JSON could not be read") from error


def _require_object(value: Any, fields: frozenset[str], *, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{kind} must contain exactly the contracted fields")
    return value


def _require_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty canonical string")
    return value


def _require_category(value: Any, *, optional: bool = False) -> EvaluationCategory | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or value not in CATEGORIES:
        raise ValueError("evaluation category is invalid")
    return value  # type: ignore[return-value]


def _canonical_raw_records(records: list[dict[str, Any]]) -> bytes:
    normalized: list[dict[str, Any]] = []
    for raw_record in records:
        record = dict(raw_record)
        record["annotations"] = sorted(
            (dict(annotation) for annotation in raw_record["annotations"]),
            key=lambda annotation: annotation["annotator_id"],
        )
        normalized.append(record)
    normalized.sort(key=lambda record: record["example_id"])
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _parse_records(raw: Any) -> tuple[list[dict[str, Any]], tuple[EvaluationRecord, ...]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("records must be a non-empty JSON array")

    canonical_inputs: list[dict[str, Any]] = []
    records: list[EvaluationRecord] = []
    for item in raw:
        record = _require_object(item, _RECORD_FIELDS, kind="record")
        annotations_raw = record["annotations"]
        if not isinstance(annotations_raw, list) or not annotations_raw:
            raise ValueError("each record requires annotations")

        annotations: list[HumanAnnotation] = []
        canonical_annotations: list[dict[str, Any]] = []
        for item_annotation in annotations_raw:
            annotation = _require_object(item_annotation, _ANNOTATION_FIELDS, kind="annotation")
            annotator_id = _require_string(annotation["annotator_id"], label="annotator id")
            category = _require_category(annotation["category"])
            assert category is not None
            annotations.append(HumanAnnotation(annotator_id=annotator_id, category=category))
            canonical_annotations.append({"annotator_id": annotator_id, "category": category})

        example_id = _require_string(record["example_id"], label="example id")
        site_id = _require_string(record["site_id"], label="site id")
        group_id = _require_string(record["group_id"], label="group id")
        comment = _require_string(record["comment"], label="comment")
        adjudicated = _require_category(record["adjudicated_category"], optional=True)
        gold = _require_category(record["gold_category"])
        assert gold is not None

        canonical_inputs.append(
            {
                "example_id": example_id,
                "site_id": site_id,
                "group_id": group_id,
                "comment": comment,
                "annotations": canonical_annotations,
                "adjudicated_category": adjudicated,
                "gold_category": gold,
            }
        )
        records.append(
            EvaluationRecord(
                example_id=example_id,
                site_id=site_id,
                group_id=group_id,
                comment=comment,
                annotations=tuple(
                    sorted(annotations, key=lambda annotation: annotation.annotator_id)
                ),
                adjudicated_category=adjudicated,
                gold_category=gold,
            )
        )
    return canonical_inputs, tuple(records)


def _validate_manifest(raw: Any) -> dict[str, Any]:
    manifest = _require_object(raw, _MANIFEST_FIELDS, kind="manifest")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ValueError("manifest schema version is unsupported")
    _require_string(manifest["corpus_id"], label="corpus id")
    if manifest["evidence_role"] != EVIDENCE_ROLE:
        raise ValueError("manifest evidence role is invalid")
    if type(manifest["records_count"]) is not int or manifest["records_count"] <= 0:
        raise ValueError("manifest records count must be a positive integer")
    digest = manifest["records_sha256"]
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("manifest records digest must be lowercase SHA-256")
    required_sites = manifest["required_sites"]
    if not isinstance(required_sites, list) or tuple(required_sites) != REQUIRED_SITES:
        raise ValueError("manifest required sites are invalid")
    if (
        type(manifest["minimum_annotators_per_example"]) is not int
        or manifest["minimum_annotators_per_example"] != MINIMUM_ANNOTATORS_PER_EXAMPLE
    ):
        raise ValueError("manifest annotator minimum is invalid")
    if manifest["adjudication_policy"] != ADJUDICATION_POLICY:
        raise ValueError("manifest adjudication policy is invalid")
    return manifest


def _validate_cohort(records: tuple[EvaluationRecord, ...]) -> None:
    example_ids = [record.example_id for record in records]
    if len(example_ids) != len(set(example_ids)):
        raise ValueError("duplicate example is not permitted")

    group_sites: dict[str, str] = {}
    for record in records:
        previous_site = group_sites.setdefault(record.group_id, record.site_id)
        if previous_site != record.site_id:
            raise ValueError("a group cannot cross site boundaries")

    if {record.site_id for record in records} != set(REQUIRED_SITES):
        raise ValueError("records must cover exactly the required sites")

    for record in records:
        annotator_ids = [annotation.annotator_id for annotation in record.annotations]
        if (
            len(annotator_ids) != len(set(annotator_ids))
            or len(annotator_ids) < MINIMUM_ANNOTATORS_PER_EXAMPLE
        ):
            raise ValueError("every example requires at least two distinct annotators")

        categories = {annotation.category for annotation in record.annotations}
        if len(categories) == 1:
            consensus = next(iter(categories))
            if record.adjudicated_category is not None:
                raise ValueError("adjudication is invalid when annotations agree")
            if record.gold_category != consensus:
                raise ValueError("gold category must match annotation consensus")
        else:
            if record.adjudicated_category is None:
                raise ValueError("annotation disagreement requires explicit adjudication")
            if record.gold_category != record.adjudicated_category:
                raise ValueError("gold category must match explicit adjudication")


def load_evaluation_corpus(manifest_path: str | Path, records_path: str | Path) -> EvaluationCorpus:
    """Load a private corpus only after its sealed contract validates completely."""

    manifest = _validate_manifest(_load_json(Path(manifest_path), expected="manifest"))
    canonical_inputs, records = _parse_records(_load_json(Path(records_path), expected="records"))

    if manifest["records_count"] != len(records):
        raise ValueError("records count mismatch")
    actual_digest = hashlib.sha256(_canonical_raw_records(canonical_inputs)).hexdigest()
    if manifest["records_sha256"] != actual_digest:
        raise ValueError("records digest mismatch")

    _validate_cohort(records)
    site_order = {site: index for index, site in enumerate(REQUIRED_SITES)}
    ordered_records = tuple(
        sorted(records, key=lambda record: (site_order[record.site_id], record.example_id))
    )
    return EvaluationCorpus(
        schema_version=SCHEMA_VERSION,
        corpus_id=manifest["corpus_id"],
        evidence_role=EVIDENCE_ROLE,
        records_count=len(ordered_records),
        records_sha256=actual_digest,
        required_sites=REQUIRED_SITES,
        minimum_annotators_per_example=MINIMUM_ANNOTATORS_PER_EXAMPLE,
        adjudication_policy=ADJUDICATION_POLICY,
        records=ordered_records,
    )


def canonical_corpus_bytes(corpus: EvaluationCorpus) -> bytes:
    """Return the deterministic, sealed representation used for corpus identity."""

    payload = {
        "schema_version": corpus.schema_version,
        "corpus_id": corpus.corpus_id,
        "evidence_role": corpus.evidence_role,
        "records_count": corpus.records_count,
        "records_sha256": corpus.records_sha256,
        "required_sites": list(corpus.required_sites),
        "minimum_annotators_per_example": corpus.minimum_annotators_per_example,
        "adjudication_policy": corpus.adjudication_policy,
        "records": [
            {
                "example_id": record.example_id,
                "site_id": record.site_id,
                "group_id": record.group_id,
                "comment": record.comment,
                "annotations": [
                    {
                        "annotator_id": annotation.annotator_id,
                        "category": annotation.category,
                    }
                    for annotation in sorted(record.annotations, key=lambda item: item.annotator_id)
                ],
                "adjudicated_category": record.adjudicated_category,
                "gold_category": record.gold_category,
            }
            for record in sorted(corpus.records, key=lambda item: item.example_id)
        ],
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def evaluation_corpus_digest(corpus: EvaluationCorpus) -> str:
    """Return the SHA-256 identity of a validated corpus contract."""

    return hashlib.sha256(canonical_corpus_bytes(corpus)).hexdigest()
