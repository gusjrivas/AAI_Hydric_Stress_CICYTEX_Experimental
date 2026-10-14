## 1. RED contracts

- [x] 1.1 Specify canonical OpenAPI JSON bytes and deterministic operation-ID diagnostics.
- [x] 1.2 Specify exact artifact manifest integrity and TypeScript AST `any` rejection.
- [x] 1.3 Specify local/offline generator and no-product-caller boundaries.
- [x] 1.4 Specify in-process export, temporal check and real local generator execution.

## 2. GREEN foundation

- [ ] 2.1 Implement the pure OpenAPI/manifest/AST contract core.
- [ ] 2.2 Pin `openapi-typescript` exactly and add the local generation script.
- [ ] 2.3 Generate schema types and manifest without a client or runtime imports.
- [ ] 2.4 Make the exact frontend lock peer-compatible with plain `npm ci`.

## 3. Verification

- [ ] 3.1 Pass the focused foundation tests and existing OpenAPI tests.
- [ ] 3.2 Pass frontend lint, tests and build without product imports of generated output.
- [ ] 3.3 Pass Ruff, Black, strict OpenSpec and diff-check.
