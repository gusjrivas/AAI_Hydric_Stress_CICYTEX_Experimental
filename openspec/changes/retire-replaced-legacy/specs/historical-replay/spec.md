## ADDED Requirements

### Requirement: CICYTEX replay persistence remains durable during legacy retirement

The CICYTEX replay deployment SHALL place its shared session and feedback SQLite database inside
the existing named persistent volume and SHALL NOT rely on the retired feedback-directory
environment variable.

#### Scenario: Deployment binds one coherent durable store

- **WHEN** the CICYTEX Compose deployment is evaluated
- **THEN** `CICYTEX_REPLAY_SESSION_DB` SHALL equal
  `/workspace/cicytex-feedback/cicytex_replay_sessions.sqlite3`
- **AND** `CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON` SHALL use empty-default interpolation
  `${CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON:-}` so a fresh volume requires no legacy file
- **AND** `/workspace/cicytex-feedback` SHALL be mounted from `cicytex-feedback`
- **AND** that volume SHALL retain external name `aai-cicytex-experiment-feedback`
- **AND** `CICYTEX_REPLAY_FEEDBACK_DIR` SHALL be absent

#### Scenario: Live data is migrated fail-closed

- **GIVEN** an existing replay SQLite database
- **WHEN** its deployment path changes
- **THEN** writers SHALL be quiesced or SQLite online backup SHALL be used
- **AND** WAL state SHALL be handled coherently
- **AND** destination SHA-256, size, `PRAGMA integrity_check`, session count and feedback count
  SHALL be recorded and compared
- **AND** the source database and original `feedback.json` SHALL remain available for rollback
  until destination verification completes
- **AND** any failed check SHALL abort cutover without deleting or overwriting the source

#### Scenario: Existing legacy feedback is imported explicitly

- **GIVEN** the preserved volume contains the historical `feedback.json`
- **WHEN** an existing deployment enters its controlled migration window
- **THEN** its operator SHALL override `CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON` with exactly
  `/workspace/cicytex-feedback/feedback.json`
- **AND** an empty override SHALL remain valid for a fresh deployment
- **AND** any other non-empty path SHALL fail before migration

#### Scenario: Compatibility remains available until separately sunset

- **WHEN** obsolete deployment configuration is retired
- **THEN** SQLite schema-v1 migration and JSON/JSONL importers SHALL remain unchanged
- **AND** the existing `feedback.json` SHALL be presented to the explicit CICYTEX compatibility
  importer
- **AND** no stored session, feedback record, backup or rollback artifact SHALL be deleted

### Requirement: Test-only replay doubles do not remain in production packages

An in-memory `SessionRepository` used only by tests SHALL live under `tests/helpers`; production,
script, configuration and recovery paths SHALL NOT import or dynamically resolve it.

#### Scenario: In-memory session adapter is retired from production

- **GIVEN** all replay and CICYTEX tests import the synchronized repository from `tests/helpers`
- **WHEN** the production tree is audited
- **THEN** `src/historical_replay/adapters/in_memory_sessions.py` SHALL be absent
- **AND** no module under `src`, `backend/app`, `scripts`, `config` or `recovery` SHALL import or
  dynamically name `historical_replay.adapters.in_memory_sessions`
- **AND** duplicate-ID conflicts, atomic updates and `with_session` serialization SHALL remain
  covered by the migrated tests

### Requirement: CICYTEX training contracts have one canonical module

Feature construction, temporal split types and split functions SHALL be imported from
`experiment_runner.cicytex.training_protocol`; the experiment runner SHALL NOT republish private
compatibility aliases or retain unused partition imports.

#### Scenario: Legacy experiment training aliases are retired

- **GIVEN** tests and provenance consumers use the canonical training protocol
- **WHEN** `experiment.py` is inspected structurally
- **THEN** it SHALL NOT import or bind `TemporalSplit`, `build_features`, `temporal_split`, `_part`
  or the unused `select_partition`
- **AND** `FEATURES`, `FAMILY_PARAMS` and `prepare_horizon` SHALL remain the runner's canonical
  dependencies
- **AND** feature boundaries, temporal partitions, experiment outputs and provenance equivalence
  SHALL remain unchanged
