# ADR-0015: Arquitectura de la interfaz de defensa: recorridos por sitio, procedencia de solo lectura y verificación sin dependencias nuevas

Estado: **Aceptado el 2026-10-18**.

Trazabilidad: HU6 (`architecture-integration`) y UI (`alerting-ui`); HU5
(`human-feedback`) sólo por el borrador de revisión del recorrido CICYTEX. Fase
CRISP-DM: despliegue e integración experimental. Cambios entregados en los PR #45 a
#57. No cambia modelos, umbrales, protocolos, hipótesis ni HU7/HU8. Laya sigue
desactivada (ADR-0014).

## Contexto

La interfaz de defensa debe mostrar cuatro contextos que el ADR-0014 declara no
intercambiables (Pergamino, Melchor Romero, CICYTEX y laboratorio sintético) sin
presentar datos simulados como evidencia ni inventar metadatos que el backend no
expone. Los PR #45 a #57 rediseñaron la navegación, los recorridos y la verificación.
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
  `.../feedback`).
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
- Lista blanca de campos: sólo identidad y particiones (hashes, commit, semilla,
  límites de partición, ids de corridas MLflow del paquete archivado). Métricas y filas
  de predicción quedan fuera para no adelantar resultados al reloj del replay.
- Los esquemas de respuesta son cerrados (`extra="forbid"` en
  `backend/app/schemas_cicytex_replay.py`, `CicytexProvenanceResponse`). Si el paquete
  no cumple el contrato, el endpoint responde 503, no 500 (PR #53, `8c78b68`).
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
- Límites: no corre en CI (la ruta de Chrome está fija a Windows y usa `%TEMP%`);
  sólo cubre el recorrido CICYTEX; no es una auditoría de accesibilidad y no usa axe.
  Cada chequeo comprueba sólo lo que declara.

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

- Playwright y axe: descartados por decisión de alcance (sin dependencias nuevas). No
  hay auditoría automática de accesibilidad ni ejecución en CI.
- Unificar las páginas: descartado por lo expuesto en la decisión 2.
- Rehidratar la sesión CICYTEX tras recargar: **no hecho**. La ruta se conserva al
  recargar, pero la sesión no se reabre (limitación declarada). Decidir si se
  implementa queda pendiente de una decisión de alcance.
- Pendientes declarados en `docs/seguimiento-tareas.md`: script de navegador para los
  otros sitios, Tab con sesión abierta y ejecución en CI.

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

Los commits `8c78b68`, `606eec7` y `5098fd9` citados arriba son commits internos del
PR #53, no merge commits.

## Verificación realizada y límites

Hechos verificados:

- Tests de componente y de API de los cambios (vitest, pruebas de `provenance`,
  guards OpenAPI y de router delgado).
- Navegador real por script (`scripts/ui/verify-journeys.mjs`): 12 PASS y 1 INFO (J6),
  solo recorrido CICYTEX.
- Verificación visual puntual en Chrome headless contra backend real (capturas en el
  scratchpad, no versionadas): Pergamino y Melchor Romero a 1366 y 360 px sin desbordes
  de página ni texto fijo de Pergamino en Melchor Romero; laboratorio verificado solo
  hasta el paso B (los pasos C y D no se ejecutaron).

Límites y pendientes (no verificados o no resueltos):

- Laboratorio: pasos C y D y final de página a 360 px sin verificar; dos defectos
  menores no corregidos (la nota «Cómo revisar» ocupa media pantalla a 1366 px; los
  campos «no disponible» repiten texto largo en negrita en la trazabilidad).
- «Confirmar resultado» y «Rechazar resultado» tienen igual peso visual: decisión de
  diseño pendiente del dueño del proyecto.
- Sin rehidratación de la sesión CICYTEX tras recargar.
- Sin linaje de recalibración operativo.
- Sin SHA, commit ni MLflow para `producer_v2` ni para el laboratorio (exigiría cambios
  de backend).
- El script de navegador no cubre los otros sitios; no hay E2E en CI ni auditoría axe.
- Las verificaciones visuales no son reproducibles desde el repositorio.

## Consecuencias

- Las vistas son seguras de recorrer: el cambio de modo no altera estado ni
  evidencia.
- La interfaz nunca muestra metadatos inventados; la ausencia es visible.
- Agregar un sitio implica una página propia o reutilizar el recorrido histórico, no
  ampliar uno existente con condicionales.
- Este ADR no altera resultados, protocolos ni la desactivación de Laya.
