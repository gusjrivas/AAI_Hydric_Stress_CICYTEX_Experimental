# generated-replay-contracts Specification

## ADDED Requirements

### Requirement: CICYTEX success responses are nominal and closed

The API SHALL describe catalog, session, prediction, reading, metric and feedback data
with named OpenAPI schemas. Every object reachable from catalog or session SHALL reject
unknown properties and SHALL NOT expose an unconstrained additional-properties map.

#### Scenario: All successful CICYTEX routes reference nominal schemas

- **WHEN** the application OpenAPI document is generated
- **THEN** catalog and feedback reference their nominal response components
- **AND** create, get, advance and reset reference the same nominal session component

### Requirement: Existing replay JSON remains compatible

Adding schemas SHALL preserve successful status codes and exact response bodies.
CICYTEX unrevealed values SHALL remain explicit JSON nulls. Historical prediction fields
that are not yet revealed SHALL remain absent.

#### Scenario: A new CICYTEX session hides the future explicitly

- **WHEN** a session is created before its target date
- **THEN** observation, label, outcome and feedback keys are present with null values
- **AND** the response still has status 201

### Requirement: Feedback validation states use one vocabulary

Replay feedback request and response schemas SHALL restrict `estado_validacion` to
`confirmada` or `rechazada`.

#### Scenario: Generated contracts see the same request and response literal

- **WHEN** the OpenAPI component schemas are inspected
- **THEN** historical requests, historical entries and CICYTEX feedback expose the same
  two-value enumeration
