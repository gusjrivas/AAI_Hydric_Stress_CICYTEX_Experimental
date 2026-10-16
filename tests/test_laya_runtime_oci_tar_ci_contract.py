import shlex
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"
JOB_NAME = "laya-oci-tar-contract"
FOCAL_TESTS = (
    "tests/test_laya_runtime_oci_tar.py",
    "tests/test_laya_runtime_oci_layers.py",
    "tests/test_laya_runtime_oci_layout_filesystem.py",
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


def test_tar_contract_job_has_exact_cross_platform_python_matrix():
    job = _job()
    assert job.get("runs-on") == "${{ matrix.os }}"
    strategy = job.get("strategy")
    assert type(strategy) is dict
    assert strategy.get("matrix") == {
        "os": ["ubuntu-latest", "windows-latest"],
    }
    assert "continue-on-error" not in job
    assert "environment" not in job

    setup_python = [
        step
        for step in _steps(job)
        if type(step.get("uses")) is str and step["uses"].startswith("actions/setup-python@")
    ]
    assert len(setup_python) == 1
    assert setup_python[0].get("with") == {"python-version": "3.11"}


def test_tar_contract_job_installs_only_the_declared_editable_dev_profile():
    commands = [_run_tokens(step) for step in _steps(_job())]
    assert commands.count(("pip", "install", "-e", ".[dev]")) == 1


def test_tar_contract_job_runs_the_exact_focal_pytest_files():
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


def test_tar_contract_job_cannot_hide_failures_or_enable_the_external_layout_gate():
    job = _job()
    assert "env" not in job
    for step in _steps(job):
        assert "continue-on-error" not in step
        assert "if" not in step
        assert "env" not in step
        command = step.get("run")
        if type(command) is str:
            assert "LAYA_RUNTIME_OCI_LAYOUT_ROOT" not in command
            assert "--runxfail" not in command
            assert "-k" not in _run_tokens(step)
