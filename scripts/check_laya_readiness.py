from __future__ import annotations

import argparse
import sys
from pathlib import Path

from human_feedback.offline_readiness import (
    canonical_report_bytes,
    evaluate_readiness,
    load_contract,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the offline Laya readiness contract")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument(
        "--use-perfect-fixture-predictions",
        action="store_true",
        help="Exercise evaluator deterministically; never counts as scientific evidence.",
    )
    parser.add_argument("--require-shadow-eligible", action="store_true")
    args = parser.parse_args(argv)

    contract = load_contract(args.contract)
    if not args.use_perfect_fixture_predictions:
        parser.error("an offline predictions input is required")
    report = evaluate_readiness(
        contract,
        contract.perfect_predictions(),
        supply_verified=False,
    )
    sys.stdout.buffer.write(canonical_report_bytes(report))
    if args.require_shadow_eligible and report.decision != "ELIGIBLE_FOR_SHADOW_REVIEW":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
