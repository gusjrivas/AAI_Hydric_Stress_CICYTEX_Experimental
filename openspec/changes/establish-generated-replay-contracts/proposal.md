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

## Impact

This phase changes only the backend/OpenAPI contract foundation. It does not generate or
adopt frontend clients, change replay persistence, or change scientific calculations.
