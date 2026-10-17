"""Opt-in release gate over the complete real PR40 artifact chain.

This test is intentionally absent from ordinary CI.  It requires non-root
Linux, a trusted local Docker daemon at ``/var/run/docker.sock``, Git, and the
four read-only external inputs below.  Enable it only with
``LAYA_RUNTIME_MATERIALIZATION_REAL=1`` and run it serially.  Missing inputs are
an explicit gate failure; the test never downloads or repairs artifacts.

The gate verifies and retains no scientific corpus and performs no inference.
It creates only a disposable rootfs and a disposable derived Docker image,
both of which are explicitly disposed.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_laya_runtime_base_ancestry import _fixture_bytes as _base_ancestry_bytes
from tests.test_laya_runtime_oci_layout import _oci_evidence

GATE_ENV = "LAYA_RUNTIME_MATERIALIZATION_REAL"
WORK_ROOT = Path(__file__).resolve().parents[2]
OCI_LAYOUT = WORK_ROOT / "pr19-oci-generation" / "layout"
CHECKPOINT_ROOT = WORK_ROOT / "laya-checkpoint-55cf4c4e"
SOURCE_GIT = WORK_ROOT / "vendor" / "laya-v0.4.2"
MODEL_GIT_CANDIDATES = (
    WORK_ROOT / "vendor" / "laya-bundle-manifest",
    WORK_ROOT / "vendor" / "laya-multilingual-manifest",
)
DOCKER_SOCKET = Path("/var/run/docker.sock")

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux")
    or not hasattr(os, "geteuid")
    or os.geteuid() == 0
    or os.environ.get(GATE_ENV) != "1",
    reason=(
        "set LAYA_RUNTIME_MATERIALIZATION_REAL=1 on non-root Linux with the "
        "closed external artifact set and a trusted local Docker daemon"
    ),
)


def _require_external_inputs() -> None:
    missing = [str(path) for path in (OCI_LAYOUT, CHECKPOINT_ROOT, SOURCE_GIT) if not path.is_dir()]
    if not any(path.is_dir() for path in MODEL_GIT_CANDIDATES):
        missing.append("one of: " + ", ".join(map(str, MODEL_GIT_CANDIDATES)))
    if shutil.which("git") is None:
        missing.append("git executable")
    try:
        socket_is_available = stat.S_ISSOCK(DOCKER_SOCKET.stat().st_mode)
    except OSError:
        socket_is_available = False
    if not socket_is_available:
        missing.append(str(DOCKER_SOCKET))
    if missing:
        pytest.fail("real runtime materialization gate is missing: " + "; ".join(missing))


def _git_object(repository: Path, kind: str, sha1: str) -> bytes:
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    completed = subprocess.run(
        (
            "git",
            "-c",
            f"safe.directory={repository}",
            "-C",
            str(repository),
            "cat-file",
            kind,
            sha1,
        ),
        check=True,
        capture_output=True,
        env=environment,
        timeout=20,
    )
    return completed.stdout


def _repository_holds_plan_objects(repository: Path, specs: tuple[object, ...]) -> bool:
    try:
        for spec in specs:
            _git_object(repository, spec.kind, spec.sha1)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def _real_provenance_packets(plan) -> tuple[tuple[object, ...], ...]:
    from human_feedback import runtime_provenance

    source_specs = tuple(
        spec for spec in plan.objects if spec.repository == runtime_provenance.SOURCE_REPOSITORY
    )
    checkpoint_specs = tuple(
        spec for spec in plan.objects if spec.repository == runtime_provenance.CHECKPOINT_REPOSITORY
    )
    assert source_specs and checkpoint_specs
    assert _repository_holds_plan_objects(SOURCE_GIT, source_specs)
    model_repository = next(
        (
            candidate
            for candidate in MODEL_GIT_CANDIDATES
            if candidate.is_dir() and _repository_holds_plan_objects(candidate, checkpoint_specs)
        ),
        None,
    )
    assert model_repository is not None, "no checkpoint Git mirror has the exact plan objects"
    repositories = {
        runtime_provenance.SOURCE_REPOSITORY: SOURCE_GIT,
        runtime_provenance.CHECKPOINT_REPOSITORY: model_repository,
    }
    packets = []
    for spec in plan.objects:
        payload = _git_object(repositories[spec.repository], spec.kind, spec.sha1)
        header = spec.kind.encode("ascii") + b" " + str(len(payload)).encode("ascii") + b"\0"
        assert hashlib.sha1(header + payload, usedforsecurity=False).hexdigest() == spec.sha1
        assert hashlib.sha256(payload).hexdigest() == spec.sha256
        assert len(payload) == spec.size_bytes
        packets.append((spec.repository, spec.kind, spec.sha1, (payload,)))
    return tuple(packets)


def _issue_real_predecessors():
    from human_feedback import (
        runtime_base_ancestry,
        runtime_checkpoint,
        runtime_deployment_metadata,
        runtime_oci_config,
        runtime_oci_rootfs,
        runtime_provenance,
        runtime_supply_convergence,
    )
    from human_feedback.adapters import filesystem_oci_layout
    from human_feedback.adapters.filesystem_checkpoint import (
        capture_and_verify_laya_runtime_checkpoint,
    )

    oci = _oci_evidence()
    layout = filesystem_oci_layout.capture_and_verify_laya_oci_layout(oci, str(OCI_LAYOUT))
    config_blob = layout.plan.blobs[1]
    config_payload = (OCI_LAYOUT / config_blob.path).read_bytes()
    config = runtime_oci_config.validate_laya_runtime_oci_config_semantics(layout, config_payload)
    layers = filesystem_oci_layout.capture_and_verify_laya_oci_layer_diff_ids(
        config, str(OCI_LAYOUT)
    )
    tar = filesystem_oci_layout.capture_and_verify_laya_oci_tar_semantics(layers, str(OCI_LAYOUT))
    rootfs = runtime_oci_rootfs.compose_laya_oci_rootfs(
        runtime_oci_rootfs.prepare_laya_oci_rootfs_plan(tar)
    )

    base_plan = runtime_base_ancestry.prepare_laya_runtime_base_ancestry_plan(layers)
    base = runtime_base_ancestry.verify_laya_runtime_base_ancestry_objects(
        base_plan,
        tuple(iter((payload,)) for payload in _base_ancestry_bytes()),
    )
    deployment = runtime_deployment_metadata.validate_laya_runtime_deployment_metadata(oci.snapshot)
    checkpoint = capture_and_verify_laya_runtime_checkpoint(deployment, str(CHECKPOINT_ROOT))
    provenance_plan = runtime_provenance.prepare_laya_runtime_provenance_plan(checkpoint)
    provenance = runtime_provenance.verify_laya_runtime_provenance_objects(
        provenance_plan, _real_provenance_packets(provenance_plan)
    )
    supply = runtime_supply_convergence.verify_laya_runtime_supply_convergence(
        layers, provenance, base
    )
    assert supply._provenance_evidence.checkpoint_evidence is checkpoint
    assert (
        checkpoint.plan.files
        == runtime_checkpoint.prepare_laya_runtime_checkpoint_plan(deployment).files
    )
    return rootfs, supply, checkpoint


def test_opt_in_real_artifact_chain_materializes_closed_offline_runtime(tmp_path):
    """Verify HU5/HU6 only: import and model-load probe, never inference."""

    assert "PYTEST_XDIST_WORKER" not in os.environ, "real artifact gate must run serially"
    _require_external_inputs()

    from human_feedback import (
        runtime_materialization,
        runtime_rootfs_materialization,
    )
    from human_feedback.adapters import (
        docker_runtime_materialization,
        filesystem_rootfs_materialization,
    )

    rootfs, supply, checkpoint = _issue_real_predecessors()
    rootfs_plan = runtime_rootfs_materialization.prepare_laya_runtime_rootfs_materialization_plan(
        rootfs, supply
    )
    private_parent = tmp_path / "private-runtime-rootfs"
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
            raise
        summary = json.loads(
            runtime_materialization.canonical_laya_runtime_materialization_summary_bytes(
                runtime_evidence
            )
        )
        assert summary["runtime_materialized"] is True
        assert summary["rootfs_materialized"] is True
        assert summary["executor_available"] is False
        assert summary["inference_executed"] is False
    finally:
        try:
            if runtime_evidence is not None:
                docker_runtime_materialization.dispose_laya_runtime(runtime_evidence)
        finally:
            if rootfs_evidence is not None:
                filesystem_rootfs_materialization.dispose_laya_runtime_rootfs(rootfs_evidence)
    assert tuple(private_parent.iterdir()) == ()
