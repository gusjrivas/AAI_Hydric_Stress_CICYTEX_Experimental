# Change: Congelar especificaciones de familias ensemble

## Why
Los planes ensemble congelaban nombres y configuración temporal, pero el ajuste y
los manifiestos todavía leían diccionarios globales mutables de hiperparámetros.
Una mutación accidental podía cambiar la evidencia científica sin alterar el plan.

## What Changes
- Introduce `EnsembleFamilySpec` profundamente inmutable.
- Incorpora specs site-locales a los planes Pergamino y Melchor Romero.
- Mantiene `FAMILY_PARAMS` como dict público compatible, pero deja de usarlo como
  fuente autoritativa para entrenamiento y manifiestos.
- Conserva callback, modelos, artefactos, orden y JSON existentes.
- No modifica CICYTEX, Laboratorio, Laya ni selección/tuning de modelos.

## Impact
HU6; `architecture-integration`. Fortalece reproducibilidad y procedencia sin
cambiar datasets, hipótesis, hiperparámetros ni resultados científicos.

