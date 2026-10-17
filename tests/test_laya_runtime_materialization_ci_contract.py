import shlex
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"
JOB_NAME = "laya-runtime-materialization-contract"
PREDECESSOR_JOB = "laya-rootfs-materialization-contract"
UNIT_TESTS = (
    "tests/test_laya_runtime_materialization.py",
    "tests/test_laya_runtime_materialization_lease.py",
    "tests/test_laya_runtime_installation_archive.py",
    "tests/test_laya_runtime_installation_verifier.py",
    "tests/test_laya_docker_runtime_materialization.py",
    "tests/test_laya_local_docker_engine.py",
)
LIVE_TEST = "tests/test_laya_local_docker_engine_live.py"


def _job() -> dict[str, object]:
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert type(loaded) is dict
    jobs = loaded.get("jobs")
    assert type(jobs) is dict
    job = jobs.get(JOB_NAME)
    assert type(job) is dict, f"CI must define the dedicated {JOB_NAME!r} job"
    return job


def _steps() -> tuple[dict[str, object], ...]:
    steps = _job().get("steps")
    assert type(steps) is list and steps
    assert all(type(step) is dict for step in steps)
    return tuple(steps)


def _tokens(step: dict[str, object]) -> tuple[str, ...]:
    command = step.get("run")
    if type(command) is not str:
        return ()
    return tuple(shlex.split(" ".join(command.split()), posix=True))


def test_materialization_job_is_bounded_nonroot_linux_after_rootfs_gate():
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
    assert job.get("timeout-minutes") == 20
    assert job.get("permissions") == {"contents": "read"}


def test_materialization_job_has_exact_setup_and_explicit_nonroot_precondition():
    checkout, setup_python, install, nonroot, unit, live = _steps()
    assert checkout == {"uses": "actions/checkout@v4"}
    assert setup_python == {
        "uses": "actions/setup-python@v5",
        "with": {"python-version": "3.11"},
    }
    assert set(install) == {"name", "run"}
    assert _tokens(install) == ("pip", "install", "-e", ".[dev]")
    assert set(nonroot) == {"name", "run"}
    assert _tokens(nonroot) == (
        "python",
        "-c",
        "import os; assert os.geteuid() != 0",
    )
    assert type(unit.get("name")) is str and unit["name"]
    assert type(live.get("name")) is str and live["name"]


def test_materialization_job_runs_exact_unit_and_synthetic_live_slices():
    pytest_steps = [step for step in _steps() if _tokens(step)[:3] == ("python", "-m", "pytest")]
    assert len(pytest_steps) == 2
    unit, live = pytest_steps
    assert _tokens(unit)[3:] == UNIT_TESTS
    assert set(unit) == {"name", "run"}
    assert _tokens(live)[3:] == (LIVE_TEST,)
    assert live.get("env") == {"LAYA_LOCAL_DOCKER_LIVE": "1"}
    assert set(live) == {"name", "run", "env"}


def test_materialization_job_uses_only_local_synthetic_engine_authority():
    forbidden_tokens = {"--runxfail", "-k", "curl", "wget", "podman", "skopeo"}
    forbidden_fragments = {
        "http://",
        "https://",
        "laya_runtime_oci_layout_root",
        "laya_runtime_checkpoint_source_root",
        "laya_runtime_materialization_live",
        "tests/fixtures/laya",
    }
    for step in _steps():
        for forbidden in ("continue-on-error", "if", "environment"):
            assert forbidden not in step
        env = step.get("env")
        assert env is None or env == {"LAYA_LOCAL_DOCKER_LIVE": "1"}
        tokens = _tokens(step)
        assert forbidden_tokens.isdisjoint(token.lower() for token in tokens)
        command = step.get("run")
        if type(command) is str:
            rendered = command.lower()
            assert not any(fragment in rendered for fragment in forbidden_fragments)

