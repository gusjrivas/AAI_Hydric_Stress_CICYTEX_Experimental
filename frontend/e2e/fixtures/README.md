# Fixtures de los recorridos de navegador

Respuestas JSON **grabadas de backends reales** (FastAPI, commit base `e575a30` del repositorio, sin modificar) con
`record_fixtures.py`. Las usa `scripts/ui/fixture-server.mjs`; no se editan a mano. Alcance: sólo lo que consumen
`scripts/ui/verify-journeys.mjs`; no sustituyen pruebas de backend ni evidencia científica.

| Directorio | Origen real | Contenido |
|------------|-------------|-----------|
| `cicytex/` | Backend con `results/cicytex/causal_replay` (paquete archivado), sonda `CP1_S1`, horizonte +1, emisión 2023-07-06 | catálogo, trazabilidad, sesión creada + 3 avances, plantilla de feedback |
| `pergamino-ensemble-demo/`, `melchor-romero-demo/` | Backend `producer_v2` (`scripts/run_producer_preview_backend.py`) sobre emisiones ya persistidas (lecturas ERA5-Land/NASA POWER y ESA CCI/NASA POWER) | lote de pronósticos y lecturas por (emisión, reloj): las 5 emisiones al reloj de emisión y la primera emisión avanzada hasta +4 días |
| `*/provenance__<batch_id>.json` | Mismo backend `producer_v2` (con este repositorio, rama de `add-emission-provenance-panel`) sobre una copia de las emisiones ya persistidas, `GET /api/v2/sensors/{sensor}/batches/{batch_id}/provenance` de cada una de las 5 emisiones por sitio | Procedencia de la emisión (lista blanca). Esas emisiones son anteriores al registro de `code_identity`: el commit figura `null` («no registrado»); no se inventó ningún valor |
| `lab/` | Backend plano (`uvicorn backend.app.main:app`) con 120 lecturas sintéticas | informe de calidad (plantilla), corrida de pronóstico, historial de feedback, predictor activo |

## Cómo se generaron

1. Entorno Python con las dependencias de `pyproject.toml` (`.[backend]`), en una **copia temporal** del repositorio (`src`, `backend`,
   `config`, `results/cicytex/causal_replay`) para no escribir en `data/` ni `mlruns/`.
2. Backend CICYTEX/laboratorio: `CICYTEX_REPLAY_SESSION_DB=<tmp>.sqlite python -m uvicorn backend.app.main:app --port 18010`.
3. Backend productor: `PRODUCER_DATA_DIR` (lecturas `sensor__*.parquet` y `ui_metadata/operational_v2__*.json` ya preparadas, copia temporal)
   y `PRODUCER_BUNDLE_ROOT` (sólo se exige un `ensemble_manifest.json`; la reproducción histórica no carga modelos) con
   `python scripts/run_producer_preview_backend.py` (`PRODUCER_PREVIEW_PORT=18020`).
4. `python record_fixtures.py --out frontend/e2e/fixtures --cicytex http://127.0.0.1:18010 --producer http://127.0.0.1:18020 --lab http://127.0.0.1:18010`.

## Normalización (única)

- `cicytex/session-steps.json`: `session_id` reemplazado por `recorded` (el servidor de fixtures asigna `fixture-session-N`).
- `cicytex/feedback.json`: `registered_at` fijado en `2023-07-07T00:00:00Z`; el servidor sobrescribe `estado_validacion` y `observacion` con lo enviado.
- `lab/*`: las fechas se grabaron relativas al día de la grabación; el servidor las recalcula desde las lecturas ingeridas (período, última fecha,
  objetivo = última + 3 días, `total_rows`, `out_of_range.temperature` con el rango de `src/data_quality/rules.py`). `lab/models-active.json`
  conserva las fechas grabadas. Las lecturas del laboratorio las genera la UI (semilla fija); su valor numérico no se compara.
- Las emisiones del productor conservan sus instantes persistidos (`issued_at`): son datos del almacén, no de la grabación.

## Limitaciones

- Una combinación no grabada responde 404 (`batch_not_prepared` o `detail`); el servidor lista esas rutas en `/__fixture/state`.
- Regrabar contra otra versión del backend cambia los archivos: revisar el diff antes de aceptar. Los chequeos fallan si el contrato cambia
  (por ejemplo `dataset_sha256` ausente en la trazabilidad).

## Uso local

```
cd frontend && VITE_API_BASE_URL= npm run build -- --outDir dist/e2e --emptyOutDir   # API en el mismo origen
PORT=4173 node scripts/ui/fixture-server.mjs &
BASE_URL=http://127.0.0.1:4173 OUT_DIR=ui-journeys-out node scripts/ui/verify-journeys.mjs
```

Control: `POST /__fixture/mode {"mode":"normal|disconnected|session-404"}`, `POST /__fixture/reset`, `GET /__fixture/state`.
