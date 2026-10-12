import hashlib
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

SCHEMA_VERSION = "laya-runtime-manifest-v1"
IDENTITY_SCHEMA_VERSION = "laya-runtime-identity-v1"
SOURCE_COMMIT = "68804629e8ccd9d616d48a40e87de9fabbeae069"
BASE_IMAGE_DIGEST = "1" * 64
ARTIFACT_KINDS = (
    "dependency_lock",
    "sbom",
    "runtime_config",
    "checkpoint_manifest",
    "oci_manifest",
)
ARTIFACT_FORMATS = {
    "dependency_lock": "uv-lock-v1",
    "sbom": "cyclonedx-json-1.6",
    "runtime_config": "json",
    "checkpoint_manifest": "json",
    "oci_manifest": "oci-image-manifest-v1",
}
ARTIFACT_PATHS = {
    "dependency_lock": "locks/uv.lock",
    "sbom": "sbom/laya-runtime.cdx.json",
    "runtime_config": "config/runtime.json",
    "checkpoint_manifest": "manifests/checkpoint.json",
    "oci_manifest": "manifests/oci.json",
}
GOLDEN_EXECUTION_SUMMARY = (
    b'{"eligible_for_shadow_review":false,"execution_completed":false,'
    b'"execution_evidence_validated":true,"execution_protocol_id":'
    b'"laya-loso-execution-v1","execution_protocol_sha256":'
    b'"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    b'"gold_blind_execution_attested":false,"latency_ms_summary":'
    b'{"count":18,"maximum":12.5,"mean":12.5,"minimum":12.5},'
    b'"model_revision":"55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851",'
    b'"origin_verified":false,"predictions_count":18,'
    b'"production_enablement_authorized":false,"provider":"laya-http",'
    b'"runtime_identity_schema_version":"laya-runtime-identity-v1",'
    b'"runtime_identity_sha256":'
    b'"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",'
    b'"runtime_identity_verified":false,"schema_version":'
    b'"laya-loso-execution-contract-v1","scientifically_sufficient":false,'
    b'"structurally_valid":true,"supply_identity_verified":false}'
)


def _manifest_object() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime_id": "laya-0.4.2-python-3.11.10-linux-amd64",
        "provider": "laya-http",
        "engine": "laya==0.4.2",
        "source": f"https://github.com/convaiinnovations/laya@{SOURCE_COMMIT}",
        "license": "Apache-2.0",
        "python": "3.11.10",
        "platform": "linux/amd64",
        "base_image_ref": f"docker.io/library/python@sha256:{BASE_IMAGE_DIGEST}",
        "artifacts": [
            {
                "kind": kind,
                "format": ARTIFACT_FORMATS[kind],
                "path": ARTIFACT_PATHS[kind],
                "sha256": str(index + 2) * 64,
                "size_bytes": (index + 1) * 100,
            }
            for index, kind in enumerate(ARTIFACT_KINDS)
        ],
    }


def _manifest_bytes(value: dict[str, object] | None = None, *, indent: int | None = None) -> bytes:
    return json.dumps(
        _manifest_object() if value is None else value,
        ensure_ascii=True,
        sort_keys=False,
        allow_nan=False,
        indent=indent,
    ).encode("ascii")


def _load(value: dict[str, object] | None = None):
    from human_feedback.runtime_identity import load_laya_runtime_manifest_bytes

    return load_laya_runtime_manifest_bytes(_manifest_bytes(value))


def test_manifest_loads_exact_runtime_and_artifact_identity():
    manifest = _load()

    assert manifest.schema_version == SCHEMA_VERSION
    assert manifest.runtime_id == "laya-0.4.2-python-3.11.10-linux-amd64"
    assert manifest.provider == "laya-http"
    assert manifest.engine == "laya==0.4.2"
    assert manifest.source == (
        "https://github.com/convaiinnovations/laya@68804629e8ccd9d616d48a40e87de9fabbeae069"
    )
    assert manifest.license == "Apache-2.0"
    assert manifest.python == "3.11.10"
    assert manifest.platform == "linux/amd64"
    assert manifest.base_image_ref == f"docker.io/library/python@sha256:{BASE_IMAGE_DIGEST}"
    assert tuple(artifact.kind for artifact in manifest.artifacts) == ARTIFACT_KINDS
    assert tuple(artifact.format for artifact in manifest.artifacts) == tuple(
        ARTIFACT_FORMATS[kind] for kind in ARTIFACT_KINDS
    )


def test_runtime_types_are_frozen_slotted_and_reference_is_shared():
    from human_feedback.runtime_identity import (
        RuntimeArtifactSpec,
        RuntimeIdentityRef,
        runtime_identity_ref,
    )

    from human_feedback.evaluation_execution import RuntimeIdentityRef as ExecutionRef

    manifest = _load()
    reference = runtime_identity_ref(manifest)

    assert ExecutionRef is RuntimeIdentityRef
    assert isinstance(manifest.artifacts[0], RuntimeArtifactSpec)
    assert isinstance(reference, RuntimeIdentityRef)
    assert reference.schema_version == IDENTITY_SCHEMA_VERSION
    assert not hasattr(manifest, "__dict__")
    assert not hasattr(manifest.artifacts[0], "__dict__")
    assert not hasattr(reference, "__dict__")
    with pytest.raises(FrozenInstanceError):
        manifest.runtime_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        manifest.artifacts[0].path = "changed"  # type: ignore[misc]


def test_schema_and_json_keys_are_exact_and_fail_closed():
    value = _manifest_object()
    value["unexpected"] = "field"
    with pytest.raises(ValueError, match="manifest|field|key|schema"):
        _load(value)

    missing = _manifest_object()
    missing.pop("platform")
    with pytest.raises(ValueError, match="manifest|field|key|platform"):
        _load(missing)

    artifact_extra = _manifest_object()
    artifact_extra["artifacts"][0]["unexpected"] = "field"  # type: ignore[index]
    with pytest.raises(ValueError, match="artifact|field|key"):
        _load(artifact_extra)


def test_loader_rejects_duplicate_json_keys_and_nonfinite_numbers():
    valid = _manifest_bytes().decode("ascii")
    duplicate = valid.replace(
        '"runtime_id": "laya-0.4.2-python-3.11.10-linux-amd64",',
        '"runtime_id":"duplicate","runtime_id":' '"laya-0.4.2-python-3.11.10-linux-amd64",',
        1,
    ).encode("ascii")
    nonfinite = valid.replace('"size_bytes": 100', '"size_bytes": NaN', 1).encode("ascii")

    from human_feedback.runtime_identity import load_laya_runtime_manifest_bytes

    with pytest.raises(ValueError, match="duplicate|JSON|key"):
        load_laya_runtime_manifest_bytes(duplicate)
    with pytest.raises(ValueError, match="finite|JSON|numeric|number"):
        load_laya_runtime_manifest_bytes(nonfinite)


def test_loader_accepts_bytes_only_and_rejects_invalid_utf8():
    from human_feedback.runtime_identity import load_laya_runtime_manifest_bytes

    with pytest.raises((TypeError, ValueError), match="bytes|payload|UTF-8"):
        load_laya_runtime_manifest_bytes(_manifest_bytes().decode("ascii"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="UTF-8|JSON|payload"):
        load_laya_runtime_manifest_bytes(b"\xff")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "laya-runtime-manifest-v2"),
        ("runtime_id", " laya-runtime"),
        ("runtime_id", "laya-runtimé"),
        ("provider", "other-provider"),
        ("engine", "laya==0.4.3"),
        ("source", f"https://github.com/convaiinnovations/laya@{'0' * 40}"),
        ("source", "https://github.com/convaiinnovations/laya@6880462"),
        ("source", f"https://github.com/convaiinnovations/laya@{SOURCE_COMMIT.upper()}"),
        ("source", f"https://github.com/convaiinnovations/laya@{'g' * 40}"),
        ("source", f"https://example.test/laya@{SOURCE_COMMIT}"),
        ("license", "MIT"),
        ("python", "3.11.11"),
        ("platform", "linux/arm64"),
        ("base_image_ref", f"docker.io/library/python:3.11@sha256:{BASE_IMAGE_DIGEST}"),
        ("base_image_ref", f"docker.io/library/python@sha256:{'0' * 64}"),
        ("base_image_ref", f"docker.io/library/python@sha256:{'A' * 64}"),
    ],
)
def test_manifest_rejects_unpinned_or_noncanonical_runtime_fields(field: str, value: str):
    manifest = _manifest_object()
    manifest[field] = value

    with pytest.raises(
        ValueError,
        match="runtime|schema|provider|engine|source|commit|license|python|platform|image|digest",
    ):
        _load(manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "wheel"),
        ("format", "json-v2"),
        ("sha256", "0" * 64),
        ("sha256", "A" * 64),
        ("sha256", "abc"),
        ("size_bytes", True),
        ("size_bytes", -1),
    ],
)
def test_artifacts_reject_invalid_kind_format_digest_and_size(field: str, value: object):
    manifest = _manifest_object()
    manifest["artifacts"][0][field] = value  # type: ignore[index]

    with pytest.raises(ValueError, match="artifact|kind|format|digest|SHA-256|size|numeric"):
        _load(manifest)


@pytest.mark.parametrize(
    "path",
    [
        "/absolute/uv.lock",
        "C:/absolute/uv.lock",
        "locks\\uv.lock",
        "./locks/uv.lock",
        "locks/../uv.lock",
        "locks//uv.lock",
        "locks/./uv.lock",
        "locks/uv lock",
        "locks/üv.lock",
        "locks/uv.lock/",
    ],
)
def test_artifact_paths_are_canonical_relative_posix(path: str):
    manifest = _manifest_object()
    manifest["artifacts"][0]["path"] = path  # type: ignore[index]

    with pytest.raises(ValueError, match="artifact|path|POSIX|relative|canonical"):
        _load(manifest)


def test_manifest_requires_each_exact_artifact_kind_once():
    missing = _manifest_object()
    missing["artifacts"] = missing["artifacts"][:-1]  # type: ignore[index]
    with pytest.raises(ValueError, match="artifact|kind|exact|missing"):
        _load(missing)

    duplicate = _manifest_object()
    duplicate["artifacts"][-1] = deepcopy(duplicate["artifacts"][0])  # type: ignore[index]
    with pytest.raises(ValueError, match="artifact|kind|duplicate|exact"):
        _load(duplicate)


def test_artifacts_are_canonically_ordered_and_digest_ignores_json_layout():
    from human_feedback.runtime_identity import (
        canonical_laya_runtime_manifest_bytes,
        laya_runtime_identity_digest,
    )

    ordered_value = _manifest_object()
    reversed_value = deepcopy(ordered_value)
    reversed_value["artifacts"] = list(reversed(reversed_value["artifacts"]))  # type: ignore[arg-type]
    ordered = _load(ordered_value)
    reversed_manifest = _load(reversed_value)

    assert tuple(item.kind for item in reversed_manifest.artifacts) == ARTIFACT_KINDS
    assert canonical_laya_runtime_manifest_bytes(ordered) == canonical_laya_runtime_manifest_bytes(
        reversed_manifest
    )
    assert laya_runtime_identity_digest(ordered) == laya_runtime_identity_digest(reversed_manifest)

    reordered_keys = dict(reversed(list(ordered_value.items())))
    pretty = json.dumps(reordered_keys, indent=4, ensure_ascii=True).encode("ascii")
    from human_feedback.runtime_identity import load_laya_runtime_manifest_bytes

    layout_variant = load_laya_runtime_manifest_bytes(pretty)
    assert laya_runtime_identity_digest(layout_variant) == laya_runtime_identity_digest(ordered)


def test_identity_digest_is_canonical_and_semantically_sensitive():
    from human_feedback.runtime_identity import (
        canonical_laya_runtime_manifest_bytes,
        laya_runtime_identity_digest,
        runtime_identity_ref,
    )

    manifest = _load()
    changed_value = _manifest_object()
    changed_value["artifacts"][0]["size_bytes"] = 101  # type: ignore[index]
    changed = _load(changed_value)
    canonical = canonical_laya_runtime_manifest_bytes(manifest)

    assert laya_runtime_identity_digest(manifest) == hashlib.sha256(canonical).hexdigest()
    assert manifest.identity_sha256 == laya_runtime_identity_digest(manifest)
    assert runtime_identity_ref(manifest).sha256 == manifest.identity_sha256
    assert laya_runtime_identity_digest(changed) != laya_runtime_identity_digest(manifest)


def test_manifest_flags_are_structural_only_and_cannot_be_forged():
    manifest = _load()
    expected = {
        "structurally_valid": True,
        "artifact_integrity_verified": False,
        "lock_verified": False,
        "sbom_verified": False,
        "lock_sbom_consistent": False,
        "checkpoint_bytes_verified": False,
        "oci_bytes_verified": False,
        "runtime_materialized": False,
        "origin_verified": False,
        "executor_available": False,
        "inference_executed": False,
    }

    for field, value in expected.items():
        assert getattr(manifest, field) is value
        with pytest.raises((TypeError, ValueError)):
            replace(manifest, **{field: not value})
    with pytest.raises((TypeError, ValueError)):
        replace(manifest, identity_sha256="f" * 64)


def test_execution_summary_bytes_remain_pr14_golden(tmp_path: Path):
    from human_feedback.runtime_identity import RuntimeIdentityRef

    from human_feedback.evaluation_execution import (
        canonical_loso_execution_summary_bytes,
        validate_loso_prediction_set,
    )
    from tests.test_laya_evaluation_execution import _contract, _predictions

    contract, _ = _contract(tmp_path)
    assert type(contract.runtime_identity) is RuntimeIdentityRef
    evidence = validate_loso_prediction_set(contract, _predictions(contract))

    assert canonical_loso_execution_summary_bytes(evidence) == GOLDEN_EXECUTION_SUMMARY


def test_runtime_identity_is_isolated_from_execution_and_operational_flows():
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
            if "human_feedback.runtime_identity" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(repository).as_posix())
    for path in files:
        if "human_feedback.runtime_identity" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []
