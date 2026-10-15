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
- **AND** `CICYTEX_REPLAY_LEGACY_FEEDBACK_DISCOVERY` SHALL equal
  `/workspace/cicytex-feedback/feedback.json`
- **AND** `/workspace/cicytex-feedback` SHALL be mounted from `cicytex-feedback`
- **AND** that volume SHALL retain external name `aai-cicytex-experiment-feedback`
- **AND** `CICYTEX_REPLAY_FEEDBACK_DIR` SHALL be absent

#### Scenario: Live data is migrated fail-closed

- **GIVEN** an existing replay SQLite database
- **WHEN** its deployment path changes
- **THEN** writers SHALL be quiesced or SQLite online backup SHALL be used
- **AND** WAL state SHALL be handled coherently
- **AND** source-snapshot version, integrity and row counts plus destination SHA-256, size,
  `PRAGMA integrity_check`, session count and feedback count SHALL be recorded
- **AND** destination sessions SHALL equal source-snapshot sessions
- **AND** destination feedback SHALL equal source-snapshot feedback plus validated legacy imports
- **AND** the source database, WAL/SHM sidecars and original `feedback.json` SHALL remain available
  for rollback
  until destination verification completes
- **AND** any failed check SHALL abort cutover without deleting or overwriting the source

#### Scenario: Existing legacy feedback is imported only with session lineage

- **GIVEN** the preserved volume contains the historical `feedback.json`
- **AND** an authoritative captured database contains every matching replay session
- **WHEN** an existing deployment enters its controlled migration window
- **THEN** its operator SHALL override `CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON` with exactly
  `/workspace/cicytex-feedback/feedback.json`
- **AND** the importer SHALL validate every record against that session lineage
- **AND** an empty override SHALL remain valid for a fresh deployment
- **AND** any other non-empty path SHALL fail before migration
- **BUT WHEN** no authoritative session database exists
- **THEN** the JSON SHALL remain unimported and byte-identical for manual reconciliation

#### Scenario: Preserved feedback cannot be hidden by an empty override

- **GIVEN** deployment discovery points to the preserved `feedback.json`
- **WHEN** the explicit override is empty or unset and the discovery file exists
- **THEN** that file SHALL be presented to the repository for complete validation
- **AND** feedback-only or invalid state SHALL fail closed instead of creating an empty database
- **BUT WHEN** the discovery file is absent
- **THEN** a fresh volume SHALL initialize without attempting a legacy import
- **AND WHEN** a non-empty explicit override disagrees with deployment discovery
- **THEN** configuration SHALL fail closed
- **AND** arbitrary explicit paths MAY remain available only when no deployment discovery policy
  is configured

#### Scenario: Compatibility remains available until separately sunset

- **WHEN** obsolete deployment configuration is retired
- **THEN** SQLite schema-v1 migration and JSON/JSONL importers SHALL remain unchanged
- **AND** the existing `feedback.json` SHALL always be preserved
- **AND** it SHALL be presented to the explicit CICYTEX compatibility importer only with an
  authoritative matching session database and full validation
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

### Requirement: Replay storage cutover is staged offline and fail-closed

The project SHALL provide an offline staging tool that creates a new verified replay database
without modifying the source database, WAL/SHM companions, legacy JSON or active named volume.

#### Scenario: Captured source and matching feedback stage atomically

- **GIVEN** a quiesced or SQLite-online-backup source database and optional matching legacy JSON
- **AND** the operator supplies expected SHA-256 values for every input
- **WHEN** a new absent output directory is staged
- **THEN** SQLite backup SHALL capture the database consistently
- **AND** the existing session and CICYTEX-feedback repositories SHALL validate schema and import
- **AND** read-only verification SHALL report schema v2, `PRAGMA integrity_check=ok`, exact session
  and feedback counts, the staged database digest and byte size
- **AND** evidence SHALL report the backup snapshot's version, integrity and row counts
- **AND** destination sessions SHALL equal source-snapshot sessions
- **AND** destination feedback SHALL equal source-snapshot feedback plus validated legacy imports
- **AND** the output SHALL publish atomically only after every check succeeds
- **AND** evidence SHALL contain no absolute path, raw feedback, observation, session identifier or
  other captured content

#### Scenario: Empty source cannot invent feedback lineage

- **GIVEN** the operator explicitly selects `--empty-source`
- **WHEN** no legacy JSON is supplied
- **THEN** an empty verified schema-v2 database MAY be staged
- **BUT WHEN** a non-empty legacy JSON is supplied without a source database
- **THEN** staging SHALL fail closed with no output
- **AND** the JSON SHALL remain byte-identical for manual reconciliation with real sessions

#### Scenario: Unsafe paths and failures never publish

- **WHEN** an input hash differs, any path component is a symlink or alias, the output already
  exists, an import is invalid, verification fails or publication raises
- **THEN** the command SHALL return a stable non-zero private error
- **AND** no partial output SHALL be visible
- **AND** every captured source SHALL remain byte-identical

#### Scenario: A concurrent source sidecar aborts without source mutation

- **GIVEN** no WAL existed at input preflight
- **WHEN** a valid WAL appears before or during SQLite backup
- **THEN** staging SHALL abort without publishing output
- **AND** the tool SHALL NOT delete, replace or truncate that WAL or any source SHM
- **AND** a WAL that existed before capture SHALL remain byte-identical
- **AND** SHM byte identity SHALL NOT be claimed because online-backup readers can update ephemeral
  reader marks
