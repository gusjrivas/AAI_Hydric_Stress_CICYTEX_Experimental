## 1. RED contracts

- [x] 1.1 Record the exact replay and CICYTEX OpenAPI surface.
- [x] 1.2 Specify router import, helper and orchestration boundaries with AST tests.
- [x] 1.3 Specify framework-free application-module placement.
- [x] 1.4 Preserve existing replay scenario tests as payload/status controls.

## 2. GREEN implementation

- [x] 2.1 Add the framework-free CICYTEX replay application module.
- [x] 2.2 Move CICYTEX rendering, metrics and feedback coordination out of the router.
- [x] 2.3 Add the framework-free historical replay application module.
- [x] 2.4 Move candidate, prediction, history and feedback orchestration out of the router.
- [x] 2.5 Keep routers limited to HTTP binding and stable error translation.

## 3. Verification

- [x] 3.1 Pass the OpenAPI golden and architecture tests.
- [x] 3.2 Pass CICYTEX, Melchor Romero, Pergamino and mock replay regressions.
- [x] 3.3 Pass Black, Ruff, strict OpenSpec and diff-check.
