import ast
import gc
import importlib
import inspect
import weakref
from dataclasses import fields, replace
from types import MappingProxyType

import pytest

from tests.test_laya_runtime_rootfs_materialization import (
    _clone_exact,
    _paired_authorities,
)

EXPECTED_RUNTIME_MATERIALIZATION_CLAIMS = {
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
    "executor_available": False,
    "inference_executed": False,
}


def _private_failure(error: BaseException, *private_values: str) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True
    for value in private_values:
        assert value not in str(error)


def _issued_runtime_inputs(monkeypatch, *, commitment="a" * 64):
    from human_feedback import runtime_rootfs_materialization

    chain, rootfs, supply = _paired_authorities(monkeypatch)
    rootfs_plan = runtime_rootfs_materialization.prepare_laya_runtime_rootfs_materialization_plan(
        rootfs, supply
    )
    issued_rootfs = (
        runtime_rootfs_materialization._seal_laya_runtime_rootfs_materialization_evidence(
            rootfs_plan, commitment
        )
    )
    checkpoint = supply._provenance_evidence.checkpoint_evidence
    return chain, supply, issued_rootfs, checkpoint


def test_runtime_materialization_public_surface_and_pure_profile_are_closed():
    module = importlib.import_module("human_feedback.runtime_materialization")

    assert module.__all__ == (
        "LayaRuntimeMaterializationPlan",
        "LayaRuntimeMaterializationEvidence",
        "prepare_laya_runtime_materialization_plan",
        "canonical_laya_runtime_materialization_summary_bytes",
    )
    assert module.MATERIALIZATION_PROFILE == "docker-local-offline-cpu-v1"
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
            "tarfile",
            "tempfile",
        }
    }
    assert forbidden == set()


def test_runtime_materialization_claim_matrix_is_explicit_conservative_and_immutable():
    module = importlib.import_module("human_feedback.runtime_materialization")
    from human_feedback import runtime_rootfs_materialization

    claims = module.MATERIALIZATION_CLAIMS
    assert isinstance(claims, MappingProxyType)
    assert claims == EXPECTED_RUNTIME_MATERIALIZATION_CLAIMS
    assert len(claims) == 35
    predecessor = dict(runtime_rootfs_materialization.MATERIALIZATION_CLAIMS)
    changed = {name for name in claims if claims[name] is not predecessor[name]}
    assert changed == {"runtime_materialized"}
    assert claims["executor_available"] is False
    assert claims["inference_executed"] is False
    with pytest.raises(TypeError):
        claims["executor_available"] = True


def test_plan_binds_live_issued_rootfs_and_exact_checkpoint_from_its_supply_graph(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")
    _chain, supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch)

    plan = module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)

    assert plan._rootfs_evidence is rootfs
    assert plan._checkpoint_evidence is checkpoint
    assert plan._supply_evidence is supply
    assert checkpoint is supply._provenance_evidence.checkpoint_evidence
    assert plan._runtime_identity is rootfs._plan._runtime_identity
    assert checkpoint.runtime_identity.schema_version == plan._runtime_identity.schema_version
    assert checkpoint.runtime_identity.sha256 == plan._runtime_identity.sha256
    assert plan.materialization_profile == "docker-local-offline-cpu-v1"
    assert plan.runtime_materialized is False
    assert plan.executor_available is False
    assert plan.inference_executed is False


def test_plan_rejects_clone_proxy_replace_and_mix_and_match_privately(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")
    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch, commitment="b" * 64)
    _other_chain, _other_supply, other_rootfs, other_checkpoint = _issued_runtime_inputs(
        monkeypatch, commitment="c" * 64
    )

    invalid = (
        (_clone_exact(rootfs), checkpoint),
        (rootfs, _clone_exact(checkpoint)),
        (rootfs, other_checkpoint),
        (other_rootfs, checkpoint),
        (object(), checkpoint),
        (rootfs, object()),
    )
    for candidate_rootfs, candidate_checkpoint in invalid:
        with pytest.raises((TypeError, ValueError)) as captured:
            module.prepare_laya_runtime_materialization_plan(candidate_rootfs, candidate_checkpoint)
        _private_failure(captured.value, "b" * 64, "c" * 64)

    plan = module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
    with pytest.raises((TypeError, ValueError)):
        replace(plan, _checkpoint_evidence=other_checkpoint)


def test_plan_rejects_revoked_rootfs_before_any_io(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")
    from human_feedback import runtime_rootfs_materialization

    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch, commitment="d" * 64)
    runtime_rootfs_materialization._revoke_evidence(rootfs)

    with pytest.raises((TypeError, ValueError)) as captured:
        module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
    _private_failure(captured.value, "d" * 64)


def test_plan_rejects_deep_checkpoint_and_rootfs_mutation_privately(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")

    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch, commitment="e" * 64)
    original_commitment = rootfs._content_manifest_sha256
    object.__setattr__(rootfs, "_content_manifest_sha256", "f" * 64)
    try:
        with pytest.raises((TypeError, ValueError)) as captured:
            module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
        _private_failure(captured.value, original_commitment, "f" * 64)
    finally:
        object.__setattr__(rootfs, "_content_manifest_sha256", original_commitment)

    descriptor = checkpoint.plan.files[0]
    original_digest = descriptor.sha256
    object.__setattr__(descriptor, "sha256", "9" * 64)
    try:
        with pytest.raises((TypeError, ValueError)) as captured:
            module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
        _private_failure(captured.value, original_digest, "9" * 64)
    finally:
        object.__setattr__(descriptor, "sha256", original_digest)


def test_evidence_scaffold_has_no_caller_sealer_or_direct_summary_authority(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")

    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch, commitment="1" * 64)
    plan = module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
    assert "_seal_laya_runtime_materialization_evidence" not in module.__all__

    with pytest.raises((TypeError, ValueError)):
        module.LayaRuntimeMaterializationEvidence(
            schema_version="laya-runtime-materialization-evidence-v1",
            _plan=plan,
            _image_id="sha256:" + "2" * 64,
            _installation_sha256="3" * 64,
            _factory_token=module._FACTORY_TOKEN,
        )

    direct = module.LayaRuntimeMaterializationEvidence(
        schema_version="laya-runtime-materialization-evidence-v1",
        _plan=plan,
        _image_id="sha256:" + "2" * 64,
        _installation_sha256="3" * 64,
        _factory_token=module._EVIDENCE_TOKEN,
    )
    assert "1" * 64 not in repr(direct)
    with pytest.raises((TypeError, ValueError)) as captured:
        module.canonical_laya_runtime_materialization_summary_bytes(direct)
    _private_failure(captured.value, "1" * 64)
    with pytest.raises((TypeError, ValueError)):
        replace(direct)


def test_evidence_scaffold_declares_the_full_claim_matrix():
    module = importlib.import_module("human_feedback.runtime_materialization")

    evidence_fields = {
        item.name: item for item in fields(module.LayaRuntimeMaterializationEvidence)
    }
    for claim, expected in EXPECTED_RUNTIME_MATERIALIZATION_CLAIMS.items():
        assert claim in evidence_fields
        assert evidence_fields[claim].default is expected


def test_private_sealer_issues_weak_bound_authority_without_leaking_ids(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")

    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch, commitment="4" * 64)
    plan = module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
    image_id = "sha256:" + "5" * 64
    installation_sha256 = "6" * 64

    evidence = module._seal_laya_runtime_materialization_evidence(
        plan, image_id, installation_sha256
    )
    summary = module.canonical_laya_runtime_materialization_summary_bytes(evidence)

    assert evidence._plan is plan
    assert evidence._image_id == image_id
    assert evidence._installation_sha256 == installation_sha256
    assert image_id.encode() not in summary
    assert installation_sha256.encode() not in summary
    assert image_id not in repr(evidence)
    assert installation_sha256 not in repr(evidence)
    assert b"path" not in summary
    assert b"nonce" not in summary
    assert b"image_id" not in summary


@pytest.mark.parametrize(
    ("image_id", "installation_sha256"),
    (
        ("5" * 64, "6" * 64),
        ("sha256:" + "5" * 63, "6" * 64),
        ("sha256:" + "G" * 64, "6" * 64),
        ("sha256:" + "0" * 64, "6" * 64),
        ("sha256:" + "5" * 64, "6" * 63),
        ("sha256:" + "5" * 64, "G" * 64),
        ("sha256:" + "5" * 64, "0" * 64),
    ),
)
def test_private_sealer_rejects_malformed_authority_commitments(
    monkeypatch, image_id, installation_sha256
):
    module = importlib.import_module("human_feedback.runtime_materialization")
    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch)
    plan = module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)

    with pytest.raises((TypeError, ValueError)) as captured:
        module._seal_laya_runtime_materialization_evidence(plan, image_id, installation_sha256)
    _private_failure(captured.value, str(image_id), str(installation_sha256))


def test_summary_rejects_clone_replace_private_rebinding_and_deep_mutation(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")
    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch)
    plan = module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
    evidence = module._seal_laya_runtime_materialization_evidence(
        plan, "sha256:" + "7" * 64, "8" * 64
    )

    invalid_values = (
        _clone_exact(evidence),
        _clone_exact(evidence, _image_id="sha256:" + "9" * 64),
        _clone_exact(evidence, _installation_sha256="a" * 64),
    )
    for invalid in invalid_values:
        with pytest.raises((TypeError, ValueError)):
            module.canonical_laya_runtime_materialization_summary_bytes(invalid)
    with pytest.raises((TypeError, ValueError)):
        replace(evidence, _image_id=evidence._image_id)

    original = checkpoint.plan.files[0].sha256
    object.__setattr__(checkpoint.plan.files[0], "sha256", "b" * 64)
    try:
        with pytest.raises((TypeError, ValueError)):
            module.canonical_laya_runtime_materialization_summary_bytes(evidence)
    finally:
        object.__setattr__(checkpoint.plan.files[0], "sha256", original)

    _other_chain, other_supply, other_rootfs, other_checkpoint = _issued_runtime_inputs(
        monkeypatch, commitment="9" * 64
    )
    object.__setattr__(plan, "_rootfs_evidence", other_rootfs)
    object.__setattr__(plan, "_checkpoint_evidence", other_checkpoint)
    object.__setattr__(plan, "_supply_evidence", other_supply)
    object.__setattr__(plan, "_runtime_identity", other_rootfs._plan._runtime_identity)
    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_materialization_summary_bytes(evidence)


def test_revocation_is_idempotent_and_removes_summary_authority(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")
    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch)
    plan = module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
    evidence = module._seal_laya_runtime_materialization_evidence(
        plan, "sha256:" + "c" * 64, "d" * 64
    )
    module.canonical_laya_runtime_materialization_summary_bytes(evidence)

    assert module._revoke_evidence(evidence) is None
    assert module._revoke_evidence(evidence) is None
    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_materialization_summary_bytes(evidence)
    with pytest.raises((TypeError, ValueError)):
        module._revoke_evidence(_clone_exact(evidence))


def test_revocation_does_not_revalidate_a_parent_already_disposed(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")
    from human_feedback import runtime_rootfs_materialization

    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch)
    plan = module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
    evidence = module._seal_laya_runtime_materialization_evidence(
        plan, "sha256:" + "e" * 64, "f" * 64
    )
    runtime_rootfs_materialization._revoke_evidence(rootfs)

    with pytest.raises((TypeError, ValueError)):
        module.canonical_laya_runtime_materialization_summary_bytes(evidence)
    assert module._revoke_evidence(evidence) is None
    assert module._revoke_evidence(evidence) is None


def test_issuance_registry_is_weak_and_does_not_retain_expired_evidence(monkeypatch):
    module = importlib.import_module("human_feedback.runtime_materialization")
    _chain, _supply, rootfs, checkpoint = _issued_runtime_inputs(monkeypatch)
    plan = module.prepare_laya_runtime_materialization_plan(rootfs, checkpoint)
    evidence = module._seal_laya_runtime_materialization_evidence(
        plan, "sha256:" + "1" * 64, "2" * 64
    )
    identity = id(evidence)
    reference = weakref.ref(evidence)
    assert identity in module._ISSUED_EVIDENCE

    del evidence
    gc.collect()

    assert reference() is None
    assert identity not in module._ISSUED_EVIDENCE
