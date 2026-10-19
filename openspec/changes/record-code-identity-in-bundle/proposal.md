# Change: registrar la identidad del codigo en `bundle.json`

## Motivacion

`persist_operational_run` captura `code_identity` (commit y estado del arbol)
pero solo lo guarda en `run_metadata.json`, que no viaja con cada bundle. Un
bundle cargado por el servicio no permite saber con que commit se entreno.
Incremento 1 de linaje: cerrar esa brecha para ejecuciones nuevas.

## Alcance

- HU4/HU6; capacidad `predictive-modeling`; CRISP-DM: despliegue/trazabilidad.
- `bundle.json` de ejecuciones nuevas incluye `code_identity` capturado en el
  momento del entrenamiento (mismo valor que `run_metadata.json`).
- `OperationalBundle.code_identity` expone el valor o `None` ("no registrado")
  para bundles anteriores; nunca se infiere desde el checkout actual.
- Si git no esta disponible se persiste `{"available": false, "reason": ...}`
  sin `commit`.

## Exclusiones e impacto

No retro-llena bundles existentes ni inventa commits. No cambia modelos,
calibradores, umbrales, contratos, protocolo, datos, resultados historicos,
holdouts ni OpenAPI. `load_operational_bundle` no valida `code_identity`.

Verificado por lectura: `contract.json`, `files` (hashes de artefactos),
`model_version`/`calibration_version`, `ensemble_identity_sha256` (usa solo
`feature_*`, `lags`, `rolling_windows`, `decision_threshold` y `files`),
`snapshot_id` (hash del dataset) y el `request_hash` de idempotencia de
`emit_snapshot` (calculado sobre slots) no dependen del resto del contenido de
`bundle.json`. Efecto lateral informativo: `input_snapshot.bundles` de lotes
nuevos almacenara `code_identity` al copiar `bundle.metadata`; no se hashea ni
aparece en la respuesta HTTP.
