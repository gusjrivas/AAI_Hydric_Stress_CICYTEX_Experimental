# Proposal: trazabilidad de una predicción concreta en CICYTEX (F6, prioridad 4)

- HU: HU6 (UI) con proyección de lectura sobre el paquete archivado de HU7/HU8. Capacidad: `alerting-ui`. Fase CRISP-DM: despliegue/evaluación.
- Impacto científico: ninguno. No cambia modelos, umbrales, datos, particiones ni protocolo; no abre holdouts; no calcula nada nuevo.
- Problema: la vista de arquitectura sólo citaba rutas de código; ninguna pantalla mostraba de dónde sale una predicción concreta (paquete, corridas de modelos, particiones).

## Cambio
1. Backend: `GET /api/v2/cicytex/replay/provenance`, proyección mínima de sólo lectura del `summary.json` archivado con lista cerrada de campos: identidad del dataset (SHA-256), commit, semilla, política del ensamble, particiones, umbral de entrenamiento y corridas MLflow por modelo y horizonte. No incluye métricas ni filas de predicción. Contrato tipado (OpenAPI regenerado, guardas congeladas actualizadas) y 503 si el paquete no está preparado.
2. Frontend: panel «Trazabilidad de esta predicción» en el recorrido CICYTEX (fuente, emisión, objetivo y, en detalle, identidad del paquete y corridas de los modelos del horizonte de la sesión).
3. Lo que no existe se declara: «Versión del modelo: no disponible» y «Linaje de recalibración: no disponible en este recorrido». Si la proyección falla, el recorrido sigue operativo y lo dice.

## Evidencia
`docs/design/capturas/cicytex-trazabilidad-desktop.png`, tomada contra un backend local con el paquete real. Los ids de corrida del panel coinciden con `results/cicytex/causal_replay/summary.json`.
