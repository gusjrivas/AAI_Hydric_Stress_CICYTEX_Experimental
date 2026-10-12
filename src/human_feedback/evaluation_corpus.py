"""Fail-closed contract for a private, adjudicated human evaluation corpus.

The validated object is deliberately provisional. It attests structural integrity
and provenance, never scientific sufficiency or production readiness.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

EvaluationCategory = Literal[
    "data_quality",
    "model_behavior",
    "agronomic_context",
    "usability",
    "other",
]

SCHEMA_VERSION = "laya-human-evaluation-corpus-v1"
EVIDENCE_ROLE = "human_corpus_candidate"
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
DECLARED_SOURCE_KIND = "human_field"

_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
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
        "rubric_version",
        "sampling_protocol_id",
        "sampling_protocol_sha256",
        "annotation_guide_id",
        "annotation_guide_sha256",
        "adjudication_protocol_id",
        "adjudication_protocol_sha256",
        "deidentification_protocol_id",
        "deidentification_protocol_sha256",
        "custody_digest",
        "frozen_at",
        "declared_source_kind",
        "deidentified",
        "privacy_reviewed",
    }
)
_RECORD_FIELDS = frozenset(
    {
        "example_id",
        "site_id",
        "group_id",
        "comment",
        "annotations",
        "adjudication",
        "gold_category",
    }
)
_ANNOTATION_FIELDS = frozenset({"annotator_id", "category"})
_ADJUDICATION_FIELDS = frozenset({"adjudicator_id", "category", "decision_ref"})


def _require_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty canonical string")
    return value


def _require_category(value: Any) -> EvaluationCategory:
    if not isinstance(value, str) or value not in CATEGORIES:
        raise ValueError("evaluation category is invalid")
    return cast(EvaluationCategory, value)


def _require_digest(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_utc_timestamp(value: Any) -> str:
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("frozen at must be a canonical UTC timestamp ending in Z")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ValueError("frozen at must be a valid canonical UTC timestamp") from error
    return value


@dataclass(frozen=True, slots=True)
class HumanAnnotation:
    annotator_id: str = field(repr=False)
    category: EvaluationCategory

    def __post_init__(self) -> None:
        _require_string(self.annotator_id, label="annotator id")
        _require_category(self.category)


@dataclass(frozen=True, slots=True)
class HumanAdjudication:
    adjudicator_id: str = field(repr=False)
    category: EvaluationCategory
    decision_ref: str = field(repr=False)

    def __post_init__(self) -> None:
        _require_string(self.adjudicator_id, label="adjudicator id")
        _require_category(self.category)
        _require_string(self.decision_ref, label="adjudication decision ref")


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    example_id: str = field(repr=False)
    site_id: str
    group_id: str = field(repr=False)
    comment: str = field(repr=False)
    annotations: tuple[HumanAnnotation, ...] = field(repr=False)
    adjudication: HumanAdjudication | None = field(repr=False)
    gold_category: EvaluationCategory

    def __post_init__(self) -> None:
        _require_string(self.example_id, label="example id")
        if _require_string(self.site_id, label="site id") not in REQUIRED_SITES:
            raise ValueError("record site must be one of the required sites")
        _require_string(self.group_id, label="group id")
        _require_string(self.comment, label="comment")
        if not isinstance(self.annotations, tuple) or not self.annotations:
            raise ValueError("record annotations must be a non-empty tuple")
        if any(not isinstance(annotation, HumanAnnotation) for annotation in self.annotations):
            raise ValueError("record annotations are invalid")
        if self.adjudication is not None and not isinstance(self.adjudication, HumanAdjudication):
            raise ValueError("record adjudication is invalid")
        _require_category(self.gold_category)


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
    rubric_version: str
    sampling_protocol_id: str
    sampling_protocol_sha256: str
    annotation_guide_id: str
    annotation_guide_sha256: str
    adjudication_protocol_id: str
    adjudication_protocol_sha256: str
    deidentification_protocol_id: str
    deidentification_protocol_sha256: str
    custody_digest: str
    frozen_at: str
    declared_source_kind: str
    deidentified: bool
    privacy_reviewed: bool
    records: tuple[EvaluationRecord, ...] = field(repr=False)
    structurally_valid: bool = field(default=True, init=False)
    scientifically_sufficient: bool = field(default=False, init=False)
    production_enablement_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Prevent direct construction or ``replace`` from self-attesting invalid data."""

        _validate_corpus_metadata(self)
        if not isinstance(self.records, tuple) or not self.records:
            raise ValueError("structurally valid corpus requires validated loader records")
        if any(not isinstance(record, EvaluationRecord) for record in self.records):
            raise ValueError("structurally valid corpus records are invalid")
        if self.records_count != len(self.records):
            raise ValueError("structurally valid corpus records count mismatch")
        _validate_cohort(self.records)
        actual_digest = hashlib.sha256(_canonical_record_objects_bytes(self.records)).hexdigest()
        if self.records_sha256 != actual_digest:
            raise ValueError("structurally valid corpus records digest mismatch")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON object contains duplicate fields")
        result[key] = value
    return result


def _reject_non_finite(_value: str) -> None:
    raise ValueError("JSON non-finite numbers are not permitted")


def _load_json(path: Path, *, expected: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{expected} JSON could not be read") from error


def _require_object(value: Any, fields: frozenset[str], *, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{kind} must contain exactly the contracted fields")
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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
    return _canonical_json_bytes(normalized)


def _record_payload(record: EvaluationRecord) -> dict[str, Any]:
    adjudication = record.adjudication
    return {
        "example_id": record.example_id,
        "site_id": record.site_id,
        "group_id": record.group_id,
        "comment": record.comment,
        "annotations": [
            {"annotator_id": annotation.annotator_id, "category": annotation.category}
            for annotation in sorted(
                record.annotations, key=lambda annotation: annotation.annotator_id
            )
        ],
        "adjudication": (
            None
            if adjudication is None
            else {
                "adjudicator_id": adjudication.adjudicator_id,
                "category": adjudication.category,
                "decision_ref": adjudication.decision_ref,
            }
        ),
        "gold_category": record.gold_category,
    }


def _canonical_record_objects_bytes(records: tuple[EvaluationRecord, ...]) -> bytes:
    return _canonical_json_bytes(
        [_record_payload(record) for record in sorted(records, key=lambda item: item.example_id)]
    )


def _parse_adjudication(value: Any) -> HumanAdjudication | None:
    if value is None:
        return None
    adjudication = _require_object(value, _ADJUDICATION_FIELDS, kind="adjudication")
    return HumanAdjudication(
        adjudicator_id=_require_string(adjudication["adjudicator_id"], label="adjudicator id"),
        category=_require_category(adjudication["category"]),
        decision_ref=_require_string(
            adjudication["decision_ref"], label="adjudication decision ref"
        ),
    )


def _parse_records(raw: Any) -> tuple[list[dict[str, Any]], tuple[EvaluationRecord, ...]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("records must be a non-empty JSON array")

    canonical_inputs: list[dict[str, Any]] = []
    records: list[EvaluationRecord] = []
    for item in raw:
        raw_record = _require_object(item, _RECORD_FIELDS, kind="record")
        annotations_raw = raw_record["annotations"]
        if not isinstance(annotations_raw, list) or not annotations_raw:
            raise ValueError("each record requires annotations")

        annotations: list[HumanAnnotation] = []
        canonical_annotations: list[dict[str, Any]] = []
        for item_annotation in annotations_raw:
            annotation = _require_object(item_annotation, _ANNOTATION_FIELDS, kind="annotation")
            annotator_id = _require_string(annotation["annotator_id"], label="annotator id")
            category = _require_category(annotation["category"])
            annotations.append(HumanAnnotation(annotator_id=annotator_id, category=category))
            canonical_annotations.append({"annotator_id": annotator_id, "category": category})

        example_id = _require_string(raw_record["example_id"], label="example id")
        site_id = _require_string(raw_record["site_id"], label="site id")
        group_id = _require_string(raw_record["group_id"], label="group id")
        comment = _require_string(raw_record["comment"], label="comment")
        adjudication = _parse_adjudication(raw_record["adjudication"])
        gold = _require_category(raw_record["gold_category"])
        canonical_record = {
            "example_id": example_id,
            "site_id": site_id,
            "group_id": group_id,
            "comment": comment,
            "annotations": canonical_annotations,
            "adjudication": (
                None
                if adjudication is None
                else {
                    "adjudicator_id": adjudication.adjudicator_id,
                    "category": adjudication.category,
                    "decision_ref": adjudication.decision_ref,
                }
            ),
            "gold_category": gold,
        }
        canonical_inputs.append(canonical_record)
        records.append(
            EvaluationRecord(
                example_id=example_id,
                site_id=site_id,
                group_id=group_id,
                comment=comment,
                annotations=tuple(
                    sorted(annotations, key=lambda annotation: annotation.annotator_id)
                ),
                adjudication=adjudication,
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
    _require_digest(manifest["records_sha256"], label="manifest records digest")
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

    for field_name, label in (
        ("rubric_version", "rubric version"),
        ("sampling_protocol_id", "sampling protocol id"),
        ("annotation_guide_id", "annotation guide id"),
        ("adjudication_protocol_id", "adjudication protocol id"),
        ("deidentification_protocol_id", "deidentification protocol id"),
    ):
        _require_string(manifest[field_name], label=label)
    for field_name, label in (
        ("sampling_protocol_sha256", "sampling protocol digest"),
        ("annotation_guide_sha256", "annotation guide digest"),
        ("adjudication_protocol_sha256", "adjudication protocol digest"),
        ("deidentification_protocol_sha256", "deidentification protocol digest"),
        ("custody_digest", "custody digest"),
    ):
        _require_digest(manifest[field_name], label=label)
    _require_utc_timestamp(manifest["frozen_at"])
    if manifest["declared_source_kind"] != DECLARED_SOURCE_KIND:
        raise ValueError("manifest source kind must be human field data")
    if manifest["deidentified"] is not True:
        raise ValueError("manifest must attest that records are deidentified")
    if manifest["privacy_reviewed"] is not True:
        raise ValueError("manifest must attest that privacy reviewed is true")
    return manifest


def _validate_corpus_metadata(corpus: EvaluationCorpus) -> None:
    if corpus.schema_version != SCHEMA_VERSION:
        raise ValueError("structurally valid corpus schema version is invalid")
    _require_string(corpus.corpus_id, label="corpus id")
    if corpus.evidence_role != EVIDENCE_ROLE:
        raise ValueError("structurally valid corpus evidence role is invalid")
    if corpus.required_sites != REQUIRED_SITES:
        raise ValueError("structurally valid corpus required sites are invalid")
    if type(corpus.records_count) is not int or corpus.records_count <= 0:
        raise ValueError("structurally valid corpus records count must be a positive integer")
    if (
        type(corpus.minimum_annotators_per_example) is not int
        or corpus.minimum_annotators_per_example != MINIMUM_ANNOTATORS_PER_EXAMPLE
    ):
        raise ValueError("structurally valid corpus annotator minimum must be an integer")
    if corpus.adjudication_policy != ADJUDICATION_POLICY:
        raise ValueError("structurally valid corpus adjudication policy is invalid")
    _require_digest(corpus.records_sha256, label="records digest")
    for value, label in (
        (corpus.rubric_version, "rubric version"),
        (corpus.sampling_protocol_id, "sampling protocol id"),
        (corpus.annotation_guide_id, "annotation guide id"),
        (corpus.adjudication_protocol_id, "adjudication protocol id"),
        (corpus.deidentification_protocol_id, "deidentification protocol id"),
    ):
        _require_string(value, label=label)
    for value, label in (
        (corpus.sampling_protocol_sha256, "sampling protocol digest"),
        (corpus.annotation_guide_sha256, "annotation guide digest"),
        (corpus.adjudication_protocol_sha256, "adjudication protocol digest"),
        (corpus.deidentification_protocol_sha256, "deidentification protocol digest"),
        (corpus.custody_digest, "custody digest"),
    ):
        _require_digest(value, label=label)
    _require_utc_timestamp(corpus.frozen_at)
    if corpus.declared_source_kind != DECLARED_SOURCE_KIND:
        raise ValueError("structurally valid corpus source kind is invalid")
    if corpus.deidentified is not True or corpus.privacy_reviewed is not True:
        raise ValueError("structurally valid corpus requires privacy attestations")


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
            if record.adjudication is not None:
                raise ValueError("adjudication is invalid when annotations agree")
            if record.gold_category != consensus:
                raise ValueError("gold category must match annotation consensus")
        else:
            if record.adjudication is None:
                raise ValueError("annotation disagreement requires explicit adjudication")
            if record.adjudication.adjudicator_id in annotator_ids:
                raise ValueError("adjudicator must be a distinct third reviewer")
            if record.gold_category != record.adjudication.category:
                raise ValueError("gold category must match explicit adjudication")


def load_evaluation_corpus(manifest_path: str | Path, records_path: str | Path) -> EvaluationCorpus:
    """Load the private corpus only after all structural checks succeed."""

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
        rubric_version=manifest["rubric_version"],
        sampling_protocol_id=manifest["sampling_protocol_id"],
        sampling_protocol_sha256=manifest["sampling_protocol_sha256"],
        annotation_guide_id=manifest["annotation_guide_id"],
        annotation_guide_sha256=manifest["annotation_guide_sha256"],
        adjudication_protocol_id=manifest["adjudication_protocol_id"],
        adjudication_protocol_sha256=manifest["adjudication_protocol_sha256"],
        deidentification_protocol_id=manifest["deidentification_protocol_id"],
        deidentification_protocol_sha256=manifest["deidentification_protocol_sha256"],
        custody_digest=manifest["custody_digest"],
        frozen_at=manifest["frozen_at"],
        declared_source_kind=DECLARED_SOURCE_KIND,
        deidentified=True,
        privacy_reviewed=True,
        records=ordered_records,
    )


def canonical_corpus_summary_bytes(corpus: EvaluationCorpus) -> bytes:
    """Return deterministic public metadata without private record payloads."""

    payload = {
        "schema_version": corpus.schema_version,
        "corpus_id": corpus.corpus_id,
        "evidence_role": corpus.evidence_role,
        "records_count": corpus.records_count,
        "records_sha256": corpus.records_sha256,
        "required_sites": list(corpus.required_sites),
        "minimum_annotators_per_example": corpus.minimum_annotators_per_example,
        "adjudication_policy": corpus.adjudication_policy,
        "rubric_version": corpus.rubric_version,
        "sampling_protocol_id": corpus.sampling_protocol_id,
        "sampling_protocol_sha256": corpus.sampling_protocol_sha256,
        "annotation_guide_id": corpus.annotation_guide_id,
        "annotation_guide_sha256": corpus.annotation_guide_sha256,
        "adjudication_protocol_id": corpus.adjudication_protocol_id,
        "adjudication_protocol_sha256": corpus.adjudication_protocol_sha256,
        "deidentification_protocol_id": corpus.deidentification_protocol_id,
        "deidentification_protocol_sha256": corpus.deidentification_protocol_sha256,
        "custody_digest": corpus.custody_digest,
        "frozen_at": corpus.frozen_at,
        "declared_source_kind": corpus.declared_source_kind,
        "deidentified": corpus.deidentified,
        "privacy_reviewed": corpus.privacy_reviewed,
        "structurally_valid": corpus.structurally_valid,
        "scientifically_sufficient": corpus.scientifically_sufficient,
        "production_enablement_authorized": corpus.production_enablement_authorized,
    }
    return _canonical_json_bytes(payload)


def evaluation_corpus_digest(corpus: EvaluationCorpus) -> str:
    """Return the SHA-256 identity of the public summary and sealed private digest."""

    return hashlib.sha256(canonical_corpus_summary_bytes(corpus)).hexdigest()
