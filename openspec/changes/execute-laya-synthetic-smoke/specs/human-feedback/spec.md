## ADDED Requirements

### Requirement: Closed synthetic execution has separate authority

The system SHALL prepare a synthetic execution plan only from an exact live
issued PR40 runtime. Preparation SHALL perform no I/O and SHALL NOT imply an
available executor or executed inference.

#### Scenario: Preparation binds a live runtime without executing it

- **GIVEN** an exact live issued runtime and the fixed synthetic profile
- **WHEN** a smoke plan is prepared
- **THEN** both execution claims remain false and no external operation occurs

#### Scenario: Rebound or revoked authority is rejected

- **GIVEN** cloned, revoked, replaced or deeply mutated predecessor authority
- **WHEN** preparation or validation is requested
- **THEN** validation fails privately before external execution

### Requirement: Synthetic smoke never grants scientific eligibility

The system SHALL issue executor/inference evidence only after two bounded
canonical-equal synthetic runs, strict output validation and owned child cleanup.
It SHALL NOT elevate scientific completion, sufficiency, shadow or production.

#### Scenario: Successful synthetic execution remains non-scientific

- **GIVEN** two successful isolated runs of the fixed synthetic input
- **WHEN** canonical outputs match and cleanup completes
- **THEN** only executor/inference claims may become true, without scientific eligibility

#### Scenario: Failure cannot produce execution authority

- **GIVEN** timeout, OOM, schema drift, nonfinite output, disagreement or cleanup failure
- **WHEN** a smoke execution is attempted
- **THEN** no execution authority is issued and only owned cleanup may be retried
