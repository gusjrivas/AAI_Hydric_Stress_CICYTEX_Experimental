"""Pure, deterministic contracts for the local OpenAPI TypeScript toolchain."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

_HTTP_METHODS = frozenset({"delete", "get", "head", "options", "patch", "post", "put", "trace"})
_MANIFEST_SCHEMA = "openapi-typescript-artifacts-v1"
_GENERATOR_NAME = "openapi-typescript"


class OpenApiOperationIdError(ValueError):
    """Raised when the OpenAPI operationId inventory is incomplete or ambiguous."""

    def __init__(self, diagnostics: tuple[str, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__("; ".join(diagnostics))


class OpenApiArtifactIntegrityError(ValueError):
    """Raised when artifact bytes do not match their frozen manifest."""


class TypeScriptAnyKeywordError(ValueError):
    """Raised when a TypeScript AST contains an actual AnyKeyword node."""


@dataclass(frozen=True, slots=True)
class OpenApiTypeScriptManifest:
    """Content-addressed metadata for one OpenAPI and TypeScript artifact pair."""

    schema_version: str
    generator_name: str
    generator_version: str
    openapi_sha256: str
    openapi_size_bytes: int
    typescript_sha256: str
    typescript_size_bytes: int

    def __post_init__(self) -> None:
        if self.schema_version != _MANIFEST_SCHEMA:
            raise ValueError("unsupported artifact manifest schema")
        if self.generator_name != _GENERATOR_NAME:
            raise ValueError("unsupported artifact generator")
        if not isinstance(self.generator_version, str) or not self.generator_version:
            raise ValueError("invalid artifact generator version")
        _validate_digest(self.openapi_sha256)
        _validate_digest(self.typescript_sha256)
        _validate_size(self.openapi_size_bytes)
        _validate_size(self.typescript_size_bytes)


def canonical_openapi_json_bytes(document: dict[str, Any]) -> bytes:
    """Return the canonical UTF-8/LF representation of an OpenAPI document."""

    if type(document) is not dict:
        raise TypeError("OpenAPI document must be a JSON object")
    try:
        canonical = json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError):
        raise ValueError("OpenAPI document is not canonical JSON data") from None
    return canonical.encode("utf-8") + b"\n"


def validate_openapi_operation_ids(document: dict[str, Any]) -> tuple[str, ...]:
    """Validate and return the deterministic operationId inventory."""

    if type(document) is not dict:
        raise TypeError("OpenAPI document must be a JSON object")
    paths = document.get("paths")
    if type(paths) is not dict:
        raise ValueError("OpenAPI paths must be a JSON object")

    diagnostics: list[str] = []
    locations_by_id: dict[str, list[str]] = {}
    for path in sorted(paths):
        if type(path) is not str:
            raise ValueError("OpenAPI path keys must be strings")
        path_item = paths[path]
        if type(path_item) is not dict:
            raise ValueError("OpenAPI path items must be JSON objects")
        for method in sorted(_HTTP_METHODS):
            if method not in path_item:
                continue
            operation = path_item[method]
            if type(operation) is not dict:
                raise ValueError("OpenAPI operations must be JSON objects")
            location = f"{method.upper()} {path}"
            if "operationId" not in operation:
                diagnostics.append(f"missing operationId: {location}")
                continue
            operation_id = operation["operationId"]
            if type(operation_id) is not str:
                diagnostics.append(f"blank operationId: {location}")
                continue
            if not operation_id.strip():
                diagnostics.append(f"blank operationId: {location}")
                continue
            locations_by_id.setdefault(operation_id, []).append(location)

    for operation_id, locations in locations_by_id.items():
        if len(locations) > 1:
            diagnostics.append(
                f"duplicate operationId {operation_id!r}: {', '.join(sorted(locations))}"
            )
    if diagnostics:
        raise OpenApiOperationIdError(tuple(sorted(diagnostics)))
    return tuple(sorted(locations_by_id))


def build_openapi_typescript_manifest(
    openapi_bytes: bytes,
    typescript_bytes: bytes,
    *,
    generator_version: str,
) -> OpenApiTypeScriptManifest:
    """Build immutable content-addressed metadata for generated artifacts."""

    _require_bytes(openapi_bytes, "OpenAPI artifact")
    _require_bytes(typescript_bytes, "TypeScript artifact")
    return OpenApiTypeScriptManifest(
        schema_version=_MANIFEST_SCHEMA,
        generator_name=_GENERATOR_NAME,
        generator_version=generator_version,
        openapi_sha256=hashlib.sha256(openapi_bytes).hexdigest(),
        openapi_size_bytes=len(openapi_bytes),
        typescript_sha256=hashlib.sha256(typescript_bytes).hexdigest(),
        typescript_size_bytes=len(typescript_bytes),
    )


def verify_openapi_typescript_manifest(
    manifest: OpenApiTypeScriptManifest,
    openapi_bytes: bytes,
    typescript_bytes: bytes,
) -> None:
    """Fail closed unless both artifacts exactly match their manifest."""

    if type(manifest) is not OpenApiTypeScriptManifest:
        raise OpenApiArtifactIntegrityError("invalid artifact manifest")
    _require_bytes(openapi_bytes, "OpenAPI artifact")
    _require_bytes(typescript_bytes, "TypeScript artifact")
    if (
        len(openapi_bytes) != manifest.openapi_size_bytes
        or hashlib.sha256(openapi_bytes).hexdigest() != manifest.openapi_sha256
        or len(typescript_bytes) != manifest.typescript_size_bytes
        or hashlib.sha256(typescript_bytes).hexdigest() != manifest.typescript_sha256
    ):
        raise OpenApiArtifactIntegrityError("artifact integrity verification failed")


def validate_typescript_ast_no_any(ast: dict[str, Any]) -> None:
    """Reject real AnyKeyword AST nodes without scanning source text."""

    if type(ast) is not dict:
        raise TypeError("TypeScript AST root must be a JSON object")
    active: set[int] = set()

    def visit(node: object) -> None:
        if type(node) is dict:
            node_id = id(node)
            if node_id in active:
                raise ValueError("TypeScript AST contains a cycle")
            if node.get("kind") == "AnyKeyword":  # type: ignore[union-attr]
                raise TypeScriptAnyKeywordError("TypeScript AST contains an AnyKeyword node")
            active.add(node_id)
            try:
                for value in node.values():  # type: ignore[union-attr]
                    visit(value)
            finally:
                active.remove(node_id)
        elif type(node) is list:
            node_id = id(node)
            if node_id in active:
                raise ValueError("TypeScript AST contains a cycle")
            active.add(node_id)
            try:
                for value in node:  # type: ignore[union-attr]
                    visit(value)
            finally:
                active.remove(node_id)

    visit(ast)


def _require_bytes(value: object, label: str) -> None:
    if type(value) is not bytes:
        raise TypeError(f"{label} must be bytes")


def _validate_digest(value: object) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("invalid artifact digest")


def _validate_size(value: object) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("invalid artifact size")
