## 0. Contrato arquitectónico

- [x] 0.1 Fijar PR22, PR35 y PR36 como únicos predecessors.
- [x] 0.2 Definir convergencia profunda de contenido sin claim co-temporal ni same-root.
- [x] 0.3 Definir API de dos operaciones, un tipo de evidencia y summary público mínimo privacy-preserving.

## 1. RED A — autoridad y API

- [ ] 1.1 Registrar tests fallidos para exact-class e issuance canónica de los tres predecessors.
- [ ] 1.2 Registrar tests fallidos para `PR36.layer_evidence is PR22 input`.
- [ ] 1.3 Registrar tests fallidos para superficie pública exacta de dos operaciones y un tipo.
- [ ] 1.4 Registrar RED con los tres validadores canónicos reales, sin monkeypatch.
- [ ] 1.5 Emitir ancestry PR22 legítima con snapshot reconstruible; prohibir el helper legado sin snapshot.

## 2. RED B — convergencia de snapshots

- [ ] 2.1 Registrar tests fallidos que exijan reconstrucción con `verify_laya_runtime_artifact_bytes`.
- [ ] 2.2 Registrar tests fallidos para rutas exactas y equivalencia profunda de manifest, cinco artefactos y runtime identity.
- [ ] 2.3 Registrar tests fallidos que distingan equivalencia de contenido de co-temporalidad/same-root.

## 3. RED C — integridad y concurrencia

- [ ] 3.1 Registrar tests fallidos para clones, ancestors mutados, identidad PR36→PR22 y PR35 issued independiente equivalente.
- [ ] 3.2 Registrar tests fallidos para registro module-side protegido por lock.
- [ ] 3.3 Registrar tests fallidos para concurrencia sin estado global one-shot.
- [ ] 3.4 Registrar RED observable para GC sin retención de cuatro grafos reales, evidencia viva estable tras cada cleanup y clones, aliases o unissued rechazados.

## 4. RED D — claims, privacidad y aislamiento

- [ ] 4.1 Registrar tests fallidos para matriz exacta de claims y cardinalidades 3/5/5/10/16/4 sin caps nuevos.
- [ ] 4.2 Registrar tests fallidos para allowlist exacta del summary público mínimo y privacidad de repr/errores.
- [ ] 4.3 Registrar tests fallidos para ausencia de I/O, adapters, fixtures y callers productivos.

## 5. GREEN

- [ ] 5.1 Implementar el combinador puro después de RED A–D.
- [ ] 5.2 Implementar evidencia issued, registry/lock y revalidación profunda.
- [ ] 5.3 Implementar summary canónico allowlisted.

## 6. Gates posteriores

- [ ] 6.1 Ejecutar focal PR37 y regresiones PR22/PR35/PR36.
- [ ] 6.2 Ejecutar regresiones Melchor Romero, Pergamino, CICYTEX y laboratorio mock.
- [ ] 6.3 Ejecutar Black, Ruff, OpenSpec strict y diff checks.
- [ ] 6.4 Añadir CI focal Linux/Windows con dependencias base ancestry + provenance.
- [ ] 6.5 Obtener gate independiente GO P0/P1/P2=0.

## 7. Deferred

- [ ] 7.1 Materializar rootfs/runtime sólo en slices posteriores.
- [ ] 7.2 Habilitar executor/inferencia sólo con sus propios contratos TDD.
- [ ] 7.3 Evaluar origen, licencia y receta/build con autoridades separadas.
