## 1. RED contract

- [x] 1.1 Specify the six closed nominal CICYTEX replay schema families.
- [x] 1.2 Freeze successful HTTP status and payload compatibility, including explicit nulls.
- [x] 1.3 Specify one feedback validation-state literal and historical omission semantics.

## 2. GREEN backend contract

- [ ] 2.1 Add closed Pydantic response schemas without changing application payloads.
- [ ] 2.2 Bind all six CICYTEX success responses to nominal OpenAPI components.
- [ ] 2.3 Narrow `ReplayFeedbackEntry.estado_validacion` to the request literal.

## 3. Verification

- [ ] 3.1 Pass focused CICYTEX, historical replay and OpenAPI contract tests.
- [ ] 3.2 Regenerate deterministic OpenAPI/TypeScript artifacts in a later bounded slice.
