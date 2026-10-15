# Design: bounded operational client type adoption

## Decisions

### One client at a time

The migration proceeds quality, lineage, laboratory, then forecast. Each slice begins with a
failing architecture/type contract and observable transport characterization before replacing
manual DTO declarations.

### Generated types, existing runtime

Each client derives public response aliases and private request/operation types from
`components` and `operations`. Existing `fetch` calls and local error semantics remain the
runtime authority; no generated transport or validation layer is added.

### Domain inputs remain domain inputs

`LabReadingValues` belongs to the deterministic UI reading generator and is not an HTTP DTO.
It remains local. The assembled HTTP body is checked against the generated
`SensorReadingRequest` and always declares `procedencia: "sintetico"`.

### Wider generated optionality is honest

Generated optional-nullable fields are not narrowed with casts or replacement interfaces.
Consumers handle absent and null values equivalently where both represent unavailable state.

## Non-goals

- Producer v2, demo control or replay-client migrations.
- Runtime routing generation, shared fetch helpers, retries, timeouts or `AbortController`.
- Backend/OpenAPI edits or regeneration.
- Scientific model, dataset, persistence, Laya or visual changes.
