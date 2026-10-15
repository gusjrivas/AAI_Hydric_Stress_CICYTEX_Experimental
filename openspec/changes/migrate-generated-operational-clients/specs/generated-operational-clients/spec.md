# generated-operational-clients Specification

## ADDED Requirements

### Requirement: Operational clients use generated contracts with bounded ownership

Forecast, quality, lineage and sensor-laboratory API modules SHALL consume generated component
and operation types. Together with historical replay and CICYTEX defense, exactly six product
modules SHALL import the generated schema. Migrated modules SHALL NOT duplicate HTTP DTO
interfaces or use unsafe casts and unconstrained records to bypass the generated contract.

#### Scenario: Product consumers are exactly enumerated

- **WHEN** product imports of the generated schema are inspected
- **THEN** only the six approved API modules consume it
- **AND** each migrated module binds its public response to its approved operation

### Requirement: Observable HTTP behavior remains unchanged

Type adoption SHALL preserve URLs, encoding, methods, headers, bodies, public client names and
existing error classes, statuses and messages. It SHALL NOT add a generated runtime client or
payload normalization.

#### Scenario: Requests remain equivalent after migration

- **WHEN** any migrated operation is invoked with the same input
- **THEN** the emitted request is identical to the pre-migration request
- **AND** success and non-success responses keep their established behavior

### Requirement: Operational safety semantics remain explicit

A missing quality dataset SHALL remain a legitimate null result on HTTP 404. Invalid lineage
SHALL continue to fail closed rather than become an empty chain. Laboratory readings SHALL
remain synthetic and stale or unmounted work SHALL NOT update the current scenario. Forecast
missing-dataset sanitization and late-response isolation SHALL remain unchanged.

#### Scenario: Absence, corruption and stale work cannot fabricate evidence

- **WHEN** quality is absent, lineage is invalid, a laboratory session changes, or a forecast
  response arrives for an inactive sensor
- **THEN** each established empty, error or stale-response guard is preserved
- **AND** no real provenance, empty lineage or current forecast is fabricated
