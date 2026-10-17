import ast
import importlib
import inspect
import json
from dataclasses import fields, replace
from types import MappingProxyType

import pytest

EXPECTED_MATERIALIZATION_CLAIMS = {
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
    "runtime_materialized": False,
    "executor_available": False,
    "inference_executed": False,
}


def _clone_exact(value, **changes):
    clone = object.__new__(type(value))
    for item in fields(value):
        object.__setattr__(clone, item.name, changes.get(item.name, getattr(value, item.name)))
    return clone


def _paired_authorities(monkeypatch):
    from human_feedback import runtime_oci_rootfs, runtime_oci_tar, runtime_supply_convergence
    from tests.laya_runtime_supply_convergence_fixtures import issue_laya_supply_chain

    chain = issue_laya_supply_chain(monkeypatch)
    supply = runtime_supply_convergence.verify_laya_runtime_supply_convergence(
        chain.layer_evidence,
        chain.provenance_evidence,
        chain.base_ancestry_evidence,
    )
    tar_plan = runtime_oci_tar.prepare_laya_oci_tar_semantics_plan(chain.layer_evidence)
    receipts = tuple(
        runtime_oci_tar.VerifiedLayaOciTarLayer(
            plan=tar_plan,
            layer_receipt=historical,
            layer_position=position,
            entries=(),
            payload_size_bytes=0,
            tar_size_bytes=historical.uncompressed_size_bytes,
            _factory_token=runtime_oci_tar._FACTORY_TOKEN,
        )
        for position, historical in enumerate(chain.layer_evidence.receipts)
    )
    tar_evidence = runtime_oci_tar.LayaRuntimeOciTarSemanticsEvidence(
        schema_version="laya-runtime-oci-tar-semantics-evidence-v1",
        plan=tar_plan,
        runtime_identity=chain.layer_evidence.runtime_identity,
        receipts=receipts,
        _factory_token=runtime_oci_tar._FACTORY_TOKEN,
    )
    rootfs = runtime_oci_rootfs.compose_laya_oci_rootfs(
        runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar_evidence)
    )
    return chain, rootfs, supply


def test_rootfs_materialization_pure_contract_is_explicit_and_io_free():
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")

    assert module.__all__ == (
        "LayaRuntimeRootfsMaterializationPlan",
        "LayaRuntimeRootfsMaterializationEvidence",
        "prepare_laya_runtime_rootfs_materialization_plan",
        "canonical_laya_runtime_rootfs_materialization_summary_bytes",
    )
    tree = ast.parse(inspect.getsource(module))
    forbidden_imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
        if alias.name.split(".")[0]
        in {"os", "pathlib", "shutil", "subprocess", "tarfile", "tempfile"}
    }
    assert forbidden_imports == set()


def test_rootfs_materialization_claim_profile_is_closed_and_conservative():
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")

    assert module.MATERIALIZATION_PROFILE == "nonroot-disposable-v1"
    assert module.MATERIALIZATION_CLAIMS == EXPECTED_MATERIALIZATION_CLAIMS
    assert len(module.MATERIALIZATION_CLAIMS) == 35


def test_materialization_claims_are_public_but_immutable():
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")

    assert isinstance(module.MATERIALIZATION_CLAIMS, MappingProxyType)
    with pytest.raises(TypeError):
        module.MATERIALIZATION_CLAIMS["runtime_materialized"] = True
    assert module.MATERIALIZATION_CLAIMS["runtime_materialized"] is False


def test_plan_accepts_only_exact_paired_pr33_and_issued_pr37(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")
    _chain, rootfs, supply = _paired_authorities(monkeypatch)
    plan = module.prepare_laya_runtime_rootfs_materialization_plan(rootfs, supply)

    assert plan._rootfs_evidence is rootfs
    assert plan._supply_evidence is supply
    assert plan._runtime_identity is rootfs.runtime_identity

    other_chain, other_rootfs, other_supply = _paired_authorities(monkeypatch)
    assert other_chain.layer_evidence is not _chain.layer_evidence
    invalid_pairs = (
        (_clone_exact(rootfs), supply),
        (rootfs, _clone_exact(supply)),
        (rootfs, other_supply),
        (other_rootfs, supply),
    )
    for invalid_rootfs, invalid_supply in invalid_pairs:
        with pytest.raises((TypeError, ValueError)) as captured:
            module.prepare_laya_runtime_rootfs_materialization_plan(invalid_rootfs, invalid_supply)
        assert captured.value.__cause__ is None
        assert captured.value.__context__ is None
        assert captured.value.__suppress_context__ is True


def test_plan_rejects_replace_proxy_and_deep_predecessor_mutation(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")
    _chain, rootfs, supply = _paired_authorities(monkeypatch)
    plan = module.prepare_laya_runtime_rootfs_materialization_plan(rootfs, supply)

    with pytest.raises((TypeError, ValueError)):
        replace(plan, _rootfs_evidence=object())
    with pytest.raises((TypeError, ValueError)):
        module.prepare_laya_runtime_rootfs_materialization_plan(object(), supply)

    original = rootfs.rootfs_manifest_sha256
    object.__setattr__(rootfs, "rootfs_manifest_sha256", "f" * 64)
    try:
        with pytest.raises((TypeError, ValueError)) as captured:
            module.prepare_laya_runtime_rootfs_materialization_plan(rootfs, supply)
        assert original not in str(captured.value)
        assert captured.value.__suppress_context__ is True
    finally:
        object.__setattr__(rootfs, "rootfs_manifest_sha256", original)


def test_evidence_cannot_be_directly_constructed_or_replaced(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")
    _chain, rootfs, supply = _paired_authorities(monkeypatch)
    plan = module.prepare_laya_runtime_rootfs_materialization_plan(rootfs, supply)

    with pytest.raises((TypeError, ValueError)):
        module.LayaRuntimeRootfsMaterializationEvidence(
            schema_version="laya-runtime-rootfs-materialization-evidence-v1",
            _plan=plan,
            _content_manifest_sha256="a" * 64,
            _factory_token=module._FACTORY_TOKEN,
        )

    forged = object.__new__(module.LayaRuntimeRootfsMaterializationEvidence)
    for item in fields(module.LayaRuntimeRootfsMaterializationEvidence):
        object.__setattr__(
            forged,
            item.name,
            (
                plan
                if item.name == "_plan"
                else (
                    "a" * 64
                    if item.name == "_content_manifest_sha256"
                    else getattr(item, "default", None)
                )
            ),
        )
    assert "a" * 64 not in repr(forged)
    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_rootfs_materialization_summary_bytes(forged)


def test_private_sealer_issues_summary_authority_without_leaking_commitment(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")
    _chain, rootfs, supply = _paired_authorities(monkeypatch)
    plan = module.prepare_laya_runtime_rootfs_materialization_plan(rootfs, supply)
    commitment = "c" * 64

    evidence = module._seal_laya_runtime_rootfs_materialization_evidence(plan, commitment)
    summary = module.canonical_laya_runtime_rootfs_materialization_summary_bytes(evidence)
    payload = json.loads(summary)

    assert evidence._plan is plan
    assert evidence._content_manifest_sha256 == commitment
    assert commitment not in repr(evidence)
    assert commitment.encode() not in summary
    assert "path" not in payload
    assert "digest" not in payload
    assert payload == {
        "schema_version": "laya-runtime-rootfs-materialization-evidence-v1",
        "materialization_profile": "nonroot-disposable-v1",
        **EXPECTED_MATERIALIZATION_CLAIMS,
    }


def test_only_exact_issued_evidence_has_summary_authority(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")
    _chain, rootfs, supply = _paired_authorities(monkeypatch)
    plan = module.prepare_laya_runtime_rootfs_materialization_plan(rootfs, supply)
    evidence = module._seal_laya_runtime_rootfs_materialization_evidence(plan, "d" * 64)
    clone = _clone_exact(evidence)

    for invalid in (clone, replace):
        if invalid is replace:
            with pytest.raises((TypeError, ValueError)):
                replace(evidence, _content_manifest_sha256="d" * 64)
        else:
            with pytest.raises((TypeError, ValueError)):
                module.canonical_laya_runtime_rootfs_materialization_summary_bytes(invalid)

    direct = module.LayaRuntimeRootfsMaterializationEvidence(
        schema_version="laya-runtime-rootfs-materialization-evidence-v1",
        _plan=plan,
        _content_manifest_sha256="d" * 64,
        _factory_token=module._EVIDENCE_TOKEN,
    )
    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_rootfs_materialization_summary_bytes(direct)


def test_summary_rejects_postseal_commitment_plan_and_predecessor_mutation(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")

    def issue():
        _chain, rootfs, supply = _paired_authorities(monkeypatch)
        plan = module.prepare_laya_runtime_rootfs_materialization_plan(rootfs, supply)
        evidence = module._seal_laya_runtime_rootfs_materialization_evidence(plan, "e" * 64)
        return rootfs, plan, evidence

    rootfs, _plan, evidence = issue()
    object.__setattr__(evidence, "_content_manifest_sha256", "f" * 64)
    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_rootfs_materialization_summary_bytes(evidence)

    _rootfs, plan, evidence = issue()
    object.__setattr__(plan, "runtime_materialized", True)
    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_rootfs_materialization_summary_bytes(evidence)

    rootfs, _plan, evidence = issue()
    object.__setattr__(rootfs, "rootfs_manifest_sha256", "f" * 64)
    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_rootfs_materialization_summary_bytes(evidence)


def test_dispose_revocation_removes_summary_authority(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")
    _chain, rootfs, supply = _paired_authorities(monkeypatch)
    plan = module.prepare_laya_runtime_rootfs_materialization_plan(rootfs, supply)
    evidence = module._seal_laya_runtime_rootfs_materialization_evidence(plan, "a" * 64)
    module.canonical_laya_runtime_rootfs_materialization_summary_bytes(evidence)

    assert module._revoke_evidence(evidence) is None
    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_rootfs_materialization_summary_bytes(evidence)


def test_registry_rejects_rebinding_issued_plan_to_another_valid_pair(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_rootfs_materialization")
    _left_chain, left_rootfs, left_supply = _paired_authorities(monkeypatch)
    plan = module.prepare_laya_runtime_rootfs_materialization_plan(left_rootfs, left_supply)
    evidence = module._seal_laya_runtime_rootfs_materialization_evidence(plan, "b" * 64)
    _right_chain, right_rootfs, right_supply = _paired_authorities(monkeypatch)

    object.__setattr__(plan, "_rootfs_evidence", right_rootfs)
    object.__setattr__(plan, "_supply_evidence", right_supply)
    object.__setattr__(plan, "_runtime_identity", right_rootfs.runtime_identity)

    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_rootfs_materialization_summary_bytes(evidence)
