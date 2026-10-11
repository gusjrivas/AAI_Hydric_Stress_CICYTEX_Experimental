"""Run the frozen CICYTEX causal ensemble preparation and archive replay data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from experiment_runner.cicytex.causal_ensemble import run_causal_ensemble  # noqa: E402
from experiment_runner.cicytex.ingestion import (  # noqa: E402
    build_cicytex_dataset_provenance,
    load_normalized_cicytex_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=ROOT / "data" / "cicytex" / "raw" / "normalizados",
    )
    parser.add_argument(
        "--dataset-file",
        type=Path,
        default=ROOT / "data" / "cicytex" / "raw" / "originales" / "cicytex" / "DTPT_Figure_8.csv",
    )
    parser.add_argument(
        "--zip",
        type=Path,
        default=Path(r"C:\Users\gusta\Downloads\AAI_Hydric_Stress_External_Datasets.zip"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "results" / "cicytex" / "causal_replay"
    )
    parser.add_argument("--tracking-uri", default="http://localhost:5500")
    args = parser.parse_args()
    for path in (args.normalized_dir, args.dataset_file, args.zip):
        if not path.exists():
            parser.error(f"No existe: {path}")
    snapshot = load_normalized_cicytex_snapshot(args.normalized_dir)
    provenance = build_cicytex_dataset_provenance(snapshot, args.dataset_file, args.zip)
    summary = run_causal_ensemble(
        snapshot.dataframe,
        args.output_dir,
        dataset_sha256=provenance.primary_source.sha256,
        zip_sha256=provenance.source_archive.sha256,
        tracking_uri=args.tracking_uri,
        dataset_provenance=provenance,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
