import ast
import copy
import gc
import hashlib
import inspect
import json
import math
import pickle
import traceback
import weakref
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "laya" / "runtime_base_ancestry"
OBJECT_FIXTURES = (
    ("root.json", 9131, "840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e"),
    (
        "linux-amd64-manifest.json",
        1752,
        "efc99f05ec45381aac55e2803c9a0245ea5b8c74965264498338e24e4bf66cc7",
    ),
    (
        "linux-amd64-config.json",
        5295,
        "80abb94774d660831663290fe0b208b3e067b88647902f0f9e1d3a331a997afd",
    ),
)
ROOT_DIGEST = "sha256:" + OBJECT_FIXTURES[0][2]
MANIFEST_DIGEST = "sha256:" + OBJECT_FIXTURES[1][2]
CONFIG_DIGEST = "sha256:" + OBJECT_FIXTURES[2][2]
LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar+gzip"
BASE_LAYERS = (
    (
        "sha256:bc0965b23a04fe7f2d9fb20f597008fcf89891de1c705ffc1c80483a1f098e4f",
        28231580,
        LAYER_MEDIA_TYPE,
    ),
    (
        "sha256:c58b365c3bcb57c930511e3fef962d15491ef2daba1e111fb5a6b41dbdecfc6b",
        3317301,
        LAYER_MEDIA_TYPE,
    ),
    (
        "sha256:3bc3f72291794502343f023ab10455e459897b13a73f38b6b56cf266dccb7ec5",
        16202769,
        LAYER_MEDIA_TYPE,
    ),
    (
        "sha256:42dacf6a4601de71542906f1be2bca5a78b8f430479b260a7097b9870498af69",
        251,
        LAYER_MEDIA_TYPE,
    ),
)
BASE_DIFF_IDS = (
    "sha256:c0f1022b22a9b36851b358f44e5475e39d166e71a8073cf53c894a299239b1c5",
    "sha256:bc9155b10ccec596b3283ceca7cc847bc4046db14eab7f77b9b170b5e825e0a5",
    "sha256:0266a6d27cd42ef4422dfb0b6dbd4186f3524600502559e13947f8d4de65c931",
    "sha256:cfc6e3b5400ce78d3df9c4826f39a78db0e7e9a01d2581b860b5611ac6829af6",
)
TRUE_PR22_CLAIMS = (
    "artifact_integrity_verified",
    "oci_manifest_semantics_verified",
    "oci_layout_controls_bytes_verified",
    "oci_blob_inventory_verified",
    "oci_same_root_capture_verified",
    "oci_manifest_blob_bytes_verified",
    "oci_config_blob_bytes_verified",
    "oci_layer_blobs_bytes_verified",
    "oci_bytes_verified",
    "oci_config_semantics_verified",
    "oci_layer_diff_ids_verified",
)
FALSE_PR22_CLAIMS = (
    "lock_verified",
    "sbom_verified",
    "lock_sbom_consistent",
    "runtime_config_semantics_verified",
    "checkpoint_manifest_semantics_verified",
    "checkpoint_bytes_verified",
    "oci_rootfs_verified",
    "tar_semantics_verified",
    "origin_verified",
    "license_verified",
    "rootfs_materialized",
    "runtime_materialized",
    "executor_available",
    "inference_executed",
)
CONSERVATIVE_FALSE_CLAIMS = (
    "oci_rootfs_verified",
    "tar_semantics_verified",
    "origin_verified",
    "license_verified",
    "runtime_build_recipe_verified",
    "build_process_attested",
    "reproducible_build_verified",
    "rootfs_materialized",
    "runtime_materialized",
    "executor_available",
    "inference_executed",
)
PR36_ONLY_FALSE_CLAIMS = (
    "runtime_build_recipe_verified",
    "build_process_attested",
    "reproducible_build_verified",
)


def _private_error(error: BaseException, *markers: str) -> None:
    rendered = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    for marker in markers:
        assert marker not in str(error)
        assert marker not in rendered
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True


def _fixture_bytes() -> tuple[bytes, bytes, bytes]:
    return tuple((FIXTURE_ROOT / name).read_bytes() for name, _size, _digest in OBJECT_FIXTURES)


def _streams(payloads=None):
    selected = _fixture_bytes() if payloads is None else payloads
    return tuple(iter((payload,)) for payload in selected)


def _clone_dataclass(value, **changes):
    clone = object.__new__(type(value))
    for item in fields(value):
        object.__setattr__(
            clone,
            item.name,
            changes.get(item.name, getattr(value, item.name)),
        )
    return clone


def _exact_pr22_evidence(monkeypatch):
    """Reuse PR22's isolation helper and make its ten-position profile exact.

    The predecessor's own canonical summary remains the authority oracle.  This
    helper does not construct PR36 plan, receipt, authority or evidence values.
    """

    from human_feedback import runtime_oci_layers
    from tests.test_laya_runtime_oci_tar import _synthetic_pr22_evidence

    evidence = _synthetic_pr22_evidence()
    plan = evidence.plan
    for position, (digest, size, media_type) in enumerate(BASE_LAYERS):
        blob = plan.layer_blobs[position]
        blob.digest = digest
        blob.size_bytes = size
        blob.media_type = media_type
    child_diff_ids = (*BASE_DIFF_IDS, *plan.declared_diff_ids[len(BASE_DIFF_IDS) :])
    object.__setattr__(plan, "declared_diff_ids", child_diff_ids)
    for position, receipt in enumerate(evidence.receipts):
        object.__setattr__(receipt, "declared_diff_id", child_diff_ids[position])
        object.__setattr__(receipt, "computed_diff_id", child_diff_ids[position])

    calls = []

    def predecessor_oracle(candidate):
        calls.append(candidate)
        if candidate is not evidence:
            raise ValueError("invalid PR22 issued evidence") from None
        return b'{"schema_version":"laya-runtime-oci-layer-diff-ids-evidence-v1"}\n'

    monkeypatch.setattr(
        runtime_oci_layers,
        "canonical_laya_runtime_oci_layer_diff_ids_summary_bytes",
        predecessor_oracle,
    )
    return evidence, calls


def _prepared(monkeypatch):
    from human_feedback import runtime_base_ancestry as module

    predecessor, calls = _exact_pr22_evidence(monkeypatch)
    plan = module.prepare_laya_runtime_base_ancestry_plan(predecessor)
    return module, predecessor, calls, plan


def _verified(monkeypatch):
    module, predecessor, calls, plan = _prepared(monkeypatch)
    evidence = module.verify_laya_runtime_base_ancestry_objects(plan, _streams())
    return module, predecessor, calls, plan, evidence


def _bounded_json(module, value):
    return module._load_laya_base_ancestry_json(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    )


def _hostile_never_iterated(marker):
    class Hostile:
        def __init__(self):
            self.touched = False

        def __iter__(self):
            self.touched = True
            raise AssertionError(marker)

    return Hostile()


def _test_object_specs(payloads):
    return tuple((len(payload), hashlib.sha256(payload).hexdigest()) for payload in payloads)


def test_captured_external_objects_are_byte_exact_and_content_addressed():
    assert sorted(path.name for path in FIXTURE_ROOT.iterdir()) == [
        "linux-amd64-config.json",
        "linux-amd64-manifest.json",
        "root.json",
    ]
    for name, size_bytes, sha256 in OBJECT_FIXTURES:
        payload = (FIXTURE_ROOT / name).read_bytes()
        assert len(payload) == size_bytes
        assert hashlib.sha256(payload).hexdigest() == sha256
        json.loads(payload, parse_constant=lambda value: pytest.fail(value))


def test_captured_profile_is_exact_index_graph_and_four_layer_prefix():
    root, manifest, config = map(json.loads, _fixture_bytes())
    assert root["schemaVersion"] == 2
    assert root["mediaType"] == "application/vnd.oci.image.index.v1+json"
    assert len(root["manifests"]) == 14
    selected = [
        item
        for item in root["manifests"]
        if item.get("platform") == {"architecture": "amd64", "os": "linux"}
    ]
    assert len(selected) == 1
    assert selected[0]["digest"] == MANIFEST_DIGEST
    assert selected[0]["size"] == OBJECT_FIXTURES[1][1]
    assert manifest["config"] == {
        "digest": CONFIG_DIGEST,
        "mediaType": "application/vnd.oci.image.config.v1+json",
        "size": OBJECT_FIXTURES[2][1],
    }
    assert (
        tuple((item["digest"], item["size"], item["mediaType"]) for item in manifest["layers"])
        == BASE_LAYERS
    )
    assert config["architecture"] == "amd64"
    assert config["os"] == "linux"
    assert config["rootfs"]["type"] == "layers"
    assert tuple(config["rootfs"]["diff_ids"]) == BASE_DIFF_IDS


def test_private_parsers_project_the_exact_graph_instead_of_trusting_hashes():
    from human_feedback import runtime_base_ancestry as module

    root, manifest, config = _fixture_bytes()
    assert module._parse_laya_base_index(root) == (
        MANIFEST_DIGEST,
        OBJECT_FIXTURES[1][1],
        "application/vnd.oci.image.manifest.v1+json",
    )
    assert module._parse_laya_base_manifest(manifest) == (
        (
            CONFIG_DIGEST,
            OBJECT_FIXTURES[2][1],
            "application/vnd.oci.image.config.v1+json",
        ),
        BASE_LAYERS,
    )
    assert module._parse_laya_base_config(config) == BASE_DIFF_IDS


def test_aggregate_verifier_uses_all_three_semantic_projections(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    observed = []
    for name in (
        "_parse_laya_base_index",
        "_parse_laya_base_manifest",
        "_parse_laya_base_config",
    ):
        original = getattr(module, name)

        def spy(payload, *, _name=name, _original=original):
            observed.append((_name, payload))
            return _original(payload)

        monkeypatch.setattr(module, name, spy)
    evidence = module.verify_laya_runtime_base_ancestry_objects(plan, _streams())
    assert evidence.base_ancestry_verified is True
    assert tuple(name for name, _payload in observed) == (
        "_parse_laya_base_index",
        "_parse_laya_base_manifest",
        "_parse_laya_base_config",
    )
    assert tuple(payload for _name, payload in observed) == _fixture_bytes()


@pytest.mark.parametrize(
    "payload",
    [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1.0}',
        b'{"x":1} trailing',
        b'{"x":"\xc3\xa9"}',
        b"\xff",
    ],
)
def test_private_bounded_json_rejects_duplicate_noncanonical_and_trailing_payloads(
    payload,
):
    from human_feedback import runtime_base_ancestry as module

    with pytest.raises((TypeError, ValueError), match="JSON|duplicate|number|UTF|canonical|valid"):
        module._load_laya_base_ancestry_json(payload)


def test_private_bounded_json_accepts_every_exact_cap():
    from human_feedback import runtime_base_ancestry as module

    depth_16 = 0
    for _ in range(15):
        depth_16 = {"x": depth_16}
    nodes_512 = [{f"k{key}": key for key in range(30 if item == 0 else 31)} for item in range(16)]
    accepted = (
        depth_16,
        "x" * 4096,
        list(range(32)),
        {f"k{index}": index for index in range(64)},
        nodes_512,
    )
    for value in accepted:
        assert _bounded_json(module, value) == value


@pytest.mark.parametrize(
    "value, marker",
    [
        (lambda: _nested_json(16), "depth"),
        (lambda: "x" * 4097, "string"),
        (lambda: list(range(33)), "array"),
        (lambda: {f"k{index}": index for index in range(65)}, "key"),
        (
            lambda: [{f"k{key}": key for key in range(31)} for _ in range(16)],
            "node",
        ),
    ],
)
def test_private_bounded_json_rejects_each_cap_plus_one(value, marker):
    from human_feedback import runtime_base_ancestry as module

    with pytest.raises((TypeError, ValueError), match=f"JSON|{marker}|limit|valid"):
        _bounded_json(module, value())


def _nested_json(container_count):
    value = 0
    for _ in range(container_count):
        value = {"x": value}
    return value


def test_module_has_three_operation_pure_public_surface():
    from human_feedback import runtime_base_ancestry as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_functions == {
        "prepare_laya_runtime_base_ancestry_plan",
        "verify_laya_runtime_base_ancestry_objects",
        "canonical_laya_runtime_base_ancestry_summary_bytes",
    }
    assert module.__all__ == (
        "prepare_laya_runtime_base_ancestry_plan",
        "verify_laya_runtime_base_ancestry_objects",
        "canonical_laya_runtime_base_ancestry_summary_bytes",
    )
    assert {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    } == {
        "LayaRuntimeBaseAncestryPlan",
        "LayaRuntimeBaseAncestryEvidence",
    }
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imports & {
        "io",
        "os",
        "pathlib",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    calls = {
        (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert calls.isdisjoint(
        {
            "open",
            "read_bytes",
            "read_text",
            "write_bytes",
            "write_text",
            "system",
            "popen",
            "run",
            "__import__",
            "eval",
            "exec",
        }
    )
    assert tuple(inspect.signature(module.prepare_laya_runtime_base_ancestry_plan).parameters) == (
        "layer_evidence",
    )
    assert tuple(
        inspect.signature(module.verify_laya_runtime_base_ancestry_objects).parameters
    ) == (
        "plan",
        "object_streams",
    )
    assert module.MAX_BASE_ANCESTRY_CHUNK_BYTES == 16 * 1024
    assert module.MAX_BASE_ANCESTRY_CHUNKS == 64
    assert module.MAX_BASE_ANCESTRY_OBJECT_BYTES == 16 * 1024
    assert module.MAX_BASE_ANCESTRY_TOTAL_BYTES == 32 * 1024
    assert module.MAX_BASE_ANCESTRY_JSON_DEPTH == 16
    assert module.MAX_BASE_ANCESTRY_JSON_NODES == 512
    assert module.MAX_BASE_ANCESTRY_JSON_STRING_BYTES == 4 * 1024
    assert module.MAX_BASE_ANCESTRY_JSON_ARRAY_ITEMS == 32
    assert module.MAX_BASE_ANCESTRY_JSON_OBJECT_KEYS == 64


def test_exact_issued_pr22_evidence_prepares_identity_bound_conservative_plan(monkeypatch):
    module, predecessor, calls, plan = _prepared(monkeypatch)
    assert plan.layer_evidence is predecessor
    assert plan.runtime_identity is predecessor.runtime_identity
    assert plan.layer_plan is predecessor.plan
    assert plan.base_ancestry_verified is False
    assert calls
    assert all(call is predecessor for call in calls)
    assert type(plan).__name__ == "LayaRuntimeBaseAncestryPlan"
    assert ROOT_DIGEST not in repr(plan)
    assert MANIFEST_DIGEST not in repr(plan)
    assert CONFIG_DIGEST not in repr(plan)
    with pytest.raises((TypeError, ValueError), match="factory|seal|issued|valid"):
        replace(plan)


@pytest.mark.parametrize(
    "invalid",
    [None, "private-pr22-proxy", SimpleNamespace(oci_layer_diff_ids_verified=True)],
)
def test_plan_rejects_non_exact_predecessor_privately(invalid):
    from human_feedback import runtime_base_ancestry as module

    with pytest.raises(
        (TypeError, ValueError), match="PR22|layer|evidence|issued|valid"
    ) as captured:
        module.prepare_laya_runtime_base_ancestry_plan(invalid)
    _private_error(captured.value, "private-pr22-proxy")


def test_plan_rejects_clone_replace_subclass_and_object_new_predecessors(monkeypatch):
    from human_feedback import runtime_base_ancestry as module

    predecessor, _calls = _exact_pr22_evidence(monkeypatch)
    clone = _clone_dataclass(predecessor)

    class Derived(type(predecessor)):
        pass

    invalid = (clone, object.__new__(type(predecessor)), object.__new__(Derived))
    for candidate in invalid:
        with pytest.raises((TypeError, ValueError), match="PR22|layer|evidence|issued|valid"):
            module.prepare_laya_runtime_base_ancestry_plan(candidate)


@pytest.mark.parametrize("mutation", ["empty", "short", "reorder", "compressed", "diffid"])
def test_plan_rejects_empty_short_reordered_or_single_axis_child_profiles(monkeypatch, mutation):
    from human_feedback import runtime_base_ancestry as module

    predecessor, _calls = _exact_pr22_evidence(monkeypatch)
    if mutation == "empty":
        object.__setattr__(predecessor.plan, "layer_blobs", ())
        object.__setattr__(predecessor.plan, "declared_diff_ids", ())
    elif mutation == "short":
        object.__setattr__(predecessor.plan, "layer_blobs", predecessor.plan.layer_blobs[:4])
        object.__setattr__(
            predecessor.plan, "declared_diff_ids", predecessor.plan.declared_diff_ids[:4]
        )
    elif mutation == "reorder":
        blobs = predecessor.plan.layer_blobs
        object.__setattr__(predecessor.plan, "layer_blobs", (blobs[1], blobs[0], *blobs[2:]))
    elif mutation == "compressed":
        predecessor.plan.layer_blobs[0].digest = "sha256:" + "0" * 64
    else:
        diff_ids = predecessor.plan.declared_diff_ids
        object.__setattr__(
            predecessor.plan, "declared_diff_ids", ("sha256:" + "0" * 64, *diff_ids[1:])
        )
    with pytest.raises((TypeError, ValueError), match="prefix|layer|DiffID|PR22|valid"):
        module.prepare_laya_runtime_base_ancestry_plan(predecessor)


def test_exact_three_objects_issue_one_conservative_evidence(monkeypatch):
    module, predecessor, calls, plan, evidence = _verified(monkeypatch)
    assert evidence.plan is plan
    assert evidence.layer_evidence is predecessor
    assert evidence.runtime_identity is predecessor.runtime_identity
    assert evidence.base_ancestry_verified is True
    for claim in TRUE_PR22_CLAIMS:
        assert getattr(evidence, claim) is True
    for claim in CONSERVATIVE_FALSE_CLAIMS:
        assert getattr(evidence, claim) is False
    assert len(calls) >= 2
    assert all(call is predecessor for call in calls)
    private_values = (ROOT_DIGEST, MANIFEST_DIGEST, CONFIG_DIGEST, *BASE_DIFF_IDS)
    assert all(value not in repr(evidence) for value in private_values)


def test_summary_is_canonical_minimal_and_does_not_expand_authority(monkeypatch):
    module, predecessor, _calls, _plan, evidence = _verified(monkeypatch)
    summary = module.canonical_laya_runtime_base_ancestry_summary_bytes(evidence)
    assert type(summary) is bytes
    assert summary.endswith(b"\n") is False
    payload = json.loads(summary)
    assert set(payload) == {
        "schema_version",
        "plan_schema_version",
        "runtime_identity_schema_version",
        "runtime_identity_sha256",
        *TRUE_PR22_CLAIMS,
        *FALSE_PR22_CLAIMS,
        "base_ancestry_verified",
        *PR36_ONLY_FALSE_CLAIMS,
    }
    assert payload["base_ancestry_verified"] is True
    assert payload["runtime_identity_sha256"] == predecessor.runtime_identity.sha256
    for claim in (*FALSE_PR22_CLAIMS, *PR36_ONLY_FALSE_CLAIMS):
        assert payload[claim] is False
    for claim in TRUE_PR22_CLAIMS:
        assert payload[claim] is True
    forbidden = (
        "docker.io",
        "python:3.11",
        "linux-amd64",
        "manifest",
        "config",
        "layer",
        "diff_id",
        "recipe",
        "https://",
        "authorization",
        ROOT_DIGEST,
        MANIFEST_DIGEST,
        CONFIG_DIGEST,
        *BASE_DIFF_IDS,
    )
    rendered = summary.decode("ascii").lower()
    assert all(value.lower() not in rendered for value in forbidden)
    assert summary == json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def test_repr_and_public_errors_do_not_leak_payloads_urls_or_internal_commitments(
    monkeypatch,
):
    module, _predecessor, _calls, plan, evidence = _verified(monkeypatch)
    private_markers = (
        "https://private.invalid/registry?token=secret",
        ROOT_DIGEST,
        MANIFEST_DIGEST,
        CONFIG_DIGEST,
        *BASE_DIFF_IDS,
    )
    rendered = repr(plan) + repr(evidence)
    assert all(marker not in rendered for marker in private_markers)
    forged = _clone_dataclass(
        evidence,
        runtime_identity=SimpleNamespace(
            schema_version=private_markers[0],
            sha256="private-runtime-identity-commitment",
        ),
    )
    with pytest.raises((TypeError, ValueError), match="evidence|identity|issued|valid") as captured:
        module.canonical_laya_runtime_base_ancestry_summary_bytes(forged)
    _private_error(captured.value, *private_markers, "private-runtime-identity-commitment")


@pytest.mark.parametrize("position", range(3))
def test_each_missing_extra_reordered_or_mutated_object_fails_closed(monkeypatch, position):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    payloads = list(_fixture_bytes())
    payloads[position] = payloads[position][:-1] + bytes([payloads[position][-1] ^ 1])
    with pytest.raises((TypeError, ValueError), match="object|digest|size|profile|stream|valid"):
        module.verify_laya_runtime_base_ancestry_objects(plan, _streams(tuple(payloads)))


def test_object_stream_tuple_cardinality_order_and_type_are_exact(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    exact = _fixture_bytes()
    invalid = (
        exact,
        _streams(exact[:2]),
        (*_streams(exact), iter((b"extra",))),
        tuple(reversed(_streams(exact))),
        (iter((exact[0],)), iter((exact[1],)), "not-a-stream"),
    )
    for candidate in invalid:
        with pytest.raises(
            (TypeError, ValueError), match="object|stream|profile|count|order|valid"
        ):
            module.verify_laya_runtime_base_ancestry_objects(plan, candidate)


@pytest.mark.parametrize(
    "invalid_chunk",
    [b"", bytearray(b"x"), memoryview(b"x"), "x", 1, None],
)
def test_chunks_are_nonempty_exact_bytes(monkeypatch, invalid_chunk):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    root, manifest, config = _fixture_bytes()
    streams = (iter((invalid_chunk,)), iter((manifest,)), iter((config,)))
    with pytest.raises((TypeError, ValueError), match="chunk|bytes|stream|object"):
        module.verify_laya_runtime_base_ancestry_objects(plan, streams)


def test_chunk_cap_plus_one_stops_before_next_chunk_and_later_objects(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    maximum = module.MAX_BASE_ANCESTRY_CHUNK_BYTES
    later_touched = False

    class Oversized:
        def __iter__(self):
            yield b"x" * (maximum + 1)
            raise AssertionError("private-root-trailing-sentinel")

    def later():
        nonlocal later_touched
        later_touched = True
        raise AssertionError("private-later-object-consumed")
        yield b"unreachable"

    with pytest.raises((TypeError, ValueError), match="chunk|limit|size|object") as captured:
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (Oversized(), later(), later()),
        )
    assert later_touched is False
    _private_error(
        captured.value,
        "private-root-trailing-sentinel",
        "private-later-object-consumed",
    )


def test_private_stream_consumer_accepts_all_streaming_caps_exactly():
    from human_feedback import runtime_base_ancestry as module

    chunked = b"a" * 64
    payloads = (chunked, b"b" * 16384, b"c" * 16320)
    streams = (iter((b"a",) * 64), iter((payloads[1],)), iter((payloads[2],)))
    assert sum(map(len, payloads)) == 32768
    assert (
        module._consume_laya_base_ancestry_object_streams(
            streams,
            _test_object_specs(payloads),
        )
        == payloads
    )


def test_private_stream_consumer_rejects_chunk_65_without_reading_chunk_66():
    from human_feedback import runtime_base_ancestry as module

    payloads = (b"a" * 65, b"b", b"c")

    class SixtyFiveChunks:
        def __init__(self):
            self.requests = 0
            self.trailing_touched = False

        def __iter__(self):
            return self

        def __next__(self):
            self.requests += 1
            if self.requests <= 65:
                return b"a"
            self.trailing_touched = True
            raise AssertionError("private-chunk-66-consumed")

    first = SixtyFiveChunks()
    later = _hostile_never_iterated("private-later-cap-object-consumed")
    with pytest.raises((TypeError, ValueError), match="chunk|count|limit|object") as captured:
        module._consume_laya_base_ancestry_object_streams(
            (first, later, later),
            _test_object_specs(payloads),
        )
    assert first.requests == 65
    assert first.trailing_touched is False
    assert later.touched is False
    _private_error(captured.value, "private-chunk-66-consumed")


def test_private_stream_consumer_rejects_object_cap_plus_one_across_chunks():
    from human_feedback import runtime_base_ancestry as module

    authorized = b"a" * 16384
    payloads = (authorized, b"b", b"c")
    first = iter((b"a" * 8192, b"a" * 8192, b"x"))
    later = _hostile_never_iterated("private-later-object-cap-consumed")
    with pytest.raises((TypeError, ValueError), match="object|size|limit") as captured:
        module._consume_laya_base_ancestry_object_streams(
            (first, later, later),
            _test_object_specs(payloads),
        )
    assert later.touched is False
    _private_error(captured.value, "private-later-object-cap-consumed")


def test_private_stream_consumer_rejects_aggregate_cap_plus_one():
    from human_feedback import runtime_base_ancestry as module

    payloads = (b"a" * 16384, b"b" * 16384, b"c")
    with pytest.raises((TypeError, ValueError), match="aggregate|total|limit|size"):
        module._consume_laya_base_ancestry_object_streams(
            tuple(iter((payload,)) for payload in payloads),
            _test_object_specs(payloads),
        )


def test_exact_payload_followed_by_extra_chunk_is_rejected_at_eof(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    root, manifest, config = _fixture_bytes()
    with pytest.raises((TypeError, ValueError), match="trailing|size|digest|object|stream"):
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (iter((root, b"extra")), iter((manifest,)), iter((config,))),
        )


def test_iterator_exception_after_exact_payload_revokes_session(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    root, manifest, config = _fixture_bytes()

    def failing_after_payload():
        yield root
        raise RuntimeError("private-iterator-failure")

    later = _hostile_never_iterated("private-later-iterator-object-consumed")
    with pytest.raises((TypeError, ValueError), match="stream|iterator|object|valid") as captured:
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (failing_after_payload(), later, later),
        )
    assert later.touched is False
    _private_error(
        captured.value,
        "private-iterator-failure",
        "private-later-iterator-object-consumed",
    )


def test_stream_preflight_rejects_outer_container_before_nested_consumption(monkeypatch):
    factories = (
        lambda value: [value, value, value],
        lambda value: iter((value, value, value)),
        lambda value: value,
    )
    for factory in factories:
        module, _predecessor, _calls, plan = _prepared(monkeypatch)
        hostile = _hostile_never_iterated("private-preflight-stream-consumed")
        candidate = factory(hostile)
        with pytest.raises((TypeError, ValueError), match="tuple|stream|object|profile|valid"):
            module.verify_laya_runtime_base_ancestry_objects(plan, candidate)
        assert hostile.touched is False


def test_first_object_failure_never_consumes_later_object_streams(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    root, _manifest, _config = _fixture_bytes()
    later_touched = False

    def later():
        nonlocal later_touched
        later_touched = True
        raise AssertionError("private-later-object-consumed")
        yield b"unreachable"

    with pytest.raises(
        (TypeError, ValueError), match="object|digest|size|profile|valid"
    ) as captured:
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (iter((root[:-1],)), later(), later()),
        )
    assert later_touched is False
    _private_error(captured.value, "private-later-object-consumed")


def test_empty_current_object_stops_before_later_objects(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    later = _hostile_never_iterated("private-later-empty-object-consumed")
    with pytest.raises((TypeError, ValueError), match="empty|object|stream|size|valid") as captured:
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (iter(()), later, later),
        )
    assert later.touched is False
    _private_error(captured.value, "private-later-empty-object-consumed")


@pytest.mark.parametrize(
    "payload",
    [
        b'{"schemaVersion":2,"schemaVersion":2}',
        b'{"schemaVersion":NaN}',
        b'{"schemaVersion":Infinity}',
        b'{"schemaVersion":2} trailing',
        b"\xff",
        (b'{"x":' * 80) + b"0" + (b"}" * 80),
    ],
)
def test_duplicate_nonfinite_trailing_utf8_and_depth_payloads_fail_closed(monkeypatch, payload):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    _root, manifest, config = _fixture_bytes()
    with pytest.raises((TypeError, ValueError), match="JSON|object|digest|size|profile|valid"):
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (iter((payload,)), iter((manifest,)), iter((config,))),
        )


@pytest.mark.parametrize(
    "mutation",
    ["absent", "duplicate", "wrong-os", "wrong-arch", "digest", "size", "media", "extra"],
)
def test_private_index_projection_rejects_platform_and_edge_mutations(mutation):
    from human_feedback import runtime_base_ancestry as module

    parsed = json.loads(_fixture_bytes()[0])
    position = next(
        index
        for index, item in enumerate(parsed["manifests"])
        if item.get("platform") == {"architecture": "amd64", "os": "linux"}
    )
    selected = parsed["manifests"][position]
    if mutation == "absent":
        parsed["manifests"].pop(position)
    elif mutation == "duplicate":
        parsed["manifests"].append(copy.deepcopy(selected))
    elif mutation == "wrong-os":
        selected["platform"]["os"] = "windows"
    elif mutation == "wrong-arch":
        selected["platform"]["architecture"] = "arm64"
    elif mutation == "digest":
        selected["digest"] = "sha256:" + "0" * 64
    elif mutation == "size":
        selected["size"] += 1
    elif mutation == "media":
        selected["mediaType"] = "application/vnd.docker.distribution.manifest.v2+json"
    else:
        parsed["unexpected"] = True
    payload = json.dumps(parsed, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    with pytest.raises((TypeError, ValueError), match="index|platform|manifest|descriptor|valid"):
        module._parse_laya_base_index(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        "config-digest",
        "config-size",
        "config-media",
        "layer-digest",
        "layer-size",
        "layer-media",
        "layer-reorder",
        "layer-extra",
        "layer-zero",
        "extra",
    ],
)
def test_private_manifest_projection_rejects_edges_and_layer_mutations(mutation):
    from human_feedback import runtime_base_ancestry as module

    parsed = json.loads(_fixture_bytes()[1])
    if mutation == "config-digest":
        parsed["config"]["digest"] = "sha256:" + "0" * 64
    elif mutation == "config-size":
        parsed["config"]["size"] += 1
    elif mutation == "config-media":
        parsed["config"]["mediaType"] = "application/json"
    elif mutation == "layer-digest":
        parsed["layers"][0]["digest"] = "sha256:" + "0" * 64
    elif mutation == "layer-size":
        parsed["layers"][0]["size"] += 1
    elif mutation == "layer-media":
        parsed["layers"][0]["mediaType"] = "application/octet-stream"
    elif mutation == "layer-reorder":
        parsed["layers"][0], parsed["layers"][1] = (
            parsed["layers"][1],
            parsed["layers"][0],
        )
    elif mutation == "layer-extra":
        parsed["layers"].append(copy.deepcopy(parsed["layers"][0]))
    elif mutation == "layer-zero":
        parsed["layers"] = []
    else:
        parsed["unexpected"] = True
    payload = json.dumps(parsed, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    with pytest.raises((TypeError, ValueError), match="manifest|config|layer|descriptor|valid"):
        module._parse_laya_base_manifest(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        "architecture",
        "os",
        "rootfs-type",
        "diffid",
        "diffid-reorder",
        "diffid-extra",
        "diffid-zero",
        "extra",
    ],
)
def test_private_config_projection_rejects_platform_and_diffid_mutations(mutation):
    from human_feedback import runtime_base_ancestry as module

    parsed = json.loads(_fixture_bytes()[2])
    if mutation == "architecture":
        parsed["architecture"] = "arm64"
    elif mutation == "os":
        parsed["os"] = "windows"
    elif mutation == "rootfs-type":
        parsed["rootfs"]["type"] = "not-layers"
    elif mutation == "diffid":
        parsed["rootfs"]["diff_ids"][0] = "sha256:" + "0" * 64
    elif mutation == "diffid-reorder":
        values = parsed["rootfs"]["diff_ids"]
        values[0], values[1] = values[1], values[0]
    elif mutation == "diffid-extra":
        parsed["rootfs"]["diff_ids"].append(parsed["rootfs"]["diff_ids"][0])
    elif mutation == "diffid-zero":
        parsed["rootfs"]["diff_ids"] = []
    else:
        parsed["unexpected"] = True
    payload = json.dumps(parsed, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    with pytest.raises((TypeError, ValueError), match="config|platform|rootfs|DiffID|valid"):
        module._parse_laya_base_config(payload)


def test_private_projections_ignore_annotations_and_history_as_authority():
    from human_feedback import runtime_base_ancestry as module

    root, manifest, config = map(json.loads, _fixture_bytes())
    selected = next(
        item
        for item in root["manifests"]
        if item.get("platform") == {"architecture": "amd64", "os": "linux"}
    )
    selected["annotations"] = {
        "org.opencontainers.image.version": "moving-latest",
        "org.opencontainers.image.source": "https://private.invalid/token",
    }
    manifest["annotations"] = {
        "org.opencontainers.image.base.digest": "sha256:" + "f" * 64,
        "org.opencontainers.image.version": "mobile-tag",
    }
    config["history"] = [{"created_by": "FROM hostile:latest"}]

    def encode(value):
        return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")

    assert module._parse_laya_base_index(encode(root))[0] == MANIFEST_DIGEST
    assert module._parse_laya_base_manifest(encode(manifest))[0][0] == CONFIG_DIGEST
    assert module._parse_laya_base_config(encode(config)) == BASE_DIFF_IDS


@pytest.mark.parametrize("mutation", ["absent", "duplicate", "wrong", "annotation"])
def test_platform_selection_cannot_fallback_to_tags_or_annotations(monkeypatch, mutation):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    root, manifest, config = _fixture_bytes()
    parsed = json.loads(root)
    position = next(
        index
        for index, item in enumerate(parsed["manifests"])
        if item.get("platform") == {"architecture": "amd64", "os": "linux"}
    )
    if mutation == "absent":
        parsed["manifests"].pop(position)
    elif mutation == "duplicate":
        parsed["manifests"].append(parsed["manifests"][position])
    elif mutation == "wrong":
        parsed["manifests"][position]["platform"]["architecture"] = "arm64"
    else:
        parsed["manifests"][position]["digest"] = "sha256:" + "0" * 64
        parsed["manifests"][position]["annotations"][
            "org.opencontainers.image.version"
        ] = "3.11.10-slim-bookworm"
    mutated = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("ascii")
    with pytest.raises(
        (TypeError, ValueError), match="platform|manifest|object|digest|profile|valid"
    ):
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (iter((mutated,)), iter((manifest,)), iter((config,))),
        )


@pytest.mark.parametrize("source", ["manifest-annotation", "config-history", "mobile-tag"])
def test_annotation_history_and_mobile_tag_never_authorize_ancestry(monkeypatch, source):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    root, manifest, config = _fixture_bytes()
    if source == "manifest-annotation":
        parsed = json.loads(manifest)
        parsed["config"]["digest"] = "sha256:" + "0" * 64
        parsed["annotations"]["org.opencontainers.image.base.digest"] = CONFIG_DIGEST
        manifest = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("ascii")
    elif source == "config-history":
        parsed = json.loads(config)
        parsed["rootfs"]["diff_ids"][0] = "sha256:" + "0" * 64
        parsed["history"][0]["comment"] = BASE_DIFF_IDS[0]
        config = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("ascii")
    else:
        parsed = json.loads(root)
        selected = next(
            item
            for item in parsed["manifests"]
            if item.get("platform") == {"architecture": "amd64", "os": "linux"}
        )
        selected["digest"] = "python:3.11.10-slim-bookworm"
        root = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("ascii")
    with pytest.raises(
        (TypeError, ValueError),
        match="annotation|history|tag|manifest|config|digest|object|valid",
    ):
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (iter((root,)), iter((manifest,)), iter((config,))),
        )


@pytest.mark.parametrize("target", ["manifest-config", "manifest-layer", "config-diffid"])
def test_manifest_config_and_dual_prefix_mix_and_match_fail_closed(monkeypatch, target):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    root, manifest, config = _fixture_bytes()
    if target.startswith("manifest"):
        parsed = json.loads(manifest)
        if target == "manifest-config":
            parsed["config"]["digest"] = "sha256:" + "0" * 64
        else:
            parsed["layers"][0]["digest"] = "sha256:" + "0" * 64
        manifest = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("ascii")
    else:
        parsed = json.loads(config)
        parsed["rootfs"]["diff_ids"][0] = "sha256:" + "0" * 64
        config = json.dumps(parsed, separators=(",", ":"), sort_keys=True).encode("ascii")
    with pytest.raises(
        (TypeError, ValueError), match="manifest|config|prefix|DiffID|digest|object|valid"
    ):
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (iter((root,)), iter((manifest,)), iter((config,))),
        )


def test_success_consumes_plan_once_and_replay_fails_before_stream_consumption(monkeypatch):
    module, _predecessor, _calls, plan, _evidence = _verified(monkeypatch)
    touched = False

    def hostile():
        nonlocal touched
        touched = True
        raise AssertionError("private-replay-consumed")
        yield b"unreachable"

    with pytest.raises(
        (TypeError, ValueError), match="session|consumed|replay|plan|valid"
    ) as captured:
        module.verify_laya_runtime_base_ancestry_objects(plan, (hostile(), hostile(), hostile()))
    assert touched is False
    _private_error(captured.value, "private-replay-consumed")


def test_failed_session_is_revoked_and_cannot_be_reused(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    root, manifest, config = _fixture_bytes()
    with pytest.raises((TypeError, ValueError)):
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (iter((root[:-1],)), iter((manifest,)), iter((config,))),
        )
    touched = False

    def hostile():
        nonlocal touched
        touched = True
        raise AssertionError("private-revoked-plan-consumed")
        yield b"unreachable"

    with pytest.raises(
        (TypeError, ValueError), match="session|consumed|revoked|plan|valid"
    ) as captured:
        module.verify_laya_runtime_base_ancestry_objects(plan, (hostile(), hostile(), hostile()))
    assert touched is False
    _private_error(captured.value, "private-revoked-plan-consumed")


def test_plan_and_evidence_clones_replace_and_unissued_values_never_gain_authority(monkeypatch):
    module, _predecessor, _calls, plan, evidence = _verified(monkeypatch)
    candidates = (
        object.__new__(type(evidence)),
        _clone_dataclass(evidence),
    )
    for candidate in candidates:
        with pytest.raises((TypeError, ValueError), match="evidence|issued|seal|valid"):
            module.canonical_laya_runtime_base_ancestry_summary_bytes(candidate)
    with pytest.raises((TypeError, ValueError), match="evidence|issued|seal|valid"):
        replace(evidence)
    plan_clone = _clone_dataclass(plan)
    with pytest.raises((TypeError, ValueError), match="plan|issued|session|valid"):
        module.verify_laya_runtime_base_ancestry_objects(plan_clone, _streams())


def test_mutated_issued_plan_fails_before_any_stream_is_consumed(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    object.__setattr__(
        plan,
        "runtime_identity",
        SimpleNamespace(schema_version="private-mutated-plan", sha256="0" * 64),
    )
    hostile = _hostile_never_iterated("private-mutated-plan-stream-consumed")
    with pytest.raises(
        (TypeError, ValueError), match="plan|identity|issued|binding|valid"
    ) as captured:
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (hostile, hostile, hostile),
        )
    assert hostile.touched is False
    _private_error(
        captured.value,
        "private-mutated-plan",
        "private-mutated-plan-stream-consumed",
    )


def test_predecessor_drift_after_plan_issuance_fails_before_streams(monkeypatch):
    module, predecessor, _calls, plan = _prepared(monkeypatch)
    predecessor.plan.layer_blobs[0].digest = "sha256:" + "0" * 64
    hostile = _hostile_never_iterated("private-drifted-predecessor-stream-consumed")
    with pytest.raises(
        (TypeError, ValueError), match="PR22|layer|prefix|drift|plan|valid"
    ) as captured:
        module.verify_laya_runtime_base_ancestry_objects(
            plan,
            (hostile, hostile, hostile),
        )
    assert hostile.touched is False
    _private_error(captured.value, "private-drifted-predecessor-stream-consumed")


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_ancestry_verified", False),
        ("origin_verified", True),
        (
            "runtime_identity",
            SimpleNamespace(schema_version="private", sha256="0" * 64),
        ),
        ("plan", None),
    ],
)
def test_mutated_issued_evidence_fails_summary_semantic_revalidation(monkeypatch, field, value):
    module, _predecessor, _calls, _plan, evidence = _verified(monkeypatch)
    object.__setattr__(evidence, field, value)
    with pytest.raises(
        (TypeError, ValueError), match="evidence|claim|identity|plan|issued|valid"
    ) as captured:
        module.canonical_laya_runtime_base_ancestry_summary_bytes(evidence)
    _private_error(captured.value, "private")


def test_copy_deepcopy_pickle_subclass_and_proxy_cannot_replay_evidence(monkeypatch):
    module, _predecessor, _calls, _plan, evidence = _verified(monkeypatch)
    candidates = [copy.copy(evidence), copy.deepcopy(evidence)]
    try:
        candidates.append(pickle.loads(pickle.dumps(evidence)))
    except (pickle.PickleError, TypeError, ValueError, AttributeError):
        pass

    class Derived(type(evidence)):
        pass

    candidates.extend(
        (
            object.__new__(Derived),
            SimpleNamespace(
                schema_version=evidence.schema_version,
                base_ancestry_verified=True,
            ),
        )
    )
    assert candidates
    for candidate in candidates:
        assert candidate is not evidence
        with pytest.raises((TypeError, ValueError), match="evidence|issued|seal|type|valid"):
            module.canonical_laya_runtime_base_ancestry_summary_bytes(candidate)


def test_copy_pickle_subclass_and_proxy_plans_fail_before_consumption(monkeypatch):
    module, _predecessor, _calls, plan = _prepared(monkeypatch)
    candidates = [copy.copy(plan), copy.deepcopy(plan)]
    try:
        candidates.append(pickle.loads(pickle.dumps(plan)))
    except (pickle.PickleError, TypeError, ValueError, AttributeError):
        pass

    class Derived(type(plan)):
        pass

    candidates.extend((object.__new__(Derived), SimpleNamespace(plan=plan)))
    for candidate in candidates:
        assert candidate is not plan
        hostile = _hostile_never_iterated("private-forged-plan-stream-consumed")
        with pytest.raises((TypeError, ValueError), match="plan|issued|type|session|valid"):
            module.verify_laya_runtime_base_ancestry_objects(
                candidate,
                (hostile, hostile, hostile),
            )
        assert hostile.touched is False


def test_cross_plan_evidence_binding_is_rejected(monkeypatch):
    module, _predecessor, _calls, _plan, evidence = _verified(monkeypatch)
    _module, _other_predecessor, _other_calls, other_plan = _prepared(monkeypatch)
    mixed = _clone_dataclass(evidence, plan=other_plan)
    with pytest.raises((TypeError, ValueError), match="evidence|plan|session|binding|issued|valid"):
        module.canonical_laya_runtime_base_ancestry_summary_bytes(mixed)


def test_issuance_registries_do_not_retain_plan_or_evidence_after_gc(monkeypatch):
    module, predecessor, calls, plan, evidence = _verified(monkeypatch)
    plan_type = type(plan)
    plan_identity = id(plan)
    plan_ref = weakref.ref(plan)
    evidence_ref = weakref.ref(evidence)
    del evidence, plan, predecessor, calls
    gc.collect()
    assert evidence_ref() is None
    assert plan_ref() is None

    reused = None
    for _ in range(10000):
        candidate = object.__new__(plan_type)
        if id(candidate) == plan_identity:
            reused = candidate
            break
    if reused is not None:
        hostile = _hostile_never_iterated("private-reused-id-stream-consumed")
        with pytest.raises((TypeError, ValueError), match="plan|issued|session|valid"):
            module.verify_laya_runtime_base_ancestry_objects(
                reused,
                (hostile, hostile, hostile),
            )
        assert hostile.touched is False


def test_module_has_no_product_callers_or_lateral_pr35_dependency():
    repository = Path(__file__).parents[1]
    owner = repository / "src" / "human_feedback" / "runtime_base_ancestry.py"
    forbidden_symbols = {
        "prepare_laya_runtime_base_ancestry_plan",
        "verify_laya_runtime_base_ancestry_objects",
        "canonical_laya_runtime_base_ancestry_summary_bytes",
        "human_feedback.runtime_base_ancestry",
    }
    offenders = []
    for relative_root in ("backend", "src", "scripts"):
        root = repository / relative_root
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if path == owner:
                continue
            source = path.read_text(encoding="utf-8")
            if any(symbol in source for symbol in forbidden_symbols):
                offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []
    if owner.is_file():
        source = owner.read_text(encoding="utf-8")
        assert "runtime_provenance" not in source
        assert "LayaRuntimeProvenance" not in source
        assert "PR35" not in source


def test_nonfinite_values_are_not_accidentally_normalized_by_test_oracle():
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            json.dumps({"value": value}, allow_nan=False)
