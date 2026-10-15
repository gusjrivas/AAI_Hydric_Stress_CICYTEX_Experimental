## ADDED Requirements

### Requirement: Producer clients derive successful HTTP contracts from canonical OpenAPI

The producer catalog, readings, forecast and historical clients SHALL derive their successful
request and response types from the checked-in generated OpenAPI schema while preserving their
public export names.

#### Scenario: Catalog and readings complete the first migration slice

- **WHEN** the catalog and readings clients are type-checked
- **THEN** their public DTO aliases and function responses SHALL bind to the exact catalog and
  readings operation IDs
- **AND** manual or import-only duplicate contracts SHALL fail the architecture gate

#### Scenario: Readings preserve complete generated payloads

- **WHEN** a successful readings response contains `input_roles` and nullable measurements
- **THEN** the client SHALL return that payload unchanged
- **AND** SHALL NOT narrow away generated fields or nullability

### Requirement: Type adoption preserves observable producer transport

Generated type adoption SHALL NOT change URLs, methods, query omission, encoding, response
identity, error classes/messages or producer-specific base URL selection.

#### Scenario: Optional catalog filter is absent

- **WHEN** sensors are listed without a sector
- **THEN** the request SHALL omit `sector_id` entirely

#### Scenario: Producer facade is unavailable

- **WHEN** catalog or readings returns a bodyless 404
- **THEN** the existing `ProducerV2UnavailableError` behavior SHALL remain unchanged
