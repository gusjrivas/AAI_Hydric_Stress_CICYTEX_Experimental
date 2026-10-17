import shlex
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"
JOB_NAME = "laya-rootfs-materialization-contract"
PREDECESSOR_JOB = "laya-runtime-supply-convergence-contract"
FOCAL_TESTS = (
    "tests/test_laya_runtime_rootfs_materialization.py",
    "tests/test_laya_runtime_rootfs_materialization_capture.py",
    "tests/test_laya_runtime_rootfs_materialization_filesystem.py",
    "tests/test_laya_runtime_rootfs_materialization_integration.py",
    "tests/test_laya_runtime_rootfs_materialization_linux.py",
    "tests/test_laya_runtime_rootfs_materialization_streaming.py",
    "tests/test_laya_runtime_oci_tar.py",
    "tests/test_laya_runtime_oci_layout_filesystem.py",
    "tests/test_laya_runtime_oci_rootfs.py",
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


def test_rootfs_materialization_job_is_bounded_linux_and_depends_on_supply_convergence():
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


def test_rootfs_materialization_job_has_exact_setup_nonroot_and_focal_steps():
    steps = _steps()
    assert len(steps) == 5
    checkout, setup_python, install, nonroot, focal = steps
    assert checkout == {"uses": "actions/checkout@v4"}
    assert setup_python == {
        "uses": "actions/setup-python@v5",
        "with": {"python-version": "3.11"},
    }
    assert _tokens(install) == ("pip", "install", "-e", ".[dev]")
    assert type(nonroot.get("name")) is str and nonroot["name"]
    assert _tokens(nonroot) == (
        "python",
        "-c",
        "import os; assert os.geteuid() != 0",
    )
    assert type(focal.get("name")) is str and focal["name"]


def test_rootfs_materialization_job_runs_all_and_only_required_regressions():
    pytest_commands = [
        tokens for step in _steps() if (tokens := _tokens(step))[:3] == ("python", "-m", "pytest")
    ]
    assert len(pytest_commands) == 1
    assert pytest_commands[0][3:] == FOCAL_TESTS


def test_rootfs_materialization_job_is_offline_and_cannot_hide_failures():
    forbidden_tokens = {
        "--runxfail",
        "-k",
        "curl",
        "wget",
        "docker",
        "podman",
        "skopeo",
    }
    forbidden_fragments = {"http://", "https://", "laya_runtime_oci_layout_root"}
    for step in _steps():
        for forbidden in ("continue-on-error", "if", "env", "environment"):
            assert forbidden not in step
        tokens = _tokens(step)
        assert forbidden_tokens.isdisjoint(token.lower() for token in tokens)
        command = step.get("run")
        if type(command) is str:
            rendered = command.lower()
            assert not any(fragment in rendered for fragment in forbidden_fragments)
