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

from experiment_runner.cicytex.causal_ensemble import run_causal_ensemble
from experiment_runner.cicytex.ingestion import load_normalized_cicytex, sha256_file


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
    summary = run_causal_ensemble(
        load_normalized_cicytex(args.normalized_dir),
        args.output_dir,
        dataset_sha256=sha256_file(args.dataset_file),
        zip_sha256=sha256_file(args.zip),
        tracking_uri=args.tracking_uri,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
