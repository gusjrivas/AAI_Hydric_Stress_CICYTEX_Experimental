## Context

PR22 verificó por streaming diez layers comprimidas y diez DiffIDs del runtime Laya,
pero mantuvo `base_ancestry_verified=false`. Su metadata declara la base
`docker.io/library/python:3.11.10-slim-bookworm` por digest; esa declaración interna
no es autoridad suficiente.

La captura externa de PR36 obtuvo sólo tres objetos pequeños e inmutables del
registry: index, manifest Linux/amd64 y config. No descargó layers. El módulo puro
revalidará esos bytes y comparará sus cuatro descriptors y cuatro DiffIDs con el
prefijo de la evidencia PR22. PR22 será el único predecessor. PR35 queda fuera para
que PR37 sea el único slice que converja todas las autoridades supply.

## Goals / Non-Goals

### Goals

- Verificar por contenido index OCI, manifest seleccionado y config externos.
- Reconstruir los enlaces por digest, size, media type y plataforma exactos.
- Demostrar igualdad posicional del tuple completo de cuatro layers/DiffIDs de la
  base con las primeras cuatro posiciones de los tuples PR22 de diez elementos.
- Producir evidencia pura, determinista, acotada, all-or-nothing e issued.
- Elevar sólo `base_ancestry_verified` con summary público mínimo.

### Non-Goals

- Consultar un registry, resolver tags o aceptar perfiles genéricos.
- Depender de PR35 o declarar convergencia source/checkpoint/runtime.
- Probar firma, builder, timestamp, licencia, receta ejecutada o build reproducible.
- Parsear TAR, componer/materializar rootfs o ejecutar Laya.
- Introducir adapter, caller productivo, readiness o cambios en UI/API.

## Decisions

### 1. Perfil exacto y module-authoritative

El módulo será la única fuente del perfil positivo. Los callers no podrán inyectar
digests, media types, plataforma, cardinalidades ni caps. Aceptará exactamente:

- index OCI `sha256:840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e`,
  9.131 bytes, 14 descriptors, media type
  `application/vnd.oci.image.index.v1+json`;
- una única entrada `linux/amd64` que selecciona manifest OCI
  `sha256:efc99f05ec45381aac55e2803c9a0245ea5b8c74965264498338e24e4bf66cc7`,
  1.752 bytes, media type `application/vnd.oci.image.manifest.v1+json`;
- config OCI `sha256:80abb94774d660831663290fe0b208b3e067b88647902f0f9e1d3a331a997afd`,
  5.295 bytes, media type `application/vnd.oci.image.config.v1+json`,
  `architecture=amd64`, `os=linux` y `rootfs.type=layers`.

Cualquier objeto extra, ausente, duplicado, reordenado o alternativo fallará cerrado.

### 2. Ancestry PR22 exacta sin autoridades laterales

`prepare_laya_runtime_base_ancestry_plan` aceptará exclusivamente una instancia
exacta, issued y profundamente revalidada de
`LayaRuntimeOciLayerDiffIdsEvidence`. Ligará por identidad el runtime identity,
config/layout ancestry, descriptors comprimidos, receipts DiffID y claims PR22.
No aceptará equivalentes por forma, `object.__new__`, `dataclasses.replace`,
copy/pickle, clases derivadas ni evidencia PR35.

Preparar el plan no consumirá bytes. La revalidación no prestará tokens ni registrará
objetos del caller como issued.

### 3. API pura y verificación incremental

La superficie pública tendrá sólo tres operaciones:

1. `prepare_laya_runtime_base_ancestry_plan`;
2. `verify_laya_runtime_base_ancestry_objects`;
3. `canonical_laya_runtime_base_ancestry_summary_bytes`.

El verificador agregado recibirá el plan issued y exactamente tres streams en orden:
index, manifest y config. Cada chunk será `bytes` exacto y no vacío. Calculará
SHA-256 y size antes de interpretar contenido; sólo bytes que coincidan con el perfil
podrán participar en el grafo.

Los caps tendrán una única fuente de verdad: chunk máximo 16 KiB, 64 chunks por
objeto, 16 KiB por objeto y 32 KiB agregados. El JSON se limita a profundidad 16,
512 nodos, strings de 4 KiB, arrays de 32 items y objetos de 64 keys. El parser
rechazará duplicate keys, números no enteros donde no correspondan, NaN/infinito,
Unicode no canónico, fields/tipos extra y trailing bytes. Los digests serán siempre
lowercase `sha256:<64 hex>` y los sizes enteros positivos exactos.

Los tests probarán límite y `cap + 1`, consumo perezoso, corte temprano y que ningún
iterable posterior sea consumido tras el primer fallo.

### 4. Grafo index/manifest/config

El index deberá contener exactamente 14 descriptors y una única selección
`linux/amd64` que enlace el manifest por digest, media type y size. El manifest
deberá enlazar el config por los tres campos y contener exactamente cuatro layers.
El config deberá declarar los fields de plataforma congelados y exactamente cuatro
`rootfs.diff_ids`. Ninguna annotation podrá sustituir una arista content-addressed.

Descriptors alternativos, una segunda entrada equivalente, un config cross-linked
desde otro manifest o un objeto correcto bajo otro plan/sesión se rechazarán.

### 5. Prefijo dual comprimido + DiffID

Los cuatro descriptors base, todos con media type
`application/vnd.oci.image.layer.v1.tar+gzip`, son:

1. `sha256:bc0965b23a04fe7f2d9fb20f597008fcf89891de1c705ffc1c80483a1f098e4f`, 28.231.580 bytes;
2. `sha256:c58b365c3bcb57c930511e3fef962d15491ef2daba1e111fb5a6b41dbdecfc6b`, 3.317.301 bytes;
3. `sha256:3bc3f72291794502343f023ab10455e459897b13a73f38b6b56cf266dccb7ec5`, 16.202.769 bytes;
4. `sha256:42dacf6a4601de71542906f1be2bca5a78b8f430479b260a7097b9870498af69`, 251 bytes.

Sus DiffIDs, en el mismo orden, son:

1. `sha256:c0f1022b22a9b36851b358f44e5475e39d166e71a8073cf53c894a299239b1c5`;
2. `sha256:bc9155b10ccec596b3283ceca7cc847bc4046db14eab7f77b9b170b5e825e0a5`;
3. `sha256:0266a6d27cd42ef4422dfb0b6dbd4186f3524600502559e13947f8d4de65c931`;
4. `sha256:cfc6e3b5400ce78d3df9c4826f39a78db0e7e9a01d2581b860b5611ac6829af6`.

PR22 contiene diez descriptors y diez DiffIDs. La evidencia sólo se sella si ambos
tuples externos de cuatro elementos coinciden exactamente con sus primeras cuatro
posiciones. Se rechaza prefix vacío, subsecuencia no inicial, reorder, duplicado,
inserción, desigual cardinalidad o coincidencia unilateral compressed/DiffID.

Esta igualdad prueba ancestry de contenido OCI, no historia de construcción. Las
seis layers posteriores del runtime Laya quedan fuera del claim de la base.

### 6. Recetas observadas sin autoridad positiva

La captura observó la receta oficial Python en commit
`37a6827e0b7a9ef099cfdec5de305e3d4cea7331`, path
`3.11/slim-bookworm/Dockerfile`, blob Git
`0cc0131f8f1d5465873f413f53e623b56dc7c9c2`, SHA-256
`4bb9a1f838ba1d940d08169464d24d50fe6776bc818ba656a1fd14ca4ab500f8`
y 4.045 bytes. El manifest la asocia mediante annotation y sus bytes declaran
`debian:bookworm-slim` y Python `3.11.10`.

Esto se registra sólo como observación; no entra en la API positiva ni eleva flags.
Además, el Dockerfile Laya recapturado discrepa materialmente del runtime observado:
base trixie, usuario 10001 y entrypoint Python frente a bookworm, usuario 65532 y
uv/laya-serve. La discrepancia es evidencia negativa. Permanecen falsos
`runtime_build_recipe_verified`, `build_process_attested` y
`reproducible_build_verified`.

### 7. Issuance, sesión y atomicidad

Plan, envelopes internos, receipts y evidencia final serán dataclasses frozen,
exact-class, creadas sólo por factories privadas y registradas por identidad débil.
Cada verificación tendrá una autoridad de sesión de un solo uso; receipts de otra
sesión, plan o posición se rechazarán aunque sus fields coincidan.

Sólo el verificador agregado podrá sellar evidencia después de verificar los tres
objetos, el grafo y el prefijo dual. Cualquier error produce cero evidencia y revoca
la sesión. Clones, replay, mezcla entre planes o reuso después de fallo/success
deben fallar antes de elevar claims.

### 8. Claims y summary conservadores

La evidencia heredará los claims verdaderos de PR22 y añadirá exclusivamente
`base_ancestry_verified=true`. Permanecerán falsos `origin_verified`,
`license_verified`, `runtime_build_recipe_verified`, `build_process_attested`,
`reproducible_build_verified`, `rootfs_materialized`, `runtime_materialized`,
`executor_available` e `inference_executed`.

El summary canónico expondrá sólo schema versions, booleans allowlisted,
`runtime_identity_sha256` y commitments públicos explícitamente aprobados. Omitirá
payloads, paths, URLs de acceso, auth/headers, digests internos, tuples y sizes.
`repr` y errores tendrán la misma disciplina.

## TDD and Gates

1. RED de plan/issuance/ancestry PR22 y superficie pública.
2. RED de bytes/grafo/parsing/caps/prefijo dual/claims/privacidad.
3. GREEN mínimo del módulo puro, sin adapter ni I/O.
4. Red-team de forgery, replay, mix-and-match, parser differential y cap bypass.
5. Suite focal, Laya completa, regresiones históricas, OpenSpec strict, Black/Ruff
   y gate independiente P0/P1/P2=0 sobre SHA exacto.

## Risks / Trade-offs

- El perfil cerrado no generaliza a otras variantes Python o plataformas; es una
  propiedad de seguridad deliberada, no una API de registry genérica.
- La comparación usa descriptors externos y receipts PR22 ya verificados; PR36 no
  vuelve a descargar los aproximadamente 47,8 MB comprimidos de la base.
- El prefijo dual prueba ancestry de contenido, no receta ni historia de build.
- Mantener PR35 fuera evita mix-and-match silencioso ahora, pero exige PR37 antes de
  presentar supply como una autoridad convergente.
