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
