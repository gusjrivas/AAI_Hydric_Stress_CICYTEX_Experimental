# Change: Verificación por streaming de DiffIDs de layers OCI de Laya

Estado: implementado como gate externo opt-in, serial y fail-closed sobre Linux;
no interpreta TAR, no materializa rootfs ni ejecuta el runtime.

## Why

PR21 validó que el config OCI declaraba exactamente diez DiffIDs, pero no calculó
esos hashes desde las layers. PR22 cierra esa brecha recapturando desde una única
raíz las diez layers exactas, revalidando primero sus bytes comprimidos y calculando
por streaming el SHA-256 de cada contenido gzip descomprimido en la misma posición.

## What Changes

- Deriva desde evidencia PR21 un plan puro, inmutable y ligado a la identidad,
  layout, diez descriptors/receipts comprimidos y diez DiffIDs declarados exactos.
- Revalida las doce blobs del layout por tamaño/SHA-256 comprimido y después abre
  nuevamente las diez layers en orden para calcular sus DiffIDs.
- Acepta únicamente streams gzip de un solo member, sin trailing bytes, con chunks
  y expansión acotados; compara `sha256` del flujo descomprimido por posición.
- El adaptador Linux descriptor-relative exige inventario cerrado, misma raíz,
  fingerprints estables, sweep final y cierre de todos los FDs antes del sellado.
- Emite evidencia sólo si las diez posiciones terminan correctamente y el agregado
  observado permanece por debajo de 3 GiB; cualquier fallo deja cero evidencia.
- Eleva como único claim nuevo `oci_layer_diff_ids_verified=true`. Mantiene falsos
  TAR, whiteouts/rootfs, origen, licencia/base, materialización y ejecución.
- Conserva los cinco roles de artefactos y el mismo runtime identity; no incorpora
  blobs al repositorio ni añade caller productivo.
- El summary público conserva únicamente schemas, flags y el commitment
  `runtime_identity_sha256`; paths, digests, DiffIDs y tamaños permanecen privados.

## Impact

`oci_layer_diff_ids_verified=true` significa que, en una captura concreta, cada
una de las diez blobs gzip coincidió nuevamente con el size/SHA-256 comprimido del
plan y que el SHA-256 del único member descomprimido coincidió con el DiffID declarado
en la misma posición del config PR21. La evidencia es all-or-nothing y queda ligada
a la captura same-root y su sweep final.

No significa compatibilidad gzip multi-member genérica, validez TAR, semántica de
whiteouts, corrección del rootfs resultante, procedencia, licencia, ancestry de la
base, materialización, executor ni inferencia.

Las evidencias finales ejecutadas fueron: suite focal `67 passed, 32 skipped`; gate real
Linux `1 passed`, con 12 revalidaciones de blobs más 10 verificaciones DiffID; suite
Laya completa `983 passed, 34 skipped`; Black y Ruff limpios. El gate real sigue
siendo manual/opt-in, no un job obligatorio de CI.

## Deferred

- interpretar TAR y whiteouts y verificar el rootfs OCI resultante;
- verificar origen, firma, licencia o base ancestry mediante evidencia independiente;
- verificar checkpoint bytes y compatibilidad modelo-runtime;
- materializar runtime, habilitar executor o ejecutar inferencia;
- conectar la evidencia a un caller productivo o readiness.
