from __future__ import annotations

import ast
import hashlib
import importlib
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "openapi_typescript_toolchain.py"


def _toolchain() -> ModuleType:
    return importlib.import_module("openapi_typescript_toolchain")


def _operation_document(paths: dict) -> dict:
    return {"openapi": "3.1.0", "info": {"title": "test", "version": "1"}, "paths": paths}


def test_canonical_openapi_json_is_utf8_lf_and_preserves_array_order():
    module = _toolchain()
    first = {
        "paths": {"/z": {"get": {"tags": ["z", "a"], "summary": "estrés"}}},
        "info": {"version": "1", "title": "API"},
        "openapi": "3.1.0",
    }
    second = {
        "openapi": "3.1.0",
        "info": {"title": "API", "version": "1"},
        "paths": {"/z": {"get": {"summary": "estrés", "tags": ["z", "a"]}}},
    }

    expected = (
        '{"info":{"title":"API","version":"1"},"openapi":"3.1.0",'
        '"paths":{"/z":{"get":{"summary":"estrés","tags":["z","a"]}}}}\n'
    ).encode()
    assert module.canonical_openapi_json_bytes(first) == expected
    assert module.canonical_openapi_json_bytes(second) == expected
    assert b"\\u00e9" not in expected
    assert b"\r" not in expected


@pytest.mark.parametrize("invalid", [None, [], {"value": float("nan")}, {"value": float("inf")}])
def test_canonical_openapi_json_rejects_invalid_or_nonfinite_documents(invalid):
    module = _toolchain()
    with pytest.raises((TypeError, ValueError)):
        module.canonical_openapi_json_bytes(invalid)


def test_operation_id_diagnostics_are_complete_and_deterministic():
    module = _toolchain()
    document = _operation_document(
        {
            "/z": {"get": {"responses": {}}},
            "/c": {"post": {"operationId": "same", "responses": {}}},
            "/a": {"post": {"operationId": "  ", "responses": {}}},
            "/b": {"get": {"operationId": "same", "responses": {}}},
        }
    )
    expected = (
        "blank operationId: POST /a",
        "duplicate operationId 'same': GET /b, POST /c",
        "missing operationId: GET /z",
    )

    with pytest.raises(module.OpenApiOperationIdError) as first:
        module.validate_openapi_operation_ids(document)
    reordered = dict(reversed(list(document["paths"].items())))
    with pytest.raises(module.OpenApiOperationIdError) as second:
        module.validate_openapi_operation_ids(_operation_document(reordered))

    assert first.value.diagnostics == expected
    assert second.value.diagnostics == expected
    assert str(first.value) == str(second.value)


def test_operation_id_validation_returns_canonical_unique_inventory():
    module = _toolchain()
    document = _operation_document(
        {
            "/z": {"post": {"operationId": "zeta", "responses": {}}},
            "/a": {"get": {"operationId": "alpha", "responses": {}}},
        }
    )
    assert module.validate_openapi_operation_ids(document) == ("alpha", "zeta")


def test_artifact_manifest_binds_exact_openapi_and_typescript_bytes():
    module = _toolchain()
    openapi_bytes = b'{"openapi":"3.1.0"}\n'
    typescript_bytes = b"export interface paths {}\n"
    manifest = module.build_openapi_typescript_manifest(
        openapi_bytes,
        typescript_bytes,
        generator_version="7.9.1",
    )

    assert manifest.schema_version == "openapi-typescript-artifacts-v1"
    assert manifest.generator_name == "openapi-typescript"
    assert manifest.generator_version == "7.9.1"
    assert manifest.openapi_sha256 == hashlib.sha256(openapi_bytes).hexdigest()
    assert manifest.openapi_size_bytes == len(openapi_bytes)
    assert manifest.typescript_sha256 == hashlib.sha256(typescript_bytes).hexdigest()
    assert manifest.typescript_size_bytes == len(typescript_bytes)
    assert type(manifest).__slots__
    with pytest.raises(FrozenInstanceError):
        manifest.openapi_size_bytes = 0
    assert (
        module.verify_openapi_typescript_manifest(manifest, openapi_bytes, typescript_bytes) is None
    )

    mutations = (
        replace(manifest, openapi_sha256="f" * 64),
        replace(manifest, openapi_size_bytes=len(openapi_bytes) + 1),
        replace(manifest, typescript_sha256="e" * 64),
        replace(manifest, typescript_size_bytes=len(typescript_bytes) + 1),
    )
    for mutated in mutations:
        with pytest.raises(module.OpenApiArtifactIntegrityError):
            module.verify_openapi_typescript_manifest(mutated, openapi_bytes, typescript_bytes)

    with pytest.raises(module.OpenApiArtifactIntegrityError):
        module.verify_openapi_typescript_manifest(manifest, openapi_bytes + b" ", typescript_bytes)
    with pytest.raises(module.OpenApiArtifactIntegrityError):
        module.verify_openapi_typescript_manifest(manifest, openapi_bytes, typescript_bytes + b" ")


def test_typescript_ast_rejects_nested_any_keywords_but_not_text_mentions():
    module = _toolchain()
    safe_ast = {
        "kind": "SourceFile",
        "statements": [
            {
                "kind": "TypeAliasDeclaration",
                "name": "ContainsAnyText",
                "type": {"kind": "StringLiteral", "text": "any"},
                "leadingComments": ["any is forbidden only as a syntax node"],
            }
        ],
    }
    module.validate_typescript_ast_no_any(safe_ast)

    nested_any = {
        "kind": "SourceFile",
        "statements": [
            {
                "kind": "InterfaceDeclaration",
                "members": [
                    {
                        "kind": "PropertySignature",
                        "type": {
                            "kind": "ArrayType",
                            "elementType": {"kind": "AnyKeyword"},
                        },
                    }
                ],
            }
        ],
    }
    with pytest.raises(module.TypeScriptAnyKeywordError) as error:
        module.validate_typescript_ast_no_any(nested_any)
    assert "AnyKeyword" in str(error.value)


def test_openapi_typescript_is_exact_local_and_never_uses_npx_or_network():
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    version = package["devDependencies"]["openapi-typescript"]
    assert version and version[0].isdigit(), "openapi-typescript must use an exact version"
    assert lock["packages"][""]["devDependencies"]["openapi-typescript"] == version
    assert lock["packages"]["node_modules/openapi-typescript"]["version"] == version
    script = package["scripts"]["generate:openapi-types"]
    assert "openapi-typescript" in script
    assert "npx" not in script.lower()
    assert "http://" not in script.lower()
    assert "https://" not in script.lower()


def _imports(tree: ast.AST) -> set[str]:
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_toolchain_core_is_pure_offline_and_has_no_product_callers():
    assert MODULE_PATH.is_file()
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_import_roots = {
        "fastapi",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "uvicorn",
    }
    assert not {name for name in _imports(tree) if name.split(".", 1)[0] in forbidden_import_roots}
    literals = {
        node.value.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any(
        marker in literal
        for literal in literals
        for marker in ("http://", "https://", "npx", "uvicorn")
    )

    offenders = []
    for root in (ROOT / "backend" / "app", ROOT / "src"):
        for path in root.rglob("*.py"):
            if path == MODULE_PATH:
                continue
            candidate = ast.parse(path.read_text(encoding="utf-8"))
            if "openapi_typescript_toolchain" in _imports(candidate):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_generated_types_are_not_a_client_or_product_dependency():
    generated = ROOT / "frontend" / "src" / "generated"
    if generated.exists():
        assert {path.name for path in generated.iterdir() if path.is_file()} <= {
            "openapi.ts",
            "openapi-manifest.json",
        }
    offenders = []
    for path in (ROOT / "frontend" / "src").rglob("*.ts*"):
        if (
            generated in path.parents
            or path.name.endswith(".test.ts")
            or path.name.endswith(".test.tsx")
        ):
            continue
        source = path.read_text(encoding="utf-8")
        if "generated/openapi" in source or "generated\\openapi" in source:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
