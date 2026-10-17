"""RED39-B: P0 fail-closed boundary for rootfs filesystem mutation."""

from __future__ import annotations

import importlib
import inspect
import os
import stat
from types import SimpleNamespace

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


@pytest.mark.parametrize("value", ("/srv/laya-source", "/var/tmp/laya-parent"))
def test_absolute_root_preflight_accepts_only_canonical_nonroot_strings(value):
    module = _adapter()

    assert module._absolute_root_components(value, "test-root") == tuple(
        value.removeprefix("/").split("/")
    )


@pytest.mark.parametrize(
    "value",
    (
        object(),
        "",
        "/",
        "relative/root",
        "/srv/./root",
        "/srv/../root",
        "/srv//root",
        "//srv/root",
        "/srv/root/",
        "C:/srv/root",
        "/srv\\root",
    ),
)
def test_absolute_root_preflight_rejects_ambiguous_or_dangerous_values(value):
    module = _adapter()

    with pytest.raises(module.RootfsMaterializationError):
        module._absolute_root_components(value, "test-root")


@pytest.mark.parametrize("value", ("rootfs-01", "laya_rootfs.v1", "A1"))
def test_destination_name_is_one_conservative_component(value):
    module = _adapter()

    assert module._validate_destination_name(value) == value


@pytest.mark.parametrize(
    "value",
    (
        object(),
        "",
        ".",
        "..",
        "root/fs",
        "root\\fs",
        " rootfs",
        "rootfs ",
        "root fs",
        "rootfs\nsecret",
        "a" * 129,
    ),
)
def test_destination_name_rejects_traversal_separators_controls_and_whitespace(value):
    module = _adapter()

    with pytest.raises(module.RootfsMaterializationError):
        module._validate_destination_name(value)


@pytest.mark.parametrize(
    ("mode", "uid"),
    (
        (stat.S_IFREG | 0o600, 1000),
        (stat.S_IFLNK | 0o700, 1000),
        (stat.S_IFDIR | 0o720, 1000),
        (stat.S_IFDIR | 0o702, 1000),
        (stat.S_IFDIR | 0o777, 1000),
        (stat.S_IFDIR | 0o700, 999),
    ),
)
def test_scratch_parent_must_be_owned_directory_without_group_or_world_write(mode, uid):
    module = _adapter()
    parent_stat = SimpleNamespace(st_mode=mode, st_uid=uid)

    with pytest.raises(module.RootfsMaterializationError):
        module._validate_private_parent_stat(parent_stat, effective_uid=1000)


def test_scratch_parent_accepts_owned_non_writable_directory_metadata():
    module = _adapter()
    parent_stat = SimpleNamespace(st_mode=stat.S_IFDIR | 0o750, st_uid=1000)

    assert module._validate_private_parent_stat(parent_stat, effective_uid=1000) is None


def test_existing_destination_is_rejected_by_injected_lookup_before_mutation(monkeypatch):
    module = _adapter()
    observed = []

    def existing_lookup(name, *, dir_fd, follow_symlinks):
        observed.append((name, dir_fd, follow_symlinks))
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=1000)

    for mutation_name in ("mkdir", "rename", "replace", "unlink", "rmdir"):
        monkeypatch.setattr(
            module.os,
            mutation_name,
            lambda *_args, _name=mutation_name, **_kwargs: pytest.fail(
                f"{_name} ran before destination absence was established"
            ),
        )

    with pytest.raises(module.RootfsMaterializationError):
        module._require_destination_absent(
            parent_fd=17,
            destination_name="rootfs-01",
            stat_fn=existing_lookup,
        )

    assert observed == [("rootfs-01", 17, False)]

