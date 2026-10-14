## ADDED Requirements

### Requirement: OpenAPI type generation is deterministic and offline

The repository SHALL canonicalize an in-memory OpenAPI document to compact
UTF-8 JSON with sorted object keys, unchanged array order and one terminal LF.
Generation SHALL use one exact lockfile-controlled local `openapi-typescript`
version without starting the backend, using HTTP, `npx` or network access.

#### Scenario: equivalent mappings produce identical bytes

- **GIVEN** two OpenAPI values that differ only in object-key insertion order
- **WHEN** each value is canonicalized
- **THEN** their bytes are identical UTF-8 with LF termination
- **AND** array element order is preserved.

#### Scenario: operation identifiers fail closed

- **GIVEN** operations with missing, blank or duplicate `operationId` values
- **WHEN** the document is validated
- **THEN** all violations are reported in deterministic path/method order
- **AND** input mapping order cannot change the diagnostics.

### Requirement: Generated artifacts are integrity-bound but not runtime code

The foundation SHALL commit the exact OpenAPI and TypeScript bytes by size and
SHA-256 and SHALL reject a mismatch in either dimension.  Generated TypeScript
SHALL contain no `AnyKeyword` syntax node.  The foundation SHALL NOT generate a
client or be imported by production backend/frontend modules in this change.

#### Scenario: artifact tampering fails

- **GIVEN** a manifest created for exact OpenAPI and TypeScript bytes
- **WHEN** either content, size or digest differs
- **THEN** verification fails closed.

#### Scenario: syntax is distinguished from text

- **GIVEN** a nested TypeScript `AnyKeyword` node
- **WHEN** the generated AST is validated
- **THEN** validation fails
- **BUT** the word `any` in a comment or string literal remains valid.
