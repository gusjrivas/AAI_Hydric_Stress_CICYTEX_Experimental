# Change: Migrate operational frontend contracts to generated types

## Why

The deterministic OpenAPI/TypeScript contract is already canonical, but forecast, quality,
lineage and sensor-laboratory clients still duplicate HTTP DTOs by hand. Those declarations
can drift from backend optionality and nullability while the generated contract remains green.

## What Changes

- Adopt generated component and operation types in exactly the forecast, quality, lineage and
  sensor-laboratory clients.
- Preserve every existing URL, method, header, request body, public export and error behavior.
- Preserve legitimate quality 404 emptiness, fail-closed lineage errors, synthetic laboratory
  provenance and stale-response guards.
- Expand the exact generated-schema consumer allowlist from two to six product modules.

## Impact

This is a compile-time contract migration. It does not introduce a generated runtime client,
payload normalization, shared error handling, retries, cancellation, endpoint changes, UI
redesign, backend changes or generated-artifact changes. Producer v2 clients remain deferred.
