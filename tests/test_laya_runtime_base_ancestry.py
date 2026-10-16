import ast
import copy
import gc
import hashlib
import inspect
import json
import math
import pickle
import threading
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
UTF8_KEY_AT_CAP = "é" * 2048
UTF8_KEY_OVER_CAP = UTF8_KEY_AT_CAP + "x"


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


def _canonical_json(value) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _canonical_json_padded_to(value, padding, target_size) -> bytes:
    padding.clear()
    for position in range(8):
        payload = _canonical_json(value)
        if len(payload) == target_size:
            return payload
        assert len(payload) < target_size
        key = f"padding-{position}"
        padding[key] = ""
        payload = _canonical_json(value)
        assert len(payload) <= target_size
        padding[key] = "x" * min(4096, target_size - len(payload))
    payload = _canonical_json(value)
    assert len(payload) == target_size
    return payload


def _exact_pr22_evidence(monkeypatch):
    """Issue PR22 evidence and bind PR36 to a small content-addressed OCI graph."""

    from human_feedback import runtime_base_ancestry, runtime_oci_layers
    from tests.test_laya_runtime_oci_layers import _issued_layer_evidence

    evidence = _issued_layer_evidence(monkeypatch).evidence
    plan = evidence.plan
    base_layers = tuple(
        (blob.digest, blob.size_bytes, blob.media_type) for blob in plan.layer_blobs[:4]
    )
    base_diff_ids = plan.declared_diff_ids[:4]

    config_padding = {}
    config_value = {
        "architecture": "amd64",
        "config": config_padding,
        "created": "1970-01-01T00:00:00Z",
        "history": [{"comment": "synthetic issued profile"}],
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": list(base_diff_ids)},
    }
    config_payload = _canonical_json_padded_to(config_value, config_padding, 5295)
    config_digest = hashlib.sha256(config_payload).hexdigest()

    manifest_padding = {}
    manifest_value = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {
            "digest": "sha256:" + config_digest,
            "size": len(config_payload),
            "mediaType": "application/vnd.oci.image.config.v1+json",
        },
        "layers": [
            {"digest": digest, "size": size, "mediaType": media_type}
            for digest, size, media_type in base_layers
        ],
        "annotations": manifest_padding,
    }
    manifest_payload = _canonical_json_padded_to(manifest_value, manifest_padding, 1752)
    manifest_digest = hashlib.sha256(manifest_payload).hexdigest()

    selected = {
        "digest": "sha256:" + manifest_digest,
        "size": len(manifest_payload),
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "platform": {"architecture": "amd64", "os": "linux"},
        "annotations": {},
    }
    decoys = [
        {
            "digest": f"sha256:{position + 1:064x}",
            "size": 1,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "platform": {"architecture": f"other-{position:02d}", "os": "linux"},
        }
        for position in range(13)
    ]
    index_payload = _canonical_json(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [selected, *decoys],
        }
    )
    object_payloads = (index_payload, manifest_payload, config_payload)
    object_specs = tuple(
        (len(payload), hashlib.sha256(payload).hexdigest()) for payload in object_payloads
    )

    monkeypatch.setattr(runtime_base_ancestry, "_BASE_LAYERS", base_layers)
    monkeypatch.setattr(runtime_base_ancestry, "_BASE_DIFF_IDS", base_diff_ids)
    monkeypatch.setattr(runtime_base_ancestry, "_ROOT_DIGEST", object_specs[0][1])
    monkeypatch.setattr(runtime_base_ancestry, "_MANIFEST_DIGEST", manifest_digest)
    monkeypatch.setattr(runtime_base_ancestry, "_CONFIG_DIGEST", config_digest)
    monkeypatch.setattr(runtime_base_ancestry, "_OBJECT_SPECS", object_specs)
    monkeypatch.setitem(globals(), "_fixture_bytes", lambda: object_payloads)

    calls = []
    canonical_predecessor = (
        runtime_oci_layers.canonical_laya_runtime_oci_layer_diff_ids_summary_bytes
    )

    def observe_predecessor(candidate):
        calls.append(candidate)
        return canonical_predecessor(candidate)

    monkeypatch.setattr(
        runtime_oci_layers,
        "canonical_laya_runtime_oci_layer_diff_ids_summary_bytes",
        observe_predecessor,
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
        {UTF8_KEY_AT_CAP: 0},
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
        (lambda: {UTF8_KEY_OVER_CAP: 0}, "key"),
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

    assert len(UTF8_KEY_AT_CAP.encode("utf-8")) == 4096
    assert len(UTF8_KEY_OVER_CAP.encode("utf-8")) == 4097
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
    expected_public_callables = {
        "LayaRuntimeBaseAncestryPlan",
        "LayaRuntimeBaseAncestryEvidence",
        "prepare_laya_runtime_base_ancestry_plan",
        "verify_laya_runtime_base_ancestry_objects",
        "canonical_laya_runtime_base_ancestry_summary_bytes",
    }
    assert {
        name for name, value in vars(module).items() if not name.startswith("_") and callable(value)
    } == expected_public_callables
    assert set(module.__all__) == expected_public_callables
    assert len(module.__all__) == len(expected_public_callables)
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
    private_values = (
        "debian:bookworm-slim",
        "3.11.10-slim-bookworm",
        "https://hub.docker.com/_/python",
        "https://github.com/docker-library/python.git",
        "A035C8C19219BA821ECEA86B64E628F8D684696D",
        "PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        ROOT_DIGEST,
        MANIFEST_DIGEST,
        CONFIG_DIGEST,
        *BASE_DIFF_IDS,
    )
    rendered = summary.decode("ascii").lower()
    assert all(value.lower() not in rendered for value in private_values)
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


def test_planner_verifier_and_private_parsers_emit_only_suppressed_generic_errors(
    monkeypatch,
):
    from human_feedback import runtime_base_ancestry as module

    private_markers = (
        "https://private.invalid/registry?token=secret",
        "Bearer private-auth-token",
        "C:\\private\\runtime\\base.json",
        "private-ancestry-marker",
    )
    hostile_value = SimpleNamespace(
        url=private_markers[0],
        authorization=private_markers[1],
        path=private_markers[2],
        marker=private_markers[3],
    )
    parser_payload = json.dumps(
        {
            "url": private_markers[0],
            "authorization": private_markers[1],
            "path": private_markers[2],
            "marker": private_markers[3],
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    hostile_stream = _hostile_never_iterated("private-error-stream-consumed")
    operations = (
        lambda: module.prepare_laya_runtime_base_ancestry_plan(hostile_value),
        lambda: module.verify_laya_runtime_base_ancestry_objects(
            hostile_value,
            (hostile_stream, hostile_stream, hostile_stream),
        ),
        lambda: module._parse_laya_base_index(parser_payload),
        lambda: module._parse_laya_base_manifest(parser_payload),
        lambda: module._parse_laya_base_config(parser_payload),
    )
    for operation in operations:
        with pytest.raises(
            (TypeError, ValueError),
            match="plan|PR22|object|index|manifest|config|validation|failed|valid",
        ) as captured:
            operation()
        _private_error(
            captured.value,
            *private_markers,
            "private-error-stream-consumed",
        )
    assert hostile_stream.touched is False


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


def test_concurrent_consumers_claim_one_plan_exactly_once_before_streams(monkeypatch):
    from human_feedback import runtime_base_ancestry as module

    _module, _predecessor, _calls, plan = _prepared(monkeypatch)
    original_record = module._ISSUED_PLANS[id(plan)]
    check_barrier = threading.Barrier(2)

    class CoordinatedRecord:
        reference = original_record.reference
        semantics = original_record.semantics

        @property
        def active(self):
            observed = original_record.active
            try:
                check_barrier.wait(timeout=1.0)
            except threading.BrokenBarrierError:
                pass
            return observed

        @active.setter
        def active(self, value):
            original_record.active = value

    monkeypatch.setitem(module._ISSUED_PLANS, id(plan), CoordinatedRecord())
    payloads = _fixture_bytes()
    streams_consumed = [False, False]
    outcomes = [None, None]

    def streams(position):
        def tracked(payload):
            streams_consumed[position] = True
            yield payload

        return tuple(tracked(payload) for payload in payloads)

    def consume(position):
        try:
            outcomes[position] = module.verify_laya_runtime_base_ancestry_objects(
                plan,
                streams(position),
            )
        except Exception as error:  # the losing public call is the expected outcome
            outcomes[position] = error

    workers = tuple(
        threading.Thread(target=consume, args=(position,), daemon=True) for position in range(2)
    )
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=5.0)
    assert all(not worker.is_alive() for worker in workers)

    winners = [
        position
        for position, outcome in enumerate(outcomes)
        if type(outcome) is module.LayaRuntimeBaseAncestryEvidence
    ]
    losers = [
        position
        for position, outcome in enumerate(outcomes)
        if isinstance(outcome, (TypeError, ValueError))
    ]
    assert len(winners) == 1
    assert len(losers) == 1
    assert streams_consumed[winners[0]] is True
    assert streams_consumed[losers[0]] is False
    _private_error(outcomes[losers[0]], "private-concurrent-plan-stream")


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


def test_issuance_registries_cleanup_and_deterministically_reject_stale_id_records(
    monkeypatch,
):
    from human_feedback import runtime_base_ancestry as module

    registry_names = ("_ISSUED_PLANS", "_ISSUED_EVIDENCE")
    registries = {name: getattr(module, name) for name in registry_names}
    assert all(type(registry) is dict for registry in registries.values())
    gc.collect()
    baseline = {name: len(registry) for name, registry in registries.items()}

    _module, first_predecessor, first_calls, first_plan, first_evidence = _verified(monkeypatch)
    first_values = {
        "_ISSUED_PLANS": first_plan,
        "_ISSUED_EVIDENCE": first_evidence,
    }
    for name, value in first_values.items():
        registry = registries[name]
        assert len(registry) == baseline[name] + 1
        record = registry[id(value)]
        assert type(record.reference) is weakref.ReferenceType
        assert record.reference() is value
    del name, value, registry, record

    _module, second_predecessor, second_calls, second_plan, second_evidence = _verified(monkeypatch)
    evidence_registry = registries["_ISSUED_EVIDENCE"]
    first_identity = id(first_evidence)
    first_reference = weakref.ref(first_evidence)
    expired_record = evidence_registry[first_identity]
    replacement_record = evidence_registry[id(second_evidence)]

    # Deterministically simulate reuse of the expired numeric identity.  The
    # stale weakref callback may remove only its own exact record.
    evidence_registry[first_identity] = replacement_record
    del first_values, first_evidence, first_plan, first_predecessor, first_calls
    gc.collect()
    assert first_reference() is None
    assert expired_record.reference() is None
    assert evidence_registry[first_identity] is replacement_record
    evidence_registry.pop(first_identity)
    del expired_record

    # A dict key match cannot authorize an alien exact-class value when the
    # record's weakref resolves to a different issued object.
    alien_evidence = _clone_dataclass(second_evidence)
    alien_identity = id(alien_evidence)
    evidence_registry[alien_identity] = replacement_record
    try:
        with pytest.raises((TypeError, ValueError), match="evidence|issued|seal|valid"):
            module.canonical_laya_runtime_base_ancestry_summary_bytes(alien_evidence)
    finally:
        if evidence_registry.get(alien_identity) is replacement_record:
            evidence_registry.pop(alien_identity)

    plan_registry = registries["_ISSUED_PLANS"]
    _module, pending_predecessor, pending_calls, pending_plan = _prepared(monkeypatch)
    pending_record = plan_registry[id(pending_plan)]
    alien_plan = _clone_dataclass(pending_plan)
    alien_plan_identity = id(alien_plan)
    plan_registry[alien_plan_identity] = pending_record
    hostile = _hostile_never_iterated("private-alien-record-stream-consumed")
    try:
        with pytest.raises((TypeError, ValueError), match="plan|issued|session|valid"):
            module.verify_laya_runtime_base_ancestry_objects(
                alien_plan,
                (hostile, hostile, hostile),
            )
        assert hostile.touched is False
    finally:
        if plan_registry.get(alien_plan_identity) is pending_record:
            plan_registry.pop(alien_plan_identity)

    live_references = tuple(
        weakref.ref(value) for value in (second_plan, second_evidence, pending_plan)
    )
    del alien_evidence, alien_plan
    del second_plan, second_evidence, second_predecessor, second_calls
    del pending_plan, pending_predecessor, pending_calls
    del replacement_record, pending_record
    gc.collect()
    assert all(reference() is None for reference in live_references)
    assert {name: len(registry) for name, registry in registries.items()} == baseline


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
