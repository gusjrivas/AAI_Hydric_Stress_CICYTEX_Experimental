# Materialize an offline Laya runtime and checkpoint

## Traceability

HU5 (`human-feedback`) and HU6 (`architecture-integration`), CRISP-DM deployment
and experimental integration, following ADR-0001/ADR-0014 and PR39. This change
does not alter experimental configurations, hypotheses, datasets, forecasts,
recalibration, HTTP contracts or HU7/HU8 results. No scientific holdout is opened.

## Problem and scope

PR39 produces an authenticated disposable rootfs. The verified real OCI contains
the runtime but none of the five pinned checkpoint objects. A separate checkpoint
at revision `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851` is now provisioned outside
Git; all five sizes and SHA-256 digests match the deployment contract.

Add an isolated, removable derived runtime image that combines exactly issued
PR39 rootfs authority with the exact issued checkpoint already bound by supply
convergence. A closed offline CPU probe imports Laya and loads the pinned model.
Only `runtime_materialized` becomes newly true; executor availability, inference,
readiness, production and legal/build provenance claims retain their prior values.

## Authorized implementation boundary

The user authorized the architecture plan, installation of Laya/tools, autonomous
TDD, independent review and PR/merge execution. Docker and its explicit local
daemon are trusted orchestration infrastructure. The child runtime is isolated
with no host mounts, no network, no privileges and bounded resources. This is an
explicit runtime-adapter decision, not a change to the scientific protocol.

## Validation

RED before each implementation slice; exact identity/anti-forgery tests; bounded
archive and checkpoint recapture; command/configuration/timeout fault injection;
Linux Docker synthetic integration; opt-in real pinned checkpoint/model loading;
historical/site/mock and predecessor regressions; independent GO and CI on SHA.
