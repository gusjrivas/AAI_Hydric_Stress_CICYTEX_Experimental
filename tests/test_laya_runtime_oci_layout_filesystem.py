import ast
import hashlib
import json
import os
import shutil
import stat
import sys
import traceback
from collections import Counter
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
LAYER_CORE_RELATIVE_PATH = "src/human_feedback/runtime_oci_layers.py"
TAR_CORE_RELATIVE_PATH = "src/human_feedback/runtime_oci_tar.py"
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


def _tree_fingerprint(root: Path) -> tuple[tuple[object, ...], ...]:
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError("OCI layout fingerprint root must be a directory")
    records = []
    for path in sorted((root, *root.rglob("*"))):
        relative = "." if path == root else path.relative_to(root).as_posix()
        status = path.lstat()
        if path == root:
            if not stat.S_ISDIR(status.st_mode):
                raise ValueError("OCI layout fingerprint root must be a directory")
        elif not (stat.S_ISDIR(status.st_mode) or stat.S_ISREG(status.st_mode)):
            raise ValueError("OCI layout fingerprint entry type is unsafe")
        control_digest = None
        if relative in {"oci-layout", "index.json", f"blobs/sha256/{MANIFEST_SHA256}"}:
            control_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append(
            (
                relative,
                status.st_mode,
                status.st_size,
                status.st_mtime_ns,
                status.st_ino,
                control_digest,
            )
        )
    return tuple(records)


def _clone_file_reflink_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl

        with source.open("rb") as source_stream, destination.open("xb") as destination_stream:
            fcntl.ioctl(destination_stream.fileno(), 0x40049409, source_stream.fileno())
    except (ImportError, OSError):
        destination.unlink(missing_ok=True)
        shutil.copyfile(source, destination)


@pytest.fixture(scope="module")
def disposable_real_layout(tmp_path_factory):
    source_value = os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV)
    if not IS_LINUX or not source_value:
        pytest.skip("requires opt-in real external OCI layout on Linux")
    assert "PYTEST_XDIST_WORKER" not in os.environ, "external OCI gate must run serially"
    canonical = Path(source_value)
    canonical_before = _tree_fingerprint(canonical)
    clone_parent = tmp_path_factory.mktemp("laya-oci-layout-gate")
    lock = clone_parent / ".serial-capture.lock"
    lock_descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    clone = clone_parent / "layout"
    clone.mkdir()
    try:
        for source in sorted(canonical.rglob("*")):
            destination = clone / source.relative_to(canonical)
            source_status = source.lstat()
            if stat.S_ISDIR(source_status.st_mode):
                destination.mkdir(parents=True, exist_ok=True)
            elif stat.S_ISREG(source_status.st_mode):
                _clone_file_reflink_or_copy(source, destination)
            else:
                raise ValueError("OCI layout clone source entry type is unsafe")
        yield clone
        assert _tree_fingerprint(canonical) == canonical_before
    finally:
        os.close(lock_descriptor)
        lock.unlink(missing_ok=True)


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


def _layer_capture_contract_used(source: str) -> set[str]:
    tree = ast.parse(source)
    symbols = {
        "verify_laya_oci_layer_diff_id_chunks",
        "_seal_laya_oci_layer_diff_ids_capture_authority",
        "_seal_laya_runtime_oci_layer_diff_ids_evidence",
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


def _tar_capture_contract_used(source: str) -> set[str]:
    tree = ast.parse(source)
    symbols = {
        "_verify_laya_oci_tar_semantics_chunks_with_budget",
        "_seal_laya_oci_tar_semantics_capture_authority",
        "_seal_laya_runtime_oci_tar_semantics_evidence",
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


def test_filesystem_adapter_is_the_only_product_caller_of_layer_engine_and_sealers():
    repository = Path(__file__).parents[1]
    adapter = repository / ADAPTER_RELATIVE_PATH
    core = repository / LAYER_CORE_RELATIVE_PATH
    expected = {
        "verify_laya_oci_layer_diff_id_chunks",
        "_seal_laya_oci_layer_diff_ids_capture_authority",
        "_seal_laya_runtime_oci_layer_diff_ids_evidence",
    }
    assert _layer_capture_contract_used(adapter.read_text(encoding="utf-8")) == expected
    offenders = []
    for path in _product_python_files(repository):
        if path in {adapter, core}:
            continue
        if _layer_capture_contract_used(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []


def test_filesystem_adapter_is_the_only_product_caller_of_tar_engine_and_sealers():
    repository = Path(__file__).parents[1]
    adapter = repository / ADAPTER_RELATIVE_PATH
    core = repository / TAR_CORE_RELATIVE_PATH
    expected = {
        "_verify_laya_oci_tar_semantics_chunks_with_budget",
        "_seal_laya_oci_tar_semantics_capture_authority",
        "_seal_laya_runtime_oci_tar_semantics_evidence",
    }
    assert _tar_capture_contract_used(adapter.read_text(encoding="utf-8")) == expected
    offenders = []
    for path in _product_python_files(repository):
        if path in {adapter, core}:
            continue
        if _tar_capture_contract_used(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(repository).as_posix())
    assert offenders == []


def test_adapter_has_one_public_facade_and_only_stdlib_plus_core_dependencies():
    module = _adapter()
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_imports = {
        "__future__",
        "human_feedback.runtime_oci_layout",
        "human_feedback.runtime_oci_layers",
        "human_feedback.runtime_oci_tar",
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
    assert public_functions == {
        "capture_and_verify_laya_oci_layout",
        "capture_and_verify_laya_oci_layer_diff_ids",
        "capture_and_verify_laya_oci_tar_semantics",
    }
    public_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    assert public_classes == {
        "OciLayoutCaptureError",
        "SecureOciLayoutCaptureUnavailableError",
    }


def test_adapter_derives_layer_budgets_only_from_public_core_limits():
    module = _adapter()
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    def constant_integer_expression(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            left = constant_integer_expression(node.left)
            right = constant_integer_expression(node.right)
            if left is not None and right is not None:
                return left * right
        return None

    forbidden_duplicates = {
        "_MAX_OCI_LAYER_UNCOMPRESSED_BYTES",
        "_MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES",
    }
    assigned_names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
        if isinstance(target, ast.Name)
    }
    core_limit_attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "runtime_oci_layers"
        and node.attr
        in {
            "MAX_OCI_LAYER_UNCOMPRESSED_BYTES",
            "MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES",
        }
    }
    duplicated_limit_literals = {
        value
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for value in (constant_integer_expression(node.value),)
        if value in {2 * 1_024 * 1_024 * 1_024, 3 * 1_024 * 1_024 * 1_024}
    }

    assert assigned_names.isdisjoint(forbidden_duplicates)
    assert duplicated_limit_literals == set()
    assert core_limit_attributes == {
        "MAX_OCI_LAYER_UNCOMPRESSED_BYTES",
        "MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES",
    }
    assert callable(module._effective_layer_budget)


def test_effective_layer_budget_uses_live_core_caps_and_validates_remaining(monkeypatch):
    module = _adapter()
    monkeypatch.setattr(
        module.runtime_oci_layers,
        "MAX_OCI_LAYER_UNCOMPRESSED_BYTES",
        10,
    )
    monkeypatch.setattr(
        module.runtime_oci_layers,
        "MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES",
        25,
    )

    remaining_values = (25, 17, 9)
    budgets = tuple(module._effective_layer_budget(value) for value in remaining_values)
    assert budgets == (10, 10, 9)
    assert all(later < earlier for earlier, later in zip(remaining_values, remaining_values[1:]))
    assert all(later <= earlier for earlier, later in zip(budgets, budgets[1:]))

    for invalid in (True, False, 0, -1, 26, 1.0, None, "9"):
        with pytest.raises((TypeError, ValueError), match="remaining|budget|integer|positive"):
            module._effective_layer_budget(invalid)


def test_tar_facade_preflights_deep_evidence_before_root_coercion_or_open(monkeypatch):
    module = _adapter()
    touched = []

    class HostileRoot:
        def __fspath__(self):
            touched.append("fspath")
            raise AssertionError("private TAR root coercion")

    def forbidden_open(*_args, **_kwargs):
        touched.append("open")
        raise AssertionError("private TAR root open")

    monkeypatch.setattr(module.os, "open", forbidden_open)
    with pytest.raises(module.OciLayoutCaptureError, match="evidence|tar|invalid") as captured:
        module.capture_and_verify_laya_oci_tar_semantics(
            SimpleNamespace(schema_version="private-tar-proxy"),
            HostileRoot(),
        )
    assert touched == []
    _private_error(
        captured.value,
        "private-tar-proxy",
        "private TAR root coercion",
        "private TAR root open",
    )


def test_tar_capture_reuses_secure_fd_capture_and_closes_before_private_sealers():
    module = _adapter()
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_capture_and_verify_tar_semantics"
    )
    calls = {
        node.func.id
        if isinstance(node.func, ast.Name)
        else node.func.attr
        if isinstance(node.func, ast.Attribute)
        else ""
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
    }
    assert {
        "_open_root_directory",
        "_capture_control",
        "_verify_exact_laya_oci_layout_inventory",
        "_rehash_blob_for_layer_capture",
        "_verify_laya_oci_tar_semantics_chunks_with_budget",
        "_verify_laya_oci_layout_final_sweep",
        "_close_owned_once",
        "_seal_laya_oci_tar_semantics_capture_authority",
        "_seal_laya_runtime_oci_tar_semantics_evidence",
    } <= calls
    statements = list(ast.walk(function))
    close_lines = [
        node.lineno
        for node in statements
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_close_owned_once"
    ]
    authority_lines = [
        node.lineno
        for node in statements
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_seal_laya_oci_tar_semantics_capture_authority"
    ]
    evidence_lines = [
        node.lineno
        for node in statements
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_seal_laya_runtime_oci_tar_semantics_evidence"
    ]
    assert close_lines and authority_lines and evidence_lines
    assert min(close_lines) < min(authority_lines) < min(evidence_lines)


@pytest.mark.parametrize("extra_byte", [False, True])
def test_blob_chunks_coalesce_short_reads_into_bounded_logical_chunks(monkeypatch, extra_byte):
    module = _adapter()
    logical_chunk_bytes = 16
    expected_size = logical_chunk_bytes * 2 + 5
    payload = bytes(range(expected_size + int(extra_byte)))
    position = 0
    requests = []
    eof_requests = 0
    sentinel_executed = False

    monkeypatch.setattr(
        module.runtime_oci_layout,
        "MAX_OCI_BLOB_CHUNK_BYTES",
        logical_chunk_bytes,
    )

    def short_read(descriptor, amount):
        nonlocal position, eof_requests, sentinel_executed
        assert descriptor == 137
        requests.append((amount, position))
        if position == len(payload):
            if extra_byte:
                sentinel_executed = True
                raise AssertionError("private-read-after-expected-plus-one")
            eof_requests += 1
            return b""
        result = payload[position : position + min(7, amount)]
        position += len(result)
        return result

    monkeypatch.setattr(module.os, "read", short_read)
    chunks = tuple(module._blob_chunks(137, expected_size))

    assert b"".join(chunks) == payload
    assert all(type(chunk) is bytes and 0 < len(chunk) <= logical_chunk_bytes for chunk in chunks)
    assert tuple(map(len, chunks)) == (
        logical_chunk_bytes,
        logical_chunk_bytes,
        5 + int(extra_byte),
    )
    assert all(
        0 < amount <= min(logical_chunk_bytes, expected_size + 1 - before)
        for amount, before in requests
    )
    assert eof_requests == (0 if extra_byte else 1)
    assert sentinel_executed is False


def test_blob_chunking_is_stream_bounded_and_layer08_fits_the_receipt_cap():
    module = _adapter()
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    blob_chunks = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_blob_chunks"
    )
    forbidden_materializers = {
        node.func.attr
        for node in ast.walk(blob_chunks)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"join", "readall", "read_bytes", "readlines"}
    } | {
        node.func.id
        for node in ast.walk(blob_chunks)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"list", "tuple"}
    }
    assert forbidden_materializers == set()

    layer08_size = LAYERS[8][1]
    assert layer08_size == 511_506_914
    maximum = module.runtime_oci_layout.MAX_OCI_BLOB_CHUNK_BYTES
    required_chunks = (layer08_size + maximum - 1) // maximum
    assert required_chunks == 488
    assert required_chunks <= module.runtime_oci_layout.MAX_OCI_BLOB_CHUNKS


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
    from human_feedback.runtime_oci_metadata import LayaRuntimeOciEvidence

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

    class EvidenceSubclass(LayaRuntimeOciEvidence):
        pass

    subclass = object.__new__(EvidenceSubclass)
    monkeypatch.setattr(module, "_secure_oci_layout_capture_available", lambda: True)
    monkeypatch.setattr(
        module.os,
        "open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid evidence must fail before os.open")
        ),
    )
    for invalid in (proxy, subclass):
        with pytest.raises((TypeError, ValueError), match="evidence|factory|seal|type"):
            module.capture_and_verify_laya_oci_layout(invalid, HostileRoot())
    assert root_coercions == 0


def test_invalid_config_evidence_fails_before_layer_root_coercion_or_open(monkeypatch):
    module = _adapter()
    root_coercions = 0

    class HostileRoot:
        def __fspath__(self):
            nonlocal root_coercions
            root_coercions += 1
            raise AssertionError("private layer root must not be coerced")

    monkeypatch.setattr(
        module.os,
        "open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("os.open must not run for invalid config evidence")
        ),
    )
    with pytest.raises((TypeError, ValueError), match="config|evidence|valid") as captured:
        module.capture_and_verify_laya_oci_layer_diff_ids(
            SimpleNamespace(oci_config_semantics_verified=True),
            HostileRoot(),
        )
    assert root_coercions == 0
    _private_error(captured.value, "private layer root")


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux absolute root traversal")
def test_root_component_cap_is_private_bounded_and_enforced_before_open(monkeypatch):
    module = _adapter()
    limit = module._MAX_OCI_LAYOUT_ROOT_COMPONENTS
    assert type(limit) is int
    assert 32 <= limit <= 256
    opened = 0

    def counted_open(*_args, **_kwargs):
        nonlocal opened
        opened += 1
        raise OSError("private structural traversal sentinel")

    monkeypatch.setattr(module, "_secure_oci_layout_capture_available", lambda: True)
    monkeypatch.setattr(module.os, "open", counted_open)
    _forbid_seal(monkeypatch)

    boundary = "/" + "/".join(f"c{index}" for index in range(limit))
    with pytest.raises(module.OciLayoutCaptureError):
        _capture(boundary)
    assert opened == 1

    opened = 0
    over_limit = boundary + "/private-over-limit-component"
    with pytest.raises(module.OciLayoutCaptureError) as captured:
        _capture(over_limit)
    assert opened == 0
    _private_error(captured.value, over_limit, "private-over-limit-component")


def test_root_fspath_exception_is_private_and_fails_before_open(monkeypatch):
    module = _adapter()
    opened = 0
    marker = "private-hostile-fspath-marker"

    class HostileRoot:
        def __fspath__(self):
            raise RuntimeError(marker)

    def counted_open(*_args, **_kwargs):
        nonlocal opened
        opened += 1
        raise AssertionError("os.open must not run after root coercion failure")

    monkeypatch.setattr(module, "_secure_oci_layout_capture_available", lambda: True)
    monkeypatch.setattr(module.os, "open", counted_open)
    _forbid_seal(monkeypatch)
    with pytest.raises(module.OciLayoutCaptureError) as captured:
        _capture(HostileRoot())
    assert opened == 0
    _private_error(captured.value, marker)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd capture")
@pytest.mark.parametrize(
    "kind",
    [
        "duplicate-separator",
        "double-leading",
        "trailing",
        "relative",
        "dot-component",
        "dotdot-component",
        "empty",
        "root",
    ],
)
def test_noncanonical_or_filesystem_root_fails_before_any_open(monkeypatch, tmp_path, kind):
    module = _adapter()
    raw = str(tmp_path / "layout")
    candidates = {
        "duplicate-separator": raw.replace("/", "//", 1),
        "double-leading": "/" + raw,
        "trailing": raw + "/",
        "relative": "relative/layout",
        "dot-component": raw + "/./private-dot-layout",
        "dotdot-component": raw + "/../private-dotdot-layout",
        "empty": "",
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
    with pytest.raises(module.OciLayoutCaptureError) as captured:
        _capture(candidates[kind])
    marker = candidates[kind]
    if kind not in {"empty", "root"}:
        _private_error(captured.value, marker)
    else:
        _private_error(captured.value)


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
@pytest.mark.parametrize(
    ("control", "limit_name"),
    [
        ("oci-layout", "MAX_OCI_LAYOUT_BYTES"),
        ("index.json", "MAX_OCI_INDEX_BYTES"),
    ],
)
def test_oversized_control_is_rejected_before_read_verification_or_sealing(
    monkeypatch, tmp_path, control, limit_name
):
    module = _adapter()
    root = _partial_layout_root(tmp_path)
    limit = getattr(module.runtime_oci_layout, limit_name)
    with (root / control).open("wb") as stream:
        stream.truncate(limit + 1)

    def forbidden_read(*_args, **_kwargs):
        raise AssertionError("oversized control must fail before os.read")

    monkeypatch.setattr(module.os, "read", forbidden_read)
    monkeypatch.setattr(
        module.runtime_oci_layout,
        "prepare_laya_oci_layout_plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("oversized control must fail before plan preparation")
        ),
    )
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(module.OciLayoutCaptureError) as captured:
        _capture(root)
    _private_error(captured.value, str(root))


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


def _fds_within(root: Path) -> set[int]:
    descriptors = set()
    root_text = str(root)
    for entry in Path("/proc/self/fd").iterdir():
        try:
            target = os.readlink(entry)
        except OSError:
            continue
        if target == root_text or target.startswith(root_text + os.sep):
            descriptors.add(int(entry.name))
    return descriptors


def _capture_with_instrumented_fault(root, operation=None, fault_at=None):
    module = _adapter()
    originals = {
        name: getattr(module.os, name) for name in ("open", "read", "scandir", "fstat", "close")
    }
    calls = Counter()
    opened = Counter()
    closed = Counter()
    injected = False

    def should_fail(name):
        nonlocal injected
        calls[name] += 1
        if name == operation and calls[name] == fault_at:
            injected = True
            return True
        return False

    def tracked_open(*args, **kwargs):
        if should_fail("open"):
            raise OSError("private injected open failure")
        descriptor = originals["open"](*args, **kwargs)
        opened[descriptor] += 1
        return descriptor

    def tracked_read(*args, **kwargs):
        if should_fail("read"):
            raise OSError("private injected read failure")
        return originals["read"](*args, **kwargs)

    def tracked_scandir(*args, **kwargs):
        if should_fail("scandir"):
            raise OSError("private injected scandir failure")
        return originals["scandir"](*args, **kwargs)

    def tracked_fstat(*args, **kwargs):
        if should_fail("fstat"):
            raise OSError("private injected fstat failure")
        return originals["fstat"](*args, **kwargs)

    def tracked_close(descriptor):
        closed[descriptor] += 1
        result = originals["close"](descriptor)
        if should_fail("close"):
            raise OSError("private injected close failure")
        return result

    before = _fds_within(root)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module.os, "open", tracked_open)
        patch.setattr(module.os, "read", tracked_read)
        patch.setattr(module.os, "scandir", tracked_scandir)
        patch.setattr(module.os, "fstat", tracked_fstat)
        patch.setattr(module.os, "close", tracked_close)
        _forbid_seal(patch)
        with pytest.raises(module.OciLayoutCaptureError) as captured:
            _capture(root)
    after = _fds_within(root)
    assert after == before == set()
    assert closed == opened
    _private_error(
        captured.value,
        str(root),
        *(("private injected",) if operation is not None else ()),
    )
    return calls, injected


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux descriptor inspection")
def test_every_observed_capture_fault_point_closes_all_fds_once_and_never_seals(tmp_path):
    baseline_root = _partial_layout_root(tmp_path / "baseline")
    baseline_calls, baseline_injected = _capture_with_instrumented_fault(baseline_root)
    assert baseline_injected is False
    assert all(baseline_calls[name] > 0 for name in ("open", "read", "scandir", "fstat", "close"))

    for operation in ("open", "read", "scandir", "fstat", "close"):
        for fault_at in range(1, baseline_calls[operation] + 1):
            root = _partial_layout_root(tmp_path / f"{operation}-{fault_at}")
            _calls, injected = _capture_with_instrumented_fault(root, operation, fault_at)
            assert injected is True, (operation, fault_at)


@pytest.mark.skipif(not IS_LINUX, reason="requires Linux dir-fd inventory")
def test_inventory_stops_on_thirteenth_unexpected_entry_without_consuming_fourteenth(
    monkeypatch, tmp_path
):
    module = _adapter()
    root = _partial_layout_root(tmp_path)
    digest_root = root / "blobs" / "sha256"
    extra = "a" * 64
    (digest_root / extra).write_bytes(b"private-extra")
    original_scandir = module.os.scandir
    consumed = 0

    class SentinelScandir:
        def __init__(self, argument):
            self._context = original_scandir(argument)
            entries = list(self._context)
            self._entries = iter(sorted(entries, key=lambda entry: entry.name == extra))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self._context.__exit__(*args)

        def __iter__(self):
            return self

        def __next__(self):
            nonlocal consumed
            if consumed == 13:
                raise AssertionError("fourteenth inventory entry must not be consumed")
            entry = next(self._entries)
            consumed += 1
            return entry

    def bounded_scandir(argument):
        try:
            path = (
                os.readlink(f"/proc/self/fd/{argument}") if type(argument) is int else str(argument)
            )
        except OSError:
            path = ""
        if Path(path).name == "sha256":
            return SentinelScandir(argument)
        return original_scandir(argument)

    monkeypatch.setattr(module.os, "scandir", bounded_scandir)
    _forbid_blob_verification_and_sealing(monkeypatch)
    with pytest.raises(module.OciLayoutCaptureError):
        _capture(root)
    assert consumed == 13


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
def test_opt_in_real_same_root_capture_produces_conservative_evidence(
    monkeypatch, disposable_real_layout
):
    from human_feedback import runtime_oci_layout
    from human_feedback.runtime_oci_metadata import canonical_laya_runtime_oci_summary_bytes

    root = disposable_real_layout
    oci_evidence = _oci_evidence()
    prior_summary = canonical_laya_runtime_oci_summary_bytes(oci_evidence)
    module = _adapter()
    original_open = module.os.open
    original_close = module.os.close
    opened = Counter()
    closed = Counter()

    def tracked_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        opened[descriptor] += 1
        return descriptor

    def tracked_close(descriptor):
        closed[descriptor] += 1
        return original_close(descriptor)

    monkeypatch.setattr(module.os, "open", tracked_open)
    monkeypatch.setattr(module.os, "close", tracked_close)
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
    assert opened
    assert closed == opened
    for flag in TRUE_FLAGS:
        assert getattr(evidence, flag) is True
    for flag in FALSE_FLAGS:
        assert getattr(evidence, flag) is False

    authority = runtime_oci_layout._seal_laya_oci_layout_capture_authority(
        evidence.plan,
        evidence.receipts,
        controls_captured_from_same_root=True,
        inventory_captured_from_same_root=True,
        final_fd_sweep_verified=True,
    )
    assert type(authority) is runtime_oci_layout._LayaOciLayoutCaptureAuthority
    assert runtime_oci_layout._seal_laya_oci_layout_evidence(authority) == evidence
    for field in fields(authority):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(authority, field.name, getattr(authority, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|token|seal|direct|valid"):
            replace(authority, **{field.name: getattr(authority, field.name)})

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
    rendered = repr(authority) + repr(evidence) + repr(evidence.receipts) + summary.decode("ascii")
    assert str(root) not in rendered
    assert all(blob.path not in rendered for blob in evidence.plan.blobs)
    assert all(blob.digest not in rendered for blob in evidence.plan.blobs)
    assert str(evidence.plan.total_size_bytes) not in rendered
    assert _layout_bytes().decode("ascii") not in rendered
    assert _index_bytes().decode("ascii") not in rendered
    assert _captured_manifest_bytes().decode("ascii") not in rendered
    assert canonical_laya_runtime_oci_summary_bytes(oci_evidence) == prior_summary


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
def test_opt_in_real_receipts_close_authority_matrix_without_shortcuts(
    disposable_real_layout,
):
    from human_feedback import runtime_oci_layout

    evidence = _capture(disposable_real_layout)
    plan = evidence.plan
    receipts = evidence.receipts
    assert len(receipts) == 12
    invalid_receipts = (
        list(receipts),
        receipts[:-1],
        receipts + (receipts[-1],),
        (receipts[0], receipts[0], *receipts[2:]),
        tuple(reversed(receipts)),
        (
            SimpleNamespace(
                **{
                    field: getattr(receipts[0], field)
                    for field in ("plan", "blob", "blob_bytes_verified")
                }
            ),
            *receipts[1:],
        ),
    )
    for invalid in invalid_receipts:
        with pytest.raises(
            (TypeError, ValueError), match="tuple|count|complete|order|duplicate|type"
        ):
            runtime_oci_layout._seal_laya_oci_layout_capture_authority(
                plan,
                invalid,
                controls_captured_from_same_root=True,
                inventory_captured_from_same_root=True,
                final_fd_sweep_verified=True,
            )

    for field in (
        "controls_captured_from_same_root",
        "inventory_captured_from_same_root",
        "final_fd_sweep_verified",
    ):
        for invalid in (False, 1, None):
            flags = {
                "controls_captured_from_same_root": True,
                "inventory_captured_from_same_root": True,
                "final_fd_sweep_verified": True,
            }
            flags[field] = invalid
            with pytest.raises(
                (TypeError, ValueError), match="capture|same.root|inventory|sweep|flag"
            ):
                runtime_oci_layout._seal_laya_oci_layout_capture_authority(plan, receipts, **flags)

    second_plan = runtime_oci_layout.prepare_laya_oci_layout_plan(
        plan.oci_evidence, _layout_bytes(), _index_bytes()
    )
    with pytest.raises(ValueError, match="plan|identity|foreign") as captured:
        runtime_oci_layout._seal_laya_oci_layout_capture_authority(
            second_plan,
            receipts,
            controls_captured_from_same_root=True,
            inventory_captured_from_same_root=True,
            final_fd_sweep_verified=True,
        )
    assert "receipt" not in str(captured.value).lower()
    assert "blob" not in str(captured.value).lower()


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
def test_opt_in_atomic_capture_order_is_observable_and_exact(monkeypatch, disposable_real_layout):
    module = _adapter()
    events = []
    opened = Counter()
    closed = Counter()
    original_open = module.os.open
    original_close = module.os.close

    def tracked_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        opened[descriptor] += 1
        return descriptor

    def tracked_close(descriptor):
        closed[descriptor] += 1
        return original_close(descriptor)

    monkeypatch.setattr(module.os, "open", tracked_open)
    monkeypatch.setattr(module.os, "close", tracked_close)

    def wrap(owner, name, event):
        original = getattr(owner, name)

        def observed(*args, **kwargs):
            result = original(*args, **kwargs)
            events.append(event)
            return result

        monkeypatch.setattr(owner, name, observed)

    wrap(module.runtime_oci_layout, "prepare_laya_oci_layout_plan", "controls")
    wrap(module, "_verify_exact_laya_oci_layout_inventory", "inventory")
    original_verify = module.verify_laya_oci_blob_chunks

    def verify(*args, **kwargs):
        result = original_verify(*args, **kwargs)
        events.append("receipt")
        return result

    monkeypatch.setattr(module, "verify_laya_oci_blob_chunks", verify)
    wrap(module, "_verify_laya_oci_layout_final_sweep", "sweep")
    original_authority_sealer = module._seal_laya_oci_layout_capture_authority

    def seal_authority(*args, **kwargs):
        assert closed == opened
        assert _fds_within(disposable_real_layout) == set()
        events.extend(("close-complete", "authority"))
        return original_authority_sealer(*args, **kwargs)

    monkeypatch.setattr(module, "_seal_laya_oci_layout_capture_authority", seal_authority)
    wrap(module, "_seal_laya_oci_layout_evidence", "evidence")
    _capture(disposable_real_layout)
    assert events == [
        "controls",
        "inventory",
        *("receipt" for _index in range(12)),
        "sweep",
        "close-complete",
        "authority",
        "evidence",
    ]


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
@pytest.mark.parametrize("target_kind", ["oci-layout", "index.json", "manifest"])
@pytest.mark.parametrize("mutation", ["same-size", "grow", "truncate", "replace"])
def test_opt_in_file_toctou_after_read_is_rejected_and_restored(
    monkeypatch, disposable_real_layout, target_kind, mutation
):
    module = _adapter()
    root = disposable_real_layout
    target = (
        root / target_kind
        if target_kind != "manifest"
        else root / "blobs" / "sha256" / MANIFEST_SHA256
    )
    original_payload = target.read_bytes()
    displaced = target.with_name(target.name + ".private-toctou-original")
    original_read = module.os.read
    mutated = False

    def mutate_once():
        nonlocal mutated
        if mutated:
            return
        mutated = True
        if mutation == "same-size":
            replacement = bytes([original_payload[0] ^ 1]) + original_payload[1:]
            target.write_bytes(replacement)
        elif mutation == "grow":
            target.write_bytes(original_payload + b"x")
        elif mutation == "truncate":
            target.write_bytes(original_payload[:-1])
        else:
            target.rename(displaced)
            target.write_bytes(original_payload)

    def adversarial_read(descriptor, amount):
        payload = original_read(descriptor, amount)
        try:
            captured_path = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
        except OSError:
            return payload
        if payload and captured_path == target:
            mutate_once()
        return payload

    monkeypatch.setattr(module.os, "read", adversarial_read)
    _forbid_seal(monkeypatch)
    try:
        with pytest.raises(module.OciLayoutCaptureError) as captured:
            _capture(root)
        assert mutated is True
        _private_error(captured.value, str(root), original_payload.decode("ascii", errors="ignore"))
    finally:
        if displaced.exists():
            target.unlink(missing_ok=True)
            displaced.rename(target)
        else:
            target.write_bytes(original_payload)


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
@pytest.mark.parametrize("target_kind", ["index.json", "blobs", "sha256", "root"])
def test_opt_in_rename_replace_between_last_blob_and_final_sweep_is_rejected(
    monkeypatch, disposable_real_layout, target_kind
):
    module = _adapter()
    root = disposable_real_layout
    target = {
        "index.json": root / "index.json",
        "blobs": root / "blobs",
        "sha256": root / "blobs" / "sha256",
        "root": root,
    }[target_kind]
    displaced = target.with_name(target.name + ".private-toctou-original")
    original_verify = module.verify_laya_oci_blob_chunks
    verified = 0
    mutated = False

    def verify(*args, **kwargs):
        nonlocal verified, mutated
        receipt = original_verify(*args, **kwargs)
        verified += 1
        if verified == 12:
            target.rename(displaced)
            if target_kind == "index.json":
                target.write_bytes(displaced.read_bytes())
            else:
                target.mkdir()
            mutated = True
        return receipt

    monkeypatch.setattr(module, "verify_laya_oci_blob_chunks", verify)
    _forbid_seal(monkeypatch)
    try:
        with pytest.raises(module.OciLayoutCaptureError) as captured:
            _capture(root)
        assert verified == 12
        assert mutated is True
        _private_error(captured.value, str(root))
    finally:
        if target_kind == "index.json":
            target.unlink(missing_ok=True)
        elif target.exists():
            target.rmdir()
        if displaced.exists():
            displaced.rename(target)


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
@pytest.mark.parametrize(
    "mutation", ["extra-top-file", "extra-top-directory", "thirteenth-digest", "sha512"]
)
def test_opt_in_late_inventory_mutation_after_receipt_twelve_is_rejected(
    monkeypatch, disposable_real_layout, mutation
):
    module = _adapter()
    root = disposable_real_layout
    marker = "private-late-inventory-entry"
    target = {
        "extra-top-file": root / marker,
        "extra-top-directory": root / marker,
        "thirteenth-digest": root / "blobs" / "sha256" / ("a" * 64),
        "sha512": root / "blobs" / "sha512",
    }[mutation]
    original_verify = module.verify_laya_oci_blob_chunks
    verified = 0

    def verify(*args, **kwargs):
        nonlocal verified
        receipt = original_verify(*args, **kwargs)
        verified += 1
        if verified == 12:
            if mutation in {"extra-top-directory", "sha512"}:
                target.mkdir()
                if mutation == "sha512":
                    (target / ("b" * 64)).write_bytes(marker.encode("ascii"))
            else:
                target.write_bytes(marker.encode("ascii"))
        return receipt

    monkeypatch.setattr(module, "verify_laya_oci_blob_chunks", verify)
    _forbid_seal(monkeypatch)
    try:
        with pytest.raises(module.OciLayoutCaptureError) as captured:
            _capture(root)
        assert verified == 12
        _private_error(captured.value, str(root), marker)
    finally:
        if target.is_dir():
            for child in target.iterdir():
                child.unlink()
            target.rmdir()
        else:
            target.unlink(missing_ok=True)


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
@pytest.mark.parametrize("fault", ["final-sweep-scandir", "final-sweep-fstat", "final-close"])
def test_opt_in_valid_layout_late_faults_close_all_fds_and_never_seal(
    monkeypatch, disposable_real_layout, fault
):
    module = _adapter()
    root = disposable_real_layout
    original_open = module.os.open
    original_close = module.os.close
    original_sweep = module._verify_laya_oci_layout_final_sweep
    opened = Counter()
    closed = Counter()
    injected = False
    verified = 0
    sweep_completed = False
    events = []
    original_verify = module.verify_laya_oci_blob_chunks

    def tracked_verify(*args, **kwargs):
        nonlocal verified
        receipt = original_verify(*args, **kwargs)
        verified += 1
        events.append("receipt")
        return receipt

    def tracked_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        opened[descriptor] += 1
        return descriptor

    def tracked_close(descriptor):
        nonlocal injected
        closed[descriptor] += 1
        result = original_close(descriptor)
        if fault == "final-close" and verified == 12 and sweep_completed and closed == opened:
            injected = True
            events.append("final-close")
            raise OSError("private final close failure")
        return result

    def failing_sweep(*args, **kwargs):
        nonlocal injected
        operation = "scandir" if fault == "final-sweep-scandir" else "fstat"
        original = getattr(module.os, operation)

        def fail(*_args, **_kwargs):
            nonlocal injected
            injected = True
            raise OSError(f"private final sweep {operation} failure")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module.os, operation, fail)
            try:
                return original_sweep(*args, **kwargs)
            finally:
                patch.setattr(module.os, operation, original)

    def tracked_sweep(*args, **kwargs):
        nonlocal sweep_completed
        result = original_sweep(*args, **kwargs)
        sweep_completed = True
        events.append("sweep-complete")
        return result

    monkeypatch.setattr(module.os, "open", tracked_open)
    monkeypatch.setattr(module.os, "close", tracked_close)
    monkeypatch.setattr(module, "verify_laya_oci_blob_chunks", tracked_verify)
    if fault != "final-close":
        monkeypatch.setattr(module, "_verify_laya_oci_layout_final_sweep", failing_sweep)
    else:
        monkeypatch.setattr(module, "_verify_laya_oci_layout_final_sweep", tracked_sweep)
    _forbid_seal(monkeypatch)
    with pytest.raises(module.OciLayoutCaptureError) as captured:
        _capture(root)
    assert injected is True
    assert verified == 12
    if fault == "final-close":
        assert sweep_completed is True
        assert events == [*("receipt" for _index in range(12)), "sweep-complete", "final-close"]
    else:
        assert sweep_completed is False
    assert closed == opened
    assert _fds_within(root) == set()
    _private_error(captured.value, str(root), "private final")


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
def test_external_layout_gate_uses_distinct_disposable_paths_and_preserves_canonical(
    disposable_real_layout,
):
    canonical = Path(os.environ[REAL_LAYOUT_RELEASE_GATE_ENV])
    canonical_before = _tree_fingerprint(canonical)
    assert disposable_real_layout != canonical
    assert not os.path.samefile(disposable_real_layout, canonical)
    assert {
        path.relative_to(disposable_real_layout).as_posix()
        for path in disposable_real_layout.rglob("*")
    } == {path.relative_to(canonical).as_posix() for path in canonical.rglob("*")}
    assert _tree_fingerprint(canonical) == canonical_before


def test_full_positive_is_an_external_opt_in_release_gate_not_a_normal_ci_fixture(
    monkeypatch,
):
    """Normal CI does not claim that the external 612 MB image was verified."""

    monkeypatch.delenv(REAL_LAYOUT_RELEASE_GATE_ENV, raising=False)
    fixture_root = Path(__file__).parent / "fixtures" / "laya" / "runtime_oci_layout"
    assert os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV) is None
    assert {path.name for path in fixture_root.iterdir()} == {"index.json", "oci-layout"}
    assert not (fixture_root / "blobs").exists()


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
def test_opt_in_same_root_layer_diff_ids_are_all_or_nothing_and_conservative(monkeypatch):
    from human_feedback import runtime_oci_layers
    from human_feedback.runtime_oci_config import validate_laya_runtime_oci_config_semantics

    assert "PYTEST_XDIST_WORKER" not in os.environ, "external OCI gate must run serially"
    root = Path(os.environ[REAL_LAYOUT_RELEASE_GATE_ENV])
    before = _tree_fingerprint(root)
    layout_evidence = _capture(root)
    config_blob = layout_evidence.plan.blobs[1]
    config_payload = (root / config_blob.path).read_bytes()
    config_evidence = validate_laya_runtime_oci_config_semantics(
        layout_evidence,
        config_payload,
    )

    module = _adapter()
    blob_calls = []
    layer_calls = []
    layer_budgets = []
    original_blob_verifier = module.runtime_oci_layout.verify_laya_oci_blob_chunks
    original_layer_verifier = runtime_oci_layers.verify_laya_oci_layer_diff_id_chunks

    def blob_spy(plan, digest, chunks):
        blob_calls.append(digest)
        return original_blob_verifier(plan, digest, chunks)

    def layer_spy(plan, digest, chunks, *, max_uncompressed_bytes=None):
        layer_calls.append(digest)
        layer_budgets.append(max_uncompressed_bytes)
        return original_layer_verifier(
            plan,
            digest,
            chunks,
            max_uncompressed_bytes=max_uncompressed_bytes,
        )

    monkeypatch.setattr(module.runtime_oci_layout, "verify_laya_oci_blob_chunks", blob_spy)
    monkeypatch.setattr(
        runtime_oci_layers,
        "verify_laya_oci_layer_diff_id_chunks",
        layer_spy,
    )
    evidence = module.capture_and_verify_laya_oci_layer_diff_ids(config_evidence, root)

    assert type(evidence) is runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence
    assert evidence.config_evidence is config_evidence
    assert evidence.plan.config_evidence is config_evidence
    assert evidence.layout_evidence is config_evidence.layout_evidence
    assert evidence.layout_plan is config_evidence.layout_evidence.plan
    assert evidence.runtime_identity is config_evidence.runtime_identity
    assert type(evidence.receipts) is tuple
    assert len(evidence.receipts) == 10
    expected_layer_digests = tuple(blob.digest for blob in evidence.plan.layer_blobs)
    assert tuple(layer_calls) == expected_layer_digests
    cumulative = 0
    expected_budgets = []
    remaining_before_each = []
    for receipt in evidence.receipts:
        remaining = runtime_oci_layers.MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES - cumulative
        assert remaining > 0
        remaining_before_each.append(remaining)
        expected_budgets.append(min(runtime_oci_layers.MAX_OCI_LAYER_UNCOMPRESSED_BYTES, remaining))
        cumulative += receipt.uncompressed_size_bytes
    assert tuple(layer_budgets) == tuple(expected_budgets)
    assert all(
        later < earlier for earlier, later in zip(remaining_before_each, remaining_before_each[1:])
    )
    assert all(later <= earlier for earlier, later in zip(layer_budgets, layer_budgets[1:]))
    assert cumulative < runtime_oci_layers.MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES
    assert layer_budgets[-1] > 0
    expected_blob_calls = Counter(blob.digest for blob in evidence.layout_plan.blobs)
    expected_blob_calls.update(expected_layer_digests)
    assert Counter(blob_calls) == expected_blob_calls
    assert all(
        receipt.plan is evidence.plan
        and receipt.layer_blob is evidence.plan.layer_blobs[position]
        and receipt.compressed_receipt is evidence.plan.layer_receipts[position]
        and receipt.layer_position == position
        and receipt.layer_diff_id_verified is True
        for position, receipt in enumerate(evidence.receipts)
    )
    true_flags = (
        *TRUE_FLAGS,
        "oci_config_semantics_verified",
        "oci_layer_diff_ids_verified",
    )
    false_flags = (
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
        "base_ancestry_verified",
        "rootfs_materialized",
        "runtime_materialized",
        "executor_available",
        "inference_executed",
    )
    for flag in true_flags:
        assert getattr(evidence, flag) is True
    for flag in false_flags:
        assert getattr(evidence, flag) is False
    assert (
        sum(
            (
                77_885_440,
                8_792_064,
                47_493_632,
                5_120,
                53_649_408,
                93_210_112,
                41_984,
                1_024,
                1_908_688_896,
                110_080,
            )
        )
        < runtime_oci_layers.MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES
    )

    summary = runtime_oci_layers.canonical_laya_runtime_oci_layer_diff_ids_summary_bytes(evidence)
    decoded = json.loads(summary)
    assert decoded == {
        "schema_version": runtime_oci_layers.OCI_LAYER_DIFF_IDS_EVIDENCE_SCHEMA,
        "plan_schema_version": evidence.plan.schema_version,
        "runtime_identity_schema_version": evidence.runtime_identity.schema_version,
        "runtime_identity_sha256": evidence.runtime_identity.sha256,
        **{flag: True for flag in true_flags},
        **{flag: False for flag in false_flags},
    }
    rendered = repr(evidence) + summary.decode("ascii")
    private_values = (
        str(root),
        *(blob.path for blob in evidence.plan.layer_blobs),
        *(blob.digest for blob in evidence.plan.layer_blobs),
        *evidence.plan.declared_diff_ids,
    )
    assert all(value not in rendered for value in private_values)
    for field in fields(evidence):
        if field.name.startswith("_"):
            continue
        with pytest.raises(FrozenInstanceError):
            setattr(evidence, field.name, getattr(evidence, field.name))
        with pytest.raises((TypeError, ValueError), match="factory|seal|token|valid"):
            replace(evidence, **{field.name: getattr(evidence, field.name)})
    corrupt = object.__new__(type(evidence))
    for field in fields(evidence):
        value = getattr(evidence, field.name)
        if field.name == "receipts":
            value = tuple(reversed(value))
        object.__setattr__(corrupt, field.name, value)
    with pytest.raises((TypeError, ValueError), match="receipt|order|evidence|valid") as captured:
        runtime_oci_layers.canonical_laya_runtime_oci_layer_diff_ids_summary_bytes(corrupt)
    _private_error(captured.value, str(root), *evidence.plan.declared_diff_ids)
    assert _tree_fingerprint(root) == before


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get(REAL_LAYOUT_RELEASE_GATE_ENV),
    reason="requires opt-in real external OCI layout on Linux",
)
def test_opt_in_same_root_tar_capture_verifies_ten_layers_in_order(monkeypatch):
    from human_feedback import runtime_oci_tar
    from human_feedback.runtime_oci_config import validate_laya_runtime_oci_config_semantics

    assert "PYTEST_XDIST_WORKER" not in os.environ, "external OCI gate must run serially"
    root = Path(os.environ[REAL_LAYOUT_RELEASE_GATE_ENV])
    before = _tree_fingerprint(root)
    layout_evidence = _capture(root)
    config_blob = layout_evidence.plan.blobs[1]
    config_payload = (root / config_blob.path).read_bytes()
    config_evidence = validate_laya_runtime_oci_config_semantics(
        layout_evidence,
        config_payload,
    )
    layer_evidence = _adapter().capture_and_verify_laya_oci_layer_diff_ids(
        config_evidence,
        root,
    )
    calls = []
    budgets = []
    original = runtime_oci_tar._verify_laya_oci_tar_semantics_chunks_with_budget

    def tar_spy(plan, digest, chunks, *, max_uncompressed_bytes):
        calls.append(digest)
        budgets.append(max_uncompressed_bytes)
        return original(
            plan,
            digest,
            chunks,
            max_uncompressed_bytes=max_uncompressed_bytes,
        )

    monkeypatch.setattr(
        runtime_oci_tar,
        "_verify_laya_oci_tar_semantics_chunks_with_budget",
        tar_spy,
    )
    evidence = _adapter().capture_and_verify_laya_oci_tar_semantics(layer_evidence, root)

    assert type(evidence) is runtime_oci_tar.LayaRuntimeOciTarSemanticsEvidence
    assert evidence.plan.layer_evidence is layer_evidence
    assert evidence.runtime_identity is layer_evidence.runtime_identity
    assert type(evidence.receipts) is tuple and len(evidence.receipts) == 10
    assert tuple(calls) == tuple(blob.digest for blob in layer_evidence.plan.layer_blobs)
    remaining = runtime_oci_tar.runtime_oci_layers.MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES
    expected_budgets = []
    for receipt in evidence.receipts:
        expected_budgets.append(
            min(
                runtime_oci_tar.runtime_oci_layers.MAX_OCI_LAYER_UNCOMPRESSED_BYTES,
                remaining,
            )
        )
        remaining -= receipt.layer_receipt.uncompressed_size_bytes
    assert budgets == expected_budgets
    assert all(later <= earlier for earlier, later in zip(budgets, budgets[1:]))
    assert all(
        receipt.plan is evidence.plan
        and receipt.layer_position == position
        and receipt.layer_receipt.layer_blob is layer_evidence.plan.layer_blobs[position]
        and receipt.tar_semantics_verified is True
        for position, receipt in enumerate(evidence.receipts)
    )
    assert evidence.tar_semantics_verified is True
    assert evidence.oci_rootfs_verified is False
    runtime_oci_tar.canonical_laya_runtime_oci_tar_semantics_summary_bytes(evidence)
    assert _tree_fingerprint(root) == before
