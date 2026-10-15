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

### Requirement: Generated replay types have bounded ownership

The historical replay and CICYTEX defense API modules SHALL consume generated component and
operation types. No other product module SHALL consume the generated schema in this change,
and the two migrated modules SHALL NOT duplicate their replay DTOs, use unsafe casts, or
replace closed response fields with unconstrained records.

#### Scenario: Product consumers are enumerated

- **WHEN** generated-schema imports in product source are inspected
- **THEN** exactly the historical replay and CICYTEX defense API modules import them
- **AND** both bind their public contracts to generated operation or component aliases

### Requirement: Type adoption preserves observable client behavior

Generated type adoption SHALL preserve request paths, methods, query encoding, headers,
request bodies, optional-field omission, public client names and established error behavior.
It SHALL NOT add a generated runtime transport or payload normalization layer.

#### Scenario: Existing clients make equivalent requests

- **WHEN** either migrated client issues each supported request
- **THEN** its URL, method, headers and serialized body match the pre-migration contract
- **AND** non-success responses retain their established error class and message behavior

### Requirement: Nullable replay state remains safe and causal

The CICYTEX UI SHALL omit unavailable null metric slots rather than fabricate values. The
historical UI SHALL treat both absent and null target observations as unrevealed, preserve
false and true observations, and prevent a late response for an earlier session from
overwriting the current session.

#### Scenario: Unrevealed and late states do not create false evidence

- **WHEN** generated payloads contain omitted or null observations, null metrics, or a late
  response from a previous session
- **THEN** the UI renders no fabricated observation or metric
- **AND** only the currently selected session may update visible replay state
