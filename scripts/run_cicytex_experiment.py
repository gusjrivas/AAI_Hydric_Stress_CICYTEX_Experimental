from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from experiment_runner.cicytex.experiment import run_experiment
from experiment_runner.cicytex.ingestion import (
    build_cicytex_dataset_provenance,
    load_normalized_cicytex_snapshot,
)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=Path("data/cicytex/raw"))
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("results/cicytex"))
    parser.add_argument("--tracking-uri", default=None)
    args = parser.parse_args()
    normalizados = args.raw_root / "normalizados"
    dataset_source = args.raw_root / "originales" / "cicytex" / "DTPT_Figure_8.csv"
    snapshot = load_normalized_cicytex_snapshot(normalizados)
    provenance = build_cicytex_dataset_provenance(snapshot, dataset_source, args.zip)
    result = run_experiment(
        snapshot.dataframe,
        args.output,
        provenance.primary_source.sha256,
        provenance.source_archive.sha256,
        args.tracking_uri,
        dataset_provenance=provenance,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
