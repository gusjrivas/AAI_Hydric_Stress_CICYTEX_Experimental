# Change: Versionar snapshot y procedencia de entradas CICYTEX

## Why
Los experimentos consumen 21 CSV normalizados, pero el campo histórico
`dataset_sha256` identifica el CSV original `DTPT_Figure_8.csv`. Esa diferencia
impide demostrar qué bytes exactos fueron parseados sin reinterpretar artefactos
ya publicados.

## What Changes
- Captura una sola vez los bytes de las 21 series declaradas y parsea esos mismos
  bytes.
- Publica un manifiesto canónico con identidad por archivo y hash agregado.
- Separa explícitamente snapshot normalizado, CSV original y ZIP de distribución.
- Conserva la semántica histórica de `dataset_sha256` y `zip_sha256`.
- Añade un sidecar versionado y opcional a ambos runners CICYTEX.
- Declara la derivación original-normalizados como externa no verificada.
- No modifica features, splits, P20, familias, calibración, predicciones, API,
  Laboratorio ni Laya.

## Impact
HU6; `architecture-integration`. Aumenta reproducibilidad y auditabilidad sin
migrar artefactos previos ni cambiar el borde DataFrame existente.
