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
- Depends on accepted and merged PR40. Its executable `4e9b84a` passed the fresh
  real chain (856.97 seconds) and CI `39025053332` (16/16). The documentary closing
  HEAD still requires checks and merge. Independent architecture review permits
  isolated unit GREEN for the image lease and closed synthetic validator/program
  during that documentary gate, without daemon, network, real inference or
  positive execution evidence. PR41 publishing, merge and real smoke remain
  blocked until PR40 merges; then rebase onto its exact merge commit and repeat
  focal/static gates. This is preparation, not downstream activation.

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
