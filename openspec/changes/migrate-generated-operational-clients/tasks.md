## 1. RED quality contract

- [x] 1.1 Require quality to become the third generated-schema product consumer.
- [x] 1.2 Freeze GET URL/encoding, 404-null and error detail/fallback behavior.
- [x] 1.3 Specify generated response optionality without narrowing casts.

## 2. GREEN quality migration

- [ ] 2.1 Replace the manual quality DTO with generated component and operation aliases.
- [ ] 2.2 Pass focused architecture, type, transport and UI tests.

## 3. RED lineage contract

- [ ] 3.1 Require lineage to become the fourth generated-schema product consumer.
- [ ] 3.2 Freeze fail-closed 409/detail/fallback and request behavior.

## 4. GREEN lineage migration

- [ ] 4.1 Replace manual lineage DTOs with generated aliases.
- [ ] 4.2 Pass focused architecture, type, transport and UI tests.

## 5. RED laboratory contract

- [ ] 5.1 Require laboratory ingestion to become the fifth generated-schema product consumer.
- [ ] 5.2 Freeze exact synthetic body, URL, method, header and error behavior.
- [ ] 5.3 Freeze stale/unmounted scenario isolation.

## 6. GREEN laboratory migration

- [ ] 6.1 Bind response and request body to generated contracts while retaining domain inputs.
- [ ] 6.2 Pass focused architecture, type, transport and scenario tests.

## 7. RED forecast contract

- [ ] 7.1 Require forecast to complete the exact six-consumer allowlist.
- [ ] 7.2 Freeze all six operations, error semantics and nullable/optional states.
- [ ] 7.3 Narrow rejection labels to the generated binary request contract.

## 8. GREEN forecast migration

- [ ] 8.1 Replace manual forecast DTOs with generated aliases and request types.
- [ ] 8.2 Preserve missing-dataset sanitization and all late-response guards.
- [ ] 8.3 Pass full frontend/backend regressions, build, lint and artifact drift gates.
