import ast
import hashlib
import json
import traceback
from copy import deepcopy
from dataclasses import FrozenInstanceError, is_dataclass, replace
from pathlib import Path

import pytest

FIXTURE_SIZE_BYTES = 3_166
FIXTURE_SHA256 = "7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0"
SEMANTICS_SHA256 = "e8b3c42b7698c4e821abbb6dca21e3226c8eca59d62983c2ba7ad0b1010539e5"
MAX_OCI_MANIFEST_BYTES = 64 * 1024
MAX_OCI_JSON_DEPTH = 32
MAX_OCI_STRING_LENGTH = 4_096
MAX_OCI_LAYERS = 128
MAX_OCI_ANNOTATIONS = 64
OCI_EVIDENCE_SCHEMA_VERSION = "laya-runtime-oci-evidence-v1"
MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"
LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
CONFIG = (
    CONFIG_MEDIA_TYPE,
    "sha256:bdd27ffe0d14dd637985f09bcdf461e58a64348829a4b3ad3cb7886ff56e20c5",
    10_261,
)
LAYERS = (
    ("sha256:bc0965b23a04fe7f2d9fb20f597008fcf89891de1c705ffc1c80483a1f098e4f", 28_231_580),
    ("sha256:c58b365c3bcb57c930511e3fef962d15491ef2daba1e111fb5a6b41dbdecfc6b", 3_317_301),
    ("sha256:3bc3f72291794502343f023ab10455e459897b13a73f38b6b56cf266dccb7ec5", 16_202_769),
    ("sha256:42dacf6a4601de71542906f1be2bca5a78b8f430479b260a7097b9870498af69", 251),
    ("sha256:418d9aeceb23d76e9191b40d18f9c73816dc849ef0e1111a42343b73c8ccc51c", 21_573_096),
    ("sha256:ce65de5ef47521f33f7eb5bb76b05d5ff9c5a562e110b077449ff3af802803df", 31_693_638),
    ("sha256:eb0f362469da4169812e6a645b36eca3678d6aaf06acb0297850b2c525692398", 11_510),
    ("sha256:4f4fb700ef54461cfa02571ae0db9a0dc1e0cdb5577484a6d75e68dc38e8acc1", 32),
    ("sha256:890fbe6d21f33111795ef040fe123b712444c40bc1f4e93a940a8baf9a93d339", 511_506_914),
    ("sha256:f3d008f925e78af5c67f1e8b54aead83de30df814e105ff93e12f02c0d515c14", 19_739),
)
ANNOTATIONS = {
    "org.aai-hydric.runtime.checkpoint-manifest.sha256": (
        "e54ad4cf767dd653c0703f3671e5317a5dca18c351bee2ab0b7943b5472900bf"
    ),
    "org.aai-hydric.runtime.config.sha256": (
        "9a14323b31c463add7188331ce2c98bb3afbd491e15d06b1f98838a917454b5f"
    ),
    "org.aai-hydric.runtime.sbom.sha256": (
        "f2fde1a342990e3b5b4d74d4930bf37f6d2229768b509a27f34edffc009a03b2"
    ),
    "org.aai-hydric.runtime.uv-lock.sha256": (
        "e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526"
    ),
    "org.opencontainers.image.base.digest": (
        "sha256:840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e"
    ),
    "org.opencontainers.image.base.name": "docker.io/library/python:3.11.10-slim-bookworm",
    "org.opencontainers.image.licenses": "Apache-2.0",
    "org.opencontainers.image.revision": "68804629e8ccd9d616d48a40e87de9fabbeae069",
    "org.opencontainers.image.source": "https://github.com/NandhaKishorM/laya",
    "org.opencontainers.image.version": "0.4.2",
}
MUTATED_ANNOTATION_VALUES = {
    "org.aai-hydric.runtime.checkpoint-manifest.sha256": "a" * 64,
    "org.aai-hydric.runtime.config.sha256": "a" * 64,
    "org.aai-hydric.runtime.sbom.sha256": "a" * 64,
    "org.aai-hydric.runtime.uv-lock.sha256": "a" * 64,
    "org.opencontainers.image.base.digest": "sha256:" + "a" * 64,
    "org.opencontainers.image.base.name": "docker.io/library/python:3.11.11-slim-bookworm",
    "org.opencontainers.image.licenses": "MIT",
    "org.opencontainers.image.revision": "a" * 40,
    "org.opencontainers.image.source": "https://github.com/NandhaKishorM/laya-other",
    "org.opencontainers.image.version": "0.4.3",
}


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "laya" / "runtime_oci" / "oci-manifest.json"


def _fixture_bytes() -> bytes:
    return _fixture_path().read_bytes()


def _fixture_object() -> dict[str, object]:
    return json.loads(_fixture_bytes())


def _canonical_semantics_sha256(value: dict[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _encoded(value: dict[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode(
        "ascii"
    )


def _validate(payload: bytes | None = None):
    from human_feedback.runtime_oci_metadata import validate_laya_oci_manifest_bytes

    return validate_laya_oci_manifest_bytes(_fixture_bytes() if payload is None else payload)


def _validate_parsed(monkeypatch, value: object):
    from human_feedback import runtime_oci_metadata as module

    monkeypatch.setattr(module.json, "loads", lambda _text: value)
    return module.validate_laya_oci_manifest_bytes(b'{"synthetic":"bounded"}')


def _oci_snapshot(
    *,
    oci_payload: bytes | None = None,
    payload_mutation=None,
    manifest_mutation=None,
):
    from tests.test_laya_runtime_artifact_integrity import ARTIFACT_PATHS, _manifest, _verify
    from tests.test_laya_runtime_dependency_metadata import (
        _fixture_bytes as dependency_lock_bytes,
    )
    from tests.test_laya_runtime_dependency_metadata import (
        _sbom_fixture_bytes,
    )
    from tests.test_laya_runtime_deployment_metadata import _deployment_payloads

    payloads, _, _ = _deployment_payloads()
    payloads[ARTIFACT_PATHS["dependency_lock"]] = dependency_lock_bytes()
    payloads[ARTIFACT_PATHS["sbom"]] = _sbom_fixture_bytes()
    payloads[ARTIFACT_PATHS["oci_manifest"]] = (
        _fixture_bytes() if oci_payload is None else oci_payload
    )
    if payload_mutation is not None:
        payload_mutation(payloads)

    def mutate_manifest(value):
        value["base_image_ref"] = (
            "docker.io/library/python@sha256:"
            "840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e"
        )
        if manifest_mutation is not None:
            manifest_mutation(value)

    manifest = _manifest(payloads=payloads, mutation=mutate_manifest)
    return _verify(manifest, payloads)


def _validate_oci_evidence(snapshot=None):
    from human_feedback.runtime_oci_metadata import validate_laya_runtime_oci_metadata

    actual = _oci_snapshot() if snapshot is None else snapshot
    return validate_laya_runtime_oci_metadata(actual)


def _captured_payload(snapshot, kind: str) -> bytes:
    return next(artifact.content for artifact in snapshot.artifacts if artifact.spec.kind == kind)


def test_committed_oci_manifest_fixture_is_exact_captured_local_profile_bytes():
    payload = _fixture_bytes()
    value = _fixture_object()

    assert len(payload) == FIXTURE_SIZE_BYTES
    assert hashlib.sha256(payload).hexdigest() == FIXTURE_SHA256
    assert _canonical_semantics_sha256(value) == SEMANTICS_SHA256
    assert len(value["layers"]) == 10
    assert len(value["annotations"]) == 10


def test_exact_oci_manifest_profile_loads_with_ordered_layers():
    from human_feedback.runtime_oci_metadata import ValidatedLayaOciManifest

    manifest = _validate()

    assert isinstance(manifest, ValidatedLayaOciManifest)
    assert manifest.schema_version == 2
    assert manifest.media_type == MANIFEST_MEDIA_TYPE
    assert (
        manifest.config.media_type,
        manifest.config.digest,
        manifest.config.size_bytes,
    ) == CONFIG
    assert tuple(
        (layer.media_type, layer.digest, layer.size_bytes) for layer in manifest.layers
    ) == tuple((LAYER_MEDIA_TYPE, digest, size) for digest, size in LAYERS)
    assert manifest.annotations == tuple(sorted(ANNOTATIONS.items()))
    assert manifest.semantics_sha256 == SEMANTICS_SHA256


def test_descriptor_digests_are_unique_and_config_is_disjoint_from_layers():
    manifest = _validate()
    layer_digests = tuple(layer.digest for layer in manifest.layers)

    assert len(layer_digests) == len(set(layer_digests)) == 10
    assert manifest.config.digest not in layer_digests


def test_validator_requires_bytes_strict_utf8_and_strict_json():
    with pytest.raises((TypeError, ValueError), match="bytes|payload"):
        _validate("not-bytes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="UTF-8|JSON|payload"):
        _validate(b"\xff")
    with pytest.raises(ValueError, match="JSON|payload"):
        _validate(b'{"schemaVersion":[')
    duplicate = _fixture_bytes().replace(
        b'"schemaVersion": 2,',
        b'"schemaVersion": 1, "schemaVersion": 2,',
        1,
    )
    with pytest.raises(ValueError, match="duplicate|JSON|payload"):
        _validate(duplicate)
    nonfinite = _fixture_bytes().replace(b'"schemaVersion": 2', b'"schemaVersion": NaN', 1)
    with pytest.raises(ValueError, match="finite|JSON|number|payload"):
        _validate(nonfinite)


def test_manifest_size_cap_is_public_and_checked_before_json_parser(monkeypatch):
    from human_feedback import runtime_oci_metadata as module

    assert module.MAX_OCI_MANIFEST_BYTES == MAX_OCI_MANIFEST_BYTES
    monkeypatch.setattr(
        module.json,
        "loads",
        lambda _text: pytest.fail("JSON parser must not run beyond the byte cap"),
    )
    with pytest.raises(ValueError, match="size|large|limit|payload"):
        module.validate_laya_oci_manifest_bytes(b"x" * (MAX_OCI_MANIFEST_BYTES + 1))


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("MAX_OCI_JSON_DEPTH", MAX_OCI_JSON_DEPTH),
        ("MAX_OCI_STRING_LENGTH", MAX_OCI_STRING_LENGTH),
        ("MAX_OCI_LAYERS", MAX_OCI_LAYERS),
        ("MAX_OCI_ANNOTATIONS", MAX_OCI_ANNOTATIONS),
    ],
)
def test_manifest_structural_caps_are_public(name, expected):
    from human_feedback import runtime_oci_metadata as module

    assert getattr(module, name) == expected


def test_layer_cardinality_cap_precedes_descriptor_parsing(monkeypatch):
    from human_feedback import runtime_oci_metadata as module

    value = _fixture_object()
    value["layers"] = [deepcopy(value["layers"][0]) for _ in range(MAX_OCI_LAYERS + 1)]
    monkeypatch.setattr(module.json, "loads", lambda _text: value)
    monkeypatch.setattr(
        module,
        "_parse_descriptor",
        lambda *_args, **_kwargs: pytest.fail("descriptor parser must not run beyond cap"),
    )
    with pytest.raises(ValueError, match="layer|cardinality|limit"):
        module.validate_laya_oci_manifest_bytes(b'{"synthetic":"bounded"}')


@pytest.mark.parametrize("case", ["depth", "string", "annotations"])
def test_depth_string_and_annotation_caps_fail_closed(case, monkeypatch):
    value = _fixture_object()
    if case == "depth":
        nested: object = "leaf"
        for _ in range(MAX_OCI_JSON_DEPTH + 1):
            nested = {"private": nested}
        value["private"] = nested
    elif case == "string":
        value["annotations"]["private"] = "x" * (MAX_OCI_STRING_LENGTH + 1)
    else:
        value["annotations"] = {
            f"private-{index}": "value" for index in range(MAX_OCI_ANNOTATIONS + 1)
        }

    with pytest.raises(ValueError, match="depth|string|annotation|limit|manifest"):
        _validate_parsed(monkeypatch, value)


@pytest.mark.parametrize("field", ["schemaVersion", "mediaType", "config", "layers", "annotations"])
def test_every_top_level_field_is_required(field):
    value = _fixture_object()
    value.pop(field)

    with pytest.raises(ValueError, match="manifest|field|exact"):
        _validate(_encoded(value))


def test_unknown_top_level_fields_are_rejected():
    value = _fixture_object()
    value["private"] = "forbidden"

    with pytest.raises(ValueError, match="manifest|field|exact"):
        _validate(_encoded(value))


@pytest.mark.parametrize("field", ["mediaType", "digest", "size"])
@pytest.mark.parametrize("case", ["missing", "unknown", "wrong-type"])
def test_config_descriptor_fields_and_types_are_exact(field, case):
    value = _fixture_object()
    config = value["config"]
    if case == "missing":
        config.pop(field)
    elif case == "unknown":
        config["private"] = "forbidden"
    elif field == "size":
        config[field] = True
    else:
        config[field] = 7

    with pytest.raises((TypeError, ValueError), match="config|descriptor|field|type|size"):
        _validate(_encoded(value))


@pytest.mark.parametrize("field", ["mediaType", "digest", "size"])
@pytest.mark.parametrize("case", ["missing", "unknown", "wrong-type"])
def test_layer_descriptor_fields_and_types_are_exact(field, case):
    value = _fixture_object()
    layer = value["layers"][0]
    if case == "missing":
        layer.pop(field)
    elif case == "unknown":
        layer["private"] = "forbidden"
    elif field == "size":
        layer[field] = False
    else:
        layer[field] = 7

    with pytest.raises((TypeError, ValueError), match="layer|descriptor|field|type|size"):
        _validate(_encoded(value))


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("schemaVersion", 1),
        ("schemaVersion", True),
        ("mediaType", "application/json"),
    ],
)
def test_manifest_schema_and_media_type_are_exact(field, invalid):
    value = _fixture_object()
    value[field] = invalid
    with pytest.raises((TypeError, ValueError), match="schema|media|manifest|profile"):
        _validate(_encoded(value))


@pytest.mark.parametrize("target", ["config", "layer"])
@pytest.mark.parametrize("case", ["media", "digest", "size"])
def test_descriptor_profile_values_are_exact(target, case):
    value = _fixture_object()
    descriptor = value["config"] if target == "config" else value["layers"][0]
    if case == "media":
        descriptor["mediaType"] = "application/octet-stream"
    elif case == "digest":
        descriptor["digest"] = "sha256:" + "f" * 64
    else:
        descriptor["size"] += 1

    with pytest.raises(ValueError, match="descriptor|config|layer|profile|exact"):
        _validate(_encoded(value))


@pytest.mark.parametrize("layer_index", range(10))
@pytest.mark.parametrize("field", ["mediaType", "digest", "size"])
def test_every_ordered_layer_descriptor_field_is_pinned(layer_index, field):
    value = _fixture_object()
    descriptor = value["layers"][layer_index]
    if field == "mediaType":
        descriptor[field] = "application/vnd.oci.image.layer.v1.tar+zstd"
    elif field == "digest":
        descriptor[field] = "sha256:" + "a" * 64
    else:
        descriptor[field] += 1

    with pytest.raises(ValueError, match="layer|descriptor|order|profile|exact"):
        _validate(_encoded(value))


@pytest.mark.parametrize("case", ["duplicate", "config-overlap", "reordered"])
def test_layer_order_cardinality_and_identity_are_exact(case):
    value = _fixture_object()
    if case == "duplicate":
        value["layers"][1] = deepcopy(value["layers"][0])
    elif case == "config-overlap":
        value["layers"][0]["digest"] = value["config"]["digest"]
    else:
        value["layers"].reverse()

    with pytest.raises(ValueError, match="layer|digest|order|profile|exact"):
        _validate(_encoded(value))


@pytest.mark.parametrize("case", ["missing", "extra", "key", "value"])
def test_annotations_are_an_exact_closed_crosslink_profile(case):
    value = _fixture_object()
    annotations = value["annotations"]
    first_key = next(iter(annotations))
    if case == "missing":
        annotations.pop(first_key)
    elif case == "extra":
        annotations["private.extra"] = "forbidden"
    elif case == "key":
        annotations["private.renamed"] = annotations.pop(first_key)
    else:
        annotations[first_key] = "f" * 64

    with pytest.raises(ValueError, match="annotation|crosslink|profile|exact"):
        _validate(_encoded(value))


@pytest.mark.parametrize("annotation_key", tuple(ANNOTATIONS))
@pytest.mark.parametrize("mutation", ["value", "rename", "missing"])
def test_every_annotation_key_and_value_is_individually_pinned(annotation_key, mutation):
    value = _fixture_object()
    annotations = value["annotations"]
    if mutation == "value":
        annotations[annotation_key] = MUTATED_ANNOTATION_VALUES[annotation_key]
    elif mutation == "rename":
        annotations[f"{annotation_key}.renamed"] = annotations.pop(annotation_key)
    else:
        annotations.pop(annotation_key)

    with pytest.raises(ValueError, match="annotation|crosslink|profile|exact"):
        _validate(_encoded(value))


def test_annotation_profile_rejects_an_additional_well_formed_entry():
    value = _fixture_object()
    value["annotations"]["org.opencontainers.image.title"] = "laya-runtime"

    with pytest.raises(ValueError, match="annotation|crosslink|profile|exact"):
        _validate(_encoded(value))


def test_json_object_key_order_and_whitespace_are_semantically_canonical():
    exact = _validate()
    value = _fixture_object()
    reordered = dict(reversed(tuple(value.items())))
    variant = json.dumps(reordered, indent=None, separators=(",", ":")).encode("ascii")

    assert variant != _fixture_bytes()
    assert hashlib.sha256(variant).hexdigest() != FIXTURE_SHA256
    assert _validate(variant) == exact
    assert _validate(variant).semantics_sha256 == SEMANTICS_SHA256


def test_validated_manifest_and_descriptors_are_frozen_slotted_sealed_and_opaque():
    manifest = _validate()
    values = (manifest, manifest.config, *manifest.layers)

    assert all(is_dataclass(value) for value in values)
    assert all(not hasattr(value, "__dict__") for value in values)
    with pytest.raises(FrozenInstanceError):
        manifest.schema_version = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        manifest.config.digest = "changed"  # type: ignore[misc]
    for value in values:
        with pytest.raises((TypeError, ValueError)):
            replace(value)
    rendered = repr(manifest) + repr(manifest.config) + repr(manifest.layers)
    assert FIXTURE_SHA256 not in rendered
    assert SEMANTICS_SHA256 not in rendered
    assert CONFIG[1] not in rendered
    assert all(digest not in rendered for digest, _size in LAYERS)
    assert all(key not in rendered and value not in rendered for key, value in ANNOTATIONS.items())


@pytest.mark.parametrize("case", ["utf8", "json", "depth", "annotation"])
def test_public_parser_errors_are_generic_private_and_context_suppressed(case):
    if case == "utf8":
        marker = "private-oci-utf8"
        payload = marker.encode("ascii") + b"\xff"
    elif case == "json":
        marker = "private-oci-json"
        payload = f'{{"{marker}":['.encode("ascii")
    elif case == "depth":
        marker = "private-oci-depth"
        payload = (
            b'{"private":'
            + b"[" * (MAX_OCI_JSON_DEPTH + 100)
            + f'"{marker}"'.encode("ascii")
            + b"]" * (MAX_OCI_JSON_DEPTH + 100)
            + b"}"
        )
    else:
        marker = "private-oci-annotation"
        value = _fixture_object()
        value["annotations"][marker] = "secret"
        payload = _encoded(value)

    with pytest.raises(ValueError) as captured:
        _validate(payload)

    error = captured.value
    rendered_chain = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    assert marker not in str(error)
    assert marker not in rendered_chain
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def test_oci_metadata_module_has_only_pure_stdlib_and_contract_dependencies():
    from human_feedback import runtime_oci_metadata

    source = Path(runtime_oci_metadata.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_imports = {
        "__future__",
        "dataclasses",
        "hashlib",
        "human_feedback.runtime_bundle",
        "human_feedback.runtime_identity",
        "json",
        "typing",
    }
    direct_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    from_imports = {
        (
            f"human_feedback.{alias.name}"
            if node.module in {None, "", "human_feedback"}
            else node.module
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    forbidden_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "open",
        "read_bytes",
        "read_text",
        "write_bytes",
        "write_text",
        "run",
        "Popen",
        "system",
        "socket",
        "urlopen",
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } | {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert direct_imports | from_imports <= allowed_imports
    assert called_names.isdisjoint(forbidden_calls)
    assert '"docker.io/library/python:3.11.10-slim-bookworm"' in source


def test_oci_combinator_uses_only_manifest_captured_in_exact_snapshot():
    from human_feedback.runtime_oci_metadata import (
        LayaRuntimeOciEvidence,
        validate_laya_runtime_oci_metadata,
    )

    snapshot = _oci_snapshot()
    evidence = _validate_oci_evidence(snapshot)

    assert isinstance(evidence, LayaRuntimeOciEvidence)
    assert evidence.schema_version == OCI_EVIDENCE_SCHEMA_VERSION
    assert evidence.snapshot is snapshot
    assert evidence.runtime_identity == snapshot.runtime_identity
    assert evidence.oci_manifest == _validate(_captured_payload(snapshot, "oci_manifest"))
    with pytest.raises(TypeError):
        validate_laya_runtime_oci_metadata(  # type: ignore[call-arg]
            snapshot,
            _fixture_bytes(),
        )
    with pytest.raises((TypeError, ValueError), match="snapshot|bundle"):
        validate_laya_runtime_oci_metadata(snapshot.artifacts)  # type: ignore[arg-type]


def test_oci_evidence_crosslinks_annotations_to_actual_captured_artifact_bytes():
    snapshot = _oci_snapshot()
    evidence = _validate_oci_evidence(snapshot)
    annotations = dict(evidence.oci_manifest.annotations)
    expected_artifact_links = {
        "dependency_lock": "org.aai-hydric.runtime.uv-lock.sha256",
        "sbom": "org.aai-hydric.runtime.sbom.sha256",
        "runtime_config": "org.aai-hydric.runtime.config.sha256",
        "checkpoint_manifest": "org.aai-hydric.runtime.checkpoint-manifest.sha256",
    }

    for kind, annotation in expected_artifact_links.items():
        assert (
            annotations[annotation] == hashlib.sha256(_captured_payload(snapshot, kind)).hexdigest()
        )
    assert annotations["org.opencontainers.image.source"] == snapshot.manifest.source.split("@")[0]
    assert (
        annotations["org.opencontainers.image.revision"]
        == snapshot.manifest.source.rsplit("@", 1)[1]
    )
    assert annotations["org.opencontainers.image.licenses"] == snapshot.manifest.license
    assert annotations["org.opencontainers.image.version"] == snapshot.manifest.engine.removeprefix(
        "laya=="
    )
    assert snapshot.manifest.base_image_ref == (
        "docker.io/library/python@" + annotations["org.opencontainers.image.base.digest"]
    )
    assert annotations["org.opencontainers.image.base.name"] == (
        "docker.io/library/python:3.11.10-slim-bookworm"
    )


def test_oci_aggregate_requires_exact_raw_manifest_not_only_semantic_equivalence():
    exact = _fixture_bytes()
    reordered = dict(reversed(tuple(_fixture_object().items())))
    variant = json.dumps(
        reordered,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")

    assert _validate(variant) == _validate(exact)
    assert len(variant) != FIXTURE_SIZE_BYTES
    assert hashlib.sha256(variant).hexdigest() != FIXTURE_SHA256
    snapshot = _oci_snapshot(oci_payload=variant)
    assert snapshot.artifact_integrity_verified is True

    with pytest.raises(ValueError, match="OCI|manifest|artifact|exact|byte") as captured:
        _validate_oci_evidence(snapshot)

    rendered_chain = "".join(
        traceback.TracebackException.from_exception(captured.value).format(chain=True)
    )
    assert variant.decode("ascii") not in rendered_chain
    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True


@pytest.mark.parametrize(
    "kind",
    ["dependency_lock", "sbom", "runtime_config", "checkpoint_manifest"],
)
def test_oci_aggregate_rejects_each_captured_annotation_digest_mismatch(kind):
    from tests.test_laya_runtime_artifact_integrity import ARTIFACT_PATHS

    marker = f"private-{kind}-crosslink-mismatch".encode("ascii")

    def mutate(payloads):
        payloads[ARTIFACT_PATHS[kind]] += marker

    snapshot = _oci_snapshot(payload_mutation=mutate)
    with pytest.raises(ValueError, match="OCI|annotation|digest|artifact|crosslink") as captured:
        _validate_oci_evidence(snapshot)

    rendered_chain = "".join(
        traceback.TracebackException.from_exception(captured.value).format(chain=True)
    )
    assert marker.decode("ascii") not in rendered_chain
    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True


def test_oci_aggregate_rejects_an_alternate_base_image_identity():
    snapshot = _oci_snapshot(
        manifest_mutation=lambda value: value.update(
            base_image_ref="docker.io/library/python@sha256:" + "a" * 64
        )
    )

    with pytest.raises(ValueError, match="OCI|base|image|runtime|profile"):
        _validate_oci_evidence(snapshot)


def test_oci_aggregate_rejects_missing_duplicate_proxy_and_identity_mismatch():
    from types import SimpleNamespace

    snapshot = _oci_snapshot()
    without_oci = tuple(
        artifact for artifact in snapshot.artifacts if artifact.spec.kind != "oci_manifest"
    )
    oci = next(artifact for artifact in snapshot.artifacts if artifact.spec.kind == "oci_manifest")
    candidates = (
        SimpleNamespace(
            manifest=snapshot.manifest,
            artifacts=without_oci,
            runtime_identity=snapshot.runtime_identity,
            artifact_integrity_verified=True,
        ),
        SimpleNamespace(
            manifest=snapshot.manifest,
            artifacts=(*snapshot.artifacts, oci),
            runtime_identity=snapshot.runtime_identity,
            artifact_integrity_verified=True,
        ),
        SimpleNamespace(
            manifest=snapshot.manifest,
            artifacts=snapshot.artifacts,
            runtime_identity=object(),
            artifact_integrity_verified=True,
        ),
        SimpleNamespace(
            manifest=snapshot.manifest,
            artifacts=snapshot.artifacts,
            runtime_identity=snapshot.runtime_identity,
            artifact_integrity_verified=False,
        ),
    )

    for candidate in candidates:
        with pytest.raises((TypeError, ValueError), match="snapshot|bundle|identity|integrity"):
            _validate_oci_evidence(candidate)
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct"):
        type(snapshot)(
            schema_version=snapshot.schema_version,
            manifest=snapshot.manifest,
            artifacts=snapshot.artifacts,
            runtime_identity=snapshot.runtime_identity,
        )


def test_oci_evidence_is_frozen_slotted_factory_sealed_and_private():
    evidence = _validate_oci_evidence()

    assert is_dataclass(evidence)
    assert not hasattr(evidence, "__dict__")
    with pytest.raises(FrozenInstanceError):
        evidence.oci_manifest_semantics_verified = False  # type: ignore[misc]
    with pytest.raises((TypeError, ValueError)):
        replace(evidence, snapshot=evidence.snapshot)
    with pytest.raises((TypeError, ValueError)):
        replace(evidence, oci_manifest=evidence.oci_manifest)
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|valid"):
        type(evidence)(
            schema_version=evidence.schema_version,
            snapshot=evidence.snapshot,
            oci_manifest=evidence.oci_manifest,
            runtime_identity=evidence.runtime_identity,
        )

    rendered = repr(evidence) + repr(evidence.snapshot) + repr(evidence.oci_manifest)
    assert _fixture_bytes().decode("ascii") not in rendered
    assert FIXTURE_SHA256 not in rendered
    assert CONFIG[1] not in rendered
    assert all(digest not in rendered for digest, _size in LAYERS)


def test_oci_evidence_flags_make_only_manifest_semantics_claims():
    evidence = _validate_oci_evidence()
    expected = {
        "artifact_integrity_verified": True,
        "oci_manifest_semantics_verified": True,
        "lock_verified": False,
        "sbom_verified": False,
        "lock_sbom_consistent": False,
        "runtime_config_semantics_verified": False,
        "checkpoint_manifest_semantics_verified": False,
        "checkpoint_bytes_verified": False,
        "oci_bytes_verified": False,
        "origin_verified": False,
        "runtime_materialized": False,
        "executor_available": False,
        "inference_executed": False,
    }

    for field, expected_value in expected.items():
        assert getattr(evidence, field) is expected_value
        with pytest.raises((TypeError, ValueError)):
            replace(evidence, **{field: not expected_value})


def test_oci_public_summary_is_minimal_deterministic_and_private():
    from human_feedback.runtime_oci_metadata import canonical_laya_runtime_oci_summary_bytes

    evidence = _validate_oci_evidence()
    first = canonical_laya_runtime_oci_summary_bytes(evidence)
    second = canonical_laya_runtime_oci_summary_bytes(evidence)
    decoded = json.loads(first)

    assert first == second
    assert decoded == {
        "artifact_integrity_verified": True,
        "checkpoint_bytes_verified": False,
        "checkpoint_manifest_semantics_verified": False,
        "executor_available": False,
        "inference_executed": False,
        "lock_sbom_consistent": False,
        "lock_verified": False,
        "oci_bytes_verified": False,
        "oci_manifest_semantics_verified": True,
        "origin_verified": False,
        "runtime_config_semantics_verified": False,
        "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
        "runtime_identity_sha256": evidence.runtime_identity.sha256,
        "runtime_materialized": False,
        "sbom_verified": False,
        "schema_version": OCI_EVIDENCE_SCHEMA_VERSION,
    }
    forbidden = {
        _fixture_bytes(),
        FIXTURE_SHA256.encode("ascii"),
        SEMANTICS_SHA256.encode("ascii"),
        *(digest.encode("ascii") for digest, _size in LAYERS),
        *(key.encode("ascii") for key in ANNOTATIONS),
        *(value.encode("ascii") for value in ANNOTATIONS.values()),
        *(spec.path.encode("ascii") for spec in evidence.snapshot.manifest.artifacts),
        *(spec.sha256.encode("ascii") for spec in evidence.snapshot.manifest.artifacts),
    }
    assert all(private not in first for private in forbidden)


def test_oci_validation_does_not_compose_or_mutate_prior_evidence_layers():
    from human_feedback.runtime_bundle import canonical_laya_runtime_bundle_summary_bytes
    from human_feedback.runtime_dependency_metadata import (
        canonical_laya_runtime_dependency_summary_bytes,
        validate_laya_runtime_dependency_metadata,
    )
    from human_feedback.runtime_deployment_metadata import (
        canonical_laya_runtime_deployment_summary_bytes,
        validate_laya_runtime_deployment_metadata,
    )

    snapshot = _oci_snapshot()
    dependency = validate_laya_runtime_dependency_metadata(snapshot)
    deployment = validate_laya_runtime_deployment_metadata(snapshot)
    before = (
        canonical_laya_runtime_bundle_summary_bytes(snapshot),
        canonical_laya_runtime_dependency_summary_bytes(dependency),
        canonical_laya_runtime_deployment_summary_bytes(deployment),
    )
    evidence = _validate_oci_evidence(snapshot)
    after = (
        canonical_laya_runtime_bundle_summary_bytes(snapshot),
        canonical_laya_runtime_dependency_summary_bytes(dependency),
        canonical_laya_runtime_deployment_summary_bytes(deployment),
    )

    assert after == before
    assert snapshot.oci_manifest_semantics_verified is False
    assert snapshot.lock_verified is False
    assert snapshot.sbom_verified is False
    assert evidence.lock_verified is False
    assert evidence.sbom_verified is False
    assert evidence.runtime_config_semantics_verified is False
    assert evidence.checkpoint_manifest_semantics_verified is False


def test_oci_aggregate_errors_hide_private_captured_content_and_context():
    from tests.test_laya_runtime_artifact_integrity import ARTIFACT_PATHS

    marker = b"private-oci-aggregate-secret"

    def mutate(payloads):
        payloads[ARTIFACT_PATHS["runtime_config"]] += marker

    snapshot = _oci_snapshot(payload_mutation=mutate)
    with pytest.raises(ValueError) as captured:
        _validate_oci_evidence(snapshot)

    error = captured.value
    rendered_chain = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    assert marker.decode("ascii") not in str(error)
    assert marker.decode("ascii") not in rendered_chain
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
