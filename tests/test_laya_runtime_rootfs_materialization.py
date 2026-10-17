import ast
import importlib
import inspect


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
    assert module.MATERIALIZATION_CLAIMS == {
        "tar_semantics_verified": True,
        "oci_rootfs_verified": True,
        "rootfs_materialized": True,
        "runtime_materialized": False,
        "executor_available": False,
        "inference_executed": False,
    }
