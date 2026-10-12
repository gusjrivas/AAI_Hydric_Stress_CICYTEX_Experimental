# Change: Extraer la preparación compartida por horizonte CICYTEX

## Why
Aunque los runners CICYTEX ya compartían features y cortes temporales, ambos
repetían la composición científicamente sensible que elimina filas incompletas,
crea cuatro particiones y calcula el percentil P20 sólo con entrenamiento. Esa
duplicación permitía que los runners divergieran silenciosamente.

## What Changes
- Introduce `HorizonPreparation` como resultado estructuralmente inmutable con
  copias mutables e independientes de las cuatro particiones.
- Introduce `prepare_horizon()` como composición pura del protocolo existente.
- Hace que ambos runners deleguen la preparación de los horizontes 1, 2 y 3.
- Mantiene en cada runner sus etiquetas, validaciones, mensajes, modelos, métricas
  y efectos externos.
- No modifica features, cortes, P20, calibración, MLflow, procedencia, artefactos,
  API, UI ni Laya.

## Impact
HU6; `architecture-integration`. El cambio reduce duplicación científica y crea
el seam necesario para seguir adelgazando ambos orquestadores sin alterar
resultados.
