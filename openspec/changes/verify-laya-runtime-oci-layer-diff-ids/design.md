## Context

PR20 capturó controles y doce blobs OCI exactos desde una raíz común. PR21 validó
la semántica del config y conservó diez DiffIDs declarados, pero mantuvo
`oci_layer_diff_ids_verified=false`. PR22 añade un plan puro, un verificador de
streams sin I/O y un adaptador filesystem Linux seguro. El layout de ~612 MB sigue
externo a Git y no existe caller productivo.

## Goals / Non-Goals

### Goals

- Ligar exactamente diez descriptors/receipts comprimidos con los diez DiffIDs de
  PR21 por identidad y posición.
- Revalidar bytes comprimidos y calcular DiffIDs incrementalmente con límites.
- Capturar todo desde una raíz Linux descriptor-relative, all-or-nothing.
- Emitir evidencia sellada y un summary público mínimo.

### Non-Goals

- Soportar gzip multi-member genérico o formatos distintos del perfil fijado.
- Parsear TAR, aplicar whiteouts o verificar/materializar un rootfs.
- Probar origen, autenticidad, licencia o base ancestry.
- Materializar runtime/checkpoint, habilitar executor o ejecutar inferencia.

## Decisions

### 1. Plan puro e identity-bound

`prepare_laya_oci_layer_diff_id_plan` acepta exclusivamente evidencia PR21 exacta
y profundamente válida. El plan liga por identidad de objeto la misma runtime
identity, evidencia/layout plan PR20, blobs `layer-00`…`layer-09`, receipts de bytes
comprimidos y DiffIDs declarados PR21, todos como tuplas exactas de cardinalidad diez.
Crear el plan no abre, lee ni descomprime archivos y mantiene falsos DiffIDs/rootfs/origin.

### 2. Verificador incremental de un único member

`verify_laya_oci_layer_diff_id_chunks` autoriza primero un digest SHA-256 único del
plan. Delega el mismo stream al verificador PR20 para revalidar tamaño y SHA-256 de
los bytes comprimidos y, simultáneamente, usa zlib en modo gzip para calcular el
SHA-256 del contenido descomprimido. El resultado sólo se acepta si coincide con el
DiffID declarado en la misma posición.

Cada chunk debe ser `bytes` exacto, no vacío y de hasta 1 MiB; se admiten hasta
1.024 chunks. La salida de cada llamada de descompresión también se limita a 1 MiB.
Cada layer tiene cap descomprimido de 2 GiB y el conjunto cap de 3 GiB; el layout
real observado suma menos de 3 GiB. El verificador rechaza truncamiento, CRC/ISIZE
inválido, trailing data, segundo member y falta de progreso. Esta restricción de
single-member es deliberada y no constituye soporte gzip genérico.

### 3. Captura segura y all-or-nothing

El adaptador falla antes de abrir si PR21 es inválida o la plataforma no ofrece las
capacidades Linux requeridas. Abre la raíz y sus componentes descriptor-relative,
captura controles, exige inventario cerrado y reconstruye el plan exacto. Luego:

1. reabre y rehashéa las doce blobs del layout para size/SHA-256 comprimido;
2. reabre las diez layers en orden y produce un receipt DiffID por posición;
3. confirma que cada fingerprint coincide entre ambas pasadas y con su path;
4. ejecuta el sweep final de raíz, controles, directorios y blobs;
5. cierra cada FD owned exactamente una vez antes de crear autoridad y evidencia.

La evidencia se sella únicamente con diez receipts exactos, ordenados, same-root,
inventario/sweep válidos y todos los descriptores cerrados. Un error de open/read,
scandir/fstat/close, gzip, digest, orden, cardinalidad o cap cierra los FDs y no
produce evidencia parcial. La atomicidad es la observada por fingerprints y sweep,
no una afirmación de snapshot filesystem absoluto.

### 4. Claims y límites

La evidencia hereda los claims verdaderos PR20/PR21 y añade exclusivamente
`oci_layer_diff_ids_verified=true`. Permanecen falsos `tar_semantics_verified`,
`oci_rootfs_verified`, origen, licencia, base ancestry, checkpoint, rootfs/runtime
materialized, executor e inferencia. Los receipts prueban hashes del flujo
descomprimido; no inspeccionan headers/entries TAR ni whiteouts.

Los cinco roles originales (`dependency_lock`, `sbom`, `runtime_config`,
`checkpoint_manifest`, `oci_manifest`) y el runtime identity no cambian. Las layers
son evidencia externa del rol `oci_manifest`, no nuevos roles. No hay caller
productivo ni se versionan los blobs.

### 5. Privacidad y API

La API pública mínima ofrece preparación del plan, verificación de chunks y summary,
más los tres tipos sellados y constantes de schemas/caps allowlisted. El finalizador
y la autoridad de captura permanecen privados al adaptador. El summary canónico
expone schemas, claims y `runtime_identity_sha256`; omite raíz, paths, digests
comprimidos, DiffIDs, sizes y contenido. Errores y `repr` tampoco filtran esos datos.

### 6. Evidencia de tests

- RED plan/ancestry `07e7224`; GREEN `4c80ebc`.
- RED streaming/límites `bcfa8db` y autorización de dependencia `85b83a2`;
  GREEN `c70ace4`.
- RED adapter/captura segura `b243c14`; GREEN `1e46ecd`.
- Suite focal final: `67 passed, 32 skipped`.
- Gate real Linux: `1 passed`, con exactamente 12 llamadas de revalidación blob y
  10 llamadas de verificación DiffID.
- Suite Laya completa: `983 passed, 34 skipped`; Black y Ruff limpios.

El gate externo fue manual, serial y opt-in. No se declara CI obligatorio ni se
eleva la preservación de fingerprint a enforcement de permisos/mount read-only.

## Risks / Trade-offs

- El perfil cerrado rechaza gzip multi-member aunque pudiera ser válido en otros
  contextos; evita ambigüedad en esta evidencia concreta.
- Dos pasadas por las layers aumentan I/O, pero separan la autoridad comprimida PR20
  del cálculo DiffID y permiten detectar reemplazos entre pasadas.
- Verificar DiffIDs reduce la brecha hacia rootfs, pero TAR/whiteouts siguen siendo
  una frontera independiente y obligatoria antes de afirmar `oci_rootfs_verified`.
