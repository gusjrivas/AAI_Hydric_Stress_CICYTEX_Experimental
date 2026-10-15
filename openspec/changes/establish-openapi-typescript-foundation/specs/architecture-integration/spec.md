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

#### Scenario: current application schema is exported without HTTP

- **WHEN** the repository exports the FastAPI schema
- **THEN** it calls the in-process application's `openapi()` method
- **AND** all real operations have complete unique identifiers
- **AND** no server, URL or network client participates.

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

#### Scenario: generation and check are reproducible

- **GIVEN** the exact locally installed generator and unchanged application schema
- **WHEN** artifacts are generated twice
- **THEN** all three artifact files are byte-identical
- **AND** a clean check succeeds without rewriting them.

#### Scenario: drift check is read-only

- **GIVEN** drift in the OpenAPI, TypeScript or manifest artifact
- **WHEN** check mode runs
- **THEN** it fails
- **AND** every tracked byte remains unchanged.

#### Scenario: the local generator installation is executable

- **WHEN** plain `npm ci` installs the exact frontend lock
- **THEN** its TypeScript version satisfies the generator's declared peer range
- **AND** the binary under `node_modules/.bin` executes twice deterministically
- **AND** no force, legacy-peer, `npx` or URL fallback is used.

#### Scenario: platform-independent contract gate

- **GIVEN** a temporary output path containing spaces
- **WHEN** the real locked generator runs on Windows and Linux
- **THEN** both generations match the three committed artifact bytes and hashes
- **AND** checkout attributes preserve those exact LF bytes
- **AND** no generated client or product import is introduced.

#### Scenario: independent CI detects generated drift

- **WHEN** the independent `api-contract` job runs on Windows and Linux
- **THEN** it uses Python 3.11, Node 22 and the exact backend constraints
- **AND** it runs plain `npm ci`, the focused toolchain tests and `api:check`
- **AND** generation starts no server and uses no HTTP, URL or `npx` fallback.

#### Scenario: generator integration remains stable and type-checked

- **WHEN** the complete frontend suite runs under concurrent test load
- **THEN** the real local generator integration retains all byte assertions and
  has an explicit bounded subprocess timeout
- **AND** adding generated declarations does not globally exclude test sources
  from mandatory TypeScript type-check coverage.
