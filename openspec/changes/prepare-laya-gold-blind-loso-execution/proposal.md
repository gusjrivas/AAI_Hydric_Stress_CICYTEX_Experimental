# Gold-blind LOSO execution mechanics with explicit scientific gates

## Traceability

HU5/HU6; `human-feedback` / `architecture-integration`; CRISP-DM experimental
integration and evaluation mechanics. No changes to hypotheses, datasets,
base/+synthetic/+anomaly/full configurations, HU7/HU8, v3, historical artifacts,
forecast, recalibration or irrigation decisions. ADR-0001 and ADR-0014 apply.

## Why

The existing LOSO plan and preregistration are structural contracts. PR41 proves
only one fixed synthetic smoke, not corpus inference or scientific sufficiency.
The legacy execution contract declares `laya-http`; an offline execution must not
reuse that provenance label or silently relax v1. Implement the planned runner
and offline adapter additively, while preserving the scientific boundary.

## Dependencies and current preparation limit

Based on accepted PR41 merge `54718d77d9902dd33e9f936552bb3c55f1485c04`.
PR41 closing CI `39043413122` passed 16/16; Python 3473 passed, 58 skipped.
Its separate fixed synthetic real gate passed in 994.00 seconds. This branch was
rebased onto that exact merge without conflicts; all 29 preparation patches were
unchanged and the 180-test pure gate and static checks passed again.
Implementation of the closed offline adapter may now proceed under TDD.
Real corpus/model evaluation and positive scientific authority remain blocked by
the separate custody, calibration-method and corpus-runtime-profile gates.

## Change

Add verified preregistration instance authority without changing the v1 public
schema/summary. Bind a successor protocol to exact preregistration/corpus/plan/
assignment commitments. Define a gold-blind port, ordered per-fold mechanics,
private receipts and a separately versioned fixed offline input/output adapter.
Only private opaque tokens and comments may reach the inference port; gold,
annotators, adjudication, group/site IDs and record objects cannot reach it.

The public runner preflights corpus custody, frozen calibration method and corpus
runtime-profile authority before reading comments or invoking inference. It does
not choose or fit an unspecified calibration algorithm. Mechanical fixtures can
verify implementation, never authorize a scientific run or upgrade claims.

## Honest completion

The technical target is an implemented, tested runner/adapter, not another
standalone contract that moves execution into PR43. PR43 remains statistical
qualification; PR44 remains readiness. Actual corpus execution, fitted calibration
and holdout release remain BLOCKED while external authorities are missing.
`IMPLEMENTED_MECHANICALLY` is not scientific completion or thesis closure.

## Non-goals

No real human corpus fabrication, opening of scientific holdouts, A/B/C runs,
method selection, scientific PASS, shadow/UI/production enablement or productive
caller. No HTTP provider impersonation and no caller-controlled executable,
environment, model, task or host mount.
