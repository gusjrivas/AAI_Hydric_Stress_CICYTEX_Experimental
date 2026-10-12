# Change: Plan estructural LOSO y cohorte de calibración para Laya

Estado: implementado como plan estructural determinista; no ejecuta evaluación ni
calibración y no acredita suficiencia científica.

## Why

El contrato del corpus humano candidato congela procedencia, sitios y grupos, pero
no define cómo separar ajuste, calibración y evaluación cross-site. Sin un plan
explícito, ejemplos correlacionados de un mismo grupo podrían cruzar particiones, la
selección de calibración podría depender de etiquetas o una descripción pública
podría filtrar identificadores privados.

## What Changes

- Define `laya-loso-evaluation-plan-v1` con un fold por cada uno de los tres sitios
  requeridos: `cicytex`, `melchor-romero` y `pergamino`.
- En cada fold reserva el sitio completo de test y divide los otros dos sitios en
  ajuste y calibración sin separar grupos.
- Fija la política `laya-loso-group-calibration-sha256-v1`: por cada sitio selecciona
  para calibración `ceil(20% del número de grupos)`, ordenados por un hash versionado
  de política, sitio y `group_id`, sin RNG ni seed.
- Exige al menos dos grupos por sitio y falla de forma cerrada cuando el corpus no
  permite que cada sitio de entrenamiento contribuya tanto a ajuste como a
  calibración.
- Reutiliza la misma cohorte de calibración de un sitio en todos los folds donde ese
  sitio participa como entrenamiento.
- Conserva un commitment interno de la asignación, excluido de `repr` y del summary
  público, y publica sólo identidad segura del corpus, metadata contractual,
  conteos agregados y flags fail-closed.

## Impact

El cambio es aditivo y está aislado en `human_feedback.evaluation_split`. Consume un
`EvaluationCorpus` ya validado y no modifica backend, gate offline, forecast,
ingesta, entrenamiento, recalibración ni runners existentes.

`structurally_valid=true` significa únicamente que el particionado satisface este
contrato. No demuestra N suficiente, balance por sitio o categoría, muestreo
aleatorio, representatividad ni validez estadística. La política hash es ciega a
comentarios, anotaciones y gold labels, pero quien controle los nombres de grupo
podría influir en el ranking. Por eso `corpus_id`, `group_id` y el protocolo de
muestreo MUST quedar congelados antes de construir o inspeccionar el plan.

## Deferred

Quedan expresamente fuera de este cambio:

- ejecutar un runner LOSO o ajustar modelos;
- elegir o ajustar un calibrador y aplicar tuning;
- calcular métricas, baseline pareado o intervalos bootstrap;
- decidir readiness, suficiencia científica o elegibilidad para shadow review;
- integrar runtime, backend o producción.
