# Change: Extraer motor común de entrenamiento ensemble para demos

## Why
Los runners científicos de Pergamino y Melchor Romero contienen un flujo de
preparación, entrenamiento, calibración y exportación casi idéntico. Mantener
esa duplicación aumenta el riesgo de divergencia científica y hace costoso
incorporar nuevos sitios. La extracción debe empezar por Pergamino y conservar
todos los contratos y artefactos actuales antes de intentar un segundo consumidor.

## What Changes
- Introduce un plan científico inmutable que compone `TemporalCutPlan` y
  `VariableMetadata` existentes.
- Extrae un motor sin conocimiento de sitio para preparar, entrenar, calibrar y
  exportar bundles ensemble.
- Convierte `run_demo_from_frame` de Pergamino en una fachada compatible que
  conserva el ciclo de vida de `run_manifest.json`.
- Mantiene Melchor Romero, CICYTEX, Laboratorio y Laya sin modificaciones.
- Exige evidencia RED/GREEN y regresión multisitio antes de integrar.

## Impact
HU6; `architecture-integration`. CRISP-DM: despliegue e integración. No cambia
hipótesis, datasets, cortes temporales, configuraciones experimentales, familias,
semillas, endpoints ni formatos de artefactos. Reduce duplicación detrás de una
fachada existente y prepara la incorporación posterior de otro sitio.

