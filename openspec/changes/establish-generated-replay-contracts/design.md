# Design: nominal replay response schemas

## Decisions

### Closed schema graph

Every object reachable from the CICYTEX catalog and session responses is closed to
unknown properties. Known horizons and model methods are represented structurally rather
than by unconstrained maps so generated clients do not collapse them to `unknown`.

### Compatibility through bounded generation

The existing HTTP bodies are golden inputs. Schema introduction must not rename a key,
remove an explicit `null`, add a defaulted field, or change a successful status code.
The deterministic OpenAPI/TypeScript artifacts are regenerated in this change, and exactly
the historical replay and CICYTEX defense clients adopt generated component and operation
types. Runtime request helpers remain hand-written: a generated runtime client and all other
consumer migrations are intentionally deferred.

### Temporal semantics remain distinct

CICYTEX continues to serialize unrevealed prediction and feedback values explicitly as
`null`. Historical replay continues using `response_model_exclude_none=True` so future
fields remain absent. The two established contracts are both preserved.

### One feedback vocabulary

`estado_validacion` is the same closed literal in requests and responses:
`confirmada | rechazada`. This narrows documentation only; it does not add a new state.

### Observable frontend behavior is invariant

Generated types replace duplicated DTO declarations without normalizing payloads at runtime.
Paths, methods, query encoding, headers, request bodies, optional-field omission, public client
names and established error classes/messages remain unchanged. The UI omits null CICYTEX
metric slots and treats absent or null historical observations as unrevealed, while preserving
late-response isolation across session changes.
