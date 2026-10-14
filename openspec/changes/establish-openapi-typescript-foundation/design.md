# Design: deterministic OpenAPI-to-TypeScript foundation

## Pure contract core

The core receives already materialized Python values or bytes.  It serializes
OpenAPI with recursively sorted object keys, unchanged array order, compact
UTF-8 JSON and one terminal LF.  It neither imports the FastAPI application nor
reads files, starts a server, invokes processes or accesses the network.

Operation diagnostics are ordered independently of input dictionary order and
report every missing, blank or duplicated identifier in one failure.  The
artifact manifest commits exact OpenAPI and TypeScript bytes by both size and
SHA-256; semantic equivalence does not authorize different artifact bytes.

## Local generator boundary

`openapi-typescript` is an exact frontend development dependency and is invoked
by an npm script from `frontend/node_modules`.  The script must not use `npx`, a
URL or a running backend.  Acquisition of dependencies remains the ordinary
lockfile-controlled install step and is not part of generation.

The exporter imports the FastAPI application in-process and calls
`app.openapi()` directly.  It never starts Uvicorn and never fetches
`/openapi.json`.  Generate writes into a caller-selected directory.  Check
always regenerates in a temporary directory and compares all three tracked
artifacts (`openapi.json`, `openapi.ts`, manifest), so a failing check cannot
repair or partially overwrite the evidence it is evaluating.

The lock must be installable by plain `npm ci`.  In particular, the TypeScript
version must satisfy the peer range declared by the exact
`openapi-typescript` package; force and legacy-peer overrides are not accepted.

## Type safety and rollout boundary

The generated source is checked through a TypeScript AST representation.
Nested `AnyKeyword` nodes fail; text containing the word `any` in comments or
string literals is not code and remains valid.  This change may generate only
the schema types and their manifest.  No generated client exists and no product
module imports generated output until a later, separately tested migration.
