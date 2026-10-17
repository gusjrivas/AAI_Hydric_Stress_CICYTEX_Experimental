"""RED contract for PR41 execution receipt and evidence authority.

These tests intentionally perform no Docker or real-model execution.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from dataclasses import replace

import pytest

from tests.test_laya_runtime_execution import (
    EXPECTED_EXECUTION_CLAIMS,
    _clone_exact,
    _issued_runtime,
    _private_failure,
)


def _module():
    return importlib.import_module("human_feedback.runtime_execution")


def _canonical_observation() -> bytes:
    prediction = {
        "choice": "data_quality",
        "probabilities": {
            "data_quality": 0.4,
            "model_behavior": 0.2,
            "agronomic_context": 0.15,
            "usability": 0.15,
            "other": 0.1,
        },
        "confidence": 0.0756,
        "answer_confidence": 0.43,
    }
    return json.dumps(
        {
            "schema_version": "laya-synthetic-execution-probe-v1",
            "predictions": [prediction, dict(prediction)],
        },
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _plan(monkeypatch, *, marker: str = "1"):
    module = _module()
    _chain, _supply, runtime, image_id, installation = _issued_runtime(monkeypatch, marker=marker)
    return (
        module,
        module.prepare_laya_runtime_execution_plan(runtime),
        runtime,
        image_id,
        installation,
    )


def _receipt(module, plan):
    return module._issue_laya_runtime_execution_receipt(plan, _canonical_observation())


def _external_replace_failure(error: BaseException, *private_values: str) -> None:
    """Check stdlib replace privacy without imposing core-facade suppression."""

    assert error.__cause__ is None
    assert error.__context__ is None
    rendered = repr((error.args, str(error), repr(error)))
    for value in private_values:
        assert value not in rendered


def _evidence(monkeypatch, *, marker: str = "1"):
    module, plan, runtime, image_id, installation = _plan(monkeypatch, marker=marker)
    receipt = _receipt(module, plan)
    evidence = module._seal_laya_runtime_execution_evidence(plan, receipt)
    return module, plan, runtime, evidence, image_id, installation


def test_private_authority_api_is_explicit_but_not_public(monkeypatch):
    module, plan, *_ = _plan(monkeypatch)

    assert "_issue_laya_runtime_execution_receipt" not in module.__all__
    assert "_seal_laya_runtime_execution_evidence" not in module.__all__
    assert tuple(inspect.signature(module._issue_laya_runtime_execution_receipt).parameters) == (
        "plan",
        "canonical_observation",
    )
    assert tuple(inspect.signature(module._seal_laya_runtime_execution_evidence).parameters) == (
        "plan",
        "receipt",
    )
    assert _receipt(module, plan) is not None


def test_receipt_issuer_accepts_only_exact_canonical_bytes(monkeypatch):
    module, plan, _runtime, image_id, installation = _plan(monkeypatch, marker="2")
    invalid_values = (
        bytearray(_canonical_observation()),
        hashlib.sha256(_canonical_observation()).hexdigest(),
        {"digest": hashlib.sha256(_canonical_observation()).hexdigest()},
        _canonical_observation() + b"\n",
        b" " + _canonical_observation(),
    )

    for invalid in invalid_values:
        with pytest.raises((TypeError, ValueError)) as captured:
            module._issue_laya_runtime_execution_receipt(plan, invalid)
        _private_failure(captured.value, image_id, installation)


def test_receipt_repr_does_not_expose_observation_or_runtime_bindings(monkeypatch):
    module, plan, _runtime, image_id, installation = _plan(monkeypatch, marker="3")
    canonical = _canonical_observation()
    receipt = module._issue_laya_runtime_execution_receipt(plan, canonical)

    rendered = repr(receipt)
    assert canonical.decode("ascii") not in rendered
    assert hashlib.sha256(canonical).hexdigest() not in rendered
    assert image_id not in rendered
    assert installation not in rendered


def test_receipt_clone_and_replace_never_gain_authority(monkeypatch):
    module, plan, _runtime, image_id, installation = _plan(monkeypatch, marker="4")
    issued = _receipt(module, plan)

    with pytest.raises((TypeError, ValueError)) as captured:
        replace(issued)
    canonical = _canonical_observation()
    _external_replace_failure(
        captured.value,
        image_id,
        installation,
        canonical.decode("ascii"),
        hashlib.sha256(canonical).hexdigest(),
    )

    unregistered = replace(issued, _factory_token=module._RECEIPT_TOKEN)
    for invalid in (_clone_exact(issued), unregistered):
        with pytest.raises((TypeError, ValueError)) as captured:
            module._seal_laya_runtime_execution_evidence(plan, invalid)
        _private_failure(captured.value, image_id, installation)


def test_receipt_is_bound_to_one_exact_plan(monkeypatch):
    module, plan, _runtime, image_id, installation = _plan(monkeypatch, marker="5")
    _module2, other_plan, *_ = _plan(monkeypatch, marker="6")
    receipt = _receipt(module, plan)

    with pytest.raises((TypeError, ValueError)) as captured:
        module._seal_laya_runtime_execution_evidence(other_plan, receipt)
    _private_failure(captured.value, image_id, installation)


def test_receipt_is_consumed_exactly_once(monkeypatch):
    module, plan, _runtime, _image_id, _installation = _plan(monkeypatch, marker="7")
    receipt = _receipt(module, plan)
    first = module._seal_laya_runtime_execution_evidence(plan, receipt)

    assert module._require_issued_evidence(first) is first
    with pytest.raises((TypeError, ValueError)):
        module._seal_laya_runtime_execution_evidence(plan, receipt)


def test_revoked_parent_between_receipt_and_seal_prevents_issuance(monkeypatch):
    module, plan, runtime, image_id, installation = _plan(monkeypatch, marker="8")
    from human_feedback import runtime_materialization

    receipt = _receipt(module, plan)
    runtime_materialization._revoke_evidence(runtime)

    with pytest.raises((TypeError, ValueError)) as captured:
        module._seal_laya_runtime_execution_evidence(plan, receipt)
    _private_failure(captured.value, image_id, installation)


def test_deep_runtime_mutation_after_receipt_prevents_issuance(monkeypatch):
    module, plan, runtime, image_id, installation = _plan(monkeypatch, marker="7")
    receipt = _receipt(module, plan)
    original = runtime._installation_sha256
    object.__setattr__(runtime, "_installation_sha256", "a" * 64)
    try:
        with pytest.raises((TypeError, ValueError)) as captured:
            module._seal_laya_runtime_execution_evidence(plan, receipt)
        _private_failure(captured.value, image_id, installation, "a" * 64)
    finally:
        object.__setattr__(runtime, "_installation_sha256", original)


def test_every_exact_plan_binding_is_rechecked_after_receipt(monkeypatch):
    module, plan, _runtime, image_id, installation = _plan(monkeypatch, marker="a")
    corruptions = {
        "_runtime_evidence": object(),
        "_materialization_plan": object(),
        "_image_id": "sha256:" + "0" * 64,
        "_installation_sha256": "0" * 64,
        "_runtime_identity": object(),
        "execution_profile": "changed-profile",
    }
    for field, corrupted in corruptions.items():
        receipt = _receipt(module, plan)
        original = getattr(plan, field)
        object.__setattr__(plan, field, corrupted)
        try:
            with pytest.raises((TypeError, ValueError)) as captured:
                module._seal_laya_runtime_execution_evidence(plan, receipt)
            _private_failure(captured.value, image_id, installation)
        finally:
            object.__setattr__(plan, field, original)


def test_positive_evidence_requires_live_registered_receipt(monkeypatch):
    module, plan, _runtime, evidence, image_id, installation = _evidence(monkeypatch, marker="c")
    direct = module.LayaRuntimeExecutionEvidence(
        schema_version="laya-runtime-execution-evidence-v1",
        _plan=plan,
        _factory_token=module._EVIDENCE_TOKEN,
    )

    assert module._require_issued_evidence(evidence) is evidence
    with pytest.raises((TypeError, ValueError)) as captured:
        replace(evidence)
    _external_replace_failure(
        captured.value,
        image_id,
        installation,
        _canonical_observation().decode("ascii"),
    )

    unregistered = replace(evidence, _factory_token=module._EVIDENCE_TOKEN)
    for invalid in (direct, _clone_exact(evidence), unregistered):
        with pytest.raises((TypeError, ValueError)) as captured:
            module._require_issued_evidence(invalid)
        _private_failure(captured.value, image_id, installation)


def test_evidence_registry_rejects_plan_rebinding(monkeypatch):
    module, _plan1, _runtime1, evidence, image_id, installation = _evidence(monkeypatch, marker="d")
    _module2, other_plan, *_ = _plan(monkeypatch, marker="e")
    original = evidence._plan
    object.__setattr__(evidence, "_plan", other_plan)
    try:
        with pytest.raises((TypeError, ValueError)) as captured:
            module._require_issued_evidence(evidence)
        _private_failure(captured.value, image_id, installation)
    finally:
        object.__setattr__(evidence, "_plan", original)


def test_summary_is_exact_canonical_claims_only_and_privacy_safe(monkeypatch):
    module, _plan1, _runtime1, evidence, image_id, installation = _evidence(monkeypatch, marker="e")

    rendered = module.canonical_laya_runtime_execution_summary_bytes(evidence)
    expected = {
        "schema_version": "laya-runtime-execution-evidence-v1",
        "execution_profile": module.EXECUTION_PROFILE,
        **EXPECTED_EXECUTION_CLAIMS,
    }
    assert rendered == json.dumps(
        expected,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert set(json.loads(rendered)) == {"schema_version", "execution_profile"} | set(
        EXPECTED_EXECUTION_CLAIMS
    )
    for forbidden in (
        image_id,
        installation,
        "predictions",
        "probabilities",
        "choice",
        "confidence",
        "answer_confidence",
        "digest",
        "sha256",
    ):
        assert forbidden not in rendered.decode("utf-8")


def test_revocation_is_idempotent_and_removes_summary_authority(monkeypatch):
    module, _plan1, _runtime1, evidence, image_id, installation = _evidence(monkeypatch, marker="1")

    module._revoke_evidence(evidence)
    module._revoke_evidence(evidence)
    with pytest.raises((TypeError, ValueError)) as captured:
        module.canonical_laya_runtime_execution_summary_bytes(evidence)
    _private_failure(captured.value, image_id, installation)


def test_parent_revocation_invalidates_already_issued_execution_evidence(monkeypatch):
    module, _plan1, runtime, evidence, image_id, installation = _evidence(monkeypatch, marker="2")
    from human_feedback import runtime_materialization

    runtime_materialization._revoke_evidence(runtime)
    with pytest.raises((TypeError, ValueError)) as captured:
        module._require_issued_evidence(evidence)
    _private_failure(captured.value, image_id, installation)


def test_all_authority_failures_drop_private_exception_context(monkeypatch):
    module, plan, _runtime, image_id, installation = _plan(monkeypatch, marker="3")
    invalid = b'{"private_canary":"DO_NOT_DISCLOSE_EXECUTION_AUTHORITY"'

    with pytest.raises((TypeError, ValueError)) as captured:
        module._issue_laya_runtime_execution_receipt(plan, invalid)
    error = captured.value
    _private_failure(captured.value, image_id, installation)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    assert "DO_NOT_DISCLOSE_EXECUTION_AUTHORITY" not in repr((error.args, str(error), repr(error)))
