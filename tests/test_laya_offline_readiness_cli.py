import json
import runpy
import socket
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "laya" / "readiness_contract_v1.json"
SCRIPT = Path(__file__).parents[1] / "scripts" / "check_laya_readiness.py"


def _write_predictions(tmp_path: Path) -> Path:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    revision = raw["supply"]["checkpoint"]["revision"]
    categories = (
        "data_quality",
        "model_behavior",
        "agronomic_context",
        "usability",
        "other",
    )
    predictions = []
    for example in raw["corpus"]["examples"]:
        gold = example["gold_category"]
        predictions.append(
            {
                "example_id": example["example_id"],
                "category": gold,
                "probabilities": [
                    [category, 1.0 if category == gold else 0.0] for category in categories
                ],
                "answer_confidence": 1.0,
                "latency_ms": 1.0,
                "provider": "laya-http",
                "model_revision": revision,
            }
        )
    path = tmp_path / "predictions.json"
    path.write_text(json.dumps(predictions), encoding="utf-8")
    return path


def test_cli_is_offline_and_reports_characterization_without_enabling_laya(
    monkeypatch, capsys, tmp_path
):
    def block_network(*args, **kwargs):
        raise AssertionError("offline readiness must never open a socket")

    monkeypatch.setattr(socket, "create_connection", block_network)
    predictions = _write_predictions(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--contract",
            str(FIXTURE),
            "--predictions",
            str(predictions),
            "--artifact-root",
            str(tmp_path),
        ],
    )

    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit as error:
        assert error.code == 0

    report = json.loads(capsys.readouterr().out)
    assert report["decision"] == "CHARACTERIZATION_ONLY"
    assert report["production_enablement_authorized"] is False


def test_cli_does_not_advertise_an_unimplemented_shadow_eligibility_gate(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--help"])

    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit as error:
        assert error.code == 0

    assert "shadow" not in capsys.readouterr().out.casefold()
