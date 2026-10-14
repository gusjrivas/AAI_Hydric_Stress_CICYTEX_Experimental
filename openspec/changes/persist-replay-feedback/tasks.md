## 1. RED contracts

- [x] 1.1 Specify schema v1-to-v2 migration, session preservation and closed DDL.
- [x] 1.2 Specify one-time bounded CICYTEX JSON import and digest binding.
- [x] 1.3 Specify natural-key conflicts and atomic feedback/reset ordering.
- [x] 1.4 Specify historical SQLite append/import/isolation/concurrency behavior.
- [x] 1.5 Specify HTTP compatibility, private 503 mapping, DI and AST boundaries.
- [x] 1.6 Specify readable imports, single-owner bootstrap and repeatable HTTP isolation.
- [x] 1.7 Specify legacy feedback binding to compatible session identity and clock.
- [x] 1.8 Specify target lower bound, atomic mixed batches and multi-session acceptance.

## 2. GREEN implementation

- [ ] 2.1 Add CICYTEX feedback domain/service/repository port.
- [ ] 2.2 Upgrade the session adapter to closed schema v2 and atomic registration.
- [ ] 2.3 Add bounded one-time legacy CICYTEX import.
- [ ] 2.4 Add the historical SQLite feedback adapter and JSONL import.
- [ ] 2.5 Wire administrator-controlled dependencies and sanitized HTTP failures.
- [ ] 2.6 Remove boundary evasions and make legacy migration bootstrap atomic.
- [ ] 2.7 Reject legacy feedback without a compatible session identity and clock.
- [ ] 2.8 Enforce complete-batch temporal validation before migration commit.

## 3. Verification

- [ ] 3.1 Pass unit, multiprocessing and restart tests.
- [ ] 3.2 Pass CICYTEX, Melchor Romero, Pergamino, laboratory/mock regressions.
- [ ] 3.3 Pass Black, Ruff, strict OpenSpec and diff-check.
