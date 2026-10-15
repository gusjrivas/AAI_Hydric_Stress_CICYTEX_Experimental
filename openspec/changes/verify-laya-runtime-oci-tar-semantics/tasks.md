## 1. TDD del plan y aislamiento

- [x] 1.1 Registrar RED para ancestry PR22 exacta, identidad, diez posiciones ordenadas, construcción sellada y superficie pública mínima (`2a3e298`, `3f20064`).
- [x] 1.2 Registrar RED para aislamiento: sin I/O en el núcleo, un único successor autorizado del streaming PR22 y cero callers productivos (`815aa0e`).
- [x] 1.3 Implementar GREEN mínimo del plan y tipos sellados sin consumir streams (`2b26362`).

## 2. TDD del parser TAR base

- [x] 2.1 Registrar RED para header completo, magic/version permitidos, checksum previo a campos, numeric fields y typeflags cerrados (`2a3e298`, `9cde9c7`).
- [x] 2.2 Registrar RED para payload exacto, padding cero, dos bloques terminales, trailing cero y truncamientos (`2a3e298`, `9cde9c7`).
- [x] 2.3 Registrar RED para chunking diferencial, binding de tamaño histórico y buffers incrementales acotados (`a4c7a07`, `18c7900`).
- [x] 2.4 Implementar GREEN mínimo de la máquina de estados TAR base (`2b26362`).

## 3. TDD de extensiones, paths y bombas

- [x] 3.1 Registrar RED para PAX local/global y GNU longname/longlink, incluida precedencia, UTF-8, records, límites y metadata pendiente (`7b9dfe0`, `5785321`).
- [x] 3.2 Registrar RED para rechazo de sparse, devices/FIFO, typeflags desconocidos, oldgnu ambiguo y overrides contradictorios (`7b9dfe0`, `8f3d604`).
- [x] 3.3 Registrar RED para normalización segura del entry path y para targets de link POSIX opacos, incluidos absolutos y `..`, acotados y sin NUL/control (`7b9dfe0`).
- [x] 3.4 Registrar RED para rechazo de paths efectivos duplicados, incluidas colisiones por normalización, slash final y PAX/GNU (`7b9dfe0`, `5785321`).
- [x] 3.5 Registrar RED para caps de entries, path/link, metadata, payload y TAR agregado, con fail-fast y generadores hostiles (`7b9dfe0`, `8f3d604`).
- [x] 3.6 Implementar GREEN mínimo de extensiones, manifest inmutable y límites (`1f9add7`).

## 4. TDD del adaptador y evidencia

- [x] 4.1 Registrar RED para preflight antes de abrir, recaptura de 12 blobs, diez verificaciones DiffID+TAR y orden exacto (`ff9faf9`).
- [x] 4.2 Registrar RED para symlink/LFS/FIFO/hardlink filesystem, TOCTOU, fingerprints, inventario, sweep y fallos de open/read/fstat/scandir/close (`ff9faf9`, RED32E `3291985`).
- [x] 4.3 Registrar RED para cleanup exactamente una vez, close-before-seal y ausencia de evidencia parcial (RED32E `3291985`).
- [x] 4.4 Registrar RED para evidencia/summary privados y elevación exclusiva de `tar_semantics_verified` (`ff9faf9`, RED32E `3291985`).
- [x] 4.5 Implementar GREEN mínimo de captura Linux same-root y sellado all-or-nothing (`4232036`), con root marker estricto RED `21aeadc` / GREEN `39ee8fe`.

## 5. Gates y cierre

- [x] 5.1 Ejecutar tests focales PR32 en Windows para el núcleo puro: `149 passed, 71 skipped`.
- [x] 5.1a Ejecutar tests focales PR32 en Linux para el núcleo puro: `187 passed, 33 skipped`.
- [x] 5.2 Ejecutar regresiones PR20-PR22 (`543 passed, 72 skipped`) y gate independiente Laya/runtime (`900 passed, 97 skipped`).
- [x] 5.3 Ejecutar gate real Linux manual, serial y opt-in sobre layout externo read-only: diez layers, `1 passed` en `76.20s`, tras root marker RED `21aeadc` / GREEN `39ee8fe`.
- [x] 5.4 Ejecutar regresiones Melchor Romero, Pergamino, CICYTEX y laboratorio/mock: `252 passed, 7 skipped`.
- [x] 5.5 Ejecutar Black (`313 files`), Ruff, diff-check y OpenSpec strict: PASS.
- [x] 5.6 Confirmar por tests y reviews cinco roles/runtime identity intactos, blobs externos y cero caller productivo.
- [ ] 5.7 Completar auditoría independiente requisito por requisito antes de merge: board y gatekeeper dieron GO con P0/P1/P2=`0`, pero falta el gatekeeper final sobre los commits CI `89605b4`/`4c4e944` y root marker `21aeadc`/`39ee8fe`.

## 6. Deferred a PR33+

- [ ] 6.1 Interpretar whiteouts/opaque directories y componer overlays/rootfs en PR33.
- [ ] 6.2 Resolver targets root-bound, dangling/ciclos y verificar `oci_rootfs_verified` sólo después de cerrar composición y efectos inter-layer.
- [ ] 6.3 Mantener fuera de PR32 materialización, provenance/licencia/base, checkpoint, executor e inferencia.
