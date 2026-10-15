from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
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


def test_contract_test_has_one_node_ready_ci_owner_without_skip_paths():
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    backend_job = workflow["jobs"]["backend-quality"]
    api_job = workflow["jobs"]["api-contract"]
    backend_contract_test = "tests/test_openapi_typescript_ci_contract.py"
    root_contract_test = "backend/tests/test_openapi_typescript_ci_contract.py"

    backend_test_step = next(
        step for step in backend_job["steps"] if "python -m pytest" in str(step.get("run", ""))
    )
    backend_command = str(backend_test_step["run"])
    backend_arguments = shlex.split(backend_command)
    ignore_arguments = tuple(
        argument for argument in backend_arguments if argument.startswith("--ignore")
    )
    assert "tests/" in backend_arguments
    assert ignore_arguments == (f"--ignore={backend_contract_test}",)

    api_steps = api_job["steps"]
    npm_ci_index = next(
        index for index, step in enumerate(api_steps) if str(step.get("run", "")) == "npm ci"
    )
    contract_step_index = next(
        index
        for index, step in enumerate(api_steps)
        if root_contract_test in str(step.get("run", ""))
    )
    contract_step = api_steps[contract_step_index]
    contract_command = str(contract_step["run"])
    contract_arguments = shlex.split(contract_command)
    pytest_arguments = contract_arguments[contract_arguments.index("pytest") + 1 :]

    assert npm_ci_index < contract_step_index
    assert pytest_arguments.count(root_contract_test) == 1
    assert backend_contract_test not in pytest_arguments
    assert "continue-on-error" not in api_job
    assert "if" not in api_job
    for step in api_steps:
        assert "continue-on-error" not in step
        assert "if" not in step
    assert not any(
        argument in {"--runxfail", "-k", "-m"} or argument.startswith(("--ignore", "--deselect"))
        for argument in pytest_arguments
    )

    test_tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    forbidden_marks = {
        node.attr
        for node in ast.walk(test_tree)
        if isinstance(node, ast.Attribute)
        and node.attr in {"skip", "skipif", "xfail"}
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    }
    assert forbidden_marks == set()


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
