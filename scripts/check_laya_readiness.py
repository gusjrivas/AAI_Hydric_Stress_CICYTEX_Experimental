from __future__ import annotations

import argparse
import sys
from pathlib import Path

from human_feedback.offline_readiness import (
    canonical_report_bytes,
    evaluate_readiness,
    load_contract,
    load_predictions,
    verify_supply_identity,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the offline Laya readiness contract")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--require-shadow-eligible", action="store_true")
    args = parser.parse_args(argv)

    contract = load_contract(args.contract)
    predictions = load_predictions(args.predictions)
    supply_verification = verify_supply_identity(contract.supply, args.artifact_root)
    report = evaluate_readiness(
        contract,
        predictions,
        supply_verification=supply_verification,
    )
    sys.stdout.buffer.write(canonical_report_bytes(report))
    if args.require_shadow_eligible and report.decision != "ELIGIBLE_FOR_SHADOW_REVIEW":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
