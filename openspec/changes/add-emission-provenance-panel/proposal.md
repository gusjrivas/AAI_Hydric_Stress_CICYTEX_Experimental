# Proposal: panel de procedencia de una emisión producer_v2 (F6, incremento 2 de linaje)

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: despliegue/evaluación.
- Impacto científico: ninguno. No cambia modelos, umbrales, datos, resultados históricos, idempotencia/hash de emisión, `snapshot_id` ni `model_version`; no abre holdouts; no calcula nada nuevo. Sólo lee lo que `emit_snapshot` ya persistió.
- Impacto sobre hipótesis, alcance o arquitectura: ninguno. Sólo lectura; no automatiza riego.
- Problema: la traza del recorrido de Pergamino/Melchor Romero declaraba «SHA-256 del dataset» y «Commit» como no disponibles aunque el repositorio operacional guarda el SHA del dataset (`snapshot_id`) y, desde #64, la `code_identity` (commit/dirty) dentro de `input_snapshot.bundles`.

## Cambio
1. Backend: `GET /api/v2/sensors/{sensor_id}/batches/{batch_id}/provenance`. El recurso es el lote (la unidad que posee `input_snapshot`), no el pronóstico; la ruta cuelga de `/sensors/{sensor_id}` igual que el resto de v2 y no colisiona con `/forecasts/{forecast_id}`. Lógica en `OperationalRepository.get_batch_provenance`; el router sólo delega.
2. Lista blanca (esquemas cerrados `extra="forbid"` en `schemas_v2.py`): `batch_id`, `sensor_id`, `as_of_date`, `contract_version`, `snapshot_id`; por horizonte `status`, `reason_code`, `mode`, `model_reference` (`model_version`, `trained_through`, `calibration_version`, `assessment_reference`), `ensemble_identity_sha256`, `code_identity` (`available`, `commit`, `dirty`; `reason` nunca se expone por poder contener rutas) y, en ensambles, `code_identity` por componente; más `not_persisted = [full_config, mlflow_run, seed]`. Nunca `input_snapshot`, parquet, entorno ni hashes de archivos.
3. `code_identity` ausente (bundles/lotes previos a #64) se devuelve `null` y la UI dice «no registrado»; jamás se infiere del checkout actual. Lote inexistente: 404 `batch_not_found` en el formato de error v2.
4. OpenAPI regenerado con `npm run api:generate`; guardas de identidad congelada (`test_openapi_typescript_ci_contract.py`, `test_openapi_typescript_composition.py`) actualizadas con el tamaño/hash/conteo de operaciones nuevos, siguiendo el precedente de #53.
5. Frontend: `provenanceApi.ts`, `EmissionProvenancePanel` (carga, error con reintento, sin romper si el backend cae) integrado bajo la traza del recorrido; la traza conserva sólo «Particiones» y «Linaje de recalibración» como no disponibles, y el panel declara configuración completa, corrida MLflow y semilla como no disponibles.

## No verificado / fuera de alcance
Persistir configuración completa, MLflow o semilla por emisión (requeriría cambios de persistencia). Revisión visual renderizada contra un backend con bundles nuevos.
