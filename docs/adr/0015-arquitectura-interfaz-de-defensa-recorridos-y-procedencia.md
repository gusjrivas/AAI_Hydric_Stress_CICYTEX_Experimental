# ADR-0015: Arquitectura de la interfaz de defensa: recorridos por sitio, procedencia de solo lectura y verificación sin dependencias nuevas

Estado: **Propuesto el 2026-10-18** (pasa a Aceptado cuando el dueño del proyecto lo confirme).

Trazabilidad: HU6 (`architecture-integration`) y UI (`alerting-ui`); HU5
(`human-feedback`) sólo por el borrador de revisión del recorrido CICYTEX. Fase
CRISP-DM: despliegue e integración experimental. Cambios entregados en los PR #45 a
#67. No cambia modelos, umbrales, protocolos, hipótesis ni HU7/HU8. Laya sigue
desactivada (ADR-0014).

## Contexto

La interfaz de defensa debe mostrar cuatro contextos que el ADR-0014 declara no
intercambiables (Pergamino, Melchor Romero, CICYTEX y laboratorio sintético) sin
presentar datos simulados como evidencia ni inventar metadatos que el backend no
expone. Los PR #45 a #67 rediseñaron la navegación, los recorridos y la verificación.
Este ADR registra las decisiones efectivamente presentes en `main`.

## Decisión

### 1. Modos de lectura y navegación por hash

- `modeForView` (`frontend/src/features/navigation/viewMode.ts`) deriva el modo sólo de
  la ruta. `ViewMode` define cuatro modos, todos con texto propio en `ModeBadge`:
  `operacion` («Operación»), `replay` («Replay histórico»), `laboratorio`
  («Laboratorio sintético») y `diseno` («Documentación de diseño», para evidencia y
  arquitectura). `modeForView` asigna un modo a cada vista (`MODE_BY_VIEW`); un sensor
  simulado activo (`simulatedSensor`) convierte una vista de `operacion` en
  `laboratorio`.
- Cambiar de vista no consulta el backend ni cambia estado: no ejecuta modelos, no
  borra sesiones ni inicia recalibraciones.
- La navegación usa hash (`useHashRoute.ts`, escucha de `hashchange`), y `App.tsx`
  muestra `ModeBadge` (`features/navigation/ModeBadge.tsx`) en todas las rutas.
  `App.resilience.test.tsx` comprueba que las 12 rutas renderizan región principal,
  título y `.mode-badge` con el backend desconectado (PR #50).
- Origen: PR #45 (diseño F3, docs) y #46 (F4, `ModeBadge` y `modeForView`).

### 2. Tres recorridos, no unificados

- CICYTEX: `features/defense/CicytexDefensePage.tsx` con
  `CicytexTraceability.tsx` y `cicytexApi.ts`. Opera una sesión con estado en el
  servidor (`POST /api/v2/cicytex/replay/sessions`, `.../advance`, `.../reset`,
  `.../feedback`). Al recargar, la página guarda en `sessionStorage` (clave
  `cicytex-defense-session`) sólo una referencia mínima (`session_id`, sensor, horizonte
  y emisión) y la restaura con `GET .../sessions/{id}` (PR #59). Valida que la sesión
  coincida con la referencia; si falla la recuperación (por ejemplo 404, registro mal formado o sesión que no coincide) se muestra el aviso `role="alert"`, se borra la referencia y se ofrece «Iniciar otra emisión». El borrador y las notas de feedback no
  se transfieren. El feedback no preselecciona ninguna opción y el botón de registro
  queda deshabilitado hasta elegir una (PR #59). La recuperación es por pestaña.
- Histórico compartido: `features/producer/HistoricalWalkthrough.tsx`, usado por
  `PergaminoDefensePage.tsx` y `MelchorRomeroDefensePage.tsx`. Es de lectura por GET
  sin estado en el servidor; el reloj vive en el cliente y el cliente filtra filas
  futuras (PR #55, #56).
- Laboratorio: `features/lab/SensorLabPage.tsx`. Ingesta con reloj ficticio y datos
  sintéticos, declarados como tales en la propia página (PR #57).

No se unificaron porque los protocolos difieren: sesión con estado y permisos de
acción por estado (CICYTEX) frente a lectura sin estado (histórico) frente a ingesta
con reloj ficticio (laboratorio). Forzar una sola página obligaría a condicionales de
sitio dentro de un componente y mezclaría contextos que el ADR-0014 mantiene
separados. Se comparten sólo piezas de presentación y la jerarquía de acciones.
El seguimiento (`docs/seguimiento-tareas.md`, fila F5) registra explícitamente que no
se unificó `CicytexDefensePage` sobre `HistoricalWalkthrough`.

### 3. Procedencia de solo lectura y regla de no simulación

- `GET /api/v2/cicytex/replay/provenance`
  (`backend/app/routers/cicytex_replay.py`) delega en
  `CicytexProvenanceApplication` (`src/historical_replay/cicytex_provenance.py`).
- Lista blanca de campos (`_TOP_LEVEL` y `_PER_HORIZON` en
  `src/historical_replay/cicytex_provenance.py`): identidad y particiones (hashes, commit,
  semilla, límites de partición, ids de corridas MLflow del paquete archivado), además de
  `proxy`, `ensemble_policy`, `prediction_sha256`, `threshold_train_p20` y
  `first_legitimate_emission`. Métricas y filas de predicción quedan fuera para no
  adelantar resultados al reloj del replay. Los hashes son los registrados en el paquete
  archivado: un SHA-256 calculado hoy identifica el archivo actual; no demuestra
  retrospectivamente qué archivo intervino en una corrida.
- Los esquemas de respuesta son cerrados (`extra="forbid"` en
  `backend/app/schemas_cicytex_replay.py`, `CicytexProvenanceResponse`). Si el paquete
  no cumple el contrato, el endpoint responde 503, no 500 (PR #53, `8c78b68`).
- Procedencia por emisión del productor (PR #64 y #67): `bundle.json` de las ejecuciones
  nuevas registra `code_identity` (commit/dirty) y `GET /api/v2/sensors/{sensor_id}/batches/{batch_id}/provenance`,
  de solo lectura, alimenta el panel «Procedencia de la emisión». Las emisiones previas a #64
  figuran «no registrado»; configuración completa, corridas MLflow y semilla figuran «no disponible»
  porque no se persisten por emisión. El estado de este ADR no cambia.
- Regla: lo que no existe se declara «no disponible», nunca se simula.
  `CicytexTraceability.tsx` declara no disponibles la versión del modelo y el linaje
  de recalibración (los modelos están congelados por corrida). `HistoricalWalkthrough`
  declara no disponibles SHA-256 del dataset, commit, semilla, corridas de MLflow,
  particiones y linaje de recalibración, porque `producer_v2` no los expone; muestra
  versión de modelo y calibración cuando el payload las trae. `SensorLabPage` declara
  procedencia sintética (semilla del generador, reloj local ficticio, datos y revisión
  sintéticos). La trazabilidad no bloquea el
  recorrido: si falla, se muestra «no disponible».
- Pruebas: `backend/tests/test_cicytex_replay_provenance.py`.

### 4. Verificación en navegador sin dependencias nuevas

- `scripts/ui/verify-journeys.mjs` y `scripts/ui/capture-view.mjs` controlan Chrome
  headless por CDP con Node >= 22, sin paquetes adicionales. Procedimiento y
  resultados en `docs/design/f7-verificacion-navegador.md` (PR #54).
- Desde el PR #62 el script cubre cuatro sitios (Melchor Romero, Pergamino, CICYTEX y
  laboratorio) y la ficha de Laya en `#arquitectura`, contra un servidor de fixtures
  determinista (`scripts/ui/fixture-server.mjs`), y corre en CI en el job
  `browser-journeys`. Sigue sin Playwright ni axe y no es una auditoría de
  accesibilidad. Cada chequeo comprueba sólo lo que declara. Las fixtures fijan el
  contrato grabado: no prueban el backend real.

### 5. Contrato OpenAPI congelado

Dos tests intervienen, con funciones distintas:

- `backend/tests/test_openapi_typescript_ci_contract.py` congela la identidad exacta
  (tamaño en bytes y SHA-256, tabla `GENERATED_ARTIFACTS`) de `manifest.json`,
  `openapi.json` y `schema.d.ts` en `frontend/src/api/generated/`, y comprueba que la
  generación real es idéntica a lo versionado. Añadir el endpoint de procedencia
  obligó a actualizar esa tabla (commit `606eec7`).
- `tests/test_openapi_typescript_foundation.py` prueba la cadena de herramientas (JSON
  canónico, ids de operación, manifiesto que vincula bytes de OpenAPI y TypeScript);
  no fija la identidad de los artefactos versionados.

Consecuencia: todo cambio de API exige regenerar el artefacto y actualizar la tabla
`GENERATED_ARTIFACTS` en el mismo PR.
El router CICYTEX permanece delgado (`test_thin_replay_router_architecture.py`;
commit `5098fd9`).

## Alternativas descartadas y limitaciones

- Playwright y axe: descartados hasta ahora por decisión de alcance (sin dependencias
  nuevas). Siguen sin incorporarse; admitirlos como dependencia nueva es una decisión
  pendiente de decisión de alcance. No hay auditoría automática de accesibilidad. Los
  recorridos de navegador sí corren en CI desde el PR #62, sin dependencias nuevas.
- Unificar las páginas: descartado por lo expuesto en la decisión 2.
- Rehidratación autónoma de la sesión CICYTEX por servidor (cookie o identidad de
  usuario): sigue descartada. La recuperación al recargar ya existe, pero del lado del
  cliente (`sessionStorage` más `GET /sessions/{id}`, PR #59), por pestaña; otra
  pestaña o ventana no la recupera. La durabilidad del almacén de sesiones del backend
  ante un reinicio no se verificó.
- Pendientes declarados en `docs/seguimiento-tareas.md`: revisiones POST de Pergamino
  y Melchor Romero y pasos C y D del laboratorio en el script de navegador. El teclado
  con la sesión abierta ya se verifica en CICYTEX (C8) y en el laboratorio (L8).

## Mapa de PR (`gh pr view`, estado MERGED)

| PR | Merge commit | Título |
| --- | --- | --- |
| #45 | `5da5b48` | docs: checkpoint F0-F1 y diseño F3 |
| #46 | `3c819fc` | destino Arquitectura e indicador de modo por vista (F4) |
| #47 | `814078c` | catálogo de arquitectura con fichas por nodo (F6) |
| #48 | `59d7eb8` | robustez operativa del recorrido CICYTEX (F5, primer sitio) |
| #49 | `116e861` | docs: checkpoint tras F4, F5 y F6 |
| #50 | `ef44b87` | resiliencia sin backend, Laya apagada y teclado (F7 parcial) |
| #51 | `2ce2cc2` | aislar el borrador de feedback CICYTEX por sesión (F5, HU5/HU6) |
| #52 | `238e3f9` | recorrido visual integral de CICYTEX (F5) |
| #53 | `a4a6ba4` | trazabilidad de una predicción concreta en CICYTEX (F6) |
| #54 | `b665c8d` | docs: verificación en navegador real de CICYTEX y paquete F8 (F7/F8) |
| #55 | `696154f` | recorrido histórico compartido con veredicto, acciones y trazabilidad declarada (F5/F6) |
| #56 | `653e4a7` | campo «Recorrido hasta» con el reloj efectivo desde el inicio (F5) |
| #57 | `43bdfb3` | laboratorio de sensores con acciones jerarquizadas y trazabilidad sintética declarada (F5/F6) |
| #58 | `73a1cfc` | docs: ADR 0015, paquete de defensa y tracking F5–F8 (F8) |
| #59 | `a433b4d` | recuperar la sesión CICYTEX al recargar y feedback sin preselección (F5, HU5/HU6) |
| #60 | `e575a30` | acciones de revisión equivalentes, foco estable y envío único (F5, HU5/HU6) |
| #61 | `c7e13b8` | laboratorio: lectura, declaración única de no disponibles y recorrido a 360 px (F5) |
| #62 | `9cea43f` | recorridos de navegador de los cuatro sitios con fixtures deterministas y job de CI (F7) |
| #63 | `f43c3b4` | docs: sincroniza ADR 0015, F7/F8 y seguimiento con #59-#62 (F5-F8) |
| #64 | `584bd94` | `code_identity` en `bundle.json` de ejecuciones nuevas (HU6, `predictive-modeling`) |
| #65 | `c5dc55e` | docs: guion de demo 3-5 min y ensayo técnico cronometrado (F8) |
| #66 | `6106b78` | objetivos táctiles del laboratorio, error de red en español y regresión de Laya (F5) |
| #67 | `5e22733` | panel de procedencia de la emisión y endpoint de solo lectura (F6) |

Los commits `8c78b68`, `606eec7` y `5098fd9` citados arriba son commits internos del
PR #53, no merge commits.

## Verificación realizada y límites

Hechos verificados:

- Tests de componente (jsdom) y de API de los cambios (vitest, pruebas de `provenance`,
  guards OpenAPI y de router delgado). Los tests de #59 y #60
  (`CicytexDefensePage.restore.test.tsx`, `ForecastCard.reviewActions.test.tsx`) son de
  componente, sin navegador real.
- Navegador real por script (`scripts/ui/verify-journeys.mjs`, PR #62), contra fixtures
  deterministas y en CI: 78 PASS en #62 y 80 PASS con #67, 0 FAIL y 1 INFO (A9, lista las rutas sin fixture
  `GET /api/v2/sectors` y `/api/v2/sensors`). Cubre recarga con sesión restaurada y con
  404 y feedback sin preselección en CICYTEX; no cubre la igualdad de peso visual de
  «Confirmar» y «Rechazar» (esa propiedad la prueba sólo el test de componente de #60).
- Verificación visual del laboratorio a 360 px en el PR #61, pasos A a D.

Límites y pendientes (no verificados o no resueltos):

- Laboratorio: #61 declaró tamaños táctiles bajos, mensaje crudo «Failed to fetch» y laboratorio con backend apagado sin probar; #66 aplica objetivos de 44 px por regla CSS a ≤600 px (no medidos en navegador), mensaje en español y un test con backend apagado. Siguen pendientes los inputs de fecha `.fp-filters` (36 px) y el enlace de `NoReadingsHint` (~20 px) en `ResumenView`.
- Procedencia (#64, #67): `code_identity` sólo existe en bundles de ejecuciones nuevas; las emisiones previas figuran «no registrado»; configuración completa, MLflow y semilla figuran «no disponible». Falta la revisión visual con un bundle que tenga `code_identity` y el incremento 3 de linaje (identidad del paquete en sesiones SQLite de CICYTEX).
- Las revisiones POST de Pergamino y Melchor Romero y los pasos C y D del laboratorio no
  están en el script de navegador.
- Sin linaje de recalibración operativo.
- Sin SHA, commit ni MLflow para `producer_v2` ni para el laboratorio (exigiría cambios
  de backend).
- Sin auditoría axe ni Playwright (decisión de alcance: sin dependencias nuevas; no consta una decisión del dueño en el repositorio).
- Las fixtures no prueban el backend real; un cambio de contrato exige regrabarlas.
- Algunas verificaciones visuales (capturas en el scratchpad) no son reproducibles desde
  el repositorio.

## Consecuencias

- Las vistas son seguras de recorrer: el cambio de modo no altera estado ni
  evidencia.
- La interfaz nunca muestra metadatos inventados; la ausencia es visible.
- Agregar un sitio implica una página propia o reutilizar el recorrido histórico, no
  ampliar uno existente con condicionales.
- Este ADR no altera resultados, protocolos ni la desactivación de Laya.
