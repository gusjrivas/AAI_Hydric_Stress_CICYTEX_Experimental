"""RED37-C: authority, lifecycle and concurrency contract for PR37."""

from __future__ import annotations

import _thread
import copy
import gc
import pickle
import sys
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
from types import SimpleNamespace

import pytest


def _module():
    from human_feedback import runtime_supply_convergence

    return runtime_supply_convergence


def _chain(monkeypatch):
    from tests.laya_runtime_supply_convergence_fixtures import issue_laya_supply_chain

    return issue_laya_supply_chain(monkeypatch)


def _issue(module, chain):
    return module.verify_laya_runtime_supply_convergence(
        chain.layer_evidence,
        chain.provenance_evidence,
        chain.base_ancestry_evidence,
    )


def _clone_exact(value, **changes):
    clone = object.__new__(type(value))
    for item in fields(value):
        object.__setattr__(clone, item.name, changes.get(item.name, getattr(value, item.name)))
    return clone


def _private_error(error: BaseException, *markers: str) -> None:
    rendered = str(error)
    assert rendered
    assert all(marker not in rendered for marker in markers)


def _assert_failure_is_atomic(module, good_chain, operation) -> None:
    trusted = _issue(module, good_chain)
    trusted_summary = module.canonical_laya_runtime_supply_convergence_summary_bytes(trusted)
    unissued = _clone_exact(trusted)

    with pytest.raises((TypeError, ValueError)):
        operation()
    with pytest.raises((TypeError, ValueError), match="evidence|issued|seal|valid"):
        module.canonical_laya_runtime_supply_convergence_summary_bytes(unissued)

    # Failure is all-or-nothing: it neither grants authority to a clone nor
    # poisons already-issued or later legitimate evidence.
    assert (
        module.canonical_laya_runtime_supply_convergence_summary_bytes(trusted) == trusted_summary
    )
    later = _issue(module, good_chain)
    assert module.canonical_laya_runtime_supply_convergence_summary_bytes(later) == trusted_summary


def test_pr36_to_pr22_binding_rejects_individually_valid_cross_graph_mix(monkeypatch):
    module = _module()
    first = _chain(monkeypatch)
    second = _chain(monkeypatch)

    def mix():
        return module.verify_laya_runtime_supply_convergence(
            first.layer_evidence,
            first.provenance_evidence,
            second.base_ancestry_evidence,
        )

    _assert_failure_is_atomic(module, first, mix)


@pytest.mark.parametrize(
    "owner,field",
    [
        ("layer_evidence", "oci_layer_diff_ids_verified"),
        ("provenance_evidence", "provenance_objects_verified"),
        ("base_ancestry_evidence", "base_ancestry_verified"),
    ],
)
def test_predecessor_mutation_after_convergence_invalidates_summary(monkeypatch, owner, field):
    module = _module()
    good_chain = _chain(monkeypatch)
    chain = _chain(monkeypatch)
    evidence = _issue(module, chain)

    object.__setattr__(getattr(chain, owner), field, False)
    with pytest.raises(
        (TypeError, ValueError),
        match="predecessor|layer|provenance|ancestry|evidence|issued|valid",
    ) as captured:
        module.canonical_laya_runtime_supply_convergence_summary_bytes(evidence)
    _private_error(captured.value, field)

    healthy = _issue(module, good_chain)
    module.canonical_laya_runtime_supply_convergence_summary_bytes(healthy)


@pytest.mark.parametrize(
    "owner,field",
    [
        ("layer_evidence", "oci_layer_diff_ids_verified"),
        ("provenance_evidence", "source_git_content_verified"),
        ("base_ancestry_evidence", "base_ancestry_verified"),
    ],
)
def test_each_mutated_issued_predecessor_fails_atomically(monkeypatch, owner, field):
    module = _module()
    good_chain = _chain(monkeypatch)
    invalid_chain = _chain(monkeypatch)
    object.__setattr__(getattr(invalid_chain, owner), field, False)

    _assert_failure_is_atomic(module, good_chain, lambda: _issue(module, invalid_chain))


def test_evidence_clone_object_new_subclass_and_proxy_never_gain_authority(monkeypatch):
    module = _module()
    evidence = _issue(module, _chain(monkeypatch))

    class Derived(type(evidence)):
        pass

    candidates = (
        _clone_exact(evidence),
        object.__new__(type(evidence)),
        object.__new__(Derived),
        SimpleNamespace(
            schema_version=evidence.schema_version,
            runtime_supply_content_convergence_verified=True,
        ),
    )
    for candidate in candidates:
        assert candidate is not evidence
        with pytest.raises((TypeError, ValueError), match="evidence|issued|seal|type|valid"):
            module.canonical_laya_runtime_supply_convergence_summary_bytes(candidate)


def test_replace_copy_deepcopy_and_pickle_cannot_create_new_authority(monkeypatch):
    module = _module()
    evidence = _issue(module, _chain(monkeypatch))

    with pytest.raises((TypeError, ValueError)):
        replace(evidence)

    candidates = [copy.copy(evidence), copy.deepcopy(evidence)]
    try:
        candidates.append(pickle.loads(pickle.dumps(evidence)))
    except (pickle.PickleError, TypeError, ValueError, AttributeError):
        pass
    assert candidates
    for candidate in candidates:
        if candidate is evidence:
            module.canonical_laya_runtime_supply_convergence_summary_bytes(candidate)
        else:
            with pytest.raises((TypeError, ValueError), match="evidence|issued|seal|type|valid"):
                module.canonical_laya_runtime_supply_convergence_summary_bytes(candidate)


def test_mutated_issued_convergence_evidence_fails_deep_revalidation(monkeypatch):
    module = _module()
    good_chain = _chain(monkeypatch)
    evidence = _issue(module, _chain(monkeypatch))
    object.__setattr__(evidence, "runtime_supply_content_convergence_verified", False)

    with pytest.raises((TypeError, ValueError), match="evidence|claim|issued|valid"):
        module.canonical_laya_runtime_supply_convergence_summary_bytes(evidence)
    module.canonical_laya_runtime_supply_convergence_summary_bytes(_issue(module, good_chain))


def test_valid_convergence_is_repeatable_concurrent_and_summary_deterministic(monkeypatch):
    module = _module()
    chain = _chain(monkeypatch)

    with ThreadPoolExecutor(max_workers=8) as executor:
        evidence_values = tuple(executor.map(lambda _index: _issue(module, chain), range(24)))
    assert len({id(value) for value in evidence_values}) == len(evidence_values)

    with ThreadPoolExecutor(max_workers=8) as executor:
        summaries = tuple(
            executor.map(
                module.canonical_laya_runtime_supply_convergence_summary_bytes,
                evidence_values,
            )
        )
    assert len(set(summaries)) == 1
    assert all(
        value.runtime_supply_content_convergence_verified is True for value in evidence_values
    )


def test_gc_releases_expired_graph_and_cleanup_preserves_live_authority(monkeypatch):
    module = _module()
    gc.collect()

    expired_chain = _chain(monkeypatch)
    expired_evidence = _issue(module, expired_chain)
    expired_reference = weakref.ref(expired_evidence)
    graph_references = tuple(
        weakref.ref(value)
        for value in (
            expired_chain.layer_evidence,
            expired_chain.provenance_evidence,
            expired_chain.base_ancestry_evidence,
        )
    )

    live_chain = _chain(monkeypatch)
    live_evidence = _issue(module, live_chain)
    live_summary = module.canonical_laya_runtime_supply_convergence_summary_bytes(live_evidence)

    del expired_evidence, expired_chain
    gc.collect()
    assert expired_reference() is None
    assert all(reference() is None for reference in graph_references)
    assert (
        module.canonical_laya_runtime_supply_convergence_summary_bytes(live_evidence)
        == live_summary
    )

    # Repeated expired callbacks exercise allocator reuse while asserting only
    # externally observable liveness and authority behavior.
    for _index in range(64):
        temporary = _issue(module, live_chain)
        temporary_reference = weakref.ref(temporary)
        del temporary
        gc.collect()
        assert temporary_reference() is None
        assert (
            module.canonical_laya_runtime_supply_convergence_summary_bytes(live_evidence)
            == live_summary
        )


def test_private_lock_is_not_held_while_calling_predecessors_or_reconstructors(
    monkeypatch,
):
    module = _module()
    chain = _chain(monkeypatch)
    from human_feedback import (
        runtime_base_ancestry,
        runtime_bundle,
        runtime_oci_layers,
        runtime_provenance,
    )

    targets = {
        runtime_oci_layers.canonical_laya_runtime_oci_layer_diff_ids_summary_bytes.__code__: (
            "layer"
        ),
        runtime_provenance.canonical_laya_runtime_provenance_summary_bytes.__code__: "provenance",
        runtime_base_ancestry.canonical_laya_runtime_base_ancestry_summary_bytes.__code__: "base",
        runtime_bundle.verify_laya_runtime_artifact_bytes.__code__: "reconstruct",
    }
    lock_types = {_thread.LockType, type(_thread.RLock())}
    observable_locks = tuple(value for value in vars(module).values() if type(value) in lock_types)
    observed = []

    def profile(frame, event, _arg):
        if event != "call" or frame.f_code not in targets:
            return
        for lock in observable_locks:
            if hasattr(lock, "locked"):
                assert lock.locked() is False
            if hasattr(lock, "_is_owned"):
                assert lock._is_owned() is False
        observed.append(targets[frame.f_code])

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        _issue(module, chain)
    finally:
        sys.setprofile(previous)

    assert observed.count("layer") >= 1
    assert observed.count("provenance") >= 1
    assert observed.count("base") >= 1
    assert observed.count("reconstruct") == 2
