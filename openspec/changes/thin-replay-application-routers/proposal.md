# Change: Thin replay application routers

## Why

The CICYTEX and historical replay routes preserve important scientific and HTTP
contracts, but the FastAPI modules still calculate projections, metrics,
visibility and persistence coordination.  That makes transport changes capable
of changing scientific behavior and prevents the same use cases from being
tested without FastAPI.

## What Changes

- Move CICYTEX session rendering, metric calculation and feedback coordination
  into a framework-free application module under `historical_replay`.
- Move historical candidate, prediction, history and feedback orchestration into
  a second framework-free application module.
- Keep both routers as HTTP adapters: dependency resolution, request parsing,
  response-schema construction and stable error/status translation only.
- Freeze the existing route paths, operation IDs, response models and observable
  payload/status behavior throughout the refactor.

## Out of Scope

- Changing replay datasets, scientific projections, thresholds or metrics.
- Changing SQLite schemas, feedback semantics or session concurrency.
- Refactoring unrelated API routers, frontend flows or Laya runtime work.
