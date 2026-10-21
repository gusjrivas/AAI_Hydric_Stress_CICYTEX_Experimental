# Guía de arranque de la demo de defensa (CICYTEX, Pergamino, Melchor Romero, Laboratorio)

Guion breve para iniciar y recorrer los sitios usados en la defensa. Las
secciones 1 a 7 documentan el arranque con `start_defense_demo.ps1`, que
cubre Pergamino, Melchor Romero y el Laboratorio. CICYTEX y el recorrido
guiado `#demo-guiada` se describen en la sección 0.1 y no tienen un modo
propio en ese script. Complementa (no reemplaza) la documentación técnica
existente:

- `docs/design/producer-ui-local-preview-2026-09-26.md` (arranque detallado
  del backend `producer_v2` compartido por Pergamino y Melchor Romero).
- `docs/design/ensemble-real-execution-report-2026-09-26.md` /
  `docs/design/ensemble-historical-walkthrough-report-2026-09-26.md`
  (procedencia real de los artefactos de Pergamino).
- `docs/seguimiento-tareas.md`, entradas "UI de defensa Pergamino..."
  (2026-09-27), "Melchor Romero como segundo sitio..." (2026-09-28) y
  "Corrección de procedencia..." (2026-09-29).

`scripts/start_defense_demo.ps1` es un envoltorio fino sobre los scripts ya
existentes y validados (`scripts/run_producer_preview_backend.py`,
`uvicorn backend.app.main:app`, `npm run dev`); no reemplaza su validación
de artefactos ni su lógica.

## 0. Qué demuestra cada modo (y qué no)

| Modo | Qué demuestra | Qué NO permite concluir |
| --- | --- | --- |
| **CICYTEX** | Reproducción causal del paquete archivado de 21 sondas de humedad (un sitio, campaña 2023): decisión del ensamble con lo observado hasta la emisión y revelado posterior. El objetivo es un proxy: humedad futura bajo el P20 de entrenamiento. | No hay etiquetas fisiológicas independientes. La evaluación inicial (420 casos por horizonte) y el replay causal (399, 378 y 357) son análisis distintos y no se mezclan. El replay es retrospectivo y exploratorio sobre un período ya inspeccionado. No es validación multisitio, ni evidencia de ahorro de agua ni de generalización geográfica. |
| **Pergamino** | Recorrido histórico real sobre un demo-runner de ensamble (`pergamino-ensemble-demo`) con emisiones ya preparadas y persistidas, con procedencia externa (ERA5-Land/NASA POWER) explícita. | No es la campaña científica cerrada `controlled_daily_v4_external_pergamino` (ADR-0011, `FAIL` de gobernanza, GD-38/GD-40) ni la reabre; no evalúa el holdout 2024-2025; no es evidencia de superioridad de ningún modelo. |
| **Melchor Romero** | El mismo recorrido, pero completamente reproducible desde el propio repositorio (dataset real ya versionado `data/melchor_romero_2024_consolidado.parquet`), incluida la distinción real/imputado/sin-observación corregida en PR #228. | No tiene evaluación agregada retrospectiva propia (a diferencia del panel 2023 de Pergamino, que a su vez es exploratorio, no confirmatorio). No reejecuta ni reinterpreta `controlled_daily_v3`. |
| **Laboratorio de sensores** | Escenarios sintéticos controlados (ruido, anomalías, sensor de prueba) contra el pipeline operativo real (ingesta, calidad, pronóstico, feedback), identificados inequívocamente como sintéticos. | Los scores del laboratorio no son evidencia científica ni probabilidades calibradas sobre datos reales; solo ilustran el comportamiento del pipeline. |

## 0.1. CICYTEX y recorrido guiado `#demo-guiada`

Esta sección se verificó por lectura de código y de configuración. No se
ejecutó ningún stack al redactarla.

### Rutas vigentes

Las rutas son hashes sin barra: `#resumen`, `#defensa-pergamino`,
`#defensa-melchor-romero`, `#defensa-cicytex`, `#laboratorio-sensores`,
`#evidencia-resultados`, `#productor` (destino por defecto), `#prediccion`,
`#calidad`, `#linaje`, `#evidencia` y `#arquitectura`. Además existen
`#demo-guiada` (ruta propia), `#demo` (vista de Herramientas técnicas, solo
con demo acelerada configurada) y `#reproduccion-historica`. Una ruta con
barra (por ejemplo `#/defensa-pergamino`) no es reconocida y la aplicación
abre el destino por defecto, `#productor`.

### Dos formas de recorrer los sitios

| | `#demo-guiada` | Vistas detalladas (`#defensa-cicytex`, `#defensa-pergamino`, `#defensa-melchor-romero`, `#laboratorio-sensores`) |
| --- | --- | --- |
| Alcance | Cuatro pasos en orden fijo: CICYTEX, Pergamino, Melchor Romero, Laboratorio. Un caso fijo por sitio | Selección de sonda, horizonte y emisión (CICYTEX), emisiones archivadas con +1/+2/+3 (productor), escenarios del laboratorio |
| Interacción | Semáforo, "N de M modelos coinciden", botón "Avanzar un día", línea "De dónde sale" y detalle técnico plegable. Cada paso se monta y se descarta, por lo que volver a un paso lo reinicia | Reloj editable, tablas de observaciones reveladas, trazabilidad completa |
| Feedback y revisión | No incluye | Incluye (sección de feedback más abajo) |
| Laya | No aparece | Solo como ficha desactivada en `#arquitectura` |
| Endpoints nuevos | Ninguno: reutiliza los clientes existentes | - |

Casos fijos del recorrido guiado:

- CICYTEX: sonda `CP1_S1`, emisión 2023-07-06, horizonte +1. Crea una sesión
  (`POST /api/v2/cicytex/replay/sessions`), avanza con `POST .../sessions/{id}/advance`
  y consulta `GET /api/v2/cicytex/replay/provenance`.
- Pergamino: sensor `pergamino-ensemble-demo`, emisión 2023-06-13, horizonte +1.
- Melchor Romero: sensor `melchor-romero-demo`, emisión 2024-10-20, horizonte +1.
  Ambos usan `GET /api/v2/sensors/{id}/historical/{fecha}/forecasts`,
  `.../historical/{fecha}/readings` y `GET /api/v2/sensors/{id}/batches/{batch_id}/provenance`.
- Laboratorio: datos sintéticos generados en el navegador (escenario A normal y
  escenario B con temperatura imposible), rotulados "SIMULACIÓN". Usa
  `POST /sensors/{id}/readings`, `POST /forecast/{id}/run` y `GET /quality/{id}`.
  No compara modelos.

### Datos y artefactos necesarios por recorrido

| Recorrido | Backend que debe responder | Artefactos |
| --- | --- | --- |
| CICYTEX (guiado o detallado) | Backend con el router `cicytex_replay`; no requiere `PRODUCER_V2_ENABLED` | `results/cicytex/causal_replay/{summary.json,predictions.csv,observations.csv}`, versionados en el repositorio. Los joblib de `models/` no se necesitan para recorrer y están ignorados por Git |
| Pergamino | `producer_v2` habilitado (`PRODUCER_V2_ENABLED=true`, que fija `run_producer_preview_backend.py`) | Lecturas, emisión y 9 bundles externos al repositorio (sección 2) |
| Melchor Romero | `producer_v2` habilitado | Se prepara con `prepare_melchor_romero_historical_demo.py` (sección 2) |
| Laboratorio | Backend plano | Ninguno |

Consecuencias:

- `compose.cicytex.yml` (frontend `http://127.0.0.1:55180`, backend
  `http://127.0.0.1:55800`, proyecto `aai-cicytex-experiment`) copia el paquete
  causal a la imagen y sirve CICYTEX. No define `PRODUCER_V2_ENABLED` ni
  `PRODUCER_DATA_DIR`: por lectura de código, los pasos de Pergamino y Melchor
  Romero del recorrido guiado y las vistas `#defensa-pergamino` y
  `#defensa-melchor-romero` no funcionan solo con ese stack. El funcionamiento
  del paso de Laboratorio en ese stack no está verificado.
- MLflow, PostgreSQL y MinIO de `compose.cicytex.yml` (puertos 5500, 55432,
  59000 y 59001) solo se necesitan para reejecutar el experimento (ver
  `docs/research/cicytex-reproduction.md`). La interfaz solo lee el paquete archivado.
- `start_defense_demo.ps1` no menciona CICYTEX. En `-Mode all` el frontend
  recibe `VITE_API_BASE_URL` apuntando al backend del laboratorio. Como el
  cliente de CICYTEX usa esa variable, las solicitudes de CICYTEX llegan al
  backend plano, que lee `results/cicytex/causal_replay` del checkout y guarda
  sesiones en `data/cicytex_replay_sessions.sqlite3`. Que esto funcione de
  extremo a extremo con el script no está verificado.
- El `docker compose up` del stack principal no copia el paquete causal a la
  imagen del backend. Se espera 503 en `/api/v2/cicytex/replay/*` (lectura de
  código, no ejecutado).

### Feedback humano: qué registra cada circuito y qué no hace

Ninguno de los circuitos de las vistas de ensamble recalibra ni reentrena.
Tampoco existe aprendizaje continuo.

- **CICYTEX** (`POST /api/v2/cicytex/replay/sessions/{id}/feedback`): registra
  `estado_validacion` (confirmada o rechazada), una `etiqueta_corregida` 0/1
  opcional y una observación de hasta 1000 caracteres, con marcas de tiempo real
  y simulada. Solo se acepta cuando el reloj de la sesión alcanzó el objetivo
  (si no, 409). Un duplicado de sensor, emisión y horizonte devuelve 409. Se
  guarda en SQLite (`CICYTEX_REPLAY_SESSION_DB`; en `compose.cicytex.yml`, el
  volumen `cicytex-feedback`). El alcance declarado es demostración.
- **Pergamino y Melchor Romero, revisión operativa**
  (`POST /api/v2/sensors/{sensor_id}/forecasts/{forecast_id}/reviews`): registra
  confirmar o rechazar, comentario e idempotencia, solo desde la madurez del
  objetivo. No cambia los bundles. La recalibración futura sería la única que
  podría marcar la revisión como aplicada.
- **Pergamino y Melchor Romero, recorrido histórico**
  (`POST .../historical/{fecha}/forecasts/{forecast_id}/reviews`): revisión de
  prueba técnica bajo reloj simulado, en `historical_feedback/<sensor_id>.json`,
  aislada del repositorio operativo. No es una opinión real.
- **Laboratorio y circuito heredado de HU5** (`POST /feedback/{sensor_id}/{fecha}/confirm|reject`
  y `POST /recalibrate/{sensor_id}`): la recalibración manual refitea un
  predictor individual con correcciones maduras y registra el sucesor con
  linaje. No recalibra el ensamble de tres familias.
- **Recorrido guiado**: no ofrece feedback ni revisión.

### Procedencia disponible por sitio

- **CICYTEX**: el endpoint de procedencia expone SHA-256 del dataset, commit de
  ejecución, semilla, proxy, política del ensamble, corrida padre de MLflow,
  SHA-256 de las predicciones y, por horizonte, umbral, particiones y corridas
  de los componentes. El recorrido guiado muestra solo el SHA-256 del dataset y el
  commit, y declara "versión del modelo y linaje de recalibración: no disponibles".
  Si el paquete no cumple el contrato, el endpoint responde 503.
- **Pergamino y Melchor Romero**: panel "Procedencia de la emisión" con SHA-256
  del dataset, referencia del modelo, identidad del ensamble y `code_identity` por
  componente. Configuración completa, corrida de MLflow y semilla figuran "no
  disponible" porque no se persisten por emisión. Cuando `code_identity` falta se
  muestra "no registrado": solo los bundles de ejecuciones posteriores a #64 la
  registran. Si los bundles actuales de Pergamino y Melchor Romero la registran
  no está verificado.
- **Laboratorio**: sin commit ni SHA ("no disponible"); muestra la semilla
  sintética y el identificador del sensor.

### Verificación: fixtures y backend real

`scripts/ui/verify-journeys.mjs` recorre en Chrome real el build del frontend
contra `scripts/ui/fixture-server.mjs`, con respuestas grabadas de backends
reales. No prueba un backend en vivo. El script define el sitio `demo-guiada`
(chequeos G0 a G21) y exige como mínimo 104 chequeos en total según
`EXPECTED_MIN_CHECKS` (`scripts/ui/lib/results.mjs`), con 23 para `demo-guiada`.
Ese mínimo no es un resultado de ejecución. La última corrida completa
registrada antes de #69 fue de 80 PASS, 0 FAIL y 1 INFO; un total de 103 PASS más
1 INFO tras #69 es lo que se deriva de los mínimos y no se ejecutó en esta
redacción. CI ejecuta el script en el job `browser-journeys`.

### Pendientes

- Ensayo humano del recorrido guiado y de las vistas detalladas, con tiempo de
  habla real, proyector y equipo de la defensa.
- Ejecución en el equipo de defensa de `compose.cicytex.yml`, de
  `start_defense_demo.ps1` con rutas de CICYTEX y de `#demo-guiada` contra un
  backend real.
- Estado efectivo del sidecar de Laya: no verificado. Está desactivada por
  defecto y la interfaz no la invoca.
- Verificación a 390 px y revisiones POST de Pergamino y Melchor Romero en
  navegador (ver secciones 7 y 8).

## 1. Requisitos previos

- Python con las dependencias del backend instaladas:
  ```powershell
  pip install -e ".[backend]"
  ```
  accesible en `PATH` como `python`, o pasado explícitamente con
  `-PythonExe "<ruta completa>"` si no lo está (frecuente en esta máquina
  de desarrollo).
- Node.js/npm instalados; `frontend/` con dependencias instaladas de forma
  reproducible (usa el lockfile, no resuelve versiones nuevas):
  ```powershell
  cd frontend
  npm ci
  ```
- Puertos libres (por defecto 8199 backend Pergamino/Melchor Romero, 8299
  backend Laboratorio, 5199 frontend — verificar con `Get-NetTCPConnection`
  antes de arrancar, puede haber otra sesión de verificación usando otros
  puertos en la misma máquina). `start_defense_demo.ps1` ya valida rango,
  duplicados y disponibilidad de los puertos que va a usar **antes** de
  arrancar cualquier proceso (sección 6).
- Ningún artefacto se referencia por ruta personal (`C:\Users\...`,
  `D:\...`, `/home/...`) en código versionado: todas las ubicaciones se
  pasan por variable de entorno o parámetro de línea de comandos.

## 2. Preparación explícita de artefactos (por sitio)

### Melchor Romero — reproducible desde este repositorio

```powershell
python scripts/prepare_melchor_romero_historical_demo.py `
    --data-dir <directorio externo vacío, p. ej. $env:TEMP\melchor-data> `
    --bundle-root <directorio externo vacío, p. ej. $env:TEMP\melchor-bundles>
```

Ajusta y calibra las 3 familias del ensamble sobre el dataset real
versionado y prepara las 5 emisiones históricas reales
(`2024-10-20`..`2024-10-24`). No requiere ningún insumo externo al
repositorio ni credenciales.

### Pergamino — **disponible localmente y verificado (verificación del 2026-09-29, histórica); no incluido en un clon limpio**

Es importante distinguir dos cosas distintas que un lector podría
confundir: **disponibilidad local** (¿existen los artefactos, en esta
máquina, ya generados y verificables por hash?) y **distribución
reproducible** (¿puede cualquiera obtenerlos con un `git clone` de este
repositorio?). Para Pergamino, la primera es **sí** (verificado en esta
tarea, ver abajo); la segunda sigue siendo **no**, deliberadamente — los
artefactos son grandes, de procedencia externa (reanálisis ERA5-Land/NASA
POWER) y no corresponde versionarlos en git.

**Aclaración sobre un apartado previo potencialmente ambiguo**: un
inventario anterior de esta tarea mencionó `run_manifest.json` y luego, en
otra sección, "NO LOCALIZADO". Esa frase se refería exclusivamente a si
los dos CSV fuente (`pergamino_era5land_soil_hourly_2015_2025.csv`,
`pergamino_nasa_power_daily_2015_2025.csv`) aparecen en el historial de
algún commit de este repositorio (`git log --all` sobre esos nombres de
archivo) — no aparecen, por diseño, ya que son deliberadamente externos y
nunca se versionaron. **No significa que falte ningún artefacto en
disco.** Los tres conjuntos de artefactos de Pergamino (CSV fuente,
lecturas+emisión del recorrido histórico, 9 bundles del ensamble) están
presentes en esta máquina y fueron verificados por hash en esta tarea
(sección 7.1).

Artefactos localizados y verificados en esta máquina (rutas externas al
repositorio, `C:\Repo\AAI_Hydric_Stress_ensemble_demo_runtime\...` /
`C:\Repo\AAI_Hydric_Stress_external_data\...` — nunca `data/` del
repositorio):

- **CSV fuente** (`AAI_Hydric_Stress_external_data\raw\`): ambos
  verificados contra `docs/research/controlled-daily-v4-external-pergamino-manifest.yaml`.
- **Lecturas + emisión del recorrido** (`pergamino-walkthrough-2023-06-13_17\`):
  `sensor__pergamino-ensemble-demo.parquet` y
  `ui_metadata/operational_v2__pergamino-ensemble-demo.json`, verificados
  contra los hashes fijos en `scripts/prepare_defense_data.ps1`
  (`$expectedReadingSha256`/`$expectedEmissionSha256`). **Usar
  exclusivamente este directorio como `-SourceDataDir`** — nunca
  `session-2` (ver nota al final de esta sección).
- **9 bundles del ensamble** (3 familias × 3 horizontes) +
  `ensemble_manifest.json` por horizonte + `run_manifest.json`
  (`pergamino-ensemble-demo-2026-09-26T034114Z\`), verificados byte a byte
  contra los hashes que el propio `run_manifest.json` registró al
  generarlos (27/27 componentes, 0 discrepancias).

Por mandato de esta tarea, **no se reentrenó ni se regeneraron
emisiones** — se reutilizan exclusivamente los artefactos ya generados y
verificados arriba. Pasos para recorrer Pergamino:

1. Verificar los hashes de los artefactos localizados con
   `Get-FileHash -Algorithm SHA256` contra los valores de esta sección
   (y contra `scripts/prepare_defense_data.ps1` para lecturas/emisión).
2. Copiar a un directorio de demo aislado **nuevo** (nunca reusar uno
   existente) con:
   ```powershell
   ./scripts/prepare_defense_data.ps1 `
       -SourceDataDir "C:\Repo\AAI_Hydric_Stress_ensemble_demo_runtime\pergamino-walkthrough-2023-06-13_17" `
       -DemoDataDir ".demo-defense-data\<nombre-nuevo>"
   ```
   (el script rechaza destinos existentes y raíces fuera de
   `.demo-defense-data/`, y no modifica el origen).
3. Usar como `-BundleRoot` la **raíz** que contiene la carpeta
   `pergamino-ensemble-demo\` — **no** agregar `pergamino-ensemble-demo`
   al final del path:
   ```
   -BundleRoot "C:\Repo\AAI_Hydric_Stress_ensemble_demo_runtime\pergamino-ensemble-demo-2026-09-26T034114Z"
   ```
   `_horizon_dir()` en `src/predictive_modeling/ensemble_bundle.py` ya
   construye `bundle_root / sensor_id / horizon_N` internamente —
   agregar el `sensor_id` a mano en `-BundleRoot` apunta a una ruta que
   no existe y el backend no puede resolver ningún horizonte.

**Nota sobre `session-2`** (directorio preexistente, no tocado por esta
tarea, fuera de este worktree): su `operational_v2__pergamino-ensemble-demo.json`
tiene un hash distinto al de `pergamino-walkthrough-2023-06-13_17`. Se
especuló en un informe previo que esto podría deberse a una revisión
histórica (`HistoricalReviewStore`) registrada durante esa sesión — **esa
atribución no está verificada** y no debe repetirse como si lo estuviera:
`HistoricalReviewStore` escribe en `historical_feedback/<sensor_id>.json`,
un archivo separado de `ui_metadata/operational_v2__*.json`, por lo que
una revisión histórica por sí sola no explica un hash distinto en ese
JSON. La causa real de la diferencia queda sin verificar. Esto no bloquea
nada: esta guía usa exclusivamente `pergamino-walkthrough-2023-06-13_17`
(cuyos hashes sí coinciden con los fijados en el script), nunca
`session-2`, que se deja intacta sin modificar ni borrar.

### Laboratorio de sensores — sin preparación previa

No requiere ningún artefacto externo. Los escenarios se generan en vivo
desde la UI contra el pipeline real.

## 3. Arranque

```powershell
# Laboratorio (sin artefactos externos):
./scripts/start_defense_demo.ps1 -Mode sensor-lab

# Melchor Romero (tras el paso de preparación de la sección 2):
./scripts/start_defense_demo.ps1 -Mode melchor-romero `
    -DataDir <mismo --data-dir usado arriba> -BundleRoot <mismo --bundle-root usado arriba>

# Pergamino (con el PRODUCER_DATA_DIR/PRODUCER_BUNDLE_ROOT reales, sección 2):
./scripts/start_defense_demo.ps1 -Mode pergamino -DataDir <...> -BundleRoot <...>

# Los tres a la vez (Pergamino y Melchor Romero pueden compartir el mismo
# -DataDir/-BundleRoot si ambos sitios fueron preparados ahí, ya que los
# archivos se nombran por sensor_id):
./scripts/start_defense_demo.ps1 -Mode all -DataDir <...> -BundleRoot <...>
```

Cada arranque valida los artefactos requeridos (delegado a
`run_producer_preview_backend.py`, cuya salida de error hace fallar todo el
arranque) y falla con un mensaje concreto si falta algo — nunca sirve datos
sintéticos en su lugar. El feedback generado durante la demo queda aislado
de las lecturas/predicciones originales:
`historical_feedback/<sensor_id>.json` dentro del `PRODUCER_DATA_DIR` para
Pergamino/Melchor Romero, y `data/feedback__lab-*.parquet` (prefijo
exclusivo, gitignored) para el Laboratorio.

### 3.1. Dos backends, dos URLs de frontend (`-Mode all`)

`-Mode all` arranca DOS backends distintos: el "productor" (`producer_v2`,
Pergamino/Melchor Romero) en `-ProducerPort`, y el "laboratorio" (endpoints
genéricos planos) en `-LabPort`. El frontend necesita saber a cuál de los
dos mandar cada solicitud.

**Hallazgo de esta entrega**: antes de esta corrección, el frontend tenía
una sola variable (`VITE_API_BASE_URL`) para todo, así que en `-Mode all`
los cuatro clientes de `frontend/src/features/producer/*Api.ts`
(`catalogApi`, `readingsApi`, `forecastsApi`, `historicalApi`) terminaban
enviando sus solicitudes al mismo backend que el laboratorio -- en la
práctica, las lecturas del laboratorio de sensores (`lab-*`) podían
terminar escribiéndose en el `PRODUCER_DATA_DIR` compartido con Pergamino/
Melchor Romero en vez de en `data/` del repositorio.

Corrección: `frontend/src/api/baseUrl.ts` ahora expone dos constantes:

- `API_BASE_URL` (`VITE_API_BASE_URL`): laboratorio, forecast operativo,
  calidad y linaje -- todos los clientes que NO son de `producer/`.
- `PRODUCER_API_BASE_URL` (`VITE_PRODUCER_API_BASE_URL`): exclusivamente
  los cuatro clientes de `producer/` listados arriba. Si no está definida,
  cae en `API_BASE_URL` (mismo comportamiento que antes de que existiera
  esta variable, para no romper el uso con un solo backend).

`start_defense_demo.ps1` asigna ambas automáticamente (`Resolve-FrontendBaseUrls`, ver también las pruebas de Pester):

| `-Mode` | `VITE_API_BASE_URL` (laboratorio, etc.) | `VITE_PRODUCER_API_BASE_URL` (Pergamino/Melchor Romero) |
| --- | --- | --- |
| `all` | `http://127.0.0.1:<LabPort>` | `http://127.0.0.1:<ProducerPort>` |
| `sensor-lab` | `http://127.0.0.1:<LabPort>` | `http://127.0.0.1:<LabPort>` (mismo backend) |
| `pergamino` / `melchor-romero` | `http://127.0.0.1:<ProducerPort>` | `http://127.0.0.1:<ProducerPort>` (mismo backend) |

## 4. URLs y recorrido sugerido

- Frontend: `http://127.0.0.1:5199` (o el puerto elegido con `-FrontendPort`).
- CICYTEX: ruta `#defensa-cicytex`. Requiere un backend que sirva
  `results/cicytex/causal_replay` (sección 0.1). Seleccionar sonda, horizonte y
  emisión, abrir la emisión congelada, avanzar el reloj y, con la realidad
  revelada, registrar feedback de demostración.
- Recorrido guiado: ruta `#demo-guiada`, con sus cuatro pasos y los requisitos
  de la sección 0.1. Es una alternativa simplificada, no reemplaza las vistas detalladas.
- Pergamino: ruta `#defensa-pergamino` — seleccionar una emisión archivada,
  revisar +1/+2/+3 y las explicaciones de indisponibilidad, avanzar el
  reloj, registrar feedback.
- Melchor Romero: ruta `#defensa-melchor-romero` — mismo recorrido;
  verificar puntualmente que la emisión del 23/10 +3 y la del 24/10 +2
  muestren el 26/10 como imputado (no como observación real) y que el 27/10
  conserve su observación original; confirmar que las observaciones
  posteriores a la fecha del reloj no aparecen hasta avanzarlo.
- Laboratorio: ruta `#laboratorio-sensores` — recorrer escenarios de ruido,
  anomalías y sensor de prueba, confirmando el rótulo de datos sintéticos y
  que los scores no se presentan como probabilidades calibradas.

## 5. Disponibilidad real, arranque transaccional y parada segura

**Disponibilidad real, no solo "el proceso existe"**: después de arrancar
cada servicio, el script espera (máximo `-ReadyTimeoutSeconds`, default 60,
con un timeout corto de 3 s por solicitud) hasta confirmar una respuesta
válida real:

- Backend productor: `GET /api/v2/sensors` responde 200.
- Backend del laboratorio: `GET /openapi.json` responde 200 **y** publica
  una ruta de ingesta de lecturas (`.../readings`) -- no solo que el
  servidor HTTP conteste algo.
- Frontend: respuesta HTTP en el puerto exacto pedido (arrancado con
  `--strictPort`, así que nunca "resuelve" un puerto ocupado usando otro
  distinto en silencio).

Si el proceso termina durante la espera (por ejemplo, el lanzador Python
falló su propia validación de artefactos), se detecta y se informa el
servicio, el error, y la ubicación del log -- nunca se anuncia "Listo"
hasta que TODOS los servicios pedidos responden correctamente.

**Arranque transaccional**: cada invocación tiene un identificador propio
y registra en `.defense-demo-run/registry.json` (gitignored) qué procesos
creó ella misma -- servicio, PID, instante de creación del proceso (no
solo el PID, que Windows recicla), ejecutable, identificador de la
ejecución. Si algo falla en cualquier paso, se revierte: se detienen
**únicamente** los procesos que esa invocación creó (nunca los de otra
ejecución concurrente), verificando su identidad antes de matarlos, y
preservando los logs para diagnóstico.

Si ya hay una ejecución propia todavía activa (verificada por identidad de
proceso, no solo por la existencia de un PID), una invocación nueva se
niega a arrancar sin sobrescribir ese registro ni detenerla
automáticamente -- corré `-Stop` primero.

**Parada segura**:

```powershell
./scripts/start_defense_demo.ps1 -Stop
```

- Detiene únicamente procesos cuya identidad (PID + instante de creación +
  ejecutable) coincide con lo registrado. Un PID que Windows recicló para
  otro proceso distinto **nunca se detiene** -- se informa un diagnóstico
  en vez de arriesgarse a matar algo ajeno.
- No hay terminación global por nombre de proceso ni por puerto.
- Se detiene el árbol completo de cada servicio (por ejemplo, `cmd.exe` →
  `npm` → `node`/Vite), verificando en cada nivel que el proceso hijo
  realmente desciende del ya validado.
- Es idempotente: correrlo una segunda vez (o sin nada que detener) no
  produce errores ni toca procesos ajenos.
- Archivos `.pid` sueltos de una versión anterior de este script (sin
  identidad grabada) nunca se usan para matar nada -- se informa que no se
  puede verificar su propietario.
- Restaura, en un bloque `finally` (tanto ante éxito como ante error), las
  variables de entorno que el script haya modificado en la sesión de
  PowerShell (`CORS_EXTRA_ORIGINS`, `PRODUCER_DATA_DIR`,
  `PRODUCER_BUNDLE_ROOT`, `PRODUCER_PREVIEW_PORT`, `VITE_API_BASE_URL`,
  `VITE_PRODUCER_API_BASE_URL`). Los procesos ya arrancados conservan el
  entorno que recibieron al momento de arrancar -- restaurarlas después no
  los afecta.

## 6. Problemas comunes

- **Puerto ocupado**: el script falla explícitamente antes de arrancar nada;
  usar `-ProducerPort`/`-LabPort`/`-FrontendPort` para elegir otros puertos.
  Puede haber otra sesión de verificación corriendo en la misma máquina.
  (El chequeo solo cuenta como "ocupado" un socket en estado `Listen`: un
  `TIME_WAIT` de una conexión ya cerrada no bloquea el reinicio.)
- **`'python' no se reconoce...` / Start-Process falla al arrancar el
  backend**: `python` no está en `PATH` en esta sesión de PowerShell. Pasar
  `-PythonExe "<ruta completa a tu intérprete>"`.
- **`falta la variable de entorno PRODUCER_DATA_DIR`/`PRODUCER_BUNDLE_ROOT`**:
  faltan `-DataDir`/`-BundleRoot` en modos `pergamino`/`melchor-romero`/`all`.
- **`batch_not_prepared` al pedir una fecha**: esa fecha no fue preparada en
  el `PRODUCER_DATA_DIR` usado; no es un error del arranque.
- **Frontend: "no se reconoce como un comando" / falla `npm`**: falta
  `frontend/node_modules` (correr `npm ci` en `frontend/` una vez, en
  cualquier checkout nuevo) o falta `npm` en `PATH`. El script valida esto
  antes de arrancar nada, con un mensaje concreto.
- **"Ya hay una ejecución propia de este script activa"**: hay entradas en
  `.defense-demo-run/registry.json` cuya identidad (PID + instante de
  creación + ejecutable) sigue coincidiendo con procesos reales. Corré
  `-Stop` primero. El script nunca sobrescribe ese registro ni detiene esa
  ejecución automáticamente.
- **"...ya no está corriendo, o el PID fue reciclado..." al correr `-Stop`
  pero el servicio sigue respondiendo**: significa que la identidad
  grabada (instante de creación + ejecutable) ya no coincide con ese PID
  -- por diseño, no se detiene un proceso cuya identidad no se puede
  confirmar. Verificar manualmente con `Get-CimInstance Win32_Process
  -Filter "ProcessId=<pid>"` y detener a mano si corresponde.
- **Frontend inalcanzable en `http://127.0.0.1:<puerto>/` pero sí en
  `http://localhost:<puerto>/`**: en algunas máquinas Vite se bindea por
  defecto solo a IPv6 (`[::1]`). El script ya fuerza `--host 127.0.0.1`; si
  se arranca `npm run dev` manualmente, agregar ese flag.
- **`Failed to fetch` en el navegador con el backend corriendo**: casi
  siempre CORS. El script setea `CORS_EXTRA_ORIGINS` **antes** de arrancar
  cualquier backend (incluido el del Laboratorio, que no pasaba por ese
  origen en una versión anterior de este script) a partir de
  `-FrontendPort`; si se arrancan procesos por separado, setearlo a mano
  antes de levantar el backend. Si el navegador venía de una pestaña
  abierta contra un backend anterior en el mismo puerto de frontend, el
  módulo JS con la URL base puede quedar cacheado: cerrar la pestaña y
  abrir una nueva (no solo recargar) resuelve esto.
- **CORS**: si el frontend corre en un puerto distinto al configurado, el
  backend producer_v2 lo agrega automáticamente vía `CORS_EXTRA_ORIGINS`
  (seteado por el script a partir de `-FrontendPort`); si se arrancan por
  separado, setearlo manualmente (ver
  `docs/design/producer-ui-local-preview-2026-09-26.md`, sección 3).

## 7. Resultado del ensayo end-to-end (2026-09-29)

Ensayado en este worktree (no un checkout separado — ver limitación abajo),
con `frontend/node_modules` instalado ad hoc (no estaba presente) y
`python`/`npm` pasados por ruta completa (no estaban en `PATH` de la sesión
de arranque). Hallazgos y correcciones aplicadas al propio script durante
el ensayo (quedaron en el código, no son pendientes):

- El chequeo de puerto libre contaba `TIME_WAIT` como "ocupado" — corregido
  para exigir solo `Listen`.
- `Start-Process -FilePath npm` falla en Windows (`npm` es `.cmd`) —
  corregido invocando vía `cmd.exe /c`.
- `-Stop` solo mataba el PID rastreado (`cmd.exe`), dejando el proceso
  `node` de Vite huérfano — corregido con `Stop-ProcessTree` (recursivo).
- `CORS_EXTRA_ORIGINS` solo se seteaba en la rama del backend producer_v2:
  el modo `sensor-lab` con un `-FrontendPort` distinto de 5173 fallaba con
  `Failed to fetch` — corregido seteándola antes de arrancar cualquier
  backend.
- Se agregó `-PythonExe` (no existía) porque `python` no resuelve por
  `PATH` en esta máquina.
- Vite se bindeaba solo a IPv6 (`[::1]`) — se agregó `--host 127.0.0.1`.

Verificado real (backend real, sin mocks, sin datos fabricados):

- **Melchor Romero**: datos preparados desde cero en un directorio temporal
  con `prepare_melchor_romero_historical_demo.py` (dataset versionado,
  ningún insumo externo). `start_defense_demo.ps1 -Mode melchor-romero`
  arrancó backend+frontend reales; verificado por API y por navegador
  (`claude-in-chrome`, clicks reales, no solo JS): emisión 23/10, +3 →
  objetivo 26/10 muestra "Observación posterior: 36.3 % · Valor imputado
  (...). No es una observación independiente para contrastar con el
  pronóstico."; la tabla "Observaciones reveladas" confirma 25/10 = 36.3 %
  (Fuente real), 26/10 = 36.3 % (Fuente real · Imputado, sin dato propio
  este día), 27/10 = 33.0 % (Fuente real, valor propio, no sobrescrito por
  el forward-fill del 26/10) — coincide exactamente con los valores del
  mandato. Retrocediendo el reloj a 24/10 se confirmó que la tabla no
  revela 25/10, 26/10 ni 27/10 (sin fuga de observaciones futuras).
- **Laboratorio de sensores**: `start_defense_demo.ps1 -Mode sensor-lab`
  arrancado real; recorridos por click los cuatro escenarios en la UI real
  (no solo `curl`): A (120 lecturas sintéticas cargadas, confirmado por
  `GET /quality`), B (lectura de 85.0 °C marcada `out_of_range.temperature`
  por el backend real), C (4 días sin lecturas nuevas: no se re-pide
  pronóstico), D (recuperación a 125 filas, pronóstico real re-emitido). El
  rótulo "Datos sintéticos / sensor de prueba" es permanente en la pantalla
  y el texto de score confirma "Señal de 0 a 1; no es un porcentaje de
  certeza." (nunca presentado como probabilidad calibrada).
- **Aislamiento cruzado**: cada modo usó su propio `sensor_id`
  (`melchor-romero-demo` vs. `lab-<hex>`) y su propio backend/puerto en
  este ensayo; no se observó mezcla de datos entre sensores.
- **Pergamino**: ensayado real en la ronda siguiente (2026-09-29, segunda
  sesión) — ver sección 7.1.

Limitaciones del ensayo:

- Se hizo en este mismo worktree de desarrollo, no en un checkout
  completamente separado ("entorno limpio" en sentido estricto sigue
  pendiente); sí se partió de un estado sin `node_modules` y sin
  `.defense-demo-run/` previo, y `python`/`npm` se pasaron explícitamente
  por ruta para no depender de configuración de `PATH` de esta máquina.
- Verificación a 390 px de ancho: no realizada. La herramienta de
  redimensionar ventana (`resize_window`) del entorno de automatización de
  navegador rechazó los tamaños pedidos ("Bounds must be at least 50%
  within visible screen space") incluso en una pestaña nueva — limitación
  de la herramienta en este entorno, no un defecto de la aplicación; queda
  pendiente con un navegador redimensionado manualmente o DevTools.
- No se probaron los flujos de feedback/revisión (confirmar/rechazar
  resultado) ni la ingesta de observaciones tardías durante este ensayo
  puntual; quedan como pendiente de una pasada adicional.

## 7.1. Pergamino desbloqueado y ensayado (2026-09-29, segunda sesión)

Autorizado explícitamente a reutilizar exclusivamente artefactos ya
localizados en esta máquina (sin entrenar ni regenerar nada). Verificación
y ensayo realizados en esta sesión:

**Verificación de hashes — completa, no muestreo** (script ad hoc, no
versionado, ejecutado en esta tarea): los 27/27 archivos de componente
(`model.joblib`/`calibrator.joblib`/`contract.json` × 3 familias × 3
horizontes) verificados byte a byte contra los hashes que
`run_manifest.json` registró al generarlos — **0 discrepancias**. Los 3
`ensemble_manifest.json` (uno por horizonte) verificados: `policy_version`,
`families` (las 3 esperadas), `weights` (suman 1.0), `sensor_id` y
`horizon_days` coherentes con `run_manifest.json` — **0 discrepancias**.
Lecturas+emisión (`pergamino-walkthrough-2023-06-13_17`) y ambos CSV
fuente también verificados contra sus hashes fijos — **0 discrepancias**.
Total: 34/34 archivos verificados, 0 discrepancias.

**Corrección de `-BundleRoot`**: un inventario previo de esta tarea había
indicado agregar `\pergamino-ensemble-demo` al final del `-BundleRoot` —
incorrecto. Verificado leyendo `_horizon_dir()` en
`src/predictive_modeling/ensemble_bundle.py:79-80`
(`Path(bundle_root) / sensor_id / f"horizon_{horizon}"`): el backend ya
agrega el `sensor_id`. El valor correcto es la raíz sin ese sufijo (ver
sección 2). Con el valor corregido, los tres horizontes resolvieron
correctamente (confirmado por API, ver abajo).

**Copia aislada nueva**: `./scripts/prepare_defense_data.ps1
-SourceDataDir "...\pergamino-walkthrough-2023-06-13_17" -DemoDataDir
".demo-defense-data\pr229-rehearsal"` — destino nuevo (no existía),
`session-1`/`session-2` no tocados. Hashes del origen verificados
idénticos antes y después de la copia.

**Arranque real**: `start_defense_demo.ps1 -Mode pergamino -DataDir
.demo-defense-data\pr229-rehearsal -BundleRoot
"...\pergamino-ensemble-demo-2026-09-26T034114Z" -PythonExe
"<ruta completa>" -ProducerPort 8199 -FrontendPort 5273` — backend+frontend
reales arrancados sin bugs nuevos específicos de este modo (los 5 bugs de
la sección 7 ya cubrían el camino producer_v2 compartido).

**Verificado real** (API + navegador, `claude-in-chrome`, clicks reales):

- Las **5 emisiones archivadas** (13 al 17 de junio de 2023) resuelven,
  cada una con sus **3 horizontes** (+1/+2/+3), sin ninguna alerta
  positiva en ninguna combinación — resultado real, no forzado.
- **Avance del reloj**: seleccionada la emisión del 13/06, "Recorrido
  hasta" llevado a 16/06 → la tabla "Observaciones reveladas" muestra
  exactamente hasta el 16/06 (10 filas, 7 al 16 de junio).
- **Retroceso del reloj**: mismo recorrido llevado de vuelta a 14/06 → la
  tabla se contrae a 11 filas, última fila 14/06 — sin fuga de fechas
  posteriores.
- **Feedback histórico en la copia aislada**: confirmado el resultado del
  slot +1 (13/06 → objetivo 14/06) vía la UI real (checkbox + "Guardar
  opinión") → `POST .../reviews` real, `201`. Verificado por
  `GET .../historical/2023-06-13/forecasts?revealed_through=2023-06-14`:
  `review.status="confirmed"`, `revision=1`. El archivo
  `historical_feedback/pergamino-ensemble-demo.json` se creó en la copia
  aislada, **separado** de `ui_metadata/operational_v2__pergamino-ensemble-demo.json`.
- **Hashes antes/después**: los 34 archivos (27 de bundle + 3 manifiestos
  de ensamble + lecturas/emisión + 2 CSV fuente) se re-verificaron
  **después** de arrancar el backend, recorrer las 5 emisiones, avanzar y
  retroceder el reloj, y registrar una revisión — **0 discrepancias**,
  igual que antes de empezar. Los originales
  (`pergamino-walkthrough-2023-06-13_17`) también se re-verificaron
  intactos.
- **Sin alertas forzadas**: las 15 combinaciones emisión×horizonte
  (5 emisiones × 3 horizontes) devolvieron `alert=false`; se registran tal
  cual, sin modificar umbral, modelo ni pronóstico para producir una
  alerta positiva.

**Ensayo combinado (Pergamino + Melchor Romero, un solo backend
compartido)**: se copiaron los árboles ya preparados de ambos sitios (la
copia aislada de Pergamino de este ensayo + el directorio de Melchor
Romero preparado en la sesión anterior, **sin volver a entrenar sus
modelos**) a un `-DataDir`/`-BundleRoot` nuevos y compartidos, organizados
por `sensor_id` como ya lo hace la fachada `producer_v2`. Hashes
verificados antes y después de la copia (4 archivos de lecturas/emisión,
0 discrepancias; originales de ambos sitios re-verificados intactos).
`start_defense_demo.ps1 -Mode all` arrancó un único backend `producer_v2`
sirviendo ambos `sensor_id` simultáneamente: `GET /api/v2/sensors` listó
`pergamino-ensemble-demo` y `melchor-romero-demo`; cada uno resolvió sus
propias emisiones históricas reales por API y por navegador
(`#defensa-pergamino` y `#defensa-melchor-romero` en la misma sesión de
frontend); pedir Pergamino en una fecha exclusiva de Melchor Romero
devolvió `404 batch_not_prepared` (aislamiento estructural por
`sensor_id`, no por coincidencia) — sin mezcla de datos entre sensores.

**No verificado en esta ronda** (pendiente):

- 390 px de ancho: sigue bloqueado por la misma limitación de la
  herramienta `resize_window` en este entorno (sección 7).
- Checkout genuinamente separado (sigue ensayado en este worktree) —
  **resuelto en la ronda siguiente, sección 7.2**.
- Ingesta de observaciones tardías (llegada fuera de orden) en Pergamino
  específicamente — se verificó el mecanismo de reloj/revelado, pero no
  un caso de respuesta de feedback deliberadamente demorada.

## 7.2. Corrección del arranque combinado y ensayo en clon separado (2026-09-29, tercera sesión)

**Corrección de una afirmación imprecisa de esta misma sección** (señalada
en una ronda posterior, ver sección 7.3): el ensayo de más abajo usó un
**checkout de git genuinamente separado**, pero **reutilizó el intérprete
Python de un venv preexistente en esta máquina** (`C:\tcnenv`, ya
compartido por otras sesiones de verificación de este mismo Trabajo
Final) — nunca se creó un venv nuevo. Describir ese ensayo como "entorno
limpio" sin esa aclaración habría sido impreciso: lo que se verificó ahí
es la independencia del *código* (checkout aparte, sin `node_modules` ni
datos de sesión reusados) y la separación de URLs del frontend, no la
independencia del *entorno Python*. La sección 7.3 documenta el intento
real de usar un venv nuevo y su resultado.

Corrigió un defecto real de `-Mode all` (las dos URLs de frontend
compartían un solo backend por error, sección 3.1) y reescribió
`start_defense_demo.ps1` con validación previa completa, espera de
disponibilidad real, registro estructurado de procesos y parada verificada
(sección 5). Ensayado con `Invoke-Pester` (18/18, Pester 3.4.0) y, esta
vez sí, en un **clon git genuinamente separado**, en otro directorio
(`C:\pr229clone`, fuera de este worktree), fijado al commit candidato
`669a7e5` (`git clone` + `git checkout 669a7e5`), sin reusar el entorno
virtual, `node_modules`, datos de sesión ni configuración local del
worktree de desarrollo:

- **Dependencias instaladas siguiendo únicamente esta guía**:
  `pip install -e ".[backend]"` (usando el intérprete de un venv
  preexistente en esta máquina, apuntado explícitamente por ruta -- el
  propio `pip install -e` reapunta ese venv compartido al nuevo clon, algo
  a tener en cuenta si se corre en la misma máquina que otro checkout
  activo del mismo venv) y `npm ci` dentro de `frontend/` (instaló 117
  paquetes desde cero, sin `node_modules` previo).
- **Datos**: se copiaron los artefactos canónicos ya verificados (no se
  regeneró ni reentrenó nada) a un destino nuevo compartido por
  `sensor_id` fuera del clon (`C:\pr229clone-rundata\`): Pergamino desde
  el original `pergamino-walkthrough-2023-06-13_17` (nunca `session-2`),
  Melchor Romero desde el directorio ya preparado en la sesión anterior de
  esta misma tarea. Hashes verificados antes y después de la copia
  (idénticos); los originales también se re-verificaron intactos
  después de todo el ensayo.
- **`./scripts/start_defense_demo.ps1 -Mode all -DataDir C:\pr229clone-rundata\combined-data -BundleRoot C:\pr229clone-rundata\combined-bundles -PythonExe <ruta> -ProducerPort 8199 -LabPort 8299 -FrontendPort 5273`**:
  arrancó los tres servicios reales, cada uno verificado disponible antes
  de anunciar "Listo".
- **Verificado real en navegador** (`claude-in-chrome`, con un espía de
  `window.fetch` para capturar la URL exacta de cada solicitud, más
  confiable en este entorno que la herramienta de red del navegador):
  - Pergamino y Melchor Romero resolvieron sus recorridos históricos
    reales -- **todas** sus solicitudes (`.../historical/.../forecasts`,
    `.../historical/.../readings`) fueron a `http://127.0.0.1:8199`
    (`ProducerPort`).
  - Laboratorio, Escenario A ejecutado por click real en la UI --
    **todas** sus solicitudes (`/sensors/lab-*/readings`,
    `/quality/lab-*`, `/forecast/lab-*`) fueron a
    `http://127.0.0.1:8299` (`LabPort`), nunca al backend productor.
  - `C:\pr229clone-rundata\combined-data\` (el `PRODUCER_DATA_DIR`
    compartido de Pergamino/Melchor Romero) se inspeccionó después de
    correr el Laboratorio: **cero archivos `lab-*`** -- confirma que la
    separación de URLs realmente evita la contaminación cruzada que
    motivó esta corrección.
  - Hashes de los artefactos (lecturas/emisión de Pergamino, en el
    original y en la copia) re-verificados idénticos después de todo el
    ensayo.
  - `-Stop` detuvo los tres servicios reales (verificado con
    `Get-NetTCPConnection`: cero listeners en los tres puertos después);
    una segunda invocación de `-Stop` no lanzó error ni tocó nada.
- **No verificado en esta ronda**: 390 px de ancho (misma limitación de
  herramienta ya declarada); observaciones tardías fuera de orden en
  Pergamino; los flujos de feedback/revisión no se repitieron en el clon
  (ya se habían verificado reales en la sesión anterior, sección 7.1, y
  esta ronda se enfocó en la corrección de arranque/enrutamiento, dentro
  del alcance acordado).

## 7.3. Parada verificable, prueba de rollback efectivo, e intento de venv nuevo (2026-09-29, cuarta sesión)

Tres correcciones puntuales sobre el arranque combinado (commit
`18300e1` en adelante):

**1. Parada verificable**: `Stop-TrackedProcesses` ahora confirma
activamente, después de intentar detener cada proceso propio (hasta 5 s,
sondeando cada 200 ms), que su identidad ya no coincide con ningún
proceso vivo -- `Stop-Process` devolver el control no garantiza por sí
solo que el proceso ya terminó. Si sigue vivo, su entrada se **conserva**
en `registry.json` (nunca se limpia como si se hubiera detenido), se
registra un diagnóstico, y la función lanza una excepción **en vez de**
anunciar "Servicios detenidos". Se aplica igual a `-Stop` directo y al
rollback transaccional (ambos llaman a la misma función); el sitio de
llamada del rollback ahora atrapa por separado una falla de verificación
para registrarla fuerte ("Rollback incompleto: ...") sin tapar el error
original que causó el rollback, que sigue siendo el que se relanza.
Verificado manualmente: un ciclo normal de `-Mode sensor-lab` arranque/
parada sigue anunciando "Servicios detenidos" solo después de confirmar
que ambos procesos ya no existen.

**2. Prueba de rollback efectivo (Pester)**: nuevo caso que arranca un
proceso propio real y lo registra exactamente como lo haría
`Add-TrackedProcess` para un servicio ya arrancado con éxito, arranca
además un proceso **ajeno** real (nunca registrado), simula el fallo de
un servicio posterior con el mismo patrón try/throw/catch del flujo real,
invoca el rollback real (`Stop-TrackedProcesses -OnlyThisRun`), y
confirma que el proceso propio fue detenido mientras el proceso ajeno
permanece intacto. **19/19 pruebas de Pester pasan** (antes 18/18).

**3. Entorno Python genuinamente limpio -- intentado, bloqueado por una
política de esta máquina**: se creó un venv **nuevo** (`python -m venv`,
nunca el `C:\tcnenv` compartido) en dos ubicaciones distintas (raíz de
`C:\` y una carpeta bajo el perfil de usuario, para descartar que fuera
un problema de ruta), y se instaló con exactamente el comando pedido:

```powershell
python -m pip install -e ".[backend]"
```

La instalación se completó con éxito en ambos casos (todas las
dependencias, incluido `scikit-learn`, se descargaron e instalaron sin
error). Pero al intentar importar el backend (`producer_backend`, que
importa `scikit-learn` transitivamente vía
`architecture_integration.pipeline`), **ambos** venv nuevos fallaron con
el mismo error, reproducible y no específico de la ruta:

```
ImportError: DLL load failed while importing _cyutility: Una directiva
de Control de aplicaciones bloqueó este archivo.
```

Es una política de control de aplicaciones de Windows (tipo WDAC/
AppLocker) de esta máquina específica, que bloquea la ejecución de DLLs
recién instaladas (el módulo Cython compilado de `scikit-learn`) fuera de
ubicaciones ya confiadas -- el venv compartido preexistente (`tcnenv`)
funciona porque ya estaba instalado/confiado antes de esta política, o
porque fue aprobado en algún momento anterior; un venv genuinamente nuevo
no lo está. No es un defecto del código de este PR ni de
`start_defense_demo.ps1`: el propio script se comportó exactamente como
debía -- detectó el fallo real del lanzador Python durante la espera de
disponibilidad, informó el servicio, el error y la ubicación del log, y
revirtió sin dejar nada corriendo (confirmado).

**No se pudo completar** la repetición funcional del arranque combinado,
la disponibilidad y la parada usando un venv genuinamente nuevo en esta
máquina, por esta política externa al código del PR. Se deja registrado
como impedimento real, no como resultado inventado. La sección 7.2 queda
corregida (nota al inicio) para no describir ese ensayo anterior como de
"entorno Python limpio".

## 8. Limitaciones conocidas de esta entrega

- Pergamino no puede recorrerse de punta a punta desde un **clon git
  limpio** sin acceso a los artefactos externos descritos en la sección 2
  — deliberado, por procedencia y tamaño de los datos, no un defecto del
  mecanismo de arranque. Distinto de "disponibilidad local": en esta
  máquina esos artefactos SÍ están presentes y fueron verificados por
  hash de punta a punta (sección 7.1); quien tenga acceso a ellos por el
  canal ya autorizado puede recorrer Pergamino igual que Melchor Romero y
  el Laboratorio.
- CICYTEX y `#demo-guiada` no tienen modo propio en `start_defense_demo.ps1`.
  Su arranque de extremo a extremo con ese script o con `compose.cicytex.yml`
  no está verificado, y las secciones 7 a 7.3 (ensayos de 2026-09-29) no los
  incluyen. Esos ensayos son verificaciones históricas parciales de Pergamino,
  Melchor Romero y Laboratorio en un equipo y un momento concretos, y no
  garantizan el estado actual del repositorio.
- Esta guía no reemplaza `docs/research/protocolo-experimental-v3.md` (v3,
  congelado) ni el protocolo `controlled_daily_v4_external_pergamino`
  (ADR-0011); tampoco reinterpreta la retrospectiva exploratoria 2023
  (`docs/research/ensemble-retrospective-evaluation-protocol.md`), que
  permanece una evaluación exploratoria, no confirmatoria, sin resultado de
  superioridad atribuido.
- **No verificado con un venv Python genuinamente nuevo**: en esta
  máquina, un venv recién creado (nunca usado antes) no puede importar
  `scikit-learn` por una política de control de aplicaciones de Windows
  que bloquea DLLs recién instaladas fuera de ubicaciones ya confiadas
  (sección 7.3) — bloqueo real del entorno, no del código de este PR. El
  arranque combinado, la espera de disponibilidad y la parada solo están
  verificados de punta a punta con el venv compartido preexistente de
  esta máquina.
- Explícitamente fuera de alcance de este arranque combinado (quedan para
  un trabajo posterior, no resueltos acá): defectos internos del
  laboratorio de sensores relativos a navegación, reintento del Escenario
  A o recuperación; condiciones de carrera de respuestas en la demo
  acelerada; textos de entrenamiento y disponibilidad temporal del
  feedback; verificación a 390 px; ingesta de observaciones fuera de orden
  específicamente para Pergamino.

## Reinicio de la demo de cero (Docker aislado)

`scripts/demo_reset.ps1` deja la demo lista y la restablece cuantas veces haga falta, para repetir pruebas sin arrastrar
estado. Opera solo sobre el proyecto Compose aislado `aai-defense-rehearsal` (`docker/defense-rehearsal/compose.yml`):
`lab-backend` (`:18299`), `producer-backend` (`:18199`) y, con `-StartFrontend`, el frontend de Vite (`:15199`). No toca
MLflow, MinIO, Postgres, `./data` del repositorio ni los demás contenedores.

**Qué restablece**

- **Productor (Pergamino, Melchor Romero y Mi cultivo):** la copia de trabajo de los datos vuelve a la línea base, verificada por
  SHA-256 (una emisión en vivo, por ejemplo, modifica `ui_metadata/` y se revierte).
- **Laboratorio:** el volumen `aai-defense-rehearsal_lab_data` se recrea con **solo los datos versionados** del repositorio.
  La imagen del backend trae horneadas sesiones viejas (`lab-*`, `demo-*`, `feedback__*`, `mlruns`): se podan, de modo que el
  laboratorio arranca sin sesiones ni feedback.

**Uso**

```powershell
# 1) Una sola vez: línea base con los artefactos ya verificados de la demo (copias, nunca los originales)
./scripts/demo_reset.ps1 -Action Init -ProducerDataSource <copia de producer-data> -ProducerBundlesSource <copia de producer-bundles>

# 2) Cada vez que se quiera partir de cero (detiene, restaura, recrea el volumen, levanta y verifica)
./scripts/demo_reset.ps1 -Action Reset -StartFrontend

# Ver si el estado actual coincide con la línea base (no modifica nada)
./scripts/demo_reset.ps1 -Action Status
```

Las copias estables viven fuera del repositorio, en `..\AAI_Hydric_Stress_demo_runtime\` (parámetro `-RuntimeDir`):
`producer-data-baseline` (línea base), `producer-data` (copia de trabajo montada en el contenedor), `producer-bundles`,
`producer-data-baseline.sha256` y, de `Init`, un respaldo comprimido del volumen del laboratorio anterior
(`lab-volume-backup-<fecha>.tgz`). Un reinicio **borra** lo que se haya hecho en el laboratorio y en el productor desde el
anterior: es el propósito, pero conviene saberlo antes de ejecutarlo.

**Verificación al reiniciar:** el productor queda idéntico a la línea base; el volumen del laboratorio sin archivos de
sesión, feedback ni `mlruns`; el laboratorio responde `openapi.json`; el productor lista sus sensores y sirve los históricos
de Pergamino (`2023-06-13`) y Melchor Romero (`2024-10-20`). Probado con un ciclo real: se emitió un pronóstico en el productor y
se cargó una lectura en el laboratorio, `Status` detectó ambas diferencias y `Reset` las revirtió (comprobado por huellas y
porque la lectura dejó de existir).

**Requisitos y límites:** Docker Desktop en ejecución, la imagen `aai-defense-rehearsal-backend:local` ya construida (el
script no reconstruye), y `npm ci` hecho en `frontend/` para `-StartFrontend`. El puerto del frontend (`15199`) es el que
permite el CORS de los backends del ensayo. No incluye el controlador de la demo acelerada (perfil `demo`).
