from __future__ import annotations

import argparse
import sys
from pathlib import Path

from human_feedback.offline_readiness import (
    canonical_report_bytes,
    evaluate_readiness,
    load_contract,
    load_predictions,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the offline Laya readiness contract")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args(argv)

    contract = load_contract(args.contract)
    predictions = load_predictions(args.predictions)
    report = evaluate_readiness(
        contract,
        predictions,
        artifact_root=args.artifact_root,
    )
    sys.stdout.buffer.write(canonical_report_bytes(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
