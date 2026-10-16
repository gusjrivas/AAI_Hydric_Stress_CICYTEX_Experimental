import ast
import gc
import inspect
import json
import os
import sys
import weakref
from dataclasses import FrozenInstanceError, dataclass, fields, is_dataclass, replace
from itertools import chain, repeat
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_laya_runtime_deployment_metadata import CHECKPOINT_FILES, _validate

PLAN_SCHEMA = "laya-runtime-checkpoint-plan-v1"
EVIDENCE_SCHEMA = "laya-runtime-checkpoint-evidence-v1"
REAL_CHECKPOINT_GATE_ENV = "LAYA_RUNTIME_CHECKPOINT_ROOT"
TRUE_FLAGS = (
    "artifact_integrity_verified",
    "runtime_config_semantics_verified",
    "checkpoint_manifest_semantics_verified",
    "checkpoint_bytes_verified",
)
FALSE_FLAGS = (
    "lock_verified",
    "sbom_verified",
    "lock_sbom_consistent",
    "oci_bytes_verified",
    "oci_manifest_semantics_verified",
    "runtime_materialized",
    "origin_verified",
    "executor_available",
    "inference_executed",
)


def _core():
    import human_feedback.runtime_checkpoint as checkpoint

    return checkpoint


def _plan():
    return _core().prepare_laya_runtime_checkpoint_plan(_validate())


def _private_error(exc: BaseException, *markers: str) -> None:
    rendered = "\n".join((str(exc), repr(exc), repr(exc.__cause__), repr(exc.__context__)))
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    assert all(marker not in rendered for marker in markers)


def _forge_exact(instance, **changes):
    forged = object.__new__(type(instance))
    for field in fields(instance):
        object.__setattr__(
            forged, field.name, changes.get(field.name, getattr(instance, field.name))
        )
    return forged


def _clone_all_slots(instance):
    """Copy even private capability slots without granting issued identity."""

    cloned = object.__new__(type(instance))
    for cls in type(instance).__mro__:
        for name in getattr(cls, "__slots__", ()):
            if name not in {"__weakref__", "__dict__"} and hasattr(instance, name):
                object.__setattr__(cloned, name, getattr(instance, name))
    return cloned


def _legitimate_checkpoint_evidence(monkeypatch):
    """Issue bounded receipts through the public byte verifier."""

    checkpoint = _core()
    plan = _plan()
    expected_digests = iter(descriptor.sha256 for descriptor in plan.files)

    class MatchingDigest:
        def __init__(self, expected):
            self.expected = expected

        def update(self, payload):
            assert type(payload) is bytes

        def hexdigest(self):
            return self.expected

    def digest_factory(initial=b""):
        assert initial == b""
        return MatchingDigest(next(expected_digests))

    reusable = b"x" * checkpoint.MAX_CHECKPOINT_CHUNK_BYTES
    receipts = []
    with monkeypatch.context() as scoped:
        scoped.setattr(checkpoint.hashlib, "sha256", digest_factory)
        for descriptor in plan.files:
            whole, remainder = divmod(descriptor.size_bytes, checkpoint.MAX_CHECKPOINT_CHUNK_BYTES)
            chunks = chain(
                repeat(reusable, whole),
                (b"x" * remainder,) if remainder else (),
            )
            receipts.append(
                checkpoint.verify_laya_checkpoint_file_chunks(plan, descriptor.sha256, chunks)
            )
    authority = checkpoint._seal_laya_checkpoint_capture_authority(plan, tuple(receipts))
    return checkpoint._seal_laya_runtime_checkpoint_evidence(authority)


def _fabricated_checkpoint_evidence():
    """Build an exact-class graph without invoking either byte or private sealers."""

    checkpoint = _core()
    plan = _plan()
    receipts = []
    for descriptor in plan.files:
        receipt = object.__new__(checkpoint.VerifiedLayaCheckpointFile)
        object.__setattr__(receipt, "plan", plan)
        object.__setattr__(receipt, "file", descriptor)
        object.__setattr__(receipt, "checkpoint_file_bytes_verified", True)
        receipts.append(receipt)

    evidence = object.__new__(checkpoint.LayaRuntimeCheckpointEvidence)
    values = {
        "schema_version": checkpoint.CHECKPOINT_EVIDENCE_SCHEMA,
        "plan": plan,
        "deployment_evidence": plan.deployment_evidence,
        "runtime_identity": plan.runtime_identity,
        "receipts": tuple(receipts),
    }
    values.update({name: True for name in TRUE_FLAGS})
    values.update({name: False for name in FALSE_FLAGS})
    for name, value in values.items():
        object.__setattr__(evidence, name, value)
    return evidence


def test_checkpoint_plan_is_exact_identity_bound_and_private():
    checkpoint = _core()
    deployment = _validate()
    plan = checkpoint.prepare_laya_runtime_checkpoint_plan(deployment)

    assert type(plan) is checkpoint.LayaRuntimeCheckpointPlan
    assert plan.schema_version == PLAN_SCHEMA
    assert plan.deployment_evidence is deployment
    assert plan.runtime_identity is deployment.runtime_identity
    assert type(plan.files) is tuple
    assert tuple(item.role for item in plan.files) == tuple(
        item["role"] for item in CHECKPOINT_FILES
    )
    assert tuple(item.path for item in plan.files) == tuple(
        item["path"] for item in CHECKPOINT_FILES
    )
    assert tuple(item.sha256 for item in plan.files) == tuple(
        item["sha256"] for item in CHECKPOINT_FILES
    )
    assert tuple(item.size_bytes for item in plan.files) == tuple(
        item["size_bytes"] for item in CHECKPOINT_FILES
    )
    private_values = tuple(
        value for item in CHECKPOINT_FILES for value in (item["path"], item["sha256"])
    )
    assert all(value not in repr(plan) for value in private_values)


def test_checkpoint_plan_and_descriptor_graph_are_frozen_slotted_and_factory_sealed():
    checkpoint = _core()
    plan = _plan()
    assert is_dataclass(plan) and plan.__dataclass_params__.frozen
    assert "__dict__" not in vars(type(plan))
    with pytest.raises((TypeError, ValueError)):
        checkpoint.LayaRuntimeCheckpointPlan(
            schema_version=plan.schema_version,
            deployment_evidence=plan.deployment_evidence,
            runtime_identity=plan.runtime_identity,
            files=plan.files,
        )
    with pytest.raises((TypeError, ValueError)):
        replace(plan, files=tuple(reversed(plan.files)))
    for descriptor in plan.files:
        assert is_dataclass(descriptor) and descriptor.__dataclass_params__.frozen
        assert "__dict__" not in vars(type(descriptor))
        for field in fields(descriptor):
            if field.init:
                with pytest.raises(FrozenInstanceError):
                    setattr(descriptor, field.name, getattr(descriptor, field.name))
        with pytest.raises((TypeError, ValueError)):
            replace(descriptor, size_bytes=descriptor.size_bytes + 1)


@pytest.mark.parametrize(
    "bad",
    [None, SimpleNamespace(), object.__new__(type(_validate()))],
)
def test_prepare_rejects_proxy_or_unsealed_deployment_evidence(bad):
    with pytest.raises((TypeError, ValueError)):
        _core().prepare_laya_runtime_checkpoint_plan(bad)


@pytest.mark.parametrize("bad_value", [False, 1, None])
def test_prepare_deeply_revalidates_inherited_deployment_claims(bad_value):
    deployment = _validate()
    corrupt = _forge_exact(deployment, artifact_integrity_verified=bad_value)
    with pytest.raises((TypeError, ValueError)):
        _core().prepare_laya_runtime_checkpoint_plan(corrupt)


def _nested_deployment_mutations():
    deployment = _validate()
    snapshot = deployment.snapshot
    config = deployment.runtime_config
    checkpoint = deployment.checkpoint_manifest
    identity = deployment.runtime_identity
    alternate_identity = _forge_exact(identity, sha256="f" * 64)
    alternate_snapshot = _forge_exact(snapshot, runtime_identity=alternate_identity)
    return (
        _forge_exact(
            deployment,
            snapshot=_forge_exact(snapshot, schema_version="private-snapshot-schema"),
        ),
        _forge_exact(
            deployment,
            snapshot=_forge_exact(snapshot, artifacts=tuple(reversed(snapshot.artifacts))),
        ),
        _forge_exact(
            deployment,
            runtime_config=_forge_exact(config, model_name="private-model-name"),
        ),
        _forge_exact(
            deployment,
            runtime_config=_forge_exact(config, checkpoint_manifest_sha256="e" * 64),
        ),
        _forge_exact(
            deployment,
            checkpoint_manifest=_forge_exact(
                checkpoint, repository="private-checkpoint-repository"
            ),
        ),
        _forge_exact(
            deployment,
            snapshot=alternate_snapshot,
            runtime_identity=alternate_identity,
        ),
    )


@pytest.mark.parametrize("corrupt", _nested_deployment_mutations())
def test_prepare_rejects_exact_type_forged_nested_deployment_graph(corrupt):
    with pytest.raises((TypeError, ValueError)) as caught:
        _core().prepare_laya_runtime_checkpoint_plan(corrupt)
    _private_error(
        caught.value,
        "private-snapshot-schema",
        "private-model-name",
        "private-checkpoint-repository",
    )


def test_stream_authorization_rejects_unknown_or_malformed_digest_before_consuming():
    checkpoint = _core()
    plan = _plan()

    class Hostile:
        requested = 0

        def __iter__(self):
            return self

        def __next__(self):
            self.requested += 1
            raise AssertionError("private-stream-sentinel")

    for digest in ("0" * 64, "A" * 64, "sha256:" + "a" * 64, "short"):
        chunks = Hostile()
        with pytest.raises((TypeError, ValueError)):
            checkpoint.verify_laya_checkpoint_file_chunks(plan, digest, chunks)
        assert chunks.requested == 0


@pytest.mark.parametrize("chunk", [b"", bytearray(b"x"), memoryview(b"x"), "x", 1])
def test_stream_rejects_empty_or_non_exact_bytes_chunks(chunk):
    checkpoint = _core()
    plan = _plan()
    with pytest.raises((TypeError, ValueError)):
        checkpoint.verify_laya_checkpoint_file_chunks(plan, plan.files[-1].sha256, iter((chunk,)))


def test_stream_is_bounded_and_stops_at_expected_size_plus_one():
    checkpoint = _core()
    plan = _plan()
    descriptor = plan.files[-1]
    assert checkpoint.MAX_CHECKPOINT_CHUNK_BYTES == 1024 * 1024
    assert checkpoint.MAX_CHECKPOINT_CHUNKS == 1024

    requested = 0

    def chunks():
        nonlocal requested
        requested += 1
        yield b"x" * descriptor.size_bytes
        requested += 1
        yield b"y"
        requested += 1
        raise AssertionError("must stop at expected plus one")

    with pytest.raises(ValueError):
        checkpoint.verify_laya_checkpoint_file_chunks(plan, descriptor.sha256, chunks())
    assert requested == 2


@pytest.mark.parametrize("terminator", [b"\n", b"\r\n", b""])
def test_git_lfs_pointer_is_rejected_even_when_declared_bytes_match_shape(terminator):
    checkpoint = _core()
    plan = _plan()
    descriptor = plan.files[-1]
    pointer = (
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:" + b"a" * 64 + b"\nsize 524" + terminator
    )
    requested = 0

    def chunks():
        nonlocal requested
        requested += 1
        yield pointer
        requested += 1
        raise AssertionError("an LFS pointer must fail before another request")

    with pytest.raises(ValueError) as caught:
        checkpoint.verify_laya_checkpoint_file_chunks(plan, descriptor.sha256, chunks())
    assert requested == 1
    _private_error(caught.value, pointer.decode("ascii"))


def test_chunk_count_cap_and_exact_size_digest_mismatch_are_independent():
    checkpoint = _core()
    plan = _plan()
    chunk_descriptor = plan.files[0]
    digest_descriptor = plan.files[-1]
    assert chunk_descriptor.size_bytes > checkpoint.MAX_CHECKPOINT_CHUNKS
    requested = 0

    def too_many():
        nonlocal requested
        while requested <= checkpoint.MAX_CHECKPOINT_CHUNKS:
            requested += 1
            yield b"x"
        raise AssertionError("chunk cap must stop the stream")

    with pytest.raises(ValueError):
        checkpoint.verify_laya_checkpoint_file_chunks(plan, chunk_descriptor.sha256, too_many())
    assert requested == checkpoint.MAX_CHECKPOINT_CHUNKS + 1

    with pytest.raises(ValueError):
        checkpoint.verify_laya_checkpoint_file_chunks(
            plan,
            digest_descriptor.sha256,
            iter((b"x" * digest_descriptor.size_bytes,)),
        )


def test_explicit_none_chunk_is_not_silently_treated_as_iterator_eof(monkeypatch):
    checkpoint = _core()
    plan = _plan()
    descriptor = plan.files[-1]
    requested = 0
    trailing_marker = b"private-trailing-data-after-none"

    class MatchingDigest:
        def update(self, payload):
            assert type(payload) is bytes

        def hexdigest(self):
            return descriptor.sha256

    monkeypatch.setattr(checkpoint.hashlib, "sha256", MatchingDigest)

    def chunks():
        nonlocal requested
        requested += 1
        yield b"x" * descriptor.size_bytes
        requested += 1
        yield None
        requested += 1
        yield trailing_marker
        raise AssertionError("private-eof-sentinel")

    with pytest.raises(ValueError) as caught:
        checkpoint.verify_laya_checkpoint_file_chunks(plan, descriptor.sha256, chunks())
    assert requested == 2
    _private_error(caught.value, trailing_marker.decode("ascii"), "private-eof-sentinel")


def test_stream_errors_are_private_and_do_not_retain_payload_or_iterator_context():
    checkpoint = _core()
    plan = _plan()
    marker = "private-checkpoint-stream-marker"

    def chunks():
        yield marker.encode("ascii")
        raise RuntimeError(marker)

    with pytest.raises(ValueError) as caught:
        checkpoint.verify_laya_checkpoint_file_chunks(plan, plan.files[-1].sha256, chunks())
    _private_error(caught.value, marker)


def test_core_implementation_is_streaming_and_pure():
    checkpoint = _core()
    source = Path(checkpoint.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imports & {"os", "pathlib", "subprocess", "socket", "requests", "urllib"}
    verify = inspect.getsource(checkpoint._verify_laya_checkpoint_file_chunks)
    verify_tree = ast.parse(verify)
    forbidden_calls = {"join", "list", "tuple", "bytearray", "read", "open"}
    assert (
        not {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(verify_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        & forbidden_calls
    )


def test_receipt_and_evidence_public_contract_is_deeply_sealed_and_conservative():
    checkpoint = _core()
    receipt_type = checkpoint.VerifiedLayaCheckpointFile
    evidence_type = checkpoint.LayaRuntimeCheckpointEvidence
    for cls in (receipt_type, evidence_type):
        assert is_dataclass(cls) and cls.__dataclass_params__.frozen
        assert "__dict__" not in vars(cls)
    assert all(not field.init for field in fields(receipt_type) if field.name.endswith("verified"))
    assert all(
        not field.init for field in fields(evidence_type) if field.name in TRUE_FLAGS + FALSE_FLAGS
    )
    with pytest.raises((TypeError, ValueError)):
        receipt_type()
    with pytest.raises((TypeError, ValueError)):
        evidence_type()


def test_exact_class_checkpoint_evidence_cannot_be_fabricated_without_byte_verification():
    checkpoint = _core()
    with pytest.raises(ValueError):
        checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(
            _fabricated_checkpoint_evidence()
        )


def test_lightweight_checkpoint_helper_uses_public_verifier_issued_receipts(monkeypatch):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    assert type(evidence) is checkpoint.LayaRuntimeCheckpointEvidence
    assert tuple(receipt.file for receipt in evidence.receipts) == evidence.plan.files
    assert all(
        type(receipt) is checkpoint.VerifiedLayaCheckpointFile for receipt in evidence.receipts
    )


def test_cloned_checkpoint_plan_is_rejected_before_stream_consumption(monkeypatch):
    checkpoint = _core()
    plan = _legitimate_checkpoint_evidence(monkeypatch).plan

    class Untouched:
        requested = 0

        def __iter__(self):
            return self

        def __next__(self):
            self.requested += 1
            raise AssertionError("private-cloned-plan-stream")

    cloned_plan = _clone_all_slots(plan)
    chunks = Untouched()
    with pytest.raises(ValueError):
        checkpoint.verify_laya_checkpoint_file_chunks(
            cloned_plan, cloned_plan.files[0].sha256, chunks
        )
    assert chunks.requested == 0


def test_cloned_checkpoint_receipt_cannot_authorize_capture(monkeypatch):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    plan = evidence.plan
    cloned_receipt = _clone_all_slots(evidence.receipts[0])
    with pytest.raises(ValueError):
        checkpoint._seal_laya_checkpoint_capture_authority(
            plan, (cloned_receipt, *evidence.receipts[1:])
        )


def test_cloned_checkpoint_authority_cannot_seal_evidence(monkeypatch):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    authority = checkpoint._seal_laya_checkpoint_capture_authority(evidence.plan, evidence.receipts)
    with pytest.raises(ValueError):
        checkpoint._seal_laya_runtime_checkpoint_evidence(_clone_all_slots(authority))


def test_cloned_checkpoint_evidence_cannot_publish_summary(monkeypatch):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    with pytest.raises(ValueError):
        checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(_clone_all_slots(evidence))


@pytest.mark.parametrize(
    ("nested_object", "field_name", "hostile_value"),
    (
        ("runtime_identity", "sha256", "f" * 64),
        ("checkpoint_manifest", "revision", "private-mutated-revision"),
    ),
)
def test_issued_checkpoint_evidence_rejects_deep_post_issue_mutation(
    monkeypatch, nested_object, field_name, hostile_value
):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    target = (
        evidence.runtime_identity
        if nested_object == "runtime_identity"
        else evidence.deployment_evidence.checkpoint_manifest
    )
    object.__setattr__(target, field_name, hostile_value)

    with pytest.raises(ValueError) as caught:
        checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(evidence)
    _private_error(caught.value, hostile_value)


def test_issued_checkpoint_evidence_rejects_deep_artifact_content_mutation(monkeypatch):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    artifact = evidence.deployment_evidence.snapshot.artifacts[0]
    hostile_content = artifact.content + b"\nprivate-mutated-artifact-content"
    assert evidence.artifact_integrity_verified is True
    object.__setattr__(artifact, "content", hostile_content)

    with pytest.raises(ValueError) as caught:
        checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(evidence)
    _private_error(caught.value, "private-mutated-artifact-content")


@pytest.mark.parametrize("nested_name", ("checkpoint_manifest", "snapshot"))
@pytest.mark.parametrize("consumer", ("checkpoint_summary", "provenance_prepare"))
def test_issued_checkpoint_evidence_rejects_equal_distinct_nested_clone(
    monkeypatch, nested_name, consumer
):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    original = getattr(evidence.deployment_evidence, nested_name)
    cloned = _clone_all_slots(original)
    assert cloned == original
    assert cloned is not original
    object.__setattr__(evidence.deployment_evidence, nested_name, cloned)

    if consumer == "checkpoint_summary":
        publish = checkpoint.canonical_laya_runtime_checkpoint_summary_bytes
    else:
        from human_feedback.runtime_provenance import (
            prepare_laya_runtime_provenance_plan,
        )

        publish = prepare_laya_runtime_provenance_plan
    with pytest.raises(ValueError):
        publish(evidence)


def test_issued_checkpoint_topology_retains_original_manifest_authority(monkeypatch):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    deployment = evidence.deployment_evidence
    original = deployment.checkpoint_manifest
    cloned = _clone_all_slots(original)
    try:
        retained = weakref.ref(original)
    except TypeError:
        retained = None
    object.__setattr__(deployment, "checkpoint_manifest", cloned)

    # The issuance seal must retain the exact original node while evidence is alive.
    # Otherwise its id can be recycled and identity-only topology checks become unsafe.
    if retained is not None:
        del original
        gc.collect()
        assert retained() is not None
    else:
        # local + getrefcount temporary + at least one seal-owned strong reference;
        # an id-only implementation has only the first two after replacement.
        assert sys.getrefcount(original) >= 3
    with pytest.raises(ValueError):
        checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(evidence)


def _retarget_identity_seals(checkpoint, value, original, replacement):
    if type(value) is checkpoint._IdentitySeal:
        if value.value is original:
            object.__setattr__(value, "value", replacement)
            return 1
        return 0
    if type(value) in {tuple, list}:
        return sum(
            _retarget_identity_seals(checkpoint, item, original, replacement) for item in value
        )
    if type(value) is dict:
        return sum(
            _retarget_identity_seals(checkpoint, item, original, replacement)
            for item in value.values()
        )
    return 0


@pytest.mark.parametrize("consumer", ("checkpoint_summary", "provenance_prepare"))
def test_caller_visible_semantic_capability_cannot_retarget_nested_authority(monkeypatch, consumer):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    deployment = evidence.deployment_evidence
    original = deployment.checkpoint_manifest
    cloned = _clone_all_slots(original)
    retargeted = sum(
        _retarget_identity_seals(
            checkpoint,
            sealed._semantic_capability,
            original,
            cloned,
        )
        for sealed in (evidence.plan, evidence)
    )
    assert retargeted >= 2
    object.__setattr__(deployment, "checkpoint_manifest", cloned)

    if consumer == "checkpoint_summary":
        publish = checkpoint.canonical_laya_runtime_checkpoint_summary_bytes
    else:
        from human_feedback.runtime_provenance import (
            prepare_laya_runtime_provenance_plan,
        )

        publish = prepare_laya_runtime_provenance_plan
    with pytest.raises(ValueError):
        publish(evidence)


def test_deep_snapshot_rejects_oversized_artifact_before_hashing(monkeypatch):
    checkpoint = _core()
    from human_feedback import runtime_deployment_metadata

    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    artifact = next(
        item
        for item in evidence.deployment_evidence.snapshot.artifacts
        if item.spec.kind == "checkpoint_manifest"
    )
    maximum = runtime_deployment_metadata.MAX_CHECKPOINT_MANIFEST_BYTES
    object.__setattr__(artifact, "content", b"x" * (maximum + 1))
    original_new = checkpoint.hashlib.new
    oversized_hash_attempts = 0

    def bounded_hash(name, payload=b"", *args, **kwargs):
        nonlocal oversized_hash_attempts
        if type(payload) is bytes and len(payload) > maximum:
            oversized_hash_attempts += 1
            raise AssertionError("oversized artifact reached the hash function")
        return original_new(name, payload, *args, **kwargs)

    monkeypatch.setattr(checkpoint.hashlib, "new", bounded_hash)
    with pytest.raises(ValueError):
        checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(evidence)
    assert oversized_hash_attempts == 0


@pytest.mark.parametrize("leaf_kind", ("bytes", "text"))
def test_deep_snapshot_enforces_aggregate_leaf_byte_budget(monkeypatch, leaf_kind):
    checkpoint = _core()
    maximum = checkpoint.MAX_SEMANTIC_SNAPSHOT_BYTES
    leaf_size = 1024 * 1024
    leaf = b"x" * leaf_size if leaf_kind == "bytes" else "x" * leaf_size
    graph = (leaf,) * (maximum // leaf_size + 1)
    oversized_hash_attempts = 0
    hashed_bytes = 0
    original_new = checkpoint.hashlib.new

    def bounded_hash(name, payload=b"", *args, **kwargs):
        nonlocal hashed_bytes, oversized_hash_attempts
        if type(payload) is bytes:
            if hashed_bytes + len(payload) > maximum:
                oversized_hash_attempts += 1
                raise AssertionError("aggregate byte budget reached the hash function")
            hashed_bytes += len(payload)
        return original_new(name, payload, *args, **kwargs)

    monkeypatch.setattr(checkpoint.hashlib, "new", bounded_hash)
    with pytest.raises(ValueError):
        checkpoint._deep_semantic_snapshot(graph)
    assert oversized_hash_attempts == 0


@pytest.mark.parametrize("node_kind", ("tuple", "dataclass"))
def test_deep_snapshot_enforces_explicit_maximum_depth_before_recursion_failure(
    node_kind,
):
    checkpoint = _core()
    maximum = getattr(checkpoint, "MAX_SEMANTIC_SNAPSHOT_DEPTH", 64)
    assert type(maximum) is int and 0 < maximum <= 64

    @dataclass(frozen=True)
    class Node:
        child: object

    graph = "leaf"
    for _ in range(maximum + 1):
        graph = (graph,) if node_kind == "tuple" else Node(graph)

    with pytest.raises(ValueError):
        checkpoint._deep_semantic_snapshot(graph)


def test_deep_snapshot_rejects_oversized_utf8_text_leaf_with_small_budget():
    checkpoint = _core()
    maximum = 16
    oversized_text = "é" * 9
    assert len(oversized_text) <= maximum
    assert len(oversized_text.encode("utf-8")) > maximum

    with pytest.raises(ValueError):
        checkpoint._deep_semantic_snapshot(oversized_text, _byte_limit=maximum)


def test_deep_snapshot_rejects_oversized_utf8_mapping_key_before_sort(monkeypatch):
    checkpoint = _core()
    import builtins

    maximum = 16
    oversized_key = "é" * 9
    sort_attempts = 0
    original_sorted = builtins.sorted

    def guarded_sorted(values, *args, **kwargs):
        nonlocal sort_attempts
        sort_attempts += 1
        return original_sorted(values, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(builtins, "sorted", guarded_sorted)
        with pytest.raises(ValueError):
            checkpoint._deep_semantic_snapshot(
                {oversized_key: None},
                _byte_limit=maximum,
            )
    assert sort_attempts == 0


def _deep_snapshot_branch(predicate: str):
    checkpoint = _core()
    tree = ast.parse(inspect.getsource(checkpoint._deep_semantic_snapshot))
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
    return next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.If) and ast.unparse(node.test) == predicate
    )


def _is_utf8_encode_call(node) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "encode"
        and any(isinstance(arg, ast.Constant) and arg.value == "utf-8" for arg in node.args)
    )


def _contains_utf8_encode(node) -> bool:
    return any(_is_utf8_encode_call(item) for item in ast.walk(node))


def test_deep_snapshot_prechecks_text_length_before_utf8_encoding():
    branch = _deep_snapshot_branch("type(value) is str")
    encode_line = min(node.lineno for node in ast.walk(branch) if _is_utf8_encode_call(node))
    prechecks = [
        node
        for node in branch.body
        if isinstance(node, ast.If)
        and node.lineno < encode_line
        and "len(value)" in ast.unparse(node.test)
        and "byte_budget" in ast.unparse(node.test)
    ]
    assert prechecks, "text length must be rejected before UTF-8 encoding"


def test_deep_snapshot_processes_mapping_keys_sequentially_with_prechecks():
    branch = _deep_snapshot_branch("type(value) is dict")
    assert not any(
        isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))
        and _contains_utf8_encode(node)
        for node in ast.walk(branch)
    )
    key_loop = next(
        (
            node
            for node in branch.body
            if isinstance(node, ast.For)
            and isinstance(node.target, ast.Name)
            and node.target.id == "key"
        ),
        None,
    )
    assert key_loop is not None, "mapping keys must be budgeted one at a time"
    encode_lines = [node.lineno for node in ast.walk(key_loop) if _is_utf8_encode_call(node)]
    assert encode_lines
    encode_line = min(encode_lines)
    assert any(
        isinstance(node, ast.If)
        and node.lineno < encode_line
        and "len(key)" in ast.unparse(node.test)
        for node in key_loop.body
    )
    consume_lines = [
        node.lineno
        for node in ast.walk(key_loop)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_consume_semantic_bytes"
    ]
    assert consume_lines and min(consume_lines) > encode_line
    sorted_lines = [
        node.lineno
        for node in ast.walk(branch)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sorted"
    ]
    assert sorted_lines and min(sorted_lines) > key_loop.end_lineno


def test_deep_snapshot_rejects_abnormal_mapping_without_iterating(monkeypatch):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)

    class HostileMapping(dict):
        requested = 0

        def __iter__(self):
            self.requested += 1
            raise AssertionError("abnormal mapping was traversed")

        def items(self):
            self.requested += 1
            raise AssertionError("abnormal mapping items were traversed")

    hostile = HostileMapping()
    object.__setattr__(evidence.deployment_evidence.runtime_config, "environment", hostile)
    with pytest.raises(ValueError):
        checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(evidence)
    assert hostile.requested == 0


def test_deep_snapshot_rejects_oversized_exact_sequence(monkeypatch):
    checkpoint = _core()
    evidence = _legitimate_checkpoint_evidence(monkeypatch)
    oversized = (("KEY", "VALUE"),) * 2049
    object.__setattr__(evidence.deployment_evidence.runtime_config, "environment", oversized)

    with pytest.raises(ValueError):
        checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(evidence)


def test_private_authority_rejects_caller_receipts_and_public_finalizers_do_not_exist():
    checkpoint = _core()
    plan = _plan()
    assert not hasattr(checkpoint, "finalize_laya_runtime_checkpoint_evidence")
    assert not hasattr(checkpoint, "checkpoint_receipt_from_digest")
    for receipts in ((), [], (SimpleNamespace(),), tuple(plan.files)):
        with pytest.raises((TypeError, ValueError)):
            checkpoint._seal_laya_checkpoint_capture_authority(plan, receipts)
    for value in (plan, (), SimpleNamespace()):
        with pytest.raises((TypeError, ValueError)):
            checkpoint._seal_laya_runtime_checkpoint_evidence(value)


def test_summary_rejects_non_evidence_and_never_publishes_file_identity():
    checkpoint = _core()
    for value in (None, _plan(), SimpleNamespace()):
        with pytest.raises((TypeError, ValueError)):
            checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(value)
    source = Path(checkpoint.__file__).read_text(encoding="utf-8")
    assert (
        '"path"' not in source[source.find("def canonical_laya_runtime_checkpoint_summary_bytes") :]
    )
    assert (
        '"sha256"'
        not in source[source.find("def canonical_laya_runtime_checkpoint_summary_bytes") :]
    )


@pytest.mark.skipif(
    not sys.platform.startswith("linux") or not os.environ.get(REAL_CHECKPOINT_GATE_ENV),
    reason="real checkpoint bytes are an explicit Linux release gate",
)
def test_opt_in_real_checkpoint_bytes_produce_all_or_nothing_conservative_evidence():
    checkpoint = _core()
    from human_feedback.adapters.filesystem_checkpoint import (
        capture_and_verify_laya_runtime_checkpoint,
    )

    deployment = _validate()
    root = Path(os.environ[REAL_CHECKPOINT_GATE_ENV])
    evidence = capture_and_verify_laya_runtime_checkpoint(deployment, root)
    assert type(evidence) is checkpoint.LayaRuntimeCheckpointEvidence
    assert evidence.runtime_identity is deployment.runtime_identity
    assert tuple(receipt.file for receipt in evidence.receipts) == evidence.plan.files
    assert all(
        type(receipt) is checkpoint.VerifiedLayaCheckpointFile for receipt in evidence.receipts
    )
    assert all(getattr(evidence, flag) is True for flag in TRUE_FLAGS)
    assert all(getattr(evidence, flag) is False for flag in FALSE_FLAGS)
    summary = checkpoint.canonical_laya_runtime_checkpoint_summary_bytes(evidence)
    decoded = json.loads(summary)
    assert decoded["schema_version"] == EVIDENCE_SCHEMA
    assert decoded["runtime_identity_sha256"] == deployment.runtime_identity.sha256
    for item in CHECKPOINT_FILES:
        assert item["path"].encode() not in summary
        assert item["sha256"].encode() not in summary
