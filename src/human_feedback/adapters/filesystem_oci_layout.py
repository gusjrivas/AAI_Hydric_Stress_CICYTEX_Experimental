"""Secure Linux descriptor boundary for an exact OCI image layout."""

from __future__ import annotations

import os
import stat
import sys
from typing import Any

import human_feedback.runtime_oci_layers as runtime_oci_layers
import human_feedback.runtime_oci_layout as runtime_oci_layout
import human_feedback.runtime_oci_tar as runtime_oci_tar

verify_laya_oci_blob_chunks = runtime_oci_layout.verify_laya_oci_blob_chunks
_seal_laya_oci_layout_capture_authority = runtime_oci_layout._seal_laya_oci_layout_capture_authority
_seal_laya_oci_layout_evidence = runtime_oci_layout._seal_laya_oci_layout_evidence

_CONTROL_LIMITS = {
    "oci-layout": runtime_oci_layout.MAX_OCI_LAYOUT_BYTES,
    "index.json": runtime_oci_layout.MAX_OCI_INDEX_BYTES,
}
_NATIVE_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
_MAX_OCI_LAYOUT_ROOT_COMPONENTS = 128


class OciLayoutCaptureError(ValueError):
    """The OCI layout could not be captured atomically and completely."""


class SecureOciLayoutCaptureUnavailableError(OciLayoutCaptureError):
    """The host lacks the descriptor capabilities required by this boundary."""


def _effective_layer_budget(remaining_rootfs: object) -> int:
    if (
        type(remaining_rootfs) is not int
        or remaining_rootfs <= 0
        or remaining_rootfs > runtime_oci_layers.MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES
    ):
        raise ValueError("remaining OCI rootfs budget must be a bounded positive integer")
    return min(
        runtime_oci_layers.MAX_OCI_LAYER_UNCOMPRESSED_BYTES,
        remaining_rootfs,
    )


def _secure_oci_layout_capture_available() -> bool:
    required_flags = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    return (
        sys.platform.startswith("linux")
        and all(hasattr(os, name) for name in required_flags)
        and _NATIVE_OPEN_SUPPORTS_DIR_FD
    )


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _file_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def _preflight_evidence(evidence: object) -> Any:
    try:
        return runtime_oci_layout._require_exact_laya_oci_evidence(evidence)
    except (TypeError, ValueError):
        error = OciLayoutCaptureError("OCI evidence must be an exact factory-sealed type")
        error.__suppress_context__ = True
        raise error


def _root_components(root: Any) -> tuple[str, ...]:
    try:
        raw_root = os.fspath(root)
    except (TypeError, ValueError):
        raise OciLayoutCaptureError("secure OCI layout root is invalid") from None
    if type(raw_root) is not str or not os.path.isabs(raw_root) or raw_root == os.sep:
        raise OciLayoutCaptureError("secure OCI layout root must be absolute and non-root")
    if raw_root.startswith(os.sep * 2) or os.sep * 2 in raw_root or raw_root.endswith(os.sep):
        raise OciLayoutCaptureError("secure OCI layout root is not canonical")
    components = tuple(component for component in raw_root.split(os.sep) if component)
    if not components or any(component in {".", ".."} for component in components):
        raise OciLayoutCaptureError("secure OCI layout root is not canonical")
    if len(components) > _MAX_OCI_LAYOUT_ROOT_COMPONENTS:
        raise OciLayoutCaptureError("secure OCI layout root component limit exceeded")
    return components


def _close_owned_once(owned: list[int]) -> OSError | None:
    first_error = None
    while owned:
        descriptor = owned.pop()
        try:
            os.close(descriptor)
        except OSError as error:
            if first_error is None:
                first_error = error
    return first_error


def _close_descriptor(owned: list[int], descriptor: int) -> None:
    for position in range(len(owned) - 1, -1, -1):
        if owned[position] == descriptor:
            owned.pop(position)
            break
    else:
        raise OciLayoutCaptureError("secure OCI descriptor ownership is invalid")
    try:
        os.close(descriptor)
    except OSError:
        raise OciLayoutCaptureError("secure OCI descriptor cleanup failed") from None


def _open_root_directory(components: tuple[str, ...], owned: list[int]) -> int:
    owned.append(os.open(os.sep, _directory_flags()))
    parent = owned[-1]
    for component in components:
        owned.append(os.open(component, _directory_flags(), dir_fd=parent))
        parent = owned[-1]
    return parent


def _open_directory(parent: int, name: str, owned: list[int]) -> int:
    descriptor = os.open(name, _directory_flags(), dir_fd=parent)
    owned.append(descriptor)
    return descriptor


def _open_file(parent: int, name: str, owned: list[int]) -> int:
    descriptor = os.open(name, _file_flags(), dir_fd=parent)
    owned.append(descriptor)
    return descriptor


def _fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _require_directory(descriptor: int) -> tuple[int, ...]:
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        raise OciLayoutCaptureError("secure OCI inventory entry is not a directory")
    return _fingerprint(metadata)


def _require_file(metadata: os.stat_result, expected_size: int | None = None) -> None:
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise OciLayoutCaptureError("secure OCI inventory entry is not a regular single-link file")
    if expected_size is not None and metadata.st_size != expected_size:
        raise OciLayoutCaptureError("secure OCI blob size does not match the plan")


def _read_bounded(descriptor: int, maximum: int) -> bytes:
    payload = b""
    while len(payload) <= maximum:
        chunk = os.read(descriptor, maximum + 1 - len(payload))
        if not chunk:
            break
        payload += chunk
    if len(payload) > maximum:
        raise OciLayoutCaptureError("secure OCI control exceeds its byte limit")
    return payload


def _capture_control(
    root_fd: int,
    name: str,
    maximum: int,
    owned: list[int],
) -> tuple[bytes, tuple[int, ...]]:
    descriptor = _open_file(root_fd, name, owned)
    try:
        before = os.fstat(descriptor)
        _require_file(before)
        if before.st_size > maximum:
            raise OciLayoutCaptureError("secure OCI control exceeds its byte limit")
        payload = _read_bounded(descriptor, maximum)
        after = os.fstat(descriptor)
        if _fingerprint(before) != _fingerprint(after) or len(payload) != before.st_size:
            raise OciLayoutCaptureError("secure OCI control changed during capture")
        return payload, _fingerprint(before)
    finally:
        _close_descriptor(owned, descriptor)


def _scan_exact(descriptor: int, expected: set[str], maximum: int) -> None:
    seen: set[str] = set()
    with os.scandir(descriptor) as entries:
        for entry in entries:
            if len(seen) >= maximum:
                raise OciLayoutCaptureError("secure OCI inventory entry count exceeds limit")
            name = entry.name
            if type(name) is not str or name not in expected or name in seen:
                raise OciLayoutCaptureError("secure OCI inventory is not exact")
            seen.add(name)
    if seen != expected:
        raise OciLayoutCaptureError("secure OCI inventory is incomplete")


def _verify_inventory_entries(
    root_fd: int,
    blobs_fd: int,
    sha256_fd: int,
    plan: runtime_oci_layout.LayaOciLayoutPlan,
) -> None:
    expected_digests = {blob.digest.removeprefix("sha256:") for blob in plan.blobs}
    _scan_exact(root_fd, {"oci-layout", "index.json", "blobs"}, 3)
    _scan_exact(blobs_fd, {"sha256"}, 1)
    _scan_exact(sha256_fd, expected_digests, len(plan.blobs))


def _verify_exact_laya_oci_layout_inventory(
    root_fd: int,
    blobs_fd: int,
    sha256_fd: int,
    plan: runtime_oci_layout.LayaOciLayoutPlan,
) -> None:
    _verify_inventory_entries(root_fd, blobs_fd, sha256_fd, plan)


def _path_fingerprint(
    parent_fd: int,
    name: str,
    owned: list[int],
    *,
    expected_size: int | None = None,
) -> tuple[int, ...]:
    descriptor = _open_file(parent_fd, name, owned)
    try:
        metadata = os.fstat(descriptor)
        _require_file(metadata, expected_size)
        return _fingerprint(metadata)
    finally:
        _close_descriptor(owned, descriptor)


def _blob_chunks(descriptor: int, expected_size: int):
    captured = 0
    capture_limit = expected_size + 1
    chunk_limit = runtime_oci_layout.MAX_OCI_BLOB_CHUNK_BYTES
    buffer = bytearray()
    while captured < capture_limit:
        amount = min(chunk_limit - len(buffer), capture_limit - captured)
        chunk = os.read(descriptor, amount)
        if not chunk:
            break
        if type(chunk) is not bytes or len(chunk) > amount:
            raise OciLayoutCaptureError("secure OCI blob read is invalid")
        buffer.extend(chunk)
        captured += len(chunk)
        if len(buffer) == chunk_limit:
            yield bytes(buffer)
            buffer.clear()
    if buffer:
        yield bytes(buffer)


def _capture_blob(
    sha256_fd: int,
    plan: runtime_oci_layout.LayaOciLayoutPlan,
    blob: runtime_oci_layout.LayaOciBlobPlan,
    owned: list[int],
) -> tuple[runtime_oci_layout.VerifiedLayaOciBlob, tuple[int, ...]]:
    name = blob.digest.removeprefix("sha256:")
    descriptor = _open_file(sha256_fd, name, owned)
    try:
        before = os.fstat(descriptor)
        _require_file(before, blob.size_bytes)
        receipt = verify_laya_oci_blob_chunks(
            plan,
            blob.digest,
            _blob_chunks(descriptor, blob.size_bytes),
        )
        after = os.fstat(descriptor)
        if _fingerprint(before) != _fingerprint(after):
            raise OciLayoutCaptureError("secure OCI blob changed during capture")
        return receipt, _fingerprint(before)
    finally:
        _close_descriptor(owned, descriptor)


def _capture_layer_diff_id(
    sha256_fd: int,
    plan: Any,
    position: int,
    max_uncompressed_bytes: int,
    owned: list[int],
):
    blob = plan.layer_blobs[position]
    name = blob.digest.removeprefix("sha256:")
    descriptor = _open_file(sha256_fd, name, owned)
    try:
        before = os.fstat(descriptor)
        _require_file(before, blob.size_bytes)
        receipt = runtime_oci_layers.verify_laya_oci_layer_diff_id_chunks(
            plan,
            blob.digest,
            _blob_chunks(descriptor, blob.size_bytes),
            max_uncompressed_bytes=max_uncompressed_bytes,
        )
        after = os.fstat(descriptor)
        if _fingerprint(before) != _fingerprint(after):
            raise OciLayoutCaptureError("secure OCI layer changed during capture")
        return receipt, _fingerprint(before)
    finally:
        _close_descriptor(owned, descriptor)


def _rehash_blob_for_layer_capture(
    sha256_fd: int,
    plan: runtime_oci_layout.LayaOciLayoutPlan,
    blob: runtime_oci_layout.LayaOciBlobPlan,
    owned: list[int],
) -> tuple[int, ...]:
    name = blob.digest.removeprefix("sha256:")
    descriptor = _open_file(sha256_fd, name, owned)
    try:
        before = os.fstat(descriptor)
        _require_file(before, blob.size_bytes)
        runtime_oci_layout.verify_laya_oci_blob_chunks(
            plan,
            blob.digest,
            _blob_chunks(descriptor, blob.size_bytes),
        )
        after = os.fstat(descriptor)
        if _fingerprint(before) != _fingerprint(after):
            raise OciLayoutCaptureError("secure OCI blob changed during capture")
        return _fingerprint(before)
    finally:
        _close_descriptor(owned, descriptor)


def _verify_laya_oci_layout_final_sweep(
    components: tuple[str, ...],
    plan: runtime_oci_layout.LayaOciLayoutPlan,
    fingerprints: dict[str, tuple[int, ...]],
    owned: list[int],
) -> None:
    boundary = len(owned)
    try:
        root_fd = _open_root_directory(components, owned)
        blobs_fd = _open_directory(root_fd, "blobs", owned)
        sha256_fd = _open_directory(blobs_fd, "sha256", owned)
        if _require_directory(root_fd) != fingerprints["root"]:
            raise OciLayoutCaptureError("secure OCI root changed before final sweep")
        if _require_directory(blobs_fd) != fingerprints["blobs"]:
            raise OciLayoutCaptureError("secure OCI blobs directory changed before final sweep")
        if _require_directory(sha256_fd) != fingerprints["sha256"]:
            raise OciLayoutCaptureError("secure OCI digest directory changed before final sweep")
        _verify_inventory_entries(root_fd, blobs_fd, sha256_fd, plan)
        for name in _CONTROL_LIMITS:
            if _path_fingerprint(root_fd, name, owned) != fingerprints["control:" + name]:
                raise OciLayoutCaptureError("secure OCI control path changed before final sweep")
        for blob in plan.blobs:
            name = blob.digest.removeprefix("sha256:")
            if (
                _path_fingerprint(
                    sha256_fd,
                    name,
                    owned,
                    expected_size=blob.size_bytes,
                )
                != fingerprints["blob:" + blob.role]
            ):
                raise OciLayoutCaptureError("secure OCI blob path changed before final sweep")
    finally:
        temporary = owned[boundary:]
        del owned[boundary:]
        if _close_owned_once(temporary) is not None:
            raise OciLayoutCaptureError("secure OCI final sweep cleanup failed") from None


def _capture_and_verify(
    evidence: Any,
    components: tuple[str, ...],
) -> runtime_oci_layout.LayaRuntimeOciLayoutEvidence:
    owned: list[int] = []
    close_error = None
    result = None
    try:
        root_fd = _open_root_directory(components, owned)
        fingerprints = {"root": _require_directory(root_fd)}
        controls = {}
        for name, maximum in _CONTROL_LIMITS.items():
            payload, fingerprint = _capture_control(root_fd, name, maximum, owned)
            controls[name] = payload
            fingerprints["control:" + name] = fingerprint
            if _path_fingerprint(root_fd, name, owned) != fingerprint:
                raise OciLayoutCaptureError("secure OCI control path changed during capture")
        plan = runtime_oci_layout.prepare_laya_oci_layout_plan(
            evidence,
            controls["oci-layout"],
            controls["index.json"],
        )
        blobs_fd = _open_directory(root_fd, "blobs", owned)
        sha256_fd = _open_directory(blobs_fd, "sha256", owned)
        fingerprints["blobs"] = _require_directory(blobs_fd)
        fingerprints["sha256"] = _require_directory(sha256_fd)
        _verify_exact_laya_oci_layout_inventory(root_fd, blobs_fd, sha256_fd, plan)
        receipts = []
        for blob in plan.blobs:
            receipt, fingerprint = _capture_blob(sha256_fd, plan, blob, owned)
            receipts.append(receipt)
            fingerprints["blob:" + blob.role] = fingerprint
            name = blob.digest.removeprefix("sha256:")
            if (
                _path_fingerprint(
                    sha256_fd,
                    name,
                    owned,
                    expected_size=blob.size_bytes,
                )
                != fingerprint
            ):
                raise OciLayoutCaptureError("secure OCI blob path changed during capture")
        receipt_tuple = tuple(receipts)
        _verify_laya_oci_layout_final_sweep(components, plan, fingerprints, owned)
        close_error = _close_owned_once(owned)
        if close_error is not None:
            raise OciLayoutCaptureError("secure OCI descriptor cleanup failed")
        authority = _seal_laya_oci_layout_capture_authority(
            plan,
            receipt_tuple,
            controls_captured_from_same_root=True,
            inventory_captured_from_same_root=True,
            final_fd_sweep_verified=True,
        )
        result = _seal_laya_oci_layout_evidence(authority)
    finally:
        final_error = _close_owned_once(owned)
        if final_error is not None and close_error is None:
            raise OciLayoutCaptureError("secure OCI descriptor cleanup failed") from None
    return result


def capture_and_verify_laya_oci_layout(
    oci_evidence: Any,
    layout_root: Any,
) -> runtime_oci_layout.LayaRuntimeOciLayoutEvidence:
    """Capture and verify one exact OCI layout through a secure Linux boundary."""

    validated_evidence = _preflight_evidence(oci_evidence)
    if not _secure_oci_layout_capture_available():
        error = SecureOciLayoutCaptureUnavailableError(
            "secure OCI layout capture capability is unavailable"
        )
        error.__suppress_context__ = True
        raise error
    try:
        components = _root_components(layout_root)
        return _capture_and_verify(validated_evidence, components)
    except SecureOciLayoutCaptureUnavailableError:
        raise
    except Exception:
        error = OciLayoutCaptureError("secure OCI layout capture failed")
        error.__suppress_context__ = True
        raise error


def _capture_and_verify_layer_diff_ids(
    layer_plan: Any,
    components: tuple[str, ...],
):
    layout_plan = layer_plan.layout_plan
    owned: list[int] = []
    close_error = None
    result = None
    try:
        root_fd = _open_root_directory(components, owned)
        fingerprints = {"root": _require_directory(root_fd)}
        controls = {}
        for name, maximum in _CONTROL_LIMITS.items():
            payload, fingerprint = _capture_control(root_fd, name, maximum, owned)
            controls[name] = payload
            fingerprints["control:" + name] = fingerprint
            if _path_fingerprint(root_fd, name, owned) != fingerprint:
                raise OciLayoutCaptureError("secure OCI control path changed during capture")
        captured_plan = runtime_oci_layout.prepare_laya_oci_layout_plan(
            layout_plan.oci_evidence,
            controls["oci-layout"],
            controls["index.json"],
        )
        if captured_plan != layout_plan:
            raise OciLayoutCaptureError("secure OCI layout plan does not match config evidence")

        blobs_fd = _open_directory(root_fd, "blobs", owned)
        sha256_fd = _open_directory(blobs_fd, "sha256", owned)
        fingerprints["blobs"] = _require_directory(blobs_fd)
        fingerprints["sha256"] = _require_directory(sha256_fd)
        _verify_exact_laya_oci_layout_inventory(root_fd, blobs_fd, sha256_fd, layout_plan)

        for blob in layout_plan.blobs:
            fingerprint = _rehash_blob_for_layer_capture(
                sha256_fd,
                layout_plan,
                blob,
                owned,
            )
            fingerprints["blob:" + blob.role] = fingerprint
            name = blob.digest.removeprefix("sha256:")
            if (
                _path_fingerprint(
                    sha256_fd,
                    name,
                    owned,
                    expected_size=blob.size_bytes,
                )
                != fingerprint
            ):
                raise OciLayoutCaptureError("secure OCI blob path changed during capture")

        receipts = []
        remaining_rootfs = runtime_oci_layers.MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES
        for position, blob in enumerate(layer_plan.layer_blobs):
            effective_limit = _effective_layer_budget(remaining_rootfs)
            receipt, fingerprint = _capture_layer_diff_id(
                sha256_fd,
                layer_plan,
                position,
                effective_limit,
                owned,
            )
            remaining_rootfs -= receipt.uncompressed_size_bytes
            if fingerprint != fingerprints["blob:" + blob.role]:
                raise OciLayoutCaptureError("secure OCI layer changed between verification passes")
            name = blob.digest.removeprefix("sha256:")
            if (
                _path_fingerprint(
                    sha256_fd,
                    name,
                    owned,
                    expected_size=blob.size_bytes,
                )
                != fingerprint
            ):
                raise OciLayoutCaptureError("secure OCI layer path changed during capture")
            receipts.append(receipt)

        receipt_tuple = tuple(receipts)
        _verify_laya_oci_layout_final_sweep(
            components,
            layout_plan,
            fingerprints,
            owned,
        )
        close_error = _close_owned_once(owned)
        if close_error is not None:
            raise OciLayoutCaptureError("secure OCI descriptor cleanup failed")
        authority = runtime_oci_layers._seal_laya_oci_layer_diff_ids_capture_authority(
            layer_plan,
            receipt_tuple,
            layers_captured_from_same_root=True,
            inventory_captured_from_same_root=True,
            final_fd_sweep_verified=True,
            descriptors_closed_before_seal=True,
        )
        result = runtime_oci_layers._seal_laya_runtime_oci_layer_diff_ids_evidence(authority)
    finally:
        final_error = _close_owned_once(owned)
        if final_error is not None and close_error is None:
            raise OciLayoutCaptureError("secure OCI descriptor cleanup failed") from None
    return result


def capture_and_verify_laya_oci_layer_diff_ids(
    config_evidence: Any,
    layout_root: Any,
) -> Any:
    """Capture all OCI layer bytes and attest their declared DiffIDs atomically."""

    preflight_failed = False
    try:
        layer_plan = runtime_oci_layers.prepare_laya_oci_layer_diff_id_plan(config_evidence)
    except Exception:
        preflight_failed = True
    if preflight_failed:
        error = OciLayoutCaptureError("OCI config evidence is invalid")
        error.__suppress_context__ = True
        raise error
    if not _secure_oci_layout_capture_available():
        error = SecureOciLayoutCaptureUnavailableError(
            "secure OCI layout capture capability is unavailable"
        )
        error.__suppress_context__ = True
        raise error
    try:
        components = _root_components(layout_root)
        return _capture_and_verify_layer_diff_ids(layer_plan, components)
    except SecureOciLayoutCaptureUnavailableError:
        raise
    except Exception:
        error = OciLayoutCaptureError("secure OCI layer DiffID capture failed")
        error.__suppress_context__ = True
        raise error


def _capture_and_verify_tar_semantics(
    tar_plan: Any,
    components: tuple[str, ...],
    *,
    _payload_sink_factory=None,
    _expected_tar_receipts=None,
):
    if _payload_sink_factory is not None and not callable(_payload_sink_factory):
        raise OciLayoutCaptureError("secure OCI TAR payload sink factory is invalid")
    if _expected_tar_receipts is not None and (
        type(_expected_tar_receipts) is not tuple or len(_expected_tar_receipts) != 10
    ):
        raise OciLayoutCaptureError("secure OCI expected TAR receipt coverage is invalid")
    layout_plan = tar_plan.layout_plan
    owned: list[int] = []
    close_error = None
    result = None
    try:
        root_fd = _open_root_directory(components, owned)
        fingerprints = {"root": _require_directory(root_fd)}
        controls = {}
        for name, maximum in _CONTROL_LIMITS.items():
            payload, fingerprint = _capture_control(root_fd, name, maximum, owned)
            controls[name] = payload
            fingerprints["control:" + name] = fingerprint
            if _path_fingerprint(root_fd, name, owned) != fingerprint:
                raise OciLayoutCaptureError("secure OCI control path changed during capture")
        captured_plan = runtime_oci_layout.prepare_laya_oci_layout_plan(
            layout_plan.oci_evidence,
            controls["oci-layout"],
            controls["index.json"],
        )
        if captured_plan != layout_plan:
            raise OciLayoutCaptureError("secure OCI layout plan does not match TAR evidence")

        blobs_fd = _open_directory(root_fd, "blobs", owned)
        sha256_fd = _open_directory(blobs_fd, "sha256", owned)
        fingerprints["blobs"] = _require_directory(blobs_fd)
        fingerprints["sha256"] = _require_directory(sha256_fd)
        _verify_exact_laya_oci_layout_inventory(root_fd, blobs_fd, sha256_fd, layout_plan)

        for blob in layout_plan.blobs:
            fingerprint = _rehash_blob_for_layer_capture(
                sha256_fd,
                layout_plan,
                blob,
                owned,
            )
            fingerprints["blob:" + blob.role] = fingerprint
            name = blob.digest.removeprefix("sha256:")
            if (
                _path_fingerprint(
                    sha256_fd,
                    name,
                    owned,
                    expected_size=blob.size_bytes,
                )
                != fingerprint
            ):
                raise OciLayoutCaptureError("secure OCI blob path changed during TAR capture")

        receipts = []
        remaining_rootfs = runtime_oci_layers.MAX_OCI_ROOTFS_UNCOMPRESSED_BYTES
        for position, blob in enumerate(tar_plan.layer_plan.layer_blobs):
            effective_limit = _effective_layer_budget(remaining_rootfs)
            name = blob.digest.removeprefix("sha256:")
            descriptor = _open_file(sha256_fd, name, owned)
            try:
                before = os.fstat(descriptor)
                _require_file(before, blob.size_bytes)
                verify_kwargs = {"max_uncompressed_bytes": effective_limit}
                if _payload_sink_factory is not None:
                    verify_kwargs["_payload_sink"] = _payload_sink_factory(position)
                receipt = runtime_oci_tar._verify_laya_oci_tar_semantics_chunks_with_budget(
                    tar_plan,
                    blob.digest,
                    _blob_chunks(descriptor, blob.size_bytes),
                    **verify_kwargs,
                )
                after = os.fstat(descriptor)
                if _fingerprint(before) != _fingerprint(after):
                    raise OciLayoutCaptureError("secure OCI layer changed during TAR capture")
                fingerprint = _fingerprint(before)
            finally:
                _close_descriptor(owned, descriptor)
            if fingerprint != fingerprints["blob:" + blob.role]:
                raise OciLayoutCaptureError("secure OCI layer changed between TAR passes")
            if (
                _path_fingerprint(
                    sha256_fd,
                    name,
                    owned,
                    expected_size=blob.size_bytes,
                )
                != fingerprint
            ):
                raise OciLayoutCaptureError("secure OCI layer path changed during TAR capture")
            if _expected_tar_receipts is not None:
                expected = _expected_tar_receipts[position]
                if any(
                    getattr(receipt, name, None) != getattr(expected, name, None)
                    for name in (
                        "layer_position",
                        "entries",
                        "root_directory",
                        "payload_size_bytes",
                        "tar_size_bytes",
                        "layer_receipt",
                    )
                ):
                    raise OciLayoutCaptureError("secure OCI TAR receipt does not match expected")
            remaining_rootfs -= receipt.layer_receipt.uncompressed_size_bytes
            receipts.append(receipt)

        receipt_tuple = tuple(receipts)
        _verify_laya_oci_layout_final_sweep(
            components,
            layout_plan,
            fingerprints,
            owned,
        )
        close_error = _close_owned_once(owned)
        if close_error is not None:
            raise OciLayoutCaptureError("secure OCI descriptor cleanup failed")
        authority = runtime_oci_tar._seal_laya_oci_tar_semantics_capture_authority(
            tar_plan,
            receipt_tuple,
            controls_captured_from_same_root=True,
            blobs_captured_from_same_root=True,
            inventory_captured_from_same_root=True,
            final_fd_sweep_verified=True,
            descriptors_closed_before_seal=True,
        )
        result = runtime_oci_tar._seal_laya_runtime_oci_tar_semantics_evidence(authority)
    finally:
        final_error = _close_owned_once(owned)
        if final_error is not None and close_error is None:
            raise OciLayoutCaptureError("secure OCI descriptor cleanup failed") from None
    return result


def capture_and_verify_laya_oci_tar_semantics(
    layer_evidence: Any,
    layout_root: Any,
) -> Any:
    """Recapture all layers and attest bounded TAR semantics atomically."""

    preflight_failed = False
    try:
        tar_plan = runtime_oci_tar.prepare_laya_oci_tar_semantics_plan(layer_evidence)
    except Exception:
        preflight_failed = True
    if preflight_failed:
        error = OciLayoutCaptureError("OCI TAR layer evidence is invalid")
        error.__suppress_context__ = True
        raise error
    if not _secure_oci_layout_capture_available():
        error = SecureOciLayoutCaptureUnavailableError(
            "secure OCI layout capture capability is unavailable"
        )
        error.__suppress_context__ = True
        raise error
    try:
        components = _root_components(layout_root)
        return _capture_and_verify_tar_semantics(tar_plan, components)
    except SecureOciLayoutCaptureUnavailableError:
        raise
    except Exception:
        error = OciLayoutCaptureError("secure OCI TAR semantics capture failed")
        error.__suppress_context__ = True
        raise error
