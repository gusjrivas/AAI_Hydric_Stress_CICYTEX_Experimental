"""RED37-D: claims, privacy, closed surface and isolation contract."""

from __future__ import annotations

import ast
import inspect
import json
import traceback
from dataclasses import fields, is_dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

TRUE_CLAIMS = (
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
    "base_ancestry_verified",
    "runtime_config_semantics_verified",
    "checkpoint_manifest_semantics_verified",
    "checkpoint_bytes_verified",
    "provenance_objects_verified",
    "source_git_content_verified",
    "checkpoint_git_content_verified",
    "source_license_declaration_observed",
    "checkpoint_license_declaration_observed",
    "runtime_supply_content_convergence_verified",
)

FALSE_CLAIMS = (
    "lock_verified",
    "sbom_verified",
    "lock_sbom_consistent",
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

NON_BOOLEAN_KEYS = (
    "schema_version",
    "layer_evidence_schema_version",
    "provenance_evidence_schema_version",
    "base_ancestry_evidence_schema_version",
    "runtime_identity_schema_version",
    "runtime_identity_sha256",
)


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


def _metadata_markers(chain) -> tuple[str, ...]:
    layer_snapshot = chain.layer_evidence.layout_evidence.plan.oci_evidence.snapshot
    provenance_snapshot = chain.provenance_evidence.checkpoint_evidence.deployment_evidence.snapshot
    markers = {
        artifact.spec.path
        for snapshot in (layer_snapshot, provenance_snapshot)
        for artifact in snapshot.artifacts
    }
    markers.update(
        artifact.spec.sha256
        for snapshot in (layer_snapshot, provenance_snapshot)
        for artifact in snapshot.artifacts
    )
    markers.update(receipt.spec.sha1 for receipt in chain.provenance_evidence.receipts)
    markers.update(receipt.layer_blob.digest for receipt in chain.layer_evidence.receipts)
    return tuple(sorted(marker for marker in markers if len(marker) >= 8))


def _unique_ascii_payload_markers(chain) -> tuple[bytes, ...]:
    groups = {
        "checkpoint": tuple(chain.checkpoint_payloads),
        "bundle": tuple(artifact.content for artifact in chain.snapshot.artifacts),
        "provenance": tuple(chain.provenance_payloads.values()),
    }

    by_group = {}
    all_candidates = []
    for name, payloads in groups.items():
        candidates = []
        for payload in payloads:
            try:
                payload.decode("ascii")
            except UnicodeDecodeError:
                continue
            if 8 <= len(payload) <= 512:
                candidates.append(payload)
            if b"\n" in payload or len(payload) > 512:
                candidates.extend(
                    line
                    for line in payload.splitlines()
                    if 12 <= len(line) <= 256 and line.strip() == line
                )
        by_group[name] = tuple(candidates)
        all_candidates.extend(candidates)

    unique = {candidate for candidate in all_candidates if all_candidates.count(candidate) == 1}
    assert all(unique.intersection(candidates) for candidates in by_group.values())
    return tuple(sorted(unique, key=lambda value: (len(value), value)))


def _complete_exception_bytes(error: BaseException) -> bytes:
    rendered = [str(error), repr(error), *traceback.format_exception(error)]
    visited = {id(error)}
    related = (error.__cause__, error.__context__)
    for item in related:
        if item is not None and id(item) not in visited:
            visited.add(id(item))
            rendered.extend((str(item), repr(item)))
            rendered.extend(traceback.format_exception(item))
    return "\n".join(rendered).encode("utf-8", errors="replace")


def test_claim_contract_is_exactly_twenty_one_true_and_fourteen_false():
    assert len(TRUE_CLAIMS) == 21
    assert len(set(TRUE_CLAIMS)) == 21
    assert len(FALSE_CLAIMS) == 14
    assert len(set(FALSE_CLAIMS)) == 14
    assert set(TRUE_CLAIMS).isdisjoint(FALSE_CLAIMS)
    assert set(NON_BOOLEAN_KEYS).isdisjoint((*TRUE_CLAIMS, *FALSE_CLAIMS))


def test_summary_has_exact_six_nonbooleans_and_thirty_five_boolean_claims(monkeypatch):
    module = _module()
    chain = _chain(monkeypatch)
    evidence = _issue(module, chain)
    summary = module.canonical_laya_runtime_supply_convergence_summary_bytes(evidence)
    payload = json.loads(summary)

    assert type(summary) is bytes
    assert summary.endswith(b"\n") is False
    assert set(payload) == {
        *NON_BOOLEAN_KEYS,
        *TRUE_CLAIMS,
        *FALSE_CLAIMS,
    }
    assert len(payload) == 6 + 35
    assert sum(type(value) is bool for value in payload.values()) == 35
    assert all(payload[name] is True for name in TRUE_CLAIMS)
    assert all(payload[name] is False for name in FALSE_CLAIMS)
    assert payload["layer_evidence_schema_version"] == chain.layer_evidence.schema_version
    assert payload["provenance_evidence_schema_version"] == chain.provenance_evidence.schema_version
    assert (
        payload["base_ancestry_evidence_schema_version"]
        == chain.base_ancestry_evidence.schema_version
    )
    assert (
        payload["runtime_identity_schema_version"]
        == chain.layer_evidence.runtime_identity.schema_version
    )
    assert payload["runtime_identity_sha256"] == chain.layer_evidence.runtime_identity.sha256
    assert "supply_content_sha256" not in payload
    assert summary == json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def test_evidence_claim_fields_are_factory_owned_and_conservative(monkeypatch):
    module = _module()
    evidence_type = module.LayaRuntimeSupplyConvergenceEvidence
    evidence_fields = {item.name: item for item in fields(evidence_type)}
    assert all(not evidence_fields[name].init for name in (*TRUE_CLAIMS, *FALSE_CLAIMS))

    evidence = _issue(module, _chain(monkeypatch))
    assert all(getattr(evidence, name) is True for name in TRUE_CLAIMS)
    assert all(getattr(evidence, name) is False for name in FALSE_CLAIMS)


def test_summary_repr_and_errors_do_not_disclose_supply_payloads_or_internal_digests(
    monkeypatch,
):
    module = _module()
    chain = _chain(monkeypatch)
    evidence = _issue(module, chain)
    metadata_markers = _metadata_markers(chain)
    payload_markers = _unique_ascii_payload_markers(chain)
    rendered = repr(evidence).encode("utf-8")
    summary = module.canonical_laya_runtime_supply_convergence_summary_bytes(evidence)
    assert all(marker.encode("utf-8") not in rendered for marker in metadata_markers)
    assert all(marker.encode("utf-8") not in summary for marker in metadata_markers)
    assert all(marker not in rendered for marker in payload_markers)
    assert all(marker not in summary for marker in payload_markers)

    secret = next(
        marker.decode("ascii")
        for marker in payload_markers
        if b"\n" not in marker and b"\r" not in marker
    )
    forged = _clone_exact(evidence, schema_version=secret)
    with pytest.raises(
        (TypeError, ValueError), match="evidence|issued|seal|schema|valid"
    ) as captured:
        module.canonical_laya_runtime_supply_convergence_summary_bytes(forged)
    forged_error = _complete_exception_bytes(captured.value)
    assert all(marker not in forged_error for marker in payload_markers)
    assert all(marker.encode("utf-8") not in forged_error for marker in metadata_markers)

    proxy = SimpleNamespace(
        schema_version=secret,
        runtime_supply_content_convergence_verified=True,
    )
    with pytest.raises((TypeError, ValueError)) as captured_proxy:
        module.canonical_laya_runtime_supply_convergence_summary_bytes(proxy)
    proxy_error = _complete_exception_bytes(captured_proxy.value)
    assert all(marker not in proxy_error for marker in payload_markers)
    assert all(marker.encode("utf-8") not in proxy_error for marker in metadata_markers)


def test_summary_makes_no_cotemporal_root_host_checkout_or_session_claim(monkeypatch):
    module = _module()
    payload = json.loads(
        module.canonical_laya_runtime_supply_convergence_summary_bytes(
            _issue(module, _chain(monkeypatch))
        )
    )
    forbidden_context_keys = {
        "capture_timestamp",
        "captured_at",
        "capture_context",
        "capture_session",
        "same_capture_time_verified",
        "same_filesystem_root_verified",
        "same_host_verified",
        "same_checkout_verified",
        "same_session_verified",
        "cotemporal_capture_verified",
    }
    assert forbidden_context_keys.isdisjoint(payload)
    assert set(payload) == {*NON_BOOLEAN_KEYS, *TRUE_CLAIMS, *FALSE_CLAIMS}


def test_public_surface_is_exactly_one_type_and_two_operations():
    module = _module()
    expected = {
        "LayaRuntimeSupplyConvergenceEvidence",
        "verify_laya_runtime_supply_convergence",
        "canonical_laya_runtime_supply_convergence_summary_bytes",
    }
    assert type(module.__all__) is tuple
    assert set(module.__all__) == expected
    assert len(module.__all__) == len(expected)
    assert {
        name for name, value in vars(module).items() if not name.startswith("_") and callable(value)
    } == expected
    assert tuple(inspect.signature(module.verify_laya_runtime_supply_convergence).parameters) == (
        "layer_evidence",
        "provenance_evidence",
        "base_ancestry_evidence",
    )
    assert tuple(
        inspect.signature(module.canonical_laya_runtime_supply_convergence_summary_bytes).parameters
    ) == ("evidence",)
    evidence_type = module.LayaRuntimeSupplyConvergenceEvidence
    assert is_dataclass(evidence_type)
    assert evidence_type.__dataclass_params__.frozen
    assert "__dict__" not in vars(evidence_type)


def _import_roots(tree: ast.AST) -> set[str]:
    return {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def _call_owner(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def test_module_ast_is_pure_and_has_no_adapter_dependency():
    module = _module()
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_roots = {
        "asyncio",
        "http",
        "io",
        "os",
        "pathlib",
        "requests",
        "shutil",
        "socket",
        "subprocess",
        "urllib",
    }
    assert not _import_roots(tree) & forbidden_roots
    assert "adapter" not in {root.lower() for root in _import_roots(tree)}
    name_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert name_calls.isdisjoint({"__import__", "compile", "eval", "exec", "open", "print"})
    attribute_owners = {
        _call_owner(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert attribute_owners.isdisjoint(forbidden_roots)


def test_supply_convergence_has_only_rootfs_materialization_authority_caller():
    repository = Path(__file__).parents[1]
    owner = repository / "src" / "human_feedback" / "runtime_supply_convergence.py"
    forbidden_symbols = {
        "human_feedback.runtime_supply_convergence",
        "verify_laya_runtime_supply_convergence",
        "canonical_laya_runtime_supply_convergence_summary_bytes",
        "LayaRuntimeSupplyConvergenceEvidence",
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
    assert offenders == ["src/human_feedback/runtime_rootfs_materialization.py"]
