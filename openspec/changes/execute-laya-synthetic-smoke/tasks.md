## 1. Dependency and pure contract

- [x] 1.1 Inspect the fixed upstream prediction API and separate scientific claims.
- [x] 1.2 Specify HU5/HU6 scope and closed synthetic profile.
- [x] 1.3 RED exact live PR40 authority, conservative preparation and privacy.
- [x] 1.4 GREEN additive pure contracts with no positive executor issuance yet.
- [x] 1.5 PR40 documentary HEAD accepted and merged; exact-SHA CI/real evidence recorded.

## 2. Executor

Dependency 1.5 closed: PR40 executable `4e9b84a` passed fresh real 1/1 (856.97
seconds) and CI `39025053332` 16/16. Documentary HEAD `eff82d7` passed CI
`39026767540` 16/16 (3351 passed, 57 skipped) and final independent global GO.
PR40 merged as `d889c98bbd556fe28cefb575b8c4c8e437f24110`.

PR41 was rebased to that exact merge. At post-rebase HEAD `81f3ef1`, source/tests
were unchanged from the reviewed preparation. Linux non-root/network-none
regression: 180 passed in 147.34 seconds; Ruff, Black (10 files), strict OpenSpec
and diff checks passed. This closes the preparation gate, not acceptance of the
remaining issuer/orchestration or real inference. Every synthetic execution must
use a fresh engine/nonce that never owns the parent image; cleanup may touch only
its exact child/intents. Scientific readiness and productive callers stay off.

- [x] 2.1 RED/GREEN runtime image lease and disposal concurrency (isolated unit scope).
- [x] 2.2 RED/GREEN fixed synthetic probe, strict output and determinism checks (unit scope).
- [x] 2.3 RED/GREEN owned isolated child and positive evidence issuance/revocation.

## 3. Acceptance

- [x] 3.1 Synthetic failure/resource/schema/privacy regression gates.
- [x] 3.2 Explicit real pinned smoke acceptance without scientific data.
- [x] 3.3 Historical/site/mock/backend/quality regressions.
- [x] 3.4 Independent critique/audit and exact-SHA CI; no open P0/P1/P2.

## Historical preparation evidence

RED: 7 missing-module failures before `runtime_execution.py` existed. GREEN:
7 focal passes; PR40+PR41 core regression 27 passes. Ruff/Black/diff-check pass.
That preparatory stage had no positive execution issuer, Docker call or inference;
PR40 acceptance had not yet closed. It is not the current implementation status.

Updated preparation: PR40/PR41 pure contracts pass 27/27 after rebasing to the
accepted executable. Image-lease RED `e595979`: 6 failures solely for the missing
private lease helper. Synthetic-probe RED `2e97d39`: 41 failures solely for the
missing module. Those were expected unmerged REDs, not failures of PR40 or main.

Unit GREEN before dependency 1.5 closed:

- Image lease RED `e595979` -> GREEN `062be9e`: 6 focal passes; Linux non-root
  lease/orchestration/core regression 51 passes. Independent architecture GO,
  no open P0/P1/P2 in this bounded slice.
- Synthetic probe RED `2e97d39` -> GREEN `8866159`; independent review found
  retained parser-error context and missing choice/maximum consistency. Follow-up
  RED `fce45fa` reproduced both; GREEN `3f6a3b8` passed 45 focal tests and
  independent re-review GO without open P0/P1/P2. Rounded ties accept any maximum.
- Ruff, Black and diff checks passed. No daemon, network or model execution was
  performed in these unit slices. This evidence is not real inference acceptance;
  The later post-merge focal/static checks are recorded above.

Closed engine unit preparation: RED `0cf1209` had 7 missing-API failures. Binary
log fixture correction `ad3c249` fixed a test oracle, not production behavior.
GREEN `0720896` passed 70 new/existing fake-transport tests. Adversarial additions
`644005e` passed 10 focal / 73 combined tests and independent GO without open
P0/P1/P2. Profile crossover, lost-response wrong-profile reconciliation and exact
post-run cleanup were covered. This slice never invoked Docker or a model; it
did not implement 2.3 or provide real acceptance.

Root verification on reviewed unit preparation `cb8f81f`: 96 combined Linux
non-root core/lease/probe/materialization tests passed in 144.17 seconds. This
does not replace post-merge rebasing and exact-head verification.

Shared observation boundary: RED `7c6936a` recorded 11 missing-module failures;
GREEN `e07c436` extracted the unchanged pure parser and reexported the same callable
from the adapter. Combined observation/probe/engine regression passed 129 tests.
Independent review identified a test-only import-scanner bypass for `ImportFrom`;
`d30a91a` closed it with hostile AST sanity cases. Re-review GO, no open P0/P1/P2;
56 parser tests and static checks passed. No authority issuance was added.

## Reviewed implementation before real/CI acceptance

- Core RED `7341eb1` -> GREEN `3360446`; persistent private commitment and
  concurrency/weak-registry RED `a8750f1` -> GREEN `1a69a27`.
- Orchestrator RED `b6df1f7` -> GREEN `efe5b51`; failure-cleanup ordering RED
  `966dc7e`; live partial-authority RED `96f67d7` -> GREEN `2036aa7` plus the
  exact-instance, idempotent core discard in `1a69a27`.
- Core 28/28; core/orchestrator combined 50/50. Independent architectural review
  of `1a69a27e65701ac338838a211b3ed20d92e6e410`: GO, no open P0/P1/P2. Adapter and
  real-gate review also GO with the reviewed core helper now integrated.
- Root integrated Linux non-root/network-none gate: **223 passed, 1 skipped in
  263.40 seconds**. The skip is the explicitly opt-in real execution test, not a
  real PASS. Later changes only clarified historical documentation and a test
  docstring; production source stayed identical to the reviewed freeze.
- Ruff, Black (14 changed Python files), strict OpenSpec and diff checks passed.
- At that unit-only stage, source was ready for exact-head CI and the fresh real
  gate; those results were not yet available. Tasks 3.2/3.3/3.4 were still open.
  Their subsequent executable acceptance is recorded below, not inferred from
  the unit results.

Historical preparation hashes above predate the PR40 rebase; equivalent patches
are retained in this branch history. Current acceptance uses the frozen source
and the actual final-head CI/real evidence, not those historical preparations.

## Final executable acceptance — 17 October 2026

- Candidate SHA: `087d0389ac235337d9922e9a0686e601e2db15c1`; its production
  source is identical to independently reviewed `1a69a27` (GO, no P0/P1/P2).
- CI `39030095587`: **16/16 PASS** on that exact candidate. Full Python:
  **3473 passed, 58 skipped in 1035.33 seconds**; Ruff and Black (372 files)
  passed, along with backend/frontend/API, Linux/Windows, historical/scientific
  container and runtime contract gates.
- Fresh original opt-in `test_laya_runtime_execution_real.py`: **1 passed in
  994.00 seconds (16:34)**. Complete real PR40 predecessor chain, source rootfs,
  independently verified derivative and offline CPU load were followed by the
  fixed synthetic execution. Two canonical-equal predictions and the exact
  schema/profile/35-claim summary passed. Runtime/source were disposed and the
  private parent was empty. No validation monkeypatch or tracer was used.
- Trusted helper image:
  `sha256:90d42f3d776d8d3434982bd00bd815166d496dd3195cea2fa6b6bbcb0d934475`;
  Docker29.5.2 Linux/amd64. Child isolation remained closed and host-mount-free.
- Only synthetic executor/inference capability is established. No human corpus,
  scientific evaluation, calibration, sufficiency, shadow or production is
  asserted. Corpus remains `BLOCKED_CORPUS_NOT_PROVIDED`.
- This closing change is documentation only. Its own checks and documentary
  review must pass before merge; no second model run is required for unchanged
  production source. The working local Codebase Memory artifacts are not staged.
