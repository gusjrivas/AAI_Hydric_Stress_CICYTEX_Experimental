import ast
import os
import traceback
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

PLAN_SCHEMA = "laya-oci-layer-diff-id-plan-v1"
REAL_LAYOUT_GATE_ENV = "LAYA_RUNTIME_OCI_LAYOUT_ROOT"
EXPECTED_LAYER_ROLES = tuple(f"layer-{index:02d}" for index in range(10))
FALSE_CLAIMS = (
    "oci_layer_diff_ids_verified",
    "oci_rootfs_verified",
    "origin_verified",
)


def _private_error(error: BaseException, *markers: str) -> None:
    rendered = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    for marker in markers:
        assert marker not in str(error)
        assert marker not in rendered
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True


def _forged_dataclass(value, **changes):
    forged = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            forged,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return forged


def test_layer_diff_id_plan_module_has_a_pure_minimal_public_surface():
    from human_feedback import runtime_oci_layers as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imports & {
        "gzip",
        "io",
        "os",
        "pathlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "zlib",
    }
    forbidden_calls = {
        "open",
        "read_bytes",
        "read_text",
        "write_bytes",
        "write_text",
        "system",
        "popen",
        "run",
        "__import__",
        "eval",
        "exec",
    }
    calls = {
        (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert calls.isdisjoint(forbidden_calls)
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    public_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    public_constants = {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
        if isinstance(target, ast.Name) and target.id.isupper() and not target.id.startswith("_")
    }
    assert public_functions == {"prepare_laya_oci_layer_diff_id_plan"}
    assert public_classes == {"LayaOciLayerDiffIdPlan"}
    assert public_constants == {"OCI_LAYER_DIFF_ID_PLAN_SCHEMA"}


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        SimpleNamespace(oci_config_semantics_verified=True),
        "private-config-evidence-proxy",
    ],
)
def test_layer_diff_id_plan_rejects_non_exact_config_evidence_privately(invalid):
    from human_feedback.runtime_oci_layers import prepare_laya_oci_layer_diff_id_plan

    with pytest.raises((TypeError, ValueError), match="config|evidence|exact|valid") as captured:
        prepare_laya_oci_layer_diff_id_plan(invalid)
    _private_error(captured.value, "private-config-evidence-proxy")


def test_no_product_module_imports_or_calls_layer_diff_id_plan():
    repository = Path(__file__).parents[1]
    owner = repository / "src" / "human_feedback" / "runtime_oci_layers.py"
    symbols = {
        "LayaOciLayerDiffIdPlan",
        "prepare_laya_oci_layer_diff_id_plan",
        "human_feedback.runtime_oci_layers",
    }
    offenders = []
    for relative_root in ("backend", "src", "scripts"):
        root = repository / relative_root
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if path == owner:
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            if any(
                (
                    isinstance(node, ast.Import)
                    and any(
                        alias.name == "human_feedback.runtime_oci_layers" for alias in node.names
                    )
                )
                or (
                    isinstance(node, ast.ImportFrom)
                    and (
                        node.module == "human_feedback.runtime_oci_layers"
                        or (
                            node.level > 0
                            and node.module in {None, "", "runtime_oci_layers"}
                            and any(
                                alias.name == "runtime_oci_layers" or alias.name in symbols
                                for alias in node.names
                            )
                        )
                    )
                )
                or (isinstance(node, ast.Name) and node.id in symbols)
                or (isinstance(node, ast.Attribute) and node.attr in symbols)
                or (isinstance(node, ast.Constant) and node.value in symbols)
                for node in ast.walk(tree)
            ):
                offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []


@pytest.mark.skipif(
    not os.environ.get(REAL_LAYOUT_GATE_ENV),
    reason="requires opt-in exact external OCI layout",
)
def test_exact_config_evidence_prepares_identity_bound_private_layer_plan():
    from human_feedback.runtime_oci_layers import (
        LayaOciLayerDiffIdPlan,
        prepare_laya_oci_layer_diff_id_plan,
    )

    from human_feedback.adapters.filesystem_oci_layout import (
        capture_and_verify_laya_oci_layout,
    )
    from human_feedback.runtime_oci_config import (
        validate_laya_runtime_oci_config_semantics,
    )
    from tests.test_laya_runtime_oci_layout import _oci_evidence

    root = Path(os.environ[REAL_LAYOUT_GATE_ENV])
    layout_evidence = capture_and_verify_laya_oci_layout(_oci_evidence(), root)
    config_blob = layout_evidence.plan.blobs[1]
    config_bytes = (root / config_blob.path).read_bytes()
    config_evidence = validate_laya_runtime_oci_config_semantics(
        layout_evidence,
        config_bytes,
    )

    plan = prepare_laya_oci_layer_diff_id_plan(config_evidence)

    assert type(plan) is LayaOciLayerDiffIdPlan
    assert plan.schema_version == PLAN_SCHEMA
    assert plan.config_evidence is config_evidence
    assert plan.layout_evidence is layout_evidence
    assert plan.layout_plan is layout_evidence.plan
    assert plan.runtime_identity is config_evidence.runtime_identity
    assert type(plan.layer_blobs) is tuple
    assert type(plan.layer_receipts) is tuple
    assert len(plan.layer_blobs) == len(plan.layer_receipts) == 10
    assert tuple(blob.role for blob in plan.layer_blobs) == EXPECTED_LAYER_ROLES
    assert all(
        blob is layout_evidence.plan.blobs[index + 2] for index, blob in enumerate(plan.layer_blobs)
    )
    assert all(
        receipt is layout_evidence.receipts[index + 2]
        and receipt.plan is layout_evidence.plan
        and receipt.blob is plan.layer_blobs[index]
        for index, receipt in enumerate(plan.layer_receipts)
    )
    assert plan.declared_diff_ids is config_evidence.config.declared_diff_ids
    assert len(plan.declared_diff_ids) == 10
    for claim in FALSE_CLAIMS:
        assert getattr(plan, claim) is False
    rendered = repr(plan)
    private_values = (
        *(blob.path for blob in plan.layer_blobs),
        *(blob.digest for blob in plan.layer_blobs),
        *plan.declared_diff_ids,
    )
    assert all(value not in rendered for value in private_values)

    for field in fields(plan):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(plan, field.name, getattr(plan, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
            replace(plan, **{field.name: getattr(plan, field.name)})
    with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
        LayaOciLayerDiffIdPlan(
            schema_version=PLAN_SCHEMA,
            config_evidence=config_evidence,
            layout_evidence=layout_evidence,
            layout_plan=layout_evidence.plan,
            runtime_identity=config_evidence.runtime_identity,
            layer_blobs=layout_evidence.plan.blobs[2:],
            layer_receipts=layout_evidence.receipts[2:],
            declared_diff_ids=config_evidence.config.declared_diff_ids,
        )


@pytest.mark.skipif(
    not os.environ.get(REAL_LAYOUT_GATE_ENV),
    reason="requires opt-in exact external OCI layout",
)
def test_layer_plan_rejects_foreign_and_deeply_mutated_config_graph():
    from human_feedback.runtime_oci_layers import prepare_laya_oci_layer_diff_id_plan

    from human_feedback.adapters.filesystem_oci_layout import (
        capture_and_verify_laya_oci_layout,
    )
    from human_feedback.runtime_oci_config import (
        LayaRuntimeOciConfigEvidence,
        validate_laya_runtime_oci_config_semantics,
    )
    from tests.test_laya_runtime_oci_layout import _oci_evidence

    root = Path(os.environ[REAL_LAYOUT_GATE_ENV])
    layout = capture_and_verify_laya_oci_layout(_oci_evidence(), root)
    config_bytes = (root / layout.plan.blobs[1].path).read_bytes()
    evidence = validate_laya_runtime_oci_config_semantics(layout, config_bytes)

    class ConfigEvidenceSubclass(LayaRuntimeOciConfigEvidence):
        pass

    invalid_values = [
        SimpleNamespace(config=evidence.config),
        object.__new__(ConfigEvidenceSubclass),
    ]
    mutated_projection = _forged_dataclass(
        evidence.config,
        declared_diff_ids=tuple(reversed(evidence.config.declared_diff_ids)),
    )
    invalid_values.append(_forged_dataclass(evidence, config=mutated_projection))
    foreign_layout = _forged_dataclass(
        evidence.layout_evidence,
        receipts=tuple(reversed(evidence.layout_evidence.receipts)),
    )
    invalid_values.append(_forged_dataclass(evidence, layout_evidence=foreign_layout))

    for invalid in invalid_values:
        with pytest.raises(
            (TypeError, ValueError), match="config|evidence|layout|diff|valid"
        ) as captured:
            prepare_laya_oci_layer_diff_id_plan(invalid)
        _private_error(captured.value, *evidence.config.declared_diff_ids)
