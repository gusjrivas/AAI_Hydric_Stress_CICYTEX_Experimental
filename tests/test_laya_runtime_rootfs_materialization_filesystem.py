"""RED39-B: P0 fail-closed boundary for rootfs filesystem mutation."""

from __future__ import annotations

import importlib
import inspect
import os

import pytest


def _adapter():
    return importlib.import_module(
        "human_feedback.adapters.filesystem_rootfs_materialization"
    )


class _PathCoercionTrap:
    def __init__(self) -> None:
        self.coerced = False

    def __fspath__(self) -> str:
        self.coerced = True
        raise AssertionError("untrusted paths must not be coerced before authority")


def test_adapter_surface_is_narrow_and_requires_separate_source_and_destination_roots():
    module = _adapter()

    assert module.__all__ == (
        "RootfsMaterializationError",
        "SecureRootfsMaterializationUnavailableError",
        "materialize_laya_runtime_rootfs",
    )
    assert tuple(inspect.signature(module.materialize_laya_runtime_rootfs).parameters) == (
        "plan",
        "source_root",
        "destination_parent",
        "destination_name",
    )


def test_unsupported_or_privileged_host_fails_closed():
    module = _adapter()

    capability = module._secure_rootfs_materialization_available()
    assert type(capability) is bool
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() == 0:
        assert capability is False


def test_invalid_authority_fails_before_path_coercion_or_filesystem_mutation(tmp_path):
    module = _adapter()
    source = _PathCoercionTrap()
    parent = _PathCoercionTrap()
    before = tuple(tmp_path.iterdir())

    with pytest.raises(module.RootfsMaterializationError) as captured:
        module.materialize_laya_runtime_rootfs(
            object(),
            source,
            parent,
            "private-rootfs",
        )

    assert source.coerced is False
    assert parent.coerced is False
    assert tuple(tmp_path.iterdir()) == before
    assert "private-rootfs" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert captured.value.__suppress_context__ is True


def test_staging_contract_is_private_sibling_and_never_allows_existing_destination():
    module = _adapter()

    assert module.STAGING_MODE == 0o700
    assert module.DESTINATION_MUST_BE_ABSENT is True
    assert module.STAGING_IS_DESTINATION_SIBLING is True
    assert module.ATOMIC_NO_CLOBBER_REQUIRED is True

