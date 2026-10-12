import json
import runpy
import socket
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "laya" / "readiness_contract_v1.json"
SCRIPT = Path(__file__).parents[1] / "scripts" / "check_laya_readiness.py"


def test_cli_is_offline_and_reports_characterization_without_enabling_laya(monkeypatch, capsys):
    def block_network(*args, **kwargs):
        raise AssertionError("offline readiness must never open a socket")

    monkeypatch.setattr(socket, "create_connection", block_network)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "--contract", str(FIXTURE), "--use-perfect-fixture-predictions"],
    )

    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit as error:
        assert error.code == 0

    report = json.loads(capsys.readouterr().out)
    assert report["decision"] == "CHARACTERIZATION_ONLY"
    assert report["production_enablement_authorized"] is False


def test_cli_require_shadow_eligibility_fails_for_synthetic_evidence(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--contract",
            str(FIXTURE),
            "--use-perfect-fixture-predictions",
            "--require-shadow-eligible",
        ],
    )

    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit as error:
        assert error.code == 1
    else:
        raise AssertionError("synthetic evidence must not satisfy the readiness gate")

    report = json.loads(capsys.readouterr().out)
    assert report["decision"] == "CHARACTERIZATION_ONLY"
