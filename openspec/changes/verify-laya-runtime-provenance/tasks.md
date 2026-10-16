## 1. Architecture and RED contract

- [x] 1.1 Fix the source and checkpoint commits, source `v0.4.2` annotated unsigned tag and exact selected paths.
- [x] 1.2 Separate pinned Git SHA-1 object identity from SHA-256 authority over supplied bytes.
- [x] 1.3 Specify source LICENSE/pyproject and checkpoint README declarations without legal claims.
- [x] 1.4 Specify the exact checkpoint `multilingual` tree and five small-or-LFS links to PR34.
- [x] 1.5 Specify caps, privacy, fail-closed DAG traversal and mix-and-match rejection.
- [x] 1.6 Preserve conservative claims and isolate the bytes-only core from all I/O and productive callers.
- [x] 1.7 RED audit remediation: prove the exact three-function public API and observed-declaration naming.
- [x] 1.8 RED audit remediation: prove README identity exclusion and exact PR34/LFS/DAG-edge bindings.
- [x] 1.9 RED audit remediation: prove local-only `git cat-file` precheck, environment and timeout controls.
- [x] 1.10 RED audit remediation: prove closed `__all__` and exactly three public functions.
- [x] 1.11 RED audit remediation: prove live chunk cap coherence and full structural preflight.
- [x] 1.12 RED audit remediation: prove factory capability secrecy and exact-class forgery rejection.
- [x] 1.13 RED audit remediation: prove the closed role/kind/derived-field matrix.
- [x] 1.14 RED audit remediation: prove deep PR34 ancestry validation in the unit verifier.
- [x] 1.15 P0 audit remediation: prove PR34 plan/receipt/capture-authority/evidence issuance, not shape alone.

## 2. RED tests

- [x] 2.1 Add failing tests for Git object framing, type, size, SHA-1 and SHA-256 authority.
- [x] 2.2 Add failing tests for source commit/tag/tree and Apache declaration selection.
- [x] 2.3 Add failing tests for checkpoint tree, small blobs, LFS pointers and PR34 binding.
- [x] 2.4 Add failing tests for exact caps, privacy, mixed PR34/LFS/edge authorities and canonical evidence.
- [x] 2.5 Add failing tests for exact conservative flags and absent productive callers.
- [x] 2.6 Add failing tests for public exports, live caps and zero-consumption structural preflight.
- [x] 2.7 Add failing tests for forged classes, derived fields and shallow PR34 wrappers.
- [x] 2.8 Add failing tests for `object.__new__`, field/slot clones and shape-only PR34 graphs before object consumption.

## 3. GREEN implementation

- [x] 3.1 Implement the pure bounded Git object validator without adapters or I/O.
- [x] 3.2 Implement exact source and checkpoint provenance plans and evidence.
- [x] 3.3 Implement deep canonical revalidation and privacy-safe summary.
- [x] 3.4 Narrowly harden PR34 issuance so its canonical summary rejects unissued checkpoint graphs.
- [x] 3.5 Require that issuance proof in provenance plan preparation and object-set verification.
- [x] 3.6 Make the module-side issuance registry authoritative; keep `_semantic_capability` as a non-authoritative mirror with weak cleanup.
- [x] 3.7 Enforce 2,048 node/item, 16 MiB aggregate and depth-64 budgets with string/key prechecks before UTF-8.

## 4. Gates

- [x] 4.1 Run focal provenance and inherited PR15–PR34 regressions; all passed.
- [x] 4.2 Run Melchor Romero, Pergamino, CICYTEX and mocked-sensor regressions; all four scenarios passed.
- [x] 4.3 Run Ruff, Black, OpenSpec strict and diff checks; quality and contract checks passed.
- [x] 4.4 Run the opt-in real gate: 5/5 passed on Linux against read-only exact bytes with network disabled.
- [x] 4.5 Obtain independent architecture and merge-gate review; final verdict GO.

## 5. Deferred

- [ ] 5.1 Design secure repository capture separately from the pure core.
- [ ] 5.2 Perform origin/authenticity attestation and legal license review separately.
- [ ] 5.3 Materialize or execute Laya only after their own TDD evidence gates.
