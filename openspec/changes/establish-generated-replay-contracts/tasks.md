## 1. RED contract

- [x] 1.1 Specify the six closed nominal CICYTEX replay schema families.
- [x] 1.2 Freeze successful HTTP status and payload compatibility, including explicit nulls.
- [x] 1.3 Specify one feedback validation-state literal and historical omission semantics.

## 2. GREEN backend contract

- [x] 2.1 Add closed Pydantic response schemas without changing application payloads.
- [x] 2.2 Bind all six CICYTEX success responses to nominal OpenAPI components.
- [x] 2.3 Narrow `ReplayFeedbackEntry.estado_validacion` to the request literal.

## 3. Verification

- [x] 3.1 Pass focused CICYTEX, historical replay and OpenAPI contract tests.
- [x] 3.2 Regenerate and drift-check deterministic OpenAPI/TypeScript artifacts.

## 4. RED generated replay consumers

- [x] 4.1 Require the first two replay clients to consume generated component and operation types.
- [x] 4.2 Prohibit duplicated DTO interfaces, unsafe casts and unconstrained record workarounds.
- [x] 4.3 Freeze public client names, separate transport helpers and required nullable fields.

## 5. GREEN generated replay consumers

- [x] 5.1 Migrate the historical replay API module without changing its runtime requests.
- [x] 5.2 Migrate the CICYTEX defense API module without changing its runtime requests.
- [x] 5.3 Pass TypeScript compile-time fixtures and existing transport and UI tests.

## 6. RED observable client equivalence

- [x] 6.1 Freeze both clients' paths, methods, query encoding, headers, request bodies and optional omission.
- [x] 6.2 Freeze historical error classes/messages and CICYTEX text error behavior.
- [x] 6.3 Specify generated nullability and late-response isolation across omitted, null, false and true states.

## 7. GREEN observable client equivalence

- [x] 7.1 Preserve both clients' transport, public APIs and established error behavior.
- [x] 7.2 Render null CICYTEX metric slots and unrevealed historical targets without fabricated values.
- [x] 7.3 Pass observable-equivalence, full frontend, build, lint and generated-artifact drift gates.
