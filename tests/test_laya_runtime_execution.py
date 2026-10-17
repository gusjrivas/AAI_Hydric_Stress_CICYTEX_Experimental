import ast
import importlib
import inspect
from dataclasses import fields, replace
from types import MappingProxyType

import pytest

from tests.test_laya_runtime_materialization import (
    _clone_exact,
    _issued_runtime_inputs,
)

EXPECTED_EXECUTION_CLAIMS = {
    "artifact_integrity_verified": True,
    "oci_manifest_semantics_verified": True,
    "oci_layout_controls_bytes_verified": True,
    "oci_blob_inventory_verified": True,
    "oci_same_root_capture_verified": True,
    "oci_manifest_blob_bytes_verified": True,
    "oci_config_blob_bytes_verified": True,
    "oci_layer_blobs_bytes_verified": True,
    "oci_bytes_verified": True,
    "oci_config_semantics_verified": True,
    "oci_layer_diff_ids_verified": True,
    "base_ancestry_verified": True,
    "runtime_config_semantics_verified": True,
    "checkpoint_manifest_semantics_verified": True,
    "checkpoint_bytes_verified": True,
    "provenance_objects_verified": True,
    "source_git_content_verified": True,
    "checkpoint_git_content_verified": True,
    "source_license_declaration_observed": True,
    "checkpoint_license_declaration_observed": True,
    "runtime_supply_content_convergence_verified": True,
    "tar_semantics_verified": True,
    "oci_rootfs_verified": True,
    "rootfs_materialized": True,
    "lock_verified": False,
    "sbom_verified": False,
    "lock_sbom_consistent": False,
    "origin_verified": False,
    "license_verified": False,
    "runtime_build_recipe_verified": False,
    "build_process_attested": False,
    "reproducible_build_verified": False,
    "runtime_materialized": True,
    "executor_available": True,
    "inference_executed": True,
}


def _private_failure(error: BaseException, *private_values: str) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    for value in private_values:
        assert value not in str(error)


def _issued_runtime(monkeypatch, *, marker: str = "1"):
    from human_feedback import runtime_materialization

    chain, supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch, commitment=marker * 64)
    materialization_plan = runtime_materialization.prepare_laya_runtime_materialization_plan(
        rootfs, checkpoint
    )
    image_id = "sha256:" + marker * 64
    installation_sha256 = chr(ord(marker) + 1) * 64
    runtime = runtime_materialization._seal_laya_runtime_materialization_evidence(
        materialization_plan,
        image_id,
        installation_sha256,
    )
    return chain, supply, runtime, image_id, installation_sha256


def test_runtime_execution_public_surface_and_pure_profile_are_closed():
    module = importlib.import_module("human_feedback.runtime_execution")

    assert module.__all__ == (
        "LayaRuntimeExecutionPlan",
        "LayaRuntimeExecutionEvidence",
        "prepare_laya_runtime_execution_plan",
        "canonical_laya_runtime_execution_summary_bytes",
    )
    assert module.EXECUTION_PROFILE == "docker-local-offline-cpu-synthetic-v1"
    tree = ast.parse(inspect.getsource(module))
    forbidden = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
        if alias.name.split(".")[0]
        in {
            "docker",
            "os",
            "pathlib",
            "shutil",
            "socket",
            "subprocess",
            "tempfile",
        }
    }
    assert forbidden == set()


def test_execution_claim_matrix_is_explicit_conservative_and_immutable():
    module = importlib.import_module("human_feedback.runtime_execution")
    from human_feedback import runtime_materialization

    claims = module.EXECUTION_CLAIMS
    assert isinstance(claims, MappingProxyType)
    assert claims == EXPECTED_EXECUTION_CLAIMS
    assert len(claims) == 35
    predecessor = dict(runtime_materialization.MATERIALIZATION_CLAIMS)
    changed = {name for name in claims if claims[name] is not predecessor[name]}
    assert changed == {"executor_available", "inference_executed"}
    with pytest.raises(TypeError):
        claims["executor_available"] = False


def test_plan_binds_one_exact_live_runtime_without_elevating_execution(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_execution")
    _chain, _supply, runtime, image_id, installation_sha256 = _issued_runtime(monkeypatch)

    plan = module.prepare_laya_runtime_execution_plan(runtime)

    assert plan._runtime_evidence is runtime
    assert plan._materialization_plan is runtime._plan
    assert plan._image_id is runtime._image_id
    assert plan._image_id == image_id
    assert plan._installation_sha256 is runtime._installation_sha256
    assert plan._installation_sha256 == installation_sha256
    assert plan._runtime_identity is runtime._plan._runtime_identity
    assert plan.execution_profile == "docker-local-offline-cpu-synthetic-v1"
    assert plan.executor_available is False
    assert plan.inference_executed is False


def test_plan_rejects_clone_proxy_replace_and_revoked_runtime_privately(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_execution")
    from human_feedback import runtime_materialization

    _chain, _supply, runtime, image_id, installation_sha256 = _issued_runtime(
        monkeypatch, marker="3"
    )
    for invalid in (_clone_exact(runtime), object()):
        with pytest.raises((TypeError, ValueError)) as captured:
            module.prepare_laya_runtime_execution_plan(invalid)
        _private_failure(captured.value, image_id, installation_sha256)

    plan = module.prepare_laya_runtime_execution_plan(runtime)
    with pytest.raises((TypeError, ValueError)):
        replace(plan, _runtime_evidence=_clone_exact(runtime))

    runtime_materialization._revoke_evidence(runtime)
    with pytest.raises((TypeError, ValueError)) as captured:
        module.prepare_laya_runtime_execution_plan(runtime)
    _private_failure(captured.value, image_id, installation_sha256)


def test_plan_rejects_rebinding_and_deep_parent_mutation_privately(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_execution")

    _chain, _supply, runtime, image_id, installation_sha256 = _issued_runtime(
        monkeypatch, marker="5"
    )
    _other_chain, _other_supply, other_runtime, _, _ = _issued_runtime(monkeypatch, marker="7")
    plan = module.prepare_laya_runtime_execution_plan(runtime)

    object.__setattr__(plan, "_runtime_evidence", other_runtime)
    with pytest.raises((TypeError, ValueError)) as captured:
        plan.__post_init__(module._FACTORY_TOKEN)
    _private_failure(captured.value, image_id, installation_sha256)

    original_image = runtime._image_id
    object.__setattr__(runtime, "_image_id", "sha256:" + "9" * 64)
    try:
        with pytest.raises((TypeError, ValueError)) as captured:
            module.prepare_laya_runtime_execution_plan(runtime)
        _private_failure(captured.value, original_image, "sha256:" + "9" * 64)
    finally:
        object.__setattr__(runtime, "_image_id", original_image)


def test_direct_evidence_scaffold_remains_unissued_private_and_outside_public_api(
    monkeypatch,
):
    module = importlib.import_module("human_feedback.runtime_execution")

    _chain, _supply, runtime, image_id, installation_sha256 = _issued_runtime(
        monkeypatch, marker="a"
    )
    plan = module.prepare_laya_runtime_execution_plan(runtime)

    assert "_seal_laya_runtime_execution_evidence" not in module.__all__
    assert "_issue_laya_runtime_execution_receipt" not in module.__all__
    direct = module.LayaRuntimeExecutionEvidence(
        schema_version="laya-runtime-execution-evidence-v1",
        _plan=plan,
        _factory_token=module._EVIDENCE_TOKEN,
    )
    assert image_id not in repr(direct)
    assert installation_sha256 not in repr(direct)
    with pytest.raises((TypeError, ValueError)) as captured:
        module.canonical_laya_runtime_execution_summary_bytes(direct)
    _private_failure(captured.value, image_id, installation_sha256)
    with pytest.raises((TypeError, ValueError)):
        replace(direct)


def test_evidence_scaffold_declares_only_the_future_two_claim_elevations():
    module = importlib.import_module("human_feedback.runtime_execution")

    evidence_fields = {item.name: item for item in fields(module.LayaRuntimeExecutionEvidence)}
    for claim, expected in EXPECTED_EXECUTION_CLAIMS.items():
        assert claim in evidence_fields
        assert evidence_fields[claim].default is expected
