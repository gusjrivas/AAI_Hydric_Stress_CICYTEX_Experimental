"""Fail-closed filesystem boundary for a disposable Laya rootfs."""

from __future__ import annotations

import os
import re
import stat
import sys

from human_feedback import runtime_rootfs_materialization as _authority

__all__ = (
    "RootfsMaterializationError",
    "SecureRootfsMaterializationUnavailableError",
    "materialize_laya_runtime_rootfs",
)

STAGING_MODE = 0o700
DESTINATION_MUST_BE_ABSENT = True
STAGING_IS_DESTINATION_SIBLING = True
ATOMIC_NO_CLOBBER_REQUIRED = True
_MAX_ROOT_COMPONENTS = 128
_DESTINATION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class RootfsMaterializationError(ValueError):
    """A rootfs could not be materialized without weakening its authority."""


class SecureRootfsMaterializationUnavailableError(RootfsMaterializationError):
    """The host lacks the required non-root Linux filesystem capabilities."""


def _raise_private(error_type: type[RootfsMaterializationError], message: str) -> None:
    error = error_type(message)
    error.__suppress_context__ = True
    raise error from None


def _secure_rootfs_materialization_available() -> bool:
    required_flags = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW")
    return (
        sys.platform.startswith("linux")
        and hasattr(os, "geteuid")
        and os.geteuid() != 0
        and all(hasattr(os, flag) for flag in required_flags)
        and os.open in os.supports_dir_fd
        and os.mkdir in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
    )


def _absolute_root_components(value: object, label: str) -> tuple[str, ...]:
    if (
        type(value) is not str
        or not value.startswith("/")
        or value.startswith("//")
        or value == "/"
        or value.endswith("/")
        or "\\" in value
        or "\x00" in value
    ):
        _raise_private(RootfsMaterializationError, f"{label} is not a canonical root")
    components = tuple(value[1:].split("/"))
    if (
        not components
        or len(components) > _MAX_ROOT_COMPONENTS
        or any(component in {"", ".", ".."} for component in components)
    ):
        _raise_private(RootfsMaterializationError, f"{label} is not a canonical root")
    return components


def _validate_destination_name(value: object) -> str:
    if type(value) is not str or value in {".", ".."} or _DESTINATION_NAME.fullmatch(value) is None:
        _raise_private(RootfsMaterializationError, "destination name is invalid")
    return value


def _validate_private_parent_stat(parent_stat: object, *, effective_uid: int) -> None:
    try:
        mode = parent_stat.st_mode
        uid = parent_stat.st_uid
        valid = (
            type(mode) is int
            and type(uid) is int
            and type(effective_uid) is int
            and stat.S_ISDIR(mode)
            and uid == effective_uid
            and mode & 0o022 == 0
        )
    except Exception:
        valid = False
    if not valid:
        _raise_private(RootfsMaterializationError, "destination parent is not private")


def _require_destination_absent(
    *,
    parent_fd: int,
    destination_name: str,
    stat_fn: object = os.stat,
) -> None:
    try:
        stat_fn(destination_name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except Exception:
        _raise_private(RootfsMaterializationError, "destination absence check failed")
    _raise_private(RootfsMaterializationError, "destination already exists")


def _preflight_plan(plan: object) -> _authority.LayaRuntimeRootfsMaterializationPlan:
    result = None
    try:
        if type(plan) is not _authority.LayaRuntimeRootfsMaterializationPlan:
            raise TypeError("rootfs materialization plan type is invalid")
        plan.__post_init__(_authority._FACTORY_TOKEN)
        _authority.prepare_laya_runtime_rootfs_materialization_plan(
            plan._rootfs_evidence,
            plan._supply_evidence,
        )
        result = plan
    except Exception:
        result = None
    if result is None:
        _raise_private(
            RootfsMaterializationError,
            "rootfs materialization authority validation failed",
        )
    return result


def materialize_laya_runtime_rootfs(
    plan: object,
    source_root: object,
    destination_parent: object,
    destination_name: object,
) -> _authority.LayaRuntimeRootfsMaterializationEvidence:
    """Validate authority before any path coercion or filesystem mutation."""

    _preflight_plan(plan)
    if not _secure_rootfs_materialization_available():
        _raise_private(
            SecureRootfsMaterializationUnavailableError,
            "secure non-root Linux rootfs materialization is unavailable",
        )
    _raise_private(
        SecureRootfsMaterializationUnavailableError,
        "secure rootfs materialization backend is not installed",
    )
