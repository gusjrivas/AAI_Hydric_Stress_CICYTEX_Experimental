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

_BLOCK_BYTES = 512
_MAX_ENTRY_PAYLOAD_BYTES = 2 * 1_024 * 1_024 * 1_024
_MAX_PAYLOAD_BYTES = 3 * 1_024 * 1_024 * 1_024
_MAX_TAR_BYTES = _MAX_PAYLOAD_BYTES + (MAX_OCI_TAR_ENTRIES + 2) * _BLOCK_BYTES
_MAX_PATH_BYTES = 4_096
_MAX_LINK_BYTES = 4_096
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
            or not 0 <= self.size_bytes <= _MAX_ENTRY_PAYLOAD_BYTES
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
            or not 0 <= self.layer_receipt.uncompressed_size_bytes <= _MAX_ENTRY_PAYLOAD_BYTES
            or self.layer_receipt.uncompressed_size_bytes != historical.uncompressed_size_bytes
            or type(self.entries) is not tuple
            or len(self.entries) > MAX_OCI_TAR_ENTRIES
            or any(type(entry) is not LayaOciTarEntry for entry in self.entries)
            or type(self.payload_size_bytes) is not int
            or not 0 <= self.payload_size_bytes <= _MAX_PAYLOAD_BYTES
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
            if payload_size > _MAX_PAYLOAD_BYTES:
                raise ValueError("OCI TAR receipt payload size is invalid")
        if payload_size != self.payload_size_bytes:
            raise ValueError("OCI TAR receipt payload size is invalid")

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
        or len(value.encode("utf-8")) > _MAX_LINK_BYTES
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("OCI TAR link target is invalid")
    return value


def _normalize_entry_path(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8")) > _MAX_PATH_BYTES
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


def _normalized_entry_path(header: bytes) -> str:
    name = _decode_field(header[0:100], limit=100)
    prefix_field = header[345:500]
    prefix = _decode_field(prefix_field, limit=155) if any(prefix_field) else ""
    value = name if not prefix else prefix + "/" + name
    return _normalize_entry_path(value)


def _link_target(header: bytes, typeflag: str) -> str | None:
    if typeflag not in ("1", "2"):
        return None
    return _validate_link_target(_decode_field(header[157:257], limit=min(100, _MAX_LINK_BYTES)))


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
        if self.total_bytes > _MAX_TAR_BYTES:
            raise ValueError("OCI TAR aggregate byte limit is invalid")
        self.buffer.extend(chunk)
        self._advance()

    def _advance(self) -> None:
        while True:
            if self.payload_remaining:
                consumed = min(self.payload_remaining, len(self.buffer))
                if not consumed:
                    return
                del self.buffer[:consumed]
                self.payload_remaining -= consumed
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

    def _accept_header(self, header: bytes) -> None:
        _validate_header_checksum(header)
        if header[257:263] != b"ustar\0" or header[263:265] != b"00":
            raise ValueError("OCI TAR header profile is invalid")
        for start, end in ((100, 108), (108, 116), (116, 124), (136, 148)):
            _parse_octal(header[start:end])
        size = _parse_octal(header[124:136])
        if size > _MAX_ENTRY_PAYLOAD_BYTES or size > _MAX_PAYLOAD_BYTES - self.payload_size:
            raise ValueError("OCI TAR payload limit is invalid")
        raw_typeflag = header[156:157]
        if raw_typeflag not in (b"\0", b"0", b"1", b"2", b"5"):
            raise ValueError("OCI TAR entry type is invalid")
        typeflag = "0" if raw_typeflag == b"\0" else raw_typeflag.decode("ascii")
        if typeflag in ("1", "2", "5") and size != 0:
            raise ValueError("OCI TAR metadata entry size is invalid")
        path = _normalized_entry_path(header)
        if path in self.paths:
            raise ValueError("OCI TAR duplicate entry path is invalid")
        if len(self.entries) >= self.max_entries:
            raise ValueError("OCI TAR entry limit is invalid")
        entry = LayaOciTarEntry(
            path=path,
            typeflag=typeflag,
            size_bytes=size,
            link_target=_link_target(header, typeflag),
            _factory_token=_FACTORY_TOKEN,
        )
        self.paths.add(path)
        self.entries.append(entry)
        self.payload_size += size
        self.payload_remaining = size
        self.padding_remaining = (-size) % _BLOCK_BYTES

    def finish(self) -> tuple[tuple[LayaOciTarEntry, ...], int, int]:
        self._advance()
        if (
            self.buffer
            or self.payload_remaining
            or self.padding_remaining
            or not self.terminated
            or self.zero_blocks < 2
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
    except Exception:
        failed = True
    if failed:
        _raise_private(ValueError, "OCI TAR plan or layer digest validation failed")
    parser = _TarParser(max_entries)
    try:
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
