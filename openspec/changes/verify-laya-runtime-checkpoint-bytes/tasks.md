## 1. RED: pure checkpoint contract

- [x] Specify exact PR17-bound plan and five ordered descriptors.
- [x] Specify bounded streaming size/SHA-256/LFS verification and private errors.
- [x] Specify immutable receipts, deep seals, conservative evidence and summary.

## 2. RED: secure filesystem capture

- [x] Specify canonical-root and exact-inventory preflight.
- [x] Specify secure descriptors, file type/link checks and TOCTOU final sweep.
- [x] Specify close-before-seal, all-or-nothing failures and external real gate.

## 3. GREEN

- [ ] Implement `human_feedback.runtime_checkpoint` without I/O.
- [ ] Implement Linux `filesystem_checkpoint` capture without public finalizers.
- [ ] Make the focal and inherited Laya suites pass.
- [ ] Run the real checkpoint gate and record separate release evidence.

## 4. CI and closure

- [x] Specify an Ubuntu/Windows focal CI job without external checkpoint bytes.
- [ ] Add the workflow job and run both matrix legs.
- [ ] Run Ruff, Black, OpenSpec strict validation and diff checks.
