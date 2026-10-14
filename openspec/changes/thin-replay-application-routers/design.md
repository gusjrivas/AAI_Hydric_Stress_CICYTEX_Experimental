# Design: thin replay application routers

## Boundary

`backend/app/routers/cicytex_replay.py` and
`backend/app/routers/replay.py` remain the only FastAPI adapters in scope.  They
may own Pydantic request/response binding and translate explicit application
errors to the existing HTTP contract.  They do not import Pandas or invoke
projection, observation, history, feedback-persistence or session-coordination
operations directly.

Framework-free orchestration lives in
`historical_replay.cicytex_application` and
`historical_replay.replay_application`.  These modules may depend on domain
ports and values, but never on `backend`, FastAPI, Starlette, HTTP status codes
or Pydantic response models.

## Compatibility seam

The application layer returns framework-neutral results.  Routers perform the
last mechanical conversion to the existing response schemas and retain the
literal Spanish error messages and status codes.  The route set, methods,
operation IDs and response model references are frozen by an OpenAPI golden
test.  Existing scenario tests remain the behavioral oracle for payloads,
future hiding, resets, feedback conflicts and private 503 responses.

## Migration strategy

1. Introduce application modules behind existing domain ports.
2. Characterize their orchestration with fakes as each use case moves.
3. Replace router helpers and direct domain pipelines incrementally.
4. Keep the OpenAPI golden and all replay scenario regressions green at every
   step; no persistence or scientific contract changes share this refactor.
