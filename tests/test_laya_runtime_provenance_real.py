import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_laya_runtime_deployment_metadata import _validate
from tests.test_laya_runtime_provenance import (
    CHECKPOINT_REPOSITORY,
    EVIDENCE_SCHEMA,
    SOURCE_REPOSITORY,
    _git_sha1,
)

REQUIRED_ENV = (
    "LAYA_RUNTIME_CHECKPOINT_ROOT",
    "LAYA_SOURCE_GIT_DIR",
    "LAYA_CHECKPOINT_GIT_DIR",
)


def _gate_enabled() -> bool:
    return sys.platform.startswith("linux") and all(os.environ.get(name) for name in REQUIRED_ENV)


def _git_object(repository: Path, kind: str, sha1: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(repository), "cat-file", kind, sha1),
        check=True,
        capture_output=True,
    )
    return completed.stdout


@pytest.mark.skipif(
    not _gate_enabled(),
    reason="real provenance repositories and checkpoint bytes are an explicit Linux gate",
)
def test_opt_in_real_git_objects_bind_to_checkpoint_evidence_without_payload_retention():
    import human_feedback.runtime_provenance as provenance

    from human_feedback.adapters.filesystem_checkpoint import (
        capture_and_verify_laya_runtime_checkpoint,
    )

    checkpoint = capture_and_verify_laya_runtime_checkpoint(
        _validate(), Path(os.environ["LAYA_RUNTIME_CHECKPOINT_ROOT"])
    )
    plan = provenance.prepare_laya_runtime_provenance_plan(checkpoint)
    repositories = {
        SOURCE_REPOSITORY: Path(os.environ["LAYA_SOURCE_GIT_DIR"]),
        CHECKPOINT_REPOSITORY: Path(os.environ["LAYA_CHECKPOINT_GIT_DIR"]),
    }
    streams = []
    for item in plan.objects:
        payload = _git_object(repositories[item.repository], item.kind, item.sha1)
        assert len(payload) == item.size_bytes
        assert _git_sha1(item.kind, payload) == item.sha1
        assert hashlib.sha256(payload).hexdigest() == item.sha256
        streams.append((item.sha1, (payload,)))

    evidence = provenance.verify_laya_runtime_provenance(checkpoint, tuple(streams))

    assert type(evidence) is provenance.LayaRuntimeProvenanceEvidence
    assert evidence.checkpoint_evidence is checkpoint
    assert evidence.plan.checkpoint_evidence is checkpoint
    assert tuple(receipt.object_spec for receipt in evidence.receipts) == plan.objects
    assert all(receipt.object_bytes_verified is True for receipt in evidence.receipts)
    assert evidence.provenance_objects_verified is True
    assert evidence.origin_verified is False
    assert evidence.license_verified is False
    summary = provenance.canonical_laya_runtime_provenance_summary_bytes(evidence)
    assert EVIDENCE_SCHEMA.encode("ascii") in summary
    for item in plan.objects:
        assert item.sha1.encode("ascii") not in summary
        assert item.sha256.encode("ascii") not in summary
        assert not hasattr(evidence, "payload")


@pytest.mark.skipif(
    not _gate_enabled(),
    reason="real provenance repositories and checkpoint bytes are an explicit Linux gate",
)
@pytest.mark.parametrize("mutation", ("missing", "extra", "reordered", "duplicate"))
def test_opt_in_real_provenance_is_exact_ordered_and_all_or_nothing(mutation):
    import human_feedback.runtime_provenance as provenance

    from human_feedback.adapters.filesystem_checkpoint import (
        capture_and_verify_laya_runtime_checkpoint,
    )

    checkpoint = capture_and_verify_laya_runtime_checkpoint(
        _validate(), Path(os.environ["LAYA_RUNTIME_CHECKPOINT_ROOT"])
    )
    plan = provenance.prepare_laya_runtime_provenance_plan(checkpoint)
    repositories = {
        SOURCE_REPOSITORY: Path(os.environ["LAYA_SOURCE_GIT_DIR"]),
        CHECKPOINT_REPOSITORY: Path(os.environ["LAYA_CHECKPOINT_GIT_DIR"]),
    }
    streams = tuple(
        (
            item.sha1,
            (_git_object(repositories[item.repository], item.kind, item.sha1),),
        )
        for item in plan.objects
    )
    invalid = {
        "missing": streams[:-1],
        "extra": streams + (streams[-1],),
        "reordered": (streams[1], streams[0], *streams[2:]),
        "duplicate": (streams[0], streams[0], *streams[2:]),
    }[mutation]

    with pytest.raises(ValueError):
        provenance.verify_laya_runtime_provenance(checkpoint, invalid)
