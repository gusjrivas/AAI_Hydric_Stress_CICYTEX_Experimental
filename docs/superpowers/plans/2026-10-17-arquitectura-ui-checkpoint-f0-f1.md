# Checkpoint F0–F1: arquitectura demostrable y UI de defensa

- HU: HU6/HU7 (presentación); capacidades OpenSpec: `architecture-integration`, `alerting-ui`.
- CRISP-DM: Deployment / Evaluation. Sin impacto sobre hipótesis, datos, modelos ni protocolo v3/v4.
- Plan fuente: `plan-maestro-arquitectura-ui-claude-code.md` (externo al repo, 2026-10-17).

## F0 — estado recuperado

| Ítem | Valor |
|---|---|
| Repo / remoto | `gusjrivas/AAI_Hydric_Stress_CICYTEX_Experimental`, `origin` |
| Base | `origin/main` = `9a52df2` (merge PR44), ascendencia verificada |
| Rama de trabajo | `feat/ui-arch-f1-discovery` (desde `origin/main`) |
| Protección de `main` | Ninguna (`gh api .../branches/main/protection` → 404 «Branch not protected»); permisos admin del usuario |
| Entorno local | Python 3.13.15, Node 24.16.0 (CI usa 3.11 / 22) |
| Línea base frontend | `node_modules` estaba desincronizado del lock (TS 6.0.3, sin `openapi-typescript`): 1 test y `tsc -b` fallaban. Tras `npm ci` (lock): TS 5.9.3, `tsc -b` exit 0, vitest 50 archivos / 360 tests pasan |
| Codebase Memory | Proyecto `AAI_Hydric_Stress_CICYTEX_Experimental`, root `C:/Repo/...`, indexado 2026-10-10 (previo a PR44; 11847 nodos). Freshness `metadata_changed`/`not_tracked`: usar sólo para localizar, verificar con fuente |

Hecho vs. inferencia: la línea base verde es un resultado local observado, no CI del HEAD.

## F1 — componentes reales (con evidencia)

| Componente | Ruta / símbolo |
|---|---|
| Ingesta | `src/data_ingestion/` (`storage.py`, `catalog.py`, `mock_sensor.py`) |
| Calidad | `src/data_quality/`; `backend/app/routers/quality.py` |
| Modelado | `src/predictive_modeling/` |
| Integración / emisión | `src/architecture_integration/` (`pipeline.py`, `producer_emission.py:emit_forecasts`) |
| Feedback humano | `src/human_feedback/` |
| Laya (consultivo, default-off) | puerto `human_feedback/ports.py`; adaptadores `adapters/disabled.py`, `adapters/laya_http.py`; selección `backend/app/dependencies.py:get_feedback_triage` |
| Replay histórico / CICYTEX | `src/historical_replay/` (puertos, adaptadores SQLite/CSV, aplicaciones) |
| Runner | `src/experiment_runner/` |
| Composición | `backend/app/dependencies.py`, `config.py`, `main.py` (routers) |
| Contrato OpenAPI | `frontend/scripts/openapi-typescript-toolchain.mjs` → `frontend/src/api/generated/`; CI `api:check` |

Persistencia: Parquet (`data/`), JSON por sensor (operativo / histórico), SQLite
(`historical_feedback`, `cicytex_replay_sessions`). Feedback histórico, operativo
y recalibración legacy están en almacenes distintos.

## F1 — UI existente

Rutas hash (11 ids, 5 grupos) en `features/navigation/useHashRoute.ts`; `#demo` y
`#reproduccion-historica` se resuelven fuera de `ROUTES` con dos hooks duplicados
en `App.tsx` (333 líneas). `ArchitectureFlow` (40 líneas, 7 etapas, sin tests)
está dentro de un `<details>` colapsado en la ruta `evidencia`. Pergamino y
Melchor Romero comparten `HistoricalWalkthrough`; `CicytexDefensePage` duplica
gráfico/tablas/feedback con código minificado a mano y sin reintento. Sin tests:
`architecture-flow`, `navigation`, `PergaminoDefensePage`, `MelchorRomeroDefensePage`,
`SiteHeader`. No hay indicador explícito de operación/replay/laboratorio en
`ProducerView`.

## Matriz de brechas (priorizada)

| # | Brecha | Evidencia | Clase | Decisión |
|---|---|---|---|---|
| G1 | Mapa de arquitectura mínimo, colapsado, sin fuentes ni límites; categorías diseño/observado/guiado ausentes | `ArchitectureFlow.tsx`, `App.tsx:322` | Bloqueante para defensa | F6 |
| G2 | Sin indicador común de modo (operación/replay/laboratorio) | `SiteHeader.tsx`, `ProducerView` | Bloqueante para defensa | F4/F5 |
| G3 | Navegación: 5 grupos sin mapeo a las 3 preguntas; casos especiales de hash | `useHashRoute.ts`, `App.tsx:38-62` | Importante | F4 |
| G4 | `CicytexDefensePage` duplicada y sin estados de reintento | `defense/CicytexDefensePage.tsx` | Importante | F5 |
| G5 | Componentes de navegación/sitio sin pruebas | ver arriba | Importante | F4 (TDD) |
| G6 | Lógica de dominio en routers (`recalibration.py`, `producer_v2.py`) | lectura explorador | Importante, deuda | Límite aceptado (sin defecto funcional demostrado) |
| G7 | `get_feedback_triage` evalúa `float(LAYA_MIN_CONFIDENCE)` antes de la rama «disabled»: un valor mal formado lanza `ValueError` aun con Laya desactivado; config Laya a medias lanza `RuntimeError`. Probable 500 (no reproducido). Es falla cerrada ante configuración inválida, sin efecto sobre datos | `dependencies.py:197-215` | Endurecimiento menor, sin defecto reproducido | Límite aceptado; RED si se reproduce |
| G8 | Variables de entorno dispersas; I/O CSV por petición | `dependencies.py` | Cosmética | Límite aceptado |
| G9 | Sin backup/restore de `data/`, JSON, SQLite en backend | exploración | Documentar en F8 | No implementado |

## Cierre de F2

Ninguna brecha demostrada afecta integridad, operación veraz o recuperación con
defecto reproducible (G6–G9 son deuda o endurecimiento, no fallos observados).
Per plan, F2 se cierra sin PR artificial; las limitaciones se documentan en F8.
Si F5/F7 demuestran un defecto, se abre RED específico.

## Próximo corte propuesto

PR-A (docs): este checkpoint + diseño F3 (mapa de navegación y wireframes en
`docs/design/ui-arquitectura-defensa.md`). PR-B (F4): shell de navegación con
indicador de modo y tres lentes sobre rutas existentes. Gate: CI exacto del HEAD,
revisión independiente sin P0/P1/P2.

## Estado tras F4, F6 y primer corte de F5 (2026-10-18)

- F4 (#46): ruta Arquitectura e indicador de modo. F6 (#47): catálogo versionado y fichas de nodo en `ArchitectureFlow`. F5 (#48): `CicytexDefensePage` robustecida (respuestas tardías, doble envío de feedback, reintento de catálogo, estado de carga). Brecha G4 cerrada.
- Recorridos restantes de F5, verificados por lectura de fuente y de tests, sin cambios de código:
  - Melchor Romero y Pergamino comparten `HistoricalWalkthrough`, que ya ignora respuestas tardías (A→B→A de emisión y de reloj, sensor, selección vacía, errores y conflictos tardíos) y tiene tests para cada caso.
  - Laboratorio mock (`useDemoSession`): tests de carrera ya cubren revisiones antiguas, sesión previa, desmontaje y error de red.
  - Pronóstico operativo: `ForecastPage.targetMaturity.test.tsx` cubre objetivo inmaduro, cambio de día UTC, compuerta de demo y 409.
- No verificado: persistencia de revisión tras recarga y permisos de acción por modo. Quedan para F7 (verificación integral); si se reproduce un defecto se abre un RED específico.
- Capturas antes/después de la interfaz: pendientes (F7/F8).
