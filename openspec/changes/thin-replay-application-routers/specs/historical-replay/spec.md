## ADDED Requirements

### Requirement: Replay routers are transport-only adapters

The CICYTEX and historical replay FastAPI modules SHALL restrict themselves to
transport binding, dependency injection, response conversion and stable HTTP
error translation.  Scientific projection, Pandas transformations, metric
calculation, session/feedback coordination and persistence calls SHALL execute
through framework-free application modules under `historical_replay`.

#### Scenario: application use cases run without the web framework

- **GIVEN** domain ports and replay values supplied by in-memory fakes
- **WHEN** a CICYTEX or historical replay use case is executed
- **THEN** its orchestration can run without importing FastAPI, Starlette or any
  `backend` module
- **AND** the result contains no HTTP exception or Pydantic response object.

#### Scenario: routers contain no scientific or persistence pipeline

- **WHEN** the two router modules are inspected structurally
- **THEN** they import their corresponding application module instead of Pandas
  or the projection/history/feedback/session implementation modules
- **AND** the former render, metric, lookup and projection helpers are absent.

#### Scenario: feedback has one application coordination owner

- **WHEN** CICYTEX feedback is posted through the HTTP adapter
- **THEN** the router delegates once to its injected feedback application facade
- **AND** the router does not import the session service, call `with_session`, or
  probe for fallback repository methods.

### Requirement: The refactor is externally invisible

The refactor SHALL preserve route paths, methods, operation IDs, response-model
references, literal payload fields and existing status/error behavior.

#### Scenario: OpenAPI remains stable

- **WHEN** the application OpenAPI document is generated after any refactor step
- **THEN** every replay and CICYTEX path, method, operation ID, success status and
  response model matches the pre-refactor golden contract.

#### Scenario: scientific replay behavior remains stable

- **WHEN** existing CICYTEX, Melchor Romero, Pergamino and mock replay scenarios
  run
- **THEN** future values remain hidden at the same clocks
- **AND** reset, feedback, conflict, 404, 409, 422 and private 503 behavior is
  unchanged
- **AND** no scientific package or persistence schema is modified by this change.
