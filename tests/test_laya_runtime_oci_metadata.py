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


def test_committed_oci_manifest_fixture_is_exact_real_evidence():
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


def test_oci_metadata_module_is_pure_parser_only():
    from human_feedback import runtime_oci_metadata

    source = Path(runtime_oci_metadata.__file__).read_text(encoding="utf-8")
    forbidden = (
        "subprocess",
        "requests",
        "httpx",
        "docker",
        "socket",
        "pathlib",
        "Path(",
        "open(",
        "read_bytes",
        "write_bytes",
        "runtime_bundle",
        "offline_readiness",
        "experiment_runner",
        "backend",
        "adapters",
    )

    assert [token for token in forbidden if token in source] == []
