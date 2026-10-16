## 0. Congelar evidencia externa

- [x] 0.1 Registrar la captura independiente del index content-addressed sin descargar layers ni confiar en tags móviles.
- [x] 0.2 Congelar index/digest, selección Linux/amd64 única, manifest, config y cardinalidades exactos.
- [x] 0.3 Fijar caps cerrados y validar cuatro compressed layers y cuatro DiffIDs como prefijo de las diez posiciones PR22.
- [x] 0.4 Actualizar proposal/design/spec con hechos exactos antes de crear cualquier fixture positivo RED.

## 1. TDD del plan y de la autoridad

- [ ] 1.1 Registrar RED para predecessor PR22 exacto, issued, deeply revalidated y ligado por identidad.
- [ ] 1.2 Registrar RED para rechazar clones `object.__new__`/`replace`/copy/pickle, subclasses, replay y mezcla entre planes/sesiones.
- [ ] 1.3 Registrar RED para superficie pública cerrada de tres operaciones y ausencia de filesystem/red/subprocess/import lateral PR35.
- [ ] 1.4 Implementar GREEN mínimo del plan puro y las autoridades de sesión de un solo uso.

## 2. TDD de objetos content-addressed

- [ ] 2.1 Registrar RED para digest/size/media type exactos de cada objeto y grafo index/manifest/config.
- [ ] 2.2 Registrar RED para selección de plataforma exacta según la forma factual de la raíz capturada.
- [ ] 2.3 Registrar RED para JSON estricto: duplicate keys, fields/tipos extra, Unicode/números no canónicos, profundidad/items/strings y trailing bytes.
- [ ] 2.4 Registrar RED para chunks/objetos/bytes agregados en límite y `cap + 1`, consumo perezoso y corte temprano.
- [ ] 2.5 Implementar GREEN incremental y all-or-nothing sin I/O.

## 3. TDD de ancestry de contenido

- [ ] 3.1 Registrar RED para prefijo exacto, ordenado y no vacío de descriptors comprimidos contra PR22.
- [ ] 3.2 Registrar RED para prefijo DiffID exacto con la misma cardinalidad/posición y rechazar validación unilateral.
- [ ] 3.3 Registrar RED para subsecuencia, reorder, duplicado, inserción, truncamiento, objeto extra/ausente y mix-and-match.
- [ ] 3.4 Registrar RED para que receta/build attestations permanezcan fuera de la API y falsos aun con ancestry válida.
- [ ] 3.5 Implementar GREEN que eleve sólo `base_ancestry_verified` al completar ambas pruebas de prefijo.

## 4. Privacidad y semántica de claims

- [ ] 4.1 Registrar RED para summary determinista allowlisted y ausencia de bytes, paths, URLs, auth, digests internos y sizes.
- [ ] 4.2 Registrar RED para `repr`/errores sin filtraciones y serialización no ambigua.
- [ ] 4.3 Mantener falsos origen/licencia/materialización/executor/inferencia, receta/build/reproducibilidad, y no declarar firma, builder o registry availability.
- [ ] 4.4 Verificar que PR35 no sea predecessor y que la convergencia permanezca diferida a PR37.

## 5. Gates

- [ ] 5.1 Ejecutar suite focal y red-team independiente de forgery/replay/parser/caps.
- [ ] 5.2 Ejecutar suite Laya completa y regresiones Melchor Romero, Pergamino, CICYTEX y laboratorio mock.
- [ ] 5.3 Ejecutar OpenSpec strict, Black, Ruff y CI sobre SHA exacto.
- [ ] 5.4 Obtener gate independiente GO con P0/P1/P2=0 antes de merge.
- [ ] 5.5 Registrar counts/SHAs reales sin convertir tests sintéticos en evidencia externa.

## 6. Deferred

- [ ] 6.1 PR37 convergerá PR22, PR35 y PR36 sobre una única identidad/snapshot supply.
- [ ] 6.2 PR39/PR40 materializarán rootfs/runtime sólo después de convergencia.
- [ ] 6.3 PR41 evaluará executor e inferencia; producción y decisión de riego permanecen fuera de alcance.
