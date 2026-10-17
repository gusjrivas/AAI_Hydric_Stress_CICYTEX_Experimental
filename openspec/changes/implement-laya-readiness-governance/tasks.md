## 1. Dependency and scope

- [x] 1.1 Read PR43 evidence, frozen preregistration and legacy readiness semantics.
- [x] 1.2 Separate diagnostic gates, scientific availability and authority.
- [x] 1.3 PR43 accepted/merged, exact-merge rebase and actual results recorded.
- [x] 1.4 Close PR43 technical result-dependent tasks historically after acceptance.

PR43 accepted HEAD `120f28fafe37973898129f9b681eef70e821b1c4`, CI
`39049102033` SUCCESS 16/16 (Python 3626 passed / 61 skipped / 1030.96 seconds),
merged 2026-10-17 at 16:40:52 UTC as
`41ab3d3700ddad6e1cd0b466259cbcd51ff9aa5e`. PR44 rebased onto that exact
merge without conflicts; all seven preparation patches equivalent by range-diff,
and the merge tree is identical to PR43's accepted HEAD. Local generated graph
caches were preserved/excluded (JSON line endings normalized by Git only).
PR43 technical task closure records observed results; its scientific section
remains open. Source `8228586` is equivalent to reviewed pre-rebase `a4cd8bf`.

Before 1.3 only isolated pure synthetic specification/TDD work is permitted.
No PR43 tracked changes, publication, real corpus/holdout or model execution.

## 2. TDD implementation

- [x] 2.1 RED/GREEN complete pure PASS/FAIL/BLOCKED precedence and validation.
- [x] 2.2 RED/GREEN frozen thresholds/site coverage/Holm diagnostics and availability.
- [x] 2.3 RED/GREEN exact parent binding, privacy, tamper/clone and mutation windows.
- [x] 2.4 RED/GREEN fixture-only end-to-end BLOCKED with canonical safe report.

Isolated pure preparation: boundary RED `bf2eacf`, rules RED `a60de63` -> first
GREEN `f29a4a0` (40 focal tests and 85 combined statistics/readiness tests passed).
Independent critique then reproduced a P1 privacy defect: equality-overriding
string subclasses could pass reason/claim-name validation and enter canonical
JSON. Causal RED `aee425c` -> corrective GREEN
`a4cd8bffcb9777e307548279febf19207ea7b08c`; exact built-in tuple/string/boolean
shapes are checked before comparison, with an independent primitive snapshot.

Final independent authority/privacy GO: privacy PoC 1/1 PASS, complete boundary
7/7 PASS in 11.42 seconds, no open P0/P1/P2. Independent rules/government GO:
34/34 PASS with no numerical/decision drift, no open P0/P1/P2. Writer combined
suite 86/86 PASS in 24.73 seconds; root Ruff/Black three changed Python files
and diff checks PASS. These were preparation gates, not scientific results.
PR43 dependency is now accepted; PR44 exact-head CI/publication gates remain open.

Pure Linux regression on the frozen corrective source, non-root/network-none,
without Docker socket: 253 passed in 32.06 seconds (new rules/boundary, PR43
statistics and legacy readiness/safety/CLI, corpus/preregistration/runner).
Trusted helper image:
`sha256:90d42f3d776d8d3434982bd00bd815166d496dd3195cea2fa6b6bbcb0d934475`.
Fixture reports evaluate available gates and remain BLOCKED with no scientific,
shadow or production claim. Raw ECE is not relabeled as calibrated/policy ECE;
latency remains NOT_EVALUATED, not zero or bootstrap/batch time.

After exact PR43-merge rebase, the same Linux directed regression repeated:
253 passed in 27.50 seconds. Full source/test Ruff and Black checks passed
(394 files unchanged). Independent architecture-board scope audit found no open
P0/P1/P2 and confirmed actual runner/statistical/government mechanics, not a
constant preflight masquerading as scientific evaluation. Its GO is conditional
on exact-head PR44 CI and final acceptance, not a human GitHub approval.

Codebase Memory `AAI_Hydric_Stress_PR44_FINAL`, generation 2026-10-17T16:37:04Z:
21001 nodes / 68031 edges, zero skipped/unusable source parses, five pre-existing
partial configuration parses and 28 binary images excluded by design. Four
critical paths reported metadata_changed, so claims used exact source fallback;
no complete-coverage claim. Both generated caches stay outside the PR.

## 3. Technical acceptance and handoff

- [ ] 3.1 Directed Linux and historical/site/mock/backend/frontend regressions.
- [ ] 3.2 Independent critique/audit with no open P0/P1/P2 and exact-head CI.
- [ ] 3.3 Final architecture/technical-plan report, reproducible status and limitations.

## 4. External scientific prerequisites — not completed by code/tests

- [ ] 4.1 Independently admitted real private corpus/custody and exact baseline.
- [ ] 4.2 Externally frozen real analysis/output-stage/calibration profile and fit.
- [ ] 4.3 Required actual measurements and independent scientific evaluation.

These remain open if unavailable. Technical closure with BLOCKED is not scientific
closure, shadow enablement, production authorization or completion of Trabajo Final.
