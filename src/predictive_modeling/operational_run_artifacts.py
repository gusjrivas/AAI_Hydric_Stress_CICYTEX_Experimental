"""Isolated artifact persistence for one `operational_run.run_operational_manifest`
execution.

Every call writes to a brand-new, empty `output_dir` (fails otherwise: this
is the "espacio operacional nuevo y aislado" required by the task, never a
historical run directory) and never touches `controlled_daily_v3`/`v4`,
their baselines, or any file under `config/` other than reading the frozen
manifest that was already verified by the caller.

Layout written under `output_dir`:

    run_metadata.json          run id, manifest/dataset/code/environment identity
    report.md                  human-readable summary, per horizon, with limits
    horizon_<h>/status.json    status/reason (training_failed horizons stop here)
    horizon_<h>/assessment.json         classify_horizon diagnostic
    horizon_<h>/final_decision.json     make_final_decision (calibration + baselines)
    horizon_<h>/contract.json           HorizonContract.to_dict()
    horizon_<h>/predictions.csv         per seed/date: raw, calibrated, persistence, outcome
    horizon_<h>/baseline_comparisons.csv
    horizon_<h>/support_results.csv
    horizon_<h>/model.joblib
    horizon_<h>/calibrator.joblib
    horizon_<h>/bundle.json    load contract, feature configuration and file digests
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

import joblib

from predictive_modeling.operational_run import (
    DEFAULT_LAGS,
    DEFAULT_ROLLING_WINDOWS,
    OperationalRunResult,
)

TRACKED_PACKAGES = ("scikit-learn", "pandas", "numpy", "pyarrow")


class ArtifactPersistenceError(ValueError):
    """The isolated-run precondition (new, empty `output_dir`) was violated."""


def capture_code_identity(repo_root: Path) -> dict[str, Any]:
    """Best-effort git commit/dirty capture; never invents a value."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout
        return {"available": True, "commit": commit, "dirty": bool(status.strip())}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "reason": str(exc)}


def capture_environment() -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for package in TRACKED_PACKAGES:
        try:
            versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            versions[package] = None
    return {"python": platform.python_version(), "dependencies": versions}


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _write_predictions_csv(path: Path, horizon_result) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "target_date", "raw", "calibrated", "persistence", "outcome"])
        for seed_fit in horizon_result.seed_fits:
            for target_date in sorted(seed_fit.outcome_by_target_date):
                writer.writerow(
                    [
                        seed_fit.seed,
                        target_date.isoformat(),
                        seed_fit.raw_by_target_date[target_date],
                        seed_fit.calibrated_by_target_date[target_date],
                        seed_fit.persistence_by_target_date[target_date],
                        seed_fit.outcome_by_target_date[target_date],
                    ]
                )


def _write_baseline_comparisons_csv(path: Path, horizon_result) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "seed",
                "period_id",
                "n",
                "brier_calibrated",
                "brier_raw",
                "brier_climatology",
                "brier_persistence",
                "log_loss_calibrated",
                "log_loss_raw",
                "log_loss_climatology",
                "log_loss_persistence",
                "ok",
                "reasons",
            ]
        )
        for comparison in horizon_result.baseline_comparisons:
            writer.writerow(
                [
                    comparison.seed,
                    comparison.period_id,
                    comparison.n,
                    comparison.brier_calibrated,
                    comparison.brier_raw,
                    comparison.brier_climatology,
                    comparison.brier_persistence,
                    comparison.log_loss_calibrated,
                    comparison.log_loss_raw,
                    comparison.log_loss_climatology,
                    comparison.log_loss_persistence,
                    comparison.ok,
                    ";".join(comparison.reasons),
                ]
            )


def _write_support_results_csv(path: Path, horizon_result, periods: dict[str, Any]) -> None:
    period_ids = list(periods)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "period_id", "ok", "reasons"])
        index = 0
        for seed_fit in horizon_result.seed_fits:
            for period_id in period_ids:
                support = horizon_result.support_results[index]
                writer.writerow([seed_fit.seed, period_id, support.ok, ";".join(support.reasons)])
                index += 1


def _horizon_report_section(horizon_result, *, deployment_seed: int) -> str:
    lines = [f"## Horizonte +{horizon_result.horizon}", ""]
    if horizon_result.status != "evaluated":
        lines.append(f"- Estado: `{horizon_result.status}` ({horizon_result.reason})")
        lines.append("- Sin evaluacion: horizonte aislado, no afecta a los otros dos.")
        return "\n".join(lines) + "\n"

    assessment = horizon_result.assessment
    decision = horizon_result.final_decision
    lines.append(f"- Umbral congelado (`event.threshold`): {horizon_result.threshold:.6f}")
    lines.append(
        f"- Diagnostico de calibracion (`classify_horizon`): "
        f"`{assessment.assessment_result}` (razones: {', '.join(assessment.reasons) or '-'})"
    )
    if assessment.joint_upper_bound is not None:
        lines.append(
            f"  - Limite superior conjunto U (percentil 95): {assessment.joint_upper_bound:.4f}"
        )
    lines.append(
        f"- Decision final (`make_final_decision`, calibracion + baselines): "
        f"`{decision.final_result}` (razones: {', '.join(decision.reasons) or '-'})"
    )
    lines.append(
        f"- Identidad del modelo desplegado (deployment_seed={deployment_seed}): "
        f"`{horizon_result.contract.model_identity.sha256}`"
    )
    horizon = horizon_result.horizon
    lines.append(f"- Predicciones/baselines: ver `horizon_{horizon}/predictions.csv`.")
    lines.append(
        "- Solo evaluacion de desarrollo sobre datos ya observados por el proyecto; "
        "no acredita validacion agronomica externa ni holdout independiente."
    )
    return "\n".join(lines) + "\n"


def _build_report(
    result: OperationalRunResult,
    *,
    run_id: str,
    manifest_path: Path,
    manifest_identity_sha256: str,
    dataset_id: str,
    code_identity: dict[str, Any],
    environment: dict[str, Any],
) -> str:
    lines = [
        f"# Corrida operacional +1/+2/+3 -- `{run_id}`",
        "",
        f"- Manifiesto: `{manifest_path}` (identidad de contenido `{manifest_identity_sha256}`)",
        f"- Dataset: `{dataset_id}` (sha256 `{result.dataset_sha256}`)",
        f"- Codigo: {code_identity}",
        f"- Entorno: {environment}",
        f"- Familia de contratos h=1/2/3 compatible: {result.contract_family_valid}",
        "",
        "Corrida de desarrollo unicamente (design.md, "
        "`openspec/changes/add-daily-multihorizon-predictors/design.md`): "
        "no abre ni usa ningun holdout protegido, no reemplaza una validacion "
        "agronomica externa, y `classify_horizon` nunca se usa por si solo "
        "como aprobacion final (ver `final_decision` de cada horizonte).",
        "",
    ]
    for horizon_result in result.horizons:
        lines.append(
            _horizon_report_section(horizon_result, deployment_seed=result.deployment_seed)
        )
    return "\n".join(lines)


def persist_operational_run(
    result: OperationalRunResult,
    *,
    output_dir: Path,
    run_id: str,
    manifest_path: Path,
    manifest_identity_sha256: str,
    dataset_id: str,
    repo_root: Path,
) -> Path:
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ArtifactPersistenceError(
            f"{output_dir} ya existe y no esta vacio: no se sobrescribe una corrida existente."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    code_identity = capture_code_identity(repo_root)
    environment = capture_environment()

    _write_json(
        output_dir / "run_metadata.json",
        {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "manifest_path": str(manifest_path),
            "manifest_identity_sha256": manifest_identity_sha256,
            "dataset_id": dataset_id,
            "dataset_sha256": result.dataset_sha256,
            "event_variable": result.event_variable,
            "threshold": result.threshold,
            "feature_columns": list(result.feature_columns),
            "periods": {
                period_id: {"start": period.start.isoformat(), "end": period.end.isoformat()}
                for period_id, period in result.periods.items()
            },
            "contract_family_valid": result.contract_family_valid,
            "code_identity": code_identity,
            "environment": environment,
        },
    )

    for horizon_result in result.horizons:
        horizon_dir = output_dir / f"horizon_{horizon_result.horizon}"
        horizon_dir.mkdir()
        _write_json(
            horizon_dir / "status.json",
            {"status": horizon_result.status, "reason": horizon_result.reason},
        )
        if horizon_result.status != "evaluated":
            continue

        _write_json(
            horizon_dir / "assessment.json",
            asdict(horizon_result.assessment),
        )
        final_decision = horizon_result.final_decision
        _write_json(
            horizon_dir / "final_decision.json",
            {
                "horizon": final_decision.horizon,
                "final_result": final_decision.final_result,
                "reasons": final_decision.reasons,
                "calibration_diagnostic": asdict(final_decision.calibration_diagnostic),
            },
        )
        _write_json(horizon_dir / "contract.json", horizon_result.contract.to_dict())
        _write_predictions_csv(horizon_dir / "predictions.csv", horizon_result)
        _write_baseline_comparisons_csv(horizon_dir / "baseline_comparisons.csv", horizon_result)
        _write_support_results_csv(
            horizon_dir / "support_results.csv", horizon_result, result.periods
        )

        deployment_fit = next(
            fit for fit in horizon_result.seed_fits if fit.seed == result.deployment_seed
        )
        joblib.dump(deployment_fit.model, horizon_dir / "model.joblib")
        joblib.dump(deployment_fit.calibrator, horizon_dir / "calibrator.joblib")
        # Last-written marker: incomplete exports have no loadable bundle.
        # 0.5 is the existing operational alert threshold; never selected on test.
        _write_json(
            horizon_dir / "bundle.json",
            {
                "format_version": 1,
                "contract": horizon_result.contract.to_dict(),
                "feature_columns": list(result.feature_columns),
                "feature_names": list(horizon_result.feature_names),
                "lags": list(DEFAULT_LAGS),
                "rolling_windows": list(DEFAULT_ROLLING_WINDOWS),
                "decision_threshold": 0.5,
                "environment": environment,
                # Captured once at training time; informative lineage only, not
                # part of any artifact/ensemble identity hash.
                "code_identity": code_identity,
                "files": {
                    name: hashlib.sha256((horizon_dir / name).read_bytes()).hexdigest()
                    for name in ("model.joblib", "calibrator.joblib", "contract.json")
                },
            },
        )

    (output_dir / "report.md").write_text(
        _build_report(
            result,
            run_id=run_id,
            manifest_path=manifest_path,
            manifest_identity_sha256=manifest_identity_sha256,
            dataset_id=dataset_id,
            code_identity=code_identity,
            environment=environment,
        ),
        encoding="utf-8",
    )
    return output_dir
