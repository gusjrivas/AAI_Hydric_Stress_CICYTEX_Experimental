# Change: Contrato de evidencia de predicciones LOSO para Laya

Estado: implementado como contrato estructural de evidencia; no ejecuta Laya, no
verifica el runtime y no acredita ejecución científica ni suficiencia.

## Why

El plan LOSO define folds privados y reproducibles, pero todavía no existe una
frontera que ligue un lote de predicciones a ese plan, al corpus, al runtime
declarado, al protocolo de ejecución y a una revisión concreta del modelo. Sin esa
frontera, filas faltantes, duplicadas, asignadas al fold incorrecto o producidas por
otra revisión podrían aceptarse como evidencia y un resumen público podría filtrar
IDs, probabilidades o commitments vulnerables a ataques de diccionario.

## What Changes

- Define `laya-loso-execution-contract-v1`, ligado por digest al plan LOSO y al
  corpus, y por identidad declarada a runtime, protocolo, proveedor y revisión del
  modelo.
- Restringe el proveedor a `laya-http` y la revisión del modelo a un SHA-1 completo,
  lowercase y distinto del sentinel nulo.
- Exige exactamente una predicción para cada registro outer-test de los tres folds;
  rechaza ausencias, extras, duplicados, folds incorrectos y registros de fit o
  calibración.
- Valida categorías y probabilidades ordenadas, argmax único, confidence opcional y
  latencia finita no negativa, junto con identidad de proveedor y revisión.
- Canonicaliza el lote por orden contractual de fold e ID de ejemplo y conserva un
  `prediction_content_sha256` privado sobre todas las filas normalizadas.
- Publica sólo identidad contractual, attestations no verificadas, conteos y
  agregados seguros de latencia. No publica filas, categorías, probabilidades, IDs
  privados ni el commitment del contenido.
- Mantiene ejecución, suficiencia científica, shadow review y producción en falso;
  validar evidencia estructural no equivale a haber ejecutado el protocolo.

## Impact

El cambio es aditivo y queda aislado en `human_feedback.evaluation_execution`.
Consume un plan LOSO ya validado y no modifica backend, adapters, gate offline,
forecast, ingesta, entrenamiento, recalibración, runners ni scripts. Las corridas
existentes de CICYTEX, Pergamino, Melchor Romero y laboratorio mock conservan sus
contratos.

La referencia de runtime y los digests de protocolo son declaraciones ligadas al
contrato, no verificaciones de origen, suministro o entorno ejecutado. Del mismo
modo, recibir un lote completo y bien formado sólo acredita que la evidencia
presentada satisface este schema.

## Deferred

Quedan expresamente fuera de este cambio y se abordarán desde PR15:

- materializar y verificar identidad de runtime, lockfile y SBOM;
- verificar origen, supply chain y correspondencia entre runtime y artefactos;
- implementar el executor o adapter HTTP de Laya y ejecutar predicciones reales;
- atestiguar ejecución gold-blind y completar el protocolo científico;
- calcular métricas, calibración, baseline pareado e intervalos bootstrap;
- decidir readiness, shadow review o habilitación productiva.
