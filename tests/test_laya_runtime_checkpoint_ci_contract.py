from pathlib import Path

import yaml


def test_checkpoint_bytes_have_a_cross_platform_focal_ci_job():
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["laya-checkpoint-bytes-contract"]
    assert job["runs-on"] == "${{ matrix.os }}"
    assert job["strategy"]["matrix"]["os"] == ["ubuntu-latest", "windows-latest"]
    assert job.get("continue-on-error") is None
    steps = job["steps"]
    python_step = next(step for step in steps if step.get("uses") == "actions/setup-python@v5")
    assert python_step["with"]["python-version"] == "3.11"
    commands = [step.get("run", "") for step in steps]
    assert 'pip install -e ".[dev]"' in commands
    pytest_command = next(command for command in commands if "pytest" in command)
    assert pytest_command.split() == [
        "python",
        "-m",
        "pytest",
        "tests/test_laya_runtime_checkpoint.py",
        "tests/test_laya_runtime_checkpoint_filesystem.py",
    ]
    assert "LAYA_RUNTIME_CHECKPOINT_ROOT" not in str(job)
    assert all("continue-on-error" not in step for step in steps)
