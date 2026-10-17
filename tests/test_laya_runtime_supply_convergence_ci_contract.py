import shlex
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"
JOB_NAME = "laya-runtime-supply-convergence-contract"
PREDECESSOR_JOBS = {
    "laya-runtime-base-ancestry-contract",
    "laya-runtime-provenance-contract",
}
FOCAL_TESTS = (
    "tests/test_laya_runtime_supply_convergence_contract.py",
    "tests/test_laya_runtime_supply_convergence_security.py",
    "tests/test_laya_runtime_supply_convergence_privacy.py",
)


def _workflow() -> dict[str, object]:
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert type(loaded) is dict
    return loaded


def _job() -> dict[str, object]:
    jobs = _workflow().get("jobs")
    assert type(jobs) is dict
    job = jobs.get(JOB_NAME)
    assert type(job) is dict, f"CI must define the dedicated {JOB_NAME!r} job"
    return job


def _steps(job: dict[str, object]) -> tuple[dict[str, object], ...]:
    steps = job.get("steps")
    assert type(steps) is list and steps
    assert all(type(step) is dict for step in steps)
    return tuple(steps)


def _run_tokens(step: dict[str, object]) -> tuple[str, ...]:
    command = step.get("run")
    if type(command) is not str:
        return ()
    return tuple(shlex.split(" ".join(command.split()), posix=True))


def test_supply_convergence_job_has_exact_predecessors_and_cross_platform_matrix():
    job = _job()
    assert set(job) == {
        "needs",
        "runs-on",
        "timeout-minutes",
        "permissions",
        "strategy",
        "steps",
    }
    needs = job.get("needs")
    assert type(needs) is list
    assert set(needs) == PREDECESSOR_JOBS
    assert len(needs) == len(PREDECESSOR_JOBS)
    assert job.get("runs-on") == "${{ matrix.os }}"
    assert job.get("strategy") == {
        "fail-fast": False,
        "matrix": {"os": ["ubuntu-latest", "windows-latest"]},
    }
    assert job.get("timeout-minutes") == 20


def test_supply_convergence_job_has_read_only_repository_authority():
    job = _job()
    assert job.get("permissions") == {"contents": "read"}


def test_supply_convergence_job_has_exact_setup_and_dependency_steps():
    steps = _steps(_job())
    assert len(steps) == 4
    checkout, setup_python, install, focal = steps
    assert checkout == {"uses": "actions/checkout@v4"}
    assert setup_python == {
        "uses": "actions/setup-python@v5",
        "with": {"python-version": "3.11"},
    }
    assert set(install) == {"name", "run"}
    assert type(install["name"]) is str and install["name"]
    assert _run_tokens(install) == ("pip", "install", "-e", ".[dev]")
    assert set(focal) == {"name", "run"}
    assert type(focal["name"]) is str and focal["name"]


def test_supply_convergence_job_runs_all_and_only_the_focal_test_files():
    commands = [_run_tokens(step) for step in _steps(_job())]
    pytest_commands = [
        command
        for command in commands
        if command[:3] == ("python", "-m", "pytest") or command[:1] == ("pytest",)
    ]
    assert len(pytest_commands) == 1
    command = pytest_commands[0]
    arguments = command[3:] if command[:3] == ("python", "-m", "pytest") else command[1:]
    assert arguments == FOCAL_TESTS


def test_supply_convergence_job_cannot_hide_failures_or_use_external_inputs():
    forbidden_tokens = {
        "--runxfail",
        "-k",
        "curl",
        "wget",
        "docker",
        "podman",
        "skopeo",
    }
    forbidden_fragments = {
        "http://",
        "https://",
        "laya_runtime_oci_layout_root",
        "laya_runtime_base_ancestry_root",
        "laya_runtime_provenance_real",
        "tests/fixtures/laya",
    }
    for step in _steps(_job()):
        for forbidden in ("continue-on-error", "if", "env", "environment"):
            assert forbidden not in step
        tokens = _run_tokens(step)
        assert forbidden_tokens.isdisjoint(token.lower() for token in tokens)
        command = step.get("run")
        if type(command) is str:
            rendered = command.lower()
            assert forbidden_fragments.isdisjoint(
                fragment for fragment in forbidden_fragments if fragment in rendered
            )
