# Design: bounded producer client type adoption

## Decisions

### Migrate in observable slices

Catalog and readings form the first slice, followed by forecasts and historical replay. Each
slice starts with generated-operation bindings, mutation-resistant architecture assertions and
transport characterization before production changes.

### Generated types, unchanged runtime

Public DTO names remain stable aliases derived from `components`; request/response contracts
derive from `operations`. Existing `fetch` calls remain the runtime implementation. Error
parsing may retain a small private defensive shape because an untrusted error body is not a
successful OpenAPI response.

### Preserve producer-specific semantics

`VITE_PRODUCER_API_BASE_URL`, URL encoding, omitted optional queries, cursors, review
idempotency, nullable fields and response identity remain unchanged. `ReadingsResponse` exposes
its required `input_roles`; test fixtures declare it instead of narrowing the generated type.

## Non-goals

- Backend/OpenAPI edits, artifact regeneration or generated runtime clients.
- Shared transport abstractions, retries, cancellation or error-policy redesign.
- UI, scientific model, dataset, persistence, Laya or laboratory changes.
