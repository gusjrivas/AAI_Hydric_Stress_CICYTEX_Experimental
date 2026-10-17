"""Pure RED contract for the blocked gold-blind LOSO run protocol.

The fixture is synthetic structural authority only.  These tests never open a
scientific holdout, invoke an executor, or authorize calibration or evaluation.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import fields, replace
from pathlib import Path

import pytest
from human_feedback.evaluation_run_protocol import (
    HumanLosoExecutionProtocol,
    canonical_human_loso_execution_protocol_summary_bytes,
    prepare_human_loso_execution_protocol,
)

from human_feedback.evaluation_preregistration import (
    verify_human_evaluation_preregistration,
)
from tests.test_laya_human_evaluation_preregistration import _inputs

_SUMMARY_KEYS = {
    "schema_version",
    "status",
    "protocol_bound",
    "scientific_execution_completed",
    "calibration_fitted",
    "gold_blind_execution_attested",
    "scientifically_sufficient",
    "eligible_for_shadow_review",
    "production_enablement_authorized",
    "calibration_method_authorized",
    "outer_test_release_authorized",
}


def _issued_preregistration(tmp_path: Path):
    raw, corpus, plan, artifacts, records = _inputs(tmp_path)
    preregistration = verify_human_evaluation_preregistration(
        raw,
        corpus=corpus,
        plan=plan,
        external_artifacts=artifacts,
    )
    return preregistration, records


def _clone_exact(value):
    clone = object.__new__(type(value))
    for item in fields(value):
        object.__setattr__(clone, item.name, getattr(value, item.name))
    return clone


def _private_failure(error: BaseException, *private_values: object) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    rendered = repr((error.args, str(error), repr(error)))
    for value in private_values:
        assert str(value) not in rendered


def test_public_surface_and_blocked_defaults_are_closed(tmp_path):
    preregistration, _records = _issued_preregistration(tmp_path)
    protocol = prepare_human_loso_execution_protocol(preregistration)

    assert type(protocol) is HumanLosoExecutionProtocol
    assert tuple(inspect.signature(prepare_human_loso_execution_protocol).parameters) == (
        "preregistration",
    )
    assert tuple(
        inspect.signature(canonical_human_loso_execution_protocol_summary_bytes).parameters
    ) == ("protocol",)
    assert protocol.status == "BLOCKED_CORPUS_NOT_PROVIDED"
    assert protocol.protocol_bound is True
    for name in _SUMMARY_KEYS - {"schema_version", "status", "protocol_bound"}:
        assert getattr(protocol, name) is False


def test_summary_is_canonical_closed_and_contains_no_private_values_or_digests(tmp_path):
    preregistration, records = _issued_preregistration(tmp_path)
    protocol = prepare_human_loso_execution_protocol(preregistration)

    first = canonical_human_loso_execution_protocol_summary_bytes(protocol)
    second = canonical_human_loso_execution_protocol_summary_bytes(protocol)
    decoded = json.loads(first)

    assert first == second
    assert set(decoded) == _SUMMARY_KEYS
    private_values = {
        preregistration.protocol_id,
        preregistration.corpus_id,
        preregistration.evaluation_corpus_sha256,
        preregistration.loso_plan_sha256,
        preregistration.loso_assignment_sha256,
        records[0]["example_id"],
        records[0]["group_id"],
        records[0]["comment"],
        records[0]["gold_category"],
    }
    assert all(str(value).encode() not in first for value in private_values)
    assert all(str(value) not in repr(protocol) for value in private_values)


def test_preparation_accepts_the_same_exact_preregistration_more_than_once(tmp_path):
    preregistration, _records = _issued_preregistration(tmp_path)

    first = prepare_human_loso_execution_protocol(preregistration)
    second = prepare_human_loso_execution_protocol(preregistration)

    assert first is not second
    assert canonical_human_loso_execution_protocol_summary_bytes(first) == (
        canonical_human_loso_execution_protocol_summary_bytes(second)
    )


def test_cloned_preregistration_is_rejected_privately(tmp_path):
    preregistration, records = _issued_preregistration(tmp_path)

    with pytest.raises((TypeError, ValueError)) as caught:
        prepare_human_loso_execution_protocol(_clone_exact(preregistration))

    _private_failure(
        caught.value,
        records[0]["comment"],
        records[0]["gold_category"],
        preregistration.loso_assignment_sha256,
    )


def test_deep_binding_mutation_is_rejected_privately(tmp_path):
    preregistration, records = _issued_preregistration(tmp_path)
    mutations = (
        ("corpus", "records_sha256", "1" * 64),
        ("plan", "assignment_sha256", "2" * 64),
        ("preregistration", "loso_assignment_sha256", "3" * 64),
    )

    for owner_name, field_name, invalid in mutations:
        owner = (
            preregistration
            if owner_name == "preregistration"
            else getattr(preregistration, owner_name)
        )
        original = getattr(owner, field_name)
        object.__setattr__(owner, field_name, invalid)
        try:
            with pytest.raises((TypeError, ValueError)) as caught:
                prepare_human_loso_execution_protocol(preregistration)
            _private_failure(
                caught.value,
                records[0]["comment"],
                records[0]["gold_category"],
                invalid,
            )
        finally:
            object.__setattr__(owner, field_name, original)


def test_protocol_clone_and_dataclass_replace_cannot_gain_factory_authority(tmp_path):
    preregistration, records = _issued_preregistration(tmp_path)
    protocol = prepare_human_loso_execution_protocol(preregistration)

    with pytest.raises((TypeError, ValueError)):
        replace(protocol)
    with pytest.raises((TypeError, ValueError)) as caught:
        canonical_human_loso_execution_protocol_summary_bytes(_clone_exact(protocol))
    _private_failure(caught.value, records[0]["comment"], records[0]["gold_category"])


def test_pure_preparation_does_not_read_files_or_import_execution_adapters(tmp_path, monkeypatch):
    preregistration, _records = _issued_preregistration(tmp_path)
    protocol_module = inspect.getmodule(HumanLosoExecutionProtocol)
    assert protocol_module is not None
    source = inspect.getsource(protocol_module)
    assert "human_feedback.runtime_execution" not in source
    assert "human_feedback.adapters" not in source

    def forbidden(*_args, **_kwargs):
        raise AssertionError("pure preparation attempted external I/O")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)

    protocol = prepare_human_loso_execution_protocol(preregistration)
    assert protocol.status == "BLOCKED_CORPUS_NOT_PROVIDED"
