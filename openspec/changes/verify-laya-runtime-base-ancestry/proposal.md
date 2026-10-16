# Change: Verificación independiente de ancestry de la imagen base de Laya

Estado: propuesta con perfil externo capturado y congelado; pendiente de registrar
RED antes de cualquier implementación GREEN.

## Why

PR22 demostró por streaming que las layers comprimidas del runtime Laya y sus
DiffIDs coinciden por posición, pero conservó `base_ancestry_verified=false`. La
referencia de imagen base y las annotations del propio runtime son declaraciones
autocontenidas: por sí solas no prueban que la cadena OCI verificada descienda de
la imagen Python declarada.

PR36 cerrará esa brecha con evidencia externa, content-addressed y
module-authoritative del index OCI de la base, su manifest Linux/amd64 y su config.
La verificación comparará un prefijo exacto de descriptors comprimidos y DiffIDs de
la base contra la evidencia PR22. No consultará un registry, no abrirá archivos, no
materializará rootfs y no confiará en annotations para elevar el claim.

## What Changes

- Añadir un módulo puro y fail-closed de ancestry que acepte como único predecessor
  de supply la evidencia PR22 exacta e issued.
- Congelar dentro del módulo index digest/media type, selección Linux/amd64 única,
  manifest, config y cuatro layers de la base.
- Verificar por chunks los tres objetos JSON content-addressed con límites cerrados
  y reconstruir sus vínculos exactos por digest/size/media type.
- Exigir que los cuatro descriptors comprimidos y cuatro DiffIDs de la base formen
  el prefijo exacto de los diez tuples equivalentes de PR22.
- Emitir evidencia all-or-nothing, issued y no forjable; elevar únicamente
  `base_ancestry_verified=true`.
- Mantener falsos origen, licencia, receta/build/reproducibilidad, materialización,
  executor e inferencia. No consumir PR35; PR37 convergerá las autoridades.
- Exponer un summary canónico mínimo con schemas, claims y commitments; omitir
  bytes, paths, URLs de acceso, headers, digests internos, tuples y sizes.

## Exact Profile Frozen Before RED

La captura independiente verificó sin descargar layers:

- index OCI `sha256:840e180ebcc6e5c8efab209c43f5e40fd2af98cb49db5c7103c90539c56bb30e`,
  media type `application/vnd.oci.image.index.v1+json`, 9.131 bytes, 14
  descriptors y una única selección `linux/amd64`;
- manifest seleccionado `sha256:efc99f05ec45381aac55e2803c9a0245ea5b8c74965264498338e24e4bf66cc7`,
  media type `application/vnd.oci.image.manifest.v1+json`, 1.752 bytes;
- config `sha256:80abb94774d660831663290fe0b208b3e067b88647902f0f9e1d3a331a997afd`,
  media type `application/vnd.oci.image.config.v1+json`, 5.295 bytes,
  `architecture=amd64`, `os=linux` y `rootfs.type=layers`;
- exactamente cuatro descriptors comprimidos y cuatro DiffIDs de la base, ambos
  prefijos exactos de los diez descriptors/DiffIDs PR22.

El RED positivo deberá usar sólo este perfil. Ninguna receta forma parte de la API
positiva ni de la autoridad que eleva el claim.

## Impact

`base_ancestry_verified=true` significará solamente que los tres objetos externos
se verificaron por contenido, que sus enlaces index/manifest/config son coherentes
y que las layers comprimidas y DiffIDs de la base son el prefijo exacto de PR22.

No significará que un registry actual conserve esos objetos, que una receta haya
sido ejecutada, que la imagen esté firmada, que el builder o la fecha sean auténticos,
que la licencia sea válida, que PR35 converja con esta captura, ni que rootfs,
runtime, executor o inferencia hayan sido materializados. PR37 queda a cargo de la
convergencia supply completa.

## Traceability

- Épica: 3 — Integración y mejora.
- Historia: HU5 — retroalimentación humana asistida por runtime Laya.
- Capacidad OpenSpec: `human-feedback`.
- CRISP-DM: despliegue e integración experimental, todavía default-off.
- Configuraciones experimentales: ninguna cambia; base, +sintéticos, +anomalías y
  completa preservan datasets, splits, modelos, probabilidades y resultados.
- Impacto científico: ninguno sobre hipótesis o métricas. Es un gate de supply y no
  evidencia eficacia agronómica ni autoriza automatizar riego.

## Deferred

- Convergencia PR22/PR35/PR36 sobre un único snapshot y runtime identity (PR37).
- Materialización segura del rootfs y runtime (PR39/PR40).
- Habilitación de executor, smoke de inferencia o caller productivo (PR41+).
- Firma, transparency log, attestations de builder o consulta online de registry.
- Verificación o reproducción de una receta de build. La receta oficial Python se
  conserva sólo como observación; el Dockerfile Laya recapturado discrepa del runtime
  observado y constituye evidencia negativa, no autoridad positiva.
