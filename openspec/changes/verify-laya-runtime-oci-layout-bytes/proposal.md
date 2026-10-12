# Change: Verificación exacta por bytes del layout OCI de Laya

Estado: implementado como gate externo opt-in, serial y fail-closed sobre Linux;
no materializa ni ejecuta el runtime.

## Why

PR19 validó los 3.166 bytes del manifest OCI y sus enlaces internos, pero no
capturó los targets referenciados. Por eso `oci_bytes_verified` permanecía falso.
PR20 añade una capa de evidencia externa para comprobar desde una única raíz los
dos controles OCI y los doce blobs exactos, sin incorporar la imagen de 612 MB al
repositorio ni ampliar los cinco roles de artefactos del runtime.

## What Changes

- Mantiene sin cambios los cinco roles PR15/PR16: `dependency_lock`, `sbom`,
  `runtime_config`, `checkpoint_manifest` y `oci_manifest`.
- Deriva desde evidencia PR19 un plan cerrado de 14 archivos: `oci-layout`,
  `index.json`, manifest, config y diez layers comprimidas.
- Verifica los controles exactos, el enlace index→manifest y los doce blobs por
  tamaño/SHA-256 mediante streams acotados.
- Captura controles, inventario y blobs descriptor-relative desde una única raíz
  Linux, revalida fingerprints y paths en un sweep final y sólo entonces sella la
  evidencia.
- Eleva los flags de bytes/inventario/same-root exactos y mantiene falsos todos los
  claims semánticos u operativos no demostrados.
- Trata la fuente externa canónica como input read-only: el gate no la modifica,
  verifica que su fingerprint se preserve y usa un clon descartable distinto para
  la captura positiva y las pruebas adversariales. PR20 no acredita ni impone
  permisos o mount read-only del host.
- Mantiene el adaptador sin caller productivo; el gate se activa manualmente mediante
  `LAYA_RUNTIME_OCI_LAYOUT_ROOT` y no se declara como job obligatorio de CI.
- Mantiene privados paths y digests de controles/blobs en el summary, pero publica
  deliberadamente `runtime_identity_sha256` como commitment de identidad.

## Impact

`oci_bytes_verified=true` significa que, durante una captura concreta, los dos
controles y los doce blobs del perfil cerrado se leyeron íntegramente desde la misma
raíz, coincidieron en size/SHA-256 y conservaron fingerprints e inventario hasta el
sweep final. No significa que el config sea semánticamente válido, que los diffIDs
coincidan, que el rootfs sea correcto, que los bytes tengan origen/licencia/ancestry
probados, ni que la imagen haya sido desempaquetada, materializada o ejecutada.

El layout completo vive fuera de Git. Los fixtures versionados contienen sólo los
dos controles pequeños; por eso una suite ordinaria sin la variable opt-in no puede
presentarse como evidencia positiva de los 612 MB.

El release gate real se ejecutó serialmente sobre Linux con la evidencia externa y
dio `224 passed, 1 skipped`, incluyendo el hardening del cap de traversal agregado
después; el único skip fue el test específico de Windows. Ese resultado es evidencia
manual/opt-in de PR20, no ejecución de CI ni prueba de que exista un job obligatorio.

## Reconciliación

Este successor satisface conceptualmente PR19 tasks 4.1 y 4.2: captura y verifica
por bytes controles, manifest, config y diez layers, y cierra sus enlaces. No edita
el change histórico ni altera el significado más estrecho de la evidencia PR19.

## Deferred

- interpretar config, history, `rootfs.diff_ids` o filesystem resultante;
- verificar origen, firma, licencia efectiva o ancestry de la base;
- verificar bytes del checkpoint o compatibilidad modelo-runtime;
- materializar rootfs/runtime, habilitar executor o ejecutar inferencia;
- conectar el adaptador a un caller productivo o readiness;
- convertir el gate opt-in en CI obligatorio, decisión que PR20 no toma.
