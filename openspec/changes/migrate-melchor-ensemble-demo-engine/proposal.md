# Change: Migrar Melchor Romero al motor común de demos ensemble

## Why
El motor neutral introducido para Pergamino sólo demuestra su abstracción al
incorporar un segundo sitio con diferencias científicas reales. Melchor Romero
mantiene dataset, imputación y manifiesto propios, pero duplicaba entrenamiento,
calibración y exportación.

## What Changes
- Declara un plan científico inmutable para Melchor Romero.
- Delega preparación de features, targets, particiones y exportación al motor común.
- Conserva carga parquet, imputación causal, threshold y manifiesto en la fachada.
- Preserva firma, reexportaciones, artefactos, inferencia y errores existentes.
- No modifica Pergamino, CICYTEX, Laboratorio ni Laya.

## Impact
HU6; `architecture-integration`. CRISP-DM: despliegue e integración. No cambia
ningún dataset, corte temporal, familia, parámetro, hipótesis o endpoint.

