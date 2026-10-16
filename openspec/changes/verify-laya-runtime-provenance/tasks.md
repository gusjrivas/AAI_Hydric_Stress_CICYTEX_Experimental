## 1. Architecture and RED contract

- [x] 1.1 Fix the source and checkpoint commits, source `v0.4.2` annotated unsigned tag and exact selected paths.
- [x] 1.2 Separate pinned Git SHA-1 object identity from SHA-256 authority over supplied bytes.
- [x] 1.3 Specify source LICENSE/pyproject and checkpoint README declarations without legal claims.
- [x] 1.4 Specify the exact checkpoint `multilingual` tree and five small-or-LFS links to PR34.
- [x] 1.5 Specify caps, privacy, fail-closed DAG traversal and mix-and-match rejection.
- [x] 1.6 Preserve conservative claims and isolate the bytes-only core from all I/O and productive callers.

## 2. RED tests

- [ ] 2.1 Add failing tests for Git object framing, type, size, SHA-1 and SHA-256 authority.
- [ ] 2.2 Add failing tests for source commit/tag/tree and Apache declaration selection.
- [ ] 2.3 Add failing tests for checkpoint tree, small blobs, LFS pointers and PR34 binding.
- [ ] 2.4 Add failing tests for caps, privacy, mixed authorities and canonical evidence.
- [ ] 2.5 Add failing tests for exact conservative flags and absent productive callers.

## 3. GREEN implementation

- [ ] 3.1 Implement the pure bounded Git object validator without adapters or I/O.
- [ ] 3.2 Implement exact source and checkpoint provenance plans and evidence.
- [ ] 3.3 Implement deep canonical revalidation and privacy-safe summary.

## 4. Gates

- [ ] 4.1 Run focal provenance and inherited PR15–PR34 regressions.
- [ ] 4.2 Run Melchor Romero, Pergamino, CICYTEX and mocked-sensor regressions.
- [ ] 4.3 Run Ruff, Black, OpenSpec strict and diff checks.
- [ ] 4.4 Run the opt-in real gate over pre-captured objects and exact PR34 evidence.
- [ ] 4.5 Obtain independent architecture and merge-gate review.

## 5. Deferred

- [ ] 5.1 Design secure repository capture separately from the pure core.
- [ ] 5.2 Perform origin/authenticity attestation and legal license review separately.
- [ ] 5.3 Materialize or execute Laya only after their own TDD evidence gates.

