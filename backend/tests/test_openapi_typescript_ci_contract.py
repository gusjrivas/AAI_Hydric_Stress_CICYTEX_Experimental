from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

import openapi_typescript_exporter as exporter

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = ROOT / "frontend"
GENERATED_ROOT = FRONTEND_ROOT / "src" / "api" / "generated"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
GENERATED_ARTIFACTS = {
    "manifest.json": (348, "9d56bf7c48d6a3fec1414f229b9e96e2322263acf72ce7f1f36004f1ef9f982f"),
    "openapi.json": (71_662, "655e94125c304ab34f2ebf8745bb56c56e4fdadb1bd5a13dee0630d79f61f96e"),
    "schema.d.ts": (103_403, "c744277eec28db4314d3210dfc28b8024f7ee0c194fdc5bcae772774c4bf0bac"),
}
RAW_TO_TRACKED = {
    "openapi.json": "openapi.json",
    "openapi.ts": "schema.d.ts",
    "openapi-manifest.json": "manifest.json",
}
EXPECTED_SCHEMA_CONSTRAINTS = (
    "annotated-types==0.8.0",
    "fastapi==0.141.1",
    "pydantic==2.13.4",
    "pydantic-core==2.46.4",
    "starlette==1.6.0",
    "typing-extensions==4.16.0",
    "typing-inspection==0.4.4",
)


def _bytes_by_name(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}


def _step_uses(step: dict) -> tuple[str, str]:
    return str(step.get("uses", "")), str(step.get("run", ""))


def test_real_generation_is_identical_in_space_containing_paths(tmp_path):
    first = tmp_path / "first generated artifacts with spaces"
    second = tmp_path / "second generated artifacts with spaces"

    exporter.generate_openapi_typescript_artifacts(first, frontend_root=FRONTEND_ROOT)
    exporter.generate_openapi_typescript_artifacts(second, frontend_root=FRONTEND_ROOT)

    assert _bytes_by_name(first) == _bytes_by_name(second)
    for raw_name, tracked_name in RAW_TO_TRACKED.items():
        generated = (first / raw_name).read_bytes()
        tracked = (GENERATED_ROOT / tracked_name).read_bytes()
        expected_size, expected_digest = GENERATED_ARTIFACTS[tracked_name]
        assert generated == tracked
        assert len(generated) == expected_size
        assert hashlib.sha256(generated).hexdigest() == expected_digest
        assert b"\r" not in generated
        assert generated.endswith(b"\n")


def test_generated_artifacts_have_exact_byte_preserving_checkout_rules():
    rules = {
        line.strip()
        for line in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {
        "/frontend/src/api/generated/manifest.json -text",
        "/frontend/src/api/generated/openapi.json -text",
        "/frontend/src/api/generated/schema.d.ts -text",
    } <= rules


def test_schema_constraints_are_the_exact_captured_python_environment():
    constraints = tuple(
        line.strip()
        for line in (ROOT / "backend" / "openapi-schema-constraints.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    assert constraints == EXPECTED_SCHEMA_CONSTRAINTS


def test_api_contract_ci_is_independent_and_runs_on_linux_and_windows():
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    job = workflow["jobs"]["api-contract"]

    assert "needs" not in job
    assert job["runs-on"] == "${{ matrix.os }}"
    assert job["strategy"]["matrix"]["os"] == ["ubuntu-latest", "windows-latest"]

    steps = job["steps"]
    uses_and_runs = [_step_uses(step) for step in steps]
    setup_python = next(step for step in steps if step.get("uses") == "actions/setup-python@v5")
    setup_node = next(step for step in steps if step.get("uses") == "actions/setup-node@v4")
    assert str(setup_python["with"]["python-version"]) == "3.11"
    assert str(setup_node["with"]["node-version"]) == "22"
    assert any(uses == "actions/checkout@v4" for uses, _ in uses_and_runs)

    commands = [run for _, run in uses_and_runs if run]
    command_text = "\n".join(commands)
    required_in_order = (
        "backend/openapi-schema-constraints.txt",
        "npm ci",
        "test_openapi_typescript_foundation.py",
        "test_openapi_typescript_composition.py",
        "test_openapi_typescript_ci_contract.py",
        "npm run test:api-toolchain",
        "npm run api:check",
    )
    positions = [command_text.index(marker) for marker in required_in_order]
    assert positions == sorted(positions)
    constraint_install = next(
        command for command in commands if "backend/openapi-schema-constraints.txt" in command
    )
    assert "pip install" in constraint_install
    assert "-c backend/openapi-schema-constraints.txt" in constraint_install
    assert '-e ".[dev,backend]"' in command_text or "-e '.[dev,backend]'" in command_text
    assert all(
        forbidden not in command_text.lower()
        for forbidden in ("npx", "http://", "https://", "uvicorn")
    )


def test_generated_schema_remains_foundation_only_and_has_no_product_importers():
    assert set(_bytes_by_name(GENERATED_ROOT)) == set(GENERATED_ARTIFACTS)
    offenders = []
    for path in (FRONTEND_ROOT / "src").rglob("*.ts*"):
        if GENERATED_ROOT in path.parents or path.name.endswith((".test.ts", ".test.tsx")):
            continue
        source = path.read_text(encoding="utf-8")
        if "api/generated" in source or "generated/schema" in source:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
    assert not any("client" in path.name.lower() for path in GENERATED_ROOT.iterdir())


def test_frontend_build_does_not_drop_test_sources_from_typecheck_coverage():
    source = (FRONTEND_ROOT / "tsconfig.app.json").read_text(encoding="utf-8")
    without_block_comments = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    config = json.loads(without_block_comments)

    assert config["include"] == ["src"]
    excluded = config.get("exclude", [])
    assert all("test" not in pattern.lower() for pattern in excluded)
    assert all("spec" not in pattern.lower() for pattern in excluded)
