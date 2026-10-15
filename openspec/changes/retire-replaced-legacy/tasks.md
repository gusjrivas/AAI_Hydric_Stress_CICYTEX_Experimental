## 1. RED durable deployment contract

- [x] 1.1 Specify the exact SQLite database, optional empty-default legacy setting, and exact
  migration-only JSON override under the preserved CICYTEX feedback volume.
- [x] 1.2 Reject the obsolete environment variable and incoherent path/mount/volume mutations.
- [x] 1.3 Document quiesced or online-backup migration, integrity, row-count and rollback evidence.

## 2. GREEN deployment correction

- [x] 2.1 Bind Compose to the durable SQLite path and remove only the obsolete variable.
- [x] 2.2 Execute focused and regression gates without modifying persisted data.

## 3. Bounded retirement audit

- [ ] 3.1 Prove zero productive, dynamic, script, configuration and recovery consumers per target.
- [ ] 3.2 Retain compatibility importers and schema migration until an explicit sunset gate exists.
- [ ] 3.3 Retire approved test/config residue in independent TDD slices.

## 4. Test-only session repository retirement

- [x] 4.1 Move the synchronized in-memory session repository into `tests/helpers` without changing
  conflict, update or `with_session` semantics.
- [x] 4.2 Migrate replay-session tests and CICYTEX dependency fakes to the test-only helper.
- [x] 4.3 Remove the production-path in-memory adapter after the absence and zero-consumer gate is
  RED first and all replay regressions remain green.

## 5. Canonical CICYTEX training seam

- [x] 5.1 Migrate experiment and provenance tests to import feature/split contracts directly from
  `training_protocol`.
- [x] 5.2 Specify AST mutation evidence against legacy aliases and the unused partition import.
- [x] 5.3 Remove the aliases and unused import from `experiment.py` while preserving the complete
  experiment, protocol and provenance regression suites.

## 6. Offline replay-storage cutover staging

- [x] 6.1 Specify source hashing, SQLite backup/WAL discipline, repository-owned import, read-only
  verification, privacy-safe evidence and atomic publication.
- [x] 6.2 Specify explicit empty-source behavior and fail closed when legacy feedback lacks matching
  session lineage.
- [x] 6.3 Publish the operator runbook while keeping the active volume and all captured inputs
  immutable.
- [ ] 6.4 Implement `scripts/stage_cicytex_replay_cutover.py` and pass the focused failure,
  privacy, alias and regression gates before any live cutover.

## 7. Source snapshot and sidecar safety hardening

- [x] 7.1 Specify a deterministic concurrent-WAL race, source snapshot evidence, destination count
  comparison, staged byte size and symlink-ancestor rejection.
- [x] 7.2 Document WAL byte stability and the narrower SHM ownership guarantee without claiming
  byte identity for ephemeral SQLite reader marks.
- [ ] 7.3 Reject late sidecars without deleting source files and emit the complete comparison
  evidence before declaring the staging tool ready.

## 8. Preserved legacy-feedback discovery

- [x] 8.1 Specify exact Compose discovery, absent-file fresh startup, present-file repository
  validation and explicit-override conflict rejection.
- [x] 8.2 Document why feedback-only volumes must block instead of silently bootstrapping an empty
  database.
- [ ] 8.3 Implement discovery-aware configuration and pass Compose, fresh-volume, migration and
  private-503 regressions.
