"""Pure bounded TAR semantics for exact PR22 OCI layer evidence."""

from __future__ import annotations

import json
from dataclasses import InitVar, dataclass, field

import human_feedback.runtime_oci_layers as runtime_oci_layers

OCI_TAR_SEMANTICS_PLAN_SCHEMA = "laya-oci-tar-semantics-plan-v1"
OCI_TAR_SEMANTICS_EVIDENCE_SCHEMA = "laya-runtime-oci-tar-semantics-evidence-v1"
MAX_OCI_TAR_CHUNK_BYTES = 1_024 * 1_024
MAX_OCI_TAR_CHUNKS = 4_096
MAX_OCI_TAR_ENTRIES = 65_536
MAX_OCI_TAR_PATH_BYTES = 4_096
MAX_OCI_TAR_LINK_BYTES = 4_096
MAX_OCI_TAR_PAX_RECORD_BYTES = 64 * 1_024
MAX_OCI_TAR_PAX_BYTES = 1_024 * 1_024
MAX_OCI_TAR_ENTRY_PAYLOAD_BYTES = 2 * 1_024 * 1_024 * 1_024
MAX_OCI_TAR_PAYLOAD_BYTES = 3 * 1_024 * 1_024 * 1_024
MAX_OCI_TAR_BYTES = MAX_OCI_TAR_PAYLOAD_BYTES + (MAX_OCI_TAR_ENTRIES + 2) * 512

_BLOCK_BYTES = 512
_FACTORY_TOKEN = object()
_ZERO_BLOCK = b"\0" * _BLOCK_BYTES
_INHERITED_CLAIMS = (
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


def _tar_claim_values(value: object) -> tuple[bool, ...]:
    return (
        value.artifact_integrity_verified,
        value.oci_manifest_semantics_verified,
        value.oci_layout_controls_bytes_verified,
        value.oci_blob_inventory_verified,
        value.oci_same_root_capture_verified,
        value.oci_manifest_blob_bytes_verified,
        value.oci_config_blob_bytes_verified,
        value.oci_layer_blobs_bytes_verified,
        value.oci_bytes_verified,
        value.oci_config_semantics_verified,
        value.oci_layer_diff_ids_verified,
        value.lock_verified,
        value.sbom_verified,
        value.lock_sbom_consistent,
        value.runtime_config_semantics_verified,
        value.checkpoint_manifest_semantics_verified,
        value.checkpoint_bytes_verified,
        value.oci_rootfs_verified,
        value.tar_semantics_verified,
        value.origin_verified,
        value.license_verified,
        value.base_ancestry_verified,
        value.rootfs_materialized,
        value.runtime_materialized,
        value.executor_available,
        value.inference_executed,
    )


def _expected_tar_claim_values(layer_evidence: object) -> tuple[bool, ...]:
    return (
        layer_evidence.artifact_integrity_verified,
        layer_evidence.oci_manifest_semantics_verified,
        layer_evidence.oci_layout_controls_bytes_verified,
        layer_evidence.oci_blob_inventory_verified,
        layer_evidence.oci_same_root_capture_verified,
        layer_evidence.oci_manifest_blob_bytes_verified,
        layer_evidence.oci_config_blob_bytes_verified,
        layer_evidence.oci_layer_blobs_bytes_verified,
        layer_evidence.oci_bytes_verified,
        layer_evidence.oci_config_semantics_verified,
        layer_evidence.oci_layer_diff_ids_verified,
        layer_evidence.lock_verified,
        layer_evidence.sbom_verified,
        layer_evidence.lock_sbom_consistent,
        layer_evidence.runtime_config_semantics_verified,
        layer_evidence.checkpoint_manifest_semantics_verified,
        layer_evidence.checkpoint_bytes_verified,
        layer_evidence.oci_rootfs_verified,
        True,
        layer_evidence.origin_verified,
        layer_evidence.license_verified,
        layer_evidence.base_ancestry_verified,
        layer_evidence.rootfs_materialized,
        layer_evidence.runtime_materialized,
        layer_evidence.executor_available,
        layer_evidence.inference_executed,
    )


def _private_repr(value: object) -> str:
    return f"<{type(value).__name__}: sealed private OCI TAR value>"


def _raise_private(error_type: type[Exception], message: str) -> None:
    error = error_type(message)
    error.__suppress_context__ = True
    raise error


@dataclass(frozen=True, slots=True, repr=False)
class LayaOciTarEntry:
    path: str = field(repr=False)
    typeflag: str
    size_bytes: int
    link_target: str | None = field(repr=False)
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI TAR entry requires the factory seal token")
        if (
            self.typeflag not in ("0", "1", "2", "5")
            or type(self.size_bytes) is not int
            or not 0 <= self.size_bytes <= MAX_OCI_TAR_ENTRY_PAYLOAD_BYTES
            or (self.typeflag in ("1", "2", "5") and self.size_bytes != 0)
            or (self.typeflag in ("1", "2")) != (type(self.link_target) is str)
            or (self.typeflag not in ("1", "2") and self.link_target is not None)
        ):
            raise ValueError("OCI TAR entry binding is invalid")
        if _normalize_entry_path(self.path) != self.path:
            raise ValueError("OCI TAR entry path is invalid")
        if self.link_target is not None:
            _validate_link_target(self.link_target)

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class LayaOciTarSemanticsPlan:
    schema_version: str
    layer_evidence: runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence = field(repr=False)
    layer_plan: object = field(repr=False)
    layout_plan: object = field(repr=False)
    runtime_identity: object = field(repr=False)
    layer_receipts: tuple[object, ...] = field(repr=False)
    _factory_token: InitVar[object]
    tar_semantics_verified: bool = field(default=False, init=False)
    oci_rootfs_verified: bool = field(default=False, init=False)
    rootfs_materialized: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI TAR plan requires the factory seal token")
        if self.schema_version != OCI_TAR_SEMANTICS_PLAN_SCHEMA:
            raise ValueError("OCI TAR plan schema is invalid")
        if type(self.layer_evidence) is not runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence:
            raise ValueError("OCI TAR layer evidence type is invalid")
        runtime_oci_layers.canonical_laya_runtime_oci_layer_diff_ids_summary_bytes(
            self.layer_evidence
        )
        if (
            self.layer_plan is not self.layer_evidence.plan
            or self.layout_plan is not self.layer_evidence.layout_plan
            or self.runtime_identity is not self.layer_evidence.runtime_identity
            or self.layer_receipts is not self.layer_evidence.receipts
            or type(self.layer_receipts) is not tuple
            or len(self.layer_receipts) != 10
            or self.layer_evidence.oci_layer_diff_ids_verified is not True
            or self.layer_evidence.tar_semantics_verified is not False
            or self.tar_semantics_verified is not False
            or self.oci_rootfs_verified is not False
            or self.rootfs_materialized is not False
            or self.origin_verified is not False
        ):
            raise ValueError("OCI TAR plan binding is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedLayaOciTarLayer:
    plan: LayaOciTarSemanticsPlan = field(repr=False)
    layer_receipt: object = field(repr=False)
    layer_position: int
    entries: tuple[LayaOciTarEntry, ...] = field(repr=False)
    payload_size_bytes: int = field(repr=False)
    tar_size_bytes: int = field(repr=False)
    _factory_token: InitVar[object]
    tar_semantics_verified: bool = field(default=True, init=False)
    oci_rootfs_verified: bool = field(default=False, init=False)
    rootfs_materialized: bool = field(default=False, init=False)
    origin_verified: bool = field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI TAR receipt requires the factory seal token")
        if type(self.plan) is not LayaOciTarSemanticsPlan:
            raise ValueError("OCI TAR receipt plan is invalid")
        historical = (
            self.plan.layer_receipts[self.layer_position]
            if type(self.layer_position) is int
            and 0 <= self.layer_position < len(self.plan.layer_receipts)
            else None
        )
        if (
            type(self.layer_position) is not int
            or not 0 <= self.layer_position < len(self.plan.layer_receipts)
            or type(self.layer_receipt) is not type(historical)
            or self.layer_receipt.plan is not self.plan.layer_plan
            or self.layer_receipt.layer_position != self.layer_position
            or self.layer_receipt.layer_blob is not historical.layer_blob
            or self.layer_receipt.compressed_receipt is not historical.compressed_receipt
            or self.layer_receipt.declared_diff_id != historical.declared_diff_id
            or self.layer_receipt.computed_diff_id != historical.computed_diff_id
            or self.layer_receipt.compressed_blob_bytes_verified is not True
            or self.layer_receipt.layer_diff_id_verified is not True
            or self.layer_receipt.tar_semantics_verified is not False
            or self.layer_receipt.rootfs_verified is not False
            or self.layer_receipt.origin_verified is not False
            or type(self.layer_receipt.uncompressed_size_bytes) is not int
            or not 0
            <= self.layer_receipt.uncompressed_size_bytes
            <= MAX_OCI_TAR_ENTRY_PAYLOAD_BYTES
            or self.layer_receipt.uncompressed_size_bytes != historical.uncompressed_size_bytes
            or type(self.entries) is not tuple
            or len(self.entries) > MAX_OCI_TAR_ENTRIES
            or any(type(entry) is not LayaOciTarEntry for entry in self.entries)
            or type(self.payload_size_bytes) is not int
            or not 0 <= self.payload_size_bytes <= MAX_OCI_TAR_PAYLOAD_BYTES
            or type(self.tar_size_bytes) is not int
            or self.tar_size_bytes != self.layer_receipt.uncompressed_size_bytes
            or self.tar_semantics_verified is not True
            or self.oci_rootfs_verified is not False
            or self.rootfs_materialized is not False
            or self.origin_verified is not False
        ):
            raise ValueError("OCI TAR receipt binding is invalid")
        paths: set[str] = set()
        payload_size = 0
        for entry in self.entries:
            entry.__post_init__(_FACTORY_TOKEN)
            if entry.path in paths:
                raise ValueError("OCI TAR receipt has duplicate entry paths")
            paths.add(entry.path)
            payload_size += entry.size_bytes
            if payload_size > MAX_OCI_TAR_PAYLOAD_BYTES:
                raise ValueError("OCI TAR receipt payload size is invalid")
        if payload_size != self.payload_size_bytes:
            raise ValueError("OCI TAR receipt payload size is invalid")

    __repr__ = _private_repr


def _validate_tar_receipts(
    plan: LayaOciTarSemanticsPlan,
    receipts: object,
) -> tuple[VerifiedLayaOciTarLayer, ...]:
    if type(receipts) is not tuple or len(receipts) != len(plan.layer_receipts):
        raise ValueError("OCI TAR receipt coverage is invalid")
    for position, receipt in enumerate(receipts):
        if type(receipt) is not VerifiedLayaOciTarLayer:
            raise ValueError("OCI TAR receipt type is invalid")
        receipt.__post_init__(_FACTORY_TOKEN)
        if receipt.plan is not plan or receipt.layer_position != position:
            raise ValueError("OCI TAR receipt order is invalid")
    return receipts


@dataclass(frozen=True, slots=True, repr=False)
class _LayaOciTarSemanticsCaptureAuthority:
    plan: LayaOciTarSemanticsPlan = field(repr=False)
    receipts: tuple[VerifiedLayaOciTarLayer, ...] = field(repr=False)
    controls_captured_from_same_root: bool
    blobs_captured_from_same_root: bool
    inventory_captured_from_same_root: bool
    final_fd_sweep_verified: bool
    descriptors_closed_before_seal: bool
    _factory_token: InitVar[object]

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI TAR capture authority requires the factory seal token")
        if type(self.plan) is not LayaOciTarSemanticsPlan:
            raise ValueError("OCI TAR capture authority plan is invalid")
        self.plan.__post_init__(_FACTORY_TOKEN)
        _validate_tar_receipts(self.plan, self.receipts)
        if any(
            flag is not True
            for flag in (
                self.controls_captured_from_same_root,
                self.blobs_captured_from_same_root,
                self.inventory_captured_from_same_root,
                self.final_fd_sweep_verified,
                self.descriptors_closed_before_seal,
            )
        ):
            raise ValueError("OCI TAR capture authority closure is invalid")

    __repr__ = _private_repr


@dataclass(frozen=True, slots=True, repr=False)
class LayaRuntimeOciTarSemanticsEvidence:
    schema_version: str
    plan: LayaOciTarSemanticsPlan = field(repr=False)
    runtime_identity: object = field(repr=False)
    receipts: tuple[VerifiedLayaOciTarLayer, ...] = field(repr=False)
    _factory_token: InitVar[object]
    artifact_integrity_verified: bool = field(default=True, init=False)
    oci_manifest_semantics_verified: bool = field(default=True, init=False)
    oci_layout_controls_bytes_verified: bool = field(default=True, init=False)
    oci_blob_inventory_verified: bool = field(default=True, init=False)
    oci_same_root_capture_verified: bool = field(default=True, init=False)
    oci_manifest_blob_bytes_verified: bool = field(default=True, init=False)
    oci_config_blob_bytes_verified: bool = field(default=True, init=False)
    oci_layer_blobs_bytes_verified: bool = field(default=True, init=False)
    oci_bytes_verified: bool = field(default=True, init=False)
    oci_config_semantics_verified: bool = field(default=True, init=False)
    oci_layer_diff_ids_verified: bool = field(default=True, init=False)
    lock_verified: bool = field(default=False, init=False)
    sbom_verified: bool = field(default=False, init=False)
    lock_sbom_consistent: bool = field(default=False, init=False)
    runtime_config_semantics_verified: bool = field(default=False, init=False)
    checkpoint_manifest_semantics_verified: bool = field(default=False, init=False)
    checkpoint_bytes_verified: bool = field(default=False, init=False)
    oci_rootfs_verified: bool = field(default=False, init=False)
    tar_semantics_verified: bool = field(default=True, init=False)
    origin_verified: bool = field(default=False, init=False)
    license_verified: bool = field(default=False, init=False)
    base_ancestry_verified: bool = field(default=False, init=False)
    rootfs_materialized: bool = field(default=False, init=False)
    runtime_materialized: bool = field(default=False, init=False)
    executor_available: bool = field(default=False, init=False)
    inference_executed: bool = field(default=False, init=False)

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise ValueError("OCI TAR evidence requires the factory seal token")
        if (
            self.schema_version != OCI_TAR_SEMANTICS_EVIDENCE_SCHEMA
            or type(self.plan) is not LayaOciTarSemanticsPlan
            or self.runtime_identity is not self.plan.runtime_identity
            or type(self.receipts) is not tuple
            or len(self.receipts) != 10
            or any(
                type(receipt) is not VerifiedLayaOciTarLayer
                or receipt.plan is not self.plan
                or receipt.layer_position != position
                for position, receipt in enumerate(self.receipts)
            )
            or any(
                actual is not expected
                for actual, expected in zip(
                    _tar_claim_values(self),
                    _expected_tar_claim_values(self.plan.layer_evidence),
                    strict=True,
                )
            )
        ):
            raise ValueError("OCI TAR evidence binding is invalid")
        self.plan.__post_init__(_FACTORY_TOKEN)
        for receipt in self.receipts:
            receipt.__post_init__(_FACTORY_TOKEN)

    __repr__ = _private_repr


def _decode_field(field_value: bytes, *, limit: int) -> str:
    terminator = field_value.find(b"\0")
    raw = field_value if terminator < 0 else field_value[:terminator]
    if terminator >= 0 and any(field_value[terminator:]):
        raise ValueError("OCI TAR string field is invalid")
    if not raw or len(raw) > limit:
        raise ValueError("OCI TAR string field size is invalid")
    value = raw.decode("utf-8")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("OCI TAR string field contains controls")
    return value


def _validate_link_target(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8")) > MAX_OCI_TAR_LINK_BYTES
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("OCI TAR link target is invalid")
    return value


def _normalize_entry_path(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8")) > MAX_OCI_TAR_PATH_BYTES
        or value.startswith("/")
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("OCI TAR entry path is invalid")
    while value.endswith("/"):
        value = value[:-1]
    normalized = ""
    for component in value.split("/"):
        if component == ".":
            continue
        if (
            not component
            or component == ".."
            or (not normalized and len(component) >= 2 and component[1] == ":")
        ):
            raise ValueError("OCI TAR entry path is invalid")
        normalized = component if not normalized else normalized + "/" + component
    if not normalized:
        raise ValueError("OCI TAR entry path is invalid")
    return normalized


def _parse_octal(field_value: bytes) -> int:
    stripped = field_value.strip(b" \0")
    if not stripped or any(value < 48 or value > 55 for value in stripped):
        raise ValueError("OCI TAR numeric field is invalid")
    return int(stripped, 8)


def _validate_header_checksum(header: bytes) -> None:
    expected = _parse_octal(header[148:156])
    checksum_view = bytearray(header)
    checksum_view[148:156] = b"        "
    if sum(checksum_view) != expected:
        raise ValueError("OCI TAR header checksum is invalid")


def _header_entry_path(header: bytes, profile: str) -> str:
    name = _decode_field(header[0:100], limit=100)
    if profile == "gnu":
        return name
    prefix_field = header[345:500]
    prefix = _decode_field(prefix_field, limit=155) if any(prefix_field) else ""
    return name if not prefix else prefix + "/" + name


def _header_link_target(header: bytes) -> str:
    return _validate_link_target(
        _decode_field(header[157:257], limit=min(100, MAX_OCI_TAR_LINK_BYTES))
    )


def _parse_pax_size(value: str) -> int:
    if (
        not value
        or any(character not in "0123456789" for character in value)
        or (len(value) > 1 and value.startswith("0"))
    ):
        raise ValueError("OCI TAR PAX size is invalid")
    size = int(value)
    if size > MAX_OCI_TAR_ENTRY_PAYLOAD_BYTES:
        raise ValueError("OCI TAR PAX size exceeds limit")
    return size


def _parse_pax_payload(payload: bytes) -> dict[str, str | int]:
    records: dict[str, str | int] = {}
    offset = 0
    while offset < len(payload):
        separator = payload.find(b" ", offset)
        if separator < 0:
            raise ValueError("OCI TAR PAX record length is invalid")
        length_bytes = payload[offset:separator]
        if (
            not length_bytes
            or any(value < 48 or value > 57 for value in length_bytes)
            or (len(length_bytes) > 1 and length_bytes.startswith(b"0"))
        ):
            raise ValueError("OCI TAR PAX record length is invalid")
        record_size = int(length_bytes)
        record_end = offset + record_size
        if (
            record_size > MAX_OCI_TAR_PAX_RECORD_BYTES
            or record_end > len(payload)
            or record_end <= separator + 2
            or payload[record_end - 1 : record_end] != b"\n"
        ):
            raise ValueError("OCI TAR PAX record is invalid")
        body = payload[separator + 1 : record_end - 1]
        equals = body.find(b"=")
        if equals <= 0:
            raise ValueError("OCI TAR PAX record is invalid")
        key_bytes = body[:equals]
        value_bytes = body[equals + 1 :]
        try:
            key = key_bytes.decode("ascii")
            value = value_bytes.decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            raise ValueError("OCI TAR PAX encoding is invalid") from None
        if key not in {"path", "linkpath", "size"} or key in records:
            raise ValueError("OCI TAR PAX key is invalid or ambiguous")
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("OCI TAR PAX value is invalid")
        if key == "path":
            records[key] = _normalize_entry_path(value)
        elif key == "linkpath":
            records[key] = _validate_link_target(value)
        else:
            records[key] = _parse_pax_size(value)
        offset = record_end
    if not records:
        raise ValueError("OCI TAR PAX payload is empty")
    return records


def _parse_gnu_payload(payload: bytes, *, link: bool) -> str:
    if not payload or payload[-1:] != b"\0" or b"\0" in payload[:-1]:
        raise ValueError("OCI TAR GNU metadata is invalid")
    raw = payload[:-1]
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("OCI TAR GNU encoding is invalid") from None
    return _validate_link_target(value) if link else _normalize_entry_path(value)


class _TarParser:
    def __init__(self, max_entries: int) -> None:
        self.buffer = bytearray()
        self.entries: list[LayaOciTarEntry] = []
        self.paths: set[str] = set()
        self.max_entries = max_entries
        self.chunk_count = 0
        self.total_bytes = 0
        self.payload_size = 0
        self.payload_remaining = 0
        self.padding_remaining = 0
        self.zero_blocks = 0
        self.terminated = False
        self.header_count = 0
        self.pax_bytes = 0
        self.current_extension: str | None = None
        self.extension_payload = bytearray()
        self.global_pax: dict[str, str | int] = {}
        self.local_pax: dict[str, str | int] = {}
        self.gnu_longname: str | None = None
        self.gnu_longlink: str | None = None
        self.global_metadata_pending = False

    def feed(self, chunk: bytes) -> None:
        self.chunk_count += 1
        if (
            type(chunk) is not bytes
            or not chunk
            or len(chunk) > MAX_OCI_TAR_CHUNK_BYTES
            or self.chunk_count > MAX_OCI_TAR_CHUNKS
        ):
            raise ValueError("OCI TAR chunk limit is invalid")
        self.total_bytes += len(chunk)
        if self.total_bytes > MAX_OCI_TAR_BYTES:
            raise ValueError("OCI TAR aggregate byte limit is invalid")
        self.buffer.extend(chunk)
        self._advance()

    def _advance(self) -> None:
        while True:
            if self.payload_remaining:
                consumed = min(self.payload_remaining, len(self.buffer))
                if not consumed:
                    return
                if self.current_extension is not None:
                    self.extension_payload.extend(self.buffer[:consumed])
                del self.buffer[:consumed]
                self.payload_remaining -= consumed
                if not self.payload_remaining:
                    self._complete_payload()
                continue
            if self.padding_remaining:
                consumed = min(self.padding_remaining, len(self.buffer))
                if not consumed:
                    return
                if any(self.buffer[:consumed]):
                    raise ValueError("OCI TAR entry padding is invalid")
                del self.buffer[:consumed]
                self.padding_remaining -= consumed
                continue
            if len(self.buffer) < _BLOCK_BYTES:
                return
            header = bytes(self.buffer[:_BLOCK_BYTES])
            del self.buffer[:_BLOCK_BYTES]
            if header == _ZERO_BLOCK:
                self.zero_blocks += 1
                if self.zero_blocks >= 2:
                    self.terminated = True
                continue
            if self.terminated:
                raise ValueError("OCI TAR data after termination is invalid")
            if self.zero_blocks:
                raise ValueError("OCI TAR termination is invalid")
            self._accept_header(header)

    def _merge_pax(self, target: dict[str, str | int], payload: bytes) -> None:
        parsed = _parse_pax_payload(payload)
        if any(key in target for key in parsed):
            raise ValueError("OCI TAR PAX key is repeated ambiguously")
        target.update(parsed)

    def _complete_payload(self) -> None:
        extension = self.current_extension
        if extension is None:
            return
        payload = bytes(self.extension_payload)
        self.current_extension = None
        self.extension_payload.clear()
        if extension == "x":
            self._merge_pax(self.local_pax, payload)
        elif extension == "g":
            self._merge_pax(self.global_pax, payload)
            self.global_metadata_pending = True
        elif extension == "L":
            if self.gnu_longname is not None:
                raise ValueError("OCI TAR GNU longname is repeated ambiguously")
            self.gnu_longname = _parse_gnu_payload(payload, link=False)
        elif extension == "K":
            if self.gnu_longlink is not None:
                raise ValueError("OCI TAR GNU longlink is repeated ambiguously")
            self.gnu_longlink = _parse_gnu_payload(payload, link=True)
        else:
            raise AssertionError("unreachable")

    def _accept_header(self, header: bytes) -> None:
        _validate_header_checksum(header)
        profile_pair = (header[257:263], header[263:265])
        if profile_pair == (b"ustar\0", b"00"):
            profile = "posix"
        elif profile_pair == (b"ustar ", b" \0"):
            profile = "gnu"
            if any(header[345:500]):
                raise ValueError("OCI TAR GNU extended header fields are invalid")
        else:
            raise ValueError("OCI TAR header profile is invalid")
        for start, end in ((100, 108), (108, 116), (116, 124), (136, 148)):
            _parse_octal(header[start:end])
        header_size = _parse_octal(header[124:136])
        raw_typeflag = header[156:157]
        if raw_typeflag not in (b"\0", b"0", b"1", b"2", b"5", b"g", b"x", b"L", b"K"):
            raise ValueError("OCI TAR entry type is invalid")
        typeflag = "0" if raw_typeflag == b"\0" else raw_typeflag.decode("ascii")
        self.header_count += 1
        if self.header_count > self.max_entries:
            raise ValueError("OCI TAR entry limit is invalid")
        if typeflag in ("g", "x", "L", "K"):
            self._accept_extension(typeflag, header_size, profile)
            return

        if (
            profile == "gnu"
            and (self.local_pax or self.global_pax)
            or profile == "posix"
            and (self.gnu_longname is not None or self.gnu_longlink is not None)
        ):
            raise ValueError("OCI TAR metadata and target profile conflict")

        size_value = self.local_pax.get("size", self.global_pax.get("size", header_size))
        if type(size_value) is not int:
            raise ValueError("OCI TAR effective size is invalid")
        size = size_value
        if (
            size > MAX_OCI_TAR_ENTRY_PAYLOAD_BYTES
            or size > MAX_OCI_TAR_PAYLOAD_BYTES - self.payload_size
        ):
            raise ValueError("OCI TAR payload limit is invalid")
        if typeflag in ("1", "2", "5") and size != 0:
            raise ValueError("OCI TAR metadata entry size is invalid")
        path_value = self.local_pax.get(
            "path",
            self.gnu_longname if self.gnu_longname is not None else self.global_pax.get("path"),
        )
        path = (
            _normalize_entry_path(path_value)
            if path_value is not None
            else _normalize_entry_path(_header_entry_path(header, profile))
        )
        if path in self.paths:
            raise ValueError("OCI TAR duplicate entry path is invalid")
        link_value = self.local_pax.get(
            "linkpath",
            self.gnu_longlink if self.gnu_longlink is not None else self.global_pax.get("linkpath"),
        )
        if typeflag in ("1", "2"):
            link_target = (
                _validate_link_target(link_value)
                if link_value is not None
                else _header_link_target(header)
            )
        else:
            if link_value is not None:
                raise ValueError("OCI TAR link metadata conflicts with entry type")
            link_target = None
        entry = LayaOciTarEntry(
            path=path,
            typeflag=typeflag,
            size_bytes=size,
            link_target=link_target,
            _factory_token=_FACTORY_TOKEN,
        )
        self.paths.add(path)
        self.entries.append(entry)
        self.payload_size += size
        self.payload_remaining = size
        self.padding_remaining = (-size) % _BLOCK_BYTES
        self.local_pax.clear()
        self.gnu_longname = None
        self.gnu_longlink = None
        self.global_metadata_pending = False

    def _accept_extension(self, typeflag: str, size: int, profile: str) -> None:
        if typeflag in ("g", "x"):
            if profile != "posix" or self.gnu_longname is not None or self.gnu_longlink is not None:
                raise ValueError("OCI TAR PAX header profile is invalid")
            if (
                size < 1
                or size > MAX_OCI_TAR_PAX_RECORD_BYTES
                or size > MAX_OCI_TAR_PAX_BYTES - self.pax_bytes
            ):
                raise ValueError("OCI TAR PAX record or aggregate limit is invalid")
            self.pax_bytes += size
        else:
            if profile != "gnu" or self.local_pax or self.global_pax:
                raise ValueError("OCI TAR GNU header profile is invalid")
            limit = MAX_OCI_TAR_LINK_BYTES if typeflag == "K" else MAX_OCI_TAR_PATH_BYTES
            if size < 2 or size > limit + 1:
                raise ValueError("OCI TAR GNU metadata limit is invalid")
        self.current_extension = typeflag
        self.extension_payload.clear()
        self.payload_remaining = size
        self.padding_remaining = (-size) % _BLOCK_BYTES
        if not size:
            self._complete_payload()

    def finish(self) -> tuple[tuple[LayaOciTarEntry, ...], int, int]:
        self._advance()
        if (
            self.buffer
            or self.payload_remaining
            or self.padding_remaining
            or not self.terminated
            or self.zero_blocks < 2
            or self.current_extension is not None
            or self.local_pax
            or self.gnu_longname is not None
            or self.gnu_longlink is not None
            or self.global_metadata_pending
        ):
            raise ValueError("OCI TAR stream is truncated or lacks termination")
        return tuple(self.entries), self.payload_size, self.total_bytes


def _authorize_plan_and_digest(
    plan: object,
    digest: object,
) -> tuple[LayaOciTarSemanticsPlan, int]:
    if type(plan) is not LayaOciTarSemanticsPlan:
        raise TypeError("OCI TAR plan must be an exact sealed value")
    plan.__post_init__(_FACTORY_TOKEN)
    if (
        type(digest) is not str
        or len(digest) != 71
        or not digest.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in digest[7:])
    ):
        raise ValueError("OCI TAR layer digest is invalid")
    positions = tuple(
        position
        for position, blob in enumerate(plan.layer_plan.layer_blobs)
        if blob.digest == digest
    )
    if len(positions) != 1:
        raise ValueError("OCI TAR layer digest is not authorized")
    return plan, positions[0]


def _prepare_laya_oci_tar_semantics_plan(layer_evidence: object) -> LayaOciTarSemanticsPlan:
    if type(layer_evidence) is not runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence:
        raise TypeError("OCI layer evidence must be an exact sealed value")
    return LayaOciTarSemanticsPlan(
        schema_version=OCI_TAR_SEMANTICS_PLAN_SCHEMA,
        layer_evidence=layer_evidence,
        layer_plan=layer_evidence.plan,
        layout_plan=layer_evidence.layout_plan,
        runtime_identity=layer_evidence.runtime_identity,
        layer_receipts=layer_evidence.receipts,
        _factory_token=_FACTORY_TOKEN,
    )


def prepare_laya_oci_tar_semantics_plan(
    layer_evidence: runtime_oci_layers.LayaRuntimeOciLayerDiffIdsEvidence,
) -> LayaOciTarSemanticsPlan:
    """Bind a conservative TAR plan to deeply validated PR22 evidence."""

    failed = False
    try:
        return _prepare_laya_oci_tar_semantics_plan(layer_evidence)
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI layer evidence validation failed")
    raise AssertionError("unreachable")


def verify_laya_oci_tar_semantics_chunks(
    plan: LayaOciTarSemanticsPlan,
    digest: str,
    compressed_chunks: object,
    *,
    max_entries: int = MAX_OCI_TAR_ENTRIES,
) -> VerifiedLayaOciTarLayer:
    """Verify PR22 bytes and DiffID while parsing their TAR output once."""

    if type(max_entries) is not int or not 1 <= max_entries <= MAX_OCI_TAR_ENTRIES:
        _raise_private(ValueError, "OCI TAR entry limit is invalid")
    failed = False
    try:
        authorized_plan, position = _authorize_plan_and_digest(plan, digest)
        parser = _TarParser(max_entries)
        layer_receipt = runtime_oci_layers._verify_laya_oci_layer_diff_id_chunks_with_consumer(
            authorized_plan.layer_plan,
            digest,
            compressed_chunks,
            parser.feed,
        )
        entries, payload_size, tar_size = parser.finish()
        return VerifiedLayaOciTarLayer(
            plan=authorized_plan,
            layer_receipt=layer_receipt,
            layer_position=position,
            entries=entries,
            payload_size_bytes=payload_size,
            tar_size_bytes=tar_size,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI TAR stream validation failed")
    raise AssertionError("unreachable")


def _verify_laya_oci_tar_semantics_chunks_with_budget(
    plan: object,
    digest: object,
    compressed_chunks: object,
    *,
    max_uncompressed_bytes: object,
) -> VerifiedLayaOciTarLayer:
    failed = False
    try:
        authorized_plan, position = _authorize_plan_and_digest(plan, digest)
        parser = _TarParser(MAX_OCI_TAR_ENTRIES)
        layer_receipt = runtime_oci_layers._verify_laya_oci_layer_diff_id_chunks_with_consumer(
            authorized_plan.layer_plan,
            digest,
            compressed_chunks,
            parser.feed,
            max_uncompressed_bytes=max_uncompressed_bytes,
        )
        entries, payload_size, tar_size = parser.finish()
        return VerifiedLayaOciTarLayer(
            plan=authorized_plan,
            layer_receipt=layer_receipt,
            layer_position=position,
            entries=entries,
            payload_size_bytes=payload_size,
            tar_size_bytes=tar_size,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI TAR bounded stream validation failed")
    raise AssertionError("unreachable")


def _seal_laya_oci_tar_semantics_capture_authority(
    plan: LayaOciTarSemanticsPlan,
    receipts: tuple[VerifiedLayaOciTarLayer, ...],
    *,
    controls_captured_from_same_root: bool,
    blobs_captured_from_same_root: bool,
    inventory_captured_from_same_root: bool,
    final_fd_sweep_verified: bool,
    descriptors_closed_before_seal: bool,
) -> _LayaOciTarSemanticsCaptureAuthority:
    failed = False
    try:
        return _LayaOciTarSemanticsCaptureAuthority(
            plan=plan,
            receipts=receipts,
            controls_captured_from_same_root=controls_captured_from_same_root,
            blobs_captured_from_same_root=blobs_captured_from_same_root,
            inventory_captured_from_same_root=inventory_captured_from_same_root,
            final_fd_sweep_verified=final_fd_sweep_verified,
            descriptors_closed_before_seal=descriptors_closed_before_seal,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI TAR capture authority sealing failed")
    raise AssertionError("unreachable")


def _seal_laya_runtime_oci_tar_semantics_evidence(
    authority: object,
) -> LayaRuntimeOciTarSemanticsEvidence:
    failed = False
    try:
        if type(authority) is not _LayaOciTarSemanticsCaptureAuthority:
            raise TypeError("OCI TAR evidence requires an exact capture authority")
        authority.__post_init__(_FACTORY_TOKEN)
        return LayaRuntimeOciTarSemanticsEvidence(
            schema_version=OCI_TAR_SEMANTICS_EVIDENCE_SCHEMA,
            plan=authority.plan,
            runtime_identity=authority.plan.runtime_identity,
            receipts=authority.receipts,
            _factory_token=_FACTORY_TOKEN,
        )
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI TAR evidence sealing failed")
    raise AssertionError("unreachable")


def _validate_tar_evidence(evidence: object) -> LayaRuntimeOciTarSemanticsEvidence:
    if type(evidence) is not LayaRuntimeOciTarSemanticsEvidence:
        raise TypeError("OCI TAR evidence must be an exact sealed value")
    evidence.__post_init__(_FACTORY_TOKEN)
    return evidence


def canonical_laya_runtime_oci_tar_semantics_summary_bytes(
    evidence: LayaRuntimeOciTarSemanticsEvidence,
) -> bytes:
    """Return the canonical privacy-safe summary of sealed TAR evidence."""

    failed = False
    try:
        validated = _validate_tar_evidence(evidence)
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI TAR evidence validation failed")
    payload = {
        "schema_version": validated.schema_version,
        "plan_schema_version": validated.plan.schema_version,
        "runtime_identity_sha256": validated.runtime_identity.sha256,
        **dict(
            zip(
                _INHERITED_CLAIMS,
                _tar_claim_values(validated),
                strict=True,
            )
        ),
    }
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
