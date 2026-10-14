## ADDED Requirements

### Requirement: CICYTEX feedback is transactionally durable

The system SHALL persist CICYTEX replay feedback in schema v2 of the session
database using the natural prediction identity and SHALL serialize feedback
registration with session reset across processes.

#### Scenario: schema v1 is upgraded without session loss

- **GIVEN** a valid schema-v1 database containing replay sessions
- **WHEN** the durable repository starts
- **THEN** it atomically upgrades to closed schema v2
- **AND** every valid session remains byte-semantically equivalent.

#### Scenario: legacy JSON import is fail-closed

- **GIVEN** a configured bounded legacy feedback document
- **WHEN** its strict schema and digest are valid
- **THEN** it is imported exactly once in the v1-to-v2 transaction
- **AND** malformed, foreign, partial, oversized or changed input leaves no
  partially imported feedback
- **AND** validation or import failure leaves the original database bytes,
  schema-v1 metadata and session rows unchanged.

#### Scenario: legacy feedback is bound to a compatible replay session

- **GIVEN** a structurally valid legacy feedback record
- **WHEN** no session has its natural sensor, emission and horizon identity
- **OR** its simulated time is later than every matching session's last observation
- **OR** its simulated time is before the emission-plus-horizon target
- **THEN** migration fails closed with zero imported feedback
- **AND** the schema-v1 database remains byte-identical.

#### Scenario: legacy feedback batch validation is atomic

- **GIVEN** a legacy document containing valid and incompatible records
- **WHEN** migration validates the complete batch
- **THEN** one incompatible record rejects the entire batch before commit
- **AND** no valid sibling record, schema change or digest is persisted.

#### Scenario: reset does not invalidate historical legacy feedback

- **GIVEN** a matching replay session whose mutable revealed clock was reset
- **WHEN** the legacy simulated time remains between target and last observation inclusive
- **THEN** the otherwise valid legacy feedback is imported once
- **AND** current `revealed_through` is not treated as the historical upper bound.

#### Scenario: reset and feedback have one serial order

- **WHEN** independent processes race reset and feedback registration
- **THEN** feedback either commits against the revealed session or is rejected
  after reset
- **AND** no stale future feedback is persisted.

### Requirement: historical feedback is append-only and isolated

The system SHALL persist historical-package feedback in an isolated SQLite
repository, ordered by append sequence and namespaced by package identity.

#### Scenario: legacy JSONL import is atomic and unique

- **GIVEN** a bounded valid legacy JSONL file
- **WHEN** the historical repository starts
- **THEN** rows are imported once in file order with a recorded digest
- **AND** malformed or partial input imports zero rows.

#### Scenario: reset changes visibility, not history

- **GIVEN** durable feedback for a revealed target
- **WHEN** the simulated clock is reset before that target
- **THEN** feedback is hidden but remains persisted and becomes visible again
  after advancing.

### Requirement: persistence failures remain private

Routers SHALL preserve existing successful payloads and 201/409 behavior and
SHALL translate repository failures to a sanitized 503 response without paths,
SQL, legacy bytes or feedback contents.

#### Scenario: a repository failure reaches HTTP

- **WHEN** feedback persistence or decoding fails
- **THEN** the endpoint returns the existing sanitized 503 envelope
- **AND** neither the response nor logs contain paths, SQL, imported bytes or
  feedback content.
