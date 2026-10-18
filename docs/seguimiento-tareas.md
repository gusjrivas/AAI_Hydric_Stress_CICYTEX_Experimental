# Seguimiento de tareas — plan de proyecto vs. estado real del repo

## 2026-10-18 — Arquitectura UI y defensa, plan maestro F0–F8 (UI, `alerting-ui`)

Reconciliación con el plan maestro (`plan-maestro-arquitectura-ui-claude-code.md`) y el alcance real de #45–#48. Capacidad `alerting-ui`, HU6; sin impacto sobre hipótesis, modelos, datos, protocolo HU7/HU8 ni holdouts. Laya sigue desactivada por defecto. No hay issues de GitHub abiertos asociados: no se cierra ninguno. ✅ sólo donde hay entregable mergeado, prueba y revisión sin P0/P1/P2 con CI verde sobre el HEAD exacto (o, en F2, decisión documentada).

| Fase | Estado | Entregable y evidencia | Falta |
|---|---|---|---|
| F0 Recuperar contexto | ✅ | Checkpoint `docs/superpowers/plans/2026-10-17-arquitectura-ui-checkpoint-f0-f1.md` (#45) | — |
| F1 Mapa verificado y brechas | ✅ | Mapa de componentes y matriz G1–G9 en el mismo checkpoint (#45) | — |
| F2 Cerrar brechas materiales | ✅ (sin PR) | Ninguna brecha con defecto reproducible; G6–G9 quedan como límites documentados | Documentarlos en F8; abrir RED si F5/F7 reproducen un defecto |
| F3 Diseño UX | ✅ | `docs/design/ui-arquitectura-defensa.md` (#45) | — |
| F4 Sistema visual y navegación | 🟡 | #46: ruta `#arquitectura`, `ModeBadge` y `modeForView` con tests (`viewMode`, `ModeBadge`, `App`, `AppHeader`); barra móvil verificada a 320 px. Cierra G2 y G3 | Verificación de teclado, contraste y movimiento reducido (F7); G5: componentes de sitio sin pruebas |
| F5 Rediseño de operación multisitio | 🟡 | #48: `CicytexDefensePage` ignora respuestas tardías, bloquea doble envío, reintenta el catálogo y muestra carga (4 tests RED→GREEN). Cierra G4 sólo en estados de reintento y robustez (hoy hay una única instancia; no se unificó). Melchor Romero, Pergamino (`HistoricalWalkthrough`), laboratorio mock (`useDemoSession`) y pronóstico (`ForecastPage`) ya tenían tests de carreras y de objetivo inmaduro; verificado por lectura, sin cambios | Persistencia de revisión tras recarga, permisos de acción por modo, capturas antes/después; no se unificó `CicytexDefensePage` sobre `HistoricalWalkthrough` |
| F6 Trazabilidad y arquitectura interactiva | 🟡 | #47: catálogo en código `architectureCatalog.ts`, versionado por git (rutas de evidencia verificadas por test), fichas por nodo y tabla textual, Laya como adaptador desactivado | Trazado interactivo de una predicción a su evidencia/linaje, si el alcance lo confirma |
| F7 Verificación integral | ⬜ | — | E2E, accesibilidad, teclado, contraste, movimiento reducido, backend desconectado, Laya apagada, capturas |
| F8 Paquete de defensa | ⬜ | — | Diagrama final, mapa antes/después, ADR, matriz de robustez, guion de demo, recuperación, limitaciones, preguntas y respuestas |

Changes OpenSpec: `add-architecture-view-and-mode-indicator` (#46), `add-architecture-node-catalog` (#47), `harden-cicytex-replay-operation` (#48).

## 2026-09-21 — Robustez de paginación operacional (HU5/HU6)

Corrección aislada desde main 2079d03: continuación por clave aunque la revisión
quite el ancla del filtro, cursores ligados al sensor y 422 para fechas invertidas.
Pruebas reproducen el fallo previo y verifican contadores/GET sin mutaciones.
Capacidades human-feedback/architecture-integration, CRISP-DM integración.
Sin cambios científicos, de arquitectura, modelos, manifiestos ni datasets;
worktrees de Claude y demo Docker preservados. Evidencia y compatibilidad:
[backend-producer-pagination-hardening.md](design/backend-producer-pagination-hardening.md).

## 2026-09-21 — Cierre acotado de integración para PR #207 (HU6)

Por aprobación explícita del autor se separa el merge funcional de Mi cultivo del
cierre completo de modelos operacionales. Se actualizan el informe de integración,
la descripción del contrato y las tareas para reflejar emisión y feedback ya
implementados. No se marcan completos assessments, gate, registro/activación MLflow,
resumen/recalibración v2 ni QA móvil/teclado pendiente. El change continúa abierto.

La revisión confirma opt-in v2 desactivado por defecto, ausencia explícita cuando
faltan bundles/datos y display_probability=null. La demo aprobada usa modelos y
datos sintéticos separados. No cambia código runtime ni resultados experimentales.
HU2/HU4/HU5/HU6/UI, CRISP-DM integración; sin impacto sobre hipótesis, arquitectura,
configuración HU7/HU8 o manifiestos. Validación estricta OpenSpec y diff registrados
en el cierre; CI del HEAD y ausencia de conflictos son condiciones para el merge.

## 2026-09-21 — Aceptación funcional y corrección del runner backend (HU6)

El usuario aprobó la prueba general de producer-preview; no se infiere validación
móvil/teclado específica ni evidencia predictiva. PR #207 seguía en borrador y
backend-quality fallaba al importar tests.test_operational_inference desde backend/.
Se agrega pythonpath raíz a pytest sin excluir tests ni modificar código runtime.
Validación: 101 tests backend aprobados desde backend/ en una copia temporal
escribible, imagen aai-producer-preview-backend:local y copia del fixture histórico
requerido por legacy. Intentos previos fallaron por dependencias de otra imagen,
montaje de solo lectura y fixture ausente; no eran evidencia de regresión funcional.
Git diff --check correcto; CI remoto debe ejecutarse nuevamente tras publicar.
HU6 / architecture-integration, CRISP-DM integración. Sin cambios experimentales,
a hipótesis, arquitectura, manifiestos ni resultados HU7/HU8. No se ejecutó la
evaluación operacional real. Detalle: docs/design/producer-ui-main-integration.md.

## 2026-09-21 — Docker local aislado para probar Mi cultivo (HU6)

HU2/HU4/HU5/HU6, capacidades data-ingestion, predictive-modeling, human-feedback,
architecture-integration y alerting-ui; CRISP-DM integración. Se agrega
compose.producer-preview.yml y docker/producer-preview/: preparación explícita
con fixtures sintéticos, dos sectores, tres sensores (uno vacío), bundles por
sensor, tandas históricas revisables y tandas futuras. Nginx sirve la UI compilada
y el proxy de API del mismo origen. No se ejecuta entrenamiento desde HTTP.

Proyecto aai-producer-preview, puertos loopback 5180/8180 y volumen independiente.
No se montan datos del repositorio ni se conectan los servicios MLflow/MinIO/Postgres
existentes. El marcador de preparación evita reentrenar o sobrescribir opiniones
al reiniciar; un volumen parcial no se sobrescribe silenciosamente.

Verificado: build de ambas imágenes, preparación exitosa, API y frontend saludables,
redirección a Mi cultivo, 30 días/3 horizontes/3 pendientes revisables por sensor,
estado vacío, documentación API y mismo conjunto de 6 emisiones tras reiniciar y
reejecutar prepare. Validación por HTTP real a través del proxy; no se declara
inspección visual de navegador. Sin porcentajes habilitados. Comandos y límites en
[docker/producer-preview/README.md](../docker/producer-preview/README.md).

No modifica configuración experimental, manifiestos congelados, hipótesis,
arquitectura ni resultados históricos. No es la corrida operacional real ni
registro científico MLflow. HU7/HU8 sin nueva evidencia. Aporte al capítulo 3:
entorno ejecutable de prueba funcional; PR #207 continúa en borrador.

## 2026-09-21 — Emisión v2 conectada a Mi cultivo (HU2/HU4/HU5/HU6)

Capacidades data-ingestion, predictive-modeling, human-feedback,
architecture-integration y alerting-ui; CRISP-DM despliegue/integración.
Se agrega carga verificada de bundles y predicción sin reajuste, POST de emisión
+1/+2/+3 con snapshot, persistencia atómica/replay HTTP y consulta explícita desde
Mi cultivo. Conserva fechas reales, fallos parciales, contratos de éxitos previos,
reserva demo y revisión humana. No modifica hipótesis ni arquitectura: el adaptador
local sobre los artefactos exportados es intermedio; registro/activación MLflow
continúa pendiente conforme a ADR-0013.

Verificación: frontend 136 tests + lint/build; datos/modelado afectados 97 tests;
backend completo 100 tests. Tras reforzar carga/contrato y diferir dependencias,
19 tests específicos (7 HTTP + 12 inferencia) nuevamente correctos. Dos changes
OpenSpec estrictos válidos, diff check limpio y Compose transmite bundle root.
Pruebas con modelos efectivamente ajustados sobre fixtures sintéticos. No se
entrenó con datos reales ni se abrió ningún holdout; manifiestos intactos.

Porcentajes siguen null hasta implementar el gate compatible de evidencia/rango.
Navegador pendiente por fallo de inicio del controlador (deny-read ACLs), sin
atribuir inspección visual a tests DOM. Persisten tareas de despliegue real,
assessment, resumen/recalibración y cierre integral del PR #207; no se declara
CI verde ni cierre científico HU7/HU8. Aporte a memoria: capítulo 3.
Detalle: [producer-ui-emission-integration.md](design/producer-ui-emission-integration.md).

## 2026-09-21 — Integración aislada UI/backend para productor (HU6)

HU2/HU4/HU5/HU6; capacidades data-ingestion, predictive-modeling,
human-feedback, architecture-integration y alerting-ui; CRISP-DM integración.
Se combinan main a657014, backend 2e22c6f y UI a250a9e sin tocar los worktrees
con desarrollo concurrente. Se corrigen selector legacy ajeno a Mi cultivo,
transmisión del flag v2 en Compose y estructura de la spec canónica
architecture-integration (tarea 1.12, sin cambio normativo).

Evidencia: 132 tests frontend, lint/build correctos, 94 tests backend, cuatro
changes y spec canónica de arquitectura válidos en modo estricto. El entorno
backend necesitó httpx2 y un cwd temporal escribible para MLflow. No se declara
CI verde, prueba visual integrada ni cierre funcional completo.

Pendientes de merge: orquestador concurrente publicado, emisión real +1/+2/+3,
evidencia y assessments, experiencia completa de productor, capacidades v2
abiertas y recorrido de navegador/móvil. Sin entrenamiento ni cambios a datos,
resultados históricos, hipótesis, configuración experimental o arquitectura.
HU7/HU8 no se dan por cerrados. Memoria: capítulo 3, evidencia de integración.
Detalle y condiciones de cierre: [producer-ui-main-integration.md](design/producer-ui-main-integration.md).

### Actualización de esta integración: orquestador e identidades congeladas

Se incorporó b573088 cuando la sesión concurrente terminó y publicó. Se ejecutaron
73 pruebas específicas del orquestador, CLI, motor y manifiestos sobre la rama
combinada. La primera ejecución falló en 6 verificaciones de identidad porque
el checkout Windows convirtió LF a CRLF; se corrigió con `.gitattributes` (`-text`
para manifiestos congelados y sidecars) y se restauraron exactamente los bytes
versionados, comprobando los hashes/longitudes existentes. Los JSON no cambiaron
respecto de Git. La segunda ejecución pasó 73/73. No hubo corrida real ni cambios
metodológicos. Sigue pendiente la conexión a emisión real, evidencia y UI completa.

## 2026-09-20 — Prerrequisitos de ejecución de controlled_daily_v4 (HU7/HU8)

Change `integrate-controlled-daily-v4-execution-prerequisites`, capacidad
`experiment-runner`, CRISP-DM preparación. Integra en `main` la versión vigente del
protocolo `controlled_daily_v4_external_pergamino`, las decisiones preejecución, la
guía de ejecución y el runner correspondiente, para satisfacer la **condición 4 de
ADR-0011** (el ADR y el protocolo detallado deben estar mergeados antes de cualquier
ejecución).

Corrección metodológica central: el protocolo en `main` afirmaba que el contrato de
features era el de `controlled_daily_v3` «sin modificación». Es falso contra la
implementación — v4 usa ocho features con valores actuales y derivaciones temporales
solo sobre humedad de suelo; v3 usa quince variables temporales sobre tres magnitudes
con `include_current=false`. Queda registrado que una diferencia v3→v4 no identifica
por sí sola un efecto de sitio, período o modelo.

Se incorporan además los pisos de soporte predeclarados (≥ 2 folds con MCC definido de
3; ≥ 80 % de réplicas bootstrap válidas), el tratamiento explícito de métricas
indefinidas y evaluaciones monoclase, las métricas de inicio de episodio y la custodia
del primer intento científico de la Etapa B. Ninguno de esos mínimos se relajó: todos
los cambios de criterio son estrictamente más exigentes (fallan cerrado).

Validación: suite completa `pytest` en verde, `ruff check src tests`,
`black --check src tests` y `git diff --check` sin hallazgos. Toda la verificación es
**exclusivamente sintética**.

**No constituye cierre científico.** A, B y C no se ejecutaron; el holdout 2024–2025
permanece cerrado; el ledger definitivo no se inicializó; no se incorporan resultados
experimentales. `controlled_daily_v3` y su evidencia congelada no se modifican. Los
runners complementarios (regresión, HITL, anomalías, robustez) siguen diseñados y no
implementados. Aporte a la memoria técnica: capítulo 2 (contrato de features real y
criterios de soporte predeclarados) y capítulo 3 (custodia y preflight de ejecución).

## 2026-09-19 — Primera entrega de catálogo e históricos para productor

HU2/HU6; `data-ingestion`, `architecture-integration` y `alerting-ui`;
CRISP-DM comprensión/preparación de datos y despliegue/integración. Implementados
catálogo persistente de sectores y sensores, adopción sin reescritura, selección
primaria, histórico UTC por snapshot SHA-256 y fachada aditiva `/api/v2` con
paginación, errores propios, OpenAPI y feature flag
`PRODUCER_V2_ENABLED`. Ver
[documentación de la entrega](design/backend-producer-ui-first-delivery.md).

Persistencia con reemplazo atómico y lock entre procesos; concurrencia,
revisiones optimistas, preservación byte a byte y compatibilidad legacy
verificadas en directorios temporales. Validación: 33 tests dirigidos de dominio,
18 de HTTP/sensores legacy, 21 de compatibilidad con escritores existentes,
suite backend completa 61, demo 56 passed/1 skipped. Ruff, Black, ambos changes
con `openspec validate --strict` y `git diff --check` pasan. OpenSpec mantiene
el aviso preexistente de estructura canónica registrado en la tarea 1.12.

ADR-0013 continúa propuesto y los cambios no se archivan. No se implementaron
modelado, calibración, porcentajes, feedback v2, UI ni autenticación. Sin cambios
en protocolos, datasets, resultados HU7/HU8, configuraciones experimentales,
hipótesis, alcance o arquitectura. Aporte a capítulo 3; capítulo 2 preserva
procedencia, faltantes y límites científicos.

## 2026-09-18 — Corrección de evidencia de calibración (solo specs)
HU4/HU6; predictive-modeling y architecture-integration; CRISP-DM modelado,
evaluación de desarrollo e integración. Se corrige el criterio de publicación:
Brier/log-loss no bastan; se exigen diagnósticos directos, incertidumbre temporal,
soporte, cobertura y tolerancias previas. API distingue motivos de no calificación.
No se ejecutaron experimentos ni se modificaron código, protocolos v3/v4,
configuraciones formales o resultados históricos HU7/HU8. Hipótesis, alcance
y arquitectura intactos. Documentación propuesta para capítulos 2 y 3.

## 2026-09-18 — Especificaciones de backend para UI de productor (propuesta)

Se proponen cuatro changes para HU2, HU4, HU5 y HU6, con ADR-0013 pendiente
de aprobación: catálogo/historial, pronósticos +1/+2/+3, feedback por emisión
y contrato API v2. Ver [plan y dependencias](design/backend-producer-ui-plan.md).
CRISP-DM: datos, modelado, evaluación de desarrollo e integración. Solo specs;
no se implementaron capacidades ni se completaron tareas de código.
Configuraciones base / +sintéticos / +anomalías / completa, protocolos formales,
resultados HU7/HU8, hipótesis y capas de arquitectura permanecen intactos.
Aporte futuro a capítulos 2 y 3: causalidad, límites de probabilidades y trazabilidad.

## 2026-09-17 — UI en lenguaje cotidiano (HU6/HU5)

Change `simplify-producer-ui`, capacidad `alerting-ui`, CRISP-DM despliegue e
integración experimental. Implementados textos orientados a productores/agrónomos,
detalle técnico secundario, guía de revisión y contador de resultados filtrados.
Las fechas y operaciones conservan el contrato actual. La evidencia y el linaje
permanecen accesibles. Sin cambios de arquitectura, hipótesis, configuración
experimental o resultados HU7/HU8. Aporte al capítulo 3: adecuación de presentación.

Validación: 68 tests frontend aprobados, `npm run lint` y `npm run build` exitosos.
Pruebas con mocks, sin escrituras de validaciones/recalibraciones en datos del usuario.
Inspección visual pendiente: el runtime de navegador no tiene browsers disponibles.
Comprensión por productores/agrónomos pendiente de revisión humana; no se declara
usabilidad validada solo por los tests. Datos locales y override Docker preservados.

Auditoría honesta del desglose de tareas técnicas del plan de tesis (sección 9 del plan de proyecto) contra lo que efectivamente existe en este repositorio a la fecha. No es autoevaluación optimista: cada tarea se marca según evidencia verificable (archivo, test, PR), no según intención.

Leyenda: ✅ Completado (cumple el criterio de aceptación de su HU) · 🟡 Parcial (hay artefacto real pero no cubre toda la tarea) · ⬜ No iniciado.

## Sprint 0 — Planificación

Ya estaba 100% completo antes de crear este repositorio: es el propio documento de planificación de tesis (acta de constitución, propósito/alcance, hipótesis, backlog, criterios de aceptación, CRISP-DM, cronograma). No cambia.

## HU1 — Estado del arte y comprensión del dominio (110 h planificadas)

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Definir el protocolo de revisión bibliográfica | ✅ | `docs/research/hu1-protocolo-revision-bibliografica.md` define objetivo/alcance, términos, cadenas de búsqueda, criterios y procedimiento de registro. |
| Definir términos, sinónimos y cadenas de búsqueda (ES/EN) | ✅ | Mismo documento, secciones 2 y 3, con cadenas adaptadas a Scopus, Web of Science, IEEE Xplore y AGRIS/SciELO/Horticultura Argentina. |
| Definir criterios de inclusión, exclusión y período de análisis | ✅ | Mismo documento, secciones 4 y 5 (período 2019–2026 con excepción para referencias seminales). |
| Ejecutar y registrar búsquedas en Scopus y Web of Science | 🟡 | Scopus: ejecutada y registrada para los 4 ejes (`docs/research/exports/scopus/`, consolidada en `docs/research/hu1-corpus-final.csv`; ver `docs/research/hu1-registro-busquedas.csv`). Web of Science: intentada (2026-09-05), no ejecutable — la cuenta institucional disponible permite búsqueda de perfiles de investigadores, pero no Document Search/Core Collection (ver `docs/research/hu1-protocolo-revision-bibliografica.md`, sección 3). |
| Ejecutar y registrar búsquedas en IEEE Xplore | ✅ | Ejecutada y registrada para los 4 ejes (`docs/research/exports/ieee/`, consolidada en `docs/research/hu1-corpus-final.csv`; ver `docs/research/hu1-registro-busquedas.csv`). |
| Buscar antecedentes agronómicos en AGRIS, SciELO y Horticultura Argentina | 🟡 | `docs/research/hu1-antecedentes-argentina.md` releva 4 antecedentes verificables en SciELO Argentina, Horticultura Argentina e INTA. AGRIS se intentó ejecutar de forma automatizada y quedó bloqueado por herramienta (SPA con JS, 403 en fetch, sin navegador disponible — ver nota en `docs/research/hu1-protocolo-revision-bibliografica.md`); requiere navegación manual, no scripting. |
| Revisar documentación técnica del INTA, FAO y organismos nacionales | 🟡 | Se relevó INTA RIAN, pero como fuente de **datos** (HU2), no como antecedente bibliográfico de estrés hídrico. |
| Consolidar referencias y eliminar registros duplicados | ✅ | `docs/research/hu1-corpus-final.csv` consolida 450 registros (Scopus, IEEE Xplore, Crossref, OpenAlex, DOAJ), deduplicados por DOI/título+año. La cola de revisión humana de 71 registros (`docs/research/hu1-cola-revision-humana.csv`) quedó resuelta (29 incluir, 30 excluir, 12 indeterminado, con motivo y trazabilidad histórica conservada, tras el control final de metadatos no verificables y la auditoría focalizada del eje 3 que reclasificó registros de augmentation convencional sin generación de datos sintéticos). Estado final del corpus: 180 incluidos, 256 excluidos, 14 indeterminados (permanentes, por metadatos insuficientes, no pendientes de resolución). |
| Evaluar títulos y resúmenes según criterios definidos | ✅ | Cribado semántico ejecutado por título y abstract sobre los 294 registros incluidos automáticamente, con clasificación de relevancia A/B/C, y resolución final de los 71 casos de la cola de revisión (incluir/excluir/indeterminado). Selección representativa de 25 referencias validada vía Crossref/DOI/editorial (`docs/research/hu1-referencias-representativas-validadas.csv`), con cobertura de los 4 ejes (6/5/9/5). |
| Analizar trabajos sobre modelado predictivo de estrés hídrico | ✅ | `docs/research/hu1-matriz-comparativa-final.md`, eje 1: 6 referencias representativas validadas, con síntesis de patrones, limitaciones e implicancias de diseño. |
| Analizar trabajos sobre detección de anomalías y datos sintéticos | ✅ | `docs/research/hu1-matriz-comparativa-final.md`: 5 referencias del eje 2 (detección de anomalías) y 9 del eje 3 (generación de datos sintéticos), tratados como ejes independientes, cada uno con síntesis propia. |
| Analizar trabajos sobre retroalimentación humana y recalibración | ✅ | `docs/research/hu1-matriz-comparativa-final.md`, eje 4: 5 referencias representativas validadas, con síntesis de patrones, limitaciones e implicancias de diseño. |
| Elaborar la matriz comparativa de antecedentes | ✅ | `docs/research/hu1-matriz-comparativa-final.md`: 25 referencias representativas validadas, organizadas por los 4 ejes, con síntesis por eje y síntesis de vacancia. Reemplaza la matriz preliminar de 8 filas. |
| Identificar vacancias y criterios para el diseño de la arquitectura | ✅ | Vacancia revalidada contra las 25 referencias (`docs/research/hu1-matriz-comparativa-final.md`, sección "Síntesis de vacancia"; `docs/research/hu1-estado-del-arte.md`, sección 4), distinguiendo integración controlada, escasez/variabilidad de datos y transferencia de técnicas desde otros dominios. Criterios de diseño ya incorporados en el esquema de `data-ingestion` y en `human-feedback`. |
| Redactar el estado del arte y el marco conceptual | ✅ | `docs/research/hu1-estado-del-arte.md`, versión definitiva (ya no preliminar): introducción, marco conceptual por eje, síntesis comparativa, vacancia revalidada, criterios de selección de técnicas, antecedentes regionales, limitaciones y conclusión. |
| Revisar trazabilidad de citas, antecedentes y decisiones metodológicas | ✅ | Revisión completa de los 5 documentos de HU1: se corrigió una atribución de autoría incorrecta (`hu1-estado-del-arte.md` citaba "Zhang et al., 2024" para la revisión de *Sensors*, cuyos autores reales son Cho et al., verificado por búsqueda); se reemplazaron 8 referencias posicionales frágiles ("ver misma referencia", "(arriba)") por citas autocontenidas con enlace propio; se verificó que las 24 referencias cruzadas entre documentos internos (`docs/research/`, `docs/adr/`) resuelven a archivos existentes; se verificaron las 19 URLs externas citadas (los 403 son protección anti-bot de las editoriales, no enlaces rotos — ya confirmados por búsqueda web). |

**Balance HU1 (actualizado 2026-09-06):** de 16 tareas, 13 completas, 3 parciales, 0 no iniciadas. Las 3 parciales corresponden a limitaciones de acceso documentadas, no a trabajo pendiente de ejecutar: Web of Science (sin acceso institucional a Document Search/Core Collection), AGRIS (interfaz no automatizable bajo el protocolo previsto) e INTA/FAO como antecedente bibliográfico de IA (la evidencia existente en el repositorio corresponde a fuente de datos e instrumentación, no a un antecedente de IA). El estado documental 🟡 de estas tres tareas individuales es independiente del cumplimiento de los criterios de aceptación de HU1: el entregable formal de HU1 (estado del arte redactado) existe en su versión definitiva (`docs/research/hu1-estado-del-arte.md`), respaldado por la matriz comparativa final de 25 referencias (`docs/research/hu1-matriz-comparativa-final.md`) y por la auditoría de cierre contra los criterios de aceptación del issue #10 (`docs/research/hu1-auditoria-cierre.md`). Los 4 criterios de aceptación del issue #10 quedan documentalmente satisfechos en estado **CUMPLE**. **HU1 cerrada**: el issue #10 y sus 12 issues hijos (#21 a #32) fueron cerrados en GitHub, cada uno con comentario de trazabilidad referenciando la evidencia documental y el PR #172 (#24 cerrado como `not_planned`, el resto como `completed`).

## HU2 — Preparación del conjunto experimental de datos (70 h planificadas)

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Definir variables agronómicas, climáticas y temporales requeridas | ✅ | `src/data_ingestion/schema.py` fija columnas obligatorias/opcionales, derivadas del borrador de HU1. |
| Identificar conjuntos de datos asociados a publicaciones científicas | ⬜ | No se hizo este relevamiento específico. Cerrado como `not_planned` (issue #35, CLOSED): no era necesario para satisfacer los criterios de aceptación de HU2, dado que ya existe un conjunto experimental real, reproducible y utilizado por las HUs posteriores obtenido por otras fuentes públicas. |
| Relevar datos disponibles en SMN, NASA POWER y Copernicus | 🟡 | Documentado en `docs/research/hu2-fuentes-datos-acceso.md`; **NASA POWER** tiene conector implementado, testeado y con descarga real ejecutada, incorporada al conjunto experimental; **SMN** relevado en profundidad y encontrado **bloqueado por acceso técnico** (dataset de datos.gob.ar removido, `smn.gob.ar/descarga-de-datos` con protección anti-bot — no es solo falta de registro, ver checklist); **Copernicus** relevado y pendiente por falta de registro del responsable del proyecto. "Relevar" no exige incorporar las tres fuentes; cerrado como `completed` con limitación documentada (issue #36, CLOSED). |
| Evaluar metadatos, licencias, procedencia y restricciones de uso | ✅ | Diccionarios de datos reales poblados para las fuentes seleccionadas, NASA POWER y ESA CCI Soil Moisture (`data/dictionaries/`, con licencia y limitaciones reales, no de ejemplo). SMN y Copernicus, al no estar incorporados, siguen documentados solo a nivel de checklist — nivel suficiente para fuentes no seleccionadas. Cerrado como `completed` (issue #37, CLOSED). |
| Descargar y organizar muestras representativas de las fuentes candidatas | ✅ | **Dos fuentes reales descargadas para el mismo punto y año** (Melchor Romero, -34.95/-58.05, Partido de La Plata, 2024): NASA POWER (`data/nasa_power_melchor_romero_2024.parquet`, 366 filas) y ESA CCI Soil Moisture (`data/esa_cci_soil_moisture_melchor_romero_2024.parquet`, 366 filas), ambas `origen: real`. |
| Homogeneizar formatos, unidades, frecuencias y zonas horarias | ✅ | `normalize_to_schema` + `consolidate_sources` (nuevo, `src/data_ingestion/consolidate.py`) combinan de verdad NASA POWER y ESA CCI en un único DataFrame por timestamp — ya no es solo mecanismo testeado con sintéticos, está validado con dos fuentes reales distintas. |
| Analizar cobertura temporal, granularidad e integridad de las fuentes | ✅ | `coverage.py` corrido sobre el dataset consolidado real (`data/melchor_romero_2024_consolidado_coverage.csv`): 100% en las 5 variables climáticas, **75.96% en humedad de suelo** (gaps reales del producto satelital, no un bug — días con celda enmascarada por nubes/vegetación densa), 0% en ET0 (columna obligatoria del esquema, no poblada por ninguna fuente incorporada ni derivada para este dataset; no se usa como predictor en HU7/HU8 — ver `docs/research/hu2-auditoria-cierre.md`, sección 4). |
| Definir criterios de selección y descarte de fuentes de datos | ✅ | `docs/research/hu2-fuentes-datos-acceso.md`, sección "Criterios de selección y descarte de fuentes de datos": 5 criterios de inclusión (aporte de variable obligatoria, cobertura geográfica verificada en el punto, accesibilidad técnica real, licencia, completitud suficiente) y 4 de descarte, informados por los hallazgos reales de esta sesión (SMN/AGRIS bloqueados pese a "sin registro", ESA CCI enmascarado en el punto original). |
| Implementar procedimiento reproducible de ingestión y consolidación | ✅ | `src/data_ingestion/ingest.py` (`run_ingestion`) + `src/data_ingestion/consolidate.py` (`consolidate_sources`) + `scripts/ingest_nasa_power.py` + `scripts/ingest_esa_cci_soil_moisture.py` + `scripts/consolidate_datasets.py` implementan el flujo completo (descarga → guardado → cobertura → diccionario → consolidación multi-fuente), testeado con inyección de dependencias y **ejecutado realmente de punta a punta**: `data/melchor_romero_2024_consolidado.parquet` es el primer conjunto experimental real y consolidado del proyecto. |
| Documentar diccionario de datos, procedencia y limitaciones | ✅ | Diccionarios reales generados para NASA POWER y ESA CCI (licencia y limitaciones reales, no de ejemplo). SMN/Copernicus siguen bloqueados (ver checklist), pero el mecanismo ya está probado con más de una fuente. |

**Balance HU2 (actualizado 2026-09-06):** de 10 tareas, 8 completas, 1 parcial (completada con limitación documentada), 1 no iniciada (cerrada como `not_planned`). Los cuatro criterios de aceptación de HU2 se encuentran satisfechos (CUMPLE en los cuatro, ver `docs/research/hu2-auditoria-cierre.md`): `data/melchor_romero_2024_consolidado.parquet` combina dos fuentes reales (NASA POWER + ESA CCI Soil Moisture) para Melchor Romero, 2024, con 6 de 7 variables obligatorias pobladas (falta ET0, columna obligatoria del esquema no poblada ni usada como predictor de HU7/HU8), y fue efectivamente utilizado por HU3-HU8. #35 no fue ejecutado porque la estrategia de obtención de datos mediante fuentes públicas seleccionadas ya produjo un conjunto experimental real, reproducible y utilizado por las HUs posteriores; fue cerrado como `not_planned`. #36 fue cerrado como `completed` con limitación documentada y #37 como `completed`. Limitaciones que se preservan documentadas: un solo punto geográfico y un solo año; SMN bloqueado por acceso técnico; Copernicus pendiente de registro/cuenta personal gratuita; humedad de suelo con 75.96% de cobertura (tratamiento correspondiente a HU3, ya implementado allí). Todos los issues hijos (#34 a #43) están cerrados y el issue principal #11 fue cerrado como `completed`. **HU2 está formalmente cerrada.**

## HU3 — Componente de calidad y robustez de datos

HU3 se dividió en tres *changes* de OpenSpec independientes (calidad/limpieza básica, detección de anomalías, generación de datos sintéticos), más integración y documentación. Este es el primero.

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Analizar distribuciones, rangos y tipos de las variables | ✅ | `src/data_quality/distributions.py` (`describe_variables`), verificado sobre `data/melchor_romero_2024_consolidado.parquet`. |
| Definir reglas de calidad y rangos agronómicos esperados | ✅ | `src/data_quality/rules.py` (`AGRONOMIC_RANGES`), rangos físicos/climáticos genéricos con justificación por variable. |
| Implementar el reporte de valores faltantes, duplicados y atípicos | ✅ | `src/data_quality/quality_report.py`; sobre el dataset real: 24.04% de faltantes en humedad de suelo, 0 duplicados, 0 valores fuera de rango. |
| Implementar el tratamiento de valores faltantes | ✅ | `src/data_quality/imputation.py` (`interpolate_missing`); imputó 88 de 366 filas de humedad de suelo en el dataset real, dejando 0 faltantes. |
| Implementar normalización, codificación y alineación temporal | ✅ | `src/data_quality/scaling.py` (`standardize`/`inverse_standardize`), roundtrip exacto verificado sobre el dataset real. Interpretada como estandarización numérica para modelado, ya que la alineación de formato/zona horaria entre fuentes la resuelve `data-ingestion` (HU2). |
| Preparar particiones sin contaminación entre entrenamiento y evaluación | ✅ | `src/data_quality/splitting.py` (`temporal_train_test_split`), verificado sobre el dataset real (274 filas de entrenamiento / 92 de evaluación, sin fechas mezcladas). |
| Seleccionar métodos candidatos para detección de anomalías | ✅ | Isolation Forest (scikit-learn) seleccionado como método base no supervisado — no hay etiquetas de anomalía disponibles (confirmado en antecedentes de HU1). Justificación y alternativas en `openspec/changes/add-anomaly-detection/proposal.md`. |
| Implementar el método base de detección de anomalías | ✅ | `src/data_quality/anomaly_detection.py` (`detect_anomalies`). |
| Evaluar el comportamiento del detector de anomalías | ✅ | `evaluate_with_injected_anomalies`; sobre el dataset real: 100% de detección de 10 anomalías sintéticas inyectadas, y sobre los datos sin modificar marcó 19/366 filas (~5.2%) correspondientes a una ola de calor y eventos de lluvia intensa reales, ninguna fuera del rango físico ya validado por `quality_report`. |
| Seleccionar técnicas candidatas para generación de datos sintéticos | ✅ | Muestreo de distribución normal multivariada seleccionado como técnica base; GAN/VAE descartado para este prototipo (no definitivamente) por el tamaño del dataset disponible (366 filas). Justificación en `openspec/changes/add-synthetic-data-generation/proposal.md`. |
| Implementar un prototipo de generación de datos sintéticos | ✅ | `src/data_quality/synthetic_data.py` (`generate_synthetic`), marca `origen: sintetico` conforme al esquema de `data-ingestion`. |
| Evaluar similitud estadística y utilidad predictiva de los datos sintéticos | ✅ | `statistical_similarity` y `evaluate_predictive_utility`; sobre el dataset real: diferencia de correlación promedio 0.023 entre real y sintético; utilidad predictiva casi idéntica (MAE real 0.02312 vs. MAE sintético 0.02323 al predecir humedad de suelo desde variables climáticas, evaluado sobre el mismo test real). |
| Integrar las transformaciones en un flujo reproducible | ✅ | `src/data_quality/pipeline.py` (`run_quality_pipeline`) + `scripts/run_data_quality_pipeline.py`. Verificado sobre el dataset real en las 4 configuraciones de la Épica 4 (base, +sintéticos, +anomalías, completa), sin fuga de información entre entrenamiento y evaluación (parámetros de escalado ajustados solo sobre el conjunto de entrenamiento). |
| Documentar decisiones, parámetros y limitaciones del componente | ✅ | `openspec/specs/data-quality/spec.md` consolida las decisiones, parámetros y limitaciones de los 4 *changes* de HU3 en un único documento vigente, con notas de verificación real por requirement. |

**Balance HU3:** de 14 tareas, 14 completas, 0 parciales, 0 no iniciadas. **HU3 queda completa**: los tres sub-proyectos (calidad básica, detección de anomalías, datos sintéticos) y su integración en un flujo reproducible y parametrizable por configuración experimental están implementados y verificados sobre datos reales.

**Revalidación posterior al cierre (2026-09-06):** HU3 permanece formalmente cerrada (issue #12 y sus 14 issues hijos, #44-#57, CLOSED / completed). El cierre fue revalidado contra el código y las specs vigentes, no solo contra la evidencia histórica de los PR originales, dado que hubo correcciones metodológicas posteriores al cierre (imputación causal, integración real de `is_anomaly`, separación fit/apply del detector de anomalías ajustado solo sobre entrenamiento, prevención de fuga temporal, purga de frontera de horizonte). Los cuatro criterios de aceptación (CA1-CA4) permanecen en estado CUMPLE y no se detectaron gaps técnicos bloqueantes. Las limitaciones del detector de anomalías (evaluado solo con anomalías sintéticas extremas, sin etiquetas reales) y del generador sintético (sin restricciones físicas posteriores al muestreo) permanecen explícitamente documentadas, sin convertirse en trabajo pendiente. Ver `docs/research/hu3-auditoria-revalidacion.md`.

## HU4 — Componente de modelado predictivo

HU4 se dividió en tres *changes* de OpenSpec independientes (definición del problema/ingeniería de variables, modelos base/candidatos, alertas tempranas), mismo criterio que HU3. Los tres ya están implementados — HU4 completa.

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Definir la variable objetivo y el horizonte de anticipación | ✅ | Clasificación binaria (estrés sí/no), horizonte 3 días, umbral relativo (percentil 20 de humedad de suelo observada). Justificación en `openspec/changes/add-feature-engineering/proposal.md`. |
| Identificar variables predictoras, retardos y ventanas temporales | ✅ | Variables climáticas + humedad de suelo, retardos 1/2/3 días, ventanas móviles 3/7 días. |
| Implementar la ingeniería de variables temporales y agronómicas | ✅ | `src/predictive_modeling/labeling.py`, `src/predictive_modeling/feature_engineering.py`. |
| Evaluar relevancia de variables y posibles fugas de información | ✅ | `src/predictive_modeling/relevance.py`; test explícito de no-fuga (`tests/test_no_leakage.py`). Sobre datos reales: 363/366 filas etiquetadas (19.6% estrés), variables más correlacionadas con sentido físico (radiación solar +0.51, humedad relativa/suelo -0.46 a -0.48). |
| Definir modelos de referencia y modelos candidatos | ✅ | `src/predictive_modeling/models.py::build_candidate_models` (regresión logística + Random Forest) y `predict_persistence_baseline`; `tests/test_models.py`. |
| Implementar el modelo de referencia | ✅ | `predict_persistence_baseline`; sobre datos reales (72 filas de test): precisión 0.500, recall 0.474, F1 0.486. |
| Implementar el flujo de entrenamiento para los modelos candidatos | ✅ | `src/predictive_modeling/training.py::train_models`; `tests/test_training.py`. |
| Implementar el esquema de validación temporal o cruzada | ✅ | `tune_hyperparameters` con `TimeSeriesSplit` (scikit-learn). |
| Ejecutar el entrenamiento inicial de los modelos candidatos | ✅ | Verificado sobre `data/melchor_romero_2024_consolidado.parquet`: 285 filas de entrenamiento, 72 de test. |
| Ejecutar el ajuste de hiperparámetros | ✅ | Mejores parámetros reales: regresión logística `C=0.1`; Random Forest `max_depth=5, n_estimators=100`. |
| Comparar desempeño, estabilidad y complejidad de los modelos | ✅ | `src/predictive_modeling/evaluation.py::compare_models`; `tests/test_evaluation.py`. Resultado real: persistencia F1=0.486, regresión logística F1=0.406 (ROC-AUC 0.533), Random Forest F1=0.475 (ROC-AUC 0.554). Ningún candidato supera claramente al baseline en F1 (ver spec, "Limitaciones conocidas"). |
| Definir e implementar la lógica de generación de alertas tempranas | ✅ | `src/predictive_modeling/alerts.py::generate_alerts` (umbral 0.5 sobre `predict_proba` del Random Forest ajustado); `tests/test_alerts.py`. Sobre datos reales: 21 alertas de 72 filas de test. |
| Analizar errores de predicción y alertas incorrectas | ✅ | `src/predictive_modeling/alerts.py::analyze_prediction_errors`; `tests/test_alerts.py`. Sobre datos reales: 7 falsos positivos, 24 falsos negativos, con fechas concretas listadas en el spec. |
| Documentar configuración, métricas y limitaciones del modelo | ✅ | `openspec/specs/predictive-modeling/spec.md` — requirements de alertas + tabla de configuración + "Limitaciones conocidas" (umbral no calibrado, recall bajo con este umbral). |

**Balance HU4:** de 14 tareas, 14 completas, 0 parciales, 0 no iniciadas. HU4 completa.

**Revalidación posterior al cierre (2026-09-06):** el issue #13 y sus 14 issues hijos (#58-#71) continúan CLOSED / completed. CA1-CA4 permanecen en estado CUMPLE. No existen gaps técnicos bloqueantes ni se detectó selección post hoc (Random Forest, umbral de estrés, `alert_threshold`, horizonte, features, folds o hiperparámetros elegidos por desempeño de test). Target, umbral, validación temporal y selección automática de modelo fueron revalidados contra el código vigente. Los ejemplos cuantitativos históricos de `openspec/specs/predictive-modeling/spec.md` (285/72 filas, hiperparámetros `C=0.1`/`max_depth=5`/`n_estimators=100`, tabla comparativa, y la descripción de la selección de Random Forest) fueron distinguidos explícitamente del mecanismo formal vigente (`select_best_candidate`, `controlled_daily_v3`), sin modificar ningún requirement. Las limitaciones (dataset de un único sitio/año, umbral relativo no calibrado agronómicamente, muestra reducida, correlación lineal simple para relevancia, umbral de alerta no calibrado) permanecen documentadas. Ver `docs/research/hu4-auditoria-revalidacion.md`.

## HU5 — Mecanismo de retroalimentación humana

HU5 se dividió en tres *changes* de OpenSpec independientes (modelo de datos, registro persistente e integración con predicciones, recalibración supervisada), mismo criterio que HU3/HU4. Los tres ya están implementados — HU5 completa.

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Definir casos de uso y estados de validación de las alertas | ✅ | Estados `pendiente`/`confirmada`/`rechazada` (`src/human_feedback/schema.py::VALIDATION_STATES`); justificación en `openspec/changes/add-feedback-data-model/proposal.md`. |
| Diseñar el modelo de datos para registrar retroalimentación | ✅ | `src/human_feedback/schema.py::FEEDBACK_COLUMNS`, `init_feedback_log`; `tests/test_feedback_schema.py`. |
| Diseñar el flujo de interacción entre alerta, usuario y modelo | ✅ | `update_feedback` (confirmar/rechazar con corrección y observación opcionales). Verificado sobre las alertas reales de HU4: registro de 72 filas inicializado en `pendiente`, una confirmada, un falso negativo real (2024-10-18) rechazado con corrección y observación. |
| Implementar el registro de validaciones de alertas | ✅ | `src/human_feedback/registry.py::save_feedback_log`/`load_feedback_log` (reutiliza `data_ingestion.storage`); `tests/test_feedback_registry.py`. Verificado sobre datos reales: guardado y recuperado sin pérdida de información. |
| Implementar el registro de correcciones y observaciones | ✅ | `upsert_feedback_log` (agrega fechas nuevas en `pendiente`, preserva estado/corrección/observación de fechas existentes). Verificado sobre datos reales: la fecha ya confirmada conservó su estado tras simular una nueva corrida de alertas. |
| Integrar la retroalimentación con los registros de predicción | ✅ | `integrate_feedback_with_predictions` (join por fecha con probabilidad predicha y etiqueta real). Verificado sobre datos reales: 72 filas integradas con `y_proba` y `stress_label` del modelo Random Forest de HU4. |
| Definir reglas para seleccionar observaciones de recalibración | ✅ | `src/human_feedback/recalibration.py::select_recalibration_observations` (solo `rechazada` con `etiqueta_corregida` no nula). Tests: `tests/test_recalibration.py`. |
| Implementar una prueba de recalibración supervisada | ✅ | `recalibrate_model` (reemplaza etiquetas por las corregidas y reentrena). Verificado sobre el dataset real con 3 correcciones sintéticas inyectadas: el modelo recalibrado predice distinto exactamente en esas 3 fechas (1,1,0 → 0,0,1, coincidiendo con la corrección). |

**Balance HU5:** de 8 tareas, 8 completas, 0 parciales, 0 no iniciadas. HU5 completa.

**Revalidación posterior al cierre (2026-09-06):** el issue #14 y sus 8 issues hijos (#72-#79) continúan CLOSED / completed. CA1-CA4 permanecen en estado CUMPLE. No hay gaps técnicos bloqueantes ni se detectó contaminación del holdout. `recalibrate_predictor` agrega garantías temporales (maduración del target, validación posterior a esa maduración, avance monótono de `trained_through`) al mecanismo original (`recalibrate_model`), sin reemplazarlo. `openspec/specs/human-feedback/spec.md` y ADR-0006 fueron sincronizados para documentar formalmente ese mecanismo ya implementado. La prueba de recalibración existente (correcciones sintéticas inyectadas) es evidencia funcional/de integración, no evidencia de mejora predictiva real; la evaluación cuantitativa formal del aporte de la retroalimentación humana (Human-in-the-Loop) continúa diseñada pero no ejecutada, separada de este cierre. Ver `docs/research/hu5-auditoria-revalidacion.md`.

## HU6 — Integración de la arquitectura experimental

HU6 se dividió en dos *changes* de OpenSpec independientes (contratos entre componentes y orquestador de punta a punta; configuración de ejecución completa, pruebas funcionales y ajustes de integración). Los dos ya están implementados — HU6 completa.

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Definir contratos, entradas y salidas entre componentes | ✅ | `openspec/specs/architecture-integration/spec.md`; orden de etapas documentado en `src/architecture_integration/pipeline.py`. |
| Integrar el componente de calidad con el componente predictivo | ✅ | `run_end_to_end_pipeline` encadena `data-quality` (imputación, anomalías) con `predictive-modeling` (etiquetado, variables, entrenamiento), evitando fuga temporal. `tests/test_architecture_integration_pipeline.py`. |
| Integrar las alertas con el mecanismo de retroalimentación | ✅ | El orquestador genera alertas y las pasa a `human_feedback.schema.init_feedback_log`. Verificado sobre el dataset real: 286 filas de entrenamiento, 71 de test, 0 NaN en variables predictoras del test, 22 alertas, 71 filas de feedback `pendiente`. |
| Configurar la ejecución completa de la arquitectura | ✅ | `scripts/run_end_to_end_pipeline.py` (misma convención que `scripts/run_data_quality_pipeline.py`). Verificado sobre el dataset real: 286 filas de entrenamiento, 71 de evaluación, 22 alertas, 71 filas `pendiente`, 15 anómalas — coincide con la verificación anterior. |
| Ejecutar pruebas funcionales de integración | ✅ | `tests/test_architecture_integration_functional.py`: valores faltantes intercalados se interpolan correctamente, desactivar anomalías omite `is_anomaly`, resultado consistente entre train/test/feedback. 3 pruebas, todas pasaron sin ajustes al orquestador. |
| Resolver incidencias y documentar los ajustes de integración | ✅ | Única incidencia: orden de imports en `scripts/run_end_to_end_pipeline.py` (detectado por `ruff`), corregido. Ningún ajuste necesario en el orquestador — las pruebas funcionales confirmaron el diseño del primer *change*. |

**Balance HU6:** de 6 tareas, 6 completas, 0 parciales, 0 no iniciadas. HU6 completa.

**Revalidación posterior al cierre (2026-09-06):** el issue #15 y sus 6 issues hijos (#80-#85) continúan CLOSED / completed. CA1-CA4 permanecen en estado CUMPLE. No existen gaps técnicos bloqueantes: arquitectura core, operativa (backend/UI) y experimental revalidadas contra el código vigente; frontend y API multi-sensor confirmados compatibles entre sí (ver actualización de la fila "Ingesta multi-sensor en paralelo" más arriba); la ruptura introducida originalmente por PR #163 quedó resuelta posteriormente. La UI usa actualmente un contrato Random Forest explícito como decisión operativa (para no depender de que la selección automática pueda evaluar folds degenerados); la selección automática permanece disponible en el núcleo experimental y es la que usa el protocolo formal `controlled_daily_v3`. El campo `model_version` del registro de retroalimentación almacena `model_id` (identificador del predictor), no una versión de MLflow — comportamiento correcto, nomenclatura aclarada en `openspec/specs/human-feedback/spec.md`. El CLI de HU6 (`scripts/run_end_to_end_pipeline.py`) no pudo reejecutarse en esta auditoría por falta de un intérprete Python en el entorno, pero no se detectó ninguna incompatibilidad por inspección de código; esto no constituye trabajo bloqueante. Ver `docs/research/hu6-auditoria-revalidacion.md`.

**Demostración dinámica acelerada (`openspec/changes/add-accelerated-sensor-demo/`, 2026-09-17):** capacidad nueva, no parte del balance 6/6 anterior. ADR-0012 (controlador local opcional) aceptado vía PR #201, solo como decisión de arquitectura. Entrega 1 (preparación y worker CLI, `scripts/demo_simulation/`) implementada y verificada: `prepare` genera un sensor exclusivo `demo-<id>` con historial sintético previo al período a reproducir y manifiesto atómico; `run` ejecuta la secuencia ingesta→verificación→pronóstico→confirmación un día calendario por paso contra el backend real, deteniéndose (`status=blocked`) ante cualquier fallo o resultado no confirmable, sin reintentar POSTs ni interpretar un timeout como cancelación. 37 tests contra un backend real (`uvicorn` en un hilo, HTTP real, sin `TestClient`) y registro MLflow aislado (sqlite en directorio temporal).

Entrega 2 (control local y recuperación, PR propio contra `main`, 2026-09-17) implementada y verificada: lock de proceso (`scripts/demo_simulation/lock.py`, `fcntl`/`msvcrt`, se libera solo si el proceso muere) impide dos workers simultáneos sobre la misma sesión, tanto entre dos instancias del adaptador HTTP como entre este y la CLI de ejecución directa (`run`) de la entrega 1. Máquina de estados persistida (`pausing`/`paused` agregados al manifiesto) con revisión monotónica y deduplicación de órdenes por `request_id` (`scripts/demo_simulation/control.py`): una orden repetida devuelve el resultado ya registrado sin lanzar un segundo worker; una revisión obsoleta o una transición inválida se rechazan con 409 explícito, nunca en silencio. Adaptador HTTP local (`scripts/demo_simulation/service.py`, FastAPI, perfil Docker opcional `demo`): `GET /demo/session` puramente de lectura, `POST start/pause/resume` con validación de `Origin` y CORS restringido por variable de entorno del proceso — el `backend_url` fijado por `prepare` no puede reconfigurarse desde una orden HTTP. Pausa resuelta al completar el paso en curso (nunca cancela un POST en vuelo) y continuación tras un reinicio siempre explícita, nunca automática (`scripts/demo_simulation/recovery.py::diagnose_and_recover`, invocada al levantar `serve` y dentro de `resume` sobre una sesión `blocked`): la ingesta se considera segura de reintentar por su semántica de reemplazo por día; el pronóstico, no idempotente, solo se reconcilia por lectura (`GET /feedback`) y bloquea con motivo diagnosticable si no puede confirmarse, sin reenviar nunca el POST. Se detectan también cambios externos al dataset de la sesión (ingeridos por fuera del worker) y se bloquea sin sobrescribir ni borrar nada. El mismo lock de proceso que evita que el worker de fondo y una orden HTTP escriban el manifiesto al mismo tiempo (necesario para que una pausa nunca se revierta en silencio por una escritura concurrente) hace que una orden repetida o de control coincidente con un paso en curso espere hasta que ese paso termine antes de responder (`GET` no se ve afectado). 19 tests nuevos (`tests/demo_simulation/test_control.py`, `tests/demo_simulation/test_service.py`; 1 marcado `skip` por una condición de temporización de borde, documentada en `scripts/demo_simulation/README.md`), más los 37 de la entrega 1 (total 56 pasan, 1 skip). Todos contra el mismo backend real y MLflow aislado que la entrega 1; ninguno usa datos ni modelos reales del usuario. `ruff`/`black` limpios sobre `scripts/demo_simulation` y `tests/demo_simulation`. Perfil Docker `demo` (`docker-compose.yml`, `docker/demo-control/Dockerfile`) verificado por construcción de imagen y validación de configuración de Compose (con y sin el perfil activo, para confirmar que no interfiere con el arranque normal); no se verificó end-to-end con el stack completo en contenedores. No se modificó `docker-compose.override.yml`. Entregas 3-4 (UI, verificación integrada) pendientes.

Entrega 3 (UI de demostración, PR propio contra `main`, 2026-09-17) implementada y verificada: vista secundaria `frontend/src/features/demo/DemoPage.tsx`, accesible por un enlace propio (`#demo`) fuera del ruteo principal de destinos, visible solo si `VITE_DEMO_CONTROL_BASE_URL` está configurada (`frontend/src/api/demoControlUrl.ts`) — sin esa variable, la aplicación funciona exactamente igual que antes, sin consultar nunca al controlador. Rótulo permanente "Demostración con datos simulados", sensor/día simulado/progreso y controles Iniciar/Pausar/Continuar habilitados según la transición vigente (`_TRANSITIONS` del contrato real de la entrega 2); ninguna acción de la UI prepara ni crea sesiones, solo consume `GET/POST /demo/session*` ya implementados. `useDemoSession` (`frontend/src/features/demo/useDemoSession.ts`) hace polling GET cada 2 segundos sin solicitudes superpuestas (guardado por una referencia en vuelo), reconsulta de inmediato al volver a la pestaña (`visibilitychange`) y nunca interpreta un GET fallido como pausa: muestra "No se pudo consultar el estado; la demostración podría seguir en marcha" preservando el último progreso confirmado. Un `request_id` nuevo por click y el bloqueo del botón mientras hay una orden en vuelo evitan un doble POST por doble clic (la deduplicación real, no obstante, sigue siendo la del controlador). Bloqueo de mutaciones manuales (`frontend/src/features/demo/lock.ts`): mientras la sesión del sensor activo no está `completed`, "Generar pronóstico" (Resumen), "Confirmar"/"Corregir resultado" (Historial y observaciones) y "Aplicar observaciones" (Ajustar próximos pronósticos) quedan deshabilitados con una explicación; al completarse, confirmar/corregir solo se ofrece para filas cuya fecha objetivo ya esté dentro del período ingerido por la demo y haya terminado en UTC real — la autoridad final sigue siendo el backend (409/procedencia/maduración sin cambios). Historial y calidad del sensor de demo se refrescan por GET (`QualityPanel`/`ResumenView` reciben un `refreshToken`) solo cuando avanza la fecha de ingesta o pronóstico confirmada, nunca por el simple paso del tiempo. Tests: 27 nuevos en frontend (`demoControlUrl.test.ts`, `features/demo/{api,lock,DemoPage}.test.ts(x)`, `App.demo.test.tsx`) más los 65 preexistentes (total 92) — `npm test`, `npm run lint` (`oxlint`) y `npm run build` (`tsc -b && vite build`) en verde. Verificación manual en navegador real: sin controlador configurado (enlace ausente, sin requests), con controlador configurado pero sin servicio (mensaje de desconexión sin afirmar pausa) y contra el contrato real de la entrega 2 (backend + `demo-control` reales vía Docker Compose, sesión `demo-60b4f4be13` descartada al finalizar): Iniciar, doble clic sin doble orden, y un bloqueo real del backend (mismatch de filas del dataset tras ingesta, ajeno a esta entrega) mostrado y sostenido correctamente por la UI a través de `Continuar`. Verificación de escritorio únicamente; no se probaron formalmente viewport móvil ni navegación exclusivamente por teclado en esta sesión (Chrome disponible pero sesión sin captura de esa evidencia específica). No se tocaron specs canónicas de `openspec/specs/` (la consolidación sigue en la tarea 4.5, entrega 4); no se avanzó la entrega 4.

**Corrección (entrega 4, 2026-09-18):** el "bloqueo real del backend" citado arriba (mismatch de filas tras ingerir) no era un defecto del backend ni de las entregas 1/2: se debía a que el montaje manual `-v "$(pwd)/data:/workspace/data"` usado para preparar esa sesión desde Git Bash en Windows quedaba corrompido por la conversión automática de rutas de MSYS, dejando el historial preparado fuera del volumen real que ve el backend. Con `MSYS_NO_PATHCONV=1` (o, mejor, declarando el volumen directamente en `docker-compose.yml`, ver más abajo) el backend ve el historial completo y no hay bloqueo. Se corrige acá para no dejar una atribución incorrecta en el registro; el hallazgo real (`demo-control` no montaba `./data`) se documenta en la entrega 4.

Entrega 4 (verificación y documentación, PR propio contra `main`, 2026-09-18) implementada y verificada — **las 4 entregas del change quedan completas.** Validación automatizada: `pytest -q` en la raíz (incluye `tests/demo_simulation`) — 783 passed, 3 skipped, dentro de un contenedor `python:3.11-slim` con `pip install -e ".[dev,backend]"` (sin intérprete Python local disponible en el entorno); `cd backend && python -m pytest -q` — 50 passed; `ruff check`/`black --check` sobre `src tests`, `scripts/demo_simulation tests/demo_simulation` y `backend/app` — limpios; frontend `npm test` (92 passed), `npm run lint` (oxlint, limpio), `npm run build` (`tsc -b && vite build`, limpio).

Verificación integrada contra Docker Compose real (backend/MLflow/frontend ya corridos por el usuario; `demo-control` levantado para esta verificación), cinco sesiones de demostración creadas y conservadas como evidencia (`data/`/`demo_sessions/`, excluidos de Git, sin tocar `sensor-a` ni datos del usuario): (1) `demo-be97e84561` (5 días, semilla 42, intervalo 3s) completada de punta a punta vía la UI real; verificado por `GET /feedback`/`GET /quality` cinco fechas consecutivas sin duplicados; revisión humana manual real sobre la fila `2026-01-01` (objetivo `2026-01-04`, dentro del período ingerido y terminado en UTC) — `estado_validacion` pasó a `confirmada` por el endpoint real; de las cinco filas, solo las dos con objetivo dentro del período ingerido ofrecieron Confirmar/Corregir, las otras tres mostraron "Todavía no hay una observación disponible", confirmando el gateo por fecha objetivo. (2) `demo-d8a94926ce` (mismos parámetros, intervalo 20s) usada para el ciclo real de pausa/continuación: Iniciar → estado "En ejecución" (1/5) → Pausar mientras el paso corría → "Pausa solicitada — terminando el paso actual" → terminó ese paso sin iniciar el siguiente (1/5, un único registro de pronóstico) → "Pausada" → Continuar → retomó desde el día 2 hasta completar 5/5, sin duplicar registros; también se observó y documentó un 409 real de "revisión obsoleta" cuando el worker avanzó su propia revisión entre el último `GET` de la UI y el clic de pausa — la UI mostró el motivo exacto sin fingir la pausa. Se confirmó además que cambiar de sensor activo a `sensor-a` (sin escribir nada en él) y volver no afecta ni duplica el worker de la demo. (3) `demo-139b36b992` (2 días) y (4) `demo-aaf5c81e7f` (2 días) usadas para verificar, respectivamente, el bloqueo de mutaciones manuales durante la reproducción ("Generar pronóstico" deshabilitado con "Esta sesión de demostración está en curso...") y que cerrar la pestaña del navegador no pausa el worker (confirmado con la sesión completándose vía `curl` mientras la pestaña estaba cerrada). (5) `demo-ae84b66085` (1 día) usada para confirmar activación por teclado (`Tab` hasta el botón "Iniciar", `Enter` lo activa igual que un clic) y, junto con los logs de acceso de `demo-control`, que solo hubo un `POST` por cada acción explícita entre 25 `GET`, ninguno por navegar o refrescar. Controlador ausente (sin `VITE_DEMO_CONTROL_BASE_URL`): sin enlace "Demostración", sin ningún request al controlador. Controlador configurado pero caído: "No se pudo consultar el estado; la demostración podría seguir en marcha", sin afirmar pausa; recuperación inmediata confirmada tanto al restablecer el servicio como al simular `visibilitychange`. App normal del usuario (contenedor `frontend` dockerizado, sin perfil `demo`): confirmada funcionando sin cambios.

**Defecto encontrado y corregido:** el servicio `demo-control` de `docker-compose.yml` no montaba `./data`, por lo que `prepare` invocado vía `docker compose --profile demo run --rm demo-control prepare ...` (el flujo documentado en el README) escribía el historial sintético en un directorio efímero del contenedor, invisible para el backend real — la sesión quedaba `blocked` tras el primer paso con un mensaje de fila faltante, indistinguible a simple vista de un defecto de `prepare`/`worker`. Corregido agregando `./data:/workspace/data` al servicio; no afecta al comando por defecto (`serve`), que sigue sin necesitar lectura directa de archivos. Verificado el flujo documentado del README de punta a punta tras el fix, sin ningún workaround manual.

**Verificación pendiente, declarada explícitamente:** viewport móvil real. La herramienta de automatización de navegador disponible en esta sesión no pudo redimensionar la resolución real (fija en 1280×800 pese a múltiples intentos con `resize_window`); se hizo una aproximación con un contenedor angosto de 390px inyectado por CSS (no dispara los `@media` reales de la hoja de estilos), que no mostró desbordes ni recortes en la vista de demostración ni en la navegación principal, pero no reemplaza una verificación en dispositivo o navegador con redimensionado genuino.

Documentación actualizada: `openspec/specs/demo-simulation/spec.md` (nueva spec canónica, consolida las 4 entregas), `openspec/specs/alerting-ui/spec.md` (tres requirements de UI de demostración agregados, con la limitación de viewport móvil declarada), `scripts/demo_simulation/README.md` (alcance completo, corrección del volumen Docker, sección "Verificación integrada" con los comandos exactos para reproducir el recorrido), `openspec/changes/add-accelerated-sensor-demo/tasks.md` (4.1-4.5 y checklist de cierre marcados con evidencia). Sin impacto en HU7/HU8, protocolo experimental `controlled_daily_v3`, aumento sintético HU3 ni resultados históricos; no se modificó ninguna configuración experimental. **HU6 — demostración dinámica acelerada: change completo**, con el único punto pendiente declarado (viewport móvil real) documentado en los tres lugares citados arriba.

## HU7 — Diseño y ejecución del plan experimental

HU7 se dividió en tres *changes* de OpenSpec independientes (diseño experimental, procedimiento automatizado con registro en MLflow, ejecución real de los experimentos). Los tres ya están implementados — HU7 completa.

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Definir preguntas experimentales y factores de evaluación | ✅ | `openspec/changes/add-experiment-design/proposal.md`: ¿aporta la detección de anomalías? ¿aportan los datos sintéticos combinados con las variables de HU4? |
| Definir escenarios de escasez, ruido y variabilidad de datos | ✅ | Escasez = subconjunto del entrenamiento real; variabilidad = 5 semillas por configuración; ruido fuera de alcance (sin caracterización real disponible). |
| Definir configuraciones comparativas y pruebas de ablación | ✅ | Las 4 configuraciones de la Épica 4 (base/+sintéticos/+anomalías/completa). **Bloqueo de HU6 resuelto**: `src/experiment_runner/synthetic_augmentation.py::add_synthetic_rows` genera sintéticos sobre las variables ya construidas, no sobre columnas físicas crudas. Tests: `tests/test_synthetic_augmentation.py`. Verificado sobre datos reales: 100 filas sintéticas agregadas a un entrenamiento de 286, sin NaN, modelo reentrenado sin error. |
| Definir métricas y criterios de evaluación | ✅ | Se reutilizan sin cambios `predictive_modeling.evaluation.evaluate_classifier`/`compare_models`. |
| Definir particiones, semillas y cantidad de repeticiones | ✅ | Partición temporal existente (`data_quality.splitting`); 5 semillas por configuración. |
| Implementar el procedimiento automatizado de experimentación | ✅ | `src/experiment_runner/runner.py::run_configuration` (ejecuta el orquestador de HU6 por semilla, con aumento sintético opcional). Tests: `tests/test_experiment_runner.py`. Verificado sobre el dataset real: configuración base, 3 semillas, F1 entre 0.400 y 0.500. |
| Configurar el registro de parámetros, versiones y resultados | ✅ | `src/experiment_runner/mlflow_logging.py::log_configuration_results` (run padre con métricas agregadas + run hijo anidado por semilla). Tests: `tests/test_mlflow_logging.py`. `mlflow>=2.14,<3` agregado como dependencia. Verificado sobre resultados reales: run padre + 3 runs hijos anidados recuperables por `tags.mlflow.parentRunId`. |
| Ejecutar una prueba piloto del protocolo experimental | ✅ | Configuración base, 2 semillas, contra el servidor MLflow real (`http://localhost:5000`). Run padre `piloto-base` con 2 runs hijos anidados. |
| Ejecutar experimentos con modelos de referencia | ✅ | `base` y `+sintéticos`, 5 semillas cada una. Real: `base` F1=0.4585±0.0423; `+sintéticos` F1=0.3123±0.0862 (peor que base). |
| Ejecutar experimentos con mecanismos de robustez integrados | ✅ | `+anomalías` y `completa`, 5 semillas cada una. Corregido y re-ejecutado en `openspec/changes/fix-anomaly-feature-integration/` (ver fila siguiente) — el hallazgo original de métricas idénticas a `base`/`+sintéticos` era un defecto de integración, ya resuelto. |
| Verificar integridad y reproducibilidad de los experimentos | ✅ | Re-ejecución de `base` con las mismas 5 semillas: `pd.testing.assert_frame_equal` confirmó métricas idénticas bit a bit entre ambas corridas. |
| Corregir la integración de `is_anomaly` como variable predictora y re-ejecutar `+anomalías`/`completa` | ✅ | `openspec/changes/fix-anomaly-feature-integration/`: `is_anomaly` ahora llega al modelo (`fit_anomaly_detector`/`apply_anomaly_detector`, ajustados solo sobre `train`). Re-ejecutado contra MLflow real (runs `anomalias-refit`/`completa-refit`): `+Anomalías` F1=0.4625±0.0414, ROC-AUC=0.5881±0.0309 (vs. `Base` F1=0.4585±0.0423, ROC-AUC=0.5551±0.0191); `Completa` F1=0.3733±0.1065, ROC-AUC=0.5297±0.0629 (vs. `+Sintéticos` F1=0.3123±0.0862, ROC-AUC=0.5083±0.0439). Ya no son idénticas — efecto positivo pero modesto. Specs y análisis de HU8 actualizados con los valores reales. |
| Corrección de fuga temporal en imputación y umbral de estrés, y re-ejecución de las 4 configuraciones | ✅ | Auditoría metodológica de la memoria técnica detectó dos fugas reales en `src/architecture_integration/pipeline.py`: (1) `interpolate_missing` (interpolación lineal bidireccional) se aplicaba sobre el dataset completo antes de partir train/test, pudiendo completar un hueco de entrenamiento con una observación de evaluación; (2) el umbral de estrés (`add_stress_label`, percentil 20) se calculaba sobre el dataset completo antes de partir. Corregido reordenando el pipeline (partir primero; `interpolate_missing_causal` — forward-fill puro, evaluación arranca con la cola de entrenamiento como semilla, nunca `bfill` — por partición; `fit_stress_threshold` congelado solo sobre entrenamiento) sin tocar el resto de la arquitectura. Tests de causalidad agregados en `tests/test_imputation.py`/`tests/test_labeling.py`; suite completa en verde (`pytest -q` 116, `cd backend && pytest -q` 24). Re-ejecutadas las 4 configuraciones + escenarios de escasez/ruido con las mismas semillas `[0,1,2,3,4]` (`scripts/run_hu7_experiments.py`, `scripts/run_hu7_scenarios.py`), registradas en un experimento MLflow nuevo (`hu7-epica4-leakage-fix`) sin sobrescribir la evidencia histórica (`hu7-epica4`). **Hallazgo principal**: el umbral corregido (0.3223) es más alto que el anterior (0.3115) porque la humedad de suelo de entrenamiento es sistemáticamente mayor que la de evaluación (época más seca) — la tasa de estrés en evaluación pasa de ~51% (artificialmente balanceada por la fuga) a ~65% real. F1 sube en las 4 configuraciones (`Base` 0.4585→0.7354, `+Sintéticos` 0.3123→0.7098, `+Anomalías` 0.4625→0.7368, `Completa` 0.3733→0.7075) pero ROC-AUC cae a ~0.44-0.50 (antes 0.51-0.59) — en o por debajo del azar. El orden relativo entre configuraciones se mantiene (anomalías ayuda modestamente, sintéticos perjudica, escasez ayuda, ruido perjudica), pero la conclusión sobre capacidad predictiva real cambia a **menos favorable**, no más: el F1 alto queda explicado por el desbalance de clases en evaluación, no por señal predictiva genuina (ver `docs/research/hu8-analisis-resultados.md`, sección 11, para el detalle completo). Specs `data-quality`, `predictive-modeling` y `architecture-integration` actualizadas. **Actualización (2026-09-05):** `docs/research/hu8-resultados-discusion-conclusiones.md` (sección 6) y `openspec/specs/experiment-runner/spec.md` también actualizados con los mismos valores re-ejecutados — habían quedado fuera del PR original de esta corrección. |
| Segunda auditoría: purga de frontera de horizonte, consistencia del detector de anomalías, CV temporal con margen y métricas robustas al desbalance | ✅ | Auditoría metodológica encontró una fuga residual (la etiqueta objetivo, calculada con desplazamiento hacia adelante del horizonte tras concatenar train+test imputados, filtraba a las últimas filas de train una etiqueta ya perteneciente a evaluación) y un error de diseño (`data_quality.pipeline.run_quality_pipeline` ajustaba el detector de anomalías de evaluación sobre la propia distribución de evaluación en vez de reusar el detector de entrenamiento). Corregido con `data_quality.splitting.purge_target_horizon` (`tests/test_splitting.py`) y con el patrón `fit_anomaly_detector(train)`→`apply_anomaly_detector` ya usado en `architecture_integration.pipeline` (`tests/test_pipeline.py::test_pipeline_anomaly_detector_for_test_is_fit_on_train_not_on_itself`). Se agregó `gap=horizon_days` a `TimeSeriesSplit` en `select_best_candidate`, se rediseñó el desempate de selección de modelo (ya no favorece Random Forest por nombre; ahora reporta `fold_diagnostics`/`selection_warning` cuando un fold de validación carece de positivos) y se agregaron baselines de clase mayoritaria/siempre-estrés junto a MCC, balanced accuracy y PR-AUC (`src/predictive_modeling/models.py`, `evaluation.py`, `model_selection.py`). También se hizo mandatorio el contrato de esquema del modelo registrado (`src/human_feedback/model_registry.py`: `feature_columns`/`horizon_days`/`threshold`/`pipeline_version` obligatorios al registrar, validación explícita al cargar — `ModelContractMismatch` en vez de carga silenciosa) y se centralizó la configuración reproducible de `scripts/run_hu7_experiments.py`/`run_hu7_scenarios.py` (constantes nombradas: dataset, columnas, horizonte, percentil, lags, ventanas, umbral, contaminación, hiperparámetros, semillas, versión de pipeline). Re-ejecutadas las 4 configuraciones + escenarios en un experimento MLflow nuevo (`hu7-epica4-purged-cv`), sin sobrescribir `hu7-epica4-leakage-fix` ni `hu7-epica4`. Suite completa en verde (`pytest -q` 158, `cd backend && pytest -q` 31). **Hallazgos principales**: (1) el orden `+Anomalías` > `Base` reportado en la corrección anterior se invierte (`Base` F1=0.7309/MCC=0.0743 > `+Anomalías` F1=0.7278/MCC=0.0571); un diagnóstico por semilla confirma que la diferencia es ruido (signo mixto), no un efecto real — la conclusión "anomalías ayuda modestamente" ya no se sostiene. (2) El escenario de escasez de datos (`train_fraction=0.5`), reportado antes como una mejora de F1 (0.8374), tiene el MCC más negativo de todo el estudio (-0.1103) — peor que persistencia — revirtiendo esa conclusión: la escasez de datos no mejora la discriminación real, agrava el desbalance de clases. (3) ET0 confirmado sin uso en ningún experimento real de HU7/HU8 (solo en datos sintéticos de HU2, `src/data_ingestion/mock_sensor.py`); no se agregó al modelo por instrucción explícita de la auditoría. Detalle completo en `docs/research/hu8-analisis-resultados.md` (sección 12) y `docs/research/hu8-resultados-discusion-conclusiones.md` (sección 7). Specs `data-quality`, `predictive-modeling`, `architecture-integration` y `experiment-runner` actualizadas. |

**Balance HU7:** de 12 tareas, 12 completas, 0 parciales, 0 no iniciadas. HU7 completa. Ninguna de las dos correcciones de fuga temporal reabre una tarea (todas seguían siendo ✅ como procedimiento), pero cambian sustancialmente los resultados numéricos reportados — ver las dos filas anteriores y HU8 secciones 11-12.

## HU8 — Análisis de resultados y contrastación de la hipótesis

HU8 no tiene capacidad de código (igual que HU1) — se dividió en tres sub-proyectos documentales: análisis de resultados, redacción de resultados/discusión/conclusiones, y la memoria técnica final. Los primeros dos ya están implementados; la memoria técnica final todavía no se redactó.

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Consolidar los resultados de todas las ejecuciones experimentales | ✅ | `docs/research/hu8-analisis-resultados.md`, sección 1: tabla de las 4 configuraciones × 5 semillas, registradas en MLflow real (HU7). |
| Identificar ejecuciones incompletas o inconsistentes | ✅ | Sección 2: las 20 corridas completaron sin error; inconsistencia detectada (`+anomalías`=`base`, `completa`=`+sintéticos`) y ya resuelta tras `openspec/changes/fix-anomaly-feature-integration/` — valores reales actualizados. |
| Calcular métricas agregadas y medidas de dispersión | ✅ | Sección 3: media±desvío de F1/ROC-AUC por configuración, ya en la tabla de la sección 1. |
| Comparar el enfoque de referencia con la arquitectura propuesta | ✅ | Sección 4: la arquitectura propuesta (RF, F1=0.4585) no supera al modelo de referencia por persistencia (F1=0.486, HU4). **Actualización (2026-09-04):** tras la corrección de fuga temporal (fila anterior), esta comparación de F1 queda confundida por un cambio real en la tasa base de estrés en evaluación; la lectura más confiable (ROC-AUC) muestra que ninguna configuración discrimina mejor que el azar — ver `docs/research/hu8-analisis-resultados.md`, sección 11.4. |
| Analizar el aporte de la detección de anomalías y los datos sintéticos | ✅ | Sección 5: detección de anomalías con efecto positivo pero modesto tras corregir la integración (`openspec/changes/fix-anomaly-feature-integration/`; `is_anomaly` ya llega al modelo); datos sintéticos con efecto negativo (F1 0.312 vs 0.459). **Actualización (2026-09-05):** tras la segunda auditoría (purga de frontera de horizonte + corrección del detector de anomalías), este hallazgo **ya no se sostiene** — `Base` supera ahora a `+Anomalías` en F1 y MCC, y la diferencia por semilla tiene signo mixto (ruido, no efecto real). Ver `docs/research/hu8-analisis-resultados.md`, sección 12.2. |
| Evaluar el efecto de la retroalimentación y la recalibración | ✅ | Sección 6: mecanismo verificado (HU5) con corrección sintética que cambia la predicción; sin evaluación agregada por falta de volumen real. |
| Analizar falsos positivos, falsos negativos y errores relevantes | ✅ | Sección 7: 7 falsos positivos, 24 falsos negativos con fechas concretas (HU4). |
| Analizar el desempeño bajo escenarios de escasez de datos | ✅ | `src/experiment_runner/scenarios.py::subsample_training_period` (`openspec/changes/add-experiment-scenarios/`). Verificado sobre datos reales: entrenamiento reducido a la mitad más reciente, F1 medio 0.6219±0.0888 — mejor que la configuración base sin reducir (0.4585±0.0423), hallazgo explicado por relevancia estacional. **Actualización (2026-09-05):** tras agregar MCC como métrica robusta al desbalance, este hallazgo se revierte — el mismo escenario (F1=0.8374 bajo el pipeline con purga de frontera) tiene el MCC más negativo de todo el estudio (-0.1103, peor que persistencia). El F1 alto no refleja mejor discriminación, sino un desbalance de clases agravado por menos datos de entrenamiento. Ver `docs/research/hu8-analisis-resultados.md`, sección 12.3. |
| Analizar el desempeño bajo escenarios de ruido y variabilidad de datos | ✅ | Variabilidad evaluada (desvío entre semillas, HU7). Ruido: `src/experiment_runner/scenarios.py::inject_gaussian_noise`. Verificado sobre datos reales: F1 medio 0.3188±0.1130 — peor y más variable que sin ruido, como se esperaba. Valor de ruido no calibrado contra una fuente real (documentado como limitación). |
| Evaluar robustez, estabilidad y compromisos entre métricas | ✅ | Sección 10: estabilidad peor con datos sintéticos; compromiso precisión>recall en todas las configuraciones; complejidad del modelo no se traduce en mejor desempeño. |
| Contrastar los resultados con la hipótesis de investigación | ✅ | `docs/research/hu8-resultados-discusion-conclusiones.md`, sección 2: la hipótesis **no se confirma** en general; modelado predictivo evaluado y sin mejora, datos sintéticos evaluados con efecto contrario, retroalimentación humana sin evaluación concluyente; detección de anomalías evaluada de forma válida tras la corrección de integración (`openspec/changes/fix-anomaly-feature-integration/`). |
| Identificar limitaciones y amenazas a la validez | ✅ | Sección 3: amenazas a validez interna (integración de `is_anomaly` — ya corregida, ver `openspec/changes/fix-anomaly-feature-integration/` — umbrales no calibrados, método de síntesis simple) y externa (un solo sitio/año, dataset chico, escenarios de escasez/ruido no ejecutados, retroalimentación real mínima). |
| Redactar la sección de resultados experimentales | ✅ | Sección 1. |
| Redactar la discusión y las conclusiones | ✅ | Sección 4, con 5 recomendaciones concretas para trabajo futuro ordenadas por impacto esperado. |
| Consolidar tablas, figuras, referencias y evidencias | ✅ | Sección 5: tabla de fuentes de evidencia primaria con referencia a cada spec/documento verificado. |
| Redactar la memoria técnica final (documento de tesis) | ⬜ | No iniciada. `docs/research/hu8-analisis-resultados.md` y `hu8-resultados-discusion-conclusiones.md` son insumos verificados para esta redacción, no la memoria en sí — no existe todavía un documento consolidado de tesis en el repo. |

**Balance HU8:** de 16 tareas, 15 completas, 0 parciales, 1 no iniciada (la memoria técnica final). HU8 parcial.

**Revalidación posterior al cierre de HU8 (2026-09-06):** auditoría científica integral realizada contra la evidencia formal `controlled_daily_v3` (`docs/research/reference-v3-formal-results.json`/`reference-v3-formal-table.md`, 8 configuraciones × 5 semillas). El issue #17 y sus 15 issues hijos (#97-#111) continúan CLOSED / completed; CA1-CA4 permanecen CUMPLE CON LIMITACIÓN (evidencia formal válida, pero los documentos de análisis no la incorporaban todavía — sincronizado en esta iteración). Conclusión científica: la evidencia es parcial y mixta, no permite sostener una mejora general de la arquitectura; `recent_fraction_0.5` es el único efecto consistente (sin corresponder a un componente de la hipótesis); anomalías y sintéticos muestran evidencia mixta, no la narrativa histórica de "modesto positivo"/"empeora consistentemente"; la retroalimentación humana tiene evidencia funcional pero no cuantitativa (diseñada, no ejecutada). No se requiere reejecutar HU7 ni HU8, ni reabrir ninguno de los dos. Ver `docs/research/hu8-auditoria-revalidacion.md`.

## Interfaz de usuario (alerting-ui, HU5+HU6)

Primer scaffolding real de `backend/` y `frontend/` (ADR-0003), anticipado desde HU5 y construido después de completar HU1-HU8. Expone el pipeline completo (HU6) y el mecanismo de retroalimentación humana (HU5) a través de una interfaz de usuario.

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Backend: `POST /forecast/run` | ✅ | `backend/app/routers/forecast.py`; `backend/tests/test_forecast.py`. |
| Backend: `GET /feedback`, confirmar, rechazar | ✅ | `backend/app/routers/feedback.py`; `backend/tests/test_feedback.py`. |
| Frontend: página de pronóstico y alertas | ✅ | `frontend/src/features/forecast/ForecastPage.tsx`; `frontend/src/features/forecast/ForecastPage.test.tsx`. |
| Verificación manual end-to-end (backend + frontend + dataset real) | ✅ | Backend y frontend reales corridos juntos contra `data/melchor_romero_2024_consolidado.parquet`: `train_rows=286`, `test_rows=71`, 22 de 71 fechas con alerta. Confirmar/rechazar sobre 2024-10-19/2024-10-20 actualizó el estado mostrado de inmediato y ambos se preservaron tras re-correr el pronóstico (`upsert_feedback_log` verificado de punta a punta). Ver `openspec/specs/alerting-ui/spec.md` para el detalle completo. |
| CI (jobs `backend-quality`, `frontend-quality`) | ✅ | `.github/workflows/ci.yml`. |
| Dockerización de `backend`/`frontend` | ✅ | `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/.dockerignore`, servicios `backend`/`frontend` en `docker-compose.yml`. Ver `docs/adr/0005-dockerizacion-backend-frontend.md`. Verificado de punta a punta vía navegador contra los contenedores reales (`docker compose up -d backend frontend`): pronóstico corrido, tabla poblada con veredictos reales, confirmar/rechazar funcionando igual que en el entorno local sin Docker. |
| Rediseño visual de `ForecastPage` | ✅ | `frontend/src/features/forecast/ForecastPage.css` (nuevo), `ForecastPage.tsx` actualizado. Filas con señal de color por severidad, gauge de probabilidad, badges de estado. Banner fijo + mensaje inline tras cada acción dejan explícito que confirmar/rechazar no reentrena el modelo en esta iteración. Decisiones registradas en `docs/design/alerting-ui-visual-design.md`. Verificado visualmente vía navegador (dev server local contra backend real) y `npm run test` en verde. |
| Disparo de recalibración desde la UI | ✅ | `src/human_feedback/model_registry.py`, `backend/app/routers/recalibration.py`, botón "Recalibrar modelo" en `ForecastPage.tsx`. Ver `docs/adr/0006-recalibracion-disparada-desde-la-ui.md`. Verificado sobre el stack real (`docker compose up -d --build`): el backend arrancó sin error de conexión tras esperar a `mlflow` (`depends_on`); se corrió `POST /forecast/run`, se rechazó la alerta del 2024-10-20 vía `POST /feedback/2024-10-20/reject`, y `POST /recalibrate` registró la versión `1` en el Model Registry de MLflow aplicando 2 correcciones reales acumuladas (`2024-10-20`, `2024-11-24`, de una validación manual previa). El siguiente `POST /forecast/run` respondió en 0.51s sin logs de reentrenamiento (contra los ~5s+ típicos de entrenar un Random Forest), confirmando que reusó el modelo recalibrado vía `skip_fit=True`. |
| Motor de selección automática entre modelos candidatos | ✅ | `src/predictive_modeling/model_selection.py`, usado por `run_end_to_end_pipeline` (`model=None`) y conectado al backend en `backend/app/pipeline.py`. Ver `openspec/changes/add-model-selection-engine/`. Verificado sobre el dataset real (Melchor Romero 2024): `logistic_regression` y `random_forest` empataron en `cv_mean_score=0.0` (mismo fenómeno de folds sin ejemplos de la clase de estrés ya documentado en `openspec/specs/predictive-modeling/spec.md`, "Limitaciones conocidas"), lo que exponía el desempate original (`max` sobre el dict, quedaba `logistic_regression` por orden de inserción) sustituyendo silenciosamente al Random Forest fijo previo. Se endureció el desempate en `select_best_candidate` para preferir `random_forest` en caso de empate; re-verificado tras el fix: `run_end_to_end_pipeline(model=None)` sobre el mismo dataset ahora elige `random_forest`. Test agregado: `tests/test_model_selection.py::test_select_best_candidate_breaks_ties_in_favor_of_random_forest`. |
| Corrección: `load_latest_recalibrated_model` tragaba fallos de conexión a MLflow en silencio | ✅ | `src/human_feedback/model_registry.py`. Causa raíz confirmada empíricamente: con un backend real, un modelo sin registrar todavía devuelve `[]` sin lanzar excepción (el `if not versions: return None` ya lo cubre); el `except MlflowException: return None` que existía no protegía ese caso — en cambio atrapaba fallos reales de conexión (`error_code=INTERNAL_ERROR`), contradiciendo ADR-0006 ("si mlflow no está corriendo, debe fallar de forma explícita, no silenciosa"). Se quitó ese `except`. Test de regresión: `tests/test_model_registry.py::test_load_latest_recalibrated_model_raises_when_mlflow_is_unreachable` (ciclo RED-GREEN verificado: con el bug, `DID NOT RAISE`; con el fix, propaga `MlflowException`). |
| Caché del modelo auto-seleccionado | ✅ | `src/data_ingestion/storage.py` (`get_dataset_fingerprint`), `backend/app/pipeline.py` (caché en memoria del proceso, invalidado por fingerprint del dataset). Ver `openspec/changes/add-selection-caching/`. Resuelve la limitación "sin cachear" documentada tras `add-model-selection-engine` — prerequisito antes de conectar una fuente de datos en vivo. |
| Ingesta de sensores en vivo (mock) | ✅ | `POST /sensors/readings` (`backend/app/routers/sensors.py`), generador por random walk acotado (`src/data_ingestion/mock_sensor.py`), scripts CLI de backfill y simulación (`scripts/seed_mock_sensor_dataset.py`, `scripts/simulate_sensor_readings.py`). Ver `docs/adr/0007-ingesta-de-sensores-en-vivo-mock.md` y `openspec/changes/add-mock-sensor-ingestion/`. Dataset en vivo separado del histórico `melchor_romero_2024_consolidado` (evidencia HU7/HU8) vía `ALERTING_UI_DATASET`, con salvaguarda que rechaza (409) escribir sobre el histórico si esa variable no fue seteada explícitamente — hallazgo real de la revisión final: el backend cayó en el dataset histórico durante la verificación manual por no tener la env var seteada (sin daño permanente, confirmado por comparación binaria contra la versión en git). También se corrigió que timestamps con hora rompían el invariante "una fila por día" y, con él, el flujo de confirmar/rechazar alertas para lecturas en vivo (`append_reading` ahora normaliza a medianoche y reemplaza la lectura del mismo día en vez de duplicarla). El dataset mock generado sirve para validar el plumbing de punta a punta, no como evidencia de tesis (valores no climatológicamente realistas, sin correlación entre variables — documentado en el ADR). |
| Derivación de `et0` para lecturas de sensor mock | ✅ | `src/data_quality/reference_et.py::estimate_et0` (FAO-56 Penman-Monteith, variante con temperatura media dado que el esquema no registra Tmax/Tmin), usado por `generate_next_reading` (`src/data_ingestion/mock_sensor.py`) para completar `et0` a partir del resto de la lectura generada. Ver `openspec/changes/add-mock-et0-derivation/` y `docs/adr/0007-ingesta-de-sensores-en-vivo-mock.md`. Tests unitarios verifican monotonicidad física de la fórmula en aislamiento (mayor radiación → mayor `et0`; mayor humedad relativa → menor `et0`; verano > invierno en el hemisferio sur) y que el resultado permanece dentro del rango agronómico ya documentado (`data_quality.rules.AGRONOMIC_RANGES["et0"]`). Verificado con un backfill real de 214 días (2024-06-01 a 2024-12-31): `et0` entre 1.05 y 9.80 mm/día, dentro de rango. **Hallazgo real**: en ese backfill, `et0` correlaciona negativamente con `solar_radiation` (-0.22) en vez de positivamente — no es un error de la fórmula (los tests unitarios aislados confirman la dirección correcta), sino una consecuencia de la limitación ya documentada en ADR-0007 de que el generador camina cada columna de forma independiente, sin correlación real entre variables: `relative_humidity` termina correlacionada por azar con `solar_radiation` (+0.23) en este backfill, y su efecto dominante sobre `et0` (-0.89) confunde el efecto directo de la radiación. Sigue pendiente para las fuentes reales (NASA POWER/ESA CCI), que tienen Tmax/Tmin y merecerían la fórmula completa de FAO-56. |
| Ingesta multi-sensor en paralelo | ✅ | `src/data_ingestion/sensor_naming.py` deriva nombres de dataset/feedback/modelo por `sensor_id`, validado contra `^[a-zA-Z0-9_-]{1,64}$`. Los cuatro routers de `alerting-ui` pasan a requerir `sensor_id` en la ruta (`POST /sensors/{sensor_id}/readings`, `POST /forecast/{sensor_id}/run`, `GET/POST /feedback/{sensor_id}/...`, `POST /recalibrate/{sensor_id}`); el caché de selección de modelo (`backend/app/pipeline.py::_selection_cache`) y el modelo recalibrado registrado en MLflow (`human_feedback/model_registry.py`) pasan a estar particionados por sensor. Ver `docs/adr/0008-ruteo-y-aislamiento-multi-sensor.md` y `openspec/changes/add-multi-sensor-ingestion/`. **Breaking change deliberado**: `frontend/ForecastPage.tsx` deja de funcionar contra este backend hasta que se le agregue un selector de sensor (fuera de alcance de este *change*, ver ADR-0008). **Actualización (2026-09-06):** resuelto en un *change* posterior — `frontend/src/features/forecast/ForecastPage.tsx` ya incorpora el input/selector de `sensor_id` y `frontend/src/features/forecast/api.ts` construye todas las rutas con `sensor_id` (`test.ts::"routes every operation to the selected sensor"` lo verifica explícitamente). El frontend actual no realiza ninguna llamada a una ruta sin `sensor_id` — ver `docs/research/hu6-auditoria-revalidacion.md`. Verificado con ingesta de dos sensores en paralelo vía `scripts/simulate_multiple_sensors.py --sensor-ids sensor-melchor-1,sensor-melchor-2 --rounds 3`: backfill de 90 filas por sensor confirmado; 3 rondas de tráfico concurrente ejecutadas sin error, con `filas_totales` manteniéndose independiente en 91 para ambos sensores (comportamiento esperado — dedup diaria preexistente, no un bug). `POST /forecast/{sensor_id}/run` retornó `train_rows=66, test_rows=16, 0 alertas` (16 veredictos del 2026-07-12 al 2026-07-27 con `alerta=false` en todos, probabilidades entre ~0.146 y ~0.223) para ambos (idénticos porque backfills se generaron con igual semilla y rango, validando aislamiento no por volumen distinto sino por contenido distinto). Los archivos `data/sensor__sensor-melchor-1.parquet` y `data/sensor__sensor-melchor-2.parquet` quedaron como archivos separados con contenido distinto en la última lectura concurrente: sensor-1 `soil_moisture=0.1622, temperature=17.05, relative_humidity=79.42, precipitation=90.03, solar_radiation=10.81, wind_speed=47.27` vs. sensor-2 `soil_moisture=0.1436, temperature=15.44, relative_humidity=81.58, precipitation=124.67, solar_radiation=10.72, wind_speed=45.13`, confirmando que cada hilo del `ThreadPoolExecutor` leyó y escribió su propio dataset sin cruce de datos. |

| Frontend demostrativo de una sola pantalla (assessment → mejora enfocada) | ✅ | Tres endpoints read-only nuevos (`GET /quality/{sensor_id}`, `GET /models/{sensor_id}/active`, `GET /lineage/{sensor_id}`; `backend/app/routers/quality.py`, `models.py`, `lineage.py`; `human_feedback/model_registry.py::get_latest_recalibrated_version`/`load_latest_issued_predictor_metadata`) exponen calidad/anomalías, identidad del predictor activo y la cadena A→B→C ya implementada en `human_feedback.model_registry.list_recalibration_lineage`, previamente sin ningún router que la sirviera. Frontend reorganizado en `frontend/src/App.tsx` (secciones ancladas: calidad, predicción/feedback/recalibración, linaje, evidencia) reutilizando `ForecastPage.tsx` existente (ahora recibe `sensorId` como prop compartida) sin agregar router ni librería de estado. Panel de evidencia (`frontend/src/features/evidence/`) estático, con los valores exactos de `docs/research/reference-v3-formal-table.md` (experimento MLflow `hu7-controlled-daily-v3-formal`, tag `scientific-baseline-v3`). `API_BASE_URL` dejó de estar hardcodeado (`VITE_API_BASE_URL`, `frontend/.env.example`). Tests: 14 nuevos en backend (`test_quality.py`, `test_models_active.py`, `test_lineage.py`, incluyendo verificación explícita de ausencia de efectos secundarios) y 14 nuevos en frontend (paneles nuevos + regresión del flujo de feedback/recalibración). Verificado con datos reales: suite completa `pytest -q` (262 tests) y `backend && pytest -q` (50 tests) en verde, `ruff check`/`black --check` limpios, `npm test` (22 tests), `npm run lint` y `npm run build` en verde. Verificación manual de punta a punta contra contenedores Docker reales (backend + MLflow real, dataset de `sensor-a` seedeado a partir del histórico): pronóstico → rechazo → recalibración → linaje reconstruido correctamente (`source_model_id != successor_model_id`, `dataset_sha256` presente, `lineage_version=2`); los runs/modelos MLflow generados por esta verificación manual se removieron del servidor compartido al finalizar (no quedó evidencia de prueba persistida). Verificación visual del frontend en navegador no pudo completarse en esta sesión (extensión Chrome no conectada); queda pendiente para quien retome esta rama.

| Rediseño de flujos, navegación y diseño coherente (`openspec/changes/improve-alerting-ui-decision-workflow/`) | ✅ | Cuatro entregas incrementales, cada una con PR propio contra `main` y CI en verde antes de empezar la siguiente. **Entrega 1 — flujos confiables** (PR #196): `frontend/src/features/forecast/useForecastWorkspace.ts` extrae historial/operación a un hook compartido; `GET /feedback/{sensor_id}` se consulta al activar el sensor sin disparar un pronóstico; bloqueo único de mutaciones (`activeMutation`), descarte de respuestas de un sensor que dejó de estar activo, reconciliación por `fecha` entre un POST exitoso y su GET de refresco. **Entrega 2 — navegación y resumen** (PR #197): `frontend/src/features/navigation/useHashRoute.ts` rutea por hash entre cinco destinos (Resumen/Alertas y revisión/Calidad de datos/Modelo y trazabilidad/Evidencia y arquitectura) sin router de terceros, compatibilizando los anchors previos; `ResumenView.tsx` como entrada por defecto (último pronóstico registrado, pendientes de revisión, acción de generar pronóstico); filtros de historial por alerta/estado/rango de fecha con contadores generales independientes del filtro. **Entrega 3 — revisión humana y trazabilidad** (PR #198): `CorrectionForm.tsx` reemplaza el "Rechazar" de un clic (que inventaba una observación y adivinaba la etiqueta) por un formulario inline que exige una etiqueta observada explícita y opuesta a la original, con `useForecastWorkspace.confirm`/`reject` devolviendo si la escritura tuvo éxito para mantener el formulario abierto ante un 409; `RecalibrationPanel.tsx` sustituye el contador engañoso de "correcciones sin incorporar" por correcciones registradas + fechas incorporadas al predictor activo (desconocida si falta metadata), y reubica la recalibración manual en Modelo y trazabilidad. **Entrega 4 — diseño coherente y verificación** (esta entrega, rama `feat/alerting-ui-design-verification`): tokens de color/tipografía/espaciado centralizados en `frontend/src/index.css` (antes duplicados por componente, con un tema oscuro parcial heredado del boilerplate de Vite que nunca se retiró); layout de página anidado corregido (`.fp-page` tenía su propio `min-height:100vh`/padding dentro de `.app-page`); estado de revisión (pendiente/confirmada/rechazada) separado en paleta propia de la señal de alerta/safe — confirmar una alerta ya no la pinta de verde; enlace "Saltar al contenido" agregado; contenedor de la tabla de evidencia formal habilitado como región enfocable por teclado. Contrastes verificados por cálculo (fórmula WCAG de luminancia relativa, no solo inspección visual): se encontró y corrigió un par por debajo de 4.5:1 (`--color-alert` sobre `--color-alert-bg`, 4.38:1) y bordes de controles interactivos reforzados a un tono con ≥3:1 (antes ~1.3:1). 68 tests en verde (`npm test`), `npm run lint`/`npm run build` limpios. Verificación en navegador con un `fetch` interceptado en el propio navegador (mocks, sin backend real): estados vacío/error/histórico extenso/alerta/sin alerta/guardado/409/fallo de integridad de linaje revisados en escritorio (1440px); confirmado por consulta directa del DOM que el enlace de salto es el primer elemento enfocable y que el foco salta al encabezado correcto tras navegar. **Limitación explícita, no resuelta**: no se pudo verificar visualmente un viewport móvil real ni zoom 200% — la herramienta de redimensionado de ventana no tuvo efecto en este entorno de sandbox en ninguna de las cuatro entregas (`window.innerWidth` no cambia pese a pedirlo); el comportamiento responsive se sostiene en la revisión de código (flex-wrap, columnas únicas por defecto, sin anchos fijos) pero no en una captura móvil real. Sin integración real contra `backend/` en ninguna de las cuatro entregas. Detalle completo de tareas y escenarios en `openspec/changes/improve-alerting-ui-decision-workflow/tasks.md` y en `openspec/specs/alerting-ui/spec.md`. |

**Fuera de alcance, documentado para la próxima iteración**: robustez ante escasez/ruido en producción (ver `openspec/changes/add-alerting-ui/proposal.md`, "Fuera de alcance de este change"); consolidación del dataset en vivo con el histórico; autenticación del endpoint de ingesta; derivación de `et0` para las fuentes reales (NASA POWER/ESA CCI) — resuelta para el mock, ver fila anterior. El selector de sensor en el frontend, listado originalmente aquí como pendiente, ya fue incorporado (ver fila "Ingesta multi-sensor en paralelo", actualización 2026-09-06).

## Infraestructura de desarrollo (ADR-0003)

Esta sección no corresponde a una tarea del backlog de tesis (HU1-HU8), sino a infraestructura de ciclo de vida de desarrollo decidida en `docs/adr/0003-stack-web-y-ciclo-de-vida-automatizado.md`. Se registra igual porque el diff que la introduce toca `src/` (reformateo con Black) y por eso queda alcanzado por la regla de trazabilidad que este mismo documento exige para cualquier PR.

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Definir stack backend/frontend y gobernanza del ciclo de vida (ADR) | ✅ | `docs/adr/0003-stack-web-y-ciclo-de-vida-automatizado.md`, aceptado 2026-08-16. |
| Integración continua (lint + formato + tests) | ✅ | `.github/workflows/ci.yml` corre `ruff check`, `black --check` y `pytest` sobre `src/`/`tests/` en cada PR contra `main`; `ruff` y `black` agregados como dependencias de desarrollo en `pyproject.toml`. |
| Formatear el código Python existente con Black | ✅ | Reformateo aplicado a `src/data_ingestion/aggregation.py` y `src/data_ingestion/schema.py` (Task 1 del plan de implementación); `black --check src tests` pasa limpio. |
| Hook de trazabilidad OpenSpec/ADR/seguimiento en `gh pr create` | ✅ | `.claude/hooks/check-pr-traceability.sh` (script) y `.claude/settings.json` (wiring del hook `PreToolUse`) bloquean la apertura de un PR que no referencie una HU/change de OpenSpec, o que toque `src/`/`docs/research/` sin actualizar este mismo documento; incluye bypass explícito vía `SKIP_PR_TRACEABILITY=1` para el caso de PR fuera de ese esquema. |
| Hook de evidencia al cerrar issues (`gh issue close`) | ✅ | `.claude/hooks/check-issue-close-evidence.sh` bloquea el cierre de un issue sin un `--comment` que referencie evidencia concreta (ruta de archivo, PR, o test); la skill `.claude/skills/closing-issues/SKILL.md` documenta el criterio real (cruzar contra este mismo documento antes de cerrar, no solo satisfacer la heurística del hook). Incluye bypass vía `SKIP_ISSUE_EVIDENCE=1`. |
| Hook de recordatorio post-merge para cerrar issues | ✅ | `.claude/hooks/remind-close-issues-after-merge.sh` (PostToolUse) se dispara automáticamente después de cada `gh pr merge` e inyecta un recordatorio de revisar este documento y cerrar los issues correspondientes con evidencia — ya no depende de que el usuario lo pida ni de que el agente se acuerde por su cuenta. |
| Skills de proyecto: backend, frontend, TDD | ✅ | `.claude/skills/backend-python-fastapi-mlflow/`, `.claude/skills/frontend-react/` y `.claude/skills/tdd-project-conventions/`: guían la futura implementación de `backend/`/`frontend/` (todavía sin código, ver ADR-0003) según la restricción de fachada delgada, y documentan las convenciones de testing ya en uso en este repo (fixtures con `normalize_to_schema`, mocking solo de la capa de red, verificación obligatoria contra datos reales antes de marcar una tarea ✅). |
| Skill de redacción de la memoria técnica (TTFA) | ✅ | `.claude/skills/memoria-tecnica/SKILL.md`: codifica la estructura de capítulos, reglas de formato (negrita, `\texttt{}`, referencias, imágenes, código) y errores típicos de IA de la Clase 1 del Taller de Preparación del Trabajo Final, para usar al redactar/revisar el documento de defensa de HU1-HU8. Validado con baseline: un agente sin el skill invierte la regla de `\texttt{}` (la aplica a bibliotecas externas en vez de nombres propios de la implementación) y agrega negrita; con el skill corrige ambos casos. |
| Pipeline de subagentes para redactar capítulos (crítico → corrector → editor) | ✅ | `.claude/agents/memoria-critico.md`, `.claude/agents/memoria-corrector.md` y `.claude/agents/memoria-editor.md`, orquestados desde `.claude/skills/memoria-tecnica/SKILL.md` (sección "Flujo de redacción de un capítulo"): el crítico revisa contenido/distribución, el corrector aplica el checklist de formato en loop con el crítico (tope 3 iteraciones), y el editor final empaqueta el texto limpio en un prompt para pegar en Prism, contra la estructura real de `Plantilla-para-memoria` (`Chapters/ChapterN.tex`, `portada.tex`, `references.bib` con `biblatex` numeric). |

**Balance:** las 4 piezas de ADR-0003 quedan implementadas y verificadas (CI corriendo localmente en verde, hook con pipe-tests, bypass probado). Pendiente fuera del alcance de esta rama: confirmar en un PR real que el check `python-quality` aparece en GitHub (requiere push real, ver "Verificación final" del plan de implementación).

## Infraestructura de ML (ADR-0004)

Tampoco corresponde a una tarea del backlog de tesis (HU1-HU8): es infraestructura de orquestación de experimentos decidida en `docs/adr/0004-orquestacion-experimentos-mlflow-minio.md`, que reemplaza la decisión de "MLflow local sin servidor" de ADR-0002. Se registra por trazabilidad, aunque el diff no toca `src/` ni `docs/research/` (no activa la regla 2 del hook).

| Tarea | Estado | Evidencia / motivo |
|---|---|---|
| Definir orquestación de experimentos (servidor MLflow + backend Postgres + artefactos MinIO) | ✅ | `docs/adr/0004-orquestacion-experimentos-mlflow-minio.md`, aceptado 2026-08-16. Reemplaza la sección correspondiente de ADR-0002 (marcada ahí como superseded). |
| Levantar y verificar el stack de punta a punta | ✅ | `docker-compose.yml` + `docker/mlflow/Dockerfile` probados con `docker compose up -d --build`: los 3 servicios (`postgres`, `minio`, `mlflow`) quedan saludables; se registró un run de prueba real (parámetro, métrica y artefacto) y se confirmó el artefacto físicamente en MinIO vía `mc ls`. Sin código de modelado real todavía (HU3/HU4 no iniciadas) — la verificación fue un experimento de humo, no una corrida de un modelo real. |

**Balance:** infraestructura implementada y verificada de punta a punta con un experimento de prueba. Ningún código de HU3/HU4 depende de esto todavía porque esas historias no arrancaron; queda listo para cuando lo hagan. Docker Desktop pasa a ser un prerequisito de desarrollo desde ahora (ver "Consecuencias" del ADR).

## Conclusión

**Actualización (2026-08-21):** esta conclusión quedó desactualizada — fue escrita cuando solo HU1/HU2 tenían avance real y describía correctamente ese momento del proyecto. El estado actual, según las secciones de arriba: HU3, HU4, HU5, HU6 y HU7 están **✅ completas**; HU8 está **🟡 parcial** (falta la redacción de la memoria técnica final, ver su sección); HU1 y HU2 siguen **🟡 parciales** (falta protocolo sistemático de búsqueda y una fuente de datos adicional, respectivamente). Además, `backend/`+`frontend/` (alerting-ui) exponen HU5+HU6 a través de una interfaz de usuario real, con recalibración manual disparada desde la UI. Ver el resumen equivalente en [`README.md`](../README.md#estado-del-proyecto).

**Riesgo identificado (histórico, sigue vigente como práctica):** cada PR debe indicar explícitamente a qué tarea(s) de la sección 9 del plan corresponde y si la deja completa o parcial, para que este documento se mantenga preciso sin tener que re-auditar todo el historial cada vez.

## Correcciones de tercera auditoría aprobadas — HU4/HU5/HU6/HU7/HU8

Plan aprobado explícitamente por el autor el 2026-09-05. Changes:
`fix-daily-model-contract`, `fix-controlled-experimental-targets`,
`fix-feedback-temporal-lifecycle` y `fix-sensor-ui-routing`. ADR-0009.

- Contrato completo raw/engineered y paquete de estado ajustado; validación antes de carga.
- Calendario diario obligatorio; fechas objetivo y purga temporal explícitas.
- Etiquetas observadas independientes de imputación/ruido; umbral común entre escenarios.
- Escasez supervisada con cobertura preservada y ventana reciente con igual presupuesto.
- Calibración inicial anterior a CV automática y anomalías ajustadas dentro de folds.
- Inferencia sobre el último día sin exigir etiquetas futuras; feedback trazable y maduro;
  reutilización de correcciones; exclusión del período recalibrado de evaluación posterior.
- Interfaz alineada a rutas por sensor, fecha objetivo visible y corrección de no-alertas.
- Artefactos por fecha y configuración efectiva, huella de datos y versiones del entorno.
- Erratas y síntesis científica vigentes agregadas conservando evidencia histórica.

El protocolo para nuevos datasets, validación externa, ablaciones (incluida ET0) y
comparación del efecto humano está redactado en `docs/research/protocolo-experimental-v3.md`.
Su ejecución científica ampliada no se declara completada. HU1 sistemático sigue pendiente.
No se agregan tecnologías, infraestructura ni automatización de riego.

La verificación y la nueva referencia reproducible se registran al cerrar el PR.

**Actualización (2026-09-05):** cierre técnico verificado y primera corrida HU7 formal
y reproducible ejecutada. Correcciones anteriores commiteadas (`be1d481` cierre técnico
de `controlled_daily_v3`; `2a40ee6` preserva provenance del runtime sin `git`). Corrida
formal ejecutada desde commit conocido `2a40ee68c52d2eb5e2040a36b1029f756f9c048a` con
working tree limpio, dataset `melchor_romero_2024_consolidado` (SHA-256
`121697dd5af202633f24adf4244a793477d34bf5e4cf4a1f10d7b2ca1b33ba8e`), registrada en un
experimento MLflow nuevo (`hu7-controlled-daily-v3-formal`, 8 configuraciones × 5
semillas `[0,1,2,3,4]` = 48 runs), exportada con `scripts/export_hu7_reference.py` a
`docs/research/reference-v3-formal-results.json` y
`docs/research/reference-v3-formal-table.md`, sin sobrescribir la evidencia histórica
provisional (`reference-v3-results.json`/`reference-v3-table.md`/
`reference-v3-source-manifest.json`). Suite completa en verde (`pytest -q` 177,
`cd backend && pytest -q` 33, `frontend npm test` 5). Resultados todavía no
interpretados científicamente; HU8 no se actualiza en este PR.

## H-01: recalibraciones HITL sucesivas (HU5, `human-feedback`)

Auditoría transversal técnica (2026-09-06) detectó que `recalibrate_predictor`
rechazaba una segunda recalibración por detectar `model_version` de más de un
predictor en el `feedback_log` acumulado, rompiendo la repetibilidad del ciclo
operativo HITL (forecast → feedback → recalibración → nuevo forecast → nuevo
feedback → nueva recalibración). No afecta `controlled_daily_v3` ni evidencia
formal HU7/HU8.

Corregido en rama `fix/hitl-multiversion-recalibration`: la verificación de
"múltiples predictores" ahora se aplica solo a las correcciones nuevas/pendientes
de la solicitud de recalibración, no al historial completo del log (que
legítimamente mezcla `model_version` de predictores sucesivos); el router deja de
elegir arbitrariamente el primer `model_version` del log y usa el predictor
vigente (`latest`). Detalle en `openspec/specs/human-feedback/spec.md`
(requirement "Recalibración temporalmente controlada con retroalimentación
madura", nota "H-01, 2026-09-06"). Test de regresión de dos ciclos agregado en
`tests/test_controlled_protocol.py`.

**Microajustes de robustez (2026-09-06):** sobre PR #182 (mergeado en `main`,
merge commit `387f64be1701d5fb9fbf17f453ccd3bfbf49ab17`), se reforzó la
verificación de procedencia: además de exigir que las correcciones pendientes
provengan de un único predictor, ahora se exige que ese predictor sea
efectivamente el `predictor.model_id` vigente (una corrección pendiente
homogénea pero originada por otro predictor también falla explícitamente, con
"otro predictor"). Test de incompatibilidad agregado
(`test_recalibration_rejects_pending_feedback_from_a_different_predictor`); el
test E2E de dos ciclos se corrigió para usar `predict_available(df,
predictor_b)` real en el segundo ciclo en vez de reutilizar filas del forecast
de A.

## Trazabilidad explícita de recalibraciones HITL (HU5, `human-feedback`)

Mejora técnica acotada, posterior a H-01 (PR #182, merge commit
`387f64be1701d5fb9fbf17f453ccd3bfbf49ab17`), rama `feat/hitl-recalibration-lineage`.
Fase CRISP-DM: despliegue e integración experimental. No afecta
`controlled_daily_v3`, evidencia formal, datasets, hipótesis, propósito, alcance
ni arquitectura conceptual; sin impacto sobre HU7/HU8.

H-01 permitió ciclos HITL sucesivos (A→B→C), pero no dejaba un registro
explícito, recuperable, de qué feedback disparó cada recalibración ni qué
predictor originó ese feedback. Se agrega `src/human_feedback/lineage.py`
(`FeedbackReference`, `RecalibrationLineage`, `build_feedback_references`,
tipado y agnóstico de MLflow) y se extiende
`src/human_feedback/model_registry.py`: `register_recalibrated_model` acepta un
`lineage` opcional y lo persiste como artefacto JSON
(`recalibration_lineage.json`) dentro del mismo run de MLflow que registra al
predictor sucesor (reutiliza el Model Registry existente, ADR-0006, sin
persistencia paralela); `load_recalibration_lineage`/`list_recalibration_lineage`
lo recuperan y permiten reconstruir la cadena completa. `POST
/recalibrate/{sensor_id}` construye el evento únicamente con las correcciones
nuevas devueltas por `recalibrate_predictor` (nunca con todo el
`feedback_log`), preservando `feedback_log.model_version` sin sobrescribir el
predictor de origen. `RecalibrationResponse` gana un campo opcional
`recalibration_id` (retrocompatible). Detalle en
`openspec/specs/human-feedback/spec.md` (requirement "Linaje explícito de
recalibraciones HITL") y `docs/adr/0006-recalibracion-disparada-desde-la-ui.md`.

Tests agregados: `tests/test_recalibration_lineage.py` (unitario, sin MLflow),
`tests/test_model_registry.py` (registro/recuperación de linaje vía MLflow
sqlite) y `backend/tests/test_recalibration.py`
(`test_recalibration_lineage_reconstructs_full_a_to_b_to_c_chain`, ciclo
completo A→B→C vía HTTP con un forecast real y nuevo emitido por B —
avanzando el dataset del sensor con una fecha nueva vía `POST
/sensors/{sensor_id}/readings`, no reutilizando artificialmente el forecast de
A — y `test_no_lineage_event_recorded_on_failed_or_noop_recalibration`, que
verifica que una recalibración fallida o sin correcciones nuevas no registra
ningún evento). Suite completa en verde: `pytest -q` 184 (previo: 177 + 7
nuevos), `cd backend && pytest -q` 35 (previo: 33 + 2 nuevos), `frontend npm
test` 5. `ruff check`/`black --check` sobre `src`/`backend`/`tests` y `npm run
lint` (oxlint) en verde.

**Microajustes de robustez (2026-09-06), sobre la misma rama, PR #183 sin
mergear:** se detectó que `RecalibrationLineage` podía construirse y
registrarse sin ninguna validación semántica (sensor inconsistente,
`source_model_id == successor_model_id`, referencias de otro predictor,
duplicadas o ausentes, `trained_through` retrocedido), y que el orden de
escritura dentro del run de MLflow permitía, en teoría, que quedara una
versión registrada sin su artefacto de linaje. Corregido:

- `RecalibrationLineage.__post_init__` valida siempre la semántica mínima
  (identificadores no vacíos, `source_model_id != successor_model_id`, al
  menos una referencia, todas del mismo sensor y del mismo `source_model_id`,
  sin duplicados, fechas/timestamps válidos, `successor_trained_through >=
  source_trained_through`, `contract_version` válido) — tanto al crear el
  evento como al reconstruirlo con `from_dict`; `LineageValidationError`
  (subclase de `ValueError`) en caso de incumplimiento.
- `feedback_references` pasó de lista a tupla (inmutable) tras
  `__post_init__`.
- `register_recalibrated_model` agrega una segunda validación cruzada
  (`sensor_id`, `successor_model_id`, `successor_trained_through`,
  `contract_version`, `pipeline_version` deben coincidir con el predictor que
  se registra), antes de abrir el run de MLflow.
- Se corrigió el orden de persistencia dentro del run: el artefacto y los
  parámetros de linaje se escriben antes de `mlflow.sklearn.log_model(...,
  registered_model_name=...)` (el paso que registra la versión), no después
  — así una versión registrada nunca queda sin su artefacto de linaje.
  `mlflow_model_version` ya no se calcula ni se graba al escribir el
  artefacto (la versión todavía no existe en ese punto): se resuelve
  dinámicamente en cada lectura (`load_recalibration_lineage`/
  `list_recalibration_lineage`) desde la versión de MLflow efectivamente
  asociada al `run_id`.
- Se corrigió además `backend/app/routers/recalibration.py`: el
  `dataset_fingerprint` del linaje debe ser texto (`str(fingerprint)`);
  `get_dataset_fingerprint` devuelve una tupla `(mtime, size)`, no un string,
  y la nueva validación de identificadores no vacíos lo detectó (el endpoint
  devolvía 400 con "dataset_fingerprint no puede estar vacío" en el flujo
  normal).

Detalle en `openspec/specs/human-feedback/spec.md` (mismo requirement,
escenarios de validación agregados) y
`docs/adr/0006-recalibracion-disparada-desde-la-ui.md` ("Microajustes
2026-09-06"). Tests agregados: 18 en `tests/test_recalibration_lineage.py`
(rechazo de cada violación semántica, inmutabilidad de `feedback_references`,
revalidación en `from_dict`), 6 nuevos en `tests/test_model_registry.py`
(persistencia/recuperación de linaje, validación cruzada contra el modelo,
ausencia de versión registrada cuando la validación falla). Suite completa en
verde: `pytest -q` 205 (previo: 184 + 21 nuevos), `cd backend && pytest -q` 35
(sin cambio de cantidad; 2 tests existentes requirieron el fix del
`dataset_fingerprint` para volver a pasar), `frontend npm test` 5. `ruff
check`/`black --check` sobre `src`/`backend`/`tests` y `npm run lint`
(oxlint) en verde.

## T-01: auditabilidad fail-closed y provenance por contenido del linaje HITL

Única mejora material resultante de la auditoría técnica final, HU5
(`human-feedback`), fase CRISP-DM de despliegue e integración experimental.
Rama `fix/hitl-lineage-auditability` desde `main` (baseline técnico
`technical-baseline-v1`, commit `f0aeaf4e363337528f417c71e798a6f1b99d6ea8`, no
movido ni recreado). Sin impacto sobre `controlled_daily_v3`, evidencia
formal, datasets, hipótesis, propósito, alcance ni arquitectura conceptual;
sin impacto sobre HU7/HU8; sin nuevos experimentos ni entrenamientos fuera de
tests.

La auditoría detectó que la carga del linaje (`load_recalibration_lineage`/
`list_recalibration_lineage`) colapsaba a `None`/omisión silenciosa
situaciones distintas: una versión histórica que legítimamente nunca declaró
linaje, un artefacto ausente, un fallo de descarga, JSON corrupto o una
violación semántica eran indistinguibles. Además, `dataset_fingerprint`
(`(mtime, size)`) servía como única "identidad" del dataset usado en una
recalibración, sin identificar realmente su contenido.

Corregido:

- **Lectura fail-closed:** el marcador canónico de que una versión *declaró*
  linaje pasa a ser los parámetros indexables ya persistidos
  (`recalibration_id`, `source_model_id`, `successor_model_id`,
  `dataset_fingerprint`), no la mera presencia descargable del artefacto. Sin
  esos parámetros → `None` (retrocompatible). Con esos parámetros pero sin
  poder reconstruir el linaje (artefacto ausente, error de descarga, JSON
  inválido, semántica inválida, inconsistencia con esos mismos parámetros) →
  `LineageValidationError` con contexto (versión, `run_id`), nunca `None`.
  `list_recalibration_lineage` propaga el error en vez de devolver una cadena
  parcial que aparente estar completa.
- **Versionado del esquema de linaje:** nuevo campo `lineage_version`
  (constantes `LINEAGE_VERSION_1`/`LINEAGE_VERSION_2`/
  `CURRENT_LINEAGE_VERSION` en `src/human_feedback/lineage.py`), deliberadamente
  distinto de `contract_version` (que sigue versionando el contrato de
  modelado del predictor, sin relación con el linaje). `LINEAGE_VERSION_1` es
  la forma histórica sin `dataset_sha256`; `LINEAGE_VERSION_2` (la que usan
  las recalibraciones nuevas) lo exige. `from_dict` nunca reinterpreta un
  evento `LINEAGE_VERSION_1` persistido como si cumpliera la versión nueva.
- **`dataset_sha256`:** SHA-256 (hex minúscula, 64 caracteres) del contenido
  binario exacto del dataset usado en cada recalibración nueva, calculado con
  lectura incremental (`compute_dataset_sha256`, sin cargar el archivo
  completo en memoria) sobre la ruta que expone el nuevo
  `data_ingestion.storage.get_dataset_path`. `dataset_fingerprint` (`(mtime,
  size)`) no se reemplaza — sigue siendo solo la clave económica de
  caché/invalidación en `execute_configured_pipeline`; el hash se calcula una
  sola vez por recalibración, no en cada lectura del dataset.

Detalle en `openspec/specs/human-feedback/spec.md` (mismo requirement,
escenarios agregados) y `docs/adr/0006-recalibracion-disparada-desde-la-ui.md`
("Actualización 2026-09-06 — T-01"). Tests agregados/ampliados: 7 nuevos en
`tests/test_recalibration_lineage.py` (compatibilidad con eventos históricos
sin `dataset_sha256`, aceptación de eventos nuevos válidos, rechazo de
`dataset_sha256` ausente/malformado, rechazo de `lineage_version` no
soportada, `compute_dataset_sha256` coincide con el contenido real y
distingue archivos de igual tamaño/`mtime` pero contenido distinto), 10
nuevos en `tests/test_model_registry.py` (carga histórica sin declarar
linaje → `None`, fail-closed ante artefacto ausente/error de descarga/JSON
corrupto/semántica inválida, `list_recalibration_lineage` propaga el error en
vez de una cadena parcial), y `backend/tests/test_recalibration.py`
(`test_recalibration_lineage_reconstructs_full_a_to_b_to_c_chain` ampliado
para verificar `lineage_version`/`dataset_sha256` de A→B y B→C contra el
contenido real del dataset en cada ciclo). Suite completa en verde: `pytest
-q` 226 (previo: 205 + 21 nuevos), `cd backend && pytest -q` 35 (sin cambio de
cantidad), `frontend npm test` 5. `ruff check`/`black --check` sobre
`src`/`backend`/`tests` y `npm run lint` (oxlint) en verde. PR no creada
todavía (pendiente de revisión dirigida).

**Microajuste (2026-09-06), sobre la misma rama:** se detectó que
`_run_declares_lineage` usaba `all(...)` sobre los cuatro parámetros
canónicos para decidir si una versión "declaraba" linaje — dejando sin
cubrir el caso de una persistencia **parcial** (algunos parámetros, no
todos), que se clasificaba incorrectamente como "histórico sin linaje"
(`None`) en vez de fallar explícitamente. Corregido separando dos
conjuntos: marcadores de declaración (`recalibration_id`, `source_model_id`,
`successor_model_id`, `lineage_version` — presencia de **cualquiera**, no de
todos; `dataset_fingerprint` excluido deliberadamente por no ser específico
de una recalibración HITL) y parámetros obligatorios (los cuatro
originales, exigidos en conjunto una vez que ya se decidió que el run
declara linaje). `register_recalibrated_model` ahora también loguea
`lineage_version` como parámetro MLflow indexable. Detalle en
`openspec/specs/human-feedback/spec.md` (párrafo "Lectura fail-closed"
reescrito) y `docs/adr/0006-recalibracion-disparada-desde-la-ui.md`
("microajuste: detección de declaraciones parciales de linaje").

Tests agregados en `tests/test_model_registry.py`: ningún marcador → `None`;
solo `dataset_fingerprint` → `None`; solo `recalibration_id` → error; solo
`source_model_id`/`successor_model_id` (parametrizado) → error; combinación
parcial de marcadores → error; evento V1 legítimo sin el parámetro
`lineage_version` (simulando la implementación anterior) → se recupera
correctamente; `list_recalibration_lineage` propaga el error ante
declaración parcial. Suite completa en verde: `pytest -q`
(`tests/test_model_registry.py` 41, previo 33 + 8 nuevos; el resto sin
cambios), `cd backend && pytest -q` 35, `frontend npm test` 5. `ruff
check`/`black --check` sobre `src`/`backend`/`tests` y `npm run lint`
(oxlint) en verde. PR sigue sin crearse.

## Revisión dirigida T-01: R1 y R2 (sobre la misma rama)

Revisión dirigida encontró dos P2 sobre T-01, ambos resueltos sobre
`fix/hitl-lineage-auditability` (HEAD de partida
`7564787fd11d79a9c82d066caca668aedbe5701b`), sin PR creada todavía. Sin
impacto sobre `controlled_daily_v3`, evidencia formal, datasets, modelos,
protocolo experimental, frontend ni endpoints públicos; sin nuevos
experimentos; `technical-baseline-v1` sin mover, `technical-baseline-v2` sin
crear.

**R1 — consistencia entre el parámetro MLflow `lineage_version` y el
artefacto.** La comparación existente no cruzaba `lineage_version` (solo los
otros 4 parámetros), dejando pasar: parámetro V2 + artefacto V1, parámetro V1
+ artefacto V2, y parámetro ausente + artefacto V2 (este último se
interpretaba incorrectamente como V1 histórico). Corregido con
`_validate_lineage_version_consistency` en
`src/human_feedback/model_registry.py`. Además, `RecalibrationLineage.from_dict`
(`src/human_feedback/lineage.py`) ahora normaliza cualquier estructura de
artefacto inválida (no-dict, `{}`, listas, escalares, referencias de feedback
mal formadas, campos ausentes/inesperados) a `LineageValidationError`, nunca
a `TypeError`/`KeyError`/`AttributeError` sin envolver; los mensajes incluyen
versión del modelo y `run_id`.

**R2 — instantánea consistente entre el `DataFrame` recalibrado y
`dataset_sha256`.** El router cargaba el dataset y por separado reabría el
mismo archivo para hashearlo — dos lecturas independientes que podían ver
contenido distinto si el archivo cambiaba entre medio. Se agregó
`DatasetSnapshot`/`load_dataset_snapshot` en `src/data_ingestion/storage.py`:
una única lectura de bytes (verificando `(mtime, size)` antes/después,
abortando con `RuntimeError` si cambió), SHA-256 incremental sobre esos
mismos bytes, y `DataFrame` construido desde ese contenido en memoria (no una
segunda apertura del archivo). `cache_fingerprint` sigue siendo exactamente
`(mtime, size)`, sin cambios de rol. `backend/app/pipeline.py` gana
`load_dataset_snapshot_or_raise` (usado solo por `POST /recalibrate/{sensor_id}`,
traduce `RuntimeError` a `ValueError` → HTTP 400 antes de llegar a
`register_recalibrated_model`); `POST /forecast/{sensor_id}/run` no cambia
(sigue usando `load_dataset_or_raise`, no necesita el hash).

Detalle en `openspec/specs/human-feedback/spec.md` (mismo requirement,
escenarios agregados) y `docs/adr/0006-recalibracion-disparada-desde-la-ui.md`
("revisión dirigida T-01: R1 y R2"). Tests agregados: 15 en
`tests/test_recalibration_lineage.py` y `tests/test_model_registry.py`
combinados (estructuras inválidas → `LineageValidationError`; los tres cruces
incompatibles de `lineage_version`; V1 sin parámetro y V2 con parámetro
coincidente siguen aceptándose; parámetro no soportado; contexto con versión
y `run_id`; propagación desde `list_recalibration_lineage`), 6 nuevos en
`tests/test_storage.py` (`DatasetSnapshot` válida y consistente, SHA
coincide con hash manual del archivo, distingue contenidos distintos, aborta
ante sustitución del archivo durante la lectura, dataset faltante), 1 nuevo
en `backend/tests/test_recalibration.py` (aborta y no registra sucesor
cuando la captura del dataset falla). Suite dirigida
(`pytest -q tests/test_recalibration_lineage.py tests/test_model_registry.py
backend/tests/test_recalibration.py`) → 109 passed. Suite completa en verde:
`pytest -q` 262 (previo 234 + 28 nuevos: 9 en `test_model_registry.py`, 15 en
`test_recalibration_lineage.py`/`test_model_registry.py` combinados por los
cruces de versión, y 6 en `test_storage.py`), `cd backend && pytest -q` 36
(previo 35 + 1), `frontend npm test` 5. `ruff check`/`black --check` sobre
`src`/`backend`/`tests` y `npm run lint` (oxlint) en verde. `git diff --check
main...HEAD` sin hallazgos.

## Protocolo controlled_daily_v4_external_pergamino documentado (2026-09-08)

Documentación formal, exclusivamente read-only sobre el repositorio (sin implementación de
código ni ejecución de experimentos), del protocolo derivado de ADR-0010 para una futura
iteración multimodelo sobre un dataset externo de reanálisis agroclimático. Pergamino queda
seleccionado como segunda fuente/sitio principal de esa iteración (ERA5-Land + NASA POWER,
2015–2025, sin faltantes estructurales); Balcarce queda reservado como
`FUTURE_GEOGRAPHIC_VALIDATION`, sin participar todavía. Artefactos creados:
`docs/adr/0011-protocolo-controlled-daily-v4-external-pergamino.md` (decisión),
`docs/research/controlled-daily-v4-external-pergamino-protocol.md` (protocolo reproducible
completo: etiquetas, fronteras causales, nested CV, selección estadística, métricas,
baselines, costo computacional), `docs/research/controlled-daily-v4-external-pergamino-manifest.yaml`
(plantilla de provenance, estado `PROTOCOL_ONLY`, con campos `PENDING_BEFORE_EXECUTION` donde
corresponde y `PENDING_CONFIRMATION` para licencias/fecha de adquisición no verificables desde
el repositorio) y `openspec/changes/add-controlled-daily-v4-external-pergamino/` (propuesta
OpenSpec con delta de `experiment-runner` en formato Given/When/Then, sin tocar el spec
canónico vigente de `controlled_daily_v3`). Implementación del runner y ejecución de
cualquier experimento quedan pendientes, fuera de alcance de esta tarea. Holdout 2024–2025
permanece completamente cerrado; `controlled_daily_v3`, `scientific-baseline-v3`,
`technical-baseline-v1` y `technical-baseline-v2` sin alteración ni movimiento.

## Runner de Etapa A de controlled_daily_v4 implementado, sin ejecutar (2026-09-08)

Implementación de código (`src/experiment_runner/controlled_daily_v4/`, 16 módulos) del runner
de la Etapa A del protocolo `controlled_daily_v4_external_pergamino` (ADR-0011), con entorno
experimental reproducible dedicado (`docker/experiment-v4/`, versiones exactas fijadas y
validadas: Python 3.11.16, NumPy 2.4.6, SciPy 1.17.1, pandas 3.0.5, PyArrow 25.0.1,
scikit-learn 1.9.0). Cubre: validación de provenance de los dos CSV de Pergamino, ingesta y
alineación causal ERA5-Land/NASA POWER, target estricto `<` con `P20_train` fold-local, lags y
rolling causales, los cuatro candidatos de ADR-0010 (LR/RF/HGB/Soft Voting) balanceados vía
`sample_weight` sin `class_weight`, nested `TimeSeriesSplit(n_splits=3, gap=3)` outer/inner con
invariante temporal verificado, MCC global sobre OOF concatenado con convención explícita de
`NaN` en casos degenerados, moving block bootstrap pareado y segment-aware, selección de
familia (ganador estable / `SIN_GANADOR_ESTABLE` con desempate por simplicidad predeclarada),
congelamiento final de hiperparámetros, serialización atómica de artefactos (sin escribir en
`docs/research/` ni en MLflow) y una CLI que solo acepta `--stage A`. 67 tests nuevos,
exclusivamente con datos sintéticos (nunca leen los CSV reales de Pergamino): 67 passed en el
entorno reproducible dedicado (~131s); suite completa del repositorio (260 preexistentes + 67
nuevos) también en verde (327 passed) sin regresiones, en un entorno separado con todas las
dependencias del proyecto. `ruff check`/`black --check` limpios sobre `src`/`backend`/`tests`
completos; `git diff --check` sin hallazgos. Documentado en
`openspec/changes/implement-controlled-daily-v4-stage-a/` (nuevo *change*, sin alterar
retrospectivamente `add-controlled-daily-v4-external-pergamino`, ya mergeado). **No se ejecutó
la Etapa A real sobre Pergamino** (solo datos sintéticos en tests); **no se implementaron las
Etapas B ni C**; el holdout 2024–2025 permanece completamente cerrado; no se integró MLflow (ni
se registró nada en el servidor compartido); `controlled_daily_v3`, `scientific-baseline-v3`,
`technical-baseline-v1` y `technical-baseline-v2` sin alteración ni movimiento; no se creó
ningún PR.

## Correcciones de la revisión técnica dirigida del runner de Etapa A (2026-09-08)

Revisión técnica dirigida sobre el delta `main...feat/controlled-daily-v4-stage-a-runner`
(HEAD `113871e`) y corrección integral de sus hallazgos, sin ejecutar el experimento real. La
revisión encontró tres contradicciones con el protocolo aprobado, todas ya resueltas:

1. **Soft Voting con ponderaciones dependientes.** `VotingClassifier` solo propaga un único
   `sample_weight` a los tres sub-estimadores, de modo que cualquier combinación mixta de modos
   de balanceo se ajustaba como si fuera toda sin ponderar (7 de 8 combinaciones degradadas), y
   el cuarto candidato dejaba de componerse con las configuraciones seleccionadas de forma
   independiente por familia. Reemplazado por un Soft Voting propio (`SoftVotingClassifier`
   sobre `SelfWeightingClassifier`), donde cada base calcula su `sample_weight` dentro de su
   propio `fit` y el ensamble promedia `predict_proba` con alineación explícita de clases.
2. **Bootstrap que no era moving-block.** Los bloques eran una partición fija no solapada, con
   residuos más cortos que 30 días, y el pool se mezclaba entre segmentos outer, de modo que
   una réplica podía sobrerrepresentar un fold (338–1148 filas de un segmento de 728).
   Reimplementado con bloques solapados de largo exacto por segmento, remuestreo independiente
   que repone el tamaño original de cada segmento, fallo explícito ante segmentos más cortos
   que el bloque y contabilidad de réplicas descartadas con su motivo.
3. **Features y target calculados sobre 2015–2025.** El pipeline los construía sobre toda la
   serie y filtraba después, contra la letra de la sección 5 del protocolo. Ahora la serie se
   recorta a la ventana autorizada más la historia causal mínima antes del constructor de
   features. No existía fuga —los centinelas extremos en 2023–2025 no alteraban ninguna
   salida— pero sí violación del contrato.

Además se corrigieron carencias de evidencia: los artefactos JSON emitían tokens `NaN`
(inválidos como JSON) y no persistían ninguna métrica más allá del MCC de selección;
`per_fold_mcc` quedaba vacío; `environment.json` era un placeholder. Ahora la serialización usa
`allow_nan=False` con normalización recursiva y estado explícito por métrica, se agrega
`metrics.json` (métricas del §12 globales y por outer fold, calibración de 10 bins, motivos de
indefinición), el diagnóstico del §8.4 (mediana/Q1/Q3/IQR con método de percentil declarado) y
la captura real del entorno. Los hallazgos menores también quedaron resueltos: `.dockerignore`
hermético más `pip check` como compuerta del build (antes fallaba por un `*.egg-info` local que
entraba al contexto), transitivas fijadas en `constraints.txt`, parámetros de grilla realmente
conectados al estimador, regularización efectiva L2 verificada por API del estimador y
registrada en los artefactos, equivalencia práctica que exige que el intervalo pareado
*incluya* el cero, marcado explícito de corridas no normativas, barrido AST de MLflow ampliado
a los 16 módulos y a la suite completa, y reemplazo de aserciones tautológicas o casi vacuas.

Esquema de artefactos elevado a `controlled_daily_v4_stage_a.v2`. **144 tests** dirigidos en el
entorno reproducible (exclusivamente sintéticos, sin warnings); **404 passed** en la suite
completa del repositorio, sin regresiones; `ruff check` y `black --check` limpios sobre
`src`/`backend`/`tests`; `git diff --check` sin hallazgos; build del contenedor experimental
repetible desde cero con `pip check` en verde. Se mantuvieron todas las restricciones: **no se
ejecutó la Etapa A real sobre Pergamino**, no se accedió a Pergamino ni a Balcarce, no se
procesó 2023, el holdout 2024–2025 permanece cerrado, no se usó MLflow compartido,
`controlled_daily_v3` y la evidencia formal v3 sin alteración, ningún tag movido ni creado, y
no se creó ningún PR. Queda pendiente una última revisión dirigida sobre el delta corregido
antes de abrir la PR.

## Auditoría externa post-merge del runner de Etapa A: H-01 a H-04 corregidos (2026-09-12)

Auditoría externa adversarial sobre `b8575f3` (merge de PR #188, arriba). Cuatro hallazgos
confirmados, todos corregidos con fixtures sintéticas, en rama
`fix/controlled-daily-v4-stage-a-validation`, sin ejecutar la Etapa A real:

- **H-01 (identidad de las entradas):** `validate_pergamino_provenance()` aceptaba hashes
  esperados opcionales (`None` por defecto en la CLI) y nunca contrastaba coordenadas. Se agrega
  `manifest_reference.py` (lee hash/coordenadas por proveedor directamente del manifiesto
  versionado, nunca calculados de los archivos recibidos) y el modo explícito
  `--input-mode {scientific,synthetic}` (por defecto `scientific`; nunca se degrada
  automáticamente a sintético ante un fallo de validación formal). Metadatos de encabezado
  inválidos generan errores controlados en vez de excepciones sin manejar.
- **H-02 (calendario y horizonte):** el inner join podía ocultar días faltantes y `shift(-3)`
  no garantizaba coincidir con `target_timestamp = feature_timestamp + 3 días` si la serie tenía
  huecos; un día con 23 horas, o con una hora duplicada que ocultara otra ausente, pasaba sin
  detectarse. `features.validate_continuous_daily_calendar` (invocada desde
  `build_feature_frame`) exige continuidad/unicidad/orden del calendario, cobertura horaria
  completa (`n_obs`/`n_unique_hours`, nuevas columnas de `aggregate_era5_daily`) y valores
  finitos en las columnas requeridas, dentro del rango recibido — nunca imputa, rechaza con
  diagnóstico preciso.
- **H-03 (aislamiento de A desde la ingesta):** `provenance.py` agregaba humedad de suelo de
  todo el archivo (`aggregate_era5_daily` sobre 2015-2025 completo) y contaba centinelas `-999`
  de NASA POWER también sobre el archivo completo, de modo que un cambio de valor en 2024
  (fuera de la Etapa A) podía tumbar la validación de identidad. Ahora la identidad/provenance
  es exclusivamente estructural (hash, encabezados, columnas, timezone, cobertura de fechas vía
  `extract_era5_daily_dates`); el análisis de valores queda confinado a la ventana ya recortada
  por etapa.
- **H-04 (validación previa del entorno):** el entorno se capturaba recién al escribir
  artefactos, después de entrenar, y `normative_deviations()` solo miraba semilla/réplicas.
  `environment.validate_environment()` contrasta Python y las 7 dependencias directas contra
  `docker/experiment-v4/constraints.txt` (vía `manifest_reference.py`) ANTES del primer ajuste;
  en modo científico aborta con código de salida dedicado (4) ante incompatibilidad o paquete
  ausente, sin llegar a importar el runner de entrenamiento. La condición normativa ahora
  considera modo, entorno y desviaciones de semilla/réplicas. Se agrega un job de CI dedicado
  (`experiment-v4-container`) que construye la imagen fijada y ejecuta allí la suite sintética.

**9 archivos de test nuevos/actualizados**, incluidos dos archivos nuevos
(`test_controlled_daily_v4_calendar_integrity.py`,
`test_controlled_daily_v4_environment_validation.py`); suite `controlled_daily_v4` completa en
verde; `ruff check`/`black --check` limpios sobre los archivos afectados; contenedor
`docker/experiment-v4` reconstruido desde cero con `pip check` en verde y la suite sintética
ejecutada dentro de él con éxito. No se ejecutó la Etapa A real, no se accedió a Pergamino ni a
Balcarce, `controlled_daily_v3` sin alteración, ningún tag movido, y no se creó ningún PR.

## Revisión externa del paquete de la corrección: 3 correcciones pendientes en H-02/H-03 (2026-09-12)

La entrada anterior declaró H-02 y H-03 "corregidos" de forma prematura: una revisión externa
sobre el paquete `controlled-daily-v4-stage-a-fix-review_20260912_222919.zip` reprodujo, con
datos exclusivamente sintéticos, tres defectos que esa corrección no cubría todavía:

- **H-03, aislamiento incompleto en la CLI:** `provenance.py` quedó correctamente acotado a lo
  estructural, pero `cli.py` seguía invocando `aggregate_era5_daily(era5_df)` y
  `replace_missing_sentinel(nasa_df)` sobre el CSV completo (2015-2025) **antes** de que
  `stage_a_runner.py` recortara la serie ya unida — una prueba instrumentada observó una media
  de humedad calculada para 2024-01-01 durante la preparación de la Etapa A (sin entrenar
  ningún modelo). Corregido agregando `features.compute_stage_window_bounds()` (única fuente de
  verdad para la ventana autorizada más la historia causal mínima, reutilizada también por
  `restrict_to_stage_window`) e `ingestion.restrict_era5_hourly_to_window()` /
  `restrict_nasa_power_daily_to_window()`, invocadas en `cli.py` **antes** de agregar/convertir
  el centinela. Regresión: `test_cli_never_aggregates_or_processes_values_outside_the_authorized_window`
  (instrumenta `aggregate_era5_daily`/`replace_missing_sentinel` con CSV sintéticos que cubren
  fechas de A, B y C; confirma que ninguna de las dos funciones recibe una fila fuera de la
  ventana, en modo `synthetic`). Se agrega también
  `test_cli_scientific_mode_still_rejects_any_identity_change_after_isolation_fix` para
  confirmar que este recorte no debilitó H-01.
- **H-02, cobertura de lecturas horarias válidas incompleta:** `n_obs == 24` y
  `n_unique_hours == 24` no bastan -- un día con 24 filas y 24 horas distintas puede tener una
  única lectura de humedad ausente/no finita, invisible porque `groupby(...).mean()` la ignora
  en silencio (`skipna=True`) y produce un promedio "completo" a partir de solo 23 lecturas.
  Reproducido con un CSV ERA5 sintético construido exactamente así. Corregido agregando
  `n_finite_<columna>` por columna de humedad de suelo en `aggregate_era5_daily`, y una
  comprobación en `features.validate_continuous_daily_calendar` exclusiva de la profundidad
  efectivamente evaluada (`depth_column`) — nunca de las profundidades excluidas ni de la otra
  profundidad (principal/sensibilidad) que no participa de esa corrida. Regresiones: lectura
  ausente y lectura infinita (`test_day_with_24_rows_and_24_hours_but_one_nan_reading_is_rejected`,
  `test_day_with_an_infinite_hourly_reading_is_rejected`), verificación de que el rechazo ocurre
  antes de cualquier `fit_estimator`
  (`test_missing_hourly_reading_rejection_happens_before_any_model_fit`), y de que el control
  está acotado a la profundidad analizada
  (`test_finite_reading_check_only_applies_to_the_depth_actually_analyzed`).
- **Columnas NASA ausentes sin control:** la ausencia de una columna requerida (p. ej. RH2M)
  producía un `KeyError` sin manejar dentro de `load_nasa_power_daily_raw`, antes de que
  `provenance.py` pudiera devolver su diagnóstico de columnas faltantes. Corregido validando las
  columnas requeridas dentro de `load_nasa_power_daily_raw` y levantando `ValueError` con el
  detalle de las columnas ausentes -- ya cubierto por el `except` existente de `provenance.py`,
  sin capturas genéricas de excepciones. Regresión por CLI:
  `test_cli_reports_a_controlled_error_when_a_required_nasa_column_is_missing` (exit code 3, sin
  traceback, sin escribir artefactos).

También se corrigió un comentario impreciso (`1e-4°` de tolerancia de coordenadas equivale a
~11 m en el ecuador, no a ~1 cm) y se actualizó la documentación de `ingestion.py` para dejar de
sugerir que la sola existencia de las funciones de agregación implicaba aislamiento por etapa.

Verificación real ejecutada: suite `tests/test_controlled_daily_v4_*.py` completa en verde
(**176 passed**, 8 tests nuevos sobre la base de 168); suite completa `tests/` en verde (**438
passed**); suite sintética dentro del contenedor `docker/experiment-v4` reconstruido desde cero
con estos cambios (`pip check` en verde, **176 passed** dentro del contenedor, idéntico al
resultado local); `ruff check`/`black --check`/`git diff --check` limpios sobre el alcance
afectado. No se leyó ningún CSV real de Pergamino/Balcarce, no se ejecutó A real ni B ni C, no se
usó MLflow compartido, `controlled_daily_v3` sin alteración, ningún tag movido, y no se hizo
push, PR ni merge.

## H-05/H-06: reproducibilidad/trazabilidad de la Etapa A y documentación coherente (2026-09-13)

Rama `fix/controlled-daily-v4-reproducibility-docs`, base `origin/main`
(`be6a5559100637180ee1c3dede4e99e24455474c`, PR #189 ya mergeado con H-01 a
H-04). Diagnóstico contra el código real de `src/experiment_runner/controlled_daily_v4/`
y contra el manifiesto de provenance, que ya anticipaba estos campos como
`PENDING_BEFORE_EXECUTION` (`repository_state.commit`,
`execution_artifacts.folds.inner_fold_boundaries`, `warnings_log`,
`future_versioned_artifacts.daily_derived_dataset_sha256`) sin que el runner
los completara todavía.

**H-05 (reproducibilidad/trazabilidad):**

- **Identidad de código** — pendiente, ahora implementado: `code_identity.py`
  (`capture_code_identity`) captura SHA completo + árbol limpio/modificado vía
  `git`, con fallback explícito a un archivo de metadatos embebido en el build
  (`.build_commit`, escrito por `docker/experiment-v4/Dockerfile` a partir de
  `--build-arg GIT_COMMIT=$(git rev-parse HEAD)`) cuando no hay `.git` en
  tiempo de ejecución (caso contenedor). Si ninguna fuente está disponible,
  se declara `available=False` explícitamente — nunca se inventa un commit.
  Persistido en `code_version.json`, capturado antes de entrenar (igual que
  el entorno). Verificado dentro del contenedor reconstruido: cae al
  fallback (`source=build_metadata_file`, `dirty=None`), nunca asume estado
  limpio.
- **Huella del conjunto derivado** — pendiente, ahora implementado:
  `dataset_fingerprint.py` calcula SHA-256 sobre una representación estable
  del conjunto elegible de la Etapa A (columnas fijas, orden por
  `feature_timestamp`, timestamps ISO, floats con formato fijo) — nunca
  `hash()` de Python, nunca sobre B/C. Persistido en `dataset_fingerprint.json`.
- **Folds internos y de congelamiento** — pendiente, ahora implementado:
  `run_stage_a` calcula los folds internos una única vez por outer fold
  (antes se recalculaban, idénticos, tres veces por familia) y los expone en
  `inner_folds_by_outer`; `FrozenConfig` ahora expone también los folds de la
  segunda pasada de congelamiento. Persistidos en `inner_fold_boundaries.json`
  y `freeze_fold_boundaries.json` — mismos folds consumidos por el
  entrenamiento, sin lógica paralela.
- **Advertencias con contexto** — pendiente, ahora implementado:
  `warnings_capture.collect_context_warnings` envuelve cada ajuste (familia,
  outer fold, fase) y deduplica por `(contexto, categoría, mensaje)` con
  conteo. Persistido en `warnings.json`, sin volcar datasets.
- **Distinción configuración congelada vs. estimador en memoria** —
  documentado explícitamente en `artifacts.py`/`freezing.py`: `frozen_config.json`
  persiste familia + hiperparámetros + detalle verificado por API (nunca el
  estimador serializado); el estimador ajustado en memoria se reconstruye
  reentrenando con la misma configuración sobre el conjunto identificado por
  `dataset_fingerprint.json`.
- **Entorno, entradas y distinción científica/sintética** — ya resueltos por
  H-01/H-04 (PR #189); sin cambios adicionales, solo verificados en
  compatibilidad.
- **Bump de esquema:** `ARTIFACT_SCHEMA_VERSION` `v2` → `v3` (nuevos
  artefactos; `frozen_config.json` cambia de forma).

**H-06 (documentación coherente):**

- `docs/research/controlled-daily-v4-external-pergamino-protocol.md`,
  sección 7.5: corregida la descripción de `VotingClassifier(voting='soft')`
  (no implementado) por la combinación propia de probabilidades
  (`SoftVotingClassifier`), con la justificación real (balanceo independiente
  por familia, que `VotingClassifier` no soporta).
- Sección 15 ("Entorno reproducible"): ya no describe el entorno como no
  fijado — refleja `docker/experiment-v4/constraints.txt` +
  `environment.validate_environment()`, y distingue lo ya validado
  (tests/CI sintético) de lo pendiente (commit de la corrida científica real).
- ADR-0011: tres referencias desactualizadas a la ausencia de entorno fijado
  (Decisión, Consecuencias, Condiciones previas) marcadas `~~tachado~~` con
  nota "Actualización (2026-09-12)", siguiendo el patrón ya usado en
  ADR-0004/ADR-0006 — no se reescribe la decisión histórica.
- `docker/experiment-v4/Dockerfile`: documentado el mecanismo de
  `--build-arg GIT_COMMIT`; `.github/workflows/ci.yml` actualizado para
  pasarlo (`$GITHUB_SHA`) en el job `experiment-v4-container`.
- Manifiesto de provenance: notas de `execution_artifacts` y
  `future_versioned_artifacts` actualizadas para distinguir "mecanismo ya
  implementado" de "valor pendiente de una ejecución real" — sin completar
  ningún campo con datos inventados.
- ~~Sin cambios necesarios: explicación del gap/OOF (sección 8, ya correcta)~~
  **Corrección (2026-09-13):** era incorrecta. Una revisión externa posterior
  reprodujo, con artefactos sintéticos, que los tres `outer_val` quedan
  calendario-adyacentes entre sí (ej.: uno termina 13/04, el siguiente
  comienza 14/04) — `gap=3` opera **dentro** de cada fold (fin de
  `outer_train` → comienzo de su propio `outer_val`), no entre segmentos
  `outer_val` sucesivos. La sección 8 del protocolo conflacionaba ambas
  nociones para justificar la prohibición de bloques de bootstrap que crucen
  segmentos. Corregido: la prohibición es una regla de remuestreo
  predeclarada y segment-aware, independiente de la distancia calendario
  real entre segmentos; la purga por `gap=3` sigue siendo exclusivamente
  intra-fold. Sin cambios en splits, sampler, longitud de bloque, réplicas,
  semillas ni ninguna decisión estadística — solo en la explicación.
- Sin cambios necesarios: descripción de VotingClassifier en ADR-0010 (no la
  mencionaba), README (no tiene referencias a v4), estado de A/B/C (ya
  correctamente `PENDING`).
- Manifiesto: los pendientes de licencia/fecha de adquisición de Pergamino
  (`PENDING_CONFIRMATION`) se dejan explícitamente sin resolver — no hay
  evidencia disponible en este repositorio para confirmarlos ni descartarlos;
  siguen bloqueando una futura ejecución científica real, no esta tarea.

**Trazabilidad — capítulo 3 (arquitectura e implementación):**

| Componente | Responsabilidad | Ruta | Evidencia de verificación |
|---|---|---|---|
| `code_identity.py` | Identidad de código (SHA + limpio/modificado) antes de entrenar, con fallback de build sin `.git` | `src/experiment_runner/controlled_daily_v4/code_identity.py` | `tests/test_controlled_daily_v4_code_identity.py` (5 tests), verificado dentro y fuera del contenedor |
| `dataset_fingerprint.py` | Huella determinista del conjunto diario elegible de la Etapa A | `src/experiment_runner/controlled_daily_v4/dataset_fingerprint.py` | `tests/test_controlled_daily_v4_dataset_fingerprint.py` (6 tests) |
| `warnings_capture.py` | Captura de advertencias de ajuste con contexto, deduplicadas | `src/experiment_runner/controlled_daily_v4/warnings_capture.py` | `tests/test_controlled_daily_v4_warnings_capture.py` (4 tests) |
| Folds internos/congelamiento expuestos | Correspondencia entre folds registrados y consumidos | `stage_a_runner.py`, `freezing.py` (campo `folds` de `FrozenConfig`) | `tests/test_controlled_daily_v4_reproducibility_artifacts.py` (10 tests) |

Implementación terminada: los cinco componentes de la tabla, integrados en la
CLI (`cli.py`) y en el runner (`stage_a_runner.py`). Diseño previsto, no
implementado en esta tarea: ejecución científica real de la Etapa A (fuera de
alcance), Etapas B/C.

Verificación real ejecutada: `tests/test_controlled_daily_v4_*.py` completa
en verde (**201 passed** — 176 previos + 25 nuevos); suite raíz `tests/`
completa en verde (**463 passed**); suite sintética dentro del contenedor
`docker/experiment-v4` reconstruido desde cero con `--build-arg
GIT_COMMIT=$(git rev-parse HEAD)` (**200 passed, 1 skipped** — el test que
exige `git` instalado se salta correctamente dentro del contenedor, que no lo
tiene; confirmado por separado que `capture_code_identity()` cae al fallback
de build con `dirty=None`); `ruff check`/`black --check`/`git diff --check`
limpios sobre el alcance afectado. No se ejecutó la Etapa A real, no se leyó
ningún CSV real de Pergamino/Balcarce, no se accedió a Balcarce, no se
ejecutó B ni C, no se usó MLflow compartido, `controlled_daily_v3` sin
alteración, ningún tag movido, y no se hizo commit, push, PR ni merge.

## Revisión externa del paquete H-05/H-06: 4 pendientes corregidos (2026-09-13)

Sobre el ZIP `controlled-daily-v4-reproducibility-docs-review.zip`
(SHA-256 `9214f04f876b9d6f5bd8f6e7004d8fa7309c9ea9cf32ab71b4fc992c2bb0a1d4`),
una revisión externa reprodujo, con fixtures sintéticas, cuatro defectos
concretos que esa entrega no cubría:

- **Punto 1, identidad de código en contenedor:** `.build_commit` era texto
  plano sin estado limpio/modificado (`dirty` quedaba siempre `None` dentro
  de un contenedor, marcando toda corrida en contenedor como no normativa
  aunque el checkout de origen estuviera limpio) y aceptaba cualquier texto
  no vacío como si fuera un commit (`available=True` con
  `commit="this-is-not-a-commit"`). Corregido con
  `docker/experiment-v4/build.py`: captura el SHA completo y `git status
  --porcelain` del MISMO checkout usado como contexto de build (el estado
  limpio/modificado se calcula ANTES de escribir el archivo de metadatos,
  para no autocontaminar el resultado), valida el formato del SHA contra el
  que este repositorio usa realmente (`git rev-parse --show-object-format`),
  y escribe un JSON versionado (`BUILD_IDENTITY_SCHEMA_VERSION`) que
  `code_identity.py` valida estrictamente al leer -- un commit inválido, un
  `dirty` con tipo incorrecto o una versión de esquema inesperada producen
  `available=False, source=build_metadata_invalid` explícito, nunca una
  identidad aceptada a ciegas ni `dirty=None` convertido en `False`. El
  Dockerfile ya no acepta `ARG GIT_COMMIT`; requiere `.build_identity.json`
  (falla el `COPY` si falta). CI actualizado para invocar el wrapper.
- **Punto 2, precisión de la huella del dataset:** `"%.12g"` (12 dígitos
  significativos) colisionaba valores `float64` distintos -- reproducido con
  `0.36482934020882524` vs. `0.3648293402088253`, y con `0.3` vs.
  `numpy.nextafter(0.3, 0)` (este último cambia la etiqueta de estrés
  resultante sin cambiar la huella). Corregido: cada float se serializa con
  `repr()` de Python (round-trip exacto, sin redondeo con pérdida);
  `dataset_fingerprint.json` agrega `schema_version`
  (`DATASET_FINGERPRINT_FORMAT_VERSION`, `v2`) y declara explícitamente
  `float_encoding`/`timestamp_encoding`/`cell_separator`. Toda huella `v1`
  (implícita, `ARTIFACT_SCHEMA_VERSION` `v3`) queda invalidada por este
  cambio, no comparable con una `v4`.
- **Punto 3, identidad de constraints y configuración efectiva:**
  `environment.json` no registraba la identidad del propio
  `constraints.txt` contrastado (solo el resultado de contrastarlo), y
  `resolved_config.json` no persistía la configuración experimental efectiva
  completa. Corregido: `environment.capture_constraints_identity()`
  (reutiliza `provenance.compute_sha256`, sin duplicar hashing) agrega
  `constraints_identity` (ruta + SHA-256) a `environment.json`;
  `resolved_config.json` agrega `effective_protocol_config` con el mismo
  objeto `ProtocolConfig` efectivamente pasado a `run_stage_a` (fronteras
  temporales, horizonte, gap, folds, lags, ventanas móviles, umbral, margen
  práctico, bootstrap y las tres grillas) -- no una copia manual mantenida
  aparte. La CLI no expone hoy forma de solicitar una configuración distinta
  de la efectivamente consumida (más allá de `--seed`/`--bootstrap-replicas`,
  ya reflejados), así que no existe una divergencia "solicitado vs.
  consumido" que documentar en este punto.
- **Punto 4, gap y ventanas OOF:** ver arriba, entrada "Corrección
  (2026-09-13)" sobre la sección de gap/OOF -- corregido en el protocolo
  (sección 8) y en esta misma bitácora.

`ARTIFACT_SCHEMA_VERSION` `v3` → `v4` (cambios de formato en
`dataset_fingerprint.json`, `code_version.json`, `environment.json` y
`resolved_config.json`; ver docstring de `artifacts.py`).

**Archivos nuevos/modificados en esta ronda:** `docker/experiment-v4/build.py`
(nuevo), `code_identity.py`, `dataset_fingerprint.py`, `environment.py`,
`cli.py`, `artifacts.py`, `Dockerfile`, `.gitignore`, `.github/workflows/ci.yml`,
protocolo v4 (sección 8), este archivo; 3 archivos de test extendidos
(`test_controlled_daily_v4_code_identity.py`,
`test_controlled_daily_v4_dataset_fingerprint.py`,
`test_controlled_daily_v4_reproducibility_artifacts.py`) con pruebas
dirigidas a los cuatro pendientes. El cambio completo, contra la base
`origin/main` (ambas rondas de H-05/H-06 incluidas), son **20 archivos: 12
modificados y 8 nuevos** (ver PR).

Verificación real ejecutada: pruebas dirigidas a los cuatro pendientes en
verde; suite `tests/test_controlled_daily_v4_*.py` completa (**231 passed**,
30 nuevos sobre la base de 201); suite raíz `tests/` completa (**493
passed**, 30 nuevos sobre 463); suite sintética dentro del contenedor
`docker/experiment-v4` reconstruido con `python docker/experiment-v4/build.py`
(**228 passed, 3 skipped** -- los 3 tests que exigen `git` instalado se
saltan correctamente dentro del contenedor, que no lo tiene; 228+3=231,
idéntico al total local); verificado además, manualmente, que un
`.build_identity.json` con un commit malformado produce
`available=False, source=build_metadata_invalid` dentro del contenedor (no
una identidad aceptada). `ruff check`/`black --check`/`git diff --check`
limpios sobre el alcance afectado. No se ejecutó la Etapa A real, no se leyó
ningún CSV real de Pergamino/Balcarce, no se accedió a Balcarce, no se
ejecutó B ni C, no se usó MLflow compartido, `controlled_daily_v3` sin
alteración, ningún tag movido, y no se hizo commit, push, PR ni merge.

## Corrección documental de cierre de controlled_daily_v4 y preparación de Etapas B/C (2026-09-13)

Rama `docs/controlled-daily-v4-close-out-diagnostics`, base `origin/main`
(`653dc0d1b15af87cfe2008c5b5ea5583512c1324`, sin divergencia). Diagnóstico de
cierre read-only previo (misma sesión) encontró siete inconsistencias
documentales (C-01 a C-07) entre el protocolo, el manifiesto de provenance,
el delta de spec de `add-controlled-daily-v4-external-pergamino` y el
`tasks.md` de `implement-controlled-daily-v4-stage-a` -- ninguna requería
cambiar metodología, solo corregir texto desactualizado. Corregidas en esta
entrega:

- `protocol.md`: nota de estado que se autodeclaraba `PROTOCOL_ONLY` "sin
  implementación de código" pese a citar módulos ya implementados
  (`models.py`, `environment.py`, `code_identity.py`); número de esquema de
  artefactos (`v2`) desactualizado frente al código (`v4`); nota de
  implementación agregada sobre `penalty='l2'` (equivalencia L2 verificada
  empíricamente por `test_final_estimator_details_record_effective_l2_regularization`,
  sin cambiar el requisito normativo).
- `controlled-daily-v4-external-pergamino-manifest.yaml`: nuevo bloque
  `implementation_status` que distingue código implementado/verificado
  sintéticamente de resultados experimentales reales (el campo `status:
  PROTOCOL_ONLY` se conserva, sigue siendo cierto sobre resultados);
  `repository_state.branch` corregido de una rama ya mergeada y obsoleta a
  `PENDING_BEFORE_EXECUTION`. Ninguno de los campos tocados es leído por
  `manifest_reference.py` (verificado antes de editar).
- `add-controlled-daily-v4-external-pergamino/specs/experiment-runner/spec.md`:
  nota de estado actualizada (los escenarios de Etapa A ya tienen código y
  verificación sintética; los de Etapa B/C, no) y corrección de un escenario
  que mezclaba la convención matemática `NaN` con su representación
  serializada (envelope JSON) -- sin modificar el contenido normativo
  (Given/When/Then) de ese *change* ya mergeado.
- `implement-controlled-daily-v4-stage-a/tasks.md`: conteo de tests interno
  contradictorio (67 vs. 144 dentro del mismo *change*) reconciliado sin
  reemplazar el conteo posterior de 231 de esta misma bitácora.
- `add-controlled-daily-v4-external-pergamino/tasks.md`: aclaración de que
  varias de sus tareas de código ya fueron completadas por
  `implement-controlled-daily-v4-stage-a` (y sus correcciones H-01 a H-06),
  sin marcar ninguna casilla y sin alterar el registro histórico original.

Además, preparación (sin código) del *change* OpenSpec
`implement-controlled-daily-v4-stage-b-c`: propuesta, delta de especificación
y `tasks.md` para el contrato de transferencia A→B (lectura estructural
separada de admisibilidad para una ejecución concreta), los tres baselines
del protocolo (sección 13, con acceso legítimo a las etiquetas de `train` para
la clase mayoritaria, distinguido de una fuga de etiquetas de evaluación), y
los runners de las Etapas B y C. Cuatro decisiones de diseño quedan
documentadas como explícitamente pendientes de aprobación, sin resolverse en
esta entrega, en
`docs/research/controlled-daily-v4-stage-b-c-decisiones-pendientes.md`:
segmentación del bootstrap de B; identidad del holdout y secuencia de
apertura de C (con tres estados de registro `AUSENTE`/`CONFIRMADA`/
`INDETERMINADA` -- este último bloquea todo acceso automático sin borrarse ni
reinicializarse solo -- y exigencia de `fsync` explícito para la durabilidad
de la apertura, una garantía que el mecanismo de escritura atómica ya
existente en `artifacts.py` no provee hoy); política de `--overwrite` para C;
y ubicación exacta de `depth_role`. Se corrigió además una comparación
incorrecta entre el commit del productor A y el de la ejecución consumidora
de B/C: ambos pueden coincidir o diferir legítimamente, y ninguna de las dos
relaciones certifica ni descarta nada por sí sola.

No se implementó ningún código de `src/`, `backend/`, `frontend/` ni
`tests/`; no se modificó CLI, Docker, dependencias ni CI; no se ejecutó
ningún experimento, entrenamiento, build ni suite; no se leyó ni se calculó
hash de ningún CSV real de Pergamino/Balcarce; no se accedió a MLflow
compartido ni al holdout real; `controlled_daily_v3`,
`scientific-baseline-v3`, `technical-baseline-v1` y `technical-baseline-v2`
sin alteración. `git diff --check`/`git diff --cached --check` limpios sobre
el alcance afectado (9 archivos: 6 modificados, 3 nuevos, más este archivo).
Commit `508fc24f99d3863398b61729398450cd934dfd44`; PR abierto contra `main`
desde esta rama.

## Contrato de transferencia A→B de controlled_daily_v4 (2026-09-13)

Rama `feat/controlled-daily-v4-stage-a-b-transfer-contract`, base `origin/main`
(`cb5b462c433fddf2dc459ee0671e08ed8414199e`, PR #191 ya integrado). Implementa
la parte no bloqueada del *change* OpenSpec
`implement-controlled-daily-v4-stage-b-c` (ver `tasks.md` de ese *change*, secciones
"Contrato de transferencia A→B"): lectura/validación estructural de
`frozen_config.json` y validación de admisibilidad para una ejecución concreta de
la Etapa B, ambas separadas entre sí y del runner de B (que no se implementa).

- `artifacts.py`: `frozen_config.json` agrega `schema_version` propio
  (`TRANSFER_CONTRACT_SCHEMA_VERSION`, distinto de `ARTIFACT_SCHEMA_VERSION` y de
  `DATASET_FINGERPRINT_FORMAT_VERSION`), `input_mode`, `scientific_run`,
  `depth_role`, `candidate_produced` (ausencia explícita cuando A no selecciona
  candidato, sin fabricar una configuración congelada) y una referencia a la
  evidencia ya persistida del productor (`code_identity`, resumen del
  `dataset_fingerprint`) -- todo derivado de los mismos objetos efectivos que la
  Etapa A ya calculaba, sin copiar defaults del protocolo ni inferir identidades
  de nombres de archivo.
- `config.py`: `depth_role_for_column` deriva `DEPTH_ROLE_PRIMARY` /
  `DEPTH_ROLE_SENSITIVITY_ONLY` desde `--depth`. **Decisión de este encargo**
  (Decisión 4 del *change*, ubicación de `depth_role`): se registra únicamente en
  `frozen_config.json`, deliberadamente sin duplicarse en `selection_decision.json`
  -- decisión explícita del alcance de esta entrega, no una aprobación atribuible
  a terceros.
- `transfer_contract.py` (nuevo): `load_frozen_config_contract` -- lectura
  tipada, sin entrenar ni seleccionar modelos ni abrir CSV crudos. Rechaza
  `schema_version` no reconocido (`TransferContractSchemaError`) y JSON
  inválido/campos ausentes/tipos incorrectos/valores no finitos/incoherencia
  entre `candidate_produced` y el candidato serializado
  (`TransferContractValidationError`). Admite por igual artefactos sintéticos y
  de sensibilidad -- la autorización de uso se evalúa aparte.
- `admissibility.py` (nuevo): `check_stage_b_admissibility`, independiente del
  runner de B, con contexto explícito del consumidor. Rechaza siempre como
  error duro un `depth_role` de sensibilidad; exige candidato presente; admite
  sintético→sintético sin tocar ningún artefacto científico; para una
  ejecución científica, `scientific_run=true` no basta por sí solo -- exige
  además identidad de código íntegra del productor (commit válido,
  `dirty=False`), evidencia de validación de entorno suficiente (no una
  bandera aislada), e igualdad exacta de huella entre el entrenamiento
  autorizado de B y el conjunto derivado de A (mismo período). Realiza **dos**
  verificaciones de commit, deliberadamente distintas y no sustituibles entre
  sí: **(a)** consistencia interna entre `frozen_config.json` y
  `code_version.json` del mismo directorio del productor (misma corrida); y
  **(b)** compatibilidad productor-consumidor, una comparación real entre el
  commit histórico de A y el commit de la ejecución consumidora de B (recibido
  explícitamente en `consumer_code_identity`, nunca calculado aquí) -- si
  difieren y no hay política de compatibilidad documentada, se rechaza por
  "compatibilidad no acreditada". Ver la corrección de 2026-09-13 (revisión
  externa) más abajo: una versión anterior de este módulo omitía (b) por
  completo.
- `cli.py`: `scientific_run` se calcula una única vez y se reutiliza tanto en
  `resolved_config.json` como en el contrato de transferencia, sin duplicar la
  lógica.

Pruebas nuevas, exclusivamente sintéticas: `tests/test_controlled_daily_v4_transfer_contract.py`
y `tests/test_controlled_daily_v4_admissibility.py` (ver conteo final y
corrección tras revisión externa en la entrada siguiente de esta misma
bitácora). `ruff check`/`black --check`/`git diff --cached --check` limpios
sobre el alcance afectado.

No se implementaron baselines, runners de las Etapas B/C, ledger del holdout ni
mecanismos de apertura del holdout -- quedan pendientes, según el alcance
explícito de este encargo. No se accedió a ningún CSV real de
Pergamino/Balcarce/holdout, no se ejecutó ningún experimento científico real ni
se usó MLflow compartido, y `controlled_daily_v3`, la evidencia histórica, los
tags de baseline, `backend/`, `frontend/` y `human_feedback/` quedan sin
alteración. No se hizo merge ni se habilitó auto-merge.

## Corrección de admisibilidad del contrato A→B tras revisión externa (2026-09-13)

Revisión externa del commit `17a3a214b0e32f341820a41c00ab124ca6bf9091` (PR
#192) reprodujo cuatro defectos que la entrega anterior de esta misma rama
dejaba pasar indebidamente. Los cuatro quedan corregidos en este commit
adicional, con regresión propia cada uno:

1. **Coherencia de modo y profundidad** (`transfer_contract.py`): la lectura
   estructural ahora rechaza explícitamente `input_mode=synthetic` con
   `scientific_run=true` (incoherencia de modo), y `depth_role` que no
   corresponda a `depth_column` según `config.depth_role_for_column` (el
   mecanismo ya existente, reutilizado, no reemplazado). No se prohíbe
   `input_mode=scientific` con `scientific_run=false`: sigue siendo una
   corrida no normativa válida, simplemente no admisible como antecedente
   científico (verificado aparte, en `admissibility.py`).
2. **Configuración del candidato** (`transfer_contract.py`): se valida que
   `selected_family` sea una familia reconocida y coincida con la familia del
   candidato serializado (única o Soft Voting); que `family` coincida con
   `config.family`; que cada clave de `soft_voting_bases` coincida con la
   familia que declara su propio candidato; y que `config.params` declare
   explícitamente los hiperparámetros requeridos de cada familia (incluido
   `weighting`, los pesos normativos de balanceo) con el tipo/restricción
   esperados -- derivados de los mismos campos que ya serializan
   `models.iter_logistic_regression_configs`/`iter_random_forest_configs`/
   `iter_hist_gradient_boosting_configs`, sin tocar esas grillas ni su
   algoritmo. Un artefacto incompleto (`params={}`, o sin `weighting`) se
   rechaza en vez de recibir un default inventado en la lectura.
3. **Fingerprint obligatorio y verificable**: la lectura estructural exige que
   `producer.dataset_fingerprint_ref` tenga SHA-256 completo y con formato
   válido, `schema_version` reconocido, y metadatos requeridos
   (`n_rows`/`scope`) -- un `{}` vacío ya no pasa por comparar `None==None`.
   `admissibility.py` revalida por su cuenta (no asume que `contract` proviene
   necesariamente del lector estructural, ya que es una función invocable de
   forma independiente) tanto la referencia embebida como el archivo hermano
   `dataset_fingerprint.json` y la huella recibida del consumidor, con la
   misma validación reutilizada (`transfer_contract.validate_fingerprint_reference`).
4. **Contexto real del consumidor** (`admissibility.py`): se agregan
   `consumer_code_identity` y `consumer_environment_issues`, recibidos
   explícitamente (nunca calculados ni asumidos). La verificación (b)
   descrita en la entrada anterior -- compatibilidad productor-consumidor,
   comparación real de commits, con rechazo explícito por "compatibilidad no
   acreditada" si difieren sin política documentada -- es enteramente nueva:
   la entrega anterior únicamente implementaba (a) y describía, de forma
   incorrecta, que ambas verificaciones eran equivalentes o que (a) bastaba.
   Esa afirmación ya está corregida tanto en el código como en esta bitácora
   y en la descripción del PR. También se corrige la evidencia de entorno del
   productor: `validated_before_training=true` aislado ya no basta -- se
   exige además `constraints_identity` verificable y `packages` capturados
   con contenido real.

**Corrección adicional de una afirmación imprecisa de la entrega anterior:**
agregar `input_mode`/`scientific_run` como argumentos obligatorios nuevos de
`write_stage_a_artifacts` **no es retrocompatible** -- los llamadores
existentes (`cli.py` y los tests que invocaban esta función) necesitaron
actualizarse explícitamente para pasarlos; la entrega anterior lo describía
incorrectamente como un cambio retrocompatible.

Pruebas: se actualizaron los fixtures de ambos archivos de test para exigir
hiperparámetros completos por familia y evidencia de entorno/fingerprint con
forma válida, y se agregaron regresiones específicas para cada uno de los
cuatro hallazgos, varias de ellas mediante el flujo completo escritura real
(`artifacts.write_stage_a_artifacts`) → modificación del JSON en disco →
lectura real (`transfer_contract.load_frozen_config_contract`) →
admisibilidad -- no únicamente estados construidos a mano. Los casos válidos
existentes (modelos individuales, Soft Voting, sintético→sintético,
productor/consumidor compatibles) se mantienen en verde.

No se amplió el alcance a baselines/B/C/ledger, no se accedió a datos
reales/holdout/MLflow, y `controlled_daily_v3`/baselines históricos/
`backend/`/`frontend/`/HITL quedan sin alteración. No se hizo merge, no se
habilitó auto-merge, no se usó force-push ni se generó ningún ZIP.

## Segunda corrección de admisibilidad del contrato A→B tras revisión externa (2026-09-13)

Revisión externa del commit `1072899d21493cd80f0599290f1226e3a559db5e` (PR
#192) confirmó las 26+21=47 pruebas en verde y CI verde en los 4 checks, pero
reprodujo tres defectos adicionales:

1. **Evidencia de entorno insuficiente**: `check_stage_b_admissibility` admitía
   `constraints_identity={"exists": true, "sha256": "NOT_A_HASH"}` y
   `packages={"invented": "invalid"}` mientras `validated_before_training=true`
   y `validation_issues=[]` -- las dos banderas booleanas bastaban, sin
   verificar el CONTENIDO. Corregido: `admissibility.py` ahora exige formato
   real de SHA-256 en `constraints_identity` (reutilizando
   `code_identity.is_valid_full_sha`), contraste contra el `constraints.txt`
   real (`environment.capture_constraints_identity()`, mecanismo ya
   existente), y revalidación normativa completa del entorno persistido
   contra la referencia versionada (`environment.validate_environment`,
   también ya existente) -- nunca sustituye el entorno HISTÓRICO del
   productor por el de la ejecución que evalúa la admisibilidad.
2. **Consistencia de fingerprint incompleta**: manteniendo el mismo `sha256`,
   cambiar `n_rows`/`scope` en `dataset_fingerprint.json` seguía permitiendo
   admisión -- solo se contrastaba el hash. Corregido: se contrastan los
   cuatro metadatos requeridos (`schema_version`/`sha256`/`n_rows`/`scope`)
   entre la referencia embebida, el archivo del productor y el contexto de
   entrenamiento del consumidor; y `transfer_contract.validate_fingerprint_reference`
   exige además el `scope` autorizado exacto
   (`dataset_fingerprint.FINGERPRINT_SCOPE_STAGE_A_ELIGIBLE_ROWS`), no
   cualquier valor no vacío.
3. **Pesos de combinación de Soft Voting confundidos con `weighting`**: el
   contrato nunca persistía los pesos de COMBINACIÓN del ensamble (protocolo,
   sección 7.5 -- fijos e iguales, 1/3 por base), solo `weighting` (balanceo
   de clases por familia, un concepto distinto). Corregido:
   `SoftVotingClassifier.combination_weights()` (nuevo, en `models.py`, sin
   tocar el algoritmo de ajuste) expone los pesos efectivamente usados
   después de `fit`; `StageAResults.soft_voting_combination_weights` (nuevo,
   en `stage_a_runner.py`) los captura; `frozen_config.json` los persiste
   bajo `soft_voting_combination_weights` (nunca inventados por defecto al
   leer un artefacto incompleto); y `transfer_contract.py` los exige
   presentes y con el valor normativo exacto (`config.SOFT_VOTING_COMBINATION_WEIGHT`
   = 1/3, con tolerancia de punto flotante) cuando hay Soft Voting, y
   ausentes cuando no lo hay.

Pruebas: se actualizaron los fixtures de entorno de ambos archivos de test
para construirse a partir de `environment.load_environment_reference()` y
`environment.capture_constraints_identity()` reales (no diccionarios
inventados, ya que ahora se revalidan de verdad); se agregaron regresiones
reales (escritura → modificación de JSON → lectura/admisibilidad) para cada
uno de los tres hallazgos, incluyendo el caso de la reproducción exacta
reportada. Suite dirigida (transfer_contract + admissibility): 56 passed.
Suite ampliada (+ artifacts + metrics_artifact + cli + models + soft_voting +
dataset_fingerprint + config): 142 passed. `ruff check`/`black --check`
limpios sobre todo `src/experiment_runner/controlled_daily_v4/` y los tests
afectados.

No se amplió el alcance a baselines/B/C/ledger, no se accedió a datos
reales/holdout/MLflow, y `controlled_daily_v3`/baselines históricos/
`backend/`/`frontend/`/HITL quedan sin alteración. No se hizo merge, no se
habilitó auto-merge, no se usó force-push ni se generó ningún ZIP.

## Baselines del protocolo y runner de la Etapa B de controlled_daily_v4 (2026-09-14)

Rama `feat/controlled-daily-v4-stage-b`, base `origin/main`
(`277aefd3a1c8bd36bd237ed85ff0b4a67ee33e4a`, PR #192 -- contrato de
transferencia A→B -- ya integrado). Cierra la parte no bloqueada del *change*
OpenSpec `implement-controlled-daily-v4-stage-b-c` que quedaba pendiente tras
esa entrega: los tres baselines del protocolo (sección 13) y el runner completo
de la Etapa B, reutilizando el contrato A→B integrado sin reabrirlo. Ninguna
ejecución científica real se realizó en este encargo; Etapa C, su ledger y la
apertura del holdout quedan explícitamente fuera de alcance (Decisiones 2 y 3
del documento de decisiones pendientes, ambas todavía bloqueadas).

**Decisión de bootstrap de la Etapa B (Decisión 1), adoptada para este encargo
-- no atribuida a una aprobación académica externa:** las predicciones
evaluables de 2023 se tratan como un único segmento temporal continuo para
`bootstrap.paired_bootstrap_delta`; moving-block bootstrap pareado, no
circular, bloques de 30 días, 5000 réplicas normativas, semilla `20250109`; los
mismos índices remuestreados se aplican a candidato, persistencia y etiquetas;
ningún bloque cruza discontinuidades ni incorpora observaciones externas al
período autorizado; se reutilizan sin cambios las convenciones existentes para
intervalos y réplicas con métricas indefinidas (`bootstrap.py`,
`NoValidBootstrapReplicasError`, `discard_reasons` explícitos). Registrada como
adoptada antes de implementar, en `openspec/changes/implement-controlled-daily-v4-stage-b-c/tasks.md`.
No se encontró ninguna contradicción normativa material distinta de esta
decisión durante la revisión acotada del protocolo/decisiones pendientes
(salvo la inconsistencia documental sobre la actualización del spec canónico,
ver más abajo).

- `baselines.py` (nuevo): `predict_majority_class_baseline` (`argmax` del
  conteo de clases del `train` autorizado; regla de desempate determinista
  `MAJORITY_CLASS_TIE_BREAK=0`, definida y documentada explícitamente antes de
  escribir los tests que la ejercitan -- el protocolo no documenta ninguna,
  consistente con la convención de igualdad de `features.build_target`),
  `predict_persistence_baseline_v4` (humedad **actual** vs. `P20_train`,
  igualdad estricta -> clase 0, nunca consulta humedad futura de la fila
  evaluada) y `predict_constant_stress_baseline` (predice `1` siempre, sin
  ajustar ningún parámetro).
- `stage_b_runner.py` (nuevo): `build_stage_b_training_frame` (mismo
  procedimiento exacto de A -- `STAGE_A_BOUNDS`, `target_timestamp ≤
  2022-12-31`, sin fuga hacia 2023 en ninguna etiqueta de entrenamiento),
  `build_stage_b_evaluation_frame` (`STAGE_B_BOUNDS`,
  `target_timestamp ∈ [2023-01-04, 2023-12-31]`), `refit_frozen_candidate`
  (reentrena exactamente la familia/hiperparámetros/pesos de combinación ya
  congelados por A, incluido Soft Voting vía `models.fit_candidate`/
  `SoftVotingSpec` -- sin búsqueda de hiperparámetros ni selección
  alternativa), `decide_stage_b_verdict` (regla exacta del protocolo, sección
  10: `MCC_candidato_2023 > 0` **y** límite inferior del intervalo pareado de
  `ΔMCC_B ≥ −0.05`, ambas desigualdades con la igualdad incluida en el
  conjunto de aprobación) y `run_stage_b` (orquestador completo). Verifica
  explícitamente la coherencia entre el `P20_train` recalculado y el del
  contrato de A (`StageBTechnicalError` si difieren -- fallo técnico,
  distinto de un veredicto experimental). Monoclase de entrenamiento o de
  evaluación produce `CANDIDATE_NOT_VALIDATED` explícito, nunca una
  aprobación ni una excepción no controlada.
- `artifacts.py`: `write_stage_b_artifacts` (nuevo, `STAGE_B_ARTIFACT_SCHEMA_VERSION`
  propio) persiste identidad de código/entorno de la ejecución consumidora,
  referencia verificable al contrato y evidencia de A consumidos, huella del
  entrenamiento de B, fronteras temporales efectivas, predicciones alineadas
  de las cuatro referencias (candidato + 3 baselines), métricas, intervalo y
  diagnóstico del bootstrap, decisión de B con motivos explícitos, y un
  `holdout_status.json` derivado del veredicto real (antes literal constante
  para A; en B, `stage_b_executed=true`/`stage_b_verdict=<veredicto>`,
  `holdout_2024_2025_open` permanece `false` -- ningún mecanismo de este
  encargo lo puede abrir). Nunca escribe dentro del directorio del productor;
  respeta la misma política de `--overwrite` explícito que A.
- `config.py`: `CLI_ENABLED_STAGES = (STAGE_A, STAGE_B)` y
  `require_enabled_stage` (nuevo), usados por la CLI para habilitar B sin
  alterar `SUPPORTED_STAGES`/`require_stage_a` (que se preservan exactamente
  como estaban, junto con su test existente, para no debilitar su contrato).
- `cli.py`: `--stage B` habilitado con `--producer-dir` explícito
  (`_run_stage_b`). Orden estricto antes de entrenar: lectura estructural del
  contrato → ingesta aislada por período (unión de las ventanas de A y B,
  ninguna fila de 2024-2025 llega jamás a un agregador) → cálculo de la
  huella de entrenamiento de B → `admissibility.check_stage_b_admissibility`
  (identidad/integridad/compatibilidad, con contexto explícito del
  consumidor) → recién entonces `run_stage_b`. `--stage A` sin cambios de
  comportamiento. `--stage C` se sigue rechazando explícitamente.

**Pruebas nuevas, exclusivamente sintéticas** (35 + 3 + extensión de CLI):
`tests/test_controlled_daily_v4_baselines.py` (10 tests: las tres referencias
incluido el caso de igualdad exacta con `P20_train`; ausencia de fuga hacia
`future_soil_moisture`; invariancia ante cambios en las etiquetas de
evaluación); `tests/test_controlled_daily_v4_stage_b_runner.py` (35 tests:
fronteras temporales exactas y ausencia de fuga por horizonte; invariancia del
entrenamiento ante cambios en 2023; invariancia de B ante cambios en
2024-2025 -- tanto del frame de evaluación como del resultado completo;
ausencia de tuning con espía sobre `tuning.select_best_config`; Soft Voting
respetado con pesos de combinación exactos 1/3; los 4 cuadrantes del veredicto
incluidas sus igualdades límite exactas; monoclase de entrenamiento y de
evaluación distinguidos entre sí; fallo técnico de coherencia de `P20_train`
distinguido de un veredicto `CANDIDATE_NOT_VALIDATED`; bootstrap de un único
segmento con una verificación dedicada de la configuración normativa completa
-- 5000 réplicas, sin repetirla en cada test); `tests/test_controlled_daily_v4_stage_b_integration.py`
(3 tests: flujo sintético completo artefactos de A → contrato → B → artefactos
y decisión vía CLI real; C todavía bloqueada tras A y B; rechazo previo al
entrenamiento de un contrato inadmisible con espía sobre
`stage_b_runner.run_stage_b`); `tests/test_controlled_daily_v4_cli.py`
actualizado (se reemplaza el test que exigía el rechazo estático de `--stage
B`, ya no vigente, por la verificación de que `--producer-dir` es requerido).

Verificación real ejecutada (entorno Docker fijado
`docker/experiment-v4/Dockerfile`, reconstruido desde cero con `.build_identity.json`
capturado del mismo checkout -- `git rev-parse --show-object-format`/`HEAD`/
`status --porcelain` reproducidos manualmente porque el host de esta sesión no
tiene `python` disponible fuera del contenedor, siguiendo el mismo mecanismo
que documenta `docker/experiment-v4/build.py`): suite dirigida nueva (baselines
+ stage_b_runner): **35 passed** en 6.90s; CLI completa: **14 passed** en
52.20s; integración A→B: **3 passed** en 43.00s.

**Contradicción documental encontrada, no resuelta en este encargo (reportada,
no inventada su resolución):** `openspec/changes/implement-controlled-daily-v4-stage-b-c/tasks.md`
pedía actualizar `openspec/specs/experiment-runner/spec.md` (canónico) "con el
mismo criterio ya usado para la Etapa A" -- pero
`openspec/changes/implement-controlled-daily-v4-stage-a/tasks.md` (línea 19)
registra esa misma actualización para la propia Etapa A como pendiente de "una
corrida real y de una decisión explícita de cuándo el spec canónico debe
actualizarse". Es decir, el precedente real de la Etapa A no aplicó ese
criterio. Se optó por NO actualizar el spec canónico en este encargo y dejar
la tarea correspondiente explícitamente sin marcar, en vez de aplicar un
criterio que el propio precedente contradice.

No se leyeron datos reales de Pergamino/Balcarce/holdout 2024-2025, no se
ejecutó ninguna etapa científica real ni la Etapa C, no se usó MLflow
compartido, y `controlled_daily_v3`, la evidencia histórica, los tags de
baseline, `backend/`, `frontend/` y `human_feedback/` quedan sin alteración.
No se hizo merge ni se habilitó auto-merge.

## Corrección de cuatro hallazgos de revisión dirigida sobre la Etapa B de controlled_daily_v4 (2026-09-14)

Rama `feat/controlled-daily-v4-stage-b` (mismo PR #193, commit auditado
`d05f80e6e4fb3402a67cac7b7416bebd2348b128` -- HEAD verificado idéntico al
auditado antes de empezar, sin trabajo local ajeno que preservar). Corrige,
en el mismo PR, cuatro hallazgos concretos de una revisión dirigida sobre ese
commit -- ninguno rediseña la arquitectura del runner ni repite una auditoría
general.

**H-1 (protección de los artefactos de A):** `write_stage_b_artifacts(output_dir=producer_dir,
producer_dir=producer_dir, overwrite=True)` reemplazaba `schema_version.json`
(y el resto de la evidencia) de A por el esquema de B. Corrección:
`artifacts.validate_stage_b_output_directory` (nuevo) rechaza `--output-dir`
idéntico a `--producer-dir` tras normalizar ambas rutas con `Path.resolve()`
(símlinks y `..` incluidos), y también el anidamiento en cualquier sentido
(`output_dir` dentro de `producer_dir`, o viceversa) -- `--overwrite` nunca
autoriza ninguno de estos casos. Verificada tanto en la CLI (`cli._run_stage_b`,
antes de leer siquiera el contrato) como en el escritor (`write_stage_b_artifacts`,
antes de `ensure_output_directory` y de cualquier escritura) -- ninguna de las
dos confía en que la otra ya la haya aplicado. Nuevo código de salida `9`.
Pruebas: `tests/test_controlled_daily_v4_artifacts.py` (5 tests unitarios
sobre `validate_stage_b_output_directory` + 1 sobre el rechazo del escritor
con verificación byte a byte); `tests/test_controlled_daily_v4_stage_b_integration.py`
(4 tests por CLI real: coincidencia literal con `--overwrite`, coincidencia
por ruta relativa normalizada, anidamiento, y conservación explícita del
funcionamiento con directorios separados), todos con espía sobre
`stage_b_runner.run_stage_b` que aborta si llega a invocarse.

**H-2 (persistencia del resultado monoclase):** con humedad sintética de 2023
fijada en un valor constante, `run_stage_b` ya calculaba correctamente
`CANDIDATE_NOT_VALIDATED` con las 362 etiquetas de evaluación pero cero
predicciones del candidato -- `write_stage_b_artifacts` fallaba con
`ValueError: All arrays must be of the same length` al construir
`predictions_2023.csv` y nunca llegaba a crear `decision.json`. Corrección:
`StageBResult.predictions_available` (nuevo campo explícito, `False` en
ambos casos monoclase -- entrenamiento y evaluación) y
`artifacts._stage_b_predictions_frame` persiste, cuando no hay predicciones,
únicamente los timestamps y (si están disponibles) las etiquetas verdaderas
-- nunca fabrica una predicción ni sustituye la ausencia por ceros.
`decision.json` incorpora `predictions_available` explícito y se persiste
siempre, incluidos ambos casos monoclase. La cobertura insuficiente (Etapa
evaluable vacía por truncamiento, no por monoclase genuina) se distingue
como fallo técnico -- ver H-3. Pruebas: `tests/test_controlled_daily_v4_stage_b_runner.py`
(datos genuinamente monoclase mediante humedad de 2023 fijada, sin
monkeypatch de `is_monoclass`, recorriendo runner → escritor para ambos
casos -- entrenamiento y evaluación monoclase); `tests/test_controlled_daily_v4_stage_b_integration.py`
(caso end-to-end por CLI con datos realmente monoclase: `decision.json`
existe con `CANDIDATE_NOT_VALIDATED` y C sigue bloqueada).

**H-3 (cobertura y validación antes del ajuste):** (a) una serie terminada el
30/06/2023 producía un resultado de B sobre 178 filas sin rechazar la falta
del resto de 2023 (`validate_continuous_daily_calendar` solo verificaba
continuidad DENTRO del rango recibido, nunca que ese rango llegara a cubrir
las fronteras exigidas); (b) un NaN en `RH2M` del 15/06/2023 producía
`CalendarIntegrityError` recién DESPUÉS de una llamada efectiva a
`refit_frozen_candidate` (el frame de evaluación se construía después del
reentrenamiento). Corrección: `features.validate_stage_window_full_coverage`
(nuevo) exige que la serie diaria completa cubra, sin huecos, la ventana
autorizada de cada etapa (incluida su historia causal), para el período de
entrenamiento (`STAGE_A_BOUNDS`) y el evaluable de B (`STAGE_B_BOUNDS`) --
verificado en `stage_b_runner.run_stage_b` ANTES de construir cualquier
feature o de tocar el estimador. Los frames de entrenamiento y evaluación se
construyen una única vez y se reutilizan de punta a punta (nunca se
reconstruyen por separado más abajo). Se agrega además una verificación de
cobertura EXACTA del período evaluable (`target_timestamp` 2023-01-04..2023-12-31,
diario, sin huecos) que distingue una evaluación vacía por cobertura
insuficiente (fallo técnico) de una evaluación monoclase válida (veredicto
experimental, H-2). Todo error esperable de cobertura/calendario/valores se
convierte en `StageBTechnicalError`, nunca en un veredicto experimental ni en
una excepción no controlada que llegue a la CLI. El aislamiento de 2024-2025
se conserva sin cambios (se verifica antes de tocar valores, como ya hacía la
ingesta). Pruebas: `tests/test_controlled_daily_v4_features.py` (4 tests
unitarios de `validate_stage_window_full_coverage`);
`tests/test_controlled_daily_v4_stage_b_runner.py` (7 tests: ausencia de
inicio/final del período de B, hueco interior, historia causal insuficiente
exclusiva de B, valor no finito -- reproduce exactamente el hallazgo original
--, evaluación vacía por cobertura insuficiente, y el caso completo que
conserva exactamente las fronteras del protocolo, `2023-01-04..2023-12-31`,
362 filas evaluables), cada rechazo previo verificado con un espía sobre
`refit_frozen_candidate` que aborta si llega a invocarse.

**H-4 (evidencia de reproducibilidad de B):** la CLI capturaba
`constraints_identity` pero nunca lo incorporaba al `environment.json` de B
(sí lo hacía para A); B no capturaba ni persistía advertencias de ajuste
(`warnings_capture.py` ya existía y se usaba en A, pero no en B); si todas
las réplicas bootstrap resultaban inválidas, `NoValidBootstrapReplicasError`
no llevaba diagnósticos adjuntos y el runner los perdía por completo.
Corrección: `cli._run_stage_b` incorpora `constraints_identity` al
`consumer_environment_info` pasado a `write_stage_b_artifacts` (igual que en
A); `stage_b_runner.refit_frozen_candidate` envuelve el ajuste con
`warnings_capture.collect_context_warnings` (contexto `stage='B'`,
`phase='refit'`, familia), y `StageBResult.warnings_log`/`write_stage_b_artifacts`
persisten `warnings.json` (antes ausente en el esquema de B); `bootstrap.NoValidBootstrapReplicasError`
ahora lleva `diagnostics` adjuntos (réplicas solicitadas/válidas/descartadas,
motivos, semilla, largo de bloque y segmentos) construidos antes de
lanzarse -- nunca se reejecuta el bootstrap para reconstruirlos.
`StageBResult.bootstrap_executed` distingue "bootstrap no ejecutado"
(monoclase) de "bootstrap ejecutado sin réplicas válidas" (diagnósticos
poblados, `bootstrap_result=None`), persistido en `bootstrap.json`. Se
verificó además que la configuración declarada (`resolved_config.json`,
`bootstrap_replicas`) coincide exactamente con la efectivamente consumida
(`bootstrap.json`, `diagnostics.replicas_requested`) incluso con una
configuración reducida no normativa -- nunca etiquetada como la normativa
completa. Pruebas: `tests/test_controlled_daily_v4_bootstrap.py` (extensión
del test existente de cero réplicas válidas, con verificación completa de
los diagnósticos adjuntos); `tests/test_controlled_daily_v4_stage_b_runner.py`
(diagnósticos completos con cero réplicas válidas vía espía sobre
`paired_bootstrap_delta`; advertencia REAL de ajuste -- regresión logística
con `max_iter` insuficiente para converger, no fabricada -- capturada con
contexto y persistida por el escritor); `tests/test_controlled_daily_v4_stage_b_integration.py`
(`constraints_identity` de B contrastado por CLI contra el SHA-256 real de
`constraints.txt`; coherencia de una configuración de bootstrap reducida
declarada vs. efectivamente consumida).

**Extensión, sin cambiar su comportamiento, de una excepción compartida con
A:** `bootstrap.NoValidBootstrapReplicasError` gana un parámetro
`diagnostics` opcional (default `None`); no se tocó su uso en `selection.py`
(Etapa A, que no la captura) ni su mensaje. Se verificó explícitamente que la
suite completa de la Etapa A (`test_controlled_daily_v4_selection.py`,
`test_controlled_daily_v4_stage_a_integration.py`, entre otras) sigue en
verde tras el cambio.

No se cambiaron familia, hiperparámetros, umbrales de decisión, bootstrap
normativo (5000 réplicas/bloques de 30 días/semilla `20250109`) ni las
fronteras temporales del protocolo (`STAGE_A_BOUNDS`/`STAGE_B_BOUNDS`
intactas) -- las cuatro correcciones son estrictamente de manejo de casos
límite, protección de evidencia y persistencia de diagnósticos, verificadas
con el mismo runner y el mismo protocolo ya congelados. Solo datos
sintéticos: no se leyó ningún CSV real de Pergamino/Balcarce ni el holdout
real 2024-2025, no se ejecutó ninguna etapa científica real, no se usó
MLflow compartido, y `controlled_daily_v3`, los baselines históricos,
`backend/`, `frontend/` y `human_feedback/` quedan sin alteración. La Etapa C
y su ledger siguen sin implementarse (fuera de alcance de este encargo). No
se hizo merge ni se habilitó auto-merge.

Verificación real ejecutada (contenedor `python:3.11-slim` con `pip install
-e ".[dev]"`, dado que el host de esta sesión no tiene `python` disponible
fuera de Docker): suite dirigida (`test_controlled_daily_v4_stage_b_runner.py`
+ `test_controlled_daily_v4_stage_b_integration.py` + `test_controlled_daily_v4_artifacts.py`
+ `test_controlled_daily_v4_features.py` + `test_controlled_daily_v4_bootstrap.py`,
existentes + los 31 tests nuevos de estos cuatro hallazgos): **88 passed** en
192.07s; suite completa `tests/test_controlled_daily_v4_*.py`: **353 passed,
3 skipped** en 828.13s (los 3 `skipped` ya existían antes de esta corrección,
sin relación con los cuatro hallazgos); `ruff check src tests` y
`black --check src tests` limpios tras aplicar el formateo automático.
Construcción del entorno experimental fijado
(`docker/experiment-v4/build.py`) y suite dentro del contenedor: ver el
cierre de esta entrada / la descripción del PR #193 para el resultado final.

## Cierre de dos pendientes técnicos y un pendiente documental sobre la Etapa B de controlled_daily_v4 (2026-09-15)

Rama `feat/controlled-daily-v4-stage-b` (mismo PR #193, commit auditado de esta
ronda `c13b917d9dd79f91739fff1a15b9948ffd545ee7` -- HEAD local/remoto
verificado idéntico al auditado antes de empezar, sin trabajo local ajeno que
preservar). Cierra dos hallazgos técnicos concretos y un pendiente documental
ya autorizado, sin repetir una auditoría general ni ampliar el alcance.

**Pendiente técnico 1 (P20_train validado ANTES del reentrenamiento):**
reproducido -- con `final_p20_train=999` en el contrato, `run_stage_b`
rechazaba el contrato (`StageBTechnicalError`), pero DESPUÉS de una llamada
efectiva a `refit_frozen_candidate` (el estimador ya se había ajustado antes
de comparar el umbral). Corrección: `stage_b_runner.run_stage_b` calcula
`P20_train` UNA sola vez sobre el `training_frame` autorizado y validado
(`compute_p20_threshold`), lo compara contra `contract.final_p20_train` (misma
tolerancia existente, `rel_tol=1e-9`/`abs_tol=1e-12`) ANTES de cualquier
llamada a `refit_frozen_candidate`, y reutiliza ese mismo umbral ya validado
-- nunca uno recalculado por separado -- tanto para construir las etiquetas de
entrenamiento (chequeo de monoclase) como para reentrenar.
`refit_frozen_candidate` gana un parámetro `p20_train` opcional (si se recibe,
lo reutiliza tal cual; si no, lo calcula como antes, para no romper las
llamadas directas de otros tests). No se cambió familia, hiperparámetros,
criterios de aprobación, ni el tratamiento explícito de entrenamiento
monoclase (que sigue devolviendo `p20_train=NaN` y `CANDIDATE_NOT_VALIDATED`
sin intentar reentrenar). Pruebas nuevas (`tests/test_controlled_daily_v4_stage_b_runner.py`):
`test_p20_train_mismatch_is_rejected_before_any_refit_call` (contrato con
P20 inconsistente: `StageBTechnicalError` y cero llamadas a
`refit_frozen_candidate`, verificado con un espía que aborta si llega a
invocarse -- reproduce exactamente el hallazgo) y
`test_p20_train_coherence_check_with_valid_contract_preserves_labels_and_behavior`
(contrato válido: conserva `P20_train`, las etiquetas de evaluación resultan
idénticas a las calculadas directamente con ese umbral, y el veredicto/las
predicciones se comportan como antes). El rechazo se sigue propagando como
`StageBTechnicalError` controlado por la CLI (código de salida `8`,
`cli._run_stage_b`), sin cambios en ese punto.

**Pendiente técnico 2 (coherencia de la bandera normativa del bootstrap):**
reproducido -- una ejecución con 5 (o cualquier número distinto de 5000)
réplicas persistía `replicas_requested=5` (o el valor pedido) y
`normative=True` en `BootstrapDiagnostics`, porque `bootstrap.py` copiaba tal
cual el argumento `normative` que le pasaba el llamador (que en la CLI de B
nunca se parametriza y siempre llega en `True`) en vez de derivarlo de la
configuración efectivamente consumida; el test existente
(`test_diagnostics_record_the_full_provenance_of_the_procedure`, con
`n_replicas=12`) solo verificaba el número de réplicas, nunca esa bandera.
Corrección: `bootstrap.compute_is_normative_configuration(n_replicas, seed,
block_length)` (nueva función pura) calcula la condición normativa real --
`True` sii, simultáneamente, `n_replicas == BOOTSTRAP_REPLICAS_DEFAULT`
(5000), `seed == BOOTSTRAP_SEED` (20250109) y
`block_length == BOOTSTRAP_BLOCK_DAYS` (30) -- y `paired_bootstrap_delta` la
usa para poblar `BootstrapDiagnostics.normative` en AMBOS puntos de
construcción (réplicas válidas, y el caso de cero réplicas válidas dentro de
`NoValidBootstrapReplicasError.diagnostics`), en vez de reenviar el argumento
`normative` recibido. Ese argumento (`build_segment_plans`/`paired_bootstrap_delta`)
conserva su responsabilidad original sin cambios -- exigir que `block_length`
sea exactamente 30 salvo que se pase `normative=False` explícitamente (modo
de test) -- ahora documentada como una responsabilidad de VALIDACIÓN,
separada de la etiqueta de evidencia persistida (cambio mínimo: no se separó
en dos parámetros distintos, se separó la fuente de la bandera de evidencia).
Se verificó por separado la distinción científico/sintético: `scientific_run`/
`input_mode` (`cli.py`, `admissibility.py`) no se tocaron, y cumplir la
configuración normativa del bootstrap sigue sin convertir por sí solo una
corrida sintética en científica. Alcance verificado explícitamente en
`resolved_config.json` (`normative_run`, ya coherente antes de este cambio --
depende de `seed`/`bootstrap_replicas` de la CLI, no de `bootstrap.py`),
`bootstrap.json` (`diagnostics.normative`, la corrección real) y los
diagnósticos del caso con cero réplicas válidas (misma corrección, mismo
punto de construcción). No se debilitó la validación existente de
`block_length` ni se cambió el algoritmo de remuestreo (`moving_block_bootstrap_indices`
intacto). Pruebas nuevas (`tests/test_controlled_daily_v4_bootstrap.py`):
`test_compute_is_normative_configuration_full_normative_configuration`,
`_reduced_replicas`, `_non_normative_seed`, `_different_block_length` (unitarias
sobre la función pura); `test_paired_bootstrap_delta_persists_normative_true_only_with_the_full_configuration`
(réplicas reducidas con `normative=True` declarado: la bandera persistida es
`False`); `test_paired_bootstrap_delta_persists_normative_flag_with_a_different_block_length`
(bloques de 10 días en modo de prueba permitido, `normative=False`: la
bandera persistida también es `False`); `test_zero_valid_replicas_with_non_normative_configuration_persists_normative_false`
(cero réplicas válidas con réplicas reducidas: `NoValidBootstrapReplicasError.diagnostics.normative`
es `False`). Pruebas nuevas en `tests/test_controlled_daily_v4_stage_b_runner.py`:
`test_bootstrap_with_reduced_replicas_never_persists_normative_true` y
`test_bootstrap_with_non_normative_seed_never_persists_normative_true` (ambas
verifican la bandera EFECTIVAMENTE persistida en `StageBResult.bootstrap_diagnostics.normative`,
no solo los valores numéricos), además de la aserción ya existente
`test_bootstrap_uses_normative_configuration_when_requested`, extendida para
verificar también `normative is True` con la configuración normativa
completa. `tests/test_controlled_daily_v4_stage_b_integration.py`
(`test_cli_reduced_bootstrap_configuration_is_never_labeled_normative`) se
extendió con la misma verificación sobre `bootstrap.json` end-to-end vía CLI.

**Corrección de dos aserciones preexistentes de la Etapa A (código compartido
`bootstrap.py`), verificadas y actualizadas, no reescritas silenciosamente:**
`tests/test_controlled_daily_v4_runner_artifacts.py::test_cli_selection_decision_records_bootstrap_provenance`
(CLI real de A con `--bootstrap-replicas 10`) y
`tests/test_controlled_daily_v4_bootstrap.py::test_diagnostics_record_the_full_provenance_of_the_procedure`
(`n_replicas=12`) afirmaban `normative is True` pese a que ninguna de las dos
configuraciones es la normativa (5000 réplicas) -- exactamente la
manifestación del mismo defecto en A, antes sin verificar. Ambas aserciones
se corrigieron a `normative is False` (comentario explícito en cada una,
citando esta corrección) tras confirmar que ningún otro comportamiento de A
depende de ese valor; el resto de la suite de A (`test_controlled_daily_v4_selection.py`
y las demás suites de A dentro de la ejecución completa) se verificó en verde
sobre el mismo cambio de `bootstrap.py`.

**Pendiente documental (cierre ya autorizado):** `openspec/specs/experiment-runner/spec.md`
(canónico) incorpora la nueva sección "Protocolo controlled_daily_v4_external_pergamino
(Etapas A y B)", que distingue explícitamente: Etapa A implementada e
integrada en `main`, verificada sintéticamente; Etapa B implementada y
verificada sintéticamente en el PR #193, con su integración a `main`
pendiente mientras ese PR siga abierto; las ejecuciones científicas reales de
A y B y sus resultados cuantitativos, pendientes por separado (ninguna se
afirma como obtenida); Etapa C y su ledger de holdout, sin implementar, fuera
de alcance de este encargo. Esta actualización resuelve, con autorización
explícita del encargo del 2026-09-15, la contradicción documental que hasta
ahora bloqueaba la actualización del spec canónico: `openspec/changes/implement-controlled-daily-v4-stage-a/tasks.md`
condicionaba esa actualización a una corrida científica real, y
`openspec/changes/implement-controlled-daily-v4-stage-b-c/tasks.md` (línea
104 original) se negaba a actualizar el spec solo para B citando ese mismo
precedente sin resolverlo. Ambos archivos de tareas quedan actualizados con
una nota de resolución que conserva, sin reescribir, el texto histórico de la
contradicción -- la tarea de A que sigue pendiente por separado (persistir
resultados reales de una corrida científica) no se marca completada ni se
confunde con la actualización documental ahora resuelta. Ningún resultado
histórico de `controlled_daily_v3` ni ninguna ejecución científica de
`controlled_daily_v4` se reescribe ni se afirma como ocurrida.

No se cambiaron familia, hiperparámetros, umbrales de decisión, el algoritmo
de remuestreo del bootstrap, ni las fronteras temporales del protocolo. Solo
datos sintéticos: no se leyó ningún CSV real de Pergamino/Balcarce ni el
holdout real 2024-2025, no se ejecutó ninguna etapa científica real, no se
usó MLflow compartido, y `controlled_daily_v3`, los baselines históricos,
`backend/`, `frontend/` y `human_feedback/` quedan sin alteración. La Etapa C
y su ledger siguen sin implementarse (fuera de alcance de este encargo). No
se hizo merge ni se habilitó auto-merge.

Verificación real ejecutada (contenedor `aai-hydric-v4-experiment:dev`, el
mismo entorno experimental fijado del *change*, vía Docker, dado que el host
de esta sesión no tiene `python` disponible fuera de contenedores): 11 tests
nuevos (4 en `test_controlled_daily_v4_stage_b_runner.py`, 7 en
`test_controlled_daily_v4_bootstrap.py`), 0 tests eliminados, 2 aserciones
preexistentes corregidas (ver arriba); suite completa
`tests/test_controlled_daily_v4_*.py`: **364 passed, 3 skipped** en 746.59s
(los 3 `skipped` son los mismos preexistentes, sin relación con estos
cambios; 364 = 353 del commit auditado `c13b917` + 11 tests nuevos de esta
corrección); `ruff check src tests` limpio; `black --check src tests` limpio
tras aplicar el formateo automático a `src/experiment_runner/controlled_daily_v4/bootstrap.py`
y `tests/test_controlled_daily_v4_stage_b_runner.py` (solo diferencias de
formato, sin cambios de comportamiento); `git diff --check` sin advertencias
de espacios en blanco.

## Etapa C y ledger de protección del holdout de controlled_daily_v4 (2026-09-15)

Encargo explícito: implementar la Etapa C (holdout final 2024-2025) y el
ledger transaccional de protección contra una segunda apertura del holdout,
adoptando como decisiones operativas de este encargo (no atribuidas a una
aprobación académica externa) las Decisiones 2 y 3 de
`docs/research/controlled-daily-v4-stage-b-c-decisiones-pendientes.md`
(documento actualizado con el detalle completo de la adopción). Base:
`origin/main` en `caa9fc93854aa704a48252b49796108c0318595c` (PR #193 ya
mergeado, verificado antes de empezar). Rama:
`feat/controlled-daily-v4-stage-c-holdout-ledger`.

**Componentes nuevos:**

- `src/experiment_runner/controlled_daily_v4/holdout_ledger.py`: ledger
  transaccional SQLite (biblioteca estándar), en una ubicación explícita y
  persistente fuera de `--output-dir`. Identidad del holdout independiente de
  commit/candidato/directorio/intento (`compute_holdout_identity_key`); tres
  estados (`AUSENTE`/`CONFIRMADA`/`INDETERMINADA`); inicialización explícita
  y separada de la ejecución (`init_ledger`, rechaza reemplazar un ledger
  existente); secuencia de apertura de dos fases con `fsync` explícito del
  archivo y, cuando la plataforma lo permite, del directorio contenedor
  (`reserve_holdout` marca `INDETERMINADA` de forma durable; `confirm_holdout_open`
  la promueve a `CONFIRMADA`, también de forma durable, antes de cualquier
  acceso al holdout); `finalize_holdout` como marca separada al terminar de
  serializar resultados; ledgers sintético/científico separados por `mode`,
  con rechazo explícito de cualquier cruce.
- `src/experiment_runner/controlled_daily_v4/stage_c_runner.py`: runner de
  evaluación única del holdout (`target_timestamp` 2024-01-04..2025-12-31),
  reentrenamiento del candidato ya congelado por A y aprobado por B con
  `target_timestamp <= 2023-12-31` y `P20_train` recalculado exclusivamente
  sobre ese rango extendido (deliberadamente sin comparar ese `P20_train`
  contra el de A/B, a diferencia de B). Sin selección, tuning, calibración ni
  ajuste de umbrales. Reutiliza los tres baselines y el mecanismo de bootstrap
  ya normativos (aquí exclusivamente diagnóstico: C no tiene compuerta de
  aprobación/rechazo). Monoclase/indefinido tratado igual que en B: ausencia
  explícita de predicciones, nunca fabricadas.
- `admissibility.check_stage_c_admissibility` (extensión de `admissibility.py`):
  revalida la coherencia entre `decision.json`, `metrics.json` y
  `bootstrap.json` de B (nunca confía en un `decision.json` aislado), el
  linaje verificable hasta el `frozen_config.json` de A (releído fresco, no
  solo la copia embebida en `producer_reference.json` de B), la identidad de
  código de B y de la ejecución consumidora de C (mismo patrón de dos
  verificaciones ya usado en B→A), el entorno persistido de B, y rechaza
  siempre `depth_role` de sensibilidad. Nunca accede a ningún CSV crudo.
- `artifacts.write_stage_c_artifacts` / `validate_stage_c_output_directory`
  (extensión de `artifacts.py`): directorio de salida exclusivo de C,
  protegido frente a coincidencia/anidamiento/alias con el directorio de A,
  el de B y el archivo del ledger; sin parámetro `overwrite` (Decisión 3).
  Persiste identidades de holdout/intento/ledger, referencias verificables a
  A y B, fingerprint del entrenamiento extendido, fronteras temporales
  efectivas, predicciones con baselines, métricas/bootstrap diagnóstico, y un
  `outcome.json` deliberadamente sin campo `verdict`.
- `cli.py`: `--stage C` (secuencia completa: admisibilidad sin tocar el
  holdout → reserva → confirmación durable → recién entonces provenance/CSV
  → evaluación → artefactos → finalización), `--init-holdout-ledger`
  (inicialización explícita, separada de cualquier ejecución),
  `--authorized-by` (sin valor por defecto), `--stage-b-dir`,
  `--holdout-ledger-path`; `--overwrite` rechazado incondicionalmente con
  `--stage C`; recuperación de solo lectura cuando el ledger ya está
  `CONFIRMADA` y finalizado (sin reentrenar ni leer CSV).
- `config.py`: `STAGE_C_TRAINING_BOUNDS` (unión exacta de A+B, hasta
  2023-12-31), `PROTOCOL_ID`/`HOLDOUT_SITE`, `CLI_ENABLED_STAGES` extendido a
  incluir `C`.

**Pruebas nuevas (exclusivamente sintéticas, sin CSV reales de
Pergamino/Balcarce ni el holdout real):**

- `tests/test_controlled_daily_v4_holdout_ledger.py` (18 tests): identidad
  independiente de commit/candidato/output-dir; inicialización explícita y
  rechazo de reinicialización; ledger ausente/corrupto tratado como
  `INDETERMINADA` nunca `AUSENTE`; cruce de modo rechazado; ciclo completo
  reserva→confirmación→finalización; segunda reserva rechazada en
  `CONFIRMADA`; cambio de intento nunca bypassa un holdout confirmado;
  interrupción entre reserva y confirmación deja `INDETERMINADA` sin
  reinicializarse; confirmación con intento equivocado; reserva sin
  inicialización previa; finalización sin confirmación previa; **dos
  procesos reales del sistema operativo** (no mocks) compitiendo por la misma
  reserva -- solo uno la obtiene; reinicio de proceso simulado (nueva
  conexión desde cero) sigue protegiendo el holdout.
- `tests/test_controlled_daily_v4_stage_c_runner.py` (13 tests): fronteras
  temporales exactas y cobertura completa del período evaluable; invariancia
  del entrenamiento ante cambios en 2024-2025; `P20_train` recalculado sin
  comparación contra el contrato de A; ausencia de tuning (espía sobre
  `tuning.select_best_config`); preservación exacta de hiperparámetros
  (espía sobre `fit_estimator`); monoclase de entrenamiento y de evaluación
  con ausencia explícita de predicciones; persistencia nunca usa humedad
  futura de la fila evaluada; bootstrap diagnóstico con la configuración
  efectivamente consumida; ausencia de un campo `verdict` en `StageCResult`.
- `tests/test_controlled_daily_v4_stage_c_admissibility.py` (12 tests):
  camino feliz científico y sintético; una aprobación sintética nunca
  habilita C científica; `depth_role` de sensibilidad siempre rechazado;
  veredicto no validado rechazado; coherencia decisión/métricas/bootstrap
  (rechazo cuando `decision.json` dice `CANDIDATE_VALIDATED` pero
  `metrics.json`/`bootstrap.json` no lo sustentan); evidencia incompleta
  (archivo faltante); linaje a A roto por referencia de directorio incorrecta
  o por `frozen_config.json` con drift respecto de lo embebido en B; commit
  no acreditado; identidad de código del consumidor ausente; entorno de C con
  fallas de validación.
- `tests/test_controlled_daily_v4_stage_c_integration.py` (8 tests): flujo
  A→B→C completo mediante los contratos reales (CLI real, ledger real en
  disco); B no validada nunca toca el holdout (espía sobre
  `ingestion.load_era5_hourly_raw`); segunda evaluación con `--output-dir`
  distinto queda bloqueada (espía sobre `stage_c_runner.run_stage_c`);
  recuperación de solo lectura de un resultado ya finalizado sin reentrenar;
  `--overwrite` rechazado incondicionalmente; conflicto de `--output-dir` con
  `--producer-dir`; autorización ausente y ledger nunca inicializado
  rechazados antes de tocar cualquier CSV.

**Comandos realmente ejecutados** (contenedor `aai-hydric-v4-experiment:dev`,
reconstruido en esta sesión con `docker build`, `.build_identity.json`
generado manualmente con el commit base `caa9fc93...` y `dirty=true` porque
el árbol tenía cambios sin commitear al momento del build -- no se usó
`docker/experiment-v4/build.py` porque el host de esta sesión no tiene
`python` fuera de contenedores):

- `pytest -q tests/test_controlled_daily_v4_holdout_ledger.py tests/test_controlled_daily_v4_stage_c_runner.py tests/test_controlled_daily_v4_stage_c_admissibility.py` → **43 passed** en ~12s (18 + 13 + 12).
- `pytest -q tests/test_controlled_daily_v4_stage_c_integration.py` → **8 passed** en ~380s (incluye entrenamiento real de Stage A/B con grillas reducidas dentro de cada test).
- Suite completa `tests/test_controlled_daily_v4_*.py` ANTES de agregar los archivos nuevos (regresión pura sobre A/B existentes tras los cambios de `admissibility.py`/`artifacts.py`/`cli.py`/`config.py`): **364 passed, 3 skipped** en 1321.58s -- idéntico al baseline del commit `caa9fc9` (PR #193), sin regresiones.
- Suite completa `tests/test_controlled_daily_v4_*.py` CON los 4 archivos de tests nuevos incluidos: **415 passed, 3 skipped, 4 warnings** en 1734.60s (0:28:54) -- 415 = 364 + 51 tests nuevos (18 ledger + 13 stage_c_runner + 12 stage_c_admissibility + 8 stage_c_integration); los 3 `skipped` y los 4 `warnings` son los mismos preexistentes, sin relación con este cambio; 0 fallidos.
- `ruff check src tests` → limpio (tras corregir 17 hallazgos: imports sin usar y líneas >100 columnas, incluida una corrección posterior de dos líneas largas adicionales detectadas en una segunda pasada).
- `black src tests` → 6 archivos reformateados (`holdout_ledger.py`, `admissibility.py`, `artifacts.py`, `cli.py`, `test_controlled_daily_v4_stage_c_runner.py`, `test_controlled_daily_v4_stage_c_integration.py`); `black --check` limpio después.
- `git diff --check` (con `git add -N` para incluir los archivos nuevos en el diff) → solo avisos de conversión LF→CRLF de `core.autocrlf=true` (mismos para cualquier archivo del repositorio en Windows), sin advertencias reales de espacios en blanco.

Solo datos sintéticos: no se leyó ningún CSV real de Pergamino/Balcarce ni el
holdout real 2024-2025, no se ejecutó ninguna etapa científica real, no se
abrió ningún holdout real, no se usó MLflow compartido, y `controlled_daily_v3`,
los baselines históricos, `backend/`, `frontend/` y `human_feedback/` quedan
sin alteración. No existe ningún ledger científico inicializado en este
repositorio. No se hizo merge ni se habilitó auto-merge.

## Revisión dirigida sobre el PR #194: cinco hallazgos corregidos (2026-09-15)

Encargo explícito de seguimiento sobre el mismo PR #194 (commit auditado
`cdad5128a29069bd51ae5d6fd723784253e065c9`), corrigiendo cinco hallazgos
reproducidos de una revisión dirigida, sin reabrir la Decisión 4
(`depth_role`, ubicación exacta ya definida) ni ampliar la arquitectura. Cada
corrección se acompañó de una regresión sintética que reproduce el defecto
concreto reportado antes de corregirlo.

**1. Admisibilidad B→C insuficiente** (`admissibility.py`): se agregó
`_validate_bounded_metric` (rechaza booleanos -- `bool` es subclase de `int`
en Python, así que `isinstance(True, (int, float))` y `True > 0` eran ambos
verdaderos --, valores no finitos, y valores fuera de `[-1, 1]`), aplicada a
`mcc_candidate.value`, `interval_lower` e `interval_upper`; se agregó
detección de intervalo bootstrap invertido (`interval_lower > interval_upper`)
y contabilidad de réplicas (`diagnostics.replicas_valid > 0`,
`valid + discarded == requested`); se agregó la verificación de coherencia
`resolved_config.input_mode`/`scientific_run` de la propia corrida de B, en
ambos sentidos (sintético y científico) -- antes solo se comparaba
`scientific_run` de forma aislada. Los fixtures de
`tests/test_controlled_daily_v4_stage_c_admissibility.py` (`_write_stage_b_evidence`)
se reconstruyeron con evidencia completa (antes omitían `interval_upper`,
`diagnostics` e `input_mode` de `resolved_config.json`, lo que admitía
evidencia incompleta como camino científico válido). 6 regresiones nuevas,
incluido un spy sobre `holdout_ledger.reserve_holdout`/`confirm_holdout_open`
e `ingestion.load_*` que confirma cero reservas/cero acceso al holdout en
cada caso rechazado.

**2. Recuperación con falso éxito** (`artifacts.py`): `write_stage_c_artifacts`
ahora escribe `integrity_manifest.json` (esquema `controlled_daily_v4_stage_c.v2`)
como ÚLTIMO artefacto, con el sha256 de cada artefacto realmente persistido,
`holdout_identity_key`, `attempt_id`, y `result_reference` resuelto (absoluto,
símlinks incluidos -- antes `finalize_holdout` guardaba la ruta cruda de
`--output-dir`, potencialmente relativa al directorio de trabajo). Se agregó
`artifacts.verify_stage_c_recovery`, que la CLI invoca antes de declarar una
recuperación satisfactoria: comprueba directorio existente, manifiesto
legible, correspondencia de holdout/intento, y sha256 exacto de cada archivo
listado -- nunca declara éxito sobre un directorio inexistente, un artefacto
faltante, contenido alterado, o evidencia de otro intento. `HoldoutLedgerState`
ahora expone `reserved_by_attempt_id` (nuevo campo en `holdout_ledger.py`,
leído de la columna ya existente) para que la CLI pueda pasar el `attempt_id`
correcto a la verificación. 7 regresiones nuevas en
`tests/test_controlled_daily_v4_stage_c_recovery.py`. **Bug real detectado y
corregido durante esta misma implementación** (no en el código auditado,
sino introducido y corregido dentro de este mismo encargo): el cálculo de
`manifest_files` iteraba `written.values()` DESPUÉS de insertar la propia
ruta de `integrity_manifest.json` en `written`, intentando leer un archivo
que todavía no existía (`FileNotFoundError` reproducible de forma
determinística en cualquier corrida real de `--stage C`) -- detectado porque
la suite de integración completa (36 tests) falló 2/36 al ejecutarla, pese a
que las pruebas unitarias aisladas de `verify_stage_c_recovery` habían
pasado con mocks más permisivos; corregido reordenando: calcular
`manifest_files` ANTES de agregar la clave `integrity_manifest` al dict
`written`.

**3. Prevalidación insuficiente antes de reservar** (`cli.py`, `artifacts.py`):
se agregó `artifacts.check_output_directory_not_occupied` (verifica ocupación
de `--output-dir` SIN crear el directorio, a diferencia de
`ensure_output_directory`) invocada en el paso 1 de `_run_stage_c`, antes de
la admisibilidad y la reserva del ledger -- antes esta verificación solo
ocurría dentro de `write_stage_c_artifacts`, después de reservar/confirmar/
evaluar. Se agregó también, en `main()`: rechazo de `--authorized-by` vacío
(antes solo se detectaba `None`, dejando pasar `--authorized-by ""` hasta
`confirm_holdout_open`, ya con la reserva tomada) y rechazo de una invocación
`--input-mode scientific` con semilla/réplicas no normativas (antes se
permitía y solo se registraba como `normative_deviations` en los artefactos
finales). 3 regresiones nuevas en `tests/test_controlled_daily_v4_stage_c_integration.py`,
cada una con espías que confirman cero reservas y el ledger en `AUSENTE` tras
el rechazo.

**4. Validación de esquema del ledger incompleta** (`holdout_ledger.py`): la
función `_validate_mode` (renombrada `_validate_ledger_meta`) no verificaba
`schema_version` en absoluto -- un valor arbitrario en esa columna no
afectaba `read_holdout_state` ni `reserve_holdout`. Corregido centralizando
la validación de esquema + `mode` coherente en una única función, reutilizada
en las cuatro operaciones (lectura → `INDETERMINADA` vía la nueva
`HoldoutLedgerSchemaError`; reserva/confirmación/finalización → rechazo
explícito, sin tocar el registro). Se detectó además que `confirm_holdout_open`
y `finalize_holdout` no verificaban la existencia del archivo antes de
`sqlite3.connect`, que crea un archivo vacío de forma implícita si no existe
-- corregido con la misma verificación explícita que ya tenía `reserve_holdout`.
`finalize_holdout` ahora exige el parámetro `attempt_id` y lo compara contra
`reserved_by_attempt_id` (`HoldoutFinalizationOwnershipError` si no coincide)
y rechaza una segunda finalización sobre un registro ya finalizado
(`HoldoutAlreadyFinalizedError`) en vez de reemplazar `finalized_result_reference`
en silencio. 8 regresiones nuevas en `tests/test_controlled_daily_v4_holdout_ledger.py`
(esquema desconocido, metadatos incoherentes, estado incoherente, ledger
ausente durante confirmación/finalización, intento incorrecto en
finalización, segunda finalización), conservando intacta la prueba de dos
procesos reales del sistema operativo compitiendo por la reserva.

**5. Trazabilidad del conjunto de C incompleta** (`dataset_fingerprint.py`,
`stage_c_runner.py`, `artifacts.py`): `compute_dataset_fingerprint` ahora
acepta un parámetro `scope` explícito (default sin cambios,
`FINGERPRINT_SCOPE_STAGE_A_ELIGIBLE_ROWS`, para no alterar A/B);
`stage_c_runner.run_stage_c` pasa el nuevo `FINGERPRINT_SCOPE_STAGE_C_EXTENDED_TRAINING`
para su entrenamiento extendido (antes se etiquetaba, incorrectamente, con el
`scope` de A/B, que describe un período distinto). `StageCResult` incorpora
`target_timestamps` (alineado 1:1 con `feature_timestamps`, horizonte D+3),
persistido en `predictions_2024_2025.csv` (antes solo tenía
`feature_timestamp`) -- esquema de artefactos de C bumpeado a
`controlled_daily_v4_stage_c.v2`. 2 regresiones nuevas en
`tests/test_controlled_daily_v4_stage_c_runner.py`; sin regresiones en A/B
(mismo `scope` por defecto, ningún llamador existente pasa el nuevo
parámetro).

**Comandos realmente ejecutados** (mismo contenedor
`aai-hydric-v4-experiment:dev` del cierre anterior, reutilizado sin
reconstruir):

- `pytest -q tests/test_controlled_daily_v4_stage_c_admissibility.py tests/test_controlled_daily_v4_holdout_ledger.py tests/test_controlled_daily_v4_stage_c_runner.py tests/test_controlled_daily_v4_dataset_fingerprint.py tests/test_controlled_daily_v4_stage_c_recovery.py` → **74 passed** en 21.42s.
- `pytest -q tests/test_controlled_daily_v4_stage_c_integration.py tests/test_controlled_daily_v4_cli.py tests/test_controlled_daily_v4_artifacts.py` → **36 passed** en 551.74s (0:09:11) -- incluye entrenamiento real de Stage A/B con grillas reducidas dentro de cada test de integración.
- `pytest -q tests/test_controlled_daily_v4_*.py` (suite completa) → ver resultado final más abajo en esta misma entrada.
- `ruff check src tests` → limpio (tras corregir una línea >100 columnas detectada en una primera pasada).
- `black src tests` → 3 archivos reformateados (`holdout_ledger.py`, `test_controlled_daily_v4_holdout_ledger.py`, `test_controlled_daily_v4_stage_c_admissibility.py`); `black --check` limpio después.
- `git diff --check` (con `git add -N` para el archivo de test nuevo) → solo avisos de conversión LF→CRLF de `core.autocrlf=true`, sin advertencias reales de espacios en blanco.

**Nota de proceso, para que quede trazado:** una primera tanda de estas
mismas verificaciones se ejecutó con `| tail -N` al final del pipeline, lo
que enmascaró el código de salida real de `pytest`/`ruff`/`black` detrás del
código de salida de `tail` (siempre 0) -- dos corridas que parecían "exit
code 0" en realidad tenían fallos reales (el bug de `integrity_manifest.json`
descrito en el punto 2, y la línea larga de `ruff`). Se detectó al leer el
contenido completo de cada archivo de salida en vez de confiar en el código
de salida reportado, y todas las verificaciones se re-ejecutaron sin `tail`
antes de reportar cualquier resultado como definitivo.

Solo datos sintéticos: no se leyó ningún CSV real de Pergamino/Balcarce ni el
holdout real 2024-2025, no se ejecutó ninguna etapa científica real, no se
abrió ningún holdout real, no se usó MLflow compartido, y `controlled_daily_v3`,
los baselines históricos, `backend/`, `frontend/` y `human_feedback/` quedan
sin alteración. No se hizo merge ni se habilitó auto-merge.

## Segunda revisión dirigida sobre el PR #194: cinco reproducciones adicionales corregidas (2026-09-15)

Encargo explícito de seguimiento sobre el mismo PR #194 (commit auditado
`b3bf0600cc6c739d01e91688f1192fc51bb60d1f`, el que cerraba la primera
revisión dirigida): el usuario reprodujo cinco defectos adicionales que
sobrevivieron a esa corrección y pidió cerrarlos con evidencia verificable,
sin repetir un resumen de la entrega anterior. `depth_role` no se reabre.

1. **Admisibilidad B→C todavía incompleta.** `diagnostics={"replicas_valid": 1}`
   sin los demás contadores, `valid=5, requested=1, discarded=-4` (la
   contabilidad `valid+discarded==requested` coincidía por casualidad con un
   descarte negativo), un bootstrap reducido/no normativo declarado
   científico, y evidencia de B sin `training_dataset_fingerprint.json`
   pasaban todos la admisibilidad. Corregido en `admissibility.py`: los tres
   contadores de `diagnostics` deben estar presentes como enteros no
   booleanos no negativos (`requested>0`, `valid>0`,
   `valid+discarded==requested`; ningún contador ausente se trata como `0`);
   `diagnostics.normative is True` se exige explícitamente para el camino
   científico (leído tal cual lo persistió B, nunca recalculado aquí); y se
   carga/valida estructuralmente `training_dataset_fingerprint.json` de B
   (sin exigirle igualdad con el fingerprint EXTENDIDO de C, que describe un
   período distinto). Los fixtures de
   `tests/test_controlled_daily_v4_stage_c_admissibility.py` ahora escriben
   por defecto un `training_dataset_fingerprint.json` válido y
   `diagnostics.normative=True` (antes ninguno de los dos existía, lo que
   hacía fallar incluso el camino feliz una vez agregada la validación).
2. **Dominio de ΔMCC incorrecto, bug propio de la primera corrección.**
   `interval_lower`/`interval_upper` de `bootstrap.json` reportan una
   DIFERENCIA de dos MCC (dominio matemático `[-2, 2]`), pero la primera
   corrección los validó contra el dominio de un MCC aislado (`[-1, 1]`),
   rechazando incorrectamente intervalos válidos como `[1.1, 1.3]`.
   Corregido con `_DELTA_MCC_LOWER_DOMAIN`/`_DELTA_MCC_UPPER_DOMAIN`
   (`[-2, 2]`) aplicado exclusivamente a esos dos campos, sin tocar el
   umbral de aprobación de B (`interval_lower >= -0.05`) ni el dominio de
   `mcc_candidate.value` (que sigue en `[-1, 1]`, correcto para un MCC
   aislado).
3. **Recuperación verificable todavía incompleta.** Un
   `integrity_manifest.json` con `schema_version` desconocido, o con
   `files` conteniendo únicamente un archivo ajeno (`only.txt`), pasaba la
   verificación de `verify_stage_c_recovery`. Corregido exigiendo
   `schema_version == STAGE_C_ARTIFACT_SCHEMA_VERSION` (bumpeado a
   `controlled_daily_v4_stage_c.v3`), que `files` cubra el conjunto
   COMPLETO de artefactos obligatorios (`REQUIRED_STAGE_C_ARTIFACT_NAMES`),
   que cada ruta declarada esté confinada a `output_dir`
   (`_is_path_confined`: rechaza rutas absolutas, `..`, o
   resoluciones/enlaces simbólicos que escapen del directorio, sin siquiera
   leer el archivo), y coherencia estructural mínima (cada artefacto `.json`
   declarado parsea, y `schema_version.json` coincide con el del
   manifiesto). Además, `cli.py::_run_stage_c` ahora lee el estado del
   ledger (y resuelve la rama de recuperación) ANTES de aplicar
   `check_output_directory_not_occupied` -- antes, ese chequeo corría
   primero y rechazaba erróneamente una recuperación que reutilizara el
   mismo `--output-dir` de la propia corrida ya finalizada (el caso más
   natural de "recuperar mis resultados"). El rechazo de una salida ocupada
   para una ejecución genuinamente NUEVA se conserva exactamente igual
   (sigue corriendo antes de la admisibilidad y de la reserva).
4. **Coherencia del registro del ledger todavía incompleta.** Un registro
   con `state='AUSENTE'` pero `confirmed_at`/`finalized_at`/
   `finalized_result_reference` ya poblados pasaba como AUSENTE real y
   permitía reservar de nuevo. Corregido con `_row_coherence_issue`
   (verifica que las columnas de una fila correspondan a alguna transición
   válida `AUSENTE`→`INDETERMINADA`→`CONFIRMADA`, incluida una finalización
   parcial), aplicado en las cuatro operaciones: `read_holdout_state`
   degrada a `INDETERMINADA` (nunca AUSENTE); `reserve_holdout`/
   `confirm_holdout_open`/`finalize_holdout` rechazan explícitamente con la
   nueva excepción `HoldoutRegistryCoherenceError`, sin reparar ni resetear
   ninguna columna.
5. **Identidad de los datos de C todavía incompleta.** No existía una
   huella separada del conjunto EFECTIVAMENTE evaluado del holdout (solo la
   del entrenamiento extendido). Corregido con `FINGERPRINT_SCOPE_STAGE_C_EVALUATION`
   (nuevo `scope`) y `StageCResult.evaluation_dataset_fingerprint`,
   calculado dentro de `run_stage_c` (por lo tanto, solo después de la
   apertura autorizada -- precondición ya documentada del módulo),
   persistido como `evaluation_dataset_fingerprint.json` e incluido en
   `integrity_manifest.json`/`REQUIRED_STAGE_C_ARTIFACT_NAMES`. Los
   fingerprints históricos de A/B no se tocan.

**Comandos realmente ejecutados** (mismo contenedor
`aai-hydric-v4-experiment:dev` reutilizado sin reconstruir):

- `pytest -q tests/test_controlled_daily_v4_stage_c_admissibility.py tests/test_controlled_daily_v4_holdout_ledger.py tests/test_controlled_daily_v4_stage_c_runner.py tests/test_controlled_daily_v4_stage_c_recovery.py` → **64 passed** en 31.12s.
- `pytest -q tests/test_controlled_daily_v4_holdout_ledger.py tests/test_controlled_daily_v4_stage_c_recovery.py tests/test_controlled_daily_v4_stage_c_admissibility.py` (tras agregar las nuevas regresiones) → **57 passed** en 23.08s.
- `pytest -q tests/test_controlled_daily_v4_stage_c_integration.py -k "recovery_succeeds_reusing"` → **1 passed** en 53.79s (verifica la recuperación sobre el propio directorio ocupado).
- `pytest -q tests/test_controlled_daily_v4_stage_c_integration.py` (archivo completo, 12 tests) → **12 passed** en 615.61s (0:10:15).
- `pytest -q tests/test_controlled_daily_v4_*.py` (suite completa) → **449 passed, 3 skipped, 0 failed** en 1027.57s (0:17:07).
- `ruff check src tests` → 3 líneas >100 columnas detectadas en una primera pasada (`artifacts.py`, `holdout_ledger.py` x2); corregidas; limpio después.
- `black --check src tests` → limpio (sin reformateos necesarios en esta ronda).
- `git diff --check` (con `git add -N` para los archivos nuevos) → solo avisos de conversión LF→CRLF de `core.autocrlf=true`, sin advertencias reales de espacios en blanco.

Solo datos sintéticos: no se leyó ningún CSV real de Pergamino/Balcarce ni el
holdout real 2024-2025, no se ejecutó ninguna etapa científica real, no se
abrió ningún holdout real, no se usó MLflow compartido, y
`controlled_daily_v3`, los baselines históricos, `backend/`, `frontend/` y
`human_feedback/` quedan sin alteración. No se hizo merge ni se habilitó
auto-merge.

## Tercera revisión dirigida sobre el PR #194: tres pendientes reproducidos y corregidos (2026-09-16)

Seguimiento sobre el mismo PR #194 (commit auditado
`5062e5ee7961b4361f503392741f9e429f314816`, el que cerraba la segunda
revisión dirigida): el usuario reprodujo tres pendientes concretos que
sobrevivían a esa corrección y pidió cerrarlos con evidencia verificable, sin
repetir un resumen de la entrega anterior. `depth_role` no se reabre.
Esquema de artefactos de C bumpeado a `controlled_daily_v4_stage_c.v4`.

1. **Configuración normativa de B insuficientemente verificada.**
   `check_stage_c_admissibility` aceptaba un antecedente científico cuyo
   bootstrap declaraba `replicas_requested=1, replicas_valid=1,
   replicas_discarded=0, seed=0, block_length=1, normative=True` -- la
   bandera `diagnostics.normative` nunca se contrastaba contra los
   parámetros efectivamente persistidos. Corregido recalculando
   `bootstrap.compute_is_normative_configuration(replicas_requested, seed,
   block_length)` sobre los valores REALMENTE consumidos (`BootstrapDiagnostics`
   ya los serializa) y comparando el resultado contra `diagnostics.normative`;
   se exige que `seed`/`block_length` sean enteros no booleanos presentes
   (nunca asumidos como default), y se cruza `resolved_config.json.seed`/
   `bootstrap_replicas` contra esos mismos valores efectivos (indicio de
   artefactos mezclados si difieren). 8 regresiones nuevas en
   `tests/test_controlled_daily_v4_stage_c_admissibility.py`: reproducción
   exacta del hallazgo, parámetros ausentes, `seed` booleano, configuración
   reducida declarada honestamente como `normative=False` (también
   rechazada), contradicción `resolved_config`↔`diagnostics` (dos casos), y
   el antecedente completo/normativo admitido.
2. **Vínculo histórico A→B nunca revalidado.** `check_stage_c_admissibility`
   nunca releía la evidencia REAL de A (`producer_dir/code_version.json`,
   `environment.json`, `dataset_fingerprint.json`): un
   `training_dataset_fingerprint.json` de B con `sha256` distinto del de A
   pasaba, y el antecedente seguía siendo admitido incluso tras eliminar los
   tres artefactos de evidencia de A. Corregido reutilizando
   `check_stage_b_admissibility` (el mismo validador ya usado en la
   transición real A→B) apuntado a `producer_dir` y a la evidencia
   PERSISTIDA de B como "consumidor histórico" (`b_code_identity`,
   `b_environment.get("validation_issues")`, `b_training_fingerprint` --
   nunca la identidad/entorno ACTUALES de la ejecución consumidora de C, que
   ya se verifican por separado en la compatibilidad B→C existente). Los
   rechazos se agregan a `reasons` prefijados con "Revalidación histórica
   A→B", sin duplicar una implementación más débil del validador existente.
   6 regresiones nuevas: fingerprint de B distinto del de A, ausencia de
   cada uno de los tres artefactos de evidencia de A por separado, identidad
   de código histórica sucia (`dirty=True`), y un spy que confirma cero
   reservas/cero acceso al holdout combinando ambos motivos de rechazo de
   esta ronda en la misma corrida.
3. **Identidad de las entradas de C no persistida.** `C` ya persistía
   `evaluation_dataset_fingerprint.json`, pero no los hashes/provenance de
   los CSV de entrada efectivamente consumidos. Corregido agregando
   `provenance_report`/`input_hashes` a `write_stage_c_artifacts` (mismos
   nombres ya establecidos por `write_stage_a_artifacts`:
   `provenance.json`/`input_hashes.json`), poblados en
   `cli.py::_run_stage_c` con el `ProvenanceReport` ya calculado en el Paso 4
   (DESPUÉS de `confirm_holdout_open`) -- nunca recalculado, nunca copiado de
   A. Ambos artefactos se agregaron a `REQUIRED_STAGE_C_ARTIFACT_NAMES`, por
   lo que `verify_stage_c_recovery` los exige. 1 assertion ampliada en
   `test_end_to_end_synthetic_a_to_b_to_c_full_flow` (los hashes persistidos
   coinciden con los bytes reales de los CSV sintéticos usados, e incluidos
   en `integrity_manifest.json`) y 2 regresiones nuevas en
   `tests/test_controlled_daily_v4_stage_c_recovery.py` (ausencia de
   `provenance.json`, alteración de `input_hashes.json`).

**Comandos realmente ejecutados** (mismo contenedor
`aai-hydric-v4-experiment:dev` reutilizado sin reconstruir):

- `pytest -q tests/test_controlled_daily_v4_stage_c_admissibility.py` (antes de agregar las regresiones, contra el código sin corregir) → **12 failed, 20 passed** -- confirma que las reproducciones fallan contra el código auditado.
- `pytest -q tests/test_controlled_daily_v4_stage_c_admissibility.py` (con el código corregido) → **32 passed** en 2.95s.
- `pytest -q tests/test_controlled_daily_v4_stage_c_recovery.py tests/test_controlled_daily_v4_stage_c_admissibility.py tests/test_controlled_daily_v4_stage_c_runner.py` → **62 passed** en 18.54s.
- `pytest -q tests/test_controlled_daily_v4_stage_c_integration.py` (12 tests, incluida la assertion ampliada de provenance/input_hashes) → **12 passed** en 326.98s (0:05:26).
- `pytest -q tests/test_controlled_daily_v4_*.py` (suite completa) → **464 passed, 3 skipped, 0 failed** en 1519.15s (0:25:19) -- exactamente 449 (cierre de la ronda anterior) + 15 regresiones nuevas de esta ronda (13 en `test_controlled_daily_v4_stage_c_admissibility.py`, 2 en `test_controlled_daily_v4_stage_c_recovery.py`).
- `ruff check` sobre los archivos tocados → 9 líneas >100 columnas detectadas en una primera pasada; `black` las reformateó (2 archivos); `ruff check`/`black --check` limpios después.
- `git diff --check` (con `git add -N` para los archivos nuevos) → solo avisos de conversión LF→CRLF de `core.autocrlf=true`, sin advertencias reales de espacios en blanco.

**Nota de proceso, para que quede trazado:** la reproducción de los tres
defectos se verificó revirtiendo temporalmente la corrección de
`admissibility.py` con `git stash` (identificado por mensaje único,
restaurado con `git stash apply <sha>` y luego `git stash drop`, nunca con
`git stash pop` a ciegas, dado que el stash es compartido entre sesiones) --
las 12 regresiones nuevas de ese archivo fallaron contra el código sin
corregir antes de aplicar la corrección, confirmando que reproducen el
defecto real y no solo ejercitan una rama ya admitida.

Solo datos sintéticos: no se leyó ningún CSV real de Pergamino/Balcarce ni el
holdout real 2024-2025, no se ejecutó ninguna etapa científica real, no se
abrió ningún holdout real, no se usó MLflow compartido, y
`controlled_daily_v3`, los baselines históricos, `backend/`, `frontend/` y
`human_feedback/` quedan sin alteración. No se hizo merge ni se habilitó
auto-merge.

## Orquestador reproducible de entrenamiento/evaluación del manifiesto operacional v3 (2026-09-21)

HU4/HU6, capacidad `predictive-modeling`/`architecture-integration`, CRISP-DM
modelado/evaluación. Cierra la tarea 3 (parcial: entrenar y congelar, sin
carga de bundles), 5.2 y 11 de
`openspec/changes/add-daily-multihorizon-predictors/tasks.md`. La evaluación
operacional (motor de bootstrap, `classify_horizon`, `make_final_decision`)
ya estaba implementada y probada (`2e22c6f`); lo que faltaba era la entrada
reproducible que conecta preparación, entrenamiento por horizonte/semilla,
calibración, baselines y decisión final — eso es lo que agrega esta entrega.

**Implementado:**

1. `src/predictive_modeling/operational_run.py` (nuevo): orquestador puro
   (no lee archivos) que, dado un manifiesto ya verificado
   (`calibration_manifest.verify_frozen_calibration_manifest`) y un
   DataFrame con su `dataset_sha256`, entrena un Random Forest por
   horizonte (`manifest.horizons`) y semilla (`training_seeds`) sobre
   `partitions.train`, calibra con `CalibratedClassifierCV(FrozenEstimator(...),
   method="sigmoid")` sobre `partitions.calibration` (reemplazo vigente de
   `cv="prefit"`, removido en la version de scikit-learn ya en uso — 1.9.x
   —, documentado en el docstring del módulo), calcula baselines
   raw/persistencia/climatología, arma las `ScopeObservations` por
   horizonte/semilla/ventana usando `target_date` como fecha de agrupamiento,
   corre el bootstrap conjunto UNA sola vez sobre toda la familia
   horizonte×semilla×período (`multiplicity.family_dimensions` incluye
   "horizon"), y arma un `HorizonContract`/`ArtifactIdentity` por horizonte
   con el modelo/calibrador de `deployment_seed`. Un horizonte cuyo
   entrenamiento falla (p. ej. una sola clase) queda `status="training_failed"`
   con motivo explícito, sin abortar los otros dos horizontes ni inventar su
   resultado.
2. `src/predictive_modeling/operational_run_artifacts.py` (nuevo): persiste
   cada corrida en un `output_dir` NUEVO y vacío (rechaza reutilizar uno
   ocupado), con identidad de manifiesto/dataset/código/entorno, predicciones
   por fecha, comparaciones contra baselines, diagnóstico y decisión final
   por horizonte, los `.joblib` del modelo/calibrador de `deployment_seed`, y
   un `report.md` legible por horizonte con límites explícitos ("solo
   evaluación de desarrollo", "`classify_horizon` no es aprobación final").
3. `scripts/run_operational_manifest_v3.py` (nuevo): entrada de línea de
   comandos. Verifica identidad del manifiesto, exige `--allow-real-data`
   explícito si `dataset.source_kind != "synthetic"` (protección adicional
   contra activar por error una corrida real), carga el dataset vía
   `data_ingestion.storage.load_dataset_snapshot` (hash y DataFrame de la
   MISMA lectura), corre el orquestador y persiste los artefactos.
4. Tres pruebas nuevas en `tests/test_calibration_assessment.py` que cierran
   la tarea 11 con fixtures reales (no mockeados) del motor ya existente:
   "rango sin respaldo" (un intervalo de probabilidad sin soporte suficiente
   sigue sumando al ECE pero no respalda cobertura — `insufficient_coverage`),
   "ventanas inestables" (una ventana de estabilidad corta con pocos bloques
   vuelve `insufficient_evidence` a la familia conjunta aunque el período
   completo por sí solo sería evaluable) y "banda amplia no basta" (una
   distribución bootstrap con dispersión real, mediana 0.067 dentro de
   tolerancia pero percentil 95 en 0.15 fuera de ella: `classify_horizon`
   falla porque solo mira el límite superior, nunca un resumen puntual).
5. `tests/test_operational_run.py` (nuevo): prueba integrada con un fixture
   sintético completo (240 días, 6 columnas, `dataset.source_kind="synthetic"`,
   parámetros de soporte/bootstrap reducidos y declarados como tales) que
   congela el manifiesto en un directorio temporal, lo verifica, y ejercita
   el orquestador de punta a punta para los tres horizontes; más una prueba
   de rechazo por hash de dataset no coincidente, una de familia de modelo
   no soportada, y una que fuerza (con `monkeypatch`) el fallo de
   entrenamiento de un único horizonte para verificar que los otros dos se
   evalúan con normalidad (tarea 5.2).
6. `tests/test_run_operational_manifest_v3_cli.py` (nuevo): smoke test del
   script de línea de comandos completo vía `subprocess`, contra un dataset y
   manifiesto sintéticos escritos en un directorio temporal: corrida exitosa
   con artefactos escritos, rechazo de una segunda corrida sobre el mismo
   `--output-dir`, y rechazo de un dataset declarado `source_kind="real"` sin
   `--allow-real-data`.

**No incluido en esta entrega (fuera del alcance acordado):** ninguna
corrida contra `data/melchor_romero_2024_consolidado.parquet` ni contra
ningún holdout; carga de un bundle ya persistido para reutilizarlo sin
reentrenar (tarea 3, parte "cargar"); publicación de porcentajes en una UI o
API (fuera de alcance explícito); registro en MLflow. `controlled_daily_v3`,
`controlled_daily_v4`, sus baselines históricos, `backend/`, `frontend/` y
`human_feedback/` quedan sin alteración.

**Comandos realmente ejecutados** (`aai-hydric-full:dev`, mount de este
worktree sobre `/workspace`, sin reconstruir imagen):

- `pytest -q tests/test_calibration_assessment.py` → **40 passed** en 2.74–3.50s
  (37 preexistentes + 3 nuevas de la tarea 11).
- `pytest -q tests/test_operational_run.py` → **4 passed** en 5.28–5.57s.
- `pytest -q tests/test_run_operational_manifest_v3_cli.py` → **3 passed** en
  ~22s (incluye dos subprocesos reales del CLI).
- `ruff check src tests scripts/run_operational_manifest_v3.py` y
  `black --check` sobre los mismos → limpio (182 archivos).
- `pytest -q tests/ --deselect tests/test_controlled_daily_v4_stage_a_integration.py
  --deselect tests/test_controlled_daily_v4_stage_b_integration.py
  --deselect tests/test_controlled_daily_v4_stage_c_integration.py` (suite
  completa menos las 3 integraciones lentas de v4) → **868 passed, 3 skipped,
  0 failed** en 1545.44s (0:25:45).
- `pytest -q tests/` (suite completa, sin exclusiones) → **894 passed, 3
  skipped, 0 failed** en 2394.09s (0:39:54) — confirma que las 3
  integraciones lentas de `controlled_daily_v4` tampoco se vieron afectadas.
- `git diff --check` (con `git add -A -n` para listar los archivos nuevos) →
  solo avisos de conversión LF→CRLF de `core.autocrlf=true`, sin advertencias
  reales de espacios en blanco.

Solo datos sintéticos: no se leyó ningún CSV/parquet real, no se abrió
ningún holdout, no se ejecutó ninguna corrida real del manifiesto v3, y no
se modificó ningún parámetro o cláusula de
`config/producer-calibration-plan.frozen.v3.json` ni de su identidad. No se
hizo merge ni se abrió PR.

## Reproducción histórica causal: demo de solo lectura (HU7/HU8) (2026-09-23)

Agrega la demo "Reproducción histórica" (`add-causal-historical-replay`):
un backtest retrospectivo de solo lectura sobre el único candidato admitido
(`base-seed4`, experimento 4, `controlled_daily_v3`, horizonte +3 días).
Paquete reproducible con política de admisión externa hardcodeada
(`src/historical_replay/admission_policy.py`), API mínima detrás de
`HISTORICAL_REPLAY_ENABLED` con contrato temporal corregido (nunca expone
campos futuros, ni siquiera como `null`), interfaz con aislamiento de
estado por `(origen, fecha simulada)` verificado en el render (no en un
efecto), y feedback de demostración (RH-07) aislado del circuito operativo.
HU7/HU8, capacidad `historical-replay`, CRISP-DM evaluación/despliegue. Sin
impacto sobre hipótesis, arquitectura, configuración experimental ni
resultados históricos de HU7/HU8; no se entrenó, no se infirió, no se
recalibró, no se recalculó ninguna métrica científica y no se accedió al
holdout v4.

Evidencia: `tests/test_historical_replay_*.py` + `test_build_replay_package.py`
(25 passed), `backend/tests/` completa (124 passed), `frontend`
(`npx vitest run`, 162 passed en 23 archivos; `npm run build` limpio),
`ruff`/`black` limpios sobre `src`, `tests`, `backend/app`. Verificación
real en navegador (dos instancias Docker desechables, nunca el contenedor
compartido) con discrepancia real, feedback registrado y preservado entre
sesiones. Detalle completo en
`openspec/scientific-closure/causal-historical-replay-2026-09-22/` y
`openspec/changes/add-causal-historical-replay/traceability.md`.

Pendiente conocido, no bloqueante: `GET /replay/history` todavía no
distingue `medida`/`imputada`/`no_determinado` por fila; no se probó
escritura concurrente de feedback para la misma predicción.
## UI de defensa Pergamino, primera iteración (2026-09-27)

- HU2/HU3/HU4/HU5/HU6, capacidad `alerting-ui` con contratos de `data-ingestion`, `predictive-modeling` y `human-feedback`; CRISP-DM: despliegue e integración para demostración. Sin cambio de configuración experimental, hipótesis, alcance científico, arquitectura de bundles o política del ensamble. HU7/HU8 solo se consultan como evidencia retrospectiva agregada.
- `origin/main` en `c0220f5` incorpora PR #223 y las tablas del capítulo 4. Rama aislada `feat/ui-defense-pergamino`; el trabajo local preexistente del checkout principal se conservó.
- Cinco emisiones persistidas de Pergamino, `2023-06-13`..`2023-06-17`, se consultan por GET histórico; se separan emisión, objetivo y reloj. La UI agrega procedencia externa, calidad, scores, observación posterior, revisión histórica y evidencia agregada sin nuevas inferencias.
- Proyección `frontend/public/retrospective-2023.json` derivada de `ui_summary.json` SHA-256 `2b640b360671e03fac9f8223380395667eb8d62df9845d39a2f9f508ce660998` y `metrics.json` SHA-256 `6a6a31d35196313061aa4363c98d422f4d1446a9f996d7af51cd93f762e67732`. `node scripts/check_retrospective_projection.mjs` comparó 18 filas método/horizonte, episodios e IC pareados con las tablas versionadas.
- Verificación local tras habilitar ejecución fuera del sandbox: frontend `npm test -- --run` 196/196; `npm run build` y `npm run lint` completados. `C:\tcnenv\Scripts\python.exe` ejecutó Python 3.13.14 y levantó el backend con `.demo-defense-data/session-2`. GET histórico real comprobó las cinco emisiones (`2023-06-13`..`17`), los tres horizontes y modelos, `probability_status=not_qualified`, A→B→A y lecturas reveladas solo hasta el reloj. POST histórico en session-2 guardó una revisión; otra petición con revisión obsoleta devolvió 409. Se corrigió la filtración de esa revisión al retroceder el reloj: GET real devuelve `pending`, revisión 0 y comentario nulo el 13/06, y recupera `confirmed`, revisión 2 y comentario el 14/06. El archivo dirigido `backend/tests/test_pergamino_ensemble_historical_reproduction.py` pasó 12/12; sus fixtures existentes preparan días sintéticos dentro de un directorio temporal y ejecutan inferencia de prueba, por lo que no se volverá a correr en esta iteración. No se generaron predicciones históricas reales ni se modificaron fuentes canónicas. La verificación de navegador y las capturas siguen bloqueadas: la herramienta rechazó explícitamente `127.0.0.1:5174` por una preferencia de usuario guardada y prohibió superficies alternativas.
- El usuario aportó `referencias/Mi cultivo · rediseño UI.html`. Se leyó el archivo real: contiene ocho vistas de escritorio y 390 px. La defensa adopta su tipografía de sistema, paleta azul y neutra, encabezado claro con navegación, espaciado y tarjetas compactas; se descartaron sus valores simulados de sensor, porcentajes, ajustes y revisiones. La comparación visual en navegador sigue pendiente por el bloqueo de acceso indicado arriba.
- El acceso de escritura al Git compartido requiere ejecutar los comandos mediante el mecanismo normal de aprobación fuera del sandbox. `gh auth status` confirmó sesión válida al usar ese mecanismo. No se alteraron permisos ni controles del directorio compartido.
- `prepare_defense_data.ps1` limita la salida a `.demo-defense-data/`, rechaza destinos existentes y enlaces en la raíz demo, exige los SHA-256 de ambos insumos autorizados y copia solo el Parquet y JSON de emisiones del sensor Pergamino. Los hashes de `session-1` coincidieron con la fuente y `session-2` se preparó con el gate nuevo; no se copiaron registros de feedback. La proyección pública solo contiene soporte, métricas y episodios agregados, intervalos, período y hashes de `ui_summary.json`/`metrics.json`; se verificó que no contiene rutas privadas, secretos ni predicciones fechadas.
- Corrección por feedback de uso: el backend respondía 200, pero la configuración local no incluía `http://127.0.0.1:5174` en CORS. El arranque ahora documenta `CORS_EXTRA_ORIGINS` y `VITE_API_BASE_URL`; GET real de la emisión 13/06 devuelve tres horizontes y `Access-Control-Allow-Origin: http://127.0.0.1:5174`. La interfaz destaca la decisión de alerta por emisión y horizonte, y separa fechas faltantes de variables sin datos. En lecturas reales del 13/06 hay 0 fechas faltantes y 4 variables sin dato en la ventana de 10 días; ambas cifras se comunican. Frontend: 197/197 tests, build y lint completos. El panel agregado se sirvió con HTTP 200 y esquema `defense-retrospective-aggregate.v1`. La inspección visual en navegador y capturas siguen pendientes por el bloqueo de Browser Use ya registrado.
- Verificación del alcance de alertas: se consultaron por GET las 15 decisiones guardadas de las cinco emisiones; las 15 tienen `alert: false`, con scores de ensamble entre 0,015 y 0,080 frente al umbral contractual 0,5. El objetivo de humedad informado por el backend es `< 0,18` en fracción volumétrica. Las lecturas externas disponibles del 13 al 17/06 muestran aproximadamente 36–38 % de humedad del suelo; no hay un caso positivo navegable en este conjunto. La UI muestra el objetivo y el dato externo de la fecha de emisión cuando existe, sin presentarlo como score, sensor instalado ni observación futura. No se generaron ejemplos ni predicciones para fabricar una alerta.

## Melchor Romero como segundo sitio real de demostración histórica (2026-09-28)

- HU2/HU3/HU4/HU5/HU6, capacidad `alerting-ui` con contratos de `data-ingestion`, `predictive-modeling` y `human-feedback` (misma arquitectura genérica por `sensor_id`, ADR-0008). CRISP-DM: despliegue e integración para demostración, no modelado nuevo. Sin cambio de configuración experimental, hipótesis, alcance ni arquitectura: `controlled_daily_v3`, `replay_packages/base-seed4-1157696b7b-v2` y `historical_replay/*` quedan intocados.
- **Corrección de premisa, hallada por relevamiento (Fase 1-3), documentada aquí para trazabilidad:** la tarea inicial asumía que Pergamino era el sitio ya integrado de la capacidad `historical-replay` (HU7/HU8, `backend/app/routers/replay.py`, `replay_packages/`) y que Melchor Romero sería el segundo. La evidencia real es la inversa: esa capacidad ya está construida, desde su origen, sobre el dataset real `melchor_romero_2024_consolidado` (evidencia congelada de `controlled_daily_v3`, `scientific-baseline-v3`) y no tiene ningún concepto de sitio múltiple — ADR-0008 excluye deliberadamente ese dataset del espacio de nombres `sensor_id`. "Pergamino" en este repositorio es una capacidad distinta: la demostración genérica multi-sensor (`pergamino-ensemble-demo`, `src/experiment_runner/pergamino_ensemble_demo_runner.py`, UI en `PergaminoDefensePage.tsx`/`HistoricalWalkthrough.tsx`), que sí es genérica por `sensor_id` y sí admite un segundo sitio real limpiamente. Se generalizó esa arquitectura, no la de `historical-replay` (que ADR-0008 excluye explícitamente de la generalización multi-sitio).
- Implementación: `src/experiment_runner/melchor_romero_historical_demo_runner.py` (nuevo, separado, nunca reejecuta ni reinterpreta `controlled_daily_v3`) carga el dataset real ya versionado `data/melchor_romero_2024_consolidado.parquet`, aplica imputación causal partición por partición (`data_quality.imputation.interpolate_missing_causal`, sin fuga, verificado por prueba de manipulación) y reutiliza el corte ya establecido y verificado para este dataset (`openspec/specs/architecture-integration/spec.md`, 2024-10-19) para train/calibración/evaluación. Ajusta y calibra las mismas 3 familias que Pergamino (regresión logística, random forest, HistGradientBoosting) para +1/+2/+3, exporta bundles reales (`predictive_modeling.bundle_export`) y sirve por la misma ruta v2 sin modificarla.
- `frontend/src/features/producer/HistoricalWalkthrough.tsx` generalizado con props opcionales (`availableDates`, `revealMax`, `provenanceNotice`), todas con el valor de Pergamino como default — `PergaminoDefensePage.tsx` no cambió una línea y sus pruebas pasan sin modificación. Nueva `MelchorRomeroDefensePage.tsx` + ruta `defensa-melchor-romero` (`useHashRoute.ts`, `App.tsx`), seleccionable desde la navegación genérica existente (`DestinationNav`, ya iterada sobre `ROUTES`, sin lógica dispersa `if site==...`).
- Cinco emisiones reales preparadas (`scripts/prepare_melchor_romero_historical_demo.py`, nuevo — ejecutable de forma reproducible, a diferencia de la preparación manual no versionada que tuvo Pergamino): `2024-10-20`..`2024-10-24`, dataset real (`origen=real`, sin CSV externo). Ejecutado localmente contra la app real (`FastAPI TestClient`, sin mocks): las 5 emisiones se prepararon, GET histórico devolvió 200 con los 3 horizontes y ensemble coherente, A→B→A determinista, y una comprobación cruzada confirmó que `pergamino-ensemble-demo` bajo el mismo directorio de datos responde `404 batch_not_prepared` (aislamiento estructural por `sensor_id`, nunca por coincidencia).
- Capacidad NO reproducida deliberadamente: el panel de evidencia agregada retrospectiva (`RetrospectiveEvidencePanel`, protocolo `controlled_daily_v4_external_pergamino`, evaluación 2023 ya ejecutada) no tiene equivalente para Melchor Romero — no existe ninguna corrida de evaluación retrospectiva agregada sobre este sitio en el repositorio. `MelchorRomeroDefensePage.tsx` lo declara explícitamente en vez de fabricar paridad.
- Pruebas nuevas: `tests/test_melchor_romero_historical_demo_runner.py` (11, dataset real, incluye prueba de no-fuga por manipulación de la partición de evaluación), `backend/tests/test_melchor_romero_historical_demo_http.py` (2), `backend/tests/test_melchor_romero_historical_walkthrough.py` (6, incluye aislamiento cruzado de sitios), `HistoricalWalkthrough.test.tsx` (+1, generalización de props sin fuga de estado A→B→A entre sitios), `App.test.tsx` (+1, secuencia Pergamino→Melchor Romero→Pergamino). Verde: `pytest -q` (783 previos + nuevos), `pytest backend/tests -q` (159), `npm test -- --run` (199), `ruff check`/`black --check` limpios sobre los archivos nuevos, `npm run lint`/`npm run build` limpios.
- Generalización demostrada: arquitectónica (un segundo sitio real, aislado, causal, con degradación explícita donde falta evidencia — el panel agregado). **No** se afirma generalización predictiva de los modelos: son ajustes nuevos, declarados, sobre una ventana propia y más corta que cualquier protocolo científico congelado, nunca una validación confirmatoria de HU7/HU8.
- Verificación visual en navegador: `VISUAL_VERIFICATION_PENDING` — sin acceso a Browser Use en esta sesión; toda la validación automatizada (backend, frontend, funcional vía TestClient real) se completó.

## Laboratorio de sensores de prueba, tercer modo de la UI de defensa (2026-09-28)

- HU5/HU6, capacidad `alerting-ui` con contratos de `data-ingestion` (ADR-0007 mock, ADR-0008 aislamiento por `sensor_id`), `data-quality` y `human-feedback`; CRISP-DM: despliegue/integración para demostración académica, no modelado nuevo. Sin cambio de configuración experimental, hipótesis, alcance ni arquitectura: `controlled_daily_v3`, `replay_packages/base-seed4-1157696b7b-v2` y `historical_replay/*` quedan intocados. Pergamino y Melchor Romero (recorridos históricos, PR #223/#225) no se modificaron.
- `origin/main` en `1b899d0` ya incluye Pergamino (#224) y Melchor Romero (#225). Rama `feat/ui-defense-sensor-lab` partida directo de `origin/main`.
- **Backend inspeccionado antes de construir la UI (mandato, sección 2):** el laboratorio reutiliza sin cambios los cuatro endpoints genéricos por `sensor_id` de ADR-0007/ADR-0008 — `POST /sensors/{sensor_id}/readings` (ingesta), `GET /quality/{sensor_id}` (calidad + `out_of_range` real, diagnóstico), `POST /forecast/{sensor_id}/run` (pipeline operativo real, `execute_configured_pipeline`) y `GET/POST /feedback/{sensor_id}/...` (revisión humana). Deliberadamente no se usó la fachada v2 (`producer_v2`, `emit_forecasts`, bundles de ensamble): esa fachada requiere sensores registrados en el catálogo y bundles operativos pre-entrenados compatibles con contratos de variables/unidades/frecuencia/historia/procedencia específicos (los de Pergamino/Melchor Romero) — conectarla a un sensor sintético nuevo habría requerido fingir esa compatibilidad, prohibido explícitamente por el mandato. No hizo falta ningún ajuste de backend: las capacidades existentes alcanzaron sin gaps.
- Cuatro escenarios reproducibles con semilla fija (`LAB_SEED=42`), implementados en `frontend/src/features/lab/`: A (backfill de 120 lecturas normales, mismo tamaño ya validado end-to-end en `openspec/specs/demo-simulation/spec.md`), B (una lectura con `temperature` fuera de `AGRONOMIC_RANGES`, marcada por el detector real de `data_quality.quality_report`), C (interrupción: se detiene la ingesta sin volver a pedir pronóstico), D (recuperación: se reingiere el período interrumpido y se vuelve a pedir pronóstico).
- Generador sintético propio (`readingGenerator.ts`, PRNG `mulberry32`, determinista) porque `data_ingestion.mock_sensor` (Python) no es importable desde el frontend; espeja los mismos límites físicos de `data_quality.rules.AGRONOMIC_RANGES`.
- Aislamiento: `sensor_id` con prefijo exclusivo `lab-` (`labSensor.ts`), nunca compartido con Pergamino/Melchor Romero/demo acelerada/histórico; "Reiniciar" genera una sesión nueva (`sensor_id` distinto) en vez de borrar la anterior. `.gitignore` extendido con `data/sensor__lab-*.parquet`/`data/feedback__lab-*.parquet`, mismo tratamiento que `demo-*`.
- Reutilización de UI existente (mandato: "reutilizá navegación, componentes y estilos"): `useForecastWorkspace` (workspace de pronóstico, invalidación de respuestas tardías por `sensor_id`+token), `ForecastPage` (revisión humana, confirmar/corregir) y `QualityPanel` (calidad/anomalías) se reutilizan sin modificar — el laboratorio solo agrega la orquestación de escenarios (`useSensorLabScenarios.ts`) y la página (`SensorLabPage.tsx`). Ruta `#laboratorio-sensores` agregada a `useHashRoute.ts`/`DestinationNav`/`App.tsx`, con el mismo patrón de layout de página completa que las páginas de defensa.
- **Corrección encontrada durante la verificación HTTP real (documentada por honestidad metodológica):** el primer diseño hacía terminar el backfill en "ayer" (día real), lo que dejaba siempre inmadura (fecha objetivo >= hoy) la fecha objetivo del único pronóstico emitido por corrida — la revisión humana nunca podía demostrarse en su rama "permitida" dentro de la misma sesión. Se ajustó `labBackfillEndDateUtc()` para terminar 6 días antes de hoy (margen sobre el horizonte de 3 días): confirmado con la misma verificación HTTP que el primer pronóstico (Escenario A) ya tiene fecha objetivo vencida y admite `confirm` real (200), mientras que el pronóstico más reciente tras la recuperación (Escenario D) todavía no vence y es rechazado con 409 real — ambas ramas del contrato de revisión demostradas con el backend real, ninguna fabricada.
- **Verificación HTTP real de punta a punta** (backend servido localmente en el puerto 8001 desde este worktree, sin mocks; procesos apagados al terminar), dos sesiones aisladas (`lab-httpcheck01`, `lab-httpcheck02`): Escenario A confirmó 120 filas totales, sin `out_of_range`, 87 filas de entrenamiento / 21 de evaluación, 1 veredicto con fecha objetivo ya vencida; confirmar ese veredicto devolvió 200/confirmada. Escenario B: `out_of_range.temperature` incluyó exactamente la fecha inyectada. Escenario C: el reloj simulado avanzó 4 días sin que cambiaran el período ni el total de filas reales (sin pronóstico re-pedido). Escenario D: período y total de filas recuperados (125 filas), pronóstico re-emitido; el veredicto más reciente (fecha objetivo aún no vencida) fue rechazado con 409 real al intentar confirmarlo. Aislamiento cruzado: la consulta de calidad de la primera sesión no cambió mientras se operaba la segunda; Pergamino y Melchor Romero devolvieron 404 (nunca tocados por este flujo). Se detectó y corrigió un efecto colateral del entorno de verificación (no del código de esta entrega): el intérprete usado tenía `data_ingestion` instalado en modo editable apuntando al checkout principal, así que los 4 Parquet sintéticos de esta verificación se escribieron ahí en vez de en este worktree — se identificaron y borraron del checkout principal; los directorios de MLflow generados sí quedaron en este worktree (ya ignorados por git) y no se tocó ningún archivo de Pergamino/Melchor Romero/histórico en ningún checkout.
- Pruebas nuevas: `frontend/src/features/lab/readingGenerator.test.ts` (determinismo del generador, límites físicos respetados tras 500 pasos, perturbación acotada) y `frontend/src/features/lab/SensorLabPage.test.tsx` (7 tests: rótulo permanente, Escenario A end-to-end con mocks, motivo real de B, banner de interrupción de C sin ingesta nueva, reinicio con `sensor_id` nuevo y controles bloqueados). Suite completa de frontend: 209/209. `npm run build` y `npm run lint` limpios, sin advertencias nuevas.
- No se tocó ningún archivo de `src/`, `backend/app/` ni tests de Python: el laboratorio es exclusivamente frontend, reutilizando contratos backend ya existentes y ya probados.
- Comandos de arranque exactos (ver también sección "Interfaz de usuario" arriba): stack completo con Docker Compose, o en local backend con Uvicorn apuntando a `backend/app/main:app` (requiere instalar el paquete en modo editable con los extras `dev,backend`) y frontend con `npm install`/`npm run dev` dentro de `frontend/` (variable `VITE_API_BASE_URL` si el backend no está en el puerto por defecto). Abrir la app y navegar a "Laboratorio · Sensores de prueba" desde el menú de destinos (ruta de hash `laboratorio-sensores`).
- Guion de laboratorio (~3 minutos): (1) abrir el laboratorio, señalar el rótulo permanente de datos sintéticos y el identificador de sensor propio; (2) iniciar el Escenario A y esperar el backfill (unos segundos) — mostrar calidad (120 filas, sin anomalías) y el primer pronóstico con su revisión humana ya disponible; (3) inyectar el Escenario B — mostrar el motivo real de la anomalía en el registro de la sesión; (4) interrumpir con el Escenario C — señalar que el reloj simulado avanza pero la última lectura real no cambia, y el aviso de verificar sensor y cultivo; (5) reanudar con el Escenario D — mostrar que la calidad se recupera y se vuelve a pedir pronóstico, y que revisar el resultado más nuevo puede seguir bloqueado mientras uno más viejo ya admite revisión; (6) reiniciar en una sesión nueva para mostrar el aislamiento.
- Capacidades efectivamente demostradas: ingesta genérica de sensor, aislamiento multi-sensor, detección real de valores fuera de rango, distinción explícita entre falta de datos y ausencia de alerta, pipeline de pronóstico operativo real, y ambas ramas del contrato de revisión humana (permitida y no permitida) con el motivo real del backend. No demostrado ni afirmado: aprendizaje continuo, desempeño predictivo sobre sensores físicos, ni ningún detector de anomalías más allá del que ya expone la consulta de calidad existente.
- Verificación visual en navegador (escritorio y 390px): `VISUAL_VERIFICATION_PENDING` — no se usó la herramienta de automatización de navegador en esta entrega (se priorizó la verificación HTTP real y automatizada según el mandato de esta tarea); queda como revisión manual pendiente. Lista breve de revisión manual sugerida: (a) que el layout a 390px no desborde en los controles de escenario ni en la tabla de calidad; (b) que el orden de tabulación llegue a los cinco botones (A/B/C/D/Reiniciar) y que Enter/Espacio los activen; (c) contraste del banner de interrupción y del rótulo permanente.

## Corrección de procedencia del recorrido histórico de Melchor Romero (F01) y de la atribución de evidencia agregada (F04) (2026-09-29)

- HU2 `data-ingestion` + HU6 `alerting-ui`/`architecture-integration`, contratos compartidos con `predictive-modeling` y `human-feedback` (misma arquitectura genérica por `sensor_id`, ADR-0008). CRISP-DM: corrección de trazabilidad/despliegue, no modelado nuevo. Sin cambio de configuración experimental, hipótesis, alcance ni arquitectura: `controlled_daily_v3`, `replay_packages/base-seed4-1157696b7b-v2` y `historical_replay/*` quedan intocados; no se ejecutó ningún A/B/C/H ni se reabrió el holdout.
- **F01 (imputación presentada como observación real):** `experiment_runner.melchor_romero_historical_demo_runner.build_daily_frame_from_repo_dataset` ya calculaba, vía `data_quality.imputation.interpolate_missing_causal`, un booleano `<variable>_imputado` por celda completada por forward-fill (el 26/10/2024 no tiene humedad en la fuente y se rellena con el valor del 25/10, exactamente el objetivo de las emisiones del 23/10 +3 y 24/10 +2), pero `data_ingestion.history.query_readings` (el lector genérico que comparten Pergamino, Melchor Romero y el laboratorio de sensores) nunca lo leía: el valor volvía como `origin=real`, sin advertencia, contado como observado. Corregido en `history.py` (nuevo `imputed_variables` por fila, `imputed_days` en la cobertura por variable, ya excluido de `observed_days`; procedencia tomada del flag ya calculado antes de la imputación, nunca inferida comparando valores entre días; `origin`/`provenance` a nivel de dataset no cambian — un dataset real puede contener valores imputados) y en `HistoricalWalkthrough.tsx` (humedad ausente → "Sin observación en la fuente"; valor imputado → identificado explícitamente, nunca presentado como observación independiente para contrastar el pronóstico). Sin estas columnas (Pergamino, laboratorio de sensores, cualquier otro sensor), el comportamiento es idéntico al de antes — verificado con la suite completa de ambos sin cambios.
- Demostraciones ya preparadas: no necesitan regenerarse — el bug estaba exclusivamente en la lectura, nunca en lo que `scripts/prepare_melchor_romero_historical_demo.py` ya guardaba en disco (esa persistencia no cambió de comportamiento). Se agrega igual, por mandato explícito y como defensa en profundidad, `scripts/refresh_melchor_romero_historical_demo_readings.py`: procedimiento idempotente que verifica identidad y correspondencia de fechas contra la fuente versionada antes de escribir, nunca toca bundles/emisiones/feedback, y se niega a escribir si no puede verificar la procedencia con certeza (probado en directorios temporales, nunca contra `data/` del usuario).
- **F04 (referencias mezcladas entre campañas):** `MelchorRomeroDefensePage.tsx` atribuía la evaluación agregada 2023 de Pergamino al protocolo científico `controlled_daily_v4_external_pergamino` (ADR-0011, etapas A/B/C) y afirmaba de forma demasiado amplia que no existe ninguna evaluación agregada para Melchor Romero. Corregido: esa evaluación 2023 es un protocolo propio y separado (`docs/research/ensemble-retrospective-evaluation-protocol.md`/`-results.md`, exploratorio, no independiente, auditoría científica FAIL por ejecución duplicada, sin superioridad ni resultado confirmatorio atribuido); Melchor Romero sí tiene su propia evidencia histórica v3 congelada (`controlled_daily_v3`, `scientific-baseline-v3`) con su propio alcance; son estos cinco bundles demostrativos concretos los que no tienen evaluación agregada propia acreditada en esta entrega.
- Pruebas nuevas/actualizadas: `tests/test_history.py` (+2, flags de imputación y compatibilidad hacia atrás), `tests/test_refresh_melchor_romero_historical_demo_readings.py` (nuevo, 4: refresco correcto, idempotencia, rechazo ante valor no verificable, rechazo ante fecha ausente de la fuente), `HistoricalWalkthrough.test.tsx` (+1, escenario exacto 25/10 observado · 26/10 imputado · 27/10 sin observación, más cobertura corregida), `App.test.tsx` (+asserciones sobre los textos corregidos de F04). Verde: `pytest tests/test_history.py tests/test_refresh_melchor_romero_historical_demo_readings.py tests/test_melchor_romero_historical_demo_runner.py -q` (29), `pytest backend/tests -q` (167), `pytest tests/ -q` (1259 passed, 11 skipped, 5 fallas preexistentes no relacionadas en `test_auxiliary_hitl_v1.py`/`test_export_ensemble_retrospective_tables.py`/`test_scientific_closure_checker.py`, ninguno de esos archivos tocado por este cambio y fuera del perímetro HU7/HU8 que esta entrega no toca), `npm test -- --run` (210), `npm run build`/`npm run lint` limpios, `ruff check`/`black --check` limpios sobre los archivos tocados, `git diff --check` limpio.
- Verificación visual en navegador: `VISUAL_VERIFICATION_PENDING` — sin acceso a herramienta de automatización de navegador en esta sesión; el escenario exacto del 26/10 (imputado, sin contraste) y del 27/10 (sin observación en la fuente) queda cubierto por pruebas automatizadas de componente (React Testing Library), no por verificación visual real.

## Cierre de robustez y claridad del sensor simulado (2026-09-29)

- HU5/HU6, capacidad `alerting-ui` (y `demo-simulation` solo para la carrera de respuestas de la demo acelerada); CRISP-DM: despliegue/comunicación. Sin cambio de hipótesis, alcance, arquitectura ni evidencia científica; no se reentrenó ningún sitio.
- Seis correcciones de frontend con pruebas de regresión: invalidación por generación de la orquestación del laboratorio (desmontaje/cambio de sesión, StrictMode, bloqueo síncrono, orden A→B→C→D), sin reintentos que sobrescriban datos aceptados (sesión nueva), D sin `period_end` con error controlado, orden de respuestas en `useDemoSession`, textos precisos de qué es simulado, y bloqueo de revisión de objetivos no vencidos (UTC). Sección plegable de conexión física como trabajo futuro.
- Ensayo real en Docker (`docker/defense-rehearsal/compose.yml`, proyecto aislado) y guion: `docs/design/sensor-lab-defense-guide.md`. Pendientes declarados: capturas y 390 px (pestaña oculta), demo acelerada en Docker, y verificación de artefactos de Melchor Romero contra un hash fijo.

## Rediseño profesional de la interfaz: prototipo, integración y cierre (2026-10-03)

- HU6, capacidad `alerting-ui`; CRISP-DM: despliegue/comunicación. Sin cambio de hipótesis, alcance, arquitectura ni configuración experimental; sin impacto sobre HU7/HU8. Base `origin/main` en `b56b97a` (tag `memoria-base-2026-09-29`). Rama `design/ui-professional-prototype`, plan y criterios de aceptación en `docs/design/ui-professional-redesign-plan.md`.
- **Etapa 1 (propuesta visual):** prototipo aislado en `design/prototypes/ui-professional/` (`python design/prototypes/ui-professional/serve.py`), sin dependencias ni red; datos de ejemplo trazables (humedad de Melchor Romero del parquet versionado; métricas de Pergamino 2023 del JSON versionado; serie de Pergamino ilustrativa y rotulada).
- **Etapa 2 (integración en `frontend/`):** tokens únicos, cinco secciones de navegación (rutas y anclas intactas), seguimiento histórico con franja de contexto, reloj con pasos y gráfico de humedad, Mi cultivo rediseñado sobre `/api/v2`, Evidencia por niveles y laboratorio con banda permanente de simulación. Sin cambios de contratos ni de política del backend (promedio de modelos, umbrales, reglas de revisión).
- **Etapa 3 (cierre):** accesibilidad (un `<h1>` por pantalla, sin saltos de encabezado, foco al navegar en todas las pantallas, pestañas con patrón ARIA), guía visual `docs/design/alerting-ui-visual-design.md` y spec `alerting-ui` actualizadas.
- **Verificación:** `npx vitest run` 277/277 (con `--maxWorkers=3`; con la máquina cargada hay timeouts intermitentes de 5 s), `tsc -b` y `npm run build` correctos, lint solo con advertencias previas (`ProducerTabs`, `HistoricalReplayPage`). En navegador contra el backend real en Docker (proyecto aislado `aai-defense-rehearsal`): seguimiento de Pergamino y Melchor Romero, Mi cultivo y herramientas; prueba en vivo de una emisión con respaldo previo y restauración verificada por SHA-256.
- **Pendientes declarados:** lector de pantalla; contraste de las etiquetas SVG por script; pasos del laboratorio contra Docker (escriben datos sintéticos); capturas de escritorio a 1440 px (la ventana de automatización no se redimensiona de forma fiable).
- **Herramientas técnicas sin mediciones (2026-10-03):** el pipeline plano exige un dataset por punto (`sensor__<id>.parquet`) que solo crean el Laboratorio y la demostración; el sensor por defecto `sensor-a` no tiene ninguno en el backend ni en `data/`, por lo que «Generar pronóstico» respondía 404 con la ruta interna del servidor. El backend no cambió. En la interfaz: el 404 de dataset ausente se traduce a un mensaje claro sin ruta (`NO_READINGS_MESSAGE`), «Generar pronóstico» se deshabilita mientras el punto no tiene mediciones y se orienta al Laboratorio (`NoReadingsHint`). «Aplicar observaciones» ya solo aparecía con correcciones registradas. 280/280 pruebas; verificado en navegador contra el backend real (`sensor-a` sin datos y `lab-6cbec9cfc4` con datos, solo lectura).
- **«Generar pronóstico» que parecía no hacer nada (2026-10-03):** con datos del Laboratorio el paso A sí emite el pronóstico (`POST /forecast/<lab-…>/run` 200); repetir la acción desde «Resumen e historial» devuelve el mismo, porque hay un pronóstico por día y no se reemplaza el ya emitido (comportamiento del backend, sin cambios). La interfaz no lo decía. Ahora informa el resultado: «Se agregó el pronóstico con datos hasta …» o «Se usó la última fecha con datos (…) y su pronóstico ya estaba emitido: no se agregaron días nuevos». Para un día nuevo hacen falta mediciones más recientes (pasos C y D del Laboratorio). 282/282 pruebas; verificado en navegador contra el backend real.
- **Del Laboratorio a Herramientas sin copiar el identificador (2026-10-03):** para usar los datos de una sesión del Laboratorio había que copiar el `lab-…` y pegarlo a mano en «Punto de medición (sensor)». Ahora, una vez cargado el historial (paso A), el Laboratorio ofrece «Ver «lab-…» en Resumen e historial» (aplica el sensor y abre Resumen), y «Herramientas técnicas» ofrece «Usar este sensor» si el usuario vuelve por el menú con otro sensor activo. Sin recargar la página en ningún paso; 285/285 pruebas; verificado en navegador contra el backend real.
- **Interfaz pensada para un productor de hortalizas como primer evaluador (2026-10-03):** (A) la app abre en «Mi cultivo» (ruta inicial `#productor`; `#demo` y `#reproduccion-historica` siguen siendo vistas de Herramientas técnicas) con una respuesta principal en lenguaje cotidiano (`ProducerAnswer`, `producerOutlook.ts`): «No se espera falta de agua en los próximos 3 días» / «Posible falta de agua pasado mañana…», la tira de tres días con ícono y texto, y siempre «revisalo igual»; «sin alerta» y «sin pronóstico» se mantienen separados. (B) nombres legibles de los puntos (`sensorLabels.ts`), sin el campo de sectores cuando no hay ninguno, y selección automática si hay un solo punto. (C) al elegir un punto se muestra el último pronóstico YA guardado (solo `GET`; nunca se emite solo) y «Actualizar pronóstico» es la acción explícita. (D) fechas en palabras («mañana», «el sábado 6 de junio») y, si las mediciones tienen 2 o más días, el titular pasa a «Este pronóstico no es actual» con el rango de fechas que cubría. Sin cambios de contratos ni de política (sin porcentajes de riesgo, acuerdo como acuerdo). Los desplegables de las tarjetas pasan a 44 px. 303/303 pruebas; verificado en navegador contra el backend real. Guion de la sesión con el productor: `docs/design/prueba-con-productor.md`. Pendiente: E (menú en dos niveles) y F («Cómo leer esto» en lenguaje simple).

- HU6, capacidad `alerting-ui`; CRISP-DM: despliegue/comunicación. Ronda final de auditoría de UI/UX (2026-10-03): semántica «sin alerta prevista», aviso único de pronóstico desactualizado, foco/título de `#demo` y `#reproduccion-historica`, barra móvil medida sin cambio de etiquetas, gráfico antes/después de la emisión. Sin cambio de hipótesis, alcance, arquitectura, backend ni configuración experimental; sin impacto sobre HU7/HU8. Detalle en `docs/design/ui-professional-redesign-plan.md`, sección 11.
