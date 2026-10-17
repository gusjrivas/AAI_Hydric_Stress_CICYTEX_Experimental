## 1. Contract and RED

- [x] 1.1 Freeze the honest non-root materialization boundary and claim profile.
- [x] 1.2 Record a failing pure-contract test before implementation (`2 failed`, missing module).
- [x] 1.3 Add exact PR33 + issued PR37 binding, anti-forgery and privacy tests.

## 2. Pure authority

- [x] 2.1 Implement the I/O-free plan and sealed evidence contract.
- [x] 2.2 Prove that only `rootfs_materialized` is newly elevated.

## 3. Secure Linux adapter

- [x] 3.1 Add RED tests for capability, destination and source preflight.
- [x] 3.2 Stream and reverify all layers while writing exact surviving payloads.
- [x] 3.3 Verify the staged tree and publish atomically without clobbering.
- [x] 3.4 Add bounded, ownership-scoped disposal and conservative orphan-recovery rules.

## 4. Gates

- [x] 4.1 Pass focal, predecessor, historical and mock-sensor regressions.
- [x] 4.2 Pass Ruff, Black, OpenSpec strict and Linux CI.
- [x] 4.3 Obtain independent critic and mechanical GO on the exact SHA.

PR39 merged on 2026-10-17: reviewed executable SHA
`841f6fe6a8daa8868e74ae36d57565b9858d0644`, CI 15/15 green,
independent GO P0/P1/P2=0; main merge
`4f6e19b839949b90180849f65339a693a991e0cb`.
Local Linux gate: 350 passed, 30 external opt-in skips; backend 251 passed,
1 skipped; historical runners 31 passed; CICYTEX/mock 82 passed.
Full remote Python/backend/frontend/contract/container gates passed on the
reviewed SHA. Real OCI mapping was reverified separately (56,114 logical nodes);
no real checkpoint/runtime execution or scientific acceptance is claimed by PR39.
