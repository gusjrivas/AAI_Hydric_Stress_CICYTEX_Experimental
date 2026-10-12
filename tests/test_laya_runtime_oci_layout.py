import ast
import hashlib
import json
import os
import traceback
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

LAYOUT_SIZE_BYTES = 30
LAYOUT_SHA256 = "18f0797eab35a4597c1e9624aa4f15fd91f6254e5538c1e0d193b2a95dd4acc6"
INDEX_SIZE_BYTES = 423
INDEX_SHA256 = "3d28b2fd93177f35031d802b830e2807253ea19838fb0386b14688a49dd75b39"
MANIFEST_SHA256 = "7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0"
MANIFEST_SIZE_BYTES = 3_166
CONFIG_SHA256 = "bdd27ffe0d14dd637985f09bcdf461e58a64348829a4b3ad3cb7886ff56e20c5"
CONFIG_SIZE_BYTES = 10_261
BLOB_TOTAL_SIZE_BYTES = 612_570_257
LAYOUT_TOTAL_SIZE_BYTES = 612_570_710
LAYOUT_PLAN_SCHEMA = "laya-oci-layout-plan-v1"
INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"
LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
MAX_OCI_LAYOUT_BYTES = 1_024
MAX_OCI_INDEX_BYTES = 64 * 1_024
MAX_OCI_CONTROL_JSON_DEPTH = 32
MAX_OCI_CONTROL_STRING_LENGTH = 256
MAX_OCI_BLOB_CHUNK_BYTES = 1_024 * 1_024
LAYOUT_PROFILE_ID = "laya-runtime-oci-layout-profile-v1"
LAYOUT_EVIDENCE_SCHEMA = "laya-runtime-oci-layout-evidence-v1"
_UNSET = object()

LAYERS = (
    ("bc0965b23a04fe7f2d9fb20f597008fcf89891de1c705ffc1c80483a1f098e4f", 28_231_580),
    ("c58b365c3bcb57c930511e3fef962d15491ef2daba1e111fb5a6b41dbdecfc6b", 3_317_301),
    ("3bc3f72291794502343f023ab10455e459897b13a73f38b6b56cf266dccb7ec5", 16_202_769),
    ("42dacf6a4601de71542906f1be2bca5a78b8f430479b260a7097b9870498af69", 251),
    ("418d9aeceb23d76e9191b40d18f9c73816dc849ef0e1111a42343b73c8ccc51c", 21_573_096),
    ("ce65de5ef47521f33f7eb5bb76b05d5ff9c5a562e110b077449ff3af802803df", 31_693_638),
    ("eb0f362469da4169812e6a645b36eca3678d6aaf06acb0297850b2c525692398", 11_510),
    ("4f4fb700ef54461cfa02571ae0db9a0dc1e0cdb5577484a6d75e68dc38e8acc1", 32),
    ("890fbe6d21f33111795ef040fe123b712444c40bc1f4e93a940a8baf9a93d339", 511_506_914),
    ("f3d008f925e78af5c67f1e8b54aead83de30df814e105ff93e12f02c0d515c14", 19_739),
)


def _fixture_path(name: str) -> Path:
    return Path(__file__).parent / "fixtures" / "laya" / "runtime_oci_layout" / name


def _layout_bytes() -> bytes:
    return _fixture_path("oci-layout").read_bytes()


def _index_bytes() -> bytes:
    return _fixture_path("index.json").read_bytes()


def _index_object() -> dict[str, object]:
    return json.loads(_index_bytes())


def _encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode(
        "ascii"
    )


def _oci_evidence():
    from tests.test_laya_runtime_oci_metadata import _validate_oci_evidence

    return _validate_oci_evidence()


def _prepare(evidence=_UNSET, layout_bytes=_UNSET, index_bytes=_UNSET):
    from human_feedback.runtime_oci_layout import prepare_laya_oci_layout_plan

    return prepare_laya_oci_layout_plan(
        _oci_evidence() if evidence is _UNSET else evidence,
        _layout_bytes() if layout_bytes is _UNSET else layout_bytes,
        _index_bytes() if index_bytes is _UNSET else index_bytes,
    )


def _captured_manifest_bytes(plan=None) -> bytes:
    actual_plan = _prepare() if plan is None else plan
    snapshot = actual_plan.oci_evidence.snapshot
    return next(
        artifact.content for artifact in snapshot.artifacts if artifact.spec.kind == "oci_manifest"
    )


def _verify_blob(plan, digest, chunks):
    from human_feedback.runtime_oci_layout import verify_laya_oci_blob_chunks

    return verify_laya_oci_blob_chunks(plan, digest, chunks)


def _verify_manifest(plan=None, chunks=_UNSET):
    actual_plan = _prepare() if plan is None else plan
    payload = _captured_manifest_bytes(actual_plan)
    actual_chunks = (payload,) if chunks is _UNSET else chunks
    return _verify_blob(actual_plan, actual_plan.blobs[0].digest, actual_chunks)


def _expected_blobs():
    yield (
        "manifest",
        f"blobs/sha256/{MANIFEST_SHA256}",
        MANIFEST_MEDIA_TYPE,
        f"sha256:{MANIFEST_SHA256}",
        MANIFEST_SIZE_BYTES,
    )
    yield (
        "config",
        f"blobs/sha256/{CONFIG_SHA256}",
        CONFIG_MEDIA_TYPE,
        f"sha256:{CONFIG_SHA256}",
        CONFIG_SIZE_BYTES,
    )
    for index, (digest, size_bytes) in enumerate(LAYERS):
        yield (
            f"layer-{index:02d}",
            f"blobs/sha256/{digest}",
            LAYER_MEDIA_TYPE,
            f"sha256:{digest}",
            size_bytes,
        )


def _assert_private_error(error: BaseException, marker: str) -> None:
    rendered = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    assert marker not in str(error)
    assert marker not in rendered
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def _uses_layout_plan_api(source: str) -> bool:
    symbols = {
        "LayaOciLayoutPlan",
        "LayaRuntimeOciLayoutEvidence",
        "VerifiedLayaOciBlob",
        "canonical_laya_runtime_oci_layout_summary_bytes",
        "finalize_laya_oci_layout_evidence",
        "prepare_laya_oci_layout_plan",
        "verify_laya_oci_blob_chunks",
    }
    module_name = "human_feedback.runtime_oci_layout"
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == module_name for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom):
            if node.module == "human_feedback" and any(
                alias.name == "runtime_oci_layout" for alias in node.names
            ):
                return True
            if node.module in {module_name, "runtime_oci_layout"} and any(
                alias.name == "*" or alias.name in symbols for alias in node.names
            ):
                return True
            if (
                node.level > 0
                and node.module in {None, "", "runtime_oci_layout"}
                and any(
                    alias.name == "runtime_oci_layout" or alias.name in symbols
                    for alias in node.names
                )
            ):
                return True
        if isinstance(node, ast.Name) and node.id in symbols:
            return True
        if isinstance(node, ast.Attribute) and node.attr in symbols:
            return True
        if isinstance(node, ast.Constant) and node.value in {module_name, *symbols}:
            return True
    return False


def test_committed_layout_control_fixtures_are_exact_captured_profile_bytes():
    assert len(_layout_bytes()) == LAYOUT_SIZE_BYTES
    assert hashlib.sha256(_layout_bytes()).hexdigest() == LAYOUT_SHA256
    assert len(_index_bytes()) == INDEX_SIZE_BYTES
    assert hashlib.sha256(_index_bytes()).hexdigest() == INDEX_SHA256
    assert _layout_bytes() == b'{"imageLayoutVersion":"1.0.0"}'


def test_layout_control_fixtures_are_protected_from_checkout_conversion():
    attributes = (Path(__file__).parents[1] / ".gitattributes").read_text(encoding="utf-8")
    assert "/tests/fixtures/laya/runtime_oci_layout/oci-layout -text" in attributes.splitlines()
    assert "/tests/fixtures/laya/runtime_oci_layout/index.json -text" in attributes.splitlines()


def test_prepare_derives_exact_closed_ordered_blob_graph_from_pr19_evidence():
    evidence = _oci_evidence()
    plan = _prepare(evidence)

    assert plan.schema_version == LAYOUT_PLAN_SCHEMA
    assert plan.oci_evidence is evidence
    assert plan.runtime_identity == evidence.runtime_identity
    assert plan.control_paths == ("oci-layout", "index.json")
    assert plan.control_file_count == 2
    assert plan.blob_count == 12
    assert plan.logical_file_count == 14
    assert plan.blob_total_size_bytes == BLOB_TOTAL_SIZE_BYTES
    assert plan.total_size_bytes == LAYOUT_TOTAL_SIZE_BYTES

    actual = tuple(
        (blob.role, blob.path, blob.media_type, blob.digest, blob.size_bytes) for blob in plan.blobs
    )
    assert actual == tuple(_expected_blobs())
    assert len({blob.path for blob in plan.blobs}) == 12
    assert len({blob.digest for blob in plan.blobs}) == 12
    assert all(
        blob.path == "blobs/sha256/" + blob.digest.removeprefix("sha256:") for blob in plan.blobs
    )


def test_prepare_binds_index_descriptor_to_the_captured_pr19_manifest():
    plan = _prepare()
    assert plan.index_manifest.media_type == MANIFEST_MEDIA_TYPE
    assert plan.index_manifest.digest == f"sha256:{MANIFEST_SHA256}"
    assert plan.index_manifest.size_bytes == MANIFEST_SIZE_BYTES
    assert plan.index_manifest is plan.blobs[0]


def test_prepare_requires_exact_profile_bytes_not_only_equivalent_json():
    original = _index_object()
    reordered = {
        "manifests": original["manifests"],
        "mediaType": original["mediaType"],
        "schemaVersion": original["schemaVersion"],
    }
    variant = _encoded(reordered) + b"\n"
    assert json.loads(variant) == original
    assert len(variant) == len(_index_bytes()) == INDEX_SIZE_BYTES
    assert hashlib.sha256(variant).hexdigest() != INDEX_SHA256

    with pytest.raises(ValueError, match="index|exact|byte|digest|profile"):
        _prepare(index_bytes=variant)

    same_size_layout = _layout_bytes().replace(b"1.0.0", b"1.0.1")
    assert len(same_size_layout) == LAYOUT_SIZE_BYTES
    assert hashlib.sha256(same_size_layout).hexdigest() != LAYOUT_SHA256
    with pytest.raises(ValueError, match="layout|version|exact|byte|profile"):
        _prepare(layout_bytes=same_size_layout)


@pytest.mark.parametrize("payload_name", ["layout", "index"])
@pytest.mark.parametrize("value", [None, "text", bytearray(b"{}"), memoryview(b"{}"), True])
def test_prepare_accepts_only_immutable_bytes_for_both_controls(payload_name, value):
    kwargs = {f"{payload_name}_bytes": value}
    with pytest.raises(TypeError, match="bytes|payload|control"):
        _prepare(**kwargs)


@pytest.mark.parametrize(
    ("payload_name", "payload", "marker"),
    [
        ("layout", b'{"private-layout-utf8":"\xff"}', "private-layout-utf8"),
        ("layout", b'{"private-layout-json":[', "private-layout-json"),
        (
            "layout",
            b'{"imageLayoutVersion":NaN,"private-layout-nonfinite":"secret"}',
            "private-layout-nonfinite",
        ),
        ("index", b'{"private-index-utf8":"\xff"}', "private-index-utf8"),
        ("index", b'{"private-index-json":[', "private-index-json"),
        (
            "index",
            b'{"schemaVersion":NaN,"private-index-nonfinite":"secret"}',
            "private-index-nonfinite",
        ),
    ],
)
def test_control_parse_errors_are_generic_private_and_context_suppressed(
    payload_name, payload, marker
):
    with pytest.raises(ValueError) as captured:
        _prepare(**{f"{payload_name}_bytes": payload})
    _assert_private_error(captured.value, marker)


@pytest.mark.parametrize(
    ("payload_name", "payload"),
    [
        (
            "layout",
            b'{"imageLayoutVersion":"1.0.0","imageLayoutVersion":"1.0.0"}',
        ),
        (
            "index",
            b'{"schemaVersion":2,"schemaVersion":2,"mediaType":"x","manifests":[]}',
        ),
    ],
)
def test_duplicate_json_keys_are_rejected(payload_name, payload):
    with pytest.raises(ValueError, match="JSON|duplicate|control|profile"):
        _prepare(**{f"{payload_name}_bytes": payload})


@pytest.mark.parametrize("payload_name", ["layout", "index"])
def test_control_json_depth_and_string_caps_are_public_and_fail_closed(payload_name):
    from human_feedback import runtime_oci_layout as module

    assert module.MAX_OCI_CONTROL_JSON_DEPTH == MAX_OCI_CONTROL_JSON_DEPTH
    assert module.MAX_OCI_CONTROL_STRING_LENGTH == MAX_OCI_CONTROL_STRING_LENGTH
    private_marker = f"private-{payload_name}-bounded-json"
    deeply_nested = (
        b'{"private":'
        + b"[" * (MAX_OCI_CONTROL_JSON_DEPTH + 100)
        + f'"{private_marker}"'.encode("ascii")
        + b"]" * (MAX_OCI_CONTROL_JSON_DEPTH + 100)
        + b"}"
    )
    long_string = _encoded({private_marker: "x" * (MAX_OCI_CONTROL_STRING_LENGTH + 1)})
    for payload in (deeply_nested, long_string):
        with pytest.raises(ValueError) as captured:
            _prepare(**{f"{payload_name}_bytes": payload})
        _assert_private_error(captured.value, private_marker)


@pytest.mark.parametrize(
    ("payload_name", "limit_name", "expected_limit"),
    [
        ("layout", "MAX_OCI_LAYOUT_BYTES", MAX_OCI_LAYOUT_BYTES),
        ("index", "MAX_OCI_INDEX_BYTES", MAX_OCI_INDEX_BYTES),
    ],
)
def test_control_caps_reject_before_json_loads(
    monkeypatch, payload_name, limit_name, expected_limit
):
    from human_feedback import runtime_oci_layout as module

    assert getattr(module, limit_name) == expected_limit
    loads_called = False

    def forbidden_loads(*_args, **_kwargs):
        nonlocal loads_called
        loads_called = True
        raise AssertionError("oversized control must fail before json.loads")

    monkeypatch.setattr(module.json, "loads", forbidden_loads)
    with pytest.raises(ValueError, match="size|limit|large|control"):
        _prepare(**{f"{payload_name}_bytes": b"x" * (expected_limit + 1)})
    assert loads_called is False


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(extra=True),
        lambda value: value.pop("imageLayoutVersion"),
        lambda value: value.update(imageLayoutVersion="1.0.1"),
        lambda value: value.update(imageLayoutVersion=1),
        lambda value: value.update(imageLayoutVersion=True),
    ],
)
def test_layout_marker_is_closed_and_exact(mutation):
    value = json.loads(_layout_bytes())
    mutation(value)
    with pytest.raises(ValueError, match="layout|version|field|profile"):
        _prepare(layout_bytes=_encoded(value))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(extra=True),
        lambda value: value.pop("schemaVersion"),
        lambda value: value.update(schemaVersion=3),
        lambda value: value.update(schemaVersion=True),
        lambda value: value.pop("mediaType"),
        lambda value: value.update(mediaType="application/json"),
        lambda value: value.pop("manifests"),
        lambda value: value.update(manifests=[]),
        lambda value: value.update(manifests=value["manifests"] * 2),
        lambda value: value.update(manifests={}),
    ],
)
def test_index_top_level_schema_is_closed_and_exact(mutation):
    value = _index_object()
    mutation(value)
    with pytest.raises(ValueError, match="index|schema|manifest|field|profile"):
        _prepare(index_bytes=_encoded(value))


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("mediaType", "application/json"),
        ("digest", "sha256:" + "a" * 64),
        ("size", 3_167),
        ("size", True),
    ],
)
def test_index_manifest_descriptor_fields_are_exact(field, replacement):
    value = _index_object()
    value["manifests"][0][field] = replacement
    with pytest.raises(ValueError, match="index|manifest|descriptor|profile|identity"):
        _prepare(index_bytes=_encoded(value))


@pytest.mark.parametrize("field", ["mediaType", "digest", "size"])
def test_index_manifest_descriptor_rejects_each_missing_field(field):
    value = _index_object()
    value["manifests"][0].pop(field)
    with pytest.raises(ValueError, match="index|manifest|descriptor|field"):
        _prepare(index_bytes=_encoded(value))


def test_index_manifest_descriptor_rejects_unknown_fields():
    value = _index_object()
    value["manifests"][0]["private-extra"] = "secret"
    with pytest.raises(ValueError, match="index|manifest|descriptor|field"):
        _prepare(index_bytes=_encoded(value))


@pytest.mark.parametrize(
    ("container", "field", "replacement"),
    [
        ("annotations", "org.opencontainers.image.created", "1970-01-01T00:00:01Z"),
        ("annotations", "org.opencontainers.image.ref.name", "laya-runtime-latest"),
        ("platform", "architecture", "arm64"),
        ("platform", "os", "windows"),
    ],
)
def test_each_index_annotation_and_platform_value_is_exact(container, field, replacement):
    value = _index_object()
    value["manifests"][0][container][field] = replacement
    with pytest.raises(ValueError, match="index|annotation|platform|profile|manifest"):
        _prepare(index_bytes=_encoded(value))


@pytest.mark.parametrize(
    ("container", "operation", "field"),
    [
        ("annotations", "missing-container", None),
        ("platform", "missing-container", None),
        ("annotations", "missing-field", "org.opencontainers.image.created"),
        ("annotations", "missing-field", "org.opencontainers.image.ref.name"),
        ("platform", "missing-field", "architecture"),
        ("platform", "missing-field", "os"),
        ("annotations", "extra-field", "private-extra"),
        ("platform", "extra-field", "private-extra"),
    ],
)
def test_index_annotation_and_platform_objects_are_closed(container, operation, field):
    value = _index_object()
    descriptor = value["manifests"][0]
    if operation == "missing-container":
        descriptor.pop(container)
    elif operation == "missing-field":
        descriptor[container].pop(field)
    else:
        descriptor[container][field] = "private-extra-value"
    with pytest.raises(ValueError, match="index|annotation|platform|field|profile"):
        _prepare(index_bytes=_encoded(value))


def test_prepare_rejects_proxy_subclass_and_mismatched_pr19_evidence():
    evidence = _oci_evidence()
    proxy = SimpleNamespace(
        schema_version=evidence.schema_version,
        snapshot=evidence.snapshot,
        oci_manifest=evidence.oci_manifest,
        runtime_identity=evidence.runtime_identity,
        artifact_integrity_verified=True,
        oci_manifest_semantics_verified=True,
    )
    with pytest.raises((TypeError, ValueError), match="evidence|OCI|factory|seal|type"):
        _prepare(evidence=proxy)

    class EvidenceSubclass(type(evidence)):
        pass

    subclass = object.__new__(EvidenceSubclass)
    with pytest.raises((TypeError, ValueError), match="evidence|OCI|factory|seal|type"):
        _prepare(evidence=subclass)

    mismatch = SimpleNamespace(
        schema_version=evidence.schema_version,
        snapshot=evidence.snapshot,
        oci_manifest=evidence.oci_manifest,
        runtime_identity=object(),
        artifact_integrity_verified=True,
        oci_manifest_semantics_verified=True,
    )
    with pytest.raises((TypeError, ValueError), match="evidence|identity|OCI|seal|type"):
        _prepare(evidence=mismatch)


def test_layout_plan_is_frozen_slotted_factory_sealed_and_opaque():
    plan = _prepare()
    assert is_dataclass(plan)
    assert not hasattr(plan, "__dict__")
    assert all(not hasattr(blob, "__dict__") for blob in plan.blobs)
    with pytest.raises(FrozenInstanceError):
        plan.total_size_bytes = 0  # type: ignore[misc]
    with pytest.raises((TypeError, ValueError)):
        replace(plan, total_size_bytes=0)
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        type(plan)(
            **{field.name: getattr(plan, field.name) for field in fields(plan) if field.init}
        )

    rendered = repr(plan) + repr(plan.blobs) + repr(plan.oci_evidence)
    assert _layout_bytes().decode("ascii") not in rendered
    assert _index_bytes().decode("ascii") not in rendered
    assert LAYOUT_SHA256 not in rendered
    assert INDEX_SHA256 not in rendered
    assert MANIFEST_SHA256 not in rendered
    assert CONFIG_SHA256 not in rendered
    assert all(digest not in rendered for digest, _size in LAYERS)
    assert all(path not in rendered for _role, path, _media, _digest, _size in _expected_blobs())


def test_layout_plan_blob_graph_is_a_deeply_immutable_factory_sealed_tuple():
    plan = _prepare()

    assert type(plan.blobs) is tuple
    assert plan.index_manifest is plan.blobs[0]
    with pytest.raises(AttributeError):
        plan.blobs.append(plan.blobs[0])  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        plan.blobs[0] = plan.blobs[1]  # type: ignore[index]

    original_manifest = plan.index_manifest
    for blob in plan.blobs:
        assert is_dataclass(blob)
        assert not hasattr(blob, "__dict__")
        for field_name in ("role", "path", "media_type", "digest", "size_bytes"):
            with pytest.raises(FrozenInstanceError):
                setattr(blob, field_name, getattr(blob, field_name))
            with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
                replace(blob, **{field_name: getattr(blob, field_name)})
        with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
            type(blob)(
                **{field.name: getattr(blob, field.name) for field in fields(blob) if field.init}
            )

    assert plan.index_manifest is original_manifest
    assert plan.index_manifest is plan.blobs[0]


def test_semantic_profile_error_does_not_expose_private_mutation_or_exception_chain():
    marker = "private-layout-ref-mutation"
    value = _index_object()
    value["manifests"][0]["annotations"]["org.opencontainers.image.ref.name"] = marker

    with pytest.raises(ValueError) as captured:
        _prepare(index_bytes=_encoded(value))

    _assert_private_error(captured.value, marker)


def test_manifest_blob_is_verified_incrementally_across_multiple_real_chunkings():
    from human_feedback import runtime_oci_layout as module

    plan = _prepare()
    payload = _captured_manifest_bytes(plan)
    assert module.MAX_OCI_BLOB_CHUNK_BYTES == MAX_OCI_BLOB_CHUNK_BYTES
    assert len(payload) == MANIFEST_SIZE_BYTES

    chunkings = (
        (payload,),
        (payload[:1], payload[1:]),
        (payload[:1_024], payload[1_024:2_048], payload[2_048:]),
        (b"", payload[:2_000], b"", payload[2_000:], b""),
        (payload[position : position + 17] for position in range(0, len(payload), 17)),
    )
    receipts = tuple(_verify_manifest(plan, chunks) for chunks in chunkings)

    assert all(type(receipt) is type(receipts[0]) for receipt in receipts)
    assert all(receipt == receipts[0] for receipt in receipts)
    assert len({id(receipt) for receipt in receipts}) == len(receipts)
    assert all(receipt.plan is plan for receipt in receipts)
    assert all(receipt.blob is plan.index_manifest for receipt in receipts)
    assert all(receipt.blob_bytes_verified is True for receipt in receipts)


@pytest.mark.parametrize("mutation", ["empty", "truncate", "append", "bitflip"])
def test_blob_verification_rejects_empty_truncated_appended_and_same_size_tamper(mutation):
    plan = _prepare()
    payload = _captured_manifest_bytes(plan)
    if mutation == "empty":
        changed = b""
    elif mutation == "truncate":
        changed = payload[:-1]
    elif mutation == "append":
        changed = payload + b"x"
    else:
        changed = bytes([payload[0] ^ 1]) + payload[1:]

    with pytest.raises(ValueError, match="blob|size|digest|content|verification"):
        _verify_manifest(plan, (changed,))


@pytest.mark.parametrize(
    "digest",
    [
        "sha256:" + "a" * 64,
        "SHA256:" + MANIFEST_SHA256,
        "sha512:" + "a" * 64,
        MANIFEST_SHA256,
        "sha256:" + MANIFEST_SHA256.upper(),
        True,
        None,
    ],
)
def test_blob_verification_requires_exact_known_sha256_identity(digest):
    plan = _prepare()
    marker = str(digest)
    with pytest.raises((TypeError, ValueError)) as captured:
        _verify_blob(plan, digest, (_captured_manifest_bytes(plan),))
    rendered = "".join(
        traceback.TracebackException.from_exception(captured.value).format(chain=True)
    )
    assert marker not in str(captured.value)
    assert marker not in rendered
    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True


@pytest.mark.parametrize("invalid_chunks", [None, b"raw-bytes", "text", 1, True])
def test_blob_verification_rejects_non_iterable_or_ambiguous_chunk_containers(invalid_chunks):
    plan = _prepare()
    with pytest.raises((TypeError, ValueError), match="chunks|iterable|stream|blob"):
        _verify_blob(plan, plan.index_manifest.digest, invalid_chunks)


@pytest.mark.parametrize("invalid_chunk", ["text", bytearray(b"x"), memoryview(b"x"), 1, True])
def test_blob_verification_accepts_only_exact_bytes_chunks(invalid_chunk):
    plan = _prepare()
    with pytest.raises(TypeError, match="chunk|bytes|blob"):
        _verify_blob(plan, plan.index_manifest.digest, (invalid_chunk,))


def test_blob_verification_enforces_chunk_cap_and_size_plus_one_cutoff():
    plan = _prepare()
    with pytest.raises(ValueError, match="chunk|limit|large"):
        _verify_blob(
            plan,
            plan.index_manifest.digest,
            (b"x" * (MAX_OCI_BLOB_CHUNK_BYTES + 1),),
        )

    payload = _captured_manifest_bytes(plan)
    chunks_consumed = 0

    def append_then_forbid_further_consumption():
        nonlocal chunks_consumed
        chunks_consumed += 1
        yield payload
        chunks_consumed += 1
        yield b"x"
        chunks_consumed += 1
        raise AssertionError("verifier read beyond expected size plus one byte")

    with pytest.raises(ValueError, match="blob|size|length|content"):
        _verify_blob(plan, plan.index_manifest.digest, append_then_forbid_further_consumption())
    assert chunks_consumed == 2


@pytest.mark.parametrize("line_ending", [b"\n", b"\r\n"])
def test_blob_verification_rejects_git_lfs_pointer_content(line_ending):
    plan = _prepare()
    pointer = line_ending.join(
        (
            b"version https://git-lfs.github.com/spec/v1",
            b"oid sha256:" + b"a" * 64,
            b"size 3166",
        )
    )
    payload = (pointer + line_ending + b"x" * MANIFEST_SIZE_BYTES)[:MANIFEST_SIZE_BYTES]
    assert len(payload) == MANIFEST_SIZE_BYTES
    for chunks in ((payload,), (payload[:3], payload[3:47], payload[47:])):
        with pytest.raises(ValueError, match="LFS|pointer|blob"):
            _verify_blob(plan, plan.index_manifest.digest, chunks)


def test_blob_generator_failure_is_private_and_context_suppressed():
    plan = _prepare()
    marker = "private-blob-generator-failure"

    def broken_chunks():
        yield _captured_manifest_bytes(plan)[:10]
        raise RuntimeError(marker)

    with pytest.raises((TypeError, ValueError)) as captured:
        _verify_blob(plan, plan.index_manifest.digest, broken_chunks())
    _assert_private_error(captured.value, marker)


def test_blob_verification_requires_exact_factory_plan_type():
    plan = _prepare()
    proxy = SimpleNamespace(blobs=plan.blobs, runtime_identity=plan.runtime_identity)
    with pytest.raises((TypeError, ValueError), match="plan|factory|seal|type"):
        _verify_blob(proxy, plan.index_manifest.digest, (_captured_manifest_bytes(plan),))

    class PlanSubclass(type(plan)):
        pass

    subclass = object.__new__(PlanSubclass)
    with pytest.raises((TypeError, ValueError), match="plan|factory|seal|type"):
        _verify_blob(subclass, plan.index_manifest.digest, (_captured_manifest_bytes(plan),))


def test_verified_blob_receipt_is_frozen_slotted_factory_sealed_and_opaque():
    plan = _prepare()
    receipt = _verify_manifest(plan)
    payload = _captured_manifest_bytes(plan)

    assert is_dataclass(receipt)
    assert not hasattr(receipt, "__dict__")
    with pytest.raises(FrozenInstanceError):
        receipt.blob_bytes_verified = False  # type: ignore[misc]
    for field_name in ("plan", "blob", "blob_bytes_verified"):
        with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
            replace(receipt, **{field_name: getattr(receipt, field_name)})
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        type(receipt)(
            **{field.name: getattr(receipt, field.name) for field in fields(receipt) if field.init}
        )

    rendered = repr(receipt) + repr((receipt,))
    assert plan.index_manifest.path not in rendered
    assert plan.index_manifest.digest not in rendered
    assert payload.decode("ascii") not in rendered


def test_blob_verifier_uses_incremental_hashing_without_materializing_chunks():
    from human_feedback import runtime_oci_layout

    source = Path(runtime_oci_layout.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    verifier = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "verify_laya_oci_blob_chunks"
    )
    calls = [node for node in ast.walk(verifier) if isinstance(node, ast.Call)]
    assert any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "update" for call in calls
    )
    assert not any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "join" for call in calls
    )
    assert not any(
        isinstance(call.func, ast.Name) and call.func.id in {"bytearray", "list", "tuple"}
        for call in calls
    )


def test_duplicate_verification_is_deterministic_but_duplicate_receipts_do_not_finalize():
    from human_feedback.runtime_oci_layout import finalize_laya_oci_layout_evidence

    plan = _prepare()
    first = _verify_manifest(plan)
    second = _verify_manifest(plan)
    assert first == second
    assert first is not second

    with pytest.raises(ValueError, match="receipt|duplicate|complete|blob|order"):
        finalize_laya_oci_layout_evidence(plan, (first, second))


def test_finalize_requires_exact_complete_ordered_receipt_tuple_without_substitution():
    from human_feedback.runtime_oci_layout import finalize_laya_oci_layout_evidence

    plan = _prepare()
    receipt = _verify_manifest(plan)
    candidates = (
        [],
        (),
        (receipt,),
        tuple(receipt for _blob in plan.blobs),
        SimpleNamespace(plan=plan, blob=plan.index_manifest, blob_bytes_verified=True),
        (
            SimpleNamespace(
                plan=plan,
                blob=plan.index_manifest,
                blob_bytes_verified=True,
            ),
        ),
    )
    for candidate in candidates:
        with pytest.raises((TypeError, ValueError), match="receipt|tuple|complete|blob|order"):
            finalize_laya_oci_layout_evidence(plan, candidate)

    foreign_plan = _prepare()
    foreign_receipt = _verify_manifest(foreign_plan)
    with pytest.raises(ValueError, match="receipt|plan|identity|foreign|blob"):
        finalize_laya_oci_layout_evidence(plan, (foreign_receipt,))

    class ReceiptSubclass(type(receipt)):
        pass

    subclass = object.__new__(ReceiptSubclass)
    with pytest.raises((TypeError, ValueError), match="receipt|factory|seal|type"):
        finalize_laya_oci_layout_evidence(plan, (subclass,))


def test_finalize_failure_is_all_or_nothing_private_and_context_suppressed():
    from human_feedback.runtime_oci_layout import finalize_laya_oci_layout_evidence

    plan = _prepare()
    marker = "private-forged-receipt-content"
    forged = SimpleNamespace(
        plan=plan,
        blob=plan.index_manifest,
        blob_bytes_verified=True,
        private_content=marker,
    )
    with pytest.raises((TypeError, ValueError)) as captured:
        finalize_laya_oci_layout_evidence(plan, (forged,))
    _assert_private_error(captured.value, marker)


def test_finalize_and_summary_reject_proxy_subclass_and_non_evidence_values():
    from human_feedback.runtime_oci_layout import (
        canonical_laya_runtime_oci_layout_summary_bytes,
        finalize_laya_oci_layout_evidence,
    )

    plan = _prepare()
    proxy = SimpleNamespace(
        schema_version=plan.schema_version,
        oci_evidence=plan.oci_evidence,
        runtime_identity=plan.runtime_identity,
        blobs=plan.blobs,
    )
    with pytest.raises((TypeError, ValueError), match="plan|factory|seal|type"):
        finalize_laya_oci_layout_evidence(proxy, ())
    for invalid in (None, plan, proxy, (), SimpleNamespace()):
        with pytest.raises((TypeError, ValueError), match="evidence|factory|seal|type"):
            canonical_laya_runtime_oci_layout_summary_bytes(invalid)


def test_final_evidence_type_is_frozen_slotted_and_factory_sealed_without_forgery():
    from human_feedback.runtime_oci_layout import LayaRuntimeOciLayoutEvidence

    plan = _prepare()
    assert is_dataclass(LayaRuntimeOciLayoutEvidence)
    assert "__slots__" in vars(LayaRuntimeOciLayoutEvidence)
    values = {
        "schema_version": LAYOUT_EVIDENCE_SCHEMA,
        "plan": plan,
        "oci_evidence": plan.oci_evidence,
        "runtime_identity": plan.runtime_identity,
        "receipts": (),
    }
    init_fields = tuple(field.name for field in fields(LayaRuntimeOciLayoutEvidence) if field.init)
    assert set(init_fields) <= set(values)
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        LayaRuntimeOciLayoutEvidence(**{name: values[name] for name in init_fields})


def test_manifest_verification_does_not_mutate_plan_or_prior_evidence_summaries():
    from human_feedback.runtime_oci_metadata import canonical_laya_runtime_oci_summary_bytes

    plan = _prepare()
    evidence = plan.oci_evidence
    blobs_before = plan.blobs
    summary_before = canonical_laya_runtime_oci_summary_bytes(evidence)
    _verify_manifest(plan)
    assert plan.blobs is blobs_before
    assert plan.oci_evidence is evidence
    assert canonical_laya_runtime_oci_summary_bytes(evidence) == summary_before


@pytest.mark.skipif(
    not os.environ.get("LAYA_OCI_LAYOUT_ROOT"),
    reason="requires opt-in external 612 MB OCI layout",
)
def test_opt_in_real_layout_finalizes_conservative_evidence_and_public_summary():
    from human_feedback.runtime_oci_layout import (
        canonical_laya_runtime_oci_layout_summary_bytes,
        finalize_laya_oci_layout_evidence,
    )

    plan = _prepare()
    root = Path(os.environ["LAYA_OCI_LAYOUT_ROOT"])

    def chunks(path):
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(MAX_OCI_BLOB_CHUNK_BYTES)
                if not chunk:
                    return
                yield chunk

    receipts = tuple(
        _verify_blob(plan, blob.digest, chunks(root / blob.path)) for blob in plan.blobs
    )
    with pytest.raises(ValueError, match="receipt|order|blob|identity"):
        finalize_laya_oci_layout_evidence(plan, tuple(reversed(receipts)))
    with pytest.raises(ValueError, match="receipt|complete|blob|duplicate"):
        finalize_laya_oci_layout_evidence(plan, (*receipts[:-1], receipts[0]))
    evidence = finalize_laya_oci_layout_evidence(plan, receipts)

    assert is_dataclass(evidence)
    assert not hasattr(evidence, "__dict__")
    assert evidence.plan is plan
    assert evidence.oci_evidence is plan.oci_evidence
    assert evidence.runtime_identity is plan.runtime_identity
    for flag in (
        "artifact_integrity_verified",
        "oci_manifest_semantics_verified",
        "oci_layout_semantics_verified",
        "oci_index_semantics_verified",
        "oci_layer_bytes_verified",
        "oci_config_bytes_verified",
        "oci_bytes_verified",
    ):
        assert getattr(evidence, flag) is True
    for flag in (
        "lock_verified",
        "sbom_verified",
        "lock_sbom_consistent",
        "runtime_config_semantics_verified",
        "checkpoint_manifest_semantics_verified",
        "checkpoint_bytes_verified",
        "origin_verified",
        "license_verified",
        "base_image_ancestry_verified",
        "layer_diff_ids_verified",
        "rootfs_materialized",
        "runtime_materialized",
        "executor_available",
        "inference_executed",
    ):
        assert getattr(evidence, flag) is False

    with pytest.raises(FrozenInstanceError):
        evidence.oci_bytes_verified = False  # type: ignore[misc]
    with pytest.raises((TypeError, ValueError)):
        replace(evidence, oci_bytes_verified=False)
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        type(evidence)(
            **{
                field.name: getattr(evidence, field.name)
                for field in fields(evidence)
                if field.init
            }
        )

    class EvidenceSubclass(type(evidence)):
        pass

    subclass = object.__new__(EvidenceSubclass)
    with pytest.raises((TypeError, ValueError), match="evidence|factory|seal|type"):
        canonical_laya_runtime_oci_layout_summary_bytes(subclass)

    summary = canonical_laya_runtime_oci_layout_summary_bytes(evidence)
    decoded = json.loads(summary)
    assert decoded == {
        "artifact_integrity_verified": True,
        "base_image_ancestry_verified": False,
        "checkpoint_bytes_verified": False,
        "checkpoint_manifest_semantics_verified": False,
        "executor_available": False,
        "inference_executed": False,
        "layer_diff_ids_verified": False,
        "license_verified": False,
        "lock_sbom_consistent": False,
        "lock_verified": False,
        "oci_bytes_verified": True,
        "oci_config_bytes_verified": True,
        "oci_index_semantics_verified": True,
        "oci_layer_bytes_verified": True,
        "oci_layout_semantics_verified": True,
        "oci_manifest_semantics_verified": True,
        "origin_verified": False,
        "plan_schema_version": LAYOUT_PLAN_SCHEMA,
        "profile_id": LAYOUT_PROFILE_ID,
        "rootfs_materialized": False,
        "runtime_config_semantics_verified": False,
        "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
        "runtime_identity_sha256": evidence.runtime_identity.sha256,
        "runtime_materialized": False,
        "sbom_verified": False,
        "schema_version": LAYOUT_EVIDENCE_SCHEMA,
    }
    assert summary == json.dumps(
        decoded, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")
    rendered = repr(evidence) + summary.decode("ascii")
    assert all(blob.path not in rendered for blob in plan.blobs)
    assert all(blob.digest not in rendered for blob in plan.blobs)
    assert str(plan.total_size_bytes) not in rendered
    assert _layout_bytes().decode("ascii") not in rendered
    assert _index_bytes().decode("ascii") not in rendered


def test_prepare_does_not_mutate_prior_evidence_or_prior_canonical_summaries():
    from human_feedback.runtime_oci_metadata import canonical_laya_runtime_oci_summary_bytes

    evidence = _oci_evidence()
    summary_before = canonical_laya_runtime_oci_summary_bytes(evidence)
    snapshot_before = evidence.snapshot
    _prepare(evidence)
    assert evidence.snapshot is snapshot_before
    assert canonical_laya_runtime_oci_summary_bytes(evidence) == summary_before


def test_pr15_runtime_artifact_roles_remain_exactly_the_original_five():
    from human_feedback.runtime_identity import ARTIFACT_KINDS

    assert ARTIFACT_KINDS == (
        "dependency_lock",
        "sbom",
        "runtime_config",
        "checkpoint_manifest",
        "oci_manifest",
    )


def test_runtime_oci_layout_module_is_pure_and_depends_only_on_pr19_contract():
    from human_feedback import runtime_oci_layout

    source = Path(runtime_oci_layout.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_imports = {
        "__future__",
        "dataclasses",
        "hashlib",
        "human_feedback.runtime_oci_metadata",
        "json",
        "typing",
    }
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imports <= allowed_imports
    forbidden_calls = {
        "open",
        "read_bytes",
        "read_text",
        "urlopen",
        "run",
        "Popen",
        "socket",
        "DockerClient",
    }
    assert not {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }.intersection(forbidden_calls)
    assert not {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }.intersection(forbidden_calls)


@pytest.mark.parametrize(
    "source",
    [
        "import human_feedback.runtime_oci_layout",
        "import human_feedback.runtime_oci_layout as layout",
        "from human_feedback import runtime_oci_layout",
        "from human_feedback import runtime_oci_layout as layout",
        "from human_feedback.runtime_oci_layout import LayaOciLayoutPlan",
        "from human_feedback.runtime_oci_layout import *",
        "from . import runtime_oci_layout as layout",
        "from .runtime_oci_layout import prepare_laya_oci_layout_plan",
        "from .runtime_oci_layout import *",
        "runtime_oci_layout.prepare_laya_oci_layout_plan(evidence, marker, index)",
        "name = 'human_feedback.runtime_oci_layout'",
        "module = import_module('human_feedback.runtime_oci_layout')",
    ],
)
def test_layout_plan_isolation_detector_recognizes_import_and_usage_forms(source):
    assert _uses_layout_plan_api(source) is True


@pytest.mark.parametrize(
    "source",
    [
        "from human_feedback.runtime_oci_metadata import validate_laya_oci_manifest_bytes",
        "name = 'runtime_oci_layoutish'",
        "def prepare_layout_plan(): return None",
    ],
)
def test_layout_plan_isolation_detector_avoids_unrelated_false_positives(source):
    assert _uses_layout_plan_api(source) is False


def test_no_existing_product_module_imports_or_uses_layout_plan_api():
    repository_root = Path(__file__).parents[1]
    target = repository_root / "src" / "human_feedback" / "runtime_oci_layout.py"
    offenders = []
    for relative_root in ("backend", "src", "scripts"):
        product_root = repository_root / relative_root
        if not product_root.is_dir():
            continue
        for path in product_root.rglob("*.py"):
            if path == target:
                continue
            if _uses_layout_plan_api(path.read_text(encoding="utf-8")):
                offenders.append(path.relative_to(repository_root).as_posix())
    assert offenders == []
