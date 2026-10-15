# Design: nominal replay response schemas

## Decisions

### Closed schema graph

Every object reachable from the CICYTEX catalog and session responses is closed to
unknown properties. Known horizons and model methods are represented structurally rather
than by unconstrained maps so generated clients do not collapse them to `unknown`.

### Compatibility before generation

The existing HTTP bodies are golden inputs. Schema introduction must not rename a key,
remove an explicit `null`, add a defaulted field, or change a successful status code.
Frontend client generation is intentionally deferred.

### Temporal semantics remain distinct

CICYTEX continues to serialize unrevealed prediction and feedback values explicitly as
`null`. Historical replay continues using `response_model_exclude_none=True` so future
fields remain absent. The two established contracts are both preserved.

### One feedback vocabulary

`estado_validacion` is the same closed literal in requests and responses:
`confirmada | rechazada`. This narrows documentation only; it does not add a new state.
