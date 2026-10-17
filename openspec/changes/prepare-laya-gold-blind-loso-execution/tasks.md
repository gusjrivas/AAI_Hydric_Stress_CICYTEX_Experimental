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
- [x] 2.3 RED/GREEN separately versioned fixed offline stdin/stdout adapter.
- [x] 2.4 RED/GREEN lease/cleanup/fault/privacy/concurrency and private receipts.
- [x] 2.5 Mechanical-only integration verification with fixed synthetic fixtures.

Pure preparation only (rebased SHAs): runner RED `3c44e55` -> GREEN `9aa76c0`;
byte-codec RED `91d4623` -> GREEN `176d0b8`. Review-driven runner RED `ca68ad7`
-> GREEN `809cadb` preserves canonical outputs and revalidates waiting executions;
RED `84bc751` -> GREEN `b0cd79b` binds sealed receipts to independent private
identity/digest commitments. Bounded pure suite: 180 passed. Independent final
runner review on pre-rebase `a024619` (equivalent `b0cd79b`): GO, no P0/P1/P2,
runner 18 passed, Ruff/Black/diff PASS.
Public preflight remains zero-consume BLOCKED; private fixture seams do not issue
scientific authority. Rounded probability ties retain the approved semantics.

The complete executable adapter is NOT accepted by these pure gates.
Fixed-program RED `b7a15df` -> GREEN `53a631f`: 22 tests passed, independent
GO without P0/P1/P2 in that program-only scope, Ruff/Black/diff PASS. Pinned Laya
returns real top-level usage metadata; no tokenizer counts are fabricated.

Engine/attach RED through `669521b` -> initial GREEN `fdcb98a`: 20 tests passed;
legacy engine/synthetic/observation/executor regression 106 passed in 108.21 s.
Real Docker transport gate `7ed750d`: 2 passed in 2.79 s (Unicode and exact 64 KiB
stdin, size/SHA response, owned-child cleanup verified). This gate uses fixed
synthetic bytes and Python only, not Laya or a scientific corpus. A first attempt
used a mismatched test timeout and was corrected without changing production.

Engine review then found a P1 response-descriptor leak on invalid upgrade / begin
failure: RED `dee173c` (5 causal failures) -> GREEN `c0ff8bc`, independent GO,
21 focal and 73 legacy tests passed. Fresh real transport repeat after this fix:
2 passed in 3.50 seconds; no fixture child remained.

Concrete runtime-bound port RED `d5e4e8f` -> GREEN `14189aa`: 14 focal tests
passed; independent peer GO without P0/P1/P2, 14 passed in 50.64 seconds.
Separate test-oracle corrections `9184d2a` / `c828195` preserve valid fixture
digests and mirror the real keyword-only engine signature, not production changes.
Mechanical end-to-end wiring `37b3c2e`: real runner/port/codec/registered lease,
fake Docker backend only, 3 folds / 6 ordered batches; focal 1 passed in 6.18 s,
combined runner/port 33 passed in 53.82 s. Replay is idempotent and public preflight
consumes nothing. Linux non-root/network-none new-code suite before that final
integration test: 107 passed / 3 opt-in skips in 54.73 s. No skip is real PASS.
Final Ruff/Black 17 changed Python files, strict OpenSpec and diff checks passed.
No scientific execution is implied by any mechanical or transport gate.

## 3. Technical acceptance

- [x] 3.1 Historical/site/mock/backend/quality regression gates.
- [x] 3.2 Independent critique/audit, no open P0/P1/P2, exact-head CI.
- [x] 3.3 Record implementation status separately from scientific BLOCKED status.

Historical acceptance recorded by PR43 after PR42 merge: executable frozen HEAD
`3903a1d2d80ddccacf468a7e1ac87152d5c5ce8c`; exact-head CI `39046683875`:
16/16 SUCCESS. Python job `117436699479`: 3580 passed / 62 skipped / 26 warnings
in 1621.09 seconds (27:01). Backend, frontend, API contracts and the historical
site/mock gates also passed. A skipped opt-in test is not genuine acceptance.

Genuine pinned-runtime offline-port gate: 1 passed in 1344.20 seconds (22:24),
exit 0, unified exec session 87915, 2026-10-17. It rebuilt the reviewed fixed
supply/rootfs/checkpoint chain, sent exactly two synthetic comments through the
new port, validated canonical outputs and actual usage, disposed runtime/rootfs
and asserted an empty private parent. No corpus/holdout, fitting or scoring.

Command (trusted helper only receives the socket; the child does not):
`docker run --rm --network none --cap-drop ALL --security-opt
no-new-privileges --user 1000:0 -e PYTHONDONTWRITEBYTECODE=1 -e
PYTHONPATH=/work/AAI_Hydric_Stress_PR42_LOSO_Runner/src:/work/AAI_Hydric_Stress_PR42_LOSO_Runner
-e LAYA_LOSO_OFFLINE_REAL=1 -v /var/run/docker.sock:/var/run/docker.sock -v
C:/Users/gusta/Documents/Codex/2026-10-10/qui/work:/work:ro -w
/work/AAI_Hydric_Stress_PR42_LOSO_Runner
sha256:90d42f3d776d8d3434982bd00bd815166d496dd3195cea2fa6b6bbcb0d934475
python -m pytest tests/test_laya_loso_docker_adapter_real.py -q -s -p
no:cacheprovider`.

Independent final GO retained with no P0/P1/P2; no tracked tree changes between
review, genuine gate, CI and guarded merge. PR42 merged on 2026-10-17 at
16:18:11 UTC as `4b06a3c97f7067fdc33f58637c3bc746dd48f0da`. Its merge tree is
identical to the accepted HEAD. These checkboxes close observed technical gates
historically, not scientific prerequisites. The change is not archived as a
scientifically completed evaluation.

## 4. Scientific execution — explicitly BLOCKED, never inferred from fixtures

- [ ] 4.1 Real corpus/custody supplied and independently bound to preregistration.
- [ ] 4.2 Calibration method externally frozen before calibration/test access.
- [ ] 4.3 Corpus runtime profile authorized; real gold-blind run and receipts.

These open scientific gates do not permit real execution during mechanical tests.
They must not be silently checked or represented as completed by code coverage.
