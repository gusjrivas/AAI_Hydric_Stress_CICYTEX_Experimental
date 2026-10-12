import hashlib
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, is_dataclass, replace
from pathlib import Path

import pytest

ARTIFACT_KINDS = (
    "dependency_lock",
    "sbom",
    "runtime_config",
    "checkpoint_manifest",
    "oci_manifest",
)
ARTIFACT_PATHS = {
    "dependency_lock": "locks/uv.lock",
    "sbom": "sbom/laya-runtime.cdx.json",
    "runtime_config": "config/runtime.json",
    "checkpoint_manifest": "manifests/checkpoint.json",
    "oci_manifest": "manifests/oci.json",
}
SNAPSHOT_SCHEMA_VERSION = "laya-runtime-bundle-snapshot-v1"


def _payloads() -> dict[str, bytes]:
    return {
        ARTIFACT_PATHS[kind]: f"private-{kind}-artifact-bytes-v1\n".encode("ascii")
        for kind in ARTIFACT_KINDS
    }


def _manifest(*, payloads: dict[str, bytes] | None = None, mutation=None):
    from human_feedback.runtime_identity import load_laya_runtime_manifest_bytes
    from tests.test_laya_runtime_identity import _manifest_object

    payload_by_path = _payloads() if payloads is None else payloads
    value = deepcopy(_manifest_object())
    for artifact in value["artifacts"]:
        content = payload_by_path[artifact["path"]]
        artifact["sha256"] = hashlib.sha256(content).hexdigest()
        artifact["size_bytes"] = len(content)
    if mutation is not None:
        mutation(value)
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return load_laya_runtime_manifest_bytes(encoded)


def _verify(manifest=None, payloads: dict[str, bytes] | None = None):
    from human_feedback.runtime_bundle import verify_laya_runtime_artifact_bytes

    actual_payloads = _payloads() if payloads is None else payloads
    actual_manifest = _manifest(payloads=actual_payloads) if manifest is None else manifest
    return verify_laya_runtime_artifact_bytes(actual_manifest, actual_payloads)


def _raw_values(payloads: dict[str, bytes]) -> tuple[str, ...]:
    return tuple(content.decode("ascii") for content in payloads.values())


def test_exact_in_memory_bundle_verification_succeeds():
    from human_feedback.runtime_bundle import (
        CapturedRuntimeArtifact,
        LayaRuntimeBundleSnapshot,
    )

    manifest = _manifest()
    snapshot = _verify(manifest)

    assert isinstance(snapshot, LayaRuntimeBundleSnapshot)
    assert snapshot.schema_version == SNAPSHOT_SCHEMA_VERSION
    assert snapshot.manifest is manifest
    assert tuple(artifact.spec.kind for artifact in snapshot.artifacts) == ARTIFACT_KINDS
    assert all(isinstance(artifact, CapturedRuntimeArtifact) for artifact in snapshot.artifacts)
    assert snapshot.artifact_integrity_verified is True


@pytest.mark.parametrize("case", ["missing", "additional"])
def test_payload_coverage_must_match_exact_contract_paths(case: str):
    manifest = _manifest()
    payloads = _payloads()
    if case == "missing":
        payloads.pop(ARTIFACT_PATHS["sbom"])
    else:
        payloads["unexpected/extra.bin"] = b"private-extra-content"

    with pytest.raises(ValueError, match="artifact|payload|coverage|missing|additional") as error:
        _verify(manifest, payloads)

    assert all(raw not in str(error.value) for raw in _raw_values(payloads))


def test_payload_values_must_be_bytes_not_bool_text_or_buffers():
    manifest = _manifest()
    for invalid in ("text", True, bytearray(b"buffer"), memoryview(b"view")):
        payloads = _payloads()
        payloads[ARTIFACT_PATHS["runtime_config"]] = invalid  # type: ignore[assignment]
        with pytest.raises((TypeError, ValueError), match="artifact|payload|bytes"):
            _verify(manifest, payloads)


@pytest.mark.parametrize("case", ["tamper", "truncate", "grow", "declared-hash", "declared-size"])
def test_payload_hash_and_size_must_match_each_declared_artifact(case: str):
    payloads = _payloads()
    path = ARTIFACT_PATHS["checkpoint_manifest"]
    manifest = _manifest(payloads=payloads)
    if case == "tamper":
        original = payloads[path]
        payloads[path] = bytes([original[0] ^ 1]) + original[1:]
    elif case == "truncate":
        payloads[path] = payloads[path][:-1]
    elif case == "grow":
        payloads[path] += b"x"
    elif case == "declared-hash":
        manifest = _manifest(
            payloads=payloads,
            mutation=lambda value: value["artifacts"][3].update(sha256="f" * 64),
        )
    else:
        manifest = _manifest(
            payloads=payloads,
            mutation=lambda value: value["artifacts"][3].update(
                size_bytes=value["artifacts"][3]["size_bytes"] + 1
            ),
        )

    with pytest.raises(ValueError, match="artifact|integrity|digest|hash|size") as error:
        _verify(manifest, payloads)

    assert all(raw not in str(error.value) for raw in _raw_values(payloads))


@pytest.mark.parametrize("path", tuple(ARTIFACT_PATHS.values()))
def test_git_lfs_pointer_is_rejected_for_every_artifact_kind(path: str):
    manifest = _manifest()
    payloads = _payloads()
    pointer = (
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        b"size 123\n"
    )
    payloads[path] = pointer

    with pytest.raises(ValueError, match="Git LFS|LFS|pointer") as error:
        _verify(manifest, payloads)

    assert pointer.decode("ascii") not in str(error.value)


def test_snapshot_and_summary_are_canonical_despite_payload_dict_order():
    from human_feedback.runtime_bundle import canonical_laya_runtime_bundle_summary_bytes

    manifest = _manifest()
    ordered = _payloads()
    reversed_payloads = dict(reversed(tuple(ordered.items())))

    snapshot_a = _verify(manifest, ordered)
    snapshot_b = _verify(manifest, reversed_payloads)

    assert snapshot_a.artifacts == snapshot_b.artifacts
    assert tuple(item.spec.kind for item in snapshot_b.artifacts) == ARTIFACT_KINDS
    assert canonical_laya_runtime_bundle_summary_bytes(
        snapshot_a
    ) == canonical_laya_runtime_bundle_summary_bytes(snapshot_b)


def test_snapshot_runtime_reference_matches_manifest_identity():
    from human_feedback.runtime_identity import runtime_identity_ref

    manifest = _manifest()
    snapshot = _verify(manifest)

    assert snapshot.runtime_identity == runtime_identity_ref(manifest)


def test_captured_artifacts_and_snapshot_are_frozen_slotted_dataclasses():
    snapshot = _verify()
    captured = snapshot.artifacts[0]

    assert is_dataclass(snapshot)
    assert is_dataclass(captured)
    assert not hasattr(snapshot, "__dict__")
    assert not hasattr(captured, "__dict__")
    with pytest.raises(FrozenInstanceError):
        snapshot.artifact_integrity_verified = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        captured.content = b"changed"  # type: ignore[misc]
    with pytest.raises((TypeError, ValueError)):
        replace(captured, content=b"changed")


def test_raw_artifact_content_never_appears_in_repr_or_public_summary():
    from human_feedback.runtime_bundle import canonical_laya_runtime_bundle_summary_bytes

    payloads = _payloads()
    snapshot = _verify(payloads=payloads)
    summary = canonical_laya_runtime_bundle_summary_bytes(snapshot)
    rendered = repr(snapshot) + repr(snapshot.artifacts)
    decoded = json.loads(summary)

    assert decoded["schema_version"] == SNAPSHOT_SCHEMA_VERSION
    assert decoded["runtime_identity_schema_version"] == snapshot.runtime_identity.schema_version
    assert decoded["runtime_identity_sha256"] == snapshot.runtime_identity.sha256
    assert decoded["artifact_integrity_verified"] is True
    for raw in _raw_values(payloads):
        assert raw not in rendered
        assert raw.encode("ascii") not in summary
    assert "content=" not in rendered
    assert "content" not in decoded


def test_snapshot_flags_do_not_overclaim_semantics_or_execution():
    snapshot = _verify()
    expected = {
        "artifact_integrity_verified": True,
        "lock_verified": False,
        "sbom_verified": False,
        "lock_sbom_consistent": False,
        "runtime_config_semantics_verified": False,
        "checkpoint_manifest_semantics_verified": False,
        "oci_manifest_semantics_verified": False,
        "runtime_materialized": False,
        "origin_verified": False,
        "executor_available": False,
        "inference_executed": False,
    }

    for field, value in expected.items():
        assert getattr(snapshot, field) is value
        with pytest.raises((TypeError, ValueError)):
            replace(snapshot, **{field: not value})


def test_direct_snapshot_construction_cannot_self_attest_validity():
    snapshot = _verify()

    with pytest.raises((TypeError, ValueError), match="verif|factory|token|seal|direct"):
        type(snapshot)(
            schema_version=snapshot.schema_version,
            manifest=snapshot.manifest,
            artifacts=snapshot.artifacts,
            runtime_identity=snapshot.runtime_identity,
        )
    with pytest.raises((TypeError, ValueError)):
        replace(snapshot, artifacts=snapshot.artifacts)


def test_runtime_bundle_implementation_is_pure_and_has_no_io_or_executor_dependency():
    from human_feedback import runtime_bundle

    source = Path(runtime_bundle.__file__).read_text(encoding="utf-8")
    forbidden = (
        "subprocess",
        "requests",
        "httpx",
        "docker",
        "Path(",
        "open(",
        "read_bytes",
        "write_bytes",
    )

    assert [token for token in forbidden if token in source] == []


def test_runtime_bundle_is_isolated_from_operational_flows():
    repository = Path(__file__).parents[1]
    roots = (
        repository / "backend",
        repository / "src" / "human_feedback" / "adapters",
        repository / "src" / "experiment_runner",
        repository / "scripts",
    )
    files = (repository / "src" / "human_feedback" / "offline_readiness.py",)
    offenders = []
    for root in roots:
        for path in root.rglob("*.py"):
            if "human_feedback.runtime_bundle" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(repository).as_posix())
    for path in files:
        if "human_feedback.runtime_bundle" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []
