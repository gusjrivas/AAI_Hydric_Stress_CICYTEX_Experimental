from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path

import pytest

from tests.laya_runtime_supply_convergence_fixtures import issue_laya_supply_chain

MODULE = "human_feedback.runtime_supply_convergence"


def _fresh_module():
    sys.modules.pop(MODULE, None)
    return importlib.import_module(MODULE)


def _clone_all_slots(value):
    clone = object.__new__(type(value))
    for owner in type(value).__mro__:
        for name in getattr(owner, "__slots__", ()):
            if name not in {"__dict__", "__weakref__"} and hasattr(value, name):
                object.__setattr__(clone, name, getattr(value, name))
    return clone


@pytest.fixture
def issued(monkeypatch):
    return issue_laya_supply_chain(monkeypatch)


def test_fixture_is_genuinely_issued_reconstructible_and_independent(issued):
    """This setup test must stay GREEN before the PR37 module exists."""

    from human_feedback import (
        runtime_base_ancestry,
        runtime_bundle,
        runtime_oci_layers,
        runtime_provenance,
    )

    assert type(issued.layer_evidence) is runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence
    assert type(issued.provenance_evidence) is runtime_provenance.LayaRuntimeProvenanceEvidence
    assert (
        type(issued.base_ancestry_evidence) is runtime_base_ancestry.LayaRuntimeBaseAncestryEvidence
    )
    assert issued.base_ancestry_evidence.layer_evidence is issued.layer_evidence
    runtime_oci_layers.canonical_laya_runtime_oci_layer_diff_ids_summary_bytes(
        issued.layer_evidence
    )
    runtime_provenance.canonical_laya_runtime_provenance_summary_bytes(issued.provenance_evidence)
    runtime_base_ancestry.canonical_laya_runtime_base_ancestry_summary_bytes(
        issued.base_ancestry_evidence
    )

    left = issued.layer_evidence.layout_evidence.plan.oci_evidence.snapshot
    right = issued.provenance_evidence.checkpoint_evidence.deployment_evidence.snapshot
    assert left is issued.snapshot
    assert right is issued.provenance_snapshot
    assert left is not right
    assert left == right
    rebuilt = []
    for snapshot in (left, right):
        payloads = {artifact.spec.path: artifact.content for artifact in snapshot.artifacts}
        rebuilt.append(
            runtime_bundle.verify_laya_runtime_artifact_bytes(snapshot.manifest, payloads)
        )
    assert rebuilt[0] == left
    assert rebuilt[1] == right
    assert rebuilt[0] == rebuilt[1]


def test_public_surface_and_signatures_are_exactly_closed():
    module = _fresh_module()
    public = {
        name
        for name in vars(module)
        if not name.startswith("_") and getattr(vars(module)[name], "__module__", MODULE) == MODULE
    }
    assert public == {
        "LayaRuntimeSupplyConvergenceEvidence",
        "verify_laya_runtime_supply_convergence",
        "canonical_laya_runtime_supply_convergence_summary_bytes",
    }
    assert tuple(inspect.signature(module.verify_laya_runtime_supply_convergence).parameters) == (
        "layer_evidence",
        "provenance_evidence",
        "base_ancestry_evidence",
    )
    assert tuple(
        inspect.signature(module.canonical_laya_runtime_supply_convergence_summary_bytes).parameters
    ) == ("evidence",)


def test_verify_accepts_exact_issued_chain_and_binds_pr36_to_the_same_pr22(issued):
    module = _fresh_module()
    evidence = module.verify_laya_runtime_supply_convergence(
        issued.layer_evidence,
        issued.provenance_evidence,
        issued.base_ancestry_evidence,
    )
    assert type(evidence) is module.LayaRuntimeSupplyConvergenceEvidence
    assert evidence.runtime_supply_content_convergence_verified is True
    assert issued.base_ancestry_evidence.layer_evidence is issued.layer_evidence


def test_verify_source_calls_exact_canonicals_and_public_snapshot_reconstructor(issued):
    module = _fresh_module()
    evidence = module.verify_laya_runtime_supply_convergence(
        issued.layer_evidence,
        issued.provenance_evidence,
        issued.base_ancestry_evidence,
    )
    assert evidence.runtime_supply_content_convergence_verified is True

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } | {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {
        "canonical_laya_runtime_oci_layer_diff_ids_summary_bytes",
        "canonical_laya_runtime_provenance_summary_bytes",
        "canonical_laya_runtime_base_ancestry_summary_bytes",
        "verify_laya_runtime_artifact_bytes",
    } <= called_names


def test_exact_existing_cardinalities_are_preserved(issued):
    layer = issued.layer_evidence
    provenance = issued.provenance_evidence
    base = issued.base_ancestry_evidence
    left = layer.layout_evidence.plan.oci_evidence.snapshot
    right = provenance.checkpoint_evidence.deployment_evidence.snapshot
    assert len((layer, provenance, base)) == 3
    assert len(left.artifacts) == len(right.artifacts) == 5
    assert len(provenance.checkpoint_evidence.plan.files) == 5
    assert len(layer.plan.layer_blobs) == len(layer.plan.declared_diff_ids) == 10
    assert len(provenance.plan.objects) == len(provenance.receipts) == 16
    assert len(base.plan.compressed_layer_prefix) == len(base.plan.diff_id_prefix) == 4


def test_equivalent_independently_issued_pr35_snapshot_is_accepted(monkeypatch):
    first = issue_laya_supply_chain(monkeypatch)
    second = issue_laya_supply_chain(monkeypatch)
    assert first.snapshot is not second.provenance_snapshot
    assert first.snapshot == second.provenance_snapshot
    module = _fresh_module()
    evidence = module.verify_laya_runtime_supply_convergence(
        first.layer_evidence,
        second.provenance_evidence,
        first.base_ancestry_evidence,
    )
    assert evidence.runtime_supply_content_convergence_verified is True


def test_mixed_equivalent_pr22_and_pr36_graphs_fail_by_identity(monkeypatch):
    first = issue_laya_supply_chain(monkeypatch)
    second = issue_laya_supply_chain(monkeypatch)
    module = _fresh_module()
    with pytest.raises((TypeError, ValueError), match="evidence|identity|binding|valid"):
        module.verify_laya_runtime_supply_convergence(
            first.layer_evidence,
            first.provenance_evidence,
            second.base_ancestry_evidence,
        )


@pytest.mark.parametrize("position", [0, 1, 2])
def test_cloned_or_non_exact_predecessor_is_rejected(issued, position):
    module = _fresh_module()
    values = [
        issued.layer_evidence,
        issued.provenance_evidence,
        issued.base_ancestry_evidence,
    ]
    values[position] = _clone_all_slots(values[position])
    with pytest.raises((TypeError, ValueError), match="evidence|issued|seal|valid|binding"):
        module.verify_laya_runtime_supply_convergence(*values)


def test_independently_issued_valid_pr35_with_one_different_artifact_fails(monkeypatch):
    issued = issue_laya_supply_chain(monkeypatch)
    alternate = issue_laya_supply_chain(
        monkeypatch,
        artifact_overrides={"locks/uv.lock": b"independently-issued-alternate-dependency-lock\n"},
    )
    left = issued.snapshot
    right = alternate.provenance_snapshot
    assert left is not right
    assert left != right
    differences = tuple(
        (left_item, right_item)
        for left_item, right_item in zip(left.artifacts, right.artifacts)
        if left_item != right_item
    )
    assert len(differences) == 1
    assert differences[0][0].spec.kind == "dependency_lock"

    from human_feedback import runtime_provenance

    runtime_provenance.canonical_laya_runtime_provenance_summary_bytes(
        alternate.provenance_evidence
    )
    module = _fresh_module()
    with pytest.raises((TypeError, ValueError), match="evidence|snapshot|content|valid"):
        module.verify_laya_runtime_supply_convergence(
            issued.layer_evidence,
            alternate.provenance_evidence,
            issued.base_ancestry_evidence,
        )
