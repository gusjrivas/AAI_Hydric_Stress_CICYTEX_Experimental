## 1. Dependencies and authority

- [x] 1.1 Read existing corpus/split/preregistration/execution contracts and ADR-0014.
- [x] 1.2 Independent scope decision: implement runner mechanics, no scientific claims.
- [x] 1.3 PR41 accepted/merged; exact merge rebase and repeated gates.
- [x] 1.4 RED/GREEN exact-issued preregistration authority; v1 regressions unchanged.
- [x] 1.5 RED/GREEN pure bound execution protocol and privacy-safe projection.

Preparation evidence (rebased SHAs): authority RED `4b38c18` -> GREEN `13330b6`;
protocol RED `79140db` -> GREEN `9767848`. Independent critique found one concurrent
issuance replacement defect: causal RED `bcfd097` -> GREEN `7d6198d`. Integrated bounded
regression: 145 passed; independent re-audit: 95 passed, Ruff/Black/diff PASS,
GO with no open P0/P1/P2 in this authority/protocol scope. This does not accept
the still-unimplemented executable adapter.

Dependency 1.3: PR41 merged as `54718d77d9902dd33e9f936552bb3c55f1485c04` on
2026-10-17 at 15:30:36 UTC. Exact-head closing CI `39043413122`: 16/16 PASS,
Python 3473 passed / 58 skipped / 1467.93 seconds. Rebase: no conflicts, all 29
patches equivalent by range-diff; only the predecessor tasks changed in the tree.
Repeated pure gate: 180 passed in 2.26 seconds; Ruff/Black four sources and diff
PASS. No real human corpus or scientific holdout was opened.

Only isolated pure/unit preparation is permitted before 1.3; no real inference,
corpus/holdout execution, positive scientific authority or publication.

## 2. Runner and closed adapter

- [x] 2.1 RED/GREEN zero-consume scientific preflight and gold-blind port.
- [x] 2.2 RED/GREEN per-fold state machine, phase release, exact coverage and resume.
- [ ] 2.3 RED/GREEN separately versioned fixed offline stdin/stdout adapter.
- [ ] 2.4 RED/GREEN lease/cleanup/fault/privacy/concurrency and private receipts.
- [ ] 2.5 Mechanical-only integration verification with fixed synthetic fixtures.

Pure preparation only (rebased SHAs): runner RED `3c44e55` -> GREEN `9aa76c0`;
byte-codec RED `91d4623` -> GREEN `176d0b8`. Review-driven runner RED `ca68ad7`
-> GREEN `809cadb` preserves canonical outputs and revalidates waiting executions;
RED `84bc751` -> GREEN `b0cd79b` binds sealed receipts to independent private
identity/digest commitments. Bounded pure suite: 180 passed. Independent final
runner review on pre-rebase `a024619` (equivalent `b0cd79b`): GO, no P0/P1/P2,
runner 18 passed, Ruff/Black/diff PASS.
Public preflight remains zero-consume BLOCKED; private fixture seams do not issue
scientific authority. Rounded probability ties retain the approved semantics.

The executable Docker adapter is NOT accepted by these pure gates. Fixed-program
RED `b7a15df` and engine/attach RED through `669521b` intentionally remain failing
until their implementation, now permitted after dependency 1.3. This includes a realistic
HTTPResponse 101 buffered-frame regression, not only transport mocks.

## 3. Technical acceptance

- [ ] 3.1 Historical/site/mock/backend/quality regression gates.
- [ ] 3.2 Independent critique/audit, no open P0/P1/P2, exact-head CI.
- [ ] 3.3 Record implementation status separately from scientific BLOCKED status.

## 4. Scientific execution — explicitly BLOCKED, never inferred from fixtures

- [ ] 4.1 Real corpus/custody supplied and independently bound to preregistration.
- [ ] 4.2 Calibration method externally frozen before calibration/test access.
- [ ] 4.3 Corpus runtime profile authorized; real gold-blind run and receipts.

These open scientific gates do not permit real execution during mechanical tests.
They must not be silently checked or represented as completed by code coverage.
