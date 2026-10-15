# Change: Migrate producer frontend contracts to generated types

## Why

The producer v2 clients still duplicate catalog, readings, forecast and historical HTTP DTOs by
hand. Those declarations can drift from the canonical OpenAPI contract while generation and
the existing product behavior remain green.

## What Changes

- Adopt generated component and operation types in exactly four producer clients and ten
  operations: catalog (two), readings (one), forecasts (four) and historical replay (three).
- Preserve existing manual `fetch` transports, producer-specific base URL, cursors,
  idempotency, review errors and stale-response behavior.
- Expand the exact generated-schema allowlist in bounded slices from six to exactly ten
  consumers.

## Impact

This is a compile-time contract migration. It does not change backend routes, regenerate the
schema, add a generated runtime client, normalize payloads, redesign the producer UI or alter
Melchor Romero, Pergamino and laboratory behavior.
