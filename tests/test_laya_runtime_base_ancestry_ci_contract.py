import shlex
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"
JOB_NAME = "laya-runtime-base-ancestry-contract"
PREDECESSOR_JOB = "laya-oci-tar-contract"
FOCAL_TEST = "tests/test_laya_runtime_base_ancestry.py"


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


def test_base_ancestry_job_has_exact_predecessor_linux_and_conservative_authority():
    job = _job()
    assert set(job) == {
        "needs",
        "runs-on",
        "timeout-minutes",
        "permissions",
        "steps",
    }
    assert job.get("needs") == PREDECESSOR_JOB
    assert job.get("runs-on") == "ubuntu-latest"
    assert job.get("timeout-minutes") == 10
    assert job.get("permissions") == {"contents": "read"}


def test_base_ancestry_job_has_exact_checkout_python_and_dependency_steps():
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
    assert _run_tokens(focal) == ("python", "-m", "pytest", FOCAL_TEST)
    assert all("shell" not in step and "working-directory" not in step for step in steps)


def test_base_ancestry_job_runs_only_the_exact_focal_contract():
    commands = [_run_tokens(step) for step in _steps(_job())]
    pytest_commands = [
        command
        for command in commands
        if command[:3] == ("python", "-m", "pytest") or command[:1] == ("pytest",)
    ]
    assert pytest_commands == [("python", "-m", "pytest", FOCAL_TEST)]


def test_base_ancestry_job_is_offline_and_cannot_hide_failures():
    forbidden_tokens = {
        "--runxfail",
        "-k",
        "curl",
        "wget",
        "docker",
        "podman",
        "skopeo",
    }
    for step in _steps(_job()):
        for forbidden in ("continue-on-error", "if", "env", "environment"):
            assert forbidden not in step
        tokens = _run_tokens(step)
        assert forbidden_tokens.isdisjoint(token.lower() for token in tokens)
        command = step.get("run")
        if type(command) is str:
            rendered = command.lower()
            assert "http://" not in rendered
            assert "https://" not in rendered
            assert "laya_runtime_oci_layout_root" not in rendered
            assert "laya_runtime_base_ancestry_root" not in rendered
            assert "tests/fixtures/laya/runtime_base_ancestry" not in rendered
