# Recomendación sobre la aceptación del ADR 0015

Documento de apoyo a la decisión. No modifica el ADR 0015, que sigue **Propuesto**. No hay
aprobación del dueño del proyecto; la aceptación formal es suya (sección 5).

Base: `main` en `9cea43f` (merge del PR #62). Posterior: #63–#67 fusionados; el estado vigente está en el ADR 0015 y en `docs/seguimiento-tareas.md`. Trazabilidad: HU6 (`architecture-integration`),
UI (`alerting-ui`), HU5 sólo por el borrador de revisión. Fase CRISP-DM: despliegue.
Sin impacto en modelos, umbrales, protocolo, hipótesis, HU7/HU8 ni en la desactivación de Laya.
Método: lectura puntual de código y tests; no se ejecutó ninguna suite (ver sección 6).

> Las secciones 1 a 4 son **históricas**: se redactaron sobre el estado de `e575a30` (PR #60). Donde dicen que algo falta o es
> obsoleto, el estado actual en `9cea43f` está en la sección 6 y en el ADR 0015 ya modificado. Cada afirmación superada lleva la marca
> «histórico» y el PR que la resolvió.

## 1. Contraste decisión por decisión

| # | Decisión del ADR | Estado | Evidencia en `main` |
| --- | --- | --- | --- |
| 1a | Cuatro modos derivados sólo de la ruta; `simulatedSensor` pasa `operacion` a `laboratorio` | Coincide | `frontend/src/features/navigation/viewMode.ts` (`MODE_BY_VIEW`, `modeForView`); `ModeBadge.tsx` con los cuatro textos |
| 1b | Hash routing; `ModeBadge` en las 12 rutas con backend caído | Coincide | `useHashRoute.ts` (`ROUTES` tiene 12 entradas); `App.resilience.test.tsx` itera `ROUTES` |
| 1c | Cambiar de vista no consulta backend ni cambia estado | Coincide en código de modo; no verificable el efecto global | `viewMode.ts` es una función pura; no se auditó cada vista |
| 2a | Recorrido CICYTEX con sesión en servidor (POST/advance/reset/feedback) | Coincide | `cicytexApi.ts`; `backend/app/routers/cicytex_replay.py` (rutas `/sessions...`) |
| 2b | Histórico compartido por GET, reloj en cliente | Coincide por existencia de archivos; reloj/filtro no re-verificados | `features/producer/HistoricalWalkthrough.tsx` y sus 3 suites de test; usado por `PergaminoDefensePage.tsx`/`MelchorRomeroDefensePage.tsx` según el ADR |
| 2c | Laboratorio con reloj ficticio y datos sintéticos | Coincide por existencia | `features/lab/SensorLabPage.tsx`, `SensorLabPage.journey.test.tsx` |
| 2d | No se unificaron las páginas | Coincide | Tres componentes separados |
| 3a | `GET /provenance` delega en `CicytexProvenanceApplication`, 503 si el paquete falla | Coincide | `cicytex_replay.py` líneas 66-74; `src/historical_replay/cicytex_provenance.py` |
| 3b | Lista blanca: hashes, commit, semilla, particiones, ids MLflow; sin métricas ni filas | **Difiere (menor, texto)** | La lista real (`_TOP_LEVEL`, `_PER_HORIZON`) también incluye `proxy`, `ensemble_policy`, `prediction_sha256`, `threshold_train_p20` y `first_legitimate_emission`. No hay métricas ni filas de predicción, como dice el ADR |
| 3c | Esquemas cerrados `extra="forbid"` | Coincide | `schemas_cicytex_replay.py` (`_ClosedResponse`, `CicytexProvenanceResponse`) |
| 3d | «No disponible», nunca simulado | Coincide | `CicytexTraceability.tsx` (versión de modelo y linaje); `HistoricalWalkthrough.tsx` (SHA-256 y commit «no disponible») |
| 4 | Navegador por CDP sin dependencias; sin CI; sólo CICYTEX | Histórico (a `e575a30`): coincidía; ya resuelto en #62, que extiende el script a cuatro sitios y lo corre en CI con fixtures | `scripts/ui/verify-journeys.mjs`, `capture-view.mjs`; `.github/workflows/ci.yml` (`frontend-quality`: sólo `npm ci`, vitest, build); sin Playwright ni axe en `frontend/package.json` |
| 5 | Dos tests de contrato OpenAPI y router delgado | Coincide por existencia; no re-ejecutados | `backend/tests/test_openapi_typescript_ci_contract.py`, `test_thin_replay_router_architecture.py`, `tests/test_openapi_typescript_foundation.py`; el job `api-contract` de CI los invoca |
| 6 | Sesión CICYTEX **no** se rehidrata al recargar | **Difiere (obsoleto)** | PR #59 (`323d83b`): `CicytexDefensePage.tsx` guarda sólo `session_id`, sensor, horizonte y emisión en `sessionStorage` y restaura por `GET /sessions/{id}`; valida coincidencia, vacía el borrador y avisa con `role="alert"` si falla. Tests: `CicytexDefensePage.restore.test.tsx` |
| 7 | «Confirmar/Rechazar resultado» con igual peso: decisión pendiente | **Difiere (obsoleto)** | PR #60 (`970b263`): ambos botones comparten clase `forecast-card-choice`, orden fijo y `aria-describedby` común (`ForecastCard.tsx`); test `ForecastCard.reviewActions.test.tsx` |
| 8 | Feedback CICYTEX | Falta en el ADR | `CicytexDefensePage.tsx` no preselecciona opción y el botón queda deshabilitado hasta elegir (`restore.test.tsx`, bloque «feedback form») |
| 9 | Cabecera: «Cambios entregados en los PR #45 a #57»; mapa de PR | **Difiere (incompleto)** | Histórico (a `e575a30`): `main` incluía además #58, #59 y #60. Ya resuelto: #61 y #62 están fusionados (`gh pr view`) y el ADR y su mapa llegan a #62 |

## 2. Alternativas descartadas: ¿siguen siendo razonables?

- **Unificar las páginas.** Sigue siendo razonable: los tres protocolos siguen distintos
  (sesión con estado, lectura sin estado, ingesta ficticia). La restauración de #59 refuerza la
  diferencia, porque sólo CICYTEX tiene estado de servidor que recuperar.
- **Rehidratar la sesión por servidor.** El ADR la deja «no hecha». Hoy existe recuperación,
  pero **del lado del cliente**: `sessionStorage` guarda una referencia mínima y el servidor
  sólo responde un GET. No hay rehidratación autónoma por servidor (cookie o identidad de
  usuario). Esa alternativa sigue descartada, y la redacción debe distinguirla de la
  recuperación ya hecha. La sesión depende del almacén del backend; su durabilidad ante un
  reinicio no se verificó (el código prevé aviso si el GET falla).
- **Playwright y axe.** El ADR los descarta por «sin dependencias nuevas». El encargo de esta
  sesión y el change `extend-browser-journeys-ci` (PR #62) pidieron extender los recorridos de
  navegador a CI sin dependencias nuevas; no hay en el repositorio una decisión del dueño sobre
  Playwright o axe. Histórico (a `e575a30`): el script fijaba la ruta de Chrome de Windows y
  `%TEMP%`; #62 lo hizo portable (`CHROME_PATH` o detección, `os.tmpdir()`) y lo ejecuta en CI.
  Axe o Playwright seguirían requiriendo una dependencia nueva. La decisión es del dueño.

## 3. Riesgos y consecuencias no cubiertos

- **Sin verificación de navegador en CI.** Histórico (a `e575a30`; resuelto en parte por #62):
  entonces los tests de CI eran vitest (jsdom) y build. Hoy el job `browser-journeys` cubre en
  navegador, con fixtures, la restauración por `sessionStorage` (C7, C10); el tamaño táctil de
  #60 sigue leído en CSS, no renderizado (#60 lo declara).
- **Trazabilidad histórica frente a futura.** `GET /provenance` lee un resumen archivado del
  paquete. Un SHA-256 calculado hoy sobre un archivo no prueba qué archivo intervino en una
  corrida pasada; la prueba sólo vale si el hash fue registrado en la corrida original.
  Conviene que el ADR separe «identidad registrada en el paquete archivado» de «verificación
  actual de los archivos».
- **Sin commit ni MLflow para `producer_v2` ni el laboratorio.** Se declaran «no disponible»;
  cerrarlo exige cambios de backend fuera de este ADR.
- **Sesión en `sessionStorage`.** Es por pestaña; otra pestaña o ventana no recupera. El
  borrador de feedback no se guarda, a propósito (no se transfiere entre sesiones).
- **Documentos hermanos desactualizados.** Histórico (a `e575a30`): `docs/design/f7-verificacion-navegador.md` (J6),
  `docs/design/f8-paquete-defensa.md` y las filas F5/F7 de `docs/seguimiento-tareas.md` decían que la
  sesión no se reabre. Corregidos en el change `sync-ui-docs-f5-f8`.

## 4. Recomendación

**Aceptar con modificaciones.** La arquitectura (modos, tres recorridos, procedencia de solo
lectura, contrato congelado) coincide con `main`. Hay tres diferencias textuales que hacen
falso el ADR si se acepta tal cual. Cambios propuestos (no aplicados):

1. Sección «Alternativas descartadas»: reemplazar «Rehidratar la sesión CICYTEX tras
   recargar: no hecho...» por la descripción de la recuperación por `sessionStorage` + GET
   (PR #59), y mantener descartada sólo la rehidratación autónoma por servidor.
2. Sección «Límites y pendientes»: quitar «Sin rehidratación de la sesión CICYTEX tras
   recargar» y la frase sobre el peso visual de «Confirmar/Rechazar resultado»; citar #60 y
   `ForecastCard.reviewActions.test.tsx`.
3. Sección 2 (CICYTEX): añadir la recuperación (clave `cicytex-defense-session`, referencia
   mínima, borrador vacío) y que el feedback no preselecciona opción.
4. Sección 3 (lista blanca): enumerar los campos reales (incluidos `proxy`,
   `ensemble_policy`, `prediction_sha256`, `threshold_train_p20`,
   `first_legitimate_emission`) y aclarar que el hash es el registrado en el paquete.
5. Cabecera y «Mapa de PR»: ampliar a #58-#60 (y #61 sólo tras confirmarlo con `gh pr view`).
6. Alternativas: anotar que Playwright/axe están en reconsideración por pedido del dueño,
   sin decisión; no escribir que se resolvió.
7. Verificación: añadir que los tests de #59/#60 son de componente (jsdom), sin navegador real.

Corregir en el mismo cambio, o en uno aparte, los documentos de la sección 3 (F7, F8,
seguimiento).

## 5. Decisiones que sólo puede tomar el dueño

- Pasar el ADR de Propuesto a Aceptado (con o sin las modificaciones anteriores).
- Si Playwright o axe se admiten como dependencia nueva, o si CI debe ejecutar
  `verify-journeys.mjs` sin dependencias, y con qué alcance (sólo CICYTEX u otros sitios).
- Si la recuperación por pestaña basta o se quiere persistencia de revisión en servidor.
- Aceptar la ausencia de commit/MLflow para `producer_v2` y laboratorio o pedir cambios de backend.
- Dar por cerrados los pendientes de laboratorio (pasos C-D, 360 px, defectos menores).

## 6. No verificado

- No se ejecutó ningún test (vitest, pytest, `api:check`, `verify-journeys.mjs`); todo es lectura.
- No se leyó el cuerpo de `HistoricalWalkthrough.tsx` (reloj en cliente, filtro de filas futuras)
  ni de `SensorLabPage.tsx`; sólo su existencia y referencias.
- Posterior: #63–#67 fusionados; el estado vigente está en el ADR 0015 y en `docs/seguimiento-tareas.md`.
- Actualización posterior: los PR #61 (`c7e13b8`) y #62 (`9cea43f`) están fusionados según `gh pr view` (#45 a #62, todos MERGED). Las secciones 1 a 4 se redactaron sobre `e575a30` y no se reescribieron; las modificaciones propuestas ya se aplicaron al ADR en el cambio `sync-ui-docs-f5-f8`, que sigue **Propuesto**.
- No se verificaron los hashes de `GENERATED_ARTIFACTS` ni que el artefacto OpenAPI coincida.
- No se verificó la durabilidad del almacén de sesiones del backend ante reinicios.
- No se verificó el comportamiento en navegador real de #59 y #60.
- Los commits `8c78b68`, `606eec7` y `5098fd9` citados por el ADR no se buscaron en el historial.
