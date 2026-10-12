import ast
import hashlib
import importlib
import os
import socket
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_laya_runtime_artifact_integrity import ARTIFACT_PATHS, _manifest, _payloads

IS_LINUX = sys.platform.startswith("linux")


def _filesystem_adapter():
    return importlib.import_module("human_feedback.adapters.filesystem_runtime_bundle")


def _materialize(root: Path, payloads: dict[str, bytes], *, omit: str | None = None) -> None:
    for relative_path, content in payloads.items():
        if relative_path == omit:
            continue
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _capture(manifest, root: Path):
    module = _filesystem_adapter()
    return module.capture_and_verify_laya_runtime_artifacts(manifest, root)


def _assert_private_details_hidden(error: BaseException, root: Path, payloads) -> None:
    rendered = str(error)
    assert str(root.absolute()) not in rendered
    for content in payloads.values():
        assert content.decode("ascii") not in rendered


def _forbid_partial_verification(monkeypatch, module) -> dict[str, bool]:
    state = {"called": False}

    def forbidden_verification(*args, **kwargs):
        state["called"] = True
        raise AssertionError("portable verifier received an unstable or partial capture")

    monkeypatch.setattr(module, "verify_laya_runtime_artifact_bytes", forbidden_verification)
    return state


def _fds_pointing_into(root: Path) -> dict[int, str]:
    root_text = str(root.absolute())
    result = {}
    for entry in Path("/proc/self/fd").iterdir():
        try:
            target = os.readlink(entry)
            file_descriptor = int(entry.name)
        except (OSError, ValueError):
            continue
        if target == root_text or target.startswith(root_text + os.sep):
            result[file_descriptor] = target
    return result


def _close_fds(file_descriptors, close) -> None:
    for file_descriptor in file_descriptors:
        try:
            close(file_descriptor)
        except OSError:
            pass


def test_missing_secure_capture_capability_fails_before_any_os_open(monkeypatch, tmp_path):
    module = _filesystem_adapter()
    payloads = _payloads()
    manifest = _manifest(payloads=payloads)
    opened = False

    monkeypatch.setattr(module, "_secure_runtime_capture_available", lambda: False)

    def forbidden_open(*args, **kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("os.open must not run without secure capture capability")

    monkeypatch.setattr(module.os, "open", forbidden_open)

    with pytest.raises(module.SecureRuntimeCaptureUnavailableError) as error:
        module.capture_and_verify_laya_runtime_artifacts(manifest, tmp_path / "private-root")

    assert opened is False
    _assert_private_details_hidden(error.value, tmp_path / "private-root", payloads)


@pytest.mark.skipif(os.name != "nt", reason="Windows must fail closed without dir-fd capture")
def test_windows_real_capture_fails_closed(tmp_path):
    module = _filesystem_adapter()
    payloads = _payloads()
    root = tmp_path / "private-runtime-root"
    _materialize(root, payloads)

    with pytest.raises(module.SecureRuntimeCaptureUnavailableError) as error:
        module.capture_and_verify_laya_runtime_artifacts(_manifest(payloads=payloads), root)

    _assert_private_details_hidden(error.value, root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="root lexical validation is a Linux boundary")
@pytest.mark.parametrize(
    "root_variant",
    ["internal-double-slash", "double-leading-slash", "trailing-slash"],
)
def test_linux_noncanonical_root_is_rejected_before_any_open(monkeypatch, tmp_path, root_variant):
    module = _filesystem_adapter()
    manifest = _manifest()
    canonical = str(tmp_path / "runtime")
    if root_variant == "internal-double-slash":
        root = f"{tmp_path}//runtime"
    elif root_variant == "double-leading-slash":
        root = f"/{canonical}"
    else:
        root = canonical + "/"
    opened = False

    def forbidden_open(*args, **kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("noncanonical roots must fail before os.open")

    monkeypatch.setattr(module, "_secure_runtime_capture_available", lambda: True)
    monkeypatch.setattr(module.os, "open", forbidden_open)

    with pytest.raises(module.RuntimeArtifactCaptureError, match="root|canonical"):
        module.capture_and_verify_laya_runtime_artifacts(manifest, root)

    assert opened is False


@pytest.mark.skipif(not IS_LINUX, reason="root lexical validation is a Linux boundary")
def test_linux_slash_root_is_explicitly_canonical():
    module = _filesystem_adapter()

    assert module._root_components("/") == ()


@pytest.mark.skipif(not IS_LINUX, reason="secure dir-fd traversal is a Linux contract")
def test_linux_captures_exactly_the_five_manifest_artifacts(tmp_path):
    from human_feedback.runtime_bundle import LayaRuntimeBundleSnapshot

    payloads = _payloads()
    root = tmp_path / "runtime"
    manifest = _manifest(payloads=payloads)
    _materialize(root, payloads)

    snapshot = _capture(manifest, root)

    assert isinstance(snapshot, LayaRuntimeBundleSnapshot)
    assert snapshot.manifest is manifest
    assert snapshot.artifact_integrity_verified is True
    assert tuple(item.spec.kind for item in snapshot.artifacts) == tuple(ARTIFACT_PATHS)


@pytest.mark.skipif(not IS_LINUX, reason="secure dir-fd traversal is a Linux contract")
@pytest.mark.parametrize("missing_path", tuple(ARTIFACT_PATHS.values()))
def test_linux_missing_artifact_never_produces_a_partial_snapshot(
    monkeypatch, tmp_path, missing_path
):
    module = _filesystem_adapter()
    payloads = _payloads()
    root = tmp_path / "runtime"
    _materialize(root, payloads, omit=missing_path)
    verifier_called = False

    def forbidden_partial_verification(*args, **kwargs):
        nonlocal verifier_called
        verifier_called = True
        raise AssertionError("portable verifier received a partial capture")

    monkeypatch.setattr(
        module, "verify_laya_runtime_artifact_bytes", forbidden_partial_verification
    )
    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(_manifest(payloads=payloads), root)

    assert verifier_called is False
    _assert_private_details_hidden(error.value, root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="secure dir-fd traversal is a Linux contract")
@pytest.mark.parametrize("link_location", ["root", "intermediate", "final"])
def test_linux_rejects_symlink_at_every_traversal_level(tmp_path, link_location):
    module = _filesystem_adapter()
    payloads = _payloads()
    real_root = tmp_path / "real-runtime"
    outside = tmp_path / "outside"
    _materialize(real_root, payloads)
    outside.mkdir()

    if link_location == "root":
        root = tmp_path / "linked-runtime"
        root.symlink_to(real_root, target_is_directory=True)
    elif link_location == "intermediate":
        root = real_root
        sbom_path = root / "sbom" / "laya-runtime.cdx.json"
        sbom_path.unlink()
        (root / "sbom").rmdir()
        (outside / "laya-runtime.cdx.json").write_bytes(payloads[ARTIFACT_PATHS["sbom"]])
        (root / "sbom").symlink_to(outside, target_is_directory=True)
    else:
        root = real_root
        target = root / ARTIFACT_PATHS["runtime_config"]
        target.unlink()
        outside_file = outside / "runtime.json"
        outside_file.write_bytes(payloads[ARTIFACT_PATHS["runtime_config"]])
        target.symlink_to(outside_file)

    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(_manifest(payloads=payloads), root)

    _assert_private_details_hidden(error.value, root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="secure dir-fd traversal is a Linux contract")
@pytest.mark.parametrize("invalid_type", ["root-file", "target-directory", "fifo", "socket"])
def test_linux_rejects_non_regular_roots_and_targets_without_blocking(tmp_path, invalid_type):
    module = _filesystem_adapter()
    payloads = _payloads()
    root = tmp_path / "runtime"
    manifest = _manifest(payloads=payloads)
    fifo_keeper = None

    if invalid_type == "root-file":
        root.write_bytes(b"not-a-directory")
    else:
        _materialize(root, payloads)
        target = root / ARTIFACT_PATHS["checkpoint_manifest"]
        target.unlink()
        if invalid_type == "target-directory":
            target.mkdir()
        elif invalid_type == "fifo":
            os.mkfifo(target)
            fifo_keeper = os.open(target, os.O_RDWR | os.O_NONBLOCK)
        else:
            unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            unix_socket.bind(str(target))

    try:
        with pytest.raises(module.RuntimeArtifactCaptureError) as error:
            module.capture_and_verify_laya_runtime_artifacts(manifest, root)
    finally:
        if fifo_keeper is not None:
            os.close(fifo_keeper)
        if invalid_type == "socket":
            unix_socket.close()

    _assert_private_details_hidden(error.value, root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="secure dir-fd traversal is a Linux contract")
def test_linux_oversize_artifact_read_is_bounded_to_expected_size_plus_one(monkeypatch, tmp_path):
    module = _filesystem_adapter()
    payloads = _payloads()
    root = tmp_path / "runtime"
    manifest = _manifest(payloads=payloads)
    path = ARTIFACT_PATHS["dependency_lock"]
    payloads[path] += b"private-growth-that-must-not-be-read"
    _materialize(root, payloads)
    declared_size = next(
        item.size_bytes for item in manifest.artifacts if item.kind == "dependency_lock"
    )
    original_read = module.os.read
    captured_bytes = 0

    def bounded_read(file_descriptor, count):
        nonlocal captured_bytes
        chunk = original_read(file_descriptor, count)
        captured_bytes += len(chunk)
        return chunk

    monkeypatch.setattr(module.os, "read", bounded_read)

    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(manifest, root)

    assert captured_bytes <= declared_size + 1
    _assert_private_details_hidden(error.value, root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="TOCTOU descriptor checks require Linux")
def test_linux_same_size_in_place_mutation_after_initial_fstat_is_rejected(monkeypatch, tmp_path):
    module = _filesystem_adapter()
    payloads = _payloads()
    manifest = _manifest(payloads=payloads)
    root = tmp_path / "runtime"
    _materialize(root, payloads)
    target = root / ARTIFACT_PATHS["dependency_lock"]
    replacement = b"x" * len(payloads[ARTIFACT_PATHS["dependency_lock"]])
    original_mtime_ns = target.stat().st_mtime_ns
    original_read = module.os.read
    mutated = False
    verifier = _forbid_partial_verification(monkeypatch, module)

    def mutate_then_read(file_descriptor, count):
        nonlocal mutated
        if not mutated:
            target.write_bytes(replacement)
            os.utime(
                target,
                ns=(original_mtime_ns + 1_000_000_000, original_mtime_ns + 1_000_000_000),
            )
            mutated = True
        return original_read(file_descriptor, count)

    monkeypatch.setattr(module.os, "read", mutate_then_read)

    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(manifest, root)

    assert mutated is True
    assert verifier["called"] is False
    _assert_private_details_hidden(
        error.value,
        root,
        {**payloads, "private/replacement": replacement},
    )


@pytest.mark.skipif(not IS_LINUX, reason="TOCTOU descriptor checks require Linux")
def test_linux_growth_during_first_read_is_bounded_and_rejected(monkeypatch, tmp_path):
    module = _filesystem_adapter()
    payloads = _payloads()
    manifest = _manifest(payloads=payloads)
    root = tmp_path / "runtime"
    _materialize(root, payloads)
    path = ARTIFACT_PATHS["dependency_lock"]
    target = root / path
    expected_size = len(payloads[path])
    original_read = module.os.read
    captured_bytes = 0
    grown = False
    verifier = _forbid_partial_verification(monkeypatch, module)

    def grow_then_read(file_descriptor, count):
        nonlocal captured_bytes, grown
        if not grown:
            with target.open("ab") as stream:
                stream.write(b"private-growth")
            grown = True
        chunk = original_read(file_descriptor, count)
        captured_bytes += len(chunk)
        return chunk

    monkeypatch.setattr(module.os, "read", grow_then_read)

    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(manifest, root)

    assert grown is True
    assert captured_bytes <= expected_size + 1
    assert verifier["called"] is False
    _assert_private_details_hidden(error.value, root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="TOCTOU descriptor checks require Linux")
def test_linux_final_sweep_rejects_file_replaced_after_capture(monkeypatch, tmp_path):
    module = _filesystem_adapter()
    payloads = _payloads()
    manifest = _manifest(payloads=payloads)
    root = tmp_path / "runtime"
    _materialize(root, payloads)
    path = ARTIFACT_PATHS["dependency_lock"]
    target = root / path
    original_capture_one = module._capture_one
    replaced = False
    verifier = _forbid_partial_verification(monkeypatch, module)

    def capture_then_replace(root_fd, spec):
        nonlocal replaced
        content = original_capture_one(root_fd, spec)
        if not replaced:
            target.rename(target.with_name("private-original.lock"))
            target.write_bytes(content)
            replaced = True
        return content

    monkeypatch.setattr(module, "_capture_one", capture_then_replace)

    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(manifest, root)

    assert replaced is True
    assert verifier["called"] is False
    _assert_private_details_hidden(error.value, root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="TOCTOU descriptor checks require Linux")
def test_linux_final_sweep_rejects_intermediate_directory_replaced_after_capture(
    monkeypatch, tmp_path
):
    module = _filesystem_adapter()
    payloads = _payloads()
    manifest = _manifest(payloads=payloads)
    root = tmp_path / "runtime"
    _materialize(root, payloads)
    directory = root / "locks"
    original_capture_one = module._capture_one
    replaced = False
    verifier = _forbid_partial_verification(monkeypatch, module)

    def capture_then_replace(root_fd, spec):
        nonlocal replaced
        content = original_capture_one(root_fd, spec)
        if not replaced:
            directory.rename(root / "private-original-locks")
            directory.mkdir()
            (directory / "uv.lock").write_bytes(content)
            replaced = True
        return content

    monkeypatch.setattr(module, "_capture_one", capture_then_replace)

    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(manifest, root)

    assert replaced is True
    assert verifier["called"] is False
    _assert_private_details_hidden(error.value, root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="secure root traversal requires Linux")
def test_linux_rejects_symlink_in_ancestor_of_runtime_root(monkeypatch, tmp_path):
    module = _filesystem_adapter()
    payloads = _payloads()
    manifest = _manifest(payloads=payloads)
    real_parent = tmp_path / "private-real-parent"
    real_root = real_parent / "runtime"
    linked_parent = tmp_path / "linked-parent"
    _materialize(real_root, payloads)
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    linked_root = linked_parent / "runtime"
    verifier = _forbid_partial_verification(monkeypatch, module)

    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(manifest, linked_root)

    assert verifier["called"] is False
    _assert_private_details_hidden(error.value, linked_root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="descriptor leak inspection requires /proc on Linux")
def test_linux_close_failure_during_root_traversal_leaks_no_descriptors(monkeypatch, tmp_path):
    module = _filesystem_adapter()
    payloads = _payloads()
    manifest = _manifest(payloads=payloads)
    root = tmp_path / "runtime"
    _materialize(root, payloads)
    original_close = module.os.close
    raised = False
    verifier = _forbid_partial_verification(monkeypatch, module)

    def close_then_raise_once(file_descriptor):
        nonlocal raised
        try:
            target = os.readlink(f"/proc/self/fd/{file_descriptor}")
        except OSError:
            target = ""
        original_close(file_descriptor)
        if not raised and target == str(tmp_path.absolute()):
            raised = True
            raise OSError("injected private root traversal close failure")

    monkeypatch.setattr(module.os, "close", close_then_raise_once)

    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(manifest, root)

    leaked = _fds_pointing_into(tmp_path)
    _close_fds(leaked, original_close)
    assert raised is True
    assert verifier["called"] is False
    assert leaked == {}
    _assert_private_details_hidden(error.value, root, payloads)


@pytest.mark.skipif(not IS_LINUX, reason="descriptor leak inspection requires /proc on Linux")
def test_linux_close_failure_for_final_file_leaks_no_descriptors(monkeypatch, tmp_path):
    module = _filesystem_adapter()
    payloads = _payloads()
    manifest = _manifest(payloads=payloads)
    root = tmp_path / "runtime"
    _materialize(root, payloads)
    target_path = str((root / ARTIFACT_PATHS["dependency_lock"]).absolute())
    original_close = module.os.close
    raised = False
    verifier = _forbid_partial_verification(monkeypatch, module)

    def close_then_raise_once(file_descriptor):
        nonlocal raised
        try:
            target = os.readlink(f"/proc/self/fd/{file_descriptor}")
        except OSError:
            target = ""
        original_close(file_descriptor)
        if not raised and target == target_path:
            raised = True
            raise OSError("injected private final file close failure")

    monkeypatch.setattr(module.os, "close", close_then_raise_once)

    with pytest.raises(module.RuntimeArtifactCaptureError) as error:
        module.capture_and_verify_laya_runtime_artifacts(manifest, root)

    leaked = _fds_pointing_into(tmp_path)
    _close_fds(leaked, original_close)
    assert raised is True
    assert verifier["called"] is False
    assert leaked == {}
    _assert_private_details_hidden(error.value, root, payloads)


def test_manifest_over_total_bundle_limit_fails_before_open(monkeypatch, tmp_path):
    module = _filesystem_adapter()
    manifest = _manifest()
    first = manifest.artifacts[0]
    oversized = replace(
        first,
        size_bytes=module.MAX_RUNTIME_BUNDLE_BYTES,
        sha256=hashlib.sha256(b"declared-only").hexdigest(),
    )
    oversized_manifest = replace(
        manifest,
        artifacts=(oversized, *manifest.artifacts[1:]),
    )
    opened = False

    def forbidden_open(*args, **kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("oversized manifest must fail before os.open")

    monkeypatch.setattr(module.os, "open", forbidden_open)

    with pytest.raises(module.RuntimeArtifactCaptureError):
        module.capture_and_verify_laya_runtime_artifacts(oversized_manifest, tmp_path)

    assert opened is False


def test_filesystem_adapter_uses_secure_relative_descriptor_traversal_only():
    module = _filesystem_adapter()
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    os_open_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "open"
    ]
    opens_without_dir_fd = [
        node
        for node in os_open_calls
        if not any(keyword.arg == "dir_fd" for keyword in node.keywords)
    ]

    forbidden = ("Path.resolve", ".resolve(", ".read_bytes(", "builtins.open")
    assert [token for token in forbidden if token in source] == []
    assert os_open_calls
    assert len(opens_without_dir_fd) <= 1  # only the trusted root may use an absolute path
    assert len(os_open_calls) > len(opens_without_dir_fd)
    assert "O_NONBLOCK" in source


def test_filesystem_adapter_depends_only_on_runtime_contracts_and_stdlib():
    module = _filesystem_adapter()
    source_path = Path(module.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    violations = []
    allowed_project_modules = {
        "human_feedback.runtime_bundle",
        "human_feedback.runtime_identity",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if name.startswith("human_feedback") and name not in allowed_project_modules:
                violations.append(name)
            elif name and name.split(".", 1)[0] not in sys.stdlib_module_names:
                violations.append(name)

    assert violations == []
