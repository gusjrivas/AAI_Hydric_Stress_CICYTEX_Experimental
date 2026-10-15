# Change: Establish deterministic OpenAPI-to-TypeScript foundation

## Why

The FastAPI contract and the handwritten frontend request types currently have
no reproducible, offline bridge.  Before typed clients or frontend migrations
are considered, the repository needs a small auditable foundation that freezes
the OpenAPI bytes, validates operation identifiers and proves that generated
TypeScript contains no `any` syntax nodes.

## What Changes

- Add deterministic UTF-8/LF canonicalization for an in-memory OpenAPI document.
- Validate missing, blank and duplicate operation IDs with stable diagnostics.
- Bind canonical OpenAPI and generated TypeScript bytes in a size/SHA-256 manifest.
- Pin and execute `openapi-typescript` from the local frontend installation.
- Validate the generated TypeScript AST without treating comments or strings as code.

## Out of Scope

- Generating API clients, request wrappers, hooks or runtime validators.
- Importing generated types into production frontend or backend code.
- Starting Uvicorn, calling `/openapi.json`, using `npx`, or requiring network access.
- Changing any HTTP, scientific, persistence or experimental contract.

## Traceability

- **HU / capacity:** HU6, `architecture-integration` and `alerting-ui` boundary.
- **CRISP-DM:** deployment/integration support only.
- **Experimental configuration:** none; historical and scientific artifacts are unchanged.
- **Architecture impact:** adds an offline build-time contract seam, not a runtime dependency.
