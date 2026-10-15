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

### Keep the historical wire wider than the UI projection

The four clients bind exactly ten operations: two catalog, one readings, four forecasts and
three historical operations. The generated historical forecast response remains the wire
authority and is statically required to extend the stable `ForecastBatch` UI projection. No
adapter, cast, default or fabricated field is introduced at that boundary.

The projection deliberately preserves OpenAPI's optional-or-null `ensemble` and its open
string-to-number `weights` map. Only nested component votes are projected to the established
public model-reference shape. This keeps historical responses assignable without claiming that
arbitrary wire weights contain a closed family set.

### Preserve a compile-time-only change

All four modules retain manual `fetch`, their existing error parsing and their presentation
helpers. The migration adds no generated runtime client, shared transport adapter, cast-based
escape hatch or response normalization.

## Implementation evidence

| Slice | RED evidence | GREEN evidence |
| --- | --- | --- |
| Catalog and readings | `fb8f31a` | `9fe545c` |
| Forecasts | `992e231` | `854ec1e` |
| Historical replay | `bfc5a25`, corrected by `138b3cf` | `52bacb5` |

The final architecture allowlist contains exactly ten generated-schema consumers. Producer
transport regressions, TypeScript build, lint and the mutation-resistant architecture gates
were green for the final implementation. The repository-wide gate in task 4.6 remains explicit
until it is run as a single closure gate.

## Non-goals

- Backend/OpenAPI edits, artifact regeneration or generated runtime clients.
- Shared transport abstractions, retries, cancellation or error-policy redesign.
- UI, scientific model, dataset, persistence, Laya or laboratory changes.
