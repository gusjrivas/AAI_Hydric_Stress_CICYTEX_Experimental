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

## 4. Gates y alcance

- [x] 4.1 Ejecutar suite focal: `60 passed, 5 skipped`.
- [x] 4.2 Ejecutar gate real manual/serial Linux: `1 passed`, 12 revalidaciones blob y 10 verificaciones DiffID.
- [x] 4.3 Ejecutar suite Laya completa: `980 passed, 34 skipped`; Black y Ruff limpios.
- [x] 4.4 Elevar sólo `oci_layer_diff_ids_verified`; mantener falsos TAR/rootfs/origen/licencia/ancestry/materialización/ejecución.
- [x] 4.5 Preservar cinco roles/runtime identity, blobs externos y ausencia de caller productivo.
- [ ] 4.6 Completar auditoría independiente final y merge gate.

## 5. Próximos slices

- [ ] 5.1 Validar semántica TAR, whiteouts y composición rootfs antes de elevar `oci_rootfs_verified`.
- [ ] 5.2 Verificar procedencia/licencia/base ancestry y checkpoint mediante evidencia independiente.
- [ ] 5.3 Diseñar materialización, caller productivo, executor e inferencia sólo tras cerrar los gates previos.
