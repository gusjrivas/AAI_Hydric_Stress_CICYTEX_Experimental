import ast
import hashlib
import json
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
MAX_OCI_BLOB_CHUNKS = 1_024
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
        "capture_and_verify_laya_oci_layout",
        "finalize_laya_oci_layout_evidence",
        "finalize_laya_runtime_oci_layout_evidence",
        "prepare_laya_oci_layout_plan",
        "verify_laya_oci_blob_chunks",
    }
    module_name = "human_feedback.runtime_oci_layout"
    adapter_module_name = "human_feedback.adapters.filesystem_oci_layout"
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name in {module_name, adapter_module_name} for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom):
            if node.module == adapter_module_name and any(
                alias.name == "*" or alias.name in symbols for alias in node.names
            ):
                return True
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
        if isinstance(node, ast.Constant) and node.value in {
            module_name,
            adapter_module_name,
            *symbols,
        }:
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
    assert module.MAX_OCI_BLOB_CHUNKS == MAX_OCI_BLOB_CHUNKS
    assert len(payload) == MANIFEST_SIZE_BYTES

    chunkings = (
        (payload,),
        (payload[:1], payload[1:]),
        (payload[:1_024], payload[1_024:2_048], payload[2_048:]),
        (payload[:2_000], payload[2_000:]),
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


@pytest.mark.parametrize("position", ["first", "middle", "last"])
def test_blob_verification_rejects_every_zero_length_chunk(position):
    plan = _prepare()
    payload = _captured_manifest_bytes(plan)
    chunks = {
        "first": (b"", payload),
        "middle": (payload[:1], b"", payload[1:]),
        "last": (payload, b""),
    }[position]
    with pytest.raises(ValueError, match="chunk|empty|zero|blob"):
        _verify_blob(plan, plan.index_manifest.digest, chunks)


def test_blob_verification_stops_at_bounded_chunk_count_without_consuming_sentinel():
    plan = _prepare()
    chunks_consumed = 0

    def hostile_many_chunks():
        nonlocal chunks_consumed
        for _index in range(MAX_OCI_BLOB_CHUNKS + 1):
            chunks_consumed += 1
            yield b"x"
        chunks_consumed += 1
        raise AssertionError("verifier consumed beyond the public chunk-count cap")

    with pytest.raises(ValueError, match="chunk|count|limit|many"):
        _verify_blob(plan, plan.index_manifest.digest, hostile_many_chunks())
    assert chunks_consumed == MAX_OCI_BLOB_CHUNKS + 1


def test_blob_verification_rejects_empty_chunk_before_resuming_hostile_generator():
    plan = _prepare()
    chunks_consumed = 0

    def hostile_empty_chunk():
        nonlocal chunks_consumed
        chunks_consumed += 1
        yield b""
        chunks_consumed += 1
        raise AssertionError("verifier resumed after an invalid empty chunk")

    with pytest.raises(ValueError, match="chunk|empty|zero|blob"):
        _verify_blob(plan, plan.index_manifest.digest, hostile_empty_chunk())
    assert chunks_consumed == 1


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


@pytest.mark.parametrize(
    "digest",
    [
        "sha256:" + "a" * 64,
        "SHA256:" + MANIFEST_SHA256,
        "sha512:" + "a" * 64,
        "malformed",
        True,
        None,
    ],
)
def test_blob_authorization_rejects_unknown_digest_before_consuming_chunks(digest):
    plan = _prepare()
    chunks_consumed = 0

    def hostile_chunks():
        nonlocal chunks_consumed
        chunks_consumed += 1
        yield b"private-unauthorized-content"
        chunks_consumed += 1
        raise AssertionError("unauthorized digest consumed the chunk stream")

    with pytest.raises((TypeError, ValueError)):
        _verify_blob(plan, digest, hostile_chunks())
    assert chunks_consumed == 0


def test_blob_authorization_rejects_invalid_plan_before_consuming_chunks():
    plan = _prepare()
    chunks_consumed = 0

    def hostile_chunks():
        nonlocal chunks_consumed
        chunks_consumed += 1
        yield b"private-unauthorized-content"
        chunks_consumed += 1
        raise AssertionError("invalid plan consumed the chunk stream")

    proxy = SimpleNamespace(
        blobs=plan.blobs,
        index_manifest=plan.index_manifest,
        runtime_identity=plan.runtime_identity,
    )
    with pytest.raises((TypeError, ValueError), match="plan|factory|seal|type"):
        _verify_blob(proxy, plan.index_manifest.digest, hostile_chunks())
    assert chunks_consumed == 0


def test_verified_blob_receipt_is_frozen_slotted_factory_sealed_and_opaque():
    plan = _prepare()
    receipt = _verify_manifest(plan)
    payload = _captured_manifest_bytes(plan)

    assert is_dataclass(receipt)
    assert not hasattr(receipt, "__dict__")
    public_fields = tuple(field.name for field in fields(receipt) if not field.name.startswith("_"))
    assert {"plan", "blob", "blob_bytes_verified"} <= set(public_fields)
    for field_name in public_fields:
        with pytest.raises(FrozenInstanceError):
            setattr(receipt, field_name, getattr(receipt, field_name))
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
    definitions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    wrapper = definitions["verify_laya_oci_blob_chunks"]
    assert "_verify_laya_oci_blob_chunks" in {
        call.func.id
        for call in ast.walk(wrapper)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    }

    reachable_names = {"_verify_laya_oci_blob_chunks"}
    pending = ["_verify_laya_oci_blob_chunks"]
    while pending:
        name = pending.pop()
        for call in (node for node in ast.walk(definitions[name]) if isinstance(node, ast.Call)):
            if (
                isinstance(call.func, ast.Name)
                and call.func.id in definitions
                and call.func.id not in reachable_names
            ):
                reachable_names.add(call.func.id)
                pending.append(call.func.id)

    calls = [
        node
        for name in reachable_names
        for node in ast.walk(definitions[name])
        if isinstance(node, ast.Call)
    ]
    private_verifier = definitions["_verify_laya_oci_blob_chunks"]
    private_calls = [node for node in ast.walk(private_verifier) if isinstance(node, ast.Call)]
    assert any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "update"
        for call in private_calls
    )
    assert any(
        isinstance(node, ast.For) and isinstance(node.iter, ast.Name) and node.iter.id == "chunks"
        for node in ast.walk(private_verifier)
    )
    assert not any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "join" for call in calls
    )
    assert not any(
        isinstance(call.func, ast.Name) and call.func.id in {"bytearray", "list", "tuple"}
        for call in calls
    )


def test_duplicate_blob_verification_is_deterministic_without_global_evidence_claims():
    plan = _prepare()
    first = _verify_manifest(plan)
    second = _verify_manifest(plan)
    assert first == second
    assert first is not second
    for receipt in (first, second):
        assert receipt.blob_bytes_verified is True
        for forbidden_claim in (
            "oci_bytes_verified",
            "oci_config_bytes_verified",
            "oci_layer_bytes_verified",
            "oci_layout_semantics_verified",
            "oci_index_semantics_verified",
            "origin_verified",
            "rootfs_materialized",
            "runtime_materialized",
        ):
            assert not hasattr(receipt, forbidden_claim)


def test_individual_receipt_cannot_finalize_or_elevate_layout_evidence():
    """RED20C owns final evidence via a sealed same-root capture/session."""

    from human_feedback import runtime_oci_layout as module

    receipt = _verify_manifest()
    assert not hasattr(receipt, "finalize")
    assert not hasattr(receipt, "as_evidence")
    assert not hasattr(receipt, "oci_bytes_verified")
    assert not hasattr(module, "verified_laya_oci_blob_from_digest")
    assert not hasattr(module, "receipt_from_digest")
    assert hasattr(module, "LayaRuntimeOciLayoutEvidence")
    assert hasattr(module, "canonical_laya_runtime_oci_layout_summary_bytes")
    for forbidden_name in (
        "finalize_laya_oci_layout_evidence",
        "finalize_laya_runtime_oci_layout_evidence",
        "laya_oci_layout_session",
        "seal_laya_oci_layout_from_receipts",
    ):
        assert not hasattr(module, forbidden_name)


def test_verified_blob_proxy_and_subclass_cannot_masquerade_as_factory_receipt():
    from human_feedback.runtime_oci_layout import VerifiedLayaOciBlob

    receipt = _verify_manifest()
    proxy = SimpleNamespace(
        plan=receipt.plan,
        blob=receipt.blob,
        blob_bytes_verified=True,
    )
    assert type(receipt) is VerifiedLayaOciBlob
    assert type(proxy) is not VerifiedLayaOciBlob

    class ReceiptSubclass(VerifiedLayaOciBlob):
        pass

    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        ReceiptSubclass(
            **{field.name: getattr(receipt, field.name) for field in fields(receipt) if field.init}
        )


def test_layout_evidence_core_api_is_private_sealed_without_public_finalizer():
    from human_feedback import runtime_oci_layout as module

    assert module.LAYOUT_PROFILE_ID == LAYOUT_PROFILE_ID
    assert module.LAYOUT_EVIDENCE_SCHEMA == LAYOUT_EVIDENCE_SCHEMA
    assert is_dataclass(module.LayaRuntimeOciLayoutEvidence)
    assert "__slots__" in vars(module.LayaRuntimeOciLayoutEvidence)
    assert is_dataclass(module._LayaOciLayoutCaptureAuthority)
    assert "__slots__" in vars(module._LayaOciLayoutCaptureAuthority)
    assert not hasattr(module, "LayaOciLayoutCaptureAuthority")
    assert callable(module._seal_laya_oci_layout_capture_authority)
    assert callable(module._seal_laya_oci_layout_evidence)
    for forbidden_name in (
        "finalize_laya_oci_layout_evidence",
        "finalize_laya_runtime_oci_layout_evidence",
        "seal_laya_oci_layout_from_receipts",
        "laya_oci_layout_session",
        "receipt_from_digest",
    ):
        assert not hasattr(module, forbidden_name)


def test_layout_evidence_fields_are_exact_conservative_and_not_forgeable():
    from human_feedback import runtime_oci_layout as module

    true_flags = {
        "artifact_integrity_verified",
        "oci_manifest_semantics_verified",
        "oci_layout_controls_bytes_verified",
        "oci_blob_inventory_verified",
        "oci_same_root_capture_verified",
        "oci_manifest_blob_bytes_verified",
        "oci_config_blob_bytes_verified",
        "oci_layer_blobs_bytes_verified",
        "oci_bytes_verified",
    }
    false_flags = {
        "lock_verified",
        "sbom_verified",
        "lock_sbom_consistent",
        "runtime_config_semantics_verified",
        "checkpoint_manifest_semantics_verified",
        "checkpoint_bytes_verified",
        "oci_config_semantics_verified",
        "oci_layer_diff_ids_verified",
        "oci_rootfs_verified",
        "origin_verified",
        "license_verified",
        "base_ancestry_verified",
        "rootfs_materialized",
        "runtime_materialized",
        "executor_available",
        "inference_executed",
    }
    evidence_fields = {field.name: field for field in fields(module.LayaRuntimeOciLayoutEvidence)}
    assert set(evidence_fields) == {
        "schema_version",
        "plan",
        "runtime_identity",
        "receipts",
        *true_flags,
        *false_flags,
    }
    assert evidence_fields["plan"].repr is False
    assert evidence_fields["runtime_identity"].repr is False
    assert evidence_fields["receipts"].repr is False
    assert all(evidence_fields[name].init is False for name in true_flags | false_flags)


def test_capture_authority_is_frozen_factory_sealed_and_opaque():
    from human_feedback import runtime_oci_layout as module

    plan = _prepare()
    authority_type = module._LayaOciLayoutCaptureAuthority
    assert authority_type.__dataclass_params__.frozen is True
    assert "__dict__" not in authority_type.__slots__
    authority_fields = {field.name: field for field in fields(authority_type)}
    assert set(authority_fields) == {
        "plan",
        "receipts",
        "controls_captured_from_same_root",
        "inventory_captured_from_same_root",
        "final_fd_sweep_verified",
    }
    assert all(field.repr is False for field in authority_fields.values())
    values = {
        "plan": plan,
        "receipts": (),
        "controls_captured_from_same_root": True,
        "inventory_captured_from_same_root": True,
        "final_fd_sweep_verified": True,
    }
    init_fields = tuple(field.name for field in fields(authority_type) if field.init)
    assert set(init_fields) <= set(values)
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        authority_type(**{name: values[name] for name in init_fields})

    class AuthoritySubclass(authority_type):
        pass

    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        AuthoritySubclass(**{name: values[name] for name in init_fields})


def test_authority_and_evidence_sealers_reject_raw_proxy_and_foreign_inputs():
    from human_feedback import runtime_oci_layout as module

    plan = _prepare()
    receipt = _verify_manifest(plan)
    proxy = SimpleNamespace(
        plan=plan,
        receipts=tuple(receipt for _blob in plan.blobs),
        controls_captured_from_same_root=True,
        inventory_captured_from_same_root=True,
        final_fd_sweep_verified=True,
    )
    raw_receipts = tuple(receipt for _blob in plan.blobs)
    for invalid in (None, plan, (), raw_receipts, proxy):
        with pytest.raises((TypeError, ValueError), match="authority|factory|seal|type"):
            module._seal_laya_oci_layout_evidence(invalid)

    foreign_plan = _prepare()
    foreign_receipt = _verify_manifest(foreign_plan)
    mixed_receipts = (foreign_receipt, *raw_receipts[1:])
    assert len(mixed_receipts) == 12
    with pytest.raises(ValueError, match="receipt|plan|identity|foreign|blob"):
        module._seal_laya_oci_layout_capture_authority(
            plan,
            mixed_receipts,
            controls_captured_from_same_root=True,
            inventory_captured_from_same_root=True,
            final_fd_sweep_verified=True,
        )


def test_layout_evidence_direct_construction_replace_proxy_and_summary_fail_closed():
    from human_feedback import runtime_oci_layout as module

    plan = _prepare()
    evidence_type = module.LayaRuntimeOciLayoutEvidence
    values = {
        "schema_version": LAYOUT_EVIDENCE_SCHEMA,
        "plan": plan,
        "runtime_identity": plan.runtime_identity,
        "receipts": (),
    }
    init_fields = tuple(field.name for field in fields(evidence_type) if field.init)
    assert set(init_fields) <= set(values)
    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        evidence_type(**{name: values[name] for name in init_fields})

    proxy = SimpleNamespace(**values)
    for invalid in (None, plan, proxy, (), SimpleNamespace()):
        with pytest.raises((TypeError, ValueError), match="evidence|factory|seal|type"):
            module.canonical_laya_runtime_oci_layout_summary_bytes(invalid)

    class EvidenceSubclass(evidence_type):
        pass

    with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
        EvidenceSubclass(**{name: values[name] for name in init_fields})


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
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_functions == {
        "prepare_laya_oci_layout_plan",
        "verify_laya_oci_blob_chunks",
        "canonical_laya_runtime_oci_layout_summary_bytes",
    }
    public_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    assert public_classes == {
        "LayaOciBlobPlan",
        "LayaOciLayoutPlan",
        "VerifiedLayaOciBlob",
        "LayaRuntimeOciLayoutEvidence",
    }
    public_constants = {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
        if isinstance(target, ast.Name) and target.id.isupper() and not target.id.startswith("_")
    }
    assert public_constants == {
        "MAX_OCI_LAYOUT_BYTES",
        "MAX_OCI_INDEX_BYTES",
        "MAX_OCI_CONTROL_JSON_DEPTH",
        "MAX_OCI_CONTROL_STRING_LENGTH",
        "MAX_OCI_BLOB_CHUNK_BYTES",
        "MAX_OCI_BLOB_CHUNKS",
        "LAYOUT_PLAN_SCHEMA",
        "LAYOUT_PROFILE_ID",
        "LAYOUT_EVIDENCE_SCHEMA",
    }
    forbidden_elevation_methods = {
        "finalize",
        "as_evidence",
        "from_receipts",
        "from_digest",
        "seal",
    }
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in {
            "VerifiedLayaOciBlob",
            "LayaRuntimeOciLayoutEvidence",
        }:
            methods = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            assert methods.isdisjoint(forbidden_elevation_methods)
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
        ("from human_feedback.runtime_oci_layout import " "LayaRuntimeOciLayoutEvidence"),
        ("from human_feedback.runtime_oci_layout import " "finalize_laya_oci_layout_evidence"),
        "name = 'canonical_laya_runtime_oci_layout_summary_bytes'",
        "from human_feedback.runtime_oci_layout import *",
        "import human_feedback.adapters.filesystem_oci_layout",
        (
            "from human_feedback.adapters.filesystem_oci_layout import "
            "capture_and_verify_laya_oci_layout"
        ),
        "filesystem_oci_layout.capture_and_verify_laya_oci_layout(evidence, root)",
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
    adapter = repository_root / "src" / "human_feedback" / "adapters" / "filesystem_oci_layout.py"
    allowed_consumers = {target, adapter}
    offenders = []
    for relative_root in ("backend", "src", "scripts"):
        product_root = repository_root / relative_root
        if not product_root.is_dir():
            continue
        for path in product_root.rglob("*.py"):
            if path in allowed_consumers:
                continue
            if _uses_layout_plan_api(path.read_text(encoding="utf-8")):
                offenders.append(path.relative_to(repository_root).as_posix())
    assert offenders == []
