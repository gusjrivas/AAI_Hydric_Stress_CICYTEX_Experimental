"""RED contract for exact-issued human-evaluation preregistration authority.

These tests use only the existing synthetic preregistration fixture.  They do
not execute a model, open a scientific corpus, or elevate evaluation claims.
"""

from __future__ import annotations

import gc
import importlib
import inspect
import json
import threading
import weakref
from dataclasses import fields, replace

import pytest

from tests.test_laya_human_evaluation_preregistration import _inputs


def _module():
    return importlib.import_module("human_feedback.evaluation_preregistration")


def _issued(tmp_path):
    module = _module()
    raw, corpus, plan, artifacts, records = _inputs(tmp_path)
    protocol = module.verify_human_evaluation_preregistration(
        raw,
        corpus=corpus,
        plan=plan,
        external_artifacts=artifacts,
    )
    return module, protocol, records


def _require(module, value):
    if not hasattr(module, "_require_issued_human_evaluation_preregistration"):
        pytest.skip("private exact-issued preregistration authority is not implemented yet")
    return module._require_issued_human_evaluation_preregistration(value)


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


def test_private_exact_issued_authority_surface_and_v1_summary_remain_unchanged(tmp_path):
    module, protocol, _records = _issued(tmp_path)
    summary_before = module.canonical_human_evaluation_preregistration_summary_bytes(protocol)
    digest_before = module.human_evaluation_preregistration_evidence_digest(protocol)

    assert len(summary_before) == 3940
    assert digest_before == "4795642aa966fa650c92b6d011e8756658a99aeda7a8078e758a4b2b4be76e2e"
    assert hasattr(module, "_require_issued_human_evaluation_preregistration")
    helper = module._require_issued_human_evaluation_preregistration
    assert tuple(inspect.signature(helper).parameters) == ("value",)
    assert helper(protocol) is protocol
    assert (
        module.canonical_human_evaluation_preregistration_summary_bytes(protocol) == summary_before
    )
    assert module.human_evaluation_preregistration_evidence_digest(protocol) == digest_before
    assert set(json.loads(summary_before)) == {
        "schema_version",
        "protocol_id",
        "frozen_at",
        "corpus_id",
        "evaluation_corpus_sha256",
        "loso_plan_sha256",
        "loso_assignment_sha256",
        "required_sites",
        "cohort",
        "analysis",
        "external_artifacts",
        "external_artifacts_verified",
        "cohort_constraints_satisfied",
        "evaluation_executed",
        "scientifically_sufficient",
        "eligible_for_shadow_review",
        "production_enablement_authorized",
    }


def test_structural_clones_and_known_seal_construction_are_not_authority(tmp_path):
    module, protocol, records = _issued(tmp_path)
    constructor_values = {
        item.name: getattr(protocol, item.name) for item in fields(protocol) if item.init
    }
    known_seal_clone = type(protocol)(
        **constructor_values,
        _verification_seal=module._VERIFICATION_SEAL,
    )
    replaced = replace(protocol, _verification_seal=module._VERIFICATION_SEAL)
    candidates = (
        _clone_exact(protocol),
        known_seal_clone,
        replaced,
        object.__new__(type(protocol)),
    )

    for candidate in candidates:
        with pytest.raises((TypeError, ValueError)) as captured:
            _require(module, candidate)
        _private_failure(
            captured.value,
            records[0]["comment"],
            records[0]["gold_category"],
            protocol.evaluation_corpus_sha256,
        )


def test_nested_corpus_mutations_invalidate_exact_authority_privately(tmp_path):
    module, protocol, records = _issued(tmp_path)
    record = protocol.corpus.records[0]
    mutations = (
        ("comment", "PRIVATE-COMMENT-CANARY"),
        ("gold_category", "PRIVATE-GOLD-CANARY"),
        ("annotations", ()),
    )

    for name, invalid in mutations:
        original = getattr(record, name)
        object.__setattr__(record, name, invalid)
        try:
            with pytest.raises((TypeError, ValueError)) as captured:
                _require(module, protocol)
            _private_failure(
                captured.value,
                "PRIVATE-COMMENT-CANARY",
                "PRIVATE-GOLD-CANARY",
                records[0]["group_id"],
            )
        finally:
            object.__setattr__(record, name, original)
    assert _require(module, protocol) is protocol


def test_nested_protocol_artifact_and_plan_mutations_invalidate_authority(tmp_path):
    module, protocol, _records = _issued(tmp_path)
    mutations = (
        (protocol.cohort, "minimum_total_examples", 61),
        (protocol.analysis, "bootstrap_seed", 20_261_018),
        (protocol.artifacts[0], "artifact_id", "PRIVATE-ARTIFACT-CANARY"),
        (protocol.plan, "assignment_sha256", "f" * 64),
    )

    for owner, name, invalid in mutations:
        original = getattr(owner, name)
        object.__setattr__(owner, name, invalid)
        try:
            with pytest.raises((TypeError, ValueError)) as captured:
                _require(module, protocol)
            _private_failure(
                captured.value,
                "PRIVATE-ARTIFACT-CANARY",
                protocol.evaluation_corpus_sha256,
                "f" * 64,
            )
        finally:
            object.__setattr__(owner, name, original)
    assert _require(module, protocol) is protocol


def test_issued_registry_releases_expired_keys(tmp_path):
    module, protocol, _records = _issued(tmp_path)
    _require(module, protocol)
    registry = module._ISSUED_HUMAN_EVALUATION_PREREGISTRATIONS
    key = id(protocol)
    reference = weakref.ref(protocol)

    del protocol
    gc.collect()

    assert reference() is None
    assert key not in registry


def test_issued_registry_rejects_a_foreign_reference_at_the_current_key(tmp_path):
    module, protocol, records = _issued(tmp_path)
    _require(module, protocol)
    registry = module._ISSUED_HUMAN_EVALUATION_PREREGISTRATIONS
    original_record = registry[id(protocol)]
    foreign = _clone_exact(protocol)
    stale_record = replace(original_record, reference=weakref.ref(foreign))
    registry[id(protocol)] = stale_record
    try:
        with pytest.raises((TypeError, ValueError)) as captured:
            _require(module, protocol)
        _private_failure(
            captured.value,
            records[0]["comment"],
            records[0]["group_id"],
            protocol.loso_assignment_sha256,
        )
    finally:
        registry[id(protocol)] = original_record


def test_concurrent_exact_authority_checks_are_safe_and_identity_preserving(tmp_path):
    module, protocol, _records = _issued(tmp_path)
    _require(module, protocol)
    barrier = threading.Barrier(3)
    results = []
    errors = []

    def validate() -> None:
        try:
            barrier.wait(timeout=5)
            results.append(_require(module, protocol))
        except BaseException as error:  # pragma: no cover - asserted below
            errors.append(error)

    threads = [threading.Thread(target=validate, daemon=False) for _ in range(2)]
    for thread in threads:
        thread.start()
    try:
        barrier.wait(timeout=5)
    finally:
        for thread in threads:
            thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert results == [protocol, protocol]
