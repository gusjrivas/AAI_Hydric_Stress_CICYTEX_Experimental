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

## 4. RED generated replay consumers

- [x] 4.1 Require the first two replay clients to consume generated component and operation types.
- [x] 4.2 Prohibit duplicated DTO interfaces, unsafe casts and unconstrained record workarounds.
- [x] 4.3 Freeze public client names, separate transport helpers and required nullable fields.

## 5. GREEN generated replay consumers

- [ ] 5.1 Migrate the historical replay API module without changing its runtime requests.
- [ ] 5.2 Migrate the CICYTEX defense API module without changing its runtime requests.
- [ ] 5.3 Pass TypeScript compile-time fixtures and existing transport and UI tests.
