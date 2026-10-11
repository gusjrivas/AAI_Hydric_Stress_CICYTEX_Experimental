# Change: Introducir contrato y fuente del dataset CICYTEX

## Why
La carga normalizada de las 21 sondas CICYTEX estaba concentrada en una función
concreta. Sin un contrato versionado ni un puerto, sustituir CSV por otra fuente
obligaría a modificar el borde usado por los experimentos científicos.

## What Changes
- Declara `CicytexDatasetContract` como configuración científica inmutable y
  versionada del dataset normalizado.
- Introduce el puerto estructural `CicytexDatasetSource`.
- Encapsula la lectura existente en `CsvCicytexDatasetSource`.
- Conserva `load_normalized_cicytex()` como fachada DataFrame compatible.
- Caracteriza antes del refactor orden, tipos, columnas adicionales, faltantes,
  validaciones y no modificación de los archivos de entrada.
- No modifica features, splits, modelos, artefactos, scripts, API ni Laya.

## Impact
HU6; `architecture-integration`. El cambio prepara fuentes alternativas y una
trazabilidad posterior sin alterar decisiones científicas ni resultados vigentes.
