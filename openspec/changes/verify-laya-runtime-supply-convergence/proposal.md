# Change: Verificar convergencia de contenido supply de Laya

## Why

PR22 verifica las diez layers comprimidas y sus DiffIDs. PR35 verifica cinco
archivos checkpoint y su provenance Git; el snapshot portable contiene el checkpoint
manifest que compromete esos archivos. PR36 prueba el prefijo OCI de la base contra
PR22. Cada autoridad es válida por separado, pero ninguna demuestra todavía que sus
snapshots de bundle describan el mismo contenido.

## What Changes

- Añadir un combinador puro para evidencia exacta e issued de PR22, PR35 y PR36.
- Exigir que `PR36.layer_evidence` sea por identidad el input PR22.
- Reconstruir los snapshots PR22 y PR35 mediante
  `verify_laya_runtime_artifact_bytes` y probar equivalencia profunda de contenido,
  manifest e identidad de runtime.
- Elevar únicamente el nuevo claim
  `runtime_supply_content_convergence_verified=true`.
- Emitir evidencia registrada por el módulo y un summary público mínimo,
  privacy-preserving y sin commitments extra.

## Impact

- Nuevo módulo puro previsto: `human_feedback.runtime_supply_convergence`.
- API pública exacta: `verify_laya_runtime_supply_convergence`,
  `canonical_laya_runtime_supply_convergence_summary_bytes` y el tipo
  `LayaRuntimeSupplyConvergenceEvidence`.
- Sin I/O, adapters, fixtures, subprocess, red, caller productivo ni cambios en
  backend, runners, readiness, datasets o experimentos.
- No se afirma captura co-temporal, misma raíz, origen, licencia, receta/build,
  reproducibilidad, materialización, executor o inferencia.
