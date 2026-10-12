## 1. TDD del plan OCI cerrado

- [x] 1.1 Registrar RED `07ec0bc` para controles exactos, enlace index→manifest y grafo de doce blobs.
- [x] 1.2 Registrar hardening `3a47351`, `b9ff9a9` y autorización successor `af6f8a1` para identidad/media types/sellado.
- [x] 1.3 Implementar GREEN `6430435` para el plan inmutable de 14 archivos.

## 2. TDD de blobs por streaming

- [x] 2.1 Registrar RED `33ee5b7` para size/SHA-256 incremental y receipts por blob.
- [x] 2.2 Registrar hardening `581498b` y `d5da30e` para caps, LFS, privacidad y límites de autoridad.
- [x] 2.3 Implementar GREEN `b8e2852` para streams acotados de los doce blobs.

## 3. TDD de captura same-root

- [x] 3.1 Registrar RED `8531c99` para adapter Linux, inventario cerrado, gate externo y flags conservadores.
- [x] 3.2 Registrar hardening `2cbd5f2`, `bfdaac1`, `2738a7c` y `6e82ad9` para sealers privados, atomicidad observada, orden, TOCTOU, sweep final y cleanup.
- [x] 3.3 Implementar GREEN `36e862f` para captura descriptor-relative y evidencia final.
- [x] 3.4 Registrar RED `a521670` y GREEN `0d997de` para cap de 128 componentes antes de abrir una raíz excesiva.

## 4. Gate y alcance

- [x] 4.1 Tratar la fuente externa como input read-only, no modificarla, verificar preservación de fingerprint y ejecutar sobre clon temporal descartable; sin afirmar enforcement de permisos/mount.
- [x] 4.2 Ejecutar el gate manual serial con `LAYA_RUNTIME_OCI_LAYOUT_ROOT`, sin xdist: `224 passed, 1 skipped`, incluido el hardening posterior del cap de traversal y únicamente el test Windows como skip; no presentarlo como CI.
- [x] 4.3 Elevar sólo claims de bytes, inventario y same-root; mantener falsos semántica config/diffIDs/rootfs y todos los claims de origen/operación.
- [x] 4.4 Mantener cinco roles de artefactos sin cambios y ningún caller productivo.
- [ ] 4.5 Completar auditoría independiente final del board y merge gate.

## 5. Próximos slices

- [ ] 5.1 Validar semántica de config, history y `rootfs.diff_ids` sin inferirla de sus bytes.
- [ ] 5.2 Verificar origen/firma/licencia/ancestry mediante evidencia independiente.
- [ ] 5.3 Verificar checkpoint bytes y compatibilidad antes de materializar runtime.
- [ ] 5.4 Diseñar caller productivo, executor e inferencia sólo tras los gates anteriores.
