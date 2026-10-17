"""Opt-in fixed-fixture offline-v2 acceptance over the genuine pinned runtime.

This operational gate performs no corpus evaluation, fitting or scoring. It
reuses the reviewed PR40 supply/rootfs/checkpoint chain without downloads or
repairs, sends only two fixed synthetic comments, then disposes all resources.
Ordinary CI skips the gate; a skip is never scientific or real acceptance.
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

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux")
    or not hasattr(os, "geteuid")
    or os.geteuid() == 0
    or os.environ.get("LAYA_LOSO_OFFLINE_REAL") != "1",
    reason="requires explicitly enabled non-root Linux and the fixed PR40 artifact set",
)


def test_real_offline_port_uses_only_fixed_synthetic_comments_and_cleans_everything(tmp_path):
    assert "PYTEST_XDIST_WORKER" not in os.environ, "real gate must run serially"
    _require_external_inputs()

    from human_feedback import runtime_materialization, runtime_rootfs_materialization
    from human_feedback.adapters import (
        docker_runtime_materialization,
        filesystem_rootfs_materialization,
        laya_loso_docker_adapter,
    )
    from human_feedback.loso_offline_adapter import (
        GoldBlindOfflineInput,
        canonical_laya_loso_offline_request_bytes,
        validate_laya_loso_offline_response,
    )

    rootfs, supply, checkpoint = _issue_real_predecessors()
    rootfs_plan = runtime_rootfs_materialization.prepare_laya_runtime_rootfs_materialization_plan(
        rootfs, supply
    )
    private_parent = tmp_path / "private-offline-loso-rootfs"
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
        assert supply._provenance_evidence.checkpoint_evidence is checkpoint
        runtime_plan = runtime_materialization.prepare_laya_runtime_materialization_plan(
            rootfs_evidence, checkpoint
        )
        try:
            runtime_evidence = docker_runtime_materialization.materialize_laya_runtime(
                runtime_plan, str(CHECKPOINT_ROOT)
            )
        except docker_runtime_materialization.LayaRuntimeMaterializationError as error:
            if error.cleanup_pending:
                docker_runtime_materialization.retry_laya_runtime_materialization_cleanup(error)
                assert error.cleanup_pending is False
            raise

        original_summary = (
            runtime_materialization.canonical_laya_runtime_materialization_summary_bytes(
                runtime_evidence
            )
        )
        request = canonical_laya_loso_offline_request_bytes(
            (
                GoldBlindOfflineInput(
                    opaque_token="a" * 64,
                    comment="Synthetic offline fixture: please review missing sensor data.",
                ),
                GoldBlindOfflineInput(
                    opaque_token="b" * 64,
                    comment="Synthetic offline fixture: please review the page layout.",
                ),
            )
        )
        port = laya_loso_docker_adapter.DockerLayaLosoOfflinePort(runtime_evidence)
        try:
            response = port.predict(request)
        except laya_loso_docker_adapter.DockerLayaLosoOfflineError as error:
            if error.cleanup_pending:
                laya_loso_docker_adapter.retry_laya_loso_offline_cleanup(error)
                assert error.cleanup_pending is False
            raise
        assert validate_laya_loso_offline_response(response, expected_count=2) == response
        decoded = json.loads(response)
        assert decoded["schema_version"] == "laya-gold-blind-offline-response-v2"
        assert [item["ordinal"] for item in decoded["predictions"]] == [0, 1]
        for item in decoded["predictions"]:
            assert item["usage"]["state_tokens_dropped"] == 0
            assert item["usage"]["truncated"] is False
        assert (
            runtime_materialization.canonical_laya_runtime_materialization_summary_bytes(
                runtime_evidence
            )
            == original_summary
        )
    finally:
        try:
            if runtime_evidence is not None:
                docker_runtime_materialization.dispose_laya_runtime(runtime_evidence)
        finally:
            if rootfs_evidence is not None:
                filesystem_rootfs_materialization.dispose_laya_runtime_rootfs(rootfs_evidence)
    assert tuple(private_parent.iterdir()) == ()
