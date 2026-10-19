# Proposal: objetivos táctiles y errores de red en español en el laboratorio (F5)

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: evaluación/despliegue.
- Impacto científico: ninguno. No cambia modelos, umbrales, protocolos, contrato OpenAPI ni resultados históricos.
- Problema: a <=600 px los selects (~36 px), los `summary` (~21 px) y el enlace «Ir al Laboratorio» (~20 px) del laboratorio quedaban bajo 44 px; con el backend apagado se mostraba el texto crudo «Failed to fetch».
- Cambio (sólo presentación): regla CSS `@media (max-width: 600px)` acotada a `.sensor-lab`; helper compartido `userFacingErrorMessage` (`frontend/src/features/shared/errorMessage.ts`) usado por el laboratorio, `QualityPanel` y `useForecastWorkspace`. Los detalles de error enviados por el servidor se conservan sin cambios.
- Bloque 7 (revisión de Laya): la UI de arquitectura ya presenta Laya como adaptador consultivo opcional, desactivado por defecto, sin sugerencias reales y con utilidad no evaluada; se agrega un test de regresión que fija esas afirmaciones y prohíbe validación científica, corpus real o calibración. No se encontró el literal «BLOCKED» asociado a Laya en `frontend/`.
- Fuera de alcance: timeout/fallback de Laya (backend, `src/human_feedback/adapters/laya_http.py`), sin cambios.
