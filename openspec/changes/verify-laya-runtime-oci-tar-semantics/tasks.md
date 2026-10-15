## 1. TDD del plan y aislamiento

- [ ] 1.1 Registrar RED para ancestry PR22 exacta, identidad, diez posiciones ordenadas, construcción sellada y superficie pública mínima.
- [ ] 1.2 Registrar RED para aislamiento: sin I/O en el núcleo, un único successor autorizado del streaming PR22 y cero callers productivos.
- [ ] 1.3 Implementar GREEN mínimo del plan y tipos sellados sin consumir streams.

## 2. TDD del parser TAR base

- [ ] 2.1 Registrar RED para header completo, magic/version permitidos, checksum previo a campos, numeric fields y typeflags cerrados.
- [ ] 2.2 Registrar RED para payload exacto, padding cero, dos bloques terminales, trailing cero y truncamientos.
- [ ] 2.3 Registrar RED para chunking diferencial y buffers incrementales acotados.
- [ ] 2.4 Implementar GREEN mínimo de la máquina de estados TAR base.

## 3. TDD de extensiones, paths y bombas

- [ ] 3.1 Registrar RED para PAX local/global y GNU longname/longlink, incluida precedencia, UTF-8, records, límites y metadata pendiente.
- [ ] 3.2 Registrar RED para rechazo de sparse, devices/FIFO, typeflags desconocidos y overrides contradictorios.
- [ ] 3.3 Registrar RED para normalización segura del entry path y para targets de link POSIX opacos, incluidos absolutos y `..`, acotados y sin NUL/control.
- [ ] 3.4 Registrar RED para rechazo de paths efectivos duplicados, incluidas colisiones por normalización, slash final y PAX/GNU.
- [ ] 3.5 Registrar RED para caps de entries, path/link, metadata, payload y TAR agregado, con fail-fast y generadores hostiles.
- [ ] 3.6 Implementar GREEN mínimo de extensiones, manifest inmutable y límites.

## 4. TDD del adaptador y evidencia

- [ ] 4.1 Registrar RED para preflight antes de abrir, recaptura de 12 blobs, diez verificaciones DiffID+TAR y orden exacto.
- [ ] 4.2 Registrar RED para symlink/LFS/FIFO/hardlink filesystem, TOCTOU, fingerprints, inventario, sweep y fallos de open/read/fstat/scandir/close.
- [ ] 4.3 Registrar RED para cleanup exactamente una vez, close-before-seal y ausencia de evidencia parcial.
- [ ] 4.4 Registrar RED para evidencia/summary privados y elevación exclusiva de `tar_semantics_verified`.
- [ ] 4.5 Implementar GREEN mínimo de captura Linux same-root y sellado all-or-nothing.

## 5. Gates y cierre

- [ ] 5.1 Ejecutar tests focales PR32 en Windows y Linux para el núcleo puro.
- [ ] 5.2 Ejecutar regresiones PR20-PR22 y suite Laya completa.
- [ ] 5.3 Ejecutar gate real Linux manual, serial y opt-in sobre layout externo disposable/read-only.
- [ ] 5.4 Ejecutar regresiones Melchor Romero, Pergamino, CICYTEX y laboratorio/mock.
- [ ] 5.5 Ejecutar Black, Ruff, diff-check y OpenSpec strict.
- [ ] 5.6 Confirmar cinco roles/runtime identity intactos, blobs externos y cero caller productivo.
- [ ] 5.7 Completar auditoría independiente requisito por requisito antes de merge.

## 6. Deferred a PR33+

- [ ] 6.1 Interpretar whiteouts/opaque directories y componer overlays/rootfs en PR33.
- [ ] 6.2 Resolver targets root-bound, dangling/ciclos y verificar `oci_rootfs_verified` sólo después de cerrar composición y efectos inter-layer.
- [ ] 6.3 Mantener fuera de PR32 materialización, provenance/licencia/base, checkpoint, executor e inferencia.
