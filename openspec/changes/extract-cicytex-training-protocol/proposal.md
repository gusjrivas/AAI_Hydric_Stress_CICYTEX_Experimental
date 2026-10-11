# Change: Extraer el protocolo de entrenamiento temporal CICYTEX

## Why
Los dos runners CICYTEX compartían features, familias y particiones mediante una
dependencia directa del ensemble causal hacia el runner experimental. Esa relación
entre orquestadores impedía evolucionarlos de forma independiente y dejaba la
semántica científica sin un dueño explícito.

## What Changes
- Extrae features, hiperparámetros autorizados, cortes temporales y selección de
  particiones a `experiment_runner.cicytex.training_protocol`.
- Hace que ambos runners dependan del protocolo compartido y no entre sí.
- Mantiene los símbolos históricos de `experiment.py` como reexports compatibles.
- Caracteriza antes del refactor horizontes 1/2/3, aislamiento por sonda, cortes
  50/65/80/100, cobertura de particiones, errores y no mutación.
- No modifica umbrales P20, ajuste, calibración, selección, métricas, procedencia,
  artefactos, API, UI ni Laya.

## Impact
HU6; `architecture-integration`. El cambio crea un seam científico estable para
extraer posteriormente la preparación por horizonte sin alterar resultados.
