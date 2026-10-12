import ast
import hashlib
import json
import sys
from copy import deepcopy
from dataclasses import FrozenInstanceError, is_dataclass, replace
from pathlib import Path

import pytest

from tests.test_laya_runtime_artifact_integrity import (
    ARTIFACT_PATHS,
    _manifest,
    _payloads,
    _verify,
)

DEPLOYMENT_SCHEMA_VERSION = "laya-runtime-deployment-evidence-v1"
RUNTIME_CONFIG_SCHEMA_VERSION = "laya-runtime-config-v1"
CHECKPOINT_SCHEMA_VERSION = "laya-checkpoint-manifest-v1"
MODEL_REPOSITORY = "convaiinnovations/laya"
MODEL_REVISION = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
MODEL_SUBFOLDER = "multilingual"
CHECKPOINT_FILES = (
    {
        "role": "encoder_config",
        "path": "encoder/config.json",
        "sha256": "83f6916d13ef0f556ac461f28308dc2bffa7ebeadee8ec9e2db5812020ea5bb4",
        "size_bytes": 1938,
    },
    {
        "role": "weights",
        "path": "model.safetensors",
        "sha256": "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204",
        "size_bytes": 643835514,
    },
    {
        "role": "laya_config",
        "path": "rl_agent_config.json",
        "sha256": "25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6",
        "size_bytes": 472,
    },
    {
        "role": "tokenizer",
        "path": "tokenizer/tokenizer.json",
        "sha256": "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f",
        "size_bytes": 34363188,
    },
    {
        "role": "tokenizer_config",
        "path": "tokenizer/tokenizer_config.json",
        "sha256": "6c6b2d8e3c84ce0e671c129cd6b374b235d6f9863042a5836358d00a89bbb5a1",
        "size_bytes": 524,
    },
)
ENVIRONMENT = {
    "LAYA_DEVICE": "cpu",
    "LAYA_PRELOAD": "1",
    "LAYA_MODELS": "multilingual",
    "LAYA_AUTO_TASK": "0",
    "LAYA_DEFAULT_MODEL": "multilingual",
    "LAYA_REVISION": MODEL_REVISION,
    "HF_HUB_OFFLINE": "1",
}


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


def _checkpoint_object() -> dict[str, object]:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "repository": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "subfolder": MODEL_SUBFOLDER,
        "files": deepcopy(list(CHECKPOINT_FILES)),
    }


def _runtime_config_object(checkpoint_bytes: bytes) -> dict[str, object]:
    return {
        "schema_version": RUNTIME_CONFIG_SCHEMA_VERSION,
        "entrypoint": "laya-serve",
        "provider": "laya-http",
        "engine": "laya==0.4.2",
        "source": (
            "https://github.com/NandhaKishorM/laya@" "68804629e8ccd9d616d48a40e87de9fabbeae069"
        ),
        "python": "3.11.10",
        "platform": "linux/amd64",
        "model": {
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "subfolder": MODEL_SUBFOLDER,
            "name": "multilingual",
        },
        "environment": deepcopy(ENVIRONMENT),
        "checkpoint_manifest_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
    }


def _deployment_payloads(
    *,
    checkpoint_mutation=None,
    config_mutation=None,
    checkpoint_encoder=_canonical_json,
    config_encoder=_canonical_json,
) -> tuple[dict[str, bytes], bytes, bytes]:
    checkpoint = _checkpoint_object()
    if checkpoint_mutation is not None:
        checkpoint_mutation(checkpoint)
    checkpoint_bytes = checkpoint_encoder(checkpoint)
    config = _runtime_config_object(checkpoint_bytes)
    if config_mutation is not None:
        config_mutation(config)
    config_bytes = config_encoder(config)
    payloads = _payloads()
    payloads[ARTIFACT_PATHS["runtime_config"]] = config_bytes
    payloads[ARTIFACT_PATHS["checkpoint_manifest"]] = checkpoint_bytes
    return payloads, config_bytes, checkpoint_bytes


def _deployment_snapshot(**kwargs):
    payloads, _, _ = _deployment_payloads(**kwargs)
    return _verify(_manifest(payloads=payloads), payloads)


def _load_config(payload: bytes):
    from human_feedback.runtime_deployment_metadata import validate_laya_runtime_config_bytes

    return validate_laya_runtime_config_bytes(payload)


def _load_checkpoint(payload: bytes):
    from human_feedback.runtime_deployment_metadata import (
        validate_laya_checkpoint_manifest_bytes,
    )

    return validate_laya_checkpoint_manifest_bytes(payload)


def _validate(snapshot=None):
    from human_feedback.runtime_deployment_metadata import (
        validate_laya_runtime_deployment_metadata,
    )

    actual = _deployment_snapshot() if snapshot is None else snapshot
    return validate_laya_runtime_deployment_metadata(actual)


def test_exact_runtime_config_and_checkpoint_manifest_load():
    from human_feedback.runtime_deployment_metadata import (
        CheckpointFileSpec,
        ValidatedCheckpointManifest,
        ValidatedRuntimeConfig,
    )

    _, config_bytes, checkpoint_bytes = _deployment_payloads()
    config = _load_config(config_bytes)
    checkpoint = _load_checkpoint(checkpoint_bytes)

    assert isinstance(config, ValidatedRuntimeConfig)
    assert config.schema_version == RUNTIME_CONFIG_SCHEMA_VERSION
    assert config.entrypoint == "laya-serve"
    assert config.provider == "laya-http"
    assert config.engine == "laya==0.4.2"
    assert config.python == "3.11.10"
    assert config.platform == "linux/amd64"
    assert config.model_repository == MODEL_REPOSITORY
    assert config.model_revision == MODEL_REVISION
    assert config.model_subfolder == MODEL_SUBFOLDER
    assert config.model_name == "multilingual"
    assert config.environment == tuple(sorted(ENVIRONMENT.items()))
    assert config.checkpoint_manifest_sha256 == hashlib.sha256(checkpoint_bytes).hexdigest()
    assert not hasattr(config, "runtime_identity_sha256")

    assert isinstance(checkpoint, ValidatedCheckpointManifest)
    assert checkpoint.schema_version == CHECKPOINT_SCHEMA_VERSION
    assert checkpoint.repository == MODEL_REPOSITORY
    assert checkpoint.revision == MODEL_REVISION
    assert checkpoint.subfolder == MODEL_SUBFOLDER
    assert all(isinstance(item, CheckpointFileSpec) for item in checkpoint.files)
    assert tuple(item.role for item in checkpoint.files) == tuple(
        item["role"] for item in CHECKPOINT_FILES
    )
    assert tuple(item.path for item in checkpoint.files) == tuple(
        item["path"] for item in CHECKPOINT_FILES
    )


@pytest.mark.parametrize("loader", [_load_config, _load_checkpoint])
def test_metadata_loaders_require_bytes_strict_utf8_and_json(loader):
    with pytest.raises((TypeError, ValueError), match="bytes|payload"):
        loader("not-bytes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="UTF-8|JSON|payload"):
        loader(b"\xff")
    with pytest.raises(ValueError, match="JSON|payload|object"):
        loader(b"[]")


@pytest.mark.parametrize("kind", ["config", "checkpoint"])
def test_metadata_loaders_reject_duplicate_keys_and_nonfinite_numbers(kind):
    _, config_bytes, checkpoint_bytes = _deployment_payloads()
    if kind == "config":
        duplicate = config_bytes.replace(
            b'"entrypoint":"laya-serve",',
            b'"entrypoint":"private","entrypoint":"laya-serve",',
        )
        nonfinite = config_bytes.replace(b'"entrypoint":"laya-serve"', b'"entrypoint":NaN')
        loader = _load_config
    else:
        duplicate = checkpoint_bytes.replace(
            b'"repository":"convaiinnovations/laya",',
            b'"repository":"private","repository":"convaiinnovations/laya",',
        )
        nonfinite = checkpoint_bytes.replace(b'"size_bytes":1938', b'"size_bytes":NaN')
        loader = _load_checkpoint

    with pytest.raises(ValueError, match="duplicate|key|JSON"):
        loader(duplicate)
    with pytest.raises(ValueError, match="finite|numeric|number|JSON"):
        loader(nonfinite)


@pytest.mark.parametrize("case", ["extra", "missing", "nested-extra", "wrong-type"])
def test_runtime_config_has_exact_closed_schema(case):
    _, _, checkpoint_bytes = _deployment_payloads()
    value = _runtime_config_object(checkpoint_bytes)
    if case == "extra":
        value["private_extra"] = "forbidden"
    elif case == "missing":
        value.pop("platform")
    elif case == "nested-extra":
        value["model"]["private_extra"] = "forbidden"  # type: ignore[index]
    else:
        value["environment"] = ["not", "an", "object"]

    with pytest.raises((TypeError, ValueError), match="config|field|key|schema|environment"):
        _load_config(_canonical_json(value))


@pytest.mark.parametrize("case", ["extra", "missing", "file-extra", "wrong-type"])
def test_checkpoint_manifest_has_exact_closed_schema(case):
    value = _checkpoint_object()
    if case == "extra":
        value["private_extra"] = "forbidden"
    elif case == "missing":
        value.pop("revision")
    elif case == "file-extra":
        value["files"][0]["private_extra"] = "forbidden"  # type: ignore[index]
    else:
        value["files"] = "not-an-array"

    with pytest.raises((TypeError, ValueError), match="checkpoint|file|field|key|schema|array"):
        _load_checkpoint(_canonical_json(value))


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("entrypoint", "other-entrypoint"),
        ("provider", "other-provider"),
        ("engine", "laya==0.4.3"),
        ("source", "https://example.invalid/laya"),
        ("python", "3.12.0"),
        ("platform", "linux/arm64"),
        ("schema_version", "other-schema"),
    ],
)
def test_runtime_config_exact_runtime_fields_are_pinned(field, invalid):
    _, _, checkpoint_bytes = _deployment_payloads()
    value = _runtime_config_object(checkpoint_bytes)
    value[field] = invalid

    with pytest.raises(ValueError, match="config|runtime|entrypoint|provider|engine|source"):
        _load_config(_canonical_json(value))


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("repository", "other/repository"),
        ("revision", "a" * 40),
        ("subfolder", "other"),
        ("name", "other"),
    ],
)
def test_runtime_config_exact_model_identity_is_pinned(field, invalid):
    _, _, checkpoint_bytes = _deployment_payloads()
    value = _runtime_config_object(checkpoint_bytes)
    value["model"][field] = invalid  # type: ignore[index]

    with pytest.raises(ValueError, match="model|repository|revision|subfolder|name"):
        _load_config(_canonical_json(value))


@pytest.mark.parametrize("case", ["missing", "extra", "changed", "secret", "url"])
def test_runtime_config_environment_is_exact_and_contains_no_extensions(case):
    _, _, checkpoint_bytes = _deployment_payloads()
    value = _runtime_config_object(checkpoint_bytes)
    environment = value["environment"]
    assert isinstance(environment, dict)
    if case == "missing":
        environment.pop("HF_HUB_OFFLINE")
    elif case == "extra":
        environment["EXTRA"] = "1"
    elif case == "changed":
        environment["LAYA_DEVICE"] = "cuda"
    elif case == "secret":
        environment["HF_TOKEN"] = "private-secret"
    else:
        environment["MODEL_URL"] = "https://example.invalid/private"

    with pytest.raises(ValueError, match="environment|variable|key|exact") as error:
        _load_config(_canonical_json(value))

    assert "private-secret" not in str(error.value)
    assert "example.invalid" not in str(error.value)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("repository", "other/repository"),
        ("revision", "a" * 40),
        ("subfolder", "other"),
        ("schema_version", "other-schema"),
    ],
)
def test_checkpoint_manifest_exact_identity_is_pinned(field, invalid):
    value = _checkpoint_object()
    value[field] = invalid

    with pytest.raises(ValueError, match="checkpoint|repository|revision|subfolder|schema"):
        _load_checkpoint(_canonical_json(value))


@pytest.mark.parametrize("field", ["role", "path", "sha256", "size_bytes"])
def test_each_checkpoint_file_field_is_exact(field):
    value = _checkpoint_object()
    file_spec = value["files"][2]  # type: ignore[index]
    if field == "size_bytes":
        file_spec[field] += 1
    elif field == "sha256":
        file_spec[field] = "a" * 64
    else:
        file_spec[field] = f"other-{field}"

    with pytest.raises(ValueError, match="checkpoint|file|role|path|digest|size"):
        _load_checkpoint(_canonical_json(value))


@pytest.mark.parametrize("case", ["missing", "additional", "duplicate"])
def test_checkpoint_requires_each_exact_file_role_once(case):
    value = _checkpoint_object()
    files = value["files"]
    assert isinstance(files, list)
    if case == "missing":
        files.pop()
    elif case == "additional":
        files.append(deepcopy(files[-1]))
        files[-1]["role"] = "private-extra"
    else:
        files[-1] = deepcopy(files[0])

    with pytest.raises(ValueError, match="checkpoint|file|role|duplicate|exact"):
        _load_checkpoint(_canonical_json(value))


def test_checkpoint_file_input_order_is_normalized_canonically():
    value = _checkpoint_object()
    value["files"] = list(reversed(value["files"]))  # type: ignore[arg-type]

    checkpoint = _load_checkpoint(_canonical_json(value))

    assert tuple(item.role for item in checkpoint.files) == tuple(
        item["role"] for item in CHECKPOINT_FILES
    )


def test_checkpoint_sizes_are_positive_plain_integers_not_booleans():
    for invalid in (True, False, 0, -1, 1.5):
        value = _checkpoint_object()
        value["files"][0]["size_bytes"] = invalid  # type: ignore[index]
        with pytest.raises((TypeError, ValueError), match="size|integer|checkpoint"):
            _load_checkpoint(_canonical_json(value))


def test_runtime_config_checkpoint_digest_is_exact_lowercase_non_null_sha256():
    _, _, checkpoint_bytes = _deployment_payloads()
    for invalid in ("0" * 64, "A" * 64, "a" * 63, True):
        value = _runtime_config_object(checkpoint_bytes)
        value["checkpoint_manifest_sha256"] = invalid
        with pytest.raises((TypeError, ValueError), match="checkpoint|digest|SHA-256"):
            _load_config(_canonical_json(value))


def test_deployment_combinator_uses_only_captured_snapshot_bytes():
    from human_feedback.runtime_deployment_metadata import (
        LayaRuntimeDeploymentEvidence,
        validate_laya_runtime_deployment_metadata,
    )

    snapshot = _deployment_snapshot()
    evidence = _validate(snapshot)

    assert isinstance(evidence, LayaRuntimeDeploymentEvidence)
    assert evidence.snapshot is snapshot
    assert evidence.runtime_identity == snapshot.runtime_identity
    assert evidence.runtime_config.provider == snapshot.manifest.provider
    assert evidence.runtime_config.engine == snapshot.manifest.engine
    assert evidence.runtime_config.source == snapshot.manifest.source
    assert evidence.runtime_config.python == snapshot.manifest.python
    assert evidence.runtime_config.platform == snapshot.manifest.platform
    assert (
        evidence.runtime_config.checkpoint_manifest_sha256
        == hashlib.sha256(
            next(
                artifact.content
                for artifact in snapshot.artifacts
                if artifact.spec.kind == "checkpoint_manifest"
            )
        ).hexdigest()
    )
    with pytest.raises(TypeError):
        validate_laya_runtime_deployment_metadata(snapshot, b"substitute")  # type: ignore[call-arg]
    with pytest.raises((TypeError, ValueError), match="snapshot|bundle"):
        _validate(snapshot.artifacts)


def test_deployment_combinator_rejects_cross_link_and_runtime_mismatches():
    mismatched_digest = _deployment_snapshot(
        config_mutation=lambda value: value.update(checkpoint_manifest_sha256="a" * 64)
    )
    mismatched_model = _deployment_snapshot(
        checkpoint_mutation=lambda value: value.update(revision="a" * 40)
    )
    mismatched_runtime = _deployment_snapshot(
        config_mutation=lambda value: value.update(platform="linux/arm64")
    )

    for snapshot in (mismatched_digest, mismatched_model, mismatched_runtime):
        with pytest.raises(ValueError, match="deployment|runtime|checkpoint|model|metadata"):
            _validate(snapshot)


def test_deployment_metadata_types_are_frozen_slotted_and_factory_sealed():
    evidence = _validate()
    values = (
        evidence,
        evidence.runtime_config,
        evidence.checkpoint_manifest,
        evidence.checkpoint_manifest.files[0],
    )

    assert all(is_dataclass(value) for value in values)
    assert all(not hasattr(value, "__dict__") for value in values)
    with pytest.raises(FrozenInstanceError):
        evidence.schema_version = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        evidence.runtime_config.entrypoint = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        evidence.checkpoint_manifest.schema_version = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        evidence.checkpoint_manifest.files[0].role = "changed"  # type: ignore[misc]
    with pytest.raises((TypeError, ValueError)):
        replace(evidence.runtime_config, entrypoint=evidence.runtime_config.entrypoint)
    with pytest.raises((TypeError, ValueError)):
        replace(evidence.checkpoint_manifest, files=evidence.checkpoint_manifest.files)
    with pytest.raises((TypeError, ValueError)):
        replace(evidence, snapshot=evidence.snapshot)
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|valid"):
        type(evidence.runtime_config)(
            schema_version=evidence.runtime_config.schema_version,
            entrypoint=evidence.runtime_config.entrypoint,
            provider=evidence.runtime_config.provider,
            engine=evidence.runtime_config.engine,
            source=evidence.runtime_config.source,
            python=evidence.runtime_config.python,
            platform=evidence.runtime_config.platform,
            model_repository=evidence.runtime_config.model_repository,
            model_revision=evidence.runtime_config.model_revision,
            model_subfolder=evidence.runtime_config.model_subfolder,
            model_name=evidence.runtime_config.model_name,
            environment=evidence.runtime_config.environment,
            checkpoint_manifest_sha256=evidence.runtime_config.checkpoint_manifest_sha256,
        )
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|valid"):
        type(evidence.checkpoint_manifest)(
            schema_version=evidence.checkpoint_manifest.schema_version,
            repository=evidence.checkpoint_manifest.repository,
            revision=evidence.checkpoint_manifest.revision,
            subfolder=evidence.checkpoint_manifest.subfolder,
            files=evidence.checkpoint_manifest.files,
        )
    checkpoint_file = evidence.checkpoint_manifest.files[0]
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|valid"):
        type(checkpoint_file)(
            role=checkpoint_file.role,
            path=checkpoint_file.path,
            sha256=checkpoint_file.sha256,
            size_bytes=checkpoint_file.size_bytes,
        )
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|valid"):
        type(evidence)(
            schema_version=evidence.schema_version,
            snapshot=evidence.snapshot,
            runtime_config=evidence.runtime_config,
            checkpoint_manifest=evidence.checkpoint_manifest,
            runtime_identity=evidence.runtime_identity,
        )


def test_deployment_evidence_flags_make_only_semantic_claims():
    evidence = _validate()
    expected = {
        "artifact_integrity_verified": True,
        "runtime_config_semantics_verified": True,
        "checkpoint_manifest_semantics_verified": True,
        "lock_verified": False,
        "sbom_verified": False,
        "lock_sbom_consistent": False,
        "checkpoint_bytes_verified": False,
        "oci_bytes_verified": False,
        "oci_manifest_semantics_verified": False,
        "runtime_materialized": False,
        "origin_verified": False,
        "executor_available": False,
        "inference_executed": False,
    }

    for field, expected_value in expected.items():
        assert getattr(evidence, field) is expected_value
        with pytest.raises((TypeError, ValueError)):
            replace(evidence, **{field: not expected_value})


def test_deployment_repr_errors_and_public_summary_hide_private_metadata():
    from human_feedback.runtime_deployment_metadata import (
        canonical_laya_runtime_deployment_summary_bytes,
    )

    payloads, config_bytes, checkpoint_bytes = _deployment_payloads()
    evidence = _validate(_verify(_manifest(payloads=payloads), payloads))
    summary = canonical_laya_runtime_deployment_summary_bytes(evidence)
    rendered = (
        repr(evidence)
        + repr(evidence.runtime_config)
        + repr(evidence.checkpoint_manifest)
        + repr(evidence.checkpoint_manifest.files)
    )
    decoded = json.loads(summary)
    forbidden_text = {
        config_bytes.decode("ascii"),
        checkpoint_bytes.decode("ascii"),
        *ENVIRONMENT.keys(),
        *ENVIRONMENT.values(),
        *(item["path"] for item in CHECKPOINT_FILES),
        *(item["sha256"] for item in CHECKPOINT_FILES),
        hashlib.sha256(checkpoint_bytes).hexdigest(),
    }

    assert decoded == {
        "artifact_integrity_verified": True,
        "checkpoint_bytes_verified": False,
        "checkpoint_manifest_semantics_verified": True,
        "executor_available": False,
        "inference_executed": False,
        "lock_sbom_consistent": False,
        "lock_verified": False,
        "oci_bytes_verified": False,
        "oci_manifest_semantics_verified": False,
        "origin_verified": False,
        "runtime_config_semantics_verified": True,
        "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
        "runtime_identity_sha256": evidence.runtime_identity.sha256,
        "runtime_materialized": False,
        "sbom_verified": False,
        "schema_version": DEPLOYMENT_SCHEMA_VERSION,
    }
    for value in forbidden_text:
        assert value not in rendered
        assert value.encode("ascii") not in summary

    invalid = _runtime_config_object(checkpoint_bytes)
    invalid["environment"]["PRIVATE_TOKEN"] = "private-secret"  # type: ignore[index]
    with pytest.raises(ValueError) as error:
        _load_config(_canonical_json(invalid))
    assert "PRIVATE_TOKEN" not in str(error.value)
    assert "private-secret" not in str(error.value)


def test_deployment_summary_is_canonical_and_rejects_unvalidated_input():
    from human_feedback.runtime_deployment_metadata import (
        canonical_laya_runtime_deployment_summary_bytes,
    )

    evidence = _validate()
    first = canonical_laya_runtime_deployment_summary_bytes(evidence)
    second = canonical_laya_runtime_deployment_summary_bytes(evidence)

    assert first == second
    assert first == _canonical_json(json.loads(first))
    with pytest.raises((TypeError, ValueError), match="deployment|evidence|validated"):
        canonical_laya_runtime_deployment_summary_bytes(evidence.snapshot)


def test_pr16_bundle_summary_and_pr14_execution_golden_remain_unchanged(tmp_path):
    from human_feedback.evaluation_execution import (
        canonical_loso_execution_summary_bytes,
        validate_loso_prediction_set,
    )
    from human_feedback.runtime_bundle import canonical_laya_runtime_bundle_summary_bytes
    from tests.test_laya_evaluation_execution import _contract, _predictions
    from tests.test_laya_runtime_identity import GOLDEN_EXECUTION_SUMMARY

    snapshot = _deployment_snapshot()
    before = canonical_laya_runtime_bundle_summary_bytes(snapshot)
    _validate(snapshot)
    after = canonical_laya_runtime_bundle_summary_bytes(snapshot)
    contract, _ = _contract(tmp_path)
    execution = validate_loso_prediction_set(contract, _predictions(contract))

    assert before == after
    assert json.loads(after)["runtime_config_semantics_verified"] is False
    assert json.loads(after)["checkpoint_manifest_semantics_verified"] is False
    assert canonical_loso_execution_summary_bytes(execution) == GOLDEN_EXECUTION_SUMMARY


def test_deployment_metadata_implementation_is_pure_and_isolated():
    from human_feedback import runtime_deployment_metadata

    source_path = Path(runtime_deployment_metadata.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    forbidden = (
        "subprocess",
        "requests",
        "httpx",
        "docker",
        "socket",
        "import os",
        "pathlib",
        "Path(",
        "open(",
        "read_bytes",
        "write_bytes",
        "offline_readiness",
        "experiment_runner",
        "backend",
        "adapters",
        "runners",
    )
    allowed_project_modules = {
        "human_feedback.runtime_bundle",
        "human_feedback.runtime_identity",
        "runtime_bundle",
        "runtime_identity",
    }
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if name.startswith("human_feedback") and name not in allowed_project_modules:
                violations.append(name)
            elif (
                name
                and name not in allowed_project_modules
                and name.split(".", 1)[0] not in sys.stdlib_module_names
            ):
                violations.append(name)

    assert [token for token in forbidden if token in source] == []
    assert violations == []


def test_deployment_metadata_is_not_imported_by_operational_flows():
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
            if "human_feedback.runtime_deployment_metadata" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(repository).as_posix())
    for path in files:
        if "human_feedback.runtime_deployment_metadata" in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(repository).as_posix())

    assert offenders == []
