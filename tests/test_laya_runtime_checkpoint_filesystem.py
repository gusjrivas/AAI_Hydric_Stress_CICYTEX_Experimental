import ast
import os
import shutil
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_laya_runtime_deployment_metadata import _validate

IS_LINUX = sys.platform.startswith("linux")
ADAPTER_PATH = Path("src/human_feedback/adapters/filesystem_checkpoint.py")
CORE_PATH = Path("src/human_feedback/runtime_checkpoint.py")


def _adapter():
    import human_feedback.adapters.filesystem_checkpoint as adapter

    return adapter


def _core():
    import human_feedback.runtime_checkpoint as checkpoint

    return checkpoint


def _sparse_checkpoint(root: Path):
    plan = _core().prepare_laya_runtime_checkpoint_plan(_validate())
    for descriptor in plan.files:
        target = root / descriptor.path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as stream:
            stream.truncate(descriptor.size_bytes)
    return plan


def _private_error(exc: BaseException, *markers: str) -> None:
    rendered = "\n".join((str(exc), repr(exc), repr(exc.__cause__), repr(exc.__context__)))
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    assert all(marker not in rendered for marker in markers)


def test_adapter_surface_is_one_facade_two_errors_and_stdlib_plus_checkpoint_core():
    adapter = _adapter()
    source = Path(adapter.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    public_classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    assert public_functions == {"capture_and_verify_laya_runtime_checkpoint"}
    assert public_classes == {
        "CheckpointCaptureError",
        "SecureCheckpointCaptureUnavailableError",
    }
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    allowed = {
        "__future__",
        "errno",
        "os",
        "stat",
        "sys",
        "typing",
        "human_feedback.runtime_checkpoint",
    }
    assert all(name in allowed for name in imports)


def test_only_adapter_calls_private_checkpoint_authority_and_sealer():
    product_roots = (Path("src"), Path("backend"), Path("scripts"))
    private_names = {
        "_seal_laya_checkpoint_capture_authority",
        "_seal_laya_runtime_checkpoint_evidence",
    }
    offenders: list[str] = []
    for root in product_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            relative = path.as_posix()
            if relative in {ADAPTER_PATH.as_posix(), CORE_PATH.as_posix()}:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if any(
                isinstance(node, ast.Name)
                and node.id in private_names
                or isinstance(node, ast.Attribute)
                and node.attr in private_names
                or isinstance(node, ast.Constant)
                and node.value in private_names
                for node in ast.walk(tree)
            ):
                offenders.append(relative)
    assert offenders == []


def test_invalid_evidence_and_root_fail_before_open(monkeypatch):
    adapter = _adapter()
    opened = 0

    def forbidden_open(*args, **kwargs):
        nonlocal opened
        opened += 1
        raise AssertionError("must not open")

    monkeypatch.setattr(os, "open", forbidden_open)
    for evidence in (None, SimpleNamespace(), object()):
        with pytest.raises((TypeError, ValueError)):
            adapter.capture_and_verify_laya_runtime_checkpoint(evidence, object())
    assert opened == 0


def test_windows_fails_closed_before_root_coercion_or_open(monkeypatch):
    if IS_LINUX:
        pytest.skip("Windows capability contract")
    adapter = _adapter()
    monkeypatch.setattr(os, "open", lambda *args, **kwargs: pytest.fail("opened"))

    class Root:
        def __fspath__(self):
            pytest.fail("coerced root")

    with pytest.raises(adapter.SecureCheckpointCaptureUnavailableError):
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), Root())


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
@pytest.mark.parametrize("suffix", ["/", "//child", "/./child", "/../child"])
def test_noncanonical_root_fails_before_open(monkeypatch, tmp_path, suffix):
    adapter = _adapter()
    root = str(tmp_path) + suffix
    monkeypatch.setattr(os, "open", lambda *args, **kwargs: pytest.fail("opened"))
    with pytest.raises(adapter.CheckpointCaptureError):
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), root)


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
def test_filesystem_root_is_rejected_before_any_open(monkeypatch):
    adapter = _adapter()
    opened: list[object] = []
    monkeypatch.setattr(adapter, "_secure_capture_available", lambda: True)

    def forbidden_open(*args, **kwargs):
        opened.append(args[0] if args else None)
        raise AssertionError("filesystem root must be rejected before open")

    monkeypatch.setattr(adapter.os, "open", forbidden_open)

    with pytest.raises(adapter.CheckpointCaptureError):
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), "/")

    assert opened == []


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
def test_exact_inventory_is_checked_before_any_file_verification(monkeypatch, tmp_path):
    adapter = _adapter()
    plan = _sparse_checkpoint(tmp_path)
    verified: list[str] = []
    sealed: list[str] = []
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "verify_laya_checkpoint_file_chunks",
        lambda *args, **kwargs: verified.append("verified"),
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_checkpoint_capture_authority",
        lambda *args, **kwargs: sealed.append("authority"),
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_runtime_checkpoint_evidence",
        lambda *args, **kwargs: sealed.append("evidence"),
    )
    extra = tmp_path / "private-extra-file"
    extra.write_bytes(b"private-extra-content")
    with pytest.raises(adapter.CheckpointCaptureError) as caught:
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), tmp_path)
    _private_error(caught.value, str(tmp_path), extra.name, "private-extra-content")
    assert verified == []
    assert sealed == []
    assert len(plan.files) == 5


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
def test_unexpected_directory_fails_at_adjacent_entry_without_recursive_descent(
    monkeypatch,
    tmp_path,
):
    adapter = _adapter()
    root = tmp_path / "multilingual"
    _sparse_checkpoint(root)
    monkeypatch.setattr(adapter, "_secure_capture_available", lambda: True)
    unexpected = root / "unexpected"
    unexpected.mkdir()
    cursor = unexpected
    for level in range(16):
        cursor = cursor / f"private-{level}"
        cursor.mkdir()

    original_open = adapter.os.open
    original_scandir = adapter.os.scandir
    unexpected_opens: list[str] = []
    scandir_calls = 0

    def tracked_open(path, flags, *args, **kwargs):
        if path == unexpected.name:
            unexpected_opens.append(path)
        return original_open(path, flags, *args, **kwargs)

    def tracked_scandir(path):
        nonlocal scandir_calls
        scandir_calls += 1
        return original_scandir(path)

    monkeypatch.setattr(adapter.os, "open", tracked_open)
    monkeypatch.setattr(adapter.os, "scandir", tracked_scandir)
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "verify_laya_checkpoint_file_chunks",
        lambda *args, **kwargs: pytest.fail("verification must not start"),
    )

    with pytest.raises(adapter.CheckpointCaptureError):
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), root)

    # Root plus the two declared one-level manifest directories is the hard bound.
    assert scandir_calls <= 3
    assert unexpected_opens == []


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
@pytest.mark.parametrize("kind", ["missing", "symlink", "hardlink", "fifo"])
def test_each_checkpoint_file_must_be_regular_single_link_and_exact(monkeypatch, tmp_path, kind):
    adapter = _adapter()
    plan = _sparse_checkpoint(tmp_path)
    target = tmp_path / plan.files[-1].path
    if kind == "missing":
        target.unlink()
    elif kind == "symlink":
        target.unlink()
        target.symlink_to(tmp_path / plan.files[0].path)
    elif kind == "hardlink":
        alias = target.with_name("alias")
        os.link(target, alias)
    else:
        target.unlink()
        os.mkfifo(target)
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "verify_laya_checkpoint_file_chunks",
        lambda *args, **kwargs: pytest.fail("verification must not start"),
    )
    with pytest.raises(adapter.CheckpointCaptureError):
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), tmp_path)


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
def test_verifier_failure_after_same_size_replacement_never_seals(monkeypatch, tmp_path):
    adapter = _adapter()
    plan = _sparse_checkpoint(tmp_path)
    calls = 0
    sealed: list[str] = []

    def mutate_after_verify(plan_arg, digest, chunks):
        nonlocal calls
        calls += 1
        descriptor = next(item for item in plan.files if item.sha256 == digest)
        for _ in chunks:
            pass
        target = tmp_path / descriptor.path
        replacement = target.with_name(target.name + ".replacement")
        with replacement.open("wb") as stream:
            stream.truncate(descriptor.size_bytes)
        os.replace(replacement, target)
        raise ValueError("private-verification-stop")

    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "verify_laya_checkpoint_file_chunks",
        mutate_after_verify,
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_checkpoint_capture_authority",
        lambda *args, **kwargs: sealed.append("authority"),
    )
    with pytest.raises(adapter.CheckpointCaptureError) as caught:
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), tmp_path)
    _private_error(caught.value, str(tmp_path), "private-verification-stop")
    assert calls == 1
    assert sealed == []


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
def test_late_checkpoint_root_path_replacement_is_detected_beyond_retained_root_fd(
    monkeypatch,
    tmp_path,
):
    adapter = _adapter()
    ancestor = tmp_path / "checkpoint-parent"
    root = ancestor / "multilingual"
    _sparse_checkpoint(root)
    monkeypatch.setattr(adapter, "_secure_capture_available", lambda: True)
    displaced = tmp_path / "checkpoint-parent-displaced"
    replaced = False
    sealed: list[str] = []

    def replace_root_after_first_receipt(plan, digest, chunks):
        nonlocal replaced
        del plan, chunks
        if not replaced:
            os.rename(ancestor, displaced)
            root.mkdir(parents=True)
            replaced = True
        return digest

    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "verify_laya_checkpoint_file_chunks",
        replace_root_after_first_receipt,
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_checkpoint_capture_authority",
        lambda *args, **kwargs: sealed.append("authority"),
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_runtime_checkpoint_evidence",
        lambda *args, **kwargs: sealed.append("evidence"),
    )

    with pytest.raises(adapter.CheckpointCaptureError):
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), root)

    assert replaced is True
    assert sealed == []


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
@pytest.mark.parametrize("operation", ["open", "scandir", "stat", "fstat", "read"])
def test_each_filesystem_failure_prevents_checkpoint_sealing(monkeypatch, tmp_path, operation):
    adapter = _adapter()
    root = tmp_path / "multilingual"
    _sparse_checkpoint(root)
    monkeypatch.setattr(adapter, "_secure_capture_available", lambda: True)
    sealed: list[str] = []

    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_checkpoint_capture_authority",
        lambda *args, **kwargs: sealed.append("authority"),
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_runtime_checkpoint_evidence",
        lambda *args, **kwargs: sealed.append("evidence"),
    )

    if operation == "open":
        monkeypatch.setattr(
            adapter.os,
            "open",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected open")),
        )
    elif operation == "scandir":
        monkeypatch.setattr(
            adapter.os,
            "scandir",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected scandir")),
        )
    elif operation == "stat":
        original_scandir = adapter.os.scandir

        class EntryWithFailingStat:
            def __init__(self, entry):
                self._entry = entry
                self.name = entry.name

            def stat(self, *, follow_symlinks=True):
                del follow_symlinks
                raise OSError("injected stat")

        class ScandirWithFailingStat:
            def __init__(self, delegate):
                self._delegate = delegate

            def __enter__(self):
                entries = list(self._delegate.__enter__())
                return iter([EntryWithFailingStat(entries[0]), *entries[1:]])

            def __exit__(self, *args):
                return self._delegate.__exit__(*args)

        monkeypatch.setattr(
            adapter.os,
            "scandir",
            lambda path: ScandirWithFailingStat(original_scandir(path)),
        )
    elif operation == "fstat":
        monkeypatch.setattr(
            adapter.os,
            "fstat",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected fstat")),
        )
    else:
        monkeypatch.setattr(
            adapter.os,
            "read",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected read")),
        )

    def verifier(plan, digest, chunks):
        del plan
        if operation == "read":
            next(iter(chunks))
        return digest

    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "verify_laya_checkpoint_file_chunks",
        verifier,
    )

    with pytest.raises(adapter.CheckpointCaptureError):
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), root)

    assert sealed == []


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
def test_last_root_close_failure_after_receipts_and_sweep_never_seals(monkeypatch, tmp_path):
    adapter = _adapter()
    root = tmp_path / "multilingual"
    _sparse_checkpoint(root)
    monkeypatch.setattr(adapter, "_secure_capture_available", lambda: True)
    original_open_root = adapter._open_root
    original_validate_inventory = adapter._validate_inventory
    original_close = adapter.os.close
    root_descriptor: list[int] = []
    sweep_count = 0
    after_final_sweep = False
    close_injected = False
    sealed: list[str] = []

    def tracked_open_root(value):
        descriptor = original_open_root(value)
        root_descriptor.append(descriptor)
        return descriptor

    def tracked_validate_inventory(root_fd, plan):
        nonlocal sweep_count, after_final_sweep
        result = original_validate_inventory(root_fd, plan)
        sweep_count += 1
        if sweep_count == 2:
            after_final_sweep = True
        return result

    def fail_last_root_close(descriptor):
        nonlocal close_injected
        original_close(descriptor)
        if (
            root_descriptor
            and descriptor == root_descriptor[0]
            and after_final_sweep
            and not close_injected
        ):
            close_injected = True
            raise OSError("injected final root close")

    monkeypatch.setattr(adapter, "_open_root", tracked_open_root)
    monkeypatch.setattr(adapter, "_validate_inventory", tracked_validate_inventory)
    monkeypatch.setattr(adapter.os, "close", fail_last_root_close)
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "verify_laya_checkpoint_file_chunks",
        lambda plan, digest, chunks: digest,
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_checkpoint_capture_authority",
        lambda *args, **kwargs: sealed.append("authority"),
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_runtime_checkpoint_evidence",
        lambda *args, **kwargs: sealed.append("evidence"),
    )

    with pytest.raises(adapter.CheckpointCaptureError):
        adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), root)

    assert sweep_count == 2
    assert close_injected is True
    assert sealed == []


@pytest.mark.skipif(not IS_LINUX, reason="secure descriptor capture is Linux-only")
def test_multilingual_manifest_root_success_closes_every_descriptor_before_sealing(
    monkeypatch,
    tmp_path,
):
    adapter = _adapter()
    root = tmp_path / "multilingual"
    plan = _sparse_checkpoint(root)
    monkeypatch.setattr(adapter, "_secure_capture_available", lambda: True)
    original_open = adapter.os.open
    original_dup = adapter.os.dup
    original_close = adapter.os.close
    live: dict[int, int] = {}
    events: list[str] = []
    evidence = object()

    def track(descriptor):
        live[descriptor] = live.get(descriptor, 0) + 1
        return descriptor

    def tracked_open(*args, **kwargs):
        return track(original_open(*args, **kwargs))

    def tracked_dup(*args, **kwargs):
        return track(original_dup(*args, **kwargs))

    def tracked_close(descriptor):
        if live.get(descriptor, 0):
            live[descriptor] -= 1
            events.append("close")
        return original_close(descriptor)

    def seal_authority(plan_arg, receipts):
        assert tuple(item.path for item in plan_arg.files) == tuple(
            item.path for item in plan.files
        )
        assert len(receipts) == len(plan.files)
        assert all(count == 0 for count in live.values())
        events.append("authority")
        return receipts

    def seal_evidence(authority):
        assert len(authority) == len(plan.files)
        assert all(count == 0 for count in live.values())
        events.append("evidence")
        return evidence

    monkeypatch.setattr(adapter.os, "open", tracked_open)
    monkeypatch.setattr(adapter.os, "dup", tracked_dup)
    monkeypatch.setattr(adapter.os, "close", tracked_close)
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "verify_laya_checkpoint_file_chunks",
        lambda plan_arg, digest, chunks: digest,
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_checkpoint_capture_authority",
        seal_authority,
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_runtime_checkpoint_evidence",
        seal_evidence,
    )

    result = adapter.capture_and_verify_laya_runtime_checkpoint(_validate(), root)

    assert result is evidence
    assert events[-2:] == ["authority", "evidence"]
    assert {item.name for item in root.iterdir()} == {
        "encoder",
        "model.safetensors",
        "rl_agent_config.json",
        "tokenizer",
    }


@pytest.mark.skipif(
    not IS_LINUX or not os.environ.get("LAYA_RUNTIME_CHECKPOINT_ROOT"),
    reason="real checkpoint TOCTOU is an explicit Linux release gate",
)
def test_opt_in_same_size_toctou_after_valid_receipt_is_rejected(monkeypatch, tmp_path):
    adapter = _adapter()
    deployment = _validate()
    source = Path(os.environ["LAYA_RUNTIME_CHECKPOINT_ROOT"])
    root = tmp_path / "checkpoint"
    root.mkdir()
    plan = _core().prepare_laya_runtime_checkpoint_plan(deployment)
    for descriptor in plan.files:
        source_file = source / descriptor.path
        target = root / descriptor.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target)
    original = adapter.runtime_checkpoint.verify_laya_checkpoint_file_chunks
    calls = 0
    sealed: list[str] = []

    def mutate_after_valid_receipt(plan_arg, digest, chunks):
        nonlocal calls
        receipt = original(plan_arg, digest, chunks)
        calls += 1
        if calls == 1:
            descriptor = next(item for item in plan.files if item.sha256 == digest)
            target = root / descriptor.path
            replacement = target.with_name(target.name + ".replacement")
            shutil.copyfile(target, replacement)
            os.replace(replacement, target)
        return receipt

    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "verify_laya_checkpoint_file_chunks",
        mutate_after_valid_receipt,
    )
    monkeypatch.setattr(
        adapter.runtime_checkpoint,
        "_seal_laya_checkpoint_capture_authority",
        lambda *args, **kwargs: sealed.append("authority"),
    )
    with pytest.raises(adapter.CheckpointCaptureError):
        adapter.capture_and_verify_laya_runtime_checkpoint(deployment, root)
    assert calls == 1
    assert sealed == []


def test_adapter_source_requires_final_fingerprint_sweep_and_close_before_seal():
    adapter = _adapter()
    source = Path(adapter.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert {"fstat", "stat", "scandir", "close"} <= names
    capture = source[source.index("def capture_and_verify_laya_runtime_checkpoint") :]
    assert capture.rfind("close") < capture.rfind("_seal_laya_checkpoint_capture_authority")
    assert capture.rfind("_seal_laya_checkpoint_capture_authority") < capture.rfind(
        "_seal_laya_runtime_checkpoint_evidence"
    )


def test_sparse_helper_declares_exact_total_without_allocating_payload(tmp_path):
    if not IS_LINUX:
        pytest.skip("sparse file accounting is platform-specific")
    plan = _sparse_checkpoint(tmp_path)
    assert sum(item.size_bytes for item in plan.files) == 678_201_636
    for item in plan.files:
        info = os.stat(tmp_path / item.path, follow_symlinks=False)
        assert stat.S_ISREG(info.st_mode)
        assert info.st_size == item.size_bytes
