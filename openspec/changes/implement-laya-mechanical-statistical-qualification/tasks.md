## 1. Scope and dependency

- [x] 1.1 Read frozen analysis, legacy metrics and PR42 sealed-output contracts.
- [x] 1.2 Record mechanical fixture conventions without changing study protocol.
- [x] 1.3 PR42 accepted/merged, exact-merge rebase, actual evidence recorded.
- [x] 1.4 Close PR42 result-dependent tasks historically after its accepted merge.

PR42 merged as `4b06a3c97f7067fdc33f58637c3bc746dd48f0da` on 2026-10-17 at
16:18:11 UTC after exact-head CI 16/16 and genuine pinned gate 1 PASS/1344.20s.
PR43 rebased from accepted `3903a1d` onto that exact merge with no conflicts;
range-diff shows all 15 preparation patches equivalent. Merge and accepted parent
trees are identical. PR42 technical task closure and actual commands/results are
recorded in its tasks file; scientific prerequisites remain open.

Before 1.3 only isolated pure synthetic unit/TDD preparation is permitted.
No PR42 edits, publication, real model/corpus run or scientific result.

## 2. TDD implementation

- [x] 2.1 RED/GREEN private exact receipt admission and zero-consume preflight.
- [x] 2.2 RED/GREEN raw and labeled policy diagnostics with availability matrix.
- [x] 2.3 RED/GREEN paired group-within-site resampling and descriptive intervals.
- [x] 2.4 RED/GREEN plus-one tails, Holm ordering/step-down and fixed-label behavior.
- [x] 2.5 RED/GREEN privacy, tamper/replay, resource bounds and complete fixture wiring.

Isolated preparation evidence: mathematical RED `52bc55e`, differential RED
`255dac1`, input/bounds RED `d76e6d3`, authority/privacy RED `a5b4a40` -> first
GREEN `0736176` (41 tests passed in 17.79 seconds). Separate test-oracle/import
corrections do not represent product failures. The cross-fold calibration/test
oracle correction `5317d08` preserves legitimate LOSO overlap between folds.

Independent critique found a P1 aliasing defect in nested aggregate commitments:
RED `89ee81e`; post-validation mutation RED `e4b825f`; exact primitive-type RED
`e98ca13` -> corrective GREEN `25e9b6b7fa49bdabc4d80b47dfbb2714c04bc644`.
The existing single issuance boundary now stores independent primitive snapshots,
including actual type tags, and rechecks binding/parent/receipts/current issuance
after deep validation. No additional authority hierarchy was introduced.

Independent final critique on that executable SHA: mathematical/mechanical GO
(36 directed tests in 7.43 seconds; all 45 tests in 17.46 seconds); authority and
privacy GO (45 tests in 18.82 seconds). No open P0/P1/P2 in either reviewed scope.
Ruff, Black and diff checks passed. These were preparation gates, not exact-head
CI or publication acceptance. Subsequent full acceptance is recorded below.

Maximum admitted synthetic work-bound measurement (not a scientific benchmark):
1536 rows, 512 groups per each of three sites, 10000 replicates, four summaries;
Python 3.13.14 / Windows 11 build 26200, source unchanged from `25e9b6b`.
Observed helper elapsed time: 95.173835 seconds. Process RSS sampled every 50 ms
peaked at 38948864 bytes; this is sampled process memory, not an allocator-wide
or cross-platform guarantee. No corpus/model/network input was used. The fixed
bound is 10000 times the sum of site group counts (at most 15.36 million draws),
with two 5x6 integer confusion-matrix additions per draw and four arrays of 10000
aggregate replicates. No duplicated private rows or repeated baseline fitting.
The measurement does not substitute for unavailable per-example Laya latency.

## 3. Technical acceptance

- [x] 3.1 Directed and historical/site/mock/backend regression gates.
- [x] 3.2 Independent critique/audit without P0/P1/P2, exact-head CI PASS.
- [x] 3.3 Record numerical fixture outputs separately from scientific BLOCKED status.

Post-rebase directed Linux/non-root/network-none regression: 212 passed in 24.60
seconds, using trusted helper image
`sha256:90d42f3d776d8d3434982bd00bd815166d496dd3195cea2fa6b6bbcb0d934475`.
It covered the three new statistics test files plus legacy readiness/safety/CLI,
preregistration issuance/preregistration/corpus and runner. No Docker socket was
mounted for this pure regression. It did not replace full CI acceptance, which
was subsequently observed and is recorded below by PR44.

Historical acceptance after PR43 merge: frozen accepted HEAD
`120f28fafe37973898129f9b681eef70e821b1c4`, source `959ba25` equivalent to the
independently reviewed pre-rebase `25e9b6b`. CI `39049102033`: SUCCESS 16/16.
Python job `117443856001`: 3626 passed / 61 skipped / 26 warnings in 1030.96
seconds (17:10). Backend/frontend/API and historical/site/mock gates passed.
Frozen-candidate Linux repeat: 45 passed in 12.40 seconds. Ruff/Black, strict
OpenSpec and final documentary dispatch GO passed with no P0/P1/P2 open.

PR43 merged on 2026-10-17 at 16:40:52 UTC as
`41ab3d3700ddad6e1cd0b466259cbcd51ff9aa5e`, guarded by exact HEAD; its merge
tree is identical to the accepted candidate. No tracked source/tree change
between acceptance and merge. The unchanged PR42 pinned-runtime/model gate
was not repeated for this pure host-side arithmetic change. No corpus/holdout,
model inference, calibration fit or real scientific scoring was performed.
Section 4 remains open. These checkboxes close technical acceptance only.

Public rebased TDD history: mathematical RED `475aff9`, authority/privacy RED
`55834cd`, bounds RED `5177c95`, differential mathematical RED `0843985` ->
first GREEN `d4e2ad5`. Critique REDs `7f48a5b` (nested aliasing), `848822e`
(post-validation mutation), `c64d087` (exact primitive types) -> corrective
GREEN `959ba25`. Earlier SHAs in the preparation narrative are pre-rebase;
these public commits retain the actual RED-before-GREEN order.

Numerical fixture examples, not observed scientific study results: the paired
balanced good/bad-group golden fixture has observed global delta 0, descriptive
bounds [-2/3, 2/3] and plus-one tail 6528/10001. Unequal-site sample counts retain
an equal-site mean of 1/3 rather than a pooled estimate. The unequal-group-size
fixture has global delta -3/11 and tail 7531/10001. Tests verify inclusive margin
and Holm boundaries, weighted ECE and fixed five-label abstention semantics.
Every privately issued fixture result still reports MECHANICAL_FIXTURE_ONLY_BLOCKED,
unavailable calibration/latency/real admissions and false scientific/shadow/
production claims; those numerical examples cannot replace external evidence.

## 4. Scientific prerequisites — not supplied, not inferred from fixtures

- [ ] 4.1 Real private corpus and custody independently admitted.
- [ ] 4.2 Exact real baseline producer and paired predictions admitted.
- [ ] 4.3 Real analysis RNG/quantile/output-stage profile externally frozen.
- [ ] 4.4 Calibration method, fitted evidence and latency inputs admitted.

These scientific gates remain open; their absence does not authorize fake values,
retrospective methodological choices or a positive readiness verdict.
