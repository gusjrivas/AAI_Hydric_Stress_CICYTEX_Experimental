## 0. Contrato arquitectónico

- [x] 0.1 Fijar PR22, PR35 y PR36 como únicos predecessors.
- [x] 0.2 Definir convergencia profunda de contenido sin claim co-temporal ni same-root.
- [x] 0.3 Definir API de dos operaciones, un tipo de evidencia y summary público mínimo privacy-preserving.

## 1. RED A — autoridad y API

- [x] 1.1 Registrar tests fallidos para exact-class e issuance canónica de los tres predecessors.
- [x] 1.2 Registrar tests fallidos para `PR36.layer_evidence is PR22 input`.
- [x] 1.3 Registrar tests fallidos para superficie pública exacta de dos operaciones y un tipo.
- [x] 1.4 Registrar RED con los tres validadores canónicos reales, sin monkeypatch.
- [x] 1.5 Emitir ancestry PR22 legítima con snapshot reconstruible; prohibir el helper legado sin snapshot.

## 2. RED B — convergencia de snapshots

- [x] 2.1 Registrar tests fallidos que exijan reconstrucción con `verify_laya_runtime_artifact_bytes`.
- [x] 2.2 Registrar tests fallidos para rutas exactas y equivalencia profunda de manifest, cinco artefactos y runtime identity.
- [x] 2.3 Registrar tests fallidos que distingan equivalencia de contenido de co-temporalidad/same-root.

## 3. RED C — integridad y concurrencia

- [x] 3.1 Registrar tests fallidos para clones, ancestors mutados, identidad PR36→PR22 y PR35 issued independiente equivalente.
- [x] 3.2 Registrar tests fallidos para registro module-side protegido por lock.
- [x] 3.3 Registrar tests fallidos para concurrencia sin estado global one-shot.
- [x] 3.4 Registrar RED observable para GC sin retención de cuatro grafos reales, evidencia viva estable tras cada cleanup y clones, aliases o unissued rechazados.

## 4. RED D — claims, privacidad y aislamiento

- [x] 4.1 Registrar tests fallidos para matriz exacta de claims y cardinalidades 3/5/5/10/16/4 sin caps nuevos.
- [x] 4.2 Registrar tests fallidos para allowlist exacta del summary público mínimo y privacidad de repr/errores.
- [x] 4.3 Registrar tests fallidos para ausencia de I/O, adapters, fixtures y callers productivos.

## 5. GREEN

- [x] 5.1 Implementar el combinador puro después de RED A–D.
- [x] 5.2 Implementar evidencia issued, registry/lock y revalidación profunda.
- [x] 5.3 Implementar summary canónico allowlisted.

## 6. Gates posteriores

- [x] 6.1 Ejecutar focal PR37 y regresiones PR22/PR35/PR36.
- [x] 6.2 Ejecutar regresiones Melchor Romero, Pergamino, CICYTEX y laboratorio mock.
- [x] 6.3 Ejecutar Black, Ruff, OpenSpec strict y diff checks.
- [x] 6.4 Añadir CI focal Linux/Windows con dependencias base ancestry + provenance.
- [ ] 6.5 Obtener gate independiente GO P0/P1/P2=0.

Evidencia: RED funcional `9a0f029` + correcciones de contrato/race
`23f94b6`/`df8ddcc`/`61bbc0d`; GREEN `3698428`; RED/GREEN CI
`f6372cf`/`6585360`; compatibilidad de gates predecessors y checkout byte-stable
Windows `5a4b447`. Focal PR37 `34 passed`; CI contract `5 passed`;
PR22/PR35/PR36 + checkout integrity `176 passed`; Laya completa en checkout limpio
`1415 passed, 127 skipped`; Melchor Romero/Pergamino `65 passed`;
CICYTEX/laboratorio mock `187 passed, 7 skipped`; Black `333 files unchanged`,
Ruff PASS, OpenSpec strict PASS y diff check PASS.

## 7. Deferred

- [ ] 7.1 Materializar rootfs/runtime sólo en slices posteriores.
- [ ] 7.2 Habilitar executor/inferencia sólo con sus propios contratos TDD.
- [ ] 7.3 Evaluar origen, licencia y receta/build con autoridades separadas.
