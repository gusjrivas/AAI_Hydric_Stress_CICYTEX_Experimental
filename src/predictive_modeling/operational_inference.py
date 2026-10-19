"""Load immutable operational bundles and infer without fitting (HU4/HU6).

Only load artifacts from an administrator-controlled run directory, never from
an uploaded file or a path supplied by an HTTP client. File digests detect damage;
they are not signatures or authorization to deserialize untrusted joblib files.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from data_ingestion.schema import TIMESTAMP_COLUMN
from predictive_modeling.contract import positive_probability
from predictive_modeling.operational_contract import (
    OPERATIONAL_CONTRACT_VERSION,
    ArtifactIdentity,
    HorizonContract,
    VariableMetadata,
)
from predictive_modeling.operational_preparation import DateRange, TemporalCutPlan
from predictive_modeling.operational_run import build_feature_frame
from predictive_modeling.operational_run_artifacts import capture_environment


class BundleUnavailable(ValueError):
    """An explicit incompatibility; never interpreted as a negative alert."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class OperationalBundle:
    metadata: dict[str, Any]
    model: Any
    calibrator: Any

    @property
    def horizon(self) -> int:
        return self.metadata["contract"]["horizon_days"]

    @property
    def code_identity(self) -> dict[str, Any] | None:
        """Training-time commit/dirty record, or None when the bundle predates
        the field ("not registered"); never inferred from the current checkout."""
        return self.metadata.get("code_identity")


def load_operational_bundle(directory: Path, *, sensor_id: str, horizon: int) -> OperationalBundle:
    """Read each artifact once, check bytes before deserialization, never fit."""
    try:
        metadata = json.loads((Path(directory) / "bundle.json").read_text(encoding="utf-8"))
        contract = metadata["contract"]
        if (
            metadata["format_version"] != 1
            or contract["contract_version"] != OPERATIONAL_CONTRACT_VERSION
            or contract["artifact_state"] != "trained_bundle"
            or contract["sensor_id"] != sensor_id
            or contract["horizon_days"] != horizon
            or horizon not in (1, 2, 3)
        ):
            raise BundleUnavailable("incompatible_model")
        cuts = contract["temporal_cuts"]
        validated = HorizonContract(
            horizon_days=contract["horizon_days"],
            sensor_id=contract["sensor_id"],
            data_snapshot_sha256=contract["data_snapshot_sha256"],
            imputation=contract["imputation"],
            variables=tuple(VariableMetadata(**item) for item in contract["variables"]),
            event_variable=contract["event"]["variable"],
            event_threshold=contract["event"]["threshold"],
            event_unit=contract["event"]["unit"],
            event_comparison=contract["event"]["comparison"],
            temporal_cuts=TemporalCutPlan(
                allowed_data=DateRange(**cuts["allowed_data"]),
                train=DateRange(**cuts["train"]),
                calibration=DateRange(**cuts["calibration"]),
                evaluation=DateRange(**cuts["evaluation"]),
                inference_as_of=cuts["inference_as_of"],
            ),
            artifact_state=contract["artifact_state"],
            contract_version=contract["contract_version"],
            model_identity=ArtifactIdentity(**contract["model_identity"]),
            calibrator_identity=ArtifactIdentity(**contract["calibrator_identity"]),
            trained_through=date.fromisoformat(contract["trained_through"]),
            calibrated_through=date.fromisoformat(contract["calibrated_through"]),
        )
        if validated.to_dict() != contract:
            raise BundleUnavailable("incompatible_model")
        if metadata["environment"] != capture_environment():
            raise BundleUnavailable("incompatible_environment")
        content = {}
        for name in ("model.joblib", "calibrator.joblib", "contract.json"):
            value = (Path(directory) / name).read_bytes()
            if hashlib.sha256(value).hexdigest() != metadata["files"][name]:
                raise BundleUnavailable("artifact_identity_mismatch")
            content[name] = value
        if json.loads(content["contract.json"]) != contract:
            raise BundleUnavailable("artifact_identity_mismatch")
        model = joblib.load(io.BytesIO(content["model.joblib"]))
        calibrator = joblib.load(io.BytesIO(content["calibrator.joblib"]))
        expected = metadata["feature_names"]
        for estimator in (model, calibrator):
            if list(estimator.classes_) != [0, 1]:
                raise BundleUnavailable("incompatible_model")
            if list(estimator.feature_names_in_) != expected:
                raise BundleUnavailable("incompatible_features")
        if not np.isfinite(metadata["decision_threshold"]) or not (
            0 <= metadata["decision_threshold"] <= 1
        ):
            raise BundleUnavailable("incompatible_model")
        return OperationalBundle(metadata, model, calibrator)
    except BundleUnavailable:
        raise
    except FileNotFoundError as error:
        raise BundleUnavailable("model_not_available") from error
    except (OSError, ValueError, TypeError, KeyError, AttributeError, EOFError) as error:
        raise BundleUnavailable("invalid_model_bundle") from error


def predict_operational_bundle(
    bundle: OperationalBundle,
    dataframe: pd.DataFrame,
    *,
    sensor_id: str,
    units: Mapping[str, str],
    as_of_date: date,
) -> dict[str, Any]:
    """Predict precisely as_of+h, using only observations through as_of.

    Qualification of percentages needs the separate assessment/domain adapter.
    Until it exists, even a saved passed decision never enables a percentage.
    """
    metadata = bundle.metadata
    contract = metadata["contract"]
    if contract["sensor_id"] != sensor_id:
        raise BundleUnavailable("incompatible_model")
    if any(units.get(v["name"]) != v["unit"] for v in contract["variables"]):
        raise BundleUnavailable("incompatible_units")
    adjusted_through = max(
        date.fromisoformat(contract["trained_through"]),
        date.fromisoformat(contract["calibrated_through"]),
    )
    if adjusted_through > as_of_date:
        raise BundleUnavailable("model_not_available_at_date")
    try:
        # Cut before constructing temporal features: future values never enter.
        dates = pd.to_datetime(dataframe[TIMESTAMP_COLUMN], utc=True, errors="raise")
        prefix = dataframe.loc[dates <= pd.Timestamp(as_of_date, tz="UTC")].copy()
        required_days = max(max(metadata["lags"]) + 1, max(metadata["rolling_windows"]))
        required = set(pd.date_range(end=as_of_date, periods=required_days, tz="UTC"))
        if not required.issubset(set(dates.loc[prefix.index])):
            raise BundleUnavailable("insufficient_data")
        frame, names = build_feature_frame(
            prefix,
            metadata["feature_columns"],
            lags=metadata["lags"],
            windows=metadata["rolling_windows"],
        )
        if list(names) != metadata["feature_names"]:
            raise BundleUnavailable("incompatible_features")
        row = frame.loc[frame[TIMESTAMP_COLUMN] == pd.Timestamp(as_of_date), list(names)]
        if len(row) != 1 or not np.isfinite(row.to_numpy(dtype=float)).all():
            raise BundleUnavailable("insufficient_data")
        score = float(positive_probability(bundle.calibrator, row)[0])
        if not np.isfinite(score) or not 0 <= score <= 1:
            raise BundleUnavailable("invalid_model_output")
    except BundleUnavailable:
        raise
    except (ValueError, TypeError, KeyError) as error:
        raise BundleUnavailable("insufficient_data") from error
    return {
        "horizon_days": bundle.horizon,
        "target_date": (as_of_date + timedelta(days=bundle.horizon)).isoformat(),
        "alert": score >= metadata["decision_threshold"],
        "score": score,
        "score_kind": "calibrated_probability",
        "display_probability": None,
        "probability_status": "not_qualified",
        "probability_reason_code": "incompatible_assessment",
        "decision_threshold": metadata["decision_threshold"],
        "event_threshold": {
            "variable": contract["event"]["variable"],
            "value": contract["event"]["threshold"],
            "unit": contract["event"]["unit"],
            "comparison": contract["event"]["comparison"],
        },
        "model_reference": {
            "model_version": metadata["files"]["model.joblib"],
            "horizon_days": bundle.horizon,
            "contract_version": contract["contract_version"],
            "trained_through": contract["trained_through"],
            "calibration_version": metadata["files"]["calibrator.joblib"],
            "assessment_reference": None,
        },
    }
