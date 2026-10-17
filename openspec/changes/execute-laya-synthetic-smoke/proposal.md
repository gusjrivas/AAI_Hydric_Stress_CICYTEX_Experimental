# Isolated synthetic Laya execution

## Why

PR40 installs and loads the exact offline model but deliberately does not execute
inference. A separate capability must prove that a governed disposable executor
can process a fixed synthetic request without creating scientific authority.

## Traceability and scope

- HU5/HU6; capabilities `human-feedback` / `architecture-integration`.
- CRISP-DM: experimental deployment/integration, not scientific evaluation.
- No change to base/synthetic/anomaly/full experimental configurations,
  hypotheses, datasets, historical results, HTTP contracts or productive wiring.
- Depends on accepted PR40. Until its gates close, work is limited to additive
  pure contracts/tests; no execution, publish, merge or downstream activation.

## Change

Bind an exact live issued runtime to a fixed CPU/offline synthetic smoke profile.
Execute the same bounded synthetic choice twice in an isolated disposable child,
validate the closed output and canonical equality, then issue private evidence.
Only `executor_available` and `inference_executed` may become true. This does not
attest LOSO completion, scientific sufficiency, readiness, shadow or production.

## Non-goals

No private corpus, holdout access, calibration, threshold selection, agronomic
decision, forecast/recalibration call, server or UI enablement. Do not change
`ports.py`, `decision_policy.py` or `evaluation_execution.py` in this slice.
