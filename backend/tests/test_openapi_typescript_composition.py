from __future__ import annotations

import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
from types import ModuleType

import pytest
from app.main import app

from openapi_typescript_toolchain import (
    canonical_openapi_json_bytes,
    validate_openapi_operation_ids,
)

ROOT = Path(__file__).resolve().parents[2]
EXPORTER_PATH = ROOT / "src" / "openapi_typescript_exporter.py"
ARTIFACT_NAMES = ("openapi.json", "openapi.ts", "openapi-manifest.json")
EXPECTED_OPENAPI_SIZE = 76_608
EXPECTED_OPENAPI_SHA256 = "e5022ffb12376dfbc4f64bd6f66a0f55670281de997fc80b611da78d76a9163f"
EXPECTED_OPERATION_COUNT = 36


def _exporter() -> ModuleType:
    return importlib.import_module("openapi_typescript_exporter")


def _artifact_bytes(directory: Path) -> dict[str, bytes]:
    return {name: (directory / name).read_bytes() for name in ARTIFACT_NAMES}


def _install_fake_local_generator(frontend_root: Path) -> None:
    frontend_root.mkdir(parents=True, exist_ok=True)
    (frontend_root / "package.json").write_text(
        json.dumps({"devDependencies": {"openapi-typescript": "7.9.1"}}),
        encoding="utf-8",
    )
    binary_dir = frontend_root / "node_modules" / ".bin"
    binary_dir.mkdir(parents=True)
    node_script = binary_dir / "openapi-typescript"
    node_script.write_text(
        "#!/usr/bin/env node\n"
        "const fs = require('fs');\n"
        "const input = process.argv[2];\n"
        "const output = process.argv[process.argv.indexOf('-o') + 1];\n"
        "const schema = JSON.parse(fs.readFileSync(input, 'utf8'));\n"
        "fs.writeFileSync(output, "
        "'// generated from ' + schema.info.title + '\\nexport interface paths {}\\n');\n",
        encoding="utf-8",
    )
    node_script.chmod(0o755)
    (binary_dir / "openapi-typescript.cmd").write_text(
        '@node "%~dp0\\openapi-typescript" %*\r\n', encoding="utf-8"
    )


def test_real_application_openapi_has_frozen_canonical_identity_and_operation_ids():
    document = app.openapi()
    openapi_bytes = canonical_openapi_json_bytes(document)
    operation_ids = validate_openapi_operation_ids(document)

    assert len(openapi_bytes) == EXPECTED_OPENAPI_SIZE
    assert hashlib.sha256(openapi_bytes).hexdigest() == EXPECTED_OPENAPI_SHA256
    assert len(operation_ids) == EXPECTED_OPERATION_COUNT
    assert len(operation_ids) == len(set(operation_ids))
    assert all(operation_id.strip() == operation_id for operation_id in operation_ids)


def test_generate_is_byte_deterministic_and_uses_only_local_binary(tmp_path):
    exporter = _exporter()
    frontend_root = tmp_path / "frontend"
    _install_fake_local_generator(frontend_root)
    first = tmp_path / "first"
    second = tmp_path / "second"

    exporter.generate_openapi_typescript_artifacts(first, frontend_root=frontend_root)
    exporter.generate_openapi_typescript_artifacts(second, frontend_root=frontend_root)

    assert _artifact_bytes(first) == _artifact_bytes(second)
    manifest = json.loads((first / "openapi-manifest.json").read_bytes())
    assert manifest["schema_version"] == "openapi-typescript-artifacts-v1"
    assert manifest["generator_name"] == "openapi-typescript"
    assert manifest["openapi_size_bytes"] == len((first / "openapi.json").read_bytes())
    assert (
        manifest["openapi_sha256"]
        == hashlib.sha256((first / "openapi.json").read_bytes()).hexdigest()
    )
    assert manifest["typescript_size_bytes"] == len((first / "openapi.ts").read_bytes())
    assert (
        manifest["typescript_sha256"]
        == hashlib.sha256((first / "openapi.ts").read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("artifact_name", ARTIFACT_NAMES)
def test_check_detects_each_artifact_drift_without_rewriting_tracked_bytes(tmp_path, artifact_name):
    exporter = _exporter()
    frontend_root = tmp_path / "frontend"
    _install_fake_local_generator(frontend_root)
    tracked = tmp_path / "tracked"
    exporter.generate_openapi_typescript_artifacts(tracked, frontend_root=frontend_root)
    path = tracked / artifact_name
    path.write_bytes(path.read_bytes() + b" ")
    before = _artifact_bytes(tracked)

    with pytest.raises(exporter.OpenApiArtifactDriftError):
        exporter.check_openapi_typescript_artifacts(tracked, frontend_root=frontend_root)

    assert _artifact_bytes(tracked) == before


def test_clean_check_is_read_only(tmp_path):
    exporter = _exporter()
    frontend_root = tmp_path / "frontend"
    _install_fake_local_generator(frontend_root)
    tracked = tmp_path / "tracked"
    exporter.generate_openapi_typescript_artifacts(tracked, frontend_root=frontend_root)
    before = _artifact_bytes(tracked)

    assert exporter.check_openapi_typescript_artifacts(tracked, frontend_root=frontend_root) is None
    assert _artifact_bytes(tracked) == before


def test_locked_typescript_version_satisfies_openapi_typescript_peer_without_overrides():
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    root_typescript = package["devDependencies"]["typescript"]
    resolved_typescript = lock["packages"]["node_modules/typescript"]["version"]
    peer = lock["packages"]["node_modules/openapi-typescript"]["peerDependencies"]["typescript"]

    assert peer == "^5.x"
    assert resolved_typescript.split(".", 1)[0] == "5"
    assert root_typescript == resolved_typescript
    assert "legacy-peer-deps" not in package.get("scripts", {}).get("prepare", "")


def _imports(tree: ast.AST) -> set[str]:
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_exporter_composes_in_process_app_and_local_generator_without_network():
    assert EXPORTER_PATH.is_file()
    source = EXPORTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = _imports(tree)
    assert "app.main" in imports
    assert not {
        "fastapi",
        "httpx",
        "requests",
        "socket",
        "urllib",
        "uvicorn",
    } & {name.split(".", 1)[0] for name in imports}
    literals = {
        node.value.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any(
        marker in literal
        for literal in literals
        for marker in ("http://", "https://", "npx", "uvicorn", "legacy-peer-deps")
    )
    assert "node_modules" in source
    assert ".bin" in source


def test_exporter_does_not_mutate_process_environment_or_start_a_server(tmp_path):
    exporter = _exporter()
    frontend_root = tmp_path / "frontend"
    _install_fake_local_generator(frontend_root)
    before = dict(os.environ)
    exporter.generate_openapi_typescript_artifacts(
        tmp_path / "artifacts", frontend_root=frontend_root
    )
    assert dict(os.environ) == before
