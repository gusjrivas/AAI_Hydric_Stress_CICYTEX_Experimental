# Change: Gate offline de readiness para Laya

Estado: implementado como evaluación offline; Laya permanece desactivada por defecto.

## Why

La integración consultiva existente valida el contrato HTTP y su fallback, pero no
demuestra calidad científica ni seguridad de la cadena de suministro. Antes de
mostrar sugerencias de Laya se necesita una evaluación reproducible, separada por
sitio y capaz de bloquear evidencia sintética, artefactos no verificados o degradación
oculta por promedios globales.

## What Changes

- Contrato inmutable y versionado para identidad de Laya, checkpoint, corpus y
  política de aceptación.
- Verificación local fail-closed de artefactos por tamaño y SHA-256, incluyendo el
  rechazo explícito de punteros Git LFS.
- Baseline determinista, independiente del sitio, para comparaciones posteriores.
- Métricas offline de exactitud, macro-F1, Brier, ECE, cobertura, exactitud selectiva,
  costo de abstención y latencia, con desglose por sitio.
- Reporte JSON canónico sin comentarios humanos, timestamps, rutas locales ni datos
  secretos.
- CLI exclusivamente offline para reproducir el gate con evidencia grabada.

## Impact

El cambio es aditivo y el gate queda aislado en `human_feedback.offline_readiness`.
Refactoriza con TDD el parsing interno de confianza del adaptador HTTP para compartir
la misma precedencia fail-closed con el evaluador offline, sin cambiar su endpoint,
contrato público ni variables `LAYA_*`. No modifica forecast, ingesta, recalibración,
training, registry, MLflow, frontend ni experimentos históricos.
Preserva las corridas de CICYTEX, Pergamino, Melchor Romero y laboratorio mock.

El corpus incluido es sintético y sólo prueba el contrato. Su decisión obligatoria es
`CHARACTERIZATION_ONLY`. Esta versión no puede emitir elegibilidad: aun con métricas
puntuales aprobadas, el máximo estado es `BLOCKED_SCIENTIFIC_METHOD_PENDING` hasta
incorporar corpus humano suficiente, LOSO, intervalos de confianza y comparación
pareada contra baseline. `production_enablement_authorized` permanece siempre en
`false`.
