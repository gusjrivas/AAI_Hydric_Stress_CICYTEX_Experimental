# AAI_Hydric_Stress (repositorio experimental)

Prototipo experimental de la arquitectura de inteligencia artificial para detección temprana de estrés hídrico en cultivos hortícolas — Trabajo Final, Maestría en Inteligencia Artificial (FIUBA).

Este repositorio es la línea experimental del Trabajo Final y se mantiene separado del repositorio original `AAI_Hydric_Stress`, que no se modifica. Ver [`docs/adr/`](docs/adr/) para las decisiones de arquitectura y [`openspec/project.md`](openspec/project.md) para el contexto, alcance y convenciones.

## Propósito, alcance y contextos

El núcleo del trabajo es el modelado predictivo con apoyo de retroalimentación humana. Los sensores y el IoT son fuentes de datos, no la contribución central. El sistema es apoyo a la decisión: no automatiza el riego, no estima ahorro de agua y no presenta resultados como validación agronómica.

| Contexto | Datos | Uso en el repositorio | Límite principal |
|----------|-------|-----------------------|------------------|
| Melchor Romero (2024) | Conjunto consolidado NASA POWER + ESA CCI Soil Moisture | Evidencia histórica `controlled_daily_v3` y recorrido histórico de cinco emisiones | La demo no tiene evaluación retrospectiva agregada propia |
| Pergamino | Reanálisis ERA5-Land y NASA POWER, sin sensor propio | Campaña externa `controlled_daily_v4_external_pergamino` y ensamble demostrativo | Un sitio y un año, etapas B y C exploratorias, objetivo bajo P20 y no estrés fisiológico |
| CICYTEX | 21 sondas de humedad del suelo, una campaña (2023), un sitio | Evaluación inicial aislada y replay causal posterior del ensamble | Objetivo proxy "humedad futura bajo el P20 de entrenamiento", sin etiquetas fisiológicas independientes |
| Laboratorio sintético | Datos generados en la interfaz | Demostración del pipeline | Sin valor de evidencia científica |

Integrar varios sitios en una misma interfaz no equivale a una validación multisitio ni a una generalización geográfica. Las cifras de un contexto no son comparables con las de otro.

## Capacidades implementadas y limitaciones

- Ingesta, calidad de datos, modelado predictivo, retroalimentación humana, integración y ejecución de experimentos (tabla de HU más abajo).
- Interfaz React con API FastAPI: seguimiento histórico por sitio, "Mi cultivo", laboratorio sintético, evidencia, arquitectura y herramientas técnicas.
- Reproducción histórica causal: las observaciones posteriores a la fecha simulada permanecen ocultas.
- Recorrido guiado de cuatro sitios en `#demo-guiada`.
- No hay aprendizaje continuo ni telemetría en vivo. La retroalimentación humana de los recorridos de ensamble se registra con fines de demostración y no recalibra ni reentrena el ensamble. Solo el circuito manual de HU5 sobre un predictor individual admite recalibración explícita.

### Laya

Laya es un adaptador consultivo de triaje de texto de retroalimentación, separado del núcleo predictivo. Está desactivada por defecto (sin `LAYA_DECISION_URL` ni `LAYA_MODEL_REVISION` el backend usa una política deshabilitada) y no está validada: no existe evaluación de utilidad sobre texto real ni corpus humano versionado. La interfaz la muestra como ficha "desactivado" en `#arquitectura`. Ver [ADR-0014](docs/adr/0014-arquitectura-multisitio-y-laya-consultiva.md).

## Entrenamiento, evaluación archivada y reproducción histórica

Son tres actividades distintas y no deben confundirse.

- **Entrenamiento o reejecución de un experimento**: ajusta modelos y escribe resultados nuevos. Requiere los datos de origen, que para CICYTEX y Pergamino están fuera de Git, y MLflow. Los scripts de preparación de la demostración (por ejemplo, el de Melchor Romero) ajustan y calibran modelos nuevos sin generar evidencia experimental. El recorrido de la interfaz en sí no reentrena.
- **Evaluación archivada**: resultados ya producidos y versionados. Para CICYTEX existen dos análisis distintos: la evaluación inicial (420 casos por horizonte) y el replay causal posterior del ensamble (399, 378 y 357 casos para +1, +2 y +3). No comparten denominador y sus métricas no se mezclan. El replay es retrospectivo y exploratorio sobre un período ya inspeccionado.
- **Reproducción histórica**: recorrido de la interfaz sobre paquetes congelados. Lee artefactos archivados, no reentrena y no genera evidencia nueva.

Resultados y documentos de referencia:

- Posición de defensa: [`docs/research/thesis-defense-position.md`](docs/research/thesis-defense-position.md).
- CICYTEX: [evaluación inicial](docs/research/cicytex-external-validation-report.md), [informe del replay causal](docs/research/cicytex-causal-ensemble-replay-report.md), [protocolo del replay](docs/research/cicytex-causal-ensemble-replay.md) y [reproducción](docs/research/cicytex-reproduction.md). Datos archivados en `results/cicytex/`.
- Pergamino: [evaluación retrospectiva exploratoria del ensamble](docs/research/ensemble-retrospective-evaluation-results.md).
- Cierre científico: [estado canónico](openspec/scientific-closure/current-execution-checkpoint.md).

## Probar Mi cultivo con Docker

El repositorio incluye un entorno local aislado con datos y modelos
sintéticos, históricos y pronósticos revisables:

```powershell
docker compose -f compose.producer-preview.yml up -d --build
```

Abrir http://localhost:5180. No requiere instalar Python/Node ni modifica los
servicios o datos del stack habitual. [Guía de prueba y reinicio](docker/producer-preview/README.md).
No representa validación predictiva real ni cierre científico. Este entorno no incluye CICYTEX.

## Estado del proyecto

Ver [`docs/seguimiento-tareas.md`](docs/seguimiento-tareas.md) para la auditoría detallada, tarea por tarea, con evidencia verificable. Resumen por historia de usuario:

| HU | Capacidad | Estado |
|----|-----------|--------|
| HU1 | Estado del arte y comprensión del dominio | ✅ Cerrada (estado del arte definitivo y auditoría de cierre completos) |
| HU2 | `data-ingestion` — preparación del conjunto experimental de datos | ✅ Cerrada (conjunto experimental real y reproducible NASA POWER + ESA CCI Soil Moisture, Melchor Romero 2024) |
| HU3 | `data-quality` — calidad, anomalías y datos sintéticos | ✅ Cerrada (revalidada sobre el pipeline causal vigente) |
| HU4 | `predictive-modeling` — modelado predictivo y alertas tempranas | ✅ Cerrada (revalidada sobre el esquema temporal y de selección vigente) |
| HU5 | `human-feedback` — retroalimentación humana y recalibración | ✅ Cerrada (revalidada con recalibración temporalmente controlada) |
| HU6 | `architecture-integration` — integración de la arquitectura | ✅ Cerrada (revalidada sobre la integración end-to-end vigente) |
| HU7 | `experiment-runner` — diseño y ejecución del plan experimental | ✅ Implementación y ejecución experimental completadas. La evidencia de `controlled_daily_v3` se preserva y la campaña externa `controlled_daily_v4_external_pergamino` ejecutó A, B, C y H. El cierre científico confirmatorio no se alcanzó: RB-05, `sc-06-scientific-synthesis`, `SC-GOV-025` y el gate `GF` permanecen en `FAIL` por una no conformidad de gobernanza documentada. |
| HU8 | Análisis de resultados y contrastación de la hipótesis | 🟡 Análisis y discusión completados con limitaciones explícitas. Los resultados de `controlled_daily_v3` se preservan; B y C de `controlled_daily_v4_external_pergamino` se interpretan como evidencia retrospectiva exploratoria. No se declara validación agronómica ni cierre científico confirmatorio. La memoria técnica final continúa en elaboración. |

Además de las HU del backlog de tesis, el repo incluye una interfaz de usuario (`backend/` + `frontend/`, ver sección siguiente) que expone HU5+HU6 y cierra el loop de recalibración manual disparada desde la UI (ver `docs/adr/0006-recalibracion-disparada-desde-la-ui.md`).

## Estructura del código

- `src/data_ingestion/`: esquema del contrato de datos, conectores (NASA POWER, ESA CCI Soil Moisture) y consolidación de fuentes.
- `src/data_quality/`: limpieza, detección de anomalías (Isolation Forest), generación de datos sintéticos y pipeline integrado.
- `src/predictive_modeling/`: etiquetado, ingeniería de variables, modelos (persistencia, regresión logística, Random Forest), evaluación y alertas.
- `src/human_feedback/`: esquema y registro de retroalimentación humana sobre alertas, e integración con predicciones para recalibración supervisada.
- `src/architecture_integration/`: orquestador de punta a punta que encadena las cuatro capacidades anteriores.
- `src/experiment_runner/`: ejecución del plan experimental (escenarios de escasez/ruido, aumentación sintética, registro de corridas en MLflow).
- `scripts/`: puntos de entrada de línea de comandos para correr cada pipeline sobre un dataset real (`run_data_quality_pipeline.py`, `run_end_to_end_pipeline.py`, conectores de ingesta).
- `backend/`: API FastAPI de la interfaz de usuario (alerting-ui) — fachada delgada que orquesta el pipeline y expone `POST /sensors/{sensor_id}/readings`, `POST /forecast/{sensor_id}/run`, `GET /feedback/{sensor_id}` + confirmar/rechazar por fecha, `POST /recalibrate/{sensor_id}`, y tres endpoints de observabilidad de solo lectura para la demo académica (`GET /quality/{sensor_id}`, `GET /models/{sensor_id}/active`, `GET /lineage/{sensor_id}`).
- `frontend/`: aplicación React + TypeScript (Vite) que consume la API del productor (`/api/v2`), el pipeline plano y `/replay`. Navegación en seis grupos: **Seguimiento histórico** (CICYTEX, Pergamino y Melchor Romero), **Mi cultivo** (pantalla de entrada, pensada para un productor), **Laboratorio** (datos sintéticos, sin validez de campo), **Evidencia** (por niveles, con el estado de gobernanza siempre visible), **Arquitectura** (catálogo por nodos, sin telemetría en vivo) y **Herramientas técnicas** (recorrido datos → calidad → predicción → feedback → recalibración → linaje). Además existe la ruta propia `#demo-guiada`.
- `openspec/specs/`: especificación viva de cada capacidad (requisitos, escenarios, verificación con datos reales, limitaciones conocidas). `openspec/changes/`: historial de decisiones de diseño por *change*.
- `docs/adr/`: decisiones de arquitectura, desde el stack técnico del PoC (ADR-0001/0002) hasta el stack web, MLflow/MinIO y la dockerización de backend/frontend (ADR-0003 a ADR-0006).

## Interfaz de usuario (alerting-ui)

Backend y frontend dockerizados que exponen el pipeline completo (HU6) y la retroalimentación humana (HU5), incluyendo recalibración manual del modelo desde un botón en la UI (ver `docs/seguimiento-tareas.md`, sección "Interfaz de usuario").

La interfaz es apoyo a la decisión, no automatiza el riego. «Sin alerta prevista» no equivale a ausencia de estrés hídrico, y un pronóstico con datos viejos se señala como «Este pronóstico no es actual». Mi cultivo solo lee el último pronóstico guardado; nunca emite uno por su cuenta.

- Diseño y criterios: [`docs/design/ui-professional-redesign-plan.md`](docs/design/ui-professional-redesign-plan.md) y [`docs/design/alerting-ui-visual-design.md`](docs/design/alerting-ui-visual-design.md). El prototipo de la etapa de diseño se conserva en `design/prototypes/ui-professional/`.
- Prueba con un productor: [`docs/design/prueba-con-productor.md`](docs/design/prueba-con-productor.md).
- Guías vigentes de defensa: [arranque de la demo](docs/design/defense-demo-startup-guide.md), [guion de 3-5 minutos](docs/design/demo-guion-defensa.md) y [paquete de defensa](docs/design/f8-paquete-defensa.md). El recorrido simplificado `#demo-guiada` recorre CICYTEX, Pergamino, Melchor Romero y el laboratorio en cuatro pasos. Los requisitos de cada recorrido están en la guía de arranque.
- Reinicio de la demo de Pergamino y Melchor Romero con línea base verificada: `./scripts/demo_reset.ps1 -Action Reset -StartFrontend`. Requiere `-Action Init` previo, Docker, la imagen `aai-defense-rehearsal-backend:local` y datos externos al repositorio (ver la guía de arranque).
- Versiones congeladas: documentos anteriores citaban los tags `memoria-base-2026-09-29` y `memoria-ui-2026-10-03`. Ninguno existe en este clon (`git tag` no devuelve resultados). Para fijar una versión se usa el SHA del commit.

### Stacks de Docker y cobertura por recorrido

Ningún `docker compose` cubre por sí solo todos los recorridos.

| Recorrido | Qué lo sirve | Observación |
|-----------|--------------|-------------|
| Mi cultivo con datos sintéticos | `compose.producer-preview.yml` (http://localhost:5180) | Sin CICYTEX |
| CICYTEX (lectura del replay archivado) | `compose.cicytex.yml` (frontend http://127.0.0.1:55180, backend http://127.0.0.1:55800) | La imagen copia `results/cicytex/causal_replay`. El compose no define `PRODUCER_V2_ENABLED`, por lo que, según la lectura del código, los recorridos de Pergamino y Melchor Romero no funcionan en ese stack (no verificado en ejecución). MLflow (5500), PostgreSQL y MinIO solo se necesitan para reejecutar el experimento |
| Pergamino y Melchor Romero | `scripts/start_defense_demo.ps1` con `-DataDir` y `-BundleRoot` externos | Los artefactos de Pergamino no están en un clon limpio. Melchor Romero se prepara con `scripts/prepare_melchor_romero_historical_demo.py` |
| Stack principal (`docker compose up`) | `docker-compose.yml` | La imagen del backend no incluye `results/cicytex/causal_replay`, por lo que se espera que `/api/v2/cicytex/replay/*` responda 503 (por lectura de código, no ejecutado) |

El funcionamiento de extremo a extremo de `compose.cicytex.yml` y de `start_defense_demo.ps1` con rutas de CICYTEX no está verificado en esta redacción. La reejecución del experimento CICYTEX está en [`docs/research/cicytex-reproduction.md`](docs/research/cicytex-reproduction.md).

Para levantar el stack principal (Postgres + MinIO + MLflow + backend + frontend), que no sirve el replay de CICYTEX:

```bash
cp .env.example .env   # ajustar si hace falta
docker compose up -d --build
```

- Frontend: http://localhost:5173
- Backend (FastAPI): http://localhost:8000
- MLflow Tracking UI: http://localhost:5000

Para correr el frontend fuera de Docker (`cd frontend && npm run dev`) apuntando a un backend en otro host/puerto, configurar `VITE_API_BASE_URL` (ver `frontend/.env.example`); por defecto usa `http://localhost:8000`.

## Desarrollo y tests

Se recomienda ejecutar el proyecto dentro del devcontainer/Docker incluido, para evitar restricciones de políticas de Control de Aplicaciones de Windows sobre las DLL nativas de pandas/pyarrow en algunos equipos:

```bash
docker build -t aai-hydric-stress-test .
docker run --rm aai-hydric-stress-test
```

También puede abrirse la carpeta en VS Code con la extensión Dev Containers (`.devcontainer/devcontainer.json`).

Si el entorno local no tiene esa restricción, alternativamente:

```bash
pip install -e ".[dev,backend]"
pytest -q                    # tests de src/ (núcleo)
pytest backend/tests -q      # tests del backend de alerting-ui
```

Para los tests del frontend:

```bash
cd frontend
npm install
npm run test
```

## Evidencia y protocolos experimentales

El repositorio conserva dos líneas de evidencia complementarias. `controlled_daily_v3` establece el esquema causal diario utilizado para la evaluación sobre Melchor Romero: objetivo observado separado de entradas imputadas o ruidosas, calendario diario obligatorio, contratos completos de modelos y evaluación temporal del ciclo de recalibración. Ver [protocolo experimental v3](docs/research/protocolo-experimental-v3.md).

La campaña externa `controlled_daily_v4_external_pergamino` ejecutó las etapas A, B y C, junto con el complemento H, sobre datos de reanálisis de Pergamino. Los resultados y sus limitaciones se preservan. Sin embargo, la auditoría final RB-05 concluyó en `FAIL` por una no conformidad de gobernanza. En consecuencia, `sc-06-scientific-synthesis`, `SC-GOV-025` y el gate `GF` permanecen en `FAIL`. Las etapas B y C se interpretan como evidencia retrospectiva exploratoria y no como cierre científico confirmatorio.

Las etapas A, B y C, junto con H, no deben repetirse dentro de la campaña cerrada. Una confirmación futura requeriría una campaña nueva, independiente y basada en datos no utilizados. Ver [estado canónico del cierre científico](openspec/scientific-closure/current-execution-checkpoint.md).

La interfaz de reproducción histórica conserva la causalidad temporal: presenta la fecha de origen, mantiene ocultas las observaciones futuras hasta la fecha simulada correspondiente y solo habilita la retroalimentación cuando existe una observación real. Esta interfaz permite inspección y trazabilidad. No constituye validación agronómica, eficacia de campo ni operación automática del riego.
