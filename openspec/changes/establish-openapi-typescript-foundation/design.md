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

`src/openapi_typescript_exporter.py` is the sole tooling successor of the pure
contract core.  It imports and calls the core's public canonicalization,
operation-ID and manifest functions directly.  Backend product modules and all
other `src` modules remain forbidden callers; dynamic imports or copied local
implementations are not alternative boundaries.

The lock must be installable by plain `npm ci`.  In particular, the TypeScript
version must satisfy the peer range declared by the exact
`openapi-typescript` package; force and legacy-peer overrides are not accepted.

The independent `api-contract` CI job runs the same contract on Windows and
Linux with Python 3.11 and Node 22.  It installs the backend schema environment
under `backend/openapi-schema-constraints.txt`, installs the exact npm lock,
runs the Python and local-binary toolchain tests, and finishes with the
read-only `api:check`.  The three committed generated files are checkout-opaque
in `.gitattributes`, so their LF bytes and hashes cannot vary by platform.

The current npm audit reports two inherited high-severity findings:
`source-map-js@1.2.1` through the existing Vite/jsdom toolchain and
`undici@8.10.0` through existing jsdom.  Both were present before this change,
are transitive development dependencies, and are not bundled or imported by
the application.  Their reported attack surfaces require processing hostile
source maps or network/WebSocket traffic, while this generator consumes the
repository-owned schema offline.  They are therefore recorded as non-blocking
for this foundation PR and remain dependency-maintenance work; this assessment
does not downgrade or auto-fix them.

The new real-generator integration test may use an explicit 30-second timeout
because it starts two cross-platform subprocesses; the timeout changes no
assertion or success criterion.  Adding generated declarations must not be
used to remove tests from TypeScript coverage: the application build continues
to type-check test sources, or an equally mandatory test type-check target runs
as part of the same build gate.

## Type safety and rollout boundary

The generated source is checked through a TypeScript AST representation.
Nested `AnyKeyword` nodes fail; text containing the word `any` in comments or
string literals is not code and remains valid.  This change may generate only
the schema types and their manifest.  No generated client exists and no product
module imports generated output until a later, separately tested migration.
