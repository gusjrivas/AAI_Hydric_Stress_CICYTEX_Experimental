## 1. TDD del plan DiffID

- [x] 1.1 Registrar RED `07e7224` para cardinalidad/orden exactos, ancestry PR21, identidad y superficie pura.
- [x] 1.2 Implementar GREEN `4c80ebc` para el plan sellado de diez layers sin I/O.

## 2. TDD del verificador streaming

- [x] 2.1 Registrar RED `bcfa8db` para rehash comprimido, gzip single-member, DiffID por posición, caps y privacidad.
- [x] 2.2 Registrar autorización de dependencia `85b83a2` para reutilizar el verificador comprimido PR20 sin ampliar su autoridad.
- [x] 2.3 Implementar GREEN `c70ace4` para SHA-256 incremental del flujo descomprimido y receipts sellados.

## 3. TDD del adaptador secure-FD

- [x] 3.1 Registrar RED `b243c14` para same-root, 12+10 pasadas, inventario, sweep, cleanup y all-or-nothing.
- [x] 3.2 Implementar GREEN `1e46ecd` para captura Linux descriptor-relative y evidencia agregada.
- [x] 3.3 Registrar RED `f3db872` tras el NO-GO independiente para exigir que el presupuesto rootfs restante limite cada stream antes del sellado.
- [x] 3.4 Implementar GREEN `436a234` con corte incremental `remaining + 1` y presupuesto agregado decreciente en el adaptador.
- [x] 3.5 Registrar RED `423c1af` tras la segunda auditoría para probar el centinela real y una única fuente de verdad de caps.
- [x] 3.6 Implementar GREEN `7b0b300` usando exclusivamente los caps públicos vivos del núcleo desde el adaptador.
- [x] 3.7 Registrar RED `c8a7c2e` para lecturas cortas `O_NONBLOCK` sin exceder el cap lógico de chunks.
- [x] 3.8 Implementar GREEN `0077f37` coalesciendo lecturas parciales en buffers acotados de 1 MiB.

## 4. Gates y alcance

- [x] 4.1 Ejecutar suite focal final después de los fixes: `67 passed, 32 skipped`.
- [x] 4.2 Ejecutar gate real manual/serial Linux sobre mount read-only: `1 passed`, 12 revalidaciones blob y 10 verificaciones DiffID.
- [x] 4.3 Ejecutar suite Laya completa después de los fixes de presupuesto: `983 passed, 34 skipped`; Black y Ruff limpios.
- [x] 4.4 Elevar sólo `oci_layer_diff_ids_verified`; mantener falsos TAR/rootfs/origen/licencia/ancestry/materialización/ejecución.
- [x] 4.5 Preservar cinco roles/runtime identity, blobs externos y ausencia de caller productivo.
- [x] 4.6 Completar auditoría independiente final y merge gate: GO sin P0/P1/P2 sobre `9f7467ba2c63663e15ad831677b6c01b09cab730`; corrección documental posterior sujeta a revalidación exacta antes del merge.

## 5. Próximos slices

- [ ] 5.1 Validar semántica TAR, whiteouts y composición rootfs antes de elevar `oci_rootfs_verified`.
- [ ] 5.2 Verificar procedencia/licencia/base ancestry y checkpoint mediante evidencia independiente.
- [ ] 5.3 Diseñar materialización, caller productivo, executor e inferencia sólo tras cerrar los gates previos.
