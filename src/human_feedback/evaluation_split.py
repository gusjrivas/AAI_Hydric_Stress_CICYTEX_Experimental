"""Deterministic, privacy-preserving LOSO evaluation partitions.

This module only builds a structural evaluation plan.  It deliberately does not
run an evaluation or attest scientific sufficiency or production readiness.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from human_feedback.evaluation_corpus import (
    EvaluationCorpus,
    EvaluationRecord,
    evaluation_corpus_digest,
)

SCHEMA_VERSION = "laya-loso-evaluation-plan-v1"
CALIBRATION_POLICY_ID = "laya-loso-group-calibration-sha256-v1"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _require_digest(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _record_ids(records: tuple[EvaluationRecord, ...]) -> set[str]:
    return {record.example_id for record in records}


def _validate_record_partition(
    records: object,
    *,
    label: str,
) -> tuple[EvaluationRecord, ...]:
    if not isinstance(records, tuple) or not records:
        raise ValueError(f"fold {label} partition must be a non-empty tuple")
    if any(not isinstance(record, EvaluationRecord) for record in records):
        raise ValueError(f"fold {label} partition contains invalid records")
    ids = [record.example_id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"fold {label} partition contains duplicate records")
    return records


@dataclass(frozen=True, slots=True)
class LosoEvaluationFold:
    """One leave-one-site-out fold with a group-safe calibration partition."""

    held_out_site: str
    fit_records: tuple[EvaluationRecord, ...] = field(repr=False)
    calibration_records: tuple[EvaluationRecord, ...] = field(repr=False)
    test_records: tuple[EvaluationRecord, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.held_out_site, str) or not self.held_out_site:
            raise ValueError("fold held-out site is invalid")

        fit = _validate_record_partition(self.fit_records, label="fit")
        calibration = _validate_record_partition(self.calibration_records, label="calibration")
        test = _validate_record_partition(self.test_records, label="test")

        fit_ids = _record_ids(fit)
        calibration_ids = _record_ids(calibration)
        test_ids = _record_ids(test)
        if (
            not fit_ids.isdisjoint(calibration_ids)
            or not fit_ids.isdisjoint(test_ids)
            or not calibration_ids.isdisjoint(test_ids)
        ):
            raise ValueError("fold partitions overlap")

        partition_by_group: dict[str, str] = {}
        for partition_name, records in (
            ("fit", fit),
            ("calibration", calibration),
            ("test", test),
        ):
            for record in records:
                previous = partition_by_group.setdefault(record.group_id, partition_name)
                if previous != partition_name:
                    raise ValueError("fold partitions split a group")

        if {record.site_id for record in test} != {self.held_out_site}:
            raise ValueError("fold test partition does not match held-out site")
        if any(record.site_id == self.held_out_site for record in fit + calibration):
            raise ValueError("fold training partition contains held-out site")
        if {record.site_id for record in fit} != {record.site_id for record in calibration}:
            raise ValueError("fold training sites must contribute to both partitions")


def _private_assignment_payload(
    folds: tuple[LosoEvaluationFold, ...],
) -> dict[str, object]:
    return {
        "domain": "laya-loso-private-assignment-v1",
        "calibration_policy_id": CALIBRATION_POLICY_ID,
        "folds": [
            {
                "held_out_site": fold.held_out_site,
                "fit": [
                    [record.site_id, record.group_id, record.example_id]
                    for record in fold.fit_records
                ],
                "calibration": [
                    [record.site_id, record.group_id, record.example_id]
                    for record in fold.calibration_records
                ],
                "test": [
                    [record.site_id, record.group_id, record.example_id]
                    for record in fold.test_records
                ],
            }
            for fold in folds
        ],
    }


def _assignment_digest(folds: tuple[LosoEvaluationFold, ...]) -> str:
    return hashlib.sha256(_canonical_json_bytes(_private_assignment_payload(folds))).hexdigest()


def _calibration_groups_by_site(corpus: EvaluationCorpus) -> dict[str, frozenset[str]]:
    groups_by_site = {
        site_id: {record.group_id for record in corpus.records if record.site_id == site_id}
        for site_id in corpus.required_sites
    }
    if any(len(group_ids) < 2 for group_ids in groups_by_site.values()):
        raise ValueError("evaluation plan requires at least two groups per site")
    return {
        site_id: frozenset(
            sorted(group_ids, key=lambda group_id: _allocation_key(site_id, group_id))[
                : math.ceil(len(group_ids) * 0.20)
            ]
        )
        for site_id, group_ids in groups_by_site.items()
    }


@dataclass(frozen=True, slots=True)
class LosoEvaluationPlan:
    """Validated structural LOSO plan tied to one sealed evaluation corpus."""

    schema_version: str
    calibration_policy_id: str
    corpus: EvaluationCorpus = field(repr=False)
    folds: tuple[LosoEvaluationFold, ...]
    assignment_sha256: str = field(repr=False)
    structurally_valid: bool = field(default=True, init=False)
    evaluation_executed: bool = field(default=False, init=False)
    calibration_fitted: bool = field(default=False, init=False)
    scientifically_sufficient: bool = field(default=False, init=False)
    eligible_for_shadow_review: bool = field(default=False, init=False)
    production_enablement_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("plan schema version is invalid")
        if self.calibration_policy_id != CALIBRATION_POLICY_ID:
            raise ValueError("plan calibration policy is invalid")
        if not isinstance(self.corpus, EvaluationCorpus):
            raise ValueError("plan evaluation corpus is invalid")
        if not isinstance(self.folds, tuple) or not self.folds:
            raise ValueError("plan folds must be a non-empty tuple")
        if any(not isinstance(fold, LosoEvaluationFold) for fold in self.folds):
            raise ValueError("plan folds are invalid")
        if tuple(fold.held_out_site for fold in self.folds) != self.corpus.required_sites:
            raise ValueError("plan fold sites are invalid")

        corpus_by_id = {record.example_id: record for record in self.corpus.records}
        corpus_ids = set(corpus_by_id)
        expected_training_sites = set(self.corpus.required_sites)
        site_order = {site_id: index for index, site_id in enumerate(self.corpus.required_sites)}
        calibration_groups = _calibration_groups_by_site(self.corpus)
        for fold in self.folds:
            partition_records = fold.fit_records + fold.calibration_records + fold.test_records
            if _record_ids(partition_records) != corpus_ids:
                raise ValueError("plan fold partition is not exhaustive")
            if any(corpus_by_id.get(record.example_id) != record for record in partition_records):
                raise ValueError("plan fold partition does not match evaluation corpus")
            training_sites = expected_training_sites - {fold.held_out_site}
            if {record.site_id for record in fold.fit_records} != training_sites:
                raise ValueError("plan fold fit sites are invalid")
            if {record.site_id for record in fold.calibration_records} != training_sites:
                raise ValueError("plan fold calibration sites are invalid")
            expected_test = tuple(
                record for record in self.corpus.records if record.site_id == fold.held_out_site
            )
            expected_calibration = tuple(
                record
                for record in self.corpus.records
                if record.site_id != fold.held_out_site
                and record.group_id in calibration_groups[record.site_id]
            )
            expected_fit = tuple(
                record
                for record in self.corpus.records
                if record.site_id != fold.held_out_site
                and record.group_id not in calibration_groups[record.site_id]
            )
            expected_partitions = tuple(
                tuple(
                    sorted(
                        records,
                        key=lambda item: _record_order(item, site_order=site_order),
                    )
                )
                for records in (expected_fit, expected_calibration, expected_test)
            )
            if (
                fold.fit_records,
                fold.calibration_records,
                fold.test_records,
            ) != expected_partitions:
                raise ValueError("plan fold assignment violates calibration policy")

        _require_digest(self.assignment_sha256, label="assignment digest")
        if self.assignment_sha256 != _assignment_digest(self.folds):
            raise ValueError("assignment digest does not match plan partitions")


def _allocation_key(site_id: str, group_id: str) -> tuple[str, str]:
    separated = f"{CALIBRATION_POLICY_ID}\0{site_id}\0{group_id}".encode()
    return hashlib.sha256(separated).hexdigest(), group_id


def _record_order(
    record: EvaluationRecord,
    *,
    site_order: dict[str, int],
) -> tuple[int, str, str]:
    return site_order[record.site_id], record.group_id, record.example_id


def build_loso_evaluation_plan(corpus: EvaluationCorpus) -> LosoEvaluationPlan:
    """Build canonical LOSO folds with 20% of each training site's groups held out."""

    if not isinstance(corpus, EvaluationCorpus):
        raise ValueError("evaluation corpus is invalid")

    site_order = {site_id: index for index, site_id in enumerate(corpus.required_sites)}
    calibration_groups = _calibration_groups_by_site(corpus)

    folds: list[LosoEvaluationFold] = []
    for held_out_site in corpus.required_sites:
        test = tuple(record for record in corpus.records if record.site_id == held_out_site)
        calibration = tuple(
            record
            for record in corpus.records
            if record.site_id != held_out_site
            and record.group_id in calibration_groups[record.site_id]
        )
        fit = tuple(
            record
            for record in corpus.records
            if record.site_id != held_out_site
            and record.group_id not in calibration_groups[record.site_id]
        )
        folds.append(
            LosoEvaluationFold(
                held_out_site=held_out_site,
                fit_records=tuple(
                    sorted(fit, key=lambda item: _record_order(item, site_order=site_order))
                ),
                calibration_records=tuple(
                    sorted(
                        calibration,
                        key=lambda item: _record_order(item, site_order=site_order),
                    )
                ),
                test_records=tuple(
                    sorted(test, key=lambda item: _record_order(item, site_order=site_order))
                ),
            )
        )

    canonical_folds = tuple(folds)
    return LosoEvaluationPlan(
        schema_version=SCHEMA_VERSION,
        calibration_policy_id=CALIBRATION_POLICY_ID,
        corpus=corpus,
        folds=canonical_folds,
        assignment_sha256=_assignment_digest(canonical_folds),
    )


def canonical_loso_plan_summary_bytes(plan: LosoEvaluationPlan) -> bytes:
    """Return a deterministic public summary without private record identifiers."""

    if not isinstance(plan, LosoEvaluationPlan):
        raise ValueError("evaluation plan is invalid")
    payload = {
        "schema_version": plan.schema_version,
        "calibration_policy_id": plan.calibration_policy_id,
        "corpus_id": plan.corpus.corpus_id,
        "evaluation_corpus_digest": evaluation_corpus_digest(plan.corpus),
        "sampling_protocol_id": plan.corpus.sampling_protocol_id,
        "sampling_protocol_sha256": plan.corpus.sampling_protocol_sha256,
        "structurally_valid": plan.structurally_valid,
        "evaluation_executed": plan.evaluation_executed,
        "calibration_fitted": plan.calibration_fitted,
        "scientifically_sufficient": plan.scientifically_sufficient,
        "eligible_for_shadow_review": plan.eligible_for_shadow_review,
        "production_enablement_authorized": plan.production_enablement_authorized,
        "folds": [
            {
                "held_out_site": fold.held_out_site,
                "fit_records_count": len(fold.fit_records),
                "fit_groups_count": len({record.group_id for record in fold.fit_records}),
                "calibration_records_count": len(fold.calibration_records),
                "calibration_groups_count": len(
                    {record.group_id for record in fold.calibration_records}
                ),
                "test_records_count": len(fold.test_records),
                "test_groups_count": len({record.group_id for record in fold.test_records}),
            }
            for fold in plan.folds
        ],
    }
    return _canonical_json_bytes(payload)


def loso_evaluation_plan_digest(plan: LosoEvaluationPlan) -> str:
    """Return the SHA-256 identity of the public LOSO plan summary."""

    return hashlib.sha256(canonical_loso_plan_summary_bytes(plan)).hexdigest()
