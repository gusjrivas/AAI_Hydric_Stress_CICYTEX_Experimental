# Change: Materialize the Laya rootfs safely

## Why

PR33 proves the logical OCI rootfs and PR37 proves convergence of the supply
graph, but neither writes payload bytes to a host filesystem. PR39 needs an
isolated boundary that materializes one disposable rootfs without widening any
runtime, executor, inference or scientific-readiness claim.

## What Changes

- Add a pure authority that binds the exact PR33 rootfs evidence to the exact
  issued PR37 supply-convergence evidence.
- Add a Linux-only, non-root filesystem adapter in a later TDD slice. It will
  recapture all ten OCI layers offline, stage a bounded tree and publish it with
  an atomic no-clobber primitive.
- Define `rootfs_materialized=true` as exact regular bytes plus directory,
  symlink and hardlink topology under the fixed `nonroot-disposable-v1` host
  profile. OCI uid/gid and unsupported host metadata remain logical evidence;
  they are not falsely claimed as applied host metadata.
- Keep `runtime_materialized`, `executor_available`, `inference_executed` and
  readiness/production authority false.

## Traceability

- HU: HU5 (`human-feedback`) and HU6 (`architecture-integration`).
- CRISP-DM: deployment and experimental integration preparation.
- Experimental configurations: none changed.
- Hypotheses/datasets/results: none changed; no A/B/C execution or holdout use.

## Compatibility

Backend, frontend, runners, datasets, Melchor Romero, Pergamino, CICYTEX and the
mock-sensor laboratory remain outside the productive call graph of this change.
