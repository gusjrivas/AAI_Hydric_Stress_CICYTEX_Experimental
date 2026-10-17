"""Opt-in real PR41 synthetic execution acceptance gate.

Requires LAYA_RUNTIME_EXECUTION_REAL=1 on non-root Linux, the fixed read-only
PR40 artifact set, Git and the trusted local Docker socket. Run serially after
unit and independent review gates. Missing external inputs fail explicitly;
this test never downloads, repairs artifacts or reads a scientific corpus.

Only the fixed synthetic fixture is executed. Success proves no scientific,
shadow or production eligibility. Ordinary CI skips this expensive gate.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

from tests.test_laya_runtime_materialization_real import (
    CHECKPOINT_ROOT,
    OCI_LAYOUT,
    _issue_real_predecessors,
    _require_external_inputs,
)

GATE_ENV = "LAYA_RUNTIME_EXECUTION_REAL"

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux")
    or not hasattr(os, "geteuid")
    or os.geteuid() == 0
    or os.environ.get(GATE_ENV) != "1",
    reason=(
        "set LAYA_RUNTIME_EXECUTION_REAL=1 on non-root Linux with the fixed "
        "closed PR40 artifact set and a trusted local Docker daemon"
    ),
)

_NON_SCIENTIFIC_CLAIMS = {
    "scientifically_sufficient",
    "eligible_for_shadow_review",
    "production_enablement_authorized",
}


def _retry_exact_execution_cleanup(adapter, error) -> None:
    """Retry only the opaque failed-attempt handle; never discover resources."""

    if not error.cleanup_pending:
        return
    try:
        adapter.retry_laya_runtime_execution_cleanup(error)
    except adapter.DockerRuntimeExecutionError as cleanup_error:
        cleanup_error.add_note(f"failure_stage={cleanup_error.failure_stage.value}")
        cleanup_error.add_note("execution_cleanup_retry=failed")
        raise cleanup_error from None
    assert error.cleanup_pending is False


def test_opt_in_real_fixed_synthetic_execution_preserves_scientific_boundary(tmp_path):
    """Verify only the fixed executor smoke; never scientific eligibility."""

    assert "PYTEST_XDIST_WORKER" not in os.environ, "real execution gate must run serially"
    _require_external_inputs()

    from human_feedback import (
        runtime_execution,
        runtime_materialization,
        runtime_rootfs_materialization,
    )
    from human_feedback.adapters import (
        docker_runtime_execution,
        docker_runtime_materialization,
        filesystem_rootfs_materialization,
    )

    rootfs, supply, checkpoint = _issue_real_predecessors()
    rootfs_plan = runtime_rootfs_materialization.prepare_laya_runtime_rootfs_materialization_plan(
        rootfs, supply
    )
    private_parent = tmp_path / "private-runtime-execution-rootfs"
    private_parent.mkdir(mode=0o700)
    private_parent.chmod(0o700)
    rootfs_evidence = None
    runtime_evidence = None
    try:
        rootfs_evidence = filesystem_rootfs_materialization.materialize_laya_runtime_rootfs(
            rootfs_plan,
            str(OCI_LAYOUT),
            str(private_parent),
            "rootfs",
        )
        exact_checkpoint = supply._provenance_evidence.checkpoint_evidence
        assert exact_checkpoint is checkpoint
        runtime_plan = runtime_materialization.prepare_laya_runtime_materialization_plan(
            rootfs_evidence, exact_checkpoint
        )
        try:
            runtime_evidence = docker_runtime_materialization.materialize_laya_runtime(
                runtime_plan, str(CHECKPOINT_ROOT)
            )
        except docker_runtime_materialization.LayaRuntimeMaterializationError as error:
            error.add_note(f"failure_stage={error.failure_stage.value}")
            if error.cleanup_pending:
                docker_runtime_materialization.retry_laya_runtime_materialization_cleanup(error)
                assert error.cleanup_pending is False
            raise

        execution_plan = runtime_execution.prepare_laya_runtime_execution_plan(runtime_evidence)
        try:
            execution_evidence = docker_runtime_execution.execute_laya_runtime(execution_plan)
        except docker_runtime_execution.DockerRuntimeExecutionError as error:
            error.add_note(f"failure_stage={error.failure_stage.value}")
            _retry_exact_execution_cleanup(docker_runtime_execution, error)
            raise

        summary = json.loads(
            runtime_execution.canonical_laya_runtime_execution_summary_bytes(execution_evidence)
        )
        claims = dict(runtime_execution.EXECUTION_CLAIMS)
        assert len(claims) == 35
        expected = {
            "schema_version": "laya-runtime-execution-evidence-v1",
            "execution_profile": runtime_execution.EXECUTION_PROFILE,
            **claims,
        }
        assert summary == expected
        assert set(summary) == set(expected)
        assert {
            claim
            for claim, value in claims.items()
            if runtime_materialization.MATERIALIZATION_CLAIMS[claim] is not value
        } == {"executor_available", "inference_executed"}
        assert summary["executor_available"] is True
        assert summary["inference_executed"] is True
        assert _NON_SCIENTIFIC_CLAIMS.isdisjoint(summary)
    finally:
        try:
            if runtime_evidence is not None:
                docker_runtime_materialization.dispose_laya_runtime(runtime_evidence)
        finally:
            if rootfs_evidence is not None:
                filesystem_rootfs_materialization.dispose_laya_runtime_rootfs(rootfs_evidence)
    assert tuple(private_parent.iterdir()) == ()
