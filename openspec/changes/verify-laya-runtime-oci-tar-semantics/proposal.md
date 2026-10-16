# Change: Verificación streaming de semántica TAR de layers OCI de Laya

Estado: propuesta foundation-only para PR32; TDD obligatorio antes de producción.
No compone whiteouts/rootfs, no materializa archivos y no habilita ejecución.

## Why

PR22 verificó los bytes comprimidos y los DiffIDs de las diez layers OCI, pero el
contenido descomprimido todavía puede ser un TAR estructuralmente inválido,
ambiguo o inseguro. Antes de interpretar overlays en PR33 necesitamos evidencia
sellada de que cada layer pertenece a un perfil TAR cerrado, incremental y
acotado, sin confiar en paths, tamaños o extensiones antes de validarlos.

## What Changes

- Deriva desde evidencia PR22 exacta un plan inmutable ligado por identidad a la
  misma runtime identity, layout, diez blobs y diez receipts DiffID ordenados.
- Añade un parser TAR puro por streaming, en bloques lógicos de 512 bytes, que
  verifica headers, checksum, tamaños, payload, padding y terminación exacta.
- Soporta sólo el perfil fijado: regular, directory, symlink y hardlink, más PAX
  local/global y GNU longname/longlink bajo precedencia y límites explícitos.
- Normaliza paths POSIX sin tocar filesystem y rechaza absolutos, traversal,
  variantes Windows, NUL/control y paths efectivos duplicados dentro de una misma
  layer, incluso cuando la colisión nace de PAX/GNU. Los targets de links se
  preservan como datos POSIX opacos, acotados y privados.
- Rechaza extensiones sparse, devices/FIFO, typeflags desconocidos y entradas o
  metadata que excedan los caps del perfil.
- Extiende la captura Linux same-root para revalidar las doce blobs, verificar las
  diez layers con DiffID+TAR, comparar fingerprints, ejecutar el sweep final y
  cerrar todos los FDs antes del sellado agregado.
- Eleva como único claim nuevo `tar_semantics_verified=true`; mantiene falsos
  whiteouts/rootfs, origen, licencia/base, materialización, executor e inferencia.
- Mantiene cinco roles de artefactos, blobs externos y ausencia de caller
  productivo. El summary público no expone paths, links, digests, tamaños,
  cantidades ni metadata TAR.

## Impact

`tar_semantics_verified=true` significará únicamente que, para una captura
same-root concreta, las diez layers ya verificadas por bytes/DiffID también
cumplieron el perfil TAR cerrado de PR32, sin ambigüedades de path efectivo y sin
violaciones de los límites estructurales. La evidencia será all-or-nothing.

No significará que los whiteouts fueron interpretados, que los overlays producen
un rootfs correcto, que se materializó contenido, ni que origen, licencia,
ancestry, checkpoint, runtime, executor o inferencia estén verificados.

## Deferred

- interpretar whiteouts y opaque directories y componer overlays en orden;
- resolver targets de symlink/hardlink, dangling/ciclos y efectos inter-layer;
- verificar el rootfs resultante y elevar `oci_rootfs_verified`;
- materializar rootfs/runtime o habilitar un caller productivo;
- verificar procedencia, licencia, base ancestry, checkpoint o inferencia.
