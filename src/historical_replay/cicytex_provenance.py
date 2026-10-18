"""Read-only projection of the archived CICYTEX package provenance.

Only identity and partition facts are exposed (hashes, commit, seed, split
boundaries, MLflow run ids). Metrics and prediction rows stay out on purpose:
this projection must never reveal results ahead of the replay clock.
"""

from __future__ import annotations

import json
from pathlib import Path

from historical_replay.cicytex_application import CicytexCatalogUnavailable

_TOP_LEVEL = (
    "dataset_sha256",
    "git_commit",
    "seed",
    "proxy",
    "ensemble_policy",
    "mlflow_parent_run_id",
    "prediction_sha256",
)
_PER_HORIZON = (
    "threshold_train_p20",
    "first_legitimate_emission",
    "split",
    "partition_rows",
    "component_mlflow_runs",
)


class CicytexProvenanceApplication:
    def __init__(self, summary_path: Path) -> None:
        self._summary_path = Path(summary_path)

    def provenance(self) -> dict:
        try:
            summary = json.loads(self._summary_path.read_text(encoding="utf-8"))
            return {
                **{key: summary[key] for key in _TOP_LEVEL},
                "horizons": {
                    str(horizon): {key: data[key] for key in _PER_HORIZON}
                    for horizon, data in summary["horizons"].items()
                },
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise CicytexCatalogUnavailable from None
