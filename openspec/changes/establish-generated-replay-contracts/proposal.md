# Change: Establish generated replay contracts

## Why

The CICYTEX replay routes currently return untyped dictionaries. Their OpenAPI success
responses therefore cannot provide a stable foundation for generated TypeScript clients,
even though the HTTP payloads are already exercised by the scientific replay tests.

## What Changes

- Give the CICYTEX catalog, session, prediction, reading, metric and feedback payloads
  closed nominal response schemas.
- Preserve all current status codes, JSON keys and explicit nullable values.
- Align historical and CICYTEX feedback validation-state literals.
- Preserve historical replay's omission of unrevealed optional fields.
- Regenerate the deterministic OpenAPI/TypeScript artifacts and adopt their component
  and operation types in exactly the historical replay and CICYTEX defense clients.
- Preserve both clients' requests, error behavior, nullable rendering and late-response
  isolation while replacing duplicated DTO declarations.

## Impact

This phase changes the backend/OpenAPI contract foundation, regenerates its deterministic
artifacts and adopts generated types in exactly two existing frontend clients. It does not
introduce a generated runtime client, migrate other consumers, change replay persistence,
or change scientific calculations.
