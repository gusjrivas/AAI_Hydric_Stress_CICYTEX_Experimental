import ast
import json
import os
import sys
import traceback
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_laya_runtime_oci_layout import (
    BLOB_TOTAL_SIZE_BYTES,
    CONFIG_SHA256,
    CONFIG_SIZE_BYTES,
    LAYERS,
    LAYOUT_EVIDENCE_SCHEMA,
    LAYOUT_PROFILE_ID,
    LAYOUT_TOTAL_SIZE_BYTES,
    MANIFEST_SHA256,
    MANIFEST_SIZE_BYTES,
    _captured_manifest_bytes,
    _index_bytes,
    _layout_bytes,
    _oci_evidence,
)

IS_LINUX = sys.platform.startswith("linux")
REAL_LAYOUT_RELEASE_GATE_ENV = "LAYA_RUNTIME_OCI_LAYOUT_ROOT"
ADAPTER_RELATIVE_PATH = "src/human_feedback/adapters/filesystem_oci_layout.py"
CORE_RELATIVE_PATH = "src/human_feedback/runtime_oci_layout.py"
TRUE_FLAGS = (
    "artifact_integrity_verified",
    "oci_manifest_semantics_verified",
    "oci_layout_controls_bytes_verified",
    "oci_blob_inventory_verified",
    "oci_same_root_capture_verified",
    "oci_manifest_blob_bytes_verified",
    "oci_config_blob_bytes_verified",
    "oci_layer_blobs_bytes_verified",
    "oci_bytes_verified",
)
FALSE_FLAGS = (
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
)


def _adapter():
    from human_feedback.adapters import filesystem_oci_layout

    return filesystem_oci_layout


def _partial_layout_root(tmp_path: Path) -> Path:
    root = tmp_path / "oci-layout-root"
    digest_root = root / "blobs" / "sha256"
    digest_root.mkdir(parents=True)
    (root / "oci-layout").write_bytes(_layout_bytes())
    (root / "index.json").write_bytes(_index_bytes())
    manifest_payload = _captured_manifest_bytes()
    assert len(manifest_payload) == MANIFEST_SIZE_BYTES
    (digest_root / MANIFEST_SHA256).write_bytes(manifest_payload)
    sparse_specs = ((CONFIG_SHA256, CONFIG_SIZE_BYTES), *LAYERS)
    for digest, size_bytes in sparse_specs:
        with (digest_root / digest).open("wb") as stream:
            stream.truncate(size_bytes)
    return root


def _capture(root, evidence=None):
    module = _adapter()
    return module.capture_and_verify_laya_oci_layout(
        _oci_evidence() if evidence is None else evidence,
        root,
    )


def test_partial_layout_helper_builds_exact_closed_sparse_inventory(tmp_path):
    root = _partial_layout_root(tmp_path)
    digest_root = root / "blobs" / "sha256"
    expected = {
        MANIFEST_SHA256: MANIFEST_SIZE_BYTES,
        CONFIG_SHA256: CONFIG_SIZE_BYTES,
        **dict(LAYERS),
    }
    assert {path.name: path.stat().st_size for path in digest_root.iterdir()} == expected
    assert sum(expected.values()) == BLOB_TOTAL_SIZE_BYTES


def _forbid_seal(monkeypatch):
    module = _adapter()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("layout evidence sealer must not run after capture failure")

    monkeypatch.setattr(module, "_seal_laya_oci_layout_capture_authority", forbidden)
    monkeypatch.setattr(module, "_seal_laya_oci_layout_evidence", forbidden)


def _forbid_blob_verification_and_sealing(monkeypatch):
    module = _adapter()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("blob verification must not run before structure is accepted")

    monkeypatch.setattr(module, "verify_laya_oci_blob_chunks", forbidden, raising=False)
    monkeypatch.setattr(module.runtime_oci_layout, "verify_laya_oci_blob_chunks", forbidden)
    _forbid_seal(monkeypatch)


def _private_error(error: BaseException, *markers: str) -> None:
    rendered = "".join(traceback.TracebackException.from_exception(error).format(chain=True))
    for marker in markers:
        assert marker not in str(error)
        assert marker not in rendered
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def _product_python_files(repository: Path):
    for relative_root in ("backend", "src", "scripts"):
        root = repository / relative_root
        if root.is_dir():
            yield from root.rglob("*.py")


def _private_sealers_used(source: str) -> set[str]:
    tree = ast.parse(source)
    symbols = {
        "_seal_laya_oci_layout_capture_authority",
        "_seal_laya_oci_layout_evidence",
    }
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found.update(alias.name for alias in node.names if alias.name in symbols)
        if isinstance(node, ast.Name) and node.id in symbols:
            found.add(node.id)
        if isinstance(node, ast.Attribute) and node.attr in symbols:
            found.add(node.attr)
        if isinstance(node, ast.Constant) and node.value in symbols:
            found.add(node.value)
    return found


def test_adapter_is_the_only_product_caller_of_both_private_layout_sealers():
    repository = Path(__file__).parents[1]
    adapter = repository / ADAPTER_RELATIVE_PATH
    core = repository / CORE_RELATIVE_PATH
    assert adapter.is_file()
    adapter_source = adapter.read_text(encoding="utf-8")
    expected = {
        "_seal_laya_oci_layout_capture_authority",
        "_seal_laya_oci_layout_evidence",
    }
    assert _private_sealers_used(adapter_source) == expected

    offenders = []
    for path in _product_python_files(repository):
        if path in {adapter, core}:
            continue
        if _private_sealers_used(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []


def test_adapter_has_one_public_facade_and_only_stdlib_plus_core_dependencies():
    module = _adapter()
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_imports = {
        "__future__",
        "human_feedback.runtime_oci_layout",
        "os",
        "stat",
        "sys",
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
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_functions == {"capture_and_verify_laya_oci_layout"}
    public_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    assert public_classes == {
        "OciLayoutCaptureError",
        "SecureOciLayoutCaptureUnavailableError",
    }


def test_missing_secure_capability_fails_before_open_or_root_coercion(monkeypatch):
    module = _adapter()
    evidence = _oci_evidence()
    root_coercions = 0
    _forbid_seal(monkeypatch)

    class HostileRoot:
        def __fspath__(self):
            nonlocal root_coercions
            root_coercions += 1
            raise AssertionError("root must not be coerced without secure capability")

    monkeypatch.setattr(module, "_secure_oci_layout_capture_available", lambda: False)
    monkeypatch.setattr(
        module.os,
        "open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("os.open must not run without secure capability")
        ),
    )
    with pytest.raises(module.SecureOciLayoutCaptureUnavailableError):
        module.capture_and_verify_laya_oci_layout(evidence, HostileRoot())
    assert root_coercions == 0


@pytest.mark.skipif(os.name != "nt", reason="Windows must fail closed")
def test_windows_fails_closed_before_root_traversal(tmp_path):
    module = _adapter()
    with pytest.raises(module.SecureOciLayoutCaptureUnavailableError):
        _capture(tmp_path)


def test_invalid_evidence_fails_before_root_coercion_or_open(monkeypatch):
    module = _adapter()
    root_coercions = 0
    _forbid_seal(monkeypatch)

    class HostileRoot:
        def __fspath__(self):
            nonlocal root_coercions
            root_coercions += 1
            raise AssertionError("invalid evidence must fail before root coercion")

    proxy = SimpleNamespace(
        oci_manifest_semantics_verified=True,
        artifact_integrity_verified=True,
    )
    monkeypatch.setattr(module, "_secure_oci_layout_capture_available", lambda: True)
    monkeypatch.setattr(
        module.os,
        "open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid evidence must fail before os.open")
        ),
    )
    with pytest.raises((TypeError, ValueError), match="evidence|factory|seal|type"):
        module.capture_and_verify_laya_oci_layout(proxy, HostileRoot())
    assert root_coercions == 0


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize(
    "kind", ["duplicate-separator", "double-leading", "trailing", "relative", "root"]
)
def test_noncanonical_or_filesystem_root_fails_before_any_open(monkeypatch, tmp_path, kind):
    module = _adapter()
    raw = str(tmp_path / "layout")
    candidates = {
        "duplicate-separator": raw.replace("/", "//", 1),
        "double-leading": "/" + raw,
        "trailing": raw + "/",
        "relative": "relative/layout",
        "root": "/",
    }
    _forbid_seal(monkeypatch)
    monkeypatch.setattr(
        module.os,
        "open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("noncanonical root must fail before os.open")
        ),
    )
    with pytest.raises(module.OciLayoutCaptureError):
        _capture(candidates[kind])


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
def test_root_symlink_is_rejected_without_sealing(monkeypatch, tmp_path):
    target = _partial_layout_root(tmp_path)
    link = tmp_path / "layout-link"
    link.symlink_to(target, target_is_directory=True)
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError):
        _capture(link)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
def test_symlink_ancestor_of_root_is_rejected_before_verification(monkeypatch, tmp_path):
    real_parent = tmp_path / "private-real-parent"
    real_parent.mkdir()
    _partial_layout_root(real_parent)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError):
        _capture(linked_parent / "oci-layout-root")


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize("directory", ["blobs", "blobs/sha256"])
def test_blob_directory_symlink_is_rejected_before_verification(monkeypatch, tmp_path, directory):
    root = _partial_layout_root(tmp_path)
    target = root / directory
    outside = tmp_path / ("private-" + directory.replace("/", "-"))
    target.rename(outside)
    target.symlink_to(outside, target_is_directory=True)
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError):
        _capture(root)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize("control", ["oci-layout", "index.json"])
@pytest.mark.parametrize("kind", ["symlink", "fifo", "hardlink"])
def test_control_must_be_regular_single_link_file(monkeypatch, tmp_path, control, kind):
    root = _partial_layout_root(tmp_path)
    target = root / control
    payload = target.read_bytes()
    target.unlink()
    if kind == "symlink":
        outside = tmp_path / f"private-outside-{control}"
        outside.write_bytes(payload)
        target.symlink_to(outside)
    elif kind == "fifo":
        os.mkfifo(target)
    else:
        outside = tmp_path / f"private-hardlink-{control}"
        outside.write_bytes(payload)
        os.link(outside, target)
        assert target.stat().st_nlink == 2
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError):
        _capture(root)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize("entry", ["oci-layout", "index.json", "blobs"])
def test_each_missing_top_level_entry_is_rejected_without_sealing(monkeypatch, tmp_path, entry):
    root = _partial_layout_root(tmp_path)
    target = root / entry
    if target.is_dir():
        digest_root = target / "sha256"
        for child in digest_root.iterdir():
            child.unlink()
        digest_root.rmdir()
        target.rmdir()
    else:
        target.unlink()
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError):
        _capture(root)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize("entry_kind", ["file", "directory"])
def test_extra_top_level_entry_is_rejected_without_sealing(monkeypatch, tmp_path, entry_kind):
    root = _partial_layout_root(tmp_path)
    extra = root / "private-extra-root-entry"
    extra.mkdir() if entry_kind == "directory" else extra.write_bytes(b"private-extra")
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError) as captured:
        _capture(root)
    _private_error(captured.value, str(root), "private-extra-root-entry")


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize("control", ["oci-layout", "index.json"])
def test_controls_are_read_from_capture_root_and_private_on_failure(monkeypatch, tmp_path, control):
    module = _adapter()
    root = _partial_layout_root(tmp_path)
    marker = f"private-mutated-{control}"
    payload = marker.encode("ascii")
    (root / control).write_bytes(payload)
    seen = []
    original = module.runtime_oci_layout.prepare_laya_oci_layout_plan

    def spy(evidence, layout_bytes, index_bytes):
        seen.append((layout_bytes, index_bytes))
        return original(evidence, layout_bytes, index_bytes)

    monkeypatch.setattr(module.runtime_oci_layout, "prepare_laya_oci_layout_plan", spy)
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(module.OciLayoutCaptureError) as captured:
        _capture(root)
    assert len(seen) == 1
    selected = seen[0][0 if control == "oci-layout" else 1]
    assert selected == payload
    _private_error(captured.value, str(root), marker)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize("mutation", ["missing-digest", "extra-digest", "extra-algorithm"])
def test_closed_blob_inventory_rejects_missing_extra_and_algorithm_entries(
    monkeypatch, tmp_path, mutation
):
    root = _partial_layout_root(tmp_path)
    digest_root = root / "blobs" / "sha256"
    selected = digest_root / CONFIG_SHA256
    if mutation == "missing-digest":
        selected.unlink()
    elif mutation == "extra-digest":
        (digest_root / ("a" * 64)).write_bytes(b"private-extra-blob")
    else:
        other = root / "blobs" / "sha512"
        other.mkdir()
        (other / ("a" * 64)).write_bytes(b"private-extra-algorithm")
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError):
        _capture(root)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize("target_kind", ["blobs-file", "sha256-file"])
def test_blob_directories_must_be_exact_directories(monkeypatch, tmp_path, target_kind):
    root = _partial_layout_root(tmp_path)
    digest_root = root / "blobs" / "sha256"
    for child in digest_root.iterdir():
        child.unlink()
    digest_root.rmdir()
    if target_kind == "sha256-file":
        digest_root.write_bytes(b"private-not-directory")
    else:
        (root / "blobs").rmdir()
        (root / "blobs").write_bytes(b"private-not-directory")
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError):
        _capture(root)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize("kind", ["symlink", "fifo", "hardlink"])
def test_blob_must_be_regular_single_link_file(monkeypatch, tmp_path, kind):
    root = _partial_layout_root(tmp_path)
    digest_root = root / "blobs" / "sha256"
    digest, size_bytes = min(LAYERS, key=lambda item: item[1])
    blob = digest_root / digest
    blob.unlink()
    if kind == "symlink":
        outside = tmp_path / "private-outside-blob"
        with outside.open("wb") as stream:
            stream.truncate(size_bytes)
        blob.symlink_to(outside)
    elif kind == "fifo":
        os.mkfifo(blob)
    else:
        outside = tmp_path / "private-hardlink-source"
        with outside.open("wb") as stream:
            stream.truncate(size_bytes)
        os.link(outside, blob)
        assert blob.stat().st_nlink == 2
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError):
        _capture(root)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
def test_blob_inventory_aborts_at_expected_plus_one_without_sealing(monkeypatch, tmp_path):
    root = _partial_layout_root(tmp_path)
    digest_root = root / "blobs" / "sha256"
    (digest_root / ("a" * 64)).write_bytes(b"private-extra")
    assert len(tuple(digest_root.iterdir())) == 13
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(_adapter().OciLayoutCaptureError):
        _capture(root)


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
def test_opt_in_real_same_root_capture_produces_conservative_evidence():
    from human_feedback import runtime_oci_layout
    from human_feedback.runtime_oci_metadata import canonical_laya_runtime_oci_summary_bytes

    root = Path(os.environ[REAL_LAYOUT_RELEASE_GATE_ENV])
    oci_evidence = _oci_evidence()
    prior_summary = canonical_laya_runtime_oci_summary_bytes(oci_evidence)
    descriptors_before = len(tuple(Path("/proc/self/fd").iterdir()))
    evidence = _capture(root, oci_evidence)
    descriptors_after = len(tuple(Path("/proc/self/fd").iterdir()))

    assert type(evidence) is runtime_oci_layout.LayaRuntimeOciLayoutEvidence
    assert is_dataclass(evidence)
    assert not hasattr(evidence, "__dict__")
    assert evidence.schema_version == LAYOUT_EVIDENCE_SCHEMA
    assert evidence.plan.oci_evidence is oci_evidence
    assert evidence.runtime_identity is oci_evidence.runtime_identity
    assert type(evidence.receipts) is tuple
    assert len(evidence.receipts) == len(evidence.plan.blobs) == 12
    assert all(
        receipt.plan is evidence.plan
        and receipt.blob is evidence.plan.blobs[index]
        and receipt.blob_bytes_verified is True
        for index, receipt in enumerate(evidence.receipts)
    )
    assert evidence.plan.logical_file_count == 14
    assert evidence.plan.blob_total_size_bytes == BLOB_TOTAL_SIZE_BYTES
    assert evidence.plan.total_size_bytes == LAYOUT_TOTAL_SIZE_BYTES
    assert descriptors_after == descriptors_before
    for flag in TRUE_FLAGS:
        assert getattr(evidence, flag) is True
    for flag in FALSE_FLAGS:
        assert getattr(evidence, flag) is False

    for field in fields(evidence):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(evidence, field.name, getattr(evidence, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
            replace(evidence, **{field.name: getattr(evidence, field.name)})

    summary = runtime_oci_layout.canonical_laya_runtime_oci_layout_summary_bytes(evidence)
    decoded = json.loads(summary)
    expected = {
        "schema_version": LAYOUT_EVIDENCE_SCHEMA,
        "profile_id": LAYOUT_PROFILE_ID,
        "plan_schema_version": evidence.plan.schema_version,
        "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
        "runtime_identity_sha256": evidence.runtime_identity.sha256,
        **{flag: True for flag in TRUE_FLAGS},
        **{flag: False for flag in FALSE_FLAGS},
    }
    assert decoded == expected
    assert summary == json.dumps(
        expected, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")
    rendered = repr(evidence) + repr(evidence.receipts) + summary.decode("ascii")
    assert str(root) not in rendered
    assert all(blob.path not in rendered for blob in evidence.plan.blobs)
    assert all(blob.digest not in rendered for blob in evidence.plan.blobs)
    assert str(evidence.plan.total_size_bytes) not in rendered
    assert _layout_bytes().decode("ascii") not in rendered
    assert _index_bytes().decode("ascii") not in rendered
    assert canonical_laya_runtime_oci_summary_bytes(oci_evidence) == prior_summary


def test_full_positive_is_a_mandatory_external_release_gate_not_a_normal_fixture(
    monkeypatch,
):
    """Normal CI may specify failures, but cannot claim the 612 MB image was verified."""

    monkeypatch.delenv(REAL_LAYOUT_RELEASE_GATE_ENV, raising=False)
    fixture_root = Path(__file__).parent / "fixtures" / "laya" / "runtime_oci_layout"
    assert os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV) is None
    assert {path.name for path in fixture_root.iterdir()} == {"index.json", "oci-layout"}
    assert not (fixture_root / "blobs").exists()
