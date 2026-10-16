import shlex
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"
JOB_NAME = "laya-runtime-provenance-contract"
CHECKPOINT_JOB_NAME = "laya-checkpoint-bytes-contract"
FOCAL_TESTS = ("tests/test_laya_runtime_provenance.py",)


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


def test_provenance_contract_job_has_exact_linux_dependency_and_python_runtime():
    job = _job()
    assert job.get("needs") == CHECKPOINT_JOB_NAME
    assert job.get("runs-on") == "ubuntu-latest"
    assert "strategy" not in job
    assert "continue-on-error" not in job
    assert "environment" not in job
    assert "env" not in job

    setup_python = [
        step
        for step in _steps(job)
        if type(step.get("uses")) is str and step["uses"].startswith("actions/setup-python@")
    ]
    assert len(setup_python) == 1
    assert setup_python[0].get("uses") == "actions/setup-python@v5"
    assert setup_python[0].get("with") == {"python-version": "3.11"}


def test_provenance_contract_job_installs_only_the_declared_editable_dev_profile():
    commands = [_run_tokens(step) for step in _steps(_job())]
    install_commands = [
        command
        for command in commands
        if command[:2] in (("pip", "install"), ("python", "-m")) and "install" in command
    ]
    assert install_commands == [("pip", "install", "-e", ".[dev]")]


def test_provenance_contract_job_runs_only_the_focal_offline_test_file():
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


def test_provenance_contract_job_cannot_enable_external_or_hidden_execution_paths():
    job = _job()
    for step in _steps(job):
        assert "continue-on-error" not in step
        assert "if" not in step
        assert "env" not in step
        assert "environment" not in step
        tokens = _run_tokens(step)
        assert "--runxfail" not in tokens
        assert "-k" not in tokens
        assert "tests/test_laya_runtime_provenance_real.py" not in tokens
        assert all("checkpoint" not in token.lower() for token in tokens)
        command = step.get("run")
        if type(command) is str:
            assert "LAYA_RUNTIME_PROVENANCE_REAL" not in command
