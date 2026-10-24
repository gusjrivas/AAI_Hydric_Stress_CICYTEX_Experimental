# Spec: alerting-ui

> **Alcance de presentación 2026-10-24:** por solicitud del autor, la UI expone
> Pergamino y Melchor Romero, más laboratorio sintético. CICYTEX queda fuera
> de rutas, navegación y recorrido guiado. La URL retirada usa la vista
> predeterminada. Los requisitos históricos de su pantalla se conservan como
> antecedente, no como obligación de exposición en esta presentación. Datos,
> API y evidencia experimental permanecen intactos. Ver
> [change](../../changes/focus-defense-ui-main-sites/proposal.md).

> **Actualización de presentación 2026-09-17:** por solicitud del usuario, las etiquetas
> vigentes son Resumen, Historial y observaciones, Datos disponibles, Ajustar próximos
> pronósticos y Acerca de esta herramienta. Los nombres de las entregas anteriores
> citados más abajo describen su momento. Se conservan hashes, contratos y operaciones.
> El resultado principal se explica en palabras; valor numérico, predictor, linaje y
> estudio se consultan mediante desplegables. El ajuste se presenta como «Aplicar
> observaciones» y explica que afecta la próxima ejecución, no los resultados previos.
> Los filtros muestran coincidencias sobre el total registrado. Ver
> [change simplify-producer-ui](../../changes/simplify-producer-ui/proposal.md).
> Implementación comprobada mediante 68 tests frontend, lint y build; revisión visual
> y validación de comprensión con usuarios pendientes.

> **Actualización normativa 2026-09-05:** rige el protocolo [controlled_daily_v3](../../../docs/research/protocolo-experimental-v3.md) y ADR-0009. Los ejemplos cuantitativos anteriores son históricos; no deben confundirse con la nueva evaluación de objetivos observados ni con inferencia futura.

Capacidad implementada (Épica 3, HU5+HU6 — primera exposición de retroalimentación humana y pipeline completo a través de una interfaz de usuario). Origen: `openspec/changes/add-alerting-ui/`. Este documento es la fuente de verdad vigente de la capacidad.

## Requirements

### Requirement: Ejecución de pronóstico desde la interfaz, por sensor

El sistema DEBE poder ejecutar el pipeline completo (calidad, modelado, alertas) sobre el dataset consolidado de un sensor dado, y devolver un veredicto para el último día observable disponible (alerta sí/no, probabilidad, fecha objetivo) sin exponer qué modelo lo generó.

#### Scenario: Correr un pronóstico produce un veredicto y persiste el feedback inicial

- **GIVEN** un dataset consolidado disponible para un `sensor_id` dado
- **WHEN** se invoca el endpoint de ejecución de pronóstico para ese sensor
- **THEN** se devuelve el veredicto correspondiente al último día observable (fecha, alerta, probabilidad, fecha objetivo), y el registro de retroalimentación de ese sensor queda persistido con esa fecha en estado `pendiente` (o conservando su estado previo si ya existía)

Implementado en `backend/app/routers/forecast.py` (`POST /forecast/{sensor_id}/run`), testeado en `backend/tests/test_forecast.py`.

**Comportamiento vigente:** `backend/app/pipeline.py::execute_configured_pipeline` construye la inferencia futura vía `predictive_modeling`/`architecture_integration.pipeline.predict_available` y filtra el resultado al último `timestamp` observable del dataset (`available[available.timestamp == latest]`) — no requiere que exista todavía el target futuro para emitir ese veredicto, y la respuesta incluye `fecha_objetivo` (`target_timestamp`) además de `fecha`/`alerta`/`probabilidad`. `POST /forecast/{sensor_id}/run` devuelve por lo tanto un único veredicto por corrida (el del día más reciente disponible para ese sensor), no una lista de veredictos sobre todo un holdout.

**Verificación histórica previa a la evolución hacia inferencia futura por sensor.** La verificación original (`train_rows=286`, `test_rows=71`, 22 de 71 fechas marcadas como alerta, dataset real de Melchor Romero 2024, sin `sensor_id`) corresponde a una versión anterior del endpoint, cuando devolvía la lista completa de veredictos sobre el holdout de evaluación en vez del último día observable. No debe usarse como evidencia del comportamiento actual; el contrato de respuesta (`ForecastRunResponse`) cambió de forma para reflejar el veredicto único.

**Modelo utilizado:** el backend operativo usa actualmente un contrato Random Forest explícito (`build_candidate_models(RANDOM_STATE)["random_forest"]`) cuando no existe un predictor recalibrado o cacheado reutilizable — ver la sección "Modelo operativo vs. selección automática experimental" al final de este documento. Esto reemplaza la actualización histórica de 2026-08-22 que documentaba selección automática entre candidatos como comportamiento vigente de esta capacidad; esa actualización describía correctamente su momento, pero ya no describe el código actual.

### Requirement: Consulta y validación humana de alertas

El sistema DEBE poder listar el registro de retroalimentación persistido, y permitir confirmar o rechazar una alerta puntual identificada por fecha.

#### Scenario: Confirmar una alerta vía la API

- **GIVEN** un registro de retroalimentación con una alerta en estado `pendiente` para una fecha dada
- **WHEN** se invoca el endpoint de confirmación para esa fecha
- **THEN** el registro persistido queda con esa fecha en estado `confirmada`

#### Scenario: Rechazar una alerta con corrección vía la API

- **GIVEN** un registro de retroalimentación con una alerta en estado `pendiente` para una fecha dada
- **WHEN** se invoca el endpoint de rechazo para esa fecha, con una etiqueta corregida y una observación
- **THEN** el registro persistido queda con esa fecha en estado `rechazada`, con la corrección y la observación guardadas

Implementado en `backend/app/routers/feedback.py` (`GET /feedback/{sensor_id}`, `POST /feedback/{sensor_id}/{fecha}/confirm`, `POST /feedback/{sensor_id}/{fecha}/reject`), testeado en `backend/tests/test_feedback.py`.

**Verificación histórica previa a la introducción obligatoria de `sensor_id` en las rutas** (ver ADR-0008): se hizo clic en "Confirmar" sobre la fila 2024-10-19 (su columna "Estado" pasó a "confirmada" inmediatamente) y en "Rechazar" sobre la fila 2024-10-20 (pasó a "rechazada" inmediatamente), contra un frontend y unas rutas anteriores al breaking change de PR #163. Al volver a correr el pronóstico desde la interfaz, ambas fechas conservaron su estado validado mientras las restantes se regeneraron en estado `pendiente` — esto confirmó el comportamiento de `upsert_feedback_log` de punta a punta a través de la interfaz de ese momento. El mecanismo de preservación (`upsert_feedback_log`) no cambió; las rutas y el frontend que lo ejercitan sí (ver la sección de multi-sensor).

### Requirement: Disparo manual de recalibración desde la interfaz

El sistema DEBE poder recalibrar el modelo usado para pronosticar a partir de las alertas rechazadas con corrección presentes en el registro de retroalimentación, y registrar el resultado de forma versionada.

#### Scenario: Recalibrar con correcciones pendientes

- **GIVEN** un registro de retroalimentación con al menos una alerta en estado `rechazada` con `etiqueta_corregida` no nula
- **WHEN** se invoca el endpoint de recalibración
- **THEN** se reentrena el modelo incorporando esas correcciones, el resultado queda registrado con una nueva versión, y la respuesta indica la versión registrada y cuántas correcciones se aplicaron

#### Scenario: Recalibrar sin correcciones pendientes

- **GIVEN** un registro de retroalimentación sin ninguna alerta `rechazada` con `etiqueta_corregida` no nula
- **WHEN** se invoca el endpoint de recalibración
- **THEN** se devuelve un error explícito indicando que no hay correcciones pendientes de aplicar, sin registrar ninguna versión nueva

Implementado en `backend/app/routers/recalibration.py` (`POST /recalibrate/{sensor_id}`) y `src/human_feedback/model_registry.py`. Testeado en `backend/tests/test_recalibration.py` y `tests/test_model_registry.py`. Verificado sobre datos reales: ver `docs/seguimiento-tareas.md`.

El mecanismo de recalibración invocado por este endpoint es `recalibrate_predictor` (`src/human_feedback/recalibration.py`), con las garantías temporales documentadas en `openspec/specs/human-feedback/spec.md` (requirement "Recalibración temporalmente controlada con retroalimentación madura"): solo incorpora correcciones cuyo target ya maduró y cuya validación humana ocurrió después de esa maduración.

**Actualización (2026-09-06) — linaje explícito, campo adicional retrocompatible:** cada recalibración exitosa registra además un evento de linaje (`openspec/specs/human-feedback/spec.md`, requirement "Linaje explícito de recalibraciones HITL") que vincula el predictor vigente (`source_model_id`), el predictor sucesor (`successor_model_id`) y el feedback nuevo que disparó la recalibración. `RecalibrationResponse` agrega el campo opcional `recalibration_id` (por defecto `None`, sin romper clientes existentes que lo ignoren) para permitir correlacionar la respuesta HTTP con ese evento; recuperarlo íntegramente requiere `human_feedback.model_registry.load_recalibration_lineage`/`list_recalibration_lineage`, no se expone todavía como ruta HTTP propia.

**Actualización (2026-09-05) — contrato de esquema obligatorio al registrar y validado al cargar:** una auditoría de reproducibilidad encontró que `register_recalibrated_model` guardaba metadatos de esquema (columnas de variables, horizonte, umbral, versión de pipeline) de forma opcional, y `load_latest_recalibrated_model` no verificaba compatibilidad antes de cargar — un modelo registrado con un esquema de variables distinto podía cargarse silenciosamente. Corregido: `register_recalibrated_model` ahora requiere `feature_columns`, `horizon_days`, `threshold` y `pipeline_version` (registrados como parámetros MLflow), y `load_latest_recalibrated_model(sensor_id, expected_feature_columns=None)` valida esas columnas contra las del modelo registrado antes de cargarlo, lanzando `ModelContractMismatch` (en vez de cargar silenciosamente) si no coinciden. `backend/app/routers/recalibration.py` y `backend/app/pipeline.py` ya pasan estos valores (`backend/app/config.py::HORIZON_DAYS`, `PIPELINE_VERSION`). Testeado en `tests/test_model_registry.py` (`test_load_latest_recalibrated_model_raises_on_feature_columns_mismatch`, entre otros).

### Requirement: Uso del modelo recalibrado en el próximo pronóstico

El sistema DEBE usar la versión más reciente del modelo recalibrado (si existe alguna) al ejecutar un nuevo pronóstico, en vez de entrenar un modelo nuevo desde cero.

#### Scenario: Pronóstico posterior a una recalibración

- **GIVEN** un modelo recalibrado ya registrado
- **WHEN** se ejecuta el pronóstico
- **THEN** las predicciones se generan con ese modelo registrado, sin reentrenar uno nuevo

#### Scenario: Pronóstico sin ninguna recalibración previa

- **GIVEN** que todavía no se registró ningún modelo recalibrado
- **WHEN** se ejecuta el pronóstico
- **THEN** se entrena un modelo nuevo, igual que el comportamiento previo a este *change*

Implementado en `backend/app/pipeline.py` (`execute_configured_pipeline`) y `src/architecture_integration/pipeline.py` (`skip_fit`). Testeado en `backend/tests/test_pipeline.py` y `tests/test_architecture_integration_pipeline.py`. Verificado sobre datos reales: ver `docs/seguimiento-tareas.md`.

### Requirement: Reutilización del modelo cacheado por sensor mientras el dataset no cambie

El sistema DEBE reutilizar, sin volver a entrenar, el último modelo ajustado para un sensor dado mientras el dataset consolidado de ese sensor no haya cambiado (según su huella/fingerprint); DEBE volver a ajustar cuando el dataset cambie o cuando todavía no exista un modelo cacheado para ese sensor. Este comportamiento solo aplica cuando no hay un modelo recalibrado registrado para ese sensor — la prioridad de un modelo recalibrado sobre el caché no cambia.

#### Scenario: El dataset no cambió entre dos corridas

- **GIVEN** un modelo ya cacheado para un sensor en una corrida anterior, sin modelo recalibrado registrado para ese sensor, y el dataset consolidado de ese sensor sin cambios
- **WHEN** se ejecuta una nueva corrida para ese mismo sensor
- **THEN** se reutiliza el mismo modelo cacheado sin volver a ajustarlo

#### Scenario: El dataset cambió entre dos corridas

- **GIVEN** un modelo ya cacheado para un sensor en una corrida anterior, sin modelo recalibrado registrado para ese sensor, y el dataset consolidado de ese sensor modificado desde esa corrida
- **WHEN** se ejecuta una nueva corrida para ese mismo sensor
- **THEN** se vuelve a ajustar el modelo, y el resultado reemplaza al modelo cacheado para ese sensor

#### Scenario: Un modelo recalibrado sigue teniendo prioridad sobre el caché

- **GIVEN** un modelo recalibrado registrado en MLflow para un sensor y, además, un modelo ya cacheado para ese mismo sensor
- **WHEN** se ejecuta una nueva corrida para ese sensor
- **THEN** se usa el modelo recalibrado, ignorando el caché

Implementado en `backend/app/pipeline.py` (`execute_configured_pipeline`, `_selection_cache` indexado por `sensor_id`), testeado en `backend/tests/test_pipeline.py`.

**Precisión sobre la semántica del caché:** este requirement se originó cuando el backend usaba selección automática entre candidatos (de ahí el nombre histórico "modelo auto-seleccionado"). El backend operativo vigente usa un contrato Random Forest explícito cuando no hay predictor recalibrado o cacheado (ver la sección "Modelo operativo vs. selección automática experimental" más abajo); el mecanismo de caché por huella de dataset y por sensor sigue vigente y sigue evitando reentrenar innecesariamente en cada corrida, independientemente de si el modelo subyacente es fijo o auto-seleccionado.

### Requirement: Observabilidad de solo lectura para la demo académica

El sistema DEBE exponer, por sensor y de solo lectura, la calidad/anomalías del dataset consolidado, la identidad verificable del predictor que usaría el próximo pronóstico, y la cadena completa de linaje de recalibraciones — sin modificar el dataset, sin entrenar ni recalibrar, y sin crear ningún run o versión nueva en MLflow.

#### Scenario: Consultar calidad y anomalías de un sensor

- **GIVEN** un dataset consolidado disponible para un `sensor_id` dado
- **WHEN** se invoca el endpoint de calidad de ese sensor
- **THEN** se devuelve el reporte de calidad (`data_quality.quality_report`) y anomalías (`data_quality.anomaly_detection.detect_anomalies`, exploratorio, calculado bajo demanda) sin modificar el dataset ni el predictor operativo

#### Scenario: Consultar el predictor activo sin que exista ninguno todavía

- **GIVEN** un sensor que nunca corrió un pronóstico ni una recalibración
- **WHEN** se invoca el endpoint del predictor activo de ese sensor
- **THEN** se devuelve la configuración del contrato (horizonte, columnas, lags, ventanas — siempre disponible desde `backend/app/config.py`) con `origin`, `model_id`, `version`, `trained_through` y `calibration_end` explícitamente `None`, nunca inventados

#### Scenario: Consultar la cadena de linaje completa

- **GIVEN** un sensor con una o más recalibraciones exitosas
- **WHEN** se invoca el endpoint de linaje de ese sensor
- **THEN** se devuelve la cadena cronológica completa (`human_feedback.model_registry.list_recalibration_lineage`), o un error HTTP explícito (409) si algún evento de linaje está corrupto o incompleto — nunca una cadena parcial ni un error oculto

Implementado en `backend/app/routers/quality.py` (`GET /quality/{sensor_id}`), `backend/app/routers/models.py` (`GET /models/{sensor_id}/active`) y `backend/app/routers/lineage.py` (`GET /lineage/{sensor_id}`). Testeado en `backend/tests/test_quality.py`, `backend/tests/test_models_active.py` y `backend/tests/test_lineage.py`, incluyendo verificación explícita de ausencia de efectos secundarios (ningún run ni versión de modelo nuevos).

El predictor "base configurado" (sin recalibración previa) se identifica leyendo la metadata del último predictor `issued` (`human_feedback.model_registry.load_latest_issued_predictor_metadata`, agregada junto con `get_latest_recalibrated_version` para esta capacidad) — nunca cargando ni entrenando un modelo distinto del que usaría `execute_configured_pipeline`.

### Requirement: Contexto global de sensor y aislamiento de solicitudes

La interfaz DEBE separar el sensor en edición del sensor activo, aplicar el cambio solo mediante confirmación explícita y validar `^[a-zA-Z0-9_-]{1,64}$`. DEBE evitar que datos o respuestas de un sensor se presenten como pertenecientes a otro.

#### Scenario: Editar y aplicar un sensor

- **GIVEN** un sensor activo con datos visibles
- **WHEN** se edita el identificador sin aplicar
- **THEN** el contexto y las consultas permanecen en el sensor activo
- **AND** al aplicar un identificador válido se limpia el contexto anterior y se consultan recursos del nuevo sensor; un valor inválido muestra un error asociado y no dispara consultas.

#### Scenario: Respuesta tardía del sensor anterior

- **GIVEN** una consulta pendiente del sensor A y un cambio aplicado al sensor B
- **WHEN** llega la respuesta de A después del cambio
- **THEN** no modifica datos, errores, contadores ni estados de carga de B.

Implementado en `frontend/src/App.tsx` (`draftSensorId`/`activeSensorId`, cabecera con formulario "Aplicar") y `frontend/src/features/forecast/useForecastWorkspace.ts` (descarte de respuestas obsoletas vía comparación con el sensor activo). Testeado en `frontend/src/App.test.tsx` y `frontend/src/features/forecast/ForecastPage.test.tsx`. Origen: Entrega 1 (tareas 1.1, 1.3, 1.5) de `openspec/changes/improve-alerting-ui-decision-workflow/`.

### Requirement: Consulta de historial independiente de la ejecución

La interfaz DEBE consultar el historial persistido al activar un sensor sin ejecutar pronóstico ni recalibración. DEBE preservar filas aunque falten probabilidad u objetivo.

#### Scenario: Consultar registros existentes

- **GIVEN** registros persistidos de un sensor
- **WHEN** se abre la aplicación o se aplica ese sensor
- **THEN** se muestran mediante GET, ordenados por fecha de referencia descendente, sin POST
- **AND** los valores ausentes se identifican como no disponibles, sin convertirse en cero o «Sin alerta».

#### Scenario: Registro ausente o consulta fallida

- **GIVEN** una consulta de historial
- **WHEN** retorna 404 por ausencia de registro
- **THEN** se muestra «Todavía no hay pronósticos registrados» y la acción explícita de generar uno
- **AND** cualquier otro error se muestra con reintento de lectura, sin presentarse como historial vacío ni contador cero.

#### Scenario: Filtrar el historial

- **GIVEN** un historial cargado
- **WHEN** se filtra por alerta, estado de validación o rango inclusivo de fecha de referencia
- **THEN** se muestran las coincidencias sin nuevas escrituras y se permite limpiar los filtros
- **AND** un resultado sin coincidencias se distingue de un historial vacío; los contadores generales conservan el total sin filtrar.

Implementado en `frontend/src/features/forecast/useForecastWorkspace.ts` (`GET /feedback/{sensor_id}` al activar el sensor, distinción de `HttpError` 404 frente a otros fallos) y `frontend/src/features/forecast/ForecastPage.tsx` (`fieldset` de filtros por alerta/estado/rango de fecha, aplicados sobre `workspace.rows` ya cargado, sin disparar nuevas consultas). Testeado en `frontend/src/features/forecast/ForecastPage.test.tsx`. Origen: Entrega 1 (tareas 1.2, 1.5) y Entrega 2 (tarea 2.3) de `openspec/changes/improve-alerting-ui-decision-workflow/`.

### Requirement: Navegación centrada en la decisión y resumen fiel

La interfaz DEBE ofrecer Resumen, Alertas y revisión, Calidad de datos, Modelo y trazabilidad, y Evidencia y arquitectura. El Resumen DEBE priorizar el último pronóstico registrado, sus fechas y el acceso a revisión humana.

#### Scenario: Leer el resumen

- **GIVEN** un historial disponible
- **WHEN** se abre Resumen
- **THEN** se presenta la fila con mayor fecha de referencia, su alerta, probabilidad disponible y fecha objetivo
- **AND** se distingue esa fecha de la cobertura de datos y se conserva la aclaración de señal predictiva relativa, no diagnóstico ni probabilidad agronómicamente calibrada.

#### Scenario: Navegar sin perder contexto

- **GIVEN** un sensor activo y un resultado consultado o generado
- **WHEN** se cambia de destino o se usa Atrás/Adelante
- **THEN** se conserva el contexto compartido, se identifica el destino activo y se enfoca su encabezado, sin iniciar POST
- **AND** los enlaces previos a calidad, predicción, linaje y evidencia siguen resolviendo al destino correspondiente.

Implementado en `frontend/src/features/navigation/useHashRoute.ts` (ruteo por hash entre los cinco destinos, sin librería de terceros — el navegador resuelve Atrás/Adelante sobre `location.hash`), `frontend/src/features/navigation/DestinationNav.tsx` (destino activo con `aria-current="page"`), `frontend/src/App.tsx` (título de documento y foco del encabezado por destino, `useForecastWorkspace` instanciado una única vez y compartido entre Resumen y Alertas y revisión) y `frontend/src/features/summary/ResumenView.tsx`. Los anchors previos `#calidad`, `#prediccion`, `#linaje` y `#evidencia` siguen resolviendo a sus destinos; `#resumen` es la entrada por defecto. Testeado en `frontend/src/App.test.tsx` y `frontend/src/features/summary/ResumenView.test.tsx`. Origen: Entrega 2 (tareas 2.1, 2.2, 2.5) de `openspec/changes/improve-alerting-ui-decision-workflow/`. **Actualización 2026-10-03 (rediseño UI, `docs/design/ui-professional-redesign-plan.md`):** el ruteo por hash cubre diez anclas agrupadas en cinco secciones de la navegación principal (`AppHeader.tsx`: Seguimiento histórico, Mi cultivo, Laboratorio, Evidencia y Herramientas técnicas; `useHashRoute.ts`: `ROUTE_GROUP`). «Resumen» e «Historial y observaciones» se presentan como una entrada («Resumen e historial», `SummarySwitch`) con ambas anclas vigentes; se agrega `#evidencia-resultados`. El foco programático pasa a ser el `<h1>` de cada pantalla (`id="<ruta>-heading"`). Ninguna capacidad ni ancla se eliminó. Testeado en `frontend/src/App.test.tsx`.

**Alcance de esta actualización:** los filtros de alerta/estado/rango sobre el historial se describen en el requirement "Consulta de historial independiente de la ejecución" (Entrega 2, tarea 2.3), no aquí. La corrección humana explícita con etiqueta y observación (requirement "Corrección humana explícita y recuperable" más abajo) y el traslado de la recalibración manual a Modelo y trazabilidad (requirement "Estado honesto de correcciones y recalibración" más abajo) se agregaron en la Entrega 3.

### Requirement: Operaciones explícitas y protección de mutaciones

La interfaz DEBE serializar sus mutaciones por instancia y mostrar su progreso. Durante una mutación DEBE impedir otra mutación y aplicar un cambio de sensor; DEBE permitir navegar. No DEBE reintentar escrituras automáticamente.

#### Scenario: Evitar operaciones superpuestas

- **GIVEN** un pronóstico, validación o recalibración pendiente
- **WHEN** se intenta repetir la acción, modificar otra fila o iniciar otra mutación
- **THEN** se mantiene una sola escritura en curso y su control muestra progreso
- **AND** al completarse o fallar se liberan los controles sin perder el sensor de origen.

#### Scenario: Escritura exitosa con actualización fallida

- **GIVEN** un POST exitoso seguido de un GET fallido
- **WHEN** se presenta el resultado
- **THEN** se conserva la respuesta exitosa y se comunica por separado el fallo de actualización, con reintento GET
- **AND** no se invita a repetir el POST como si la operación no hubiera ocurrido.

#### Scenario: Resultado de escritura no verificable

- **GIVEN** una pérdida de conexión durante un POST
- **WHEN** no puede confirmarse su resultado
- **THEN** la interfaz explica la incertidumbre y ofrece consultar el estado antes de repetir la operación, sin reintento automático.

Implementado en `frontend/src/features/forecast/useForecastWorkspace.ts` (bloqueo único `activeMutation` compartido entre pronosticar/confirmar/rechazar/recalibrar, reconciliación por `fecha` entre el resultado de un POST y su GET de refresco, y distinción entre `HttpError` — con respuesta — y un fallo de red sin respuesta). Testeado en `frontend/src/App.test.tsx` y `frontend/src/features/forecast/ForecastPage.test.tsx`. Origen: Entrega 1 (tareas 1.3, 1.4, 1.5) de `openspec/changes/improve-alerting-ui-decision-workflow/`.

### Requirement: Corrección humana explícita y recuperable

La interfaz DEBE permitir confirmar el resultado o corregirlo mediante una etiqueta observada explícita y una observación editable. DEBE mostrar errores junto a la fila y conservar la autoridad del backend sobre maduración y procedencia.

#### Scenario: Guardar una corrección

- **GIVEN** una fila y su resultado original
- **WHEN** se abre «Corregir resultado»
- **THEN** se muestran resultado original y fecha objetivo, y no se envía ninguna escritura hasta guardar una etiqueta opuesta seleccionada explícitamente
- **AND** se envía la observación introducida, o cadena vacía si se omite, sin texto inventado; elegir la misma etiqueta orienta a confirmar.

#### Scenario: Confirmación o corrección guardada

- **GIVEN** una validación aceptada por el servidor
- **WHEN** se recibe la fila actualizada
- **THEN** la interfaz refleja ese registro y anuncia que la validación se guardó sin actualizar el modelo
- **AND** conserva separado el estado de alerta del estado de revisión.

#### Scenario: Cancelación o rechazo temporal

- **GIVEN** un formulario de corrección abierto
- **WHEN** se cancela
- **THEN** no se escribe y el foco retorna al activador
- **AND** si se guarda y el backend responde 409, se muestra su motivo junto a la fila y se conserva el contenido para revisión, sin eludir la regla temporal.

Implementado en `frontend/src/features/forecast/CorrectionForm.tsx` (formulario inline por fila; etiqueta observada como radio sin preselección, deshabilita "Guardar corrección" si coincide con el resultado original y muestra una guía hacia "Confirmar"; "Cancelar" no escribe y devuelve el foco al botón "Corregir resultado" de esa fila vía una referencia por fecha) y `frontend/src/features/forecast/useForecastWorkspace.ts` (`confirm`/`reject` devuelven si la escritura tuvo éxito, para que el formulario permanezca abierto con su contenido ante un 409 y solo se cierre tras éxito). Testeado en `frontend/src/features/forecast/ForecastPage.test.tsx` (describe "corrección inline"). Origen: Entrega 3 (tareas 3.1, 3.2, 3.5) de `openspec/changes/improve-alerting-ui-decision-workflow/`.

### Requirement: Estado honesto de correcciones y recalibración

La interfaz DEBE diferenciar correcciones registradas de fechas incorporadas al predictor activo. No DEBE inferir elegibilidad temporal ni incorporación de una edición posterior a partir del estado «rechazada» o de la sola fecha.

#### Scenario: Correcciones registradas y fechas incorporadas

- **GIVEN** feedback rechazado y metadata del predictor con `applied_feedback_dates`
- **WHEN** se presenta el resumen de recalibración
- **THEN** se muestran por separado las correcciones registradas y las fechas incorporadas
- **AND** no se rotula su diferencia como correcciones elegibles; si falta metadata, la incorporación se informa como desconocida.

#### Scenario: Recalibrar explícitamente

- **GIVEN** correcciones registradas y ninguna mutación pendiente
- **WHEN** el usuario ejecuta recalibración manual
- **THEN** el backend determina si son aplicables; sus rechazos se muestran sin inventar una versión nueva
- **AND** tras éxito se actualizan predictor y linaje, se conservan los pronósticos anteriores y se indica que la próxima ejecución usará el nuevo predictor, sin afirmar mejora de desempeño.

Implementado en `frontend/src/features/forecast/RecalibrationPanel.tsx`, montado en Modelo y trazabilidad (`App.tsx`, destino `#linaje`) junto a `ActivePredictorSummary` y `LineageChain`. Consulta de forma independiente `GET /models/{sensor_id}/active` para las fechas `applied_feedback_dates`; si esa consulta falla, la incorporación se muestra explícitamente como desconocida en vez de asumir "no incorporada". No calcula un total de correcciones "elegibles": solo cuenta las filas `rechazada` con `etiqueta_corregida` no nula (correcciones registradas) y, por separado y solo informativamente, si su fecha aparece en `applied_feedback_dates` — sin inferir que una corrección posterior a esa fecha ya fue aplicada. Tras una recalibración exitosa, `predictorRefreshToken`/`lineageRefreshToken` (`App.tsx`) fuerzan un refetch de predictor y linaje; el historial de Alertas y revisión no se recarga ni se modifica. El error de una recalibración (p. ej. sin correcciones temporalmente elegibles) usa un campo separado (`recalibrateError`) del error de un pronóstico, para no aparecer fuera de contexto en Resumen. Testeado en `frontend/src/features/forecast/RecalibrationPanel.test.tsx`. Origen: Entrega 3 (tareas 3.3, 3.4, 3.5) de `openspec/changes/improve-alerting-ui-decision-workflow/`.

### Requirement: Presentación accesible y adaptable

La interfaz DEBE mantener jerarquía visual, tema claro consistente, controles etiquetados, foco visible y estados comprensibles sin depender del color. DEBE permitir completar consulta y revisión mediante teclado.

#### Scenario: Uso mediante teclado

- **GIVEN** navegación con teclado sin ratón
- **WHEN** se selecciona sensor, consulta historial, corrige una fila y abre detalles
- **THEN** todos los controles son alcanzables y operables, el foco no queda oculto y los mensajes de guardado/error son anunciados
- **AND** los identificadores completos no dependen exclusivamente de hover o `title`.

Implementado en `frontend/src/index.css` (tokens de color centralizados con contrastes verificados por cálculo — fórmula de luminancia relativa de WCAG, no solo inspección visual —, regla global `:focus-visible`, enlace "Saltar al contenido" hacia `<main id="main-content" tabIndex={-1}>`), `frontend/src/App.tsx` (foco programático al `<h2>` de cada destino tras navegar, reconfirmado por `document.activeElement`), `frontend/src/features/evidence/EvidencePanel.tsx` (contenedor de la tabla formal como `role="region"` con `tabIndex={0}`, alcanzable y desplazable por teclado). El badge de estado de revisión (pendiente/confirmada/rechazada) usa una paleta propia, distinta de la señal de alerta/sin alerta — confirmar ya no se presenta como "seguro" (verde). Testeado en `frontend/src/App.test.tsx` (enlace de salto y su destino) y `frontend/src/features/evidence/EvidencePanel.test.tsx` (región de scroll enfocable). Origen: Entrega 4 (tarea 4.1, 4.3 parcial) de `openspec/changes/improve-alerting-ui-decision-workflow/`. **Actualización 2026-10-03 (rediseño UI):** paleta azul sobre blanco sin verdes, tres lenguajes de estado con tokens separados (señal, calidad del dato y revisión), contraste de texto medido ≥ 7:1 (valores en `docs/design/alerting-ui-visual-design.md`), pestañas de Evidencia con el patrón ARIA (flechas, Inicio y Fin; `EvidenceResultsPage.tsx`), encabezados sin saltos de nivel y barrido del DOM real con ids únicos y referencias `aria-*` válidas. Testeado en `EvidenceResultsPage.test.tsx`, `HistoricalWalkthrough.redesign.test.tsx` y `App.test.tsx`. Pendiente: lector de pantalla y contraste de las etiquetas SVG por script.

**Alcance de esta actualización — pendiente, no verificado:** el escenario "Pantalla angosta, zoom y contraste" del delta de este change (anchos 360/768/1440 px, reflow a 320 CSS px, zoom 200%) **no se mergea a este requirement**: no pudo verificarse en esta entrega por una limitación del entorno de automatización (la herramienta de redimensionado de ventana no tuvo efecto). El trazado manual completo de Tab por teclado tampoco se pudo confirmar con confianza en esta sesión (resultados inconsistentes entre intentos); el orden de foco se verificó en cambio por inspección directa del DOM. Detalle completo en `openspec/changes/improve-alerting-ui-decision-workflow/tasks.md`, tarea 4.3.

### Requirement: Conservación de evidencia y explicación científica

La interfaz DEBE conservar el acceso al recorrido de arquitectura, evidencia congelada, procedencia y limitaciones, diferenciados del estado operativo por sensor.

#### Scenario: Consultar evidencia y trazabilidad

- **GIVEN** cualquier sensor seleccionado
- **WHEN** se abre Evidencia y arquitectura
- **THEN** los valores y fuentes científicas existentes permanecen idénticos y la navegación no ejecuta experimentos
- **AND** Modelo y trazabilidad presenta el predictor para el próximo pronóstico sin atribuirlo a registros históricos; un error de integridad del linaje permanece explícito.

Implementado en `frontend/src/App.tsx` (destinos `#evidencia` y `#linaje`, ya establecidos desde la Entrega 2) y verificado nuevamente tras el rediseño visual de la Entrega 4: los valores de `EvidencePanel.tsx` (evidencia congelada `controlled_daily_v3`) y `ArchitectureFlow.tsx` (recorrido de defensa) no cambiaron; un fallo de integridad de linaje (409 simulado) se muestra explícito en Modelo y trazabilidad, sin ocultarse ni presentarse como cadena vacía. Testeado en `frontend/src/features/evidence/EvidencePanel.test.tsx`; verificado también en navegador con un `fetch` interceptado simulando un evento de linaje corrupto. Origen: Entrega 2 (tarea 2.4) y Entrega 4 (tarea 4.7) de `openspec/changes/improve-alerting-ui-decision-workflow/`.

### Requirement: Control explícito de demostración opcional

La UI DEBE mostrar controles cotidianos de inicio, pausa y continuación cuando el controlador local esté configurado, manteniendo el uso normal si no lo está.

#### Scenario: Abrir la demostración

- **GIVEN** una sesión preparada accesible
- **WHEN** se abre la vista de demostración
- **THEN** se muestra sensor, día simulado, progreso y estado bajo el rótulo permanente «Demostración con datos simulados»
- **AND** navegar solo consulta; iniciar requiere una acción explícita.

#### Scenario: Controlador ausente o inaccesible

- **GIVEN** controlador no configurado o consulta fallida
- **WHEN** se usa la aplicación
- **THEN** las vistas operativas siguen disponibles y no se crea una sesión automáticamente
- **AND** si hay pérdida de conexión se advierte que la demo podría seguir activa, sin afirmar que está pausada.

Implementado en `frontend/src/features/demo/{DemoPage.tsx,useDemoSession.ts,api.ts}` y `frontend/src/api/demoControlUrl.ts` (HU6, `openspec/changes/add-accelerated-sensor-demo/`, entrega 3). La vista es un enlace propio (`#demo`) fuera del ruteo principal de destinos, visible solo si `VITE_DEMO_CONTROL_BASE_URL` está configurada; ninguna acción prepara ni crea sesiones, solo `GET/POST /demo/session*` del contrato de `scripts/demo_simulation/service.py` (entrega 2). Testeado en `frontend/src/features/demo/DemoPage.test.tsx` y `frontend/src/App.demo.test.tsx` (27 tests). Verificado además en navegador real (Chrome, extensión de automatización) contra el backend y el controlador reales vía Docker Compose (entrega 4, 2026-09-18): sin `VITE_DEMO_CONTROL_BASE_URL` no aparece el enlace ni se emite ningún request al controlador; con la variable configurada pero el servicio caído, se muestra "No se pudo consultar el estado; la demostración podría seguir en marcha" sin afirmar pausa, y el estado se recupera de inmediato al restablecerse la conexión o al volver a la pestaña.

### Requirement: Refresco por progreso confirmado

La UI DEBE consultar el estado sin solicitudes superpuestas y actualizar historial y calidad cuando avance una revisión confirmada, sin ejecutar POST por refrescar.

#### Scenario: Ver un nuevo día

- **GIVEN** una demostración en ejecución
- **WHEN** el controlador confirma una nueva ingesta y su pronóstico
- **THEN** la UI actualiza datos e historial del sensor correcto, conserva filtros y presenta la cantidad real de resultados guardados
- **AND** no agrega registros optimistas ni confunde el día simulado con hoy.

#### Scenario: Cambiar de sensor o volver a la pestaña

- **GIVEN** una sesión que continúa en el controlador
- **WHEN** el usuario consulta otro sensor o vuelve a la pestaña
- **THEN** las respuestas obsoletas no contaminan el contexto; volver a la demo consulta su estado real sin iniciar otro worker.

Implementado en `frontend/src/features/demo/useDemoSession.ts` (polling GET cada 2 segundos con una referencia en vuelo que evita solicitudes superpuestas; el polling corre mientras la vista está montada, sin condicionarlo al estado de visibilidad del documento — ver limitación más abajo) y `App.tsx` (dispara `workspace.reloadHistory()` y un `refreshToken` de calidad solo cuando cambia la fecha de ingesta o pronóstico confirmada del sensor de demo activo). Verificado con el contrato real en tres sesiones de demostración completas (entrega 4, 2026-09-18: `demo-be97e84561`, `demo-d8a94926ce`, cinco días cada una): fechas consecutivas (`GET /feedback/{sensor}` devolvió exactamente cinco registros por sesión, sin duplicados), progreso confirmado reflejado en la UI paso a paso, y aislamiento entre el sensor de demo y `sensor-a` al cambiar de sensor sin detener ni mezclar el worker.

**Hallazgo de esta entrega, corregido:** la primera implementación pausaba el polling mientras `document.visibilityState` era `"hidden"`. Al verificar en un navegador real la pestaña reportó `"hidden"` de forma persistente pese a estar activa en pantalla (artefacto del entorno de automatización), exponiendo un riesgo real: si el montaje inicial coincidía con ese estado, la vista quedaba cargando indefinidamente sin nunca hacer el primer GET. Se corrigió en la entrega 3 (PR #204): el polling corre siempre que la vista está montada; `visibilitychange` solo dispara un refresco inmediato adicional al volver a la pestaña.

### Requirement: Revisión humana posterior a la reproducción

La UI DEBE impedir mutaciones manuales del sensor demo hasta completar la sesión. Luego DEBE conservar la validación temporal del backend y distinguir objetivos sin datos.

#### Scenario: Intentar escribir durante la reproducción

- **GIVEN** sesión preparada, en ejecución, pausándose, pausada o bloqueada
- **WHEN** se consulta el sensor demo
- **THEN** generar pronóstico, confirmar/corregir y aplicar observaciones manualmente están deshabilitados con explicación; los controles de demo y las consultas siguen disponibles.

#### Scenario: Revisar un resultado al terminar

- **GIVEN** sesión completada y una fecha objetivo ya terminada en UTC y presente en los datos ingeridos
- **WHEN** la persona registra su observación
- **THEN** se usa el endpoint existente y se respetan sus rechazos de procedencia/maduración
- **AND** filas sin objetivo observable no se ofrecen como revisables; no se crean observaciones humanas automáticas ni se reanuda una sesión completada después de ajustar el predictor.

Implementado en `frontend/src/features/demo/lock.ts` (`computeDemoWriteGate`/`demoGateForSensor`), aplicado en `ResumenView` (Generar pronóstico), `ForecastPage` (Confirmar/Corregir resultado) y `RecalibrationPanel` (Aplicar observaciones), solo cuando el sensor activo coincide con el de la sesión. `isRowReviewable` exige fecha objetivo dentro del período ingerido por la demo (`last_ingested_date`) y ya terminada en UTC real; la autoridad de aceptar/rechazar sigue siendo `confirmAlert`/`rejectAlert` sin cambios. Verificado en navegador real contra el contrato real (entrega 4, 2026-09-18): con la sesión `demo-be97e84561` en curso, "Generar pronóstico" quedó deshabilitado con la explicación "Esta sesión de demostración está en curso..."; al completarse, de sus cinco filas solo las dos con fecha objetivo dentro del período ingerido ofrecieron Confirmar/Corregir, y se registró manualmente una observación real sobre la fila `2026-01-01` (`estado_validacion` pasó a `confirmada` vía `POST /feedback/{sensor_id}/{fecha}/confirm`, verificado por `GET` directo al backend).

### Requirement: Laboratorio de sensores de prueba (tercer modo de la UI de defensa)

La UI DEBE ofrecer un modo "Laboratorio / Sensores de prueba" que reproduzca, sobre un `sensor_id` propio y aislado, cuatro escenarios encadenados con semilla fija (lecturas normales, anomalía de sensado, interrupción de lecturas, recuperación) usando exclusivamente los endpoints reales de ingesta, calidad, pronóstico y revisión humana ya existentes — nunca un backend, un detector ni un pronóstico paralelos o fabricados.

#### Scenario: Recorrer los cuatro escenarios

- **GIVEN** el laboratorio recién abierto
- **WHEN** la persona inicia el Escenario A y avanza B → C → D
- **THEN** cada paso llama a `POST /sensors/{sensor_id}/readings`, confirma por `GET /quality/{sensor_id}` y, cuando corresponde, vuelve a pedir `POST /forecast/{sensor_id}/run`
- **AND** el rótulo permanente "SIMULACIÓN · Datos sintéticos · Sin sensor físico conectado" está siempre visible, y el reloj simulado se distingue explícitamente de la hora real.

#### Scenario: Anomalía marcada por el mecanismo real

- **GIVEN** el Escenario A completado
- **WHEN** se inyecta el Escenario B (una lectura con `temperature` fuera de `AGRONOMIC_RANGES`)
- **THEN** la UI muestra la fecha y el motivo tal como los devuelve `GET /quality/{sensor_id}` (`out_of_range.temperature`), nunca un resultado fabricado en el cliente.

#### Scenario: Interrupción sin sustituir "sin alerta"

- **GIVEN** el Escenario B completado
- **WHEN** se avanza el Escenario C sin ingerir lecturas nuevas
- **THEN** el reloj simulado avanza pero la última lectura confirmada por el backend no cambia; no se vuelve a pedir un pronóstico sin datos nuevos que lo sustenten
- **AND** se muestra la última lectura, el último pronóstico obtenido (fechado, nunca presentado como vigente) y la orientación "Verificar sensor y cultivo", nunca "sin alerta" como sustituto de datos faltantes.

#### Scenario: Recuperación y disponibilidad real de revisión

- **GIVEN** el Escenario C completado
- **WHEN** se reanuda el Escenario D
- **THEN** las lecturas del período interrumpido se ingieren y se confirman por `GET /quality/{sensor_id}`, y se vuelve a pedir un pronóstico
- **AND** la revisión humana sobre cada resultado usa `confirmAlert`/`rejectAlert` sin cambios: si la fecha objetivo del pronóstico más reciente todavía no venció, el backend real la rechaza (`409`) y la UI muestra ese motivo real, nunca la fabrica ni la oculta.

#### Scenario: Ejecución invalidada, error sin reintento y recuperación con salida

- **GIVEN** un paso del laboratorio con una solicitud pendiente
- **WHEN** la pantalla se desmonta o se inicia una sesión nueva
- **THEN** la ejecución anterior no inicia solicitudes de ingesta, consulta ni pronóstico nuevas ni modifica el estado vigente (una solicitud ya enviada puede terminar y sus datos se conservan)
- **AND** un error de paso deja la sesión en `error` con A–D deshabilitados; la única salida es una sesión nueva (otro `sensor_id`, semilla y calendario reiniciados), sin sobrescribir ni reintentar lecturas ya aceptadas
- **AND** el escenario D sin `period_end` termina en ese mismo estado de error con el mensaje controlado.

#### Scenario: Revisión bloqueada mientras el día objetivo no terminó (UTC)

- **GIVEN** una fila cuyo `fecha_objetivo` es igual o posterior al día UTC actual, o ausente/inválida
- **THEN** Confirmar y Corregir están deshabilitados con el motivo correspondiente, se compone con el bloqueo de la demo acelerada sin relajarlo, se reevalúa al volver a la pestaña y al cambiar el día UTC, y se comprueba de nuevo antes de guardar; el backend sigue siendo la autoridad (409).

#### Scenario: Respuestas fuera de orden de la demo acelerada

- **THEN** para una misma `session_id` nunca se aplica una revisión inferior a la vigente (GET y comandos por igual) y se descartan respuestas de sesiones/generaciones anteriores o posteriores al desmontaje.

Implementado en `frontend/src/features/lab/{SensorLabPage.tsx,useSensorLabScenarios.ts,readingGenerator.ts,labSensor.ts,sensorLabApi.ts}`, ruta `#laboratorio-sensores` (`useHashRoute.ts`, `App.tsx`). Reutiliza sin cambios `useForecastWorkspace` (invalidación de respuestas tardías, un único `activeMutation` en curso), `ForecastPage` (revisión humana) y `QualityPanel` (calidad/anomalías) — este *change* no agrega HITL ni detección de calidad propios, solo los orquesta desde un `sensor_id` de laboratorio. `sensor_id` usa el prefijo exclusivo `lab-` (`labSensor.ts`, `.gitignore`: `data/sensor__lab-*.parquet`, `data/feedback__lab-*.parquet`), nunca reutilizado por Pergamino (`pergamino-ensemble-demo`), Melchor Romero (`melchor-romero-demo`), la demo acelerada (`demo-*`) ni `melchor_romero_2024_consolidado`; "Reiniciar" genera un `sensor_id` nuevo en vez de borrar el anterior. El generador de lecturas sintéticas (`readingGenerator.ts`, PRNG `mulberry32` con semilla fija) es una implementación propia en TypeScript (el generador Python `data_ingestion.mock_sensor` no es importable desde el frontend) que espeja los mismos límites físicos de `data_quality.rules.AGRONOMIC_RANGES` documentados ahí.

**No existe pronóstico ni HITL propios de este modo**: el pronóstico usa el mismo pipeline operativo del resto de `alerting-ui` (`execute_configured_pipeline`, contrato Random Forest explícito, ver "Modelo operativo vs. selección automática experimental" más abajo) sobre el dataset aislado del sensor de laboratorio; una revisión humana registrada acá nunca dispara entrenamiento ni recalibración, y no acredita desempeño predictivo sobre sensores físicos reales.

Verificado con una verificación HTTP real de punta a punta contra el backend (`backend/app/main.py` servido localmente, sin mocks), dos sesiones de sensor aisladas (`lab-httpcheck01`, `lab-httpcheck02`): backfill de 120 lecturas normales confirmado por `GET /quality` (`total_rows=120`, sin `out_of_range`); Escenario B marcó realmente `out_of_range.temperature` en la fecha inyectada; Escenario C mostró el reloj simulado avanzando sin que cambiara `period_end`/`total_rows` reales; Escenario D recuperó `period_end`/`total_rows` tras reingerir el período interrumpido y volvió a emitir pronóstico; la revisión humana se demostró en ambos sentidos reales — `POST /feedback/{sensor_id}/{fecha}/confirm` devolvió `200 confirmada` sobre un objetivo ya vencido y `409` sobre uno todavía no vencido, con el mensaje real del backend en ambos casos; aislamiento cruzado confirmado (`GET /quality/lab-httpcheck01` no cambió mientras se operaba `lab-httpcheck02`, y `pergamino-ensemble-demo`/`melchor-romero-demo` devolvieron `404`, nunca tocados). Verificación automatizada: `frontend/src/features/lab/{readingGenerator.test.ts,SensorLabPage.test.tsx}` (10 tests), suite completa de frontend 209/209, `npm run build` y `npm run lint` limpios. Verificación visual en navegador (escritorio y 390px): pendiente en esta entrega (ver limitación más abajo).

### Requirement: Elegibilidad de la revisión en el recorrido histórico exige observación objetivo verificada

En el recorrido histórico (`/api/v2/sensors/{sensor_id}/historical/...`), confirmar o rechazar un pronóstico DEBE requerir, además del reloj simulado, una observación de la variable objetivo (humedad del suelo) en su propia fecha, con procedencia verificada y ya revelada por el reloj. Un valor imputado, ausente o de procedencia no verificada NO habilita la revisión, aunque su fecha ya haya pasado. La regla es exclusiva del recorrido histórico: no modifica el feedback operativo ni el del laboratorio sintético. "Observación en la fuente" conserva la distinción de procedencia de cada sitio (no implica un sensor físico).

#### Scenario: Una misma condición para consultar y escribir

- **GIVEN** un pronóstico histórico cuyo objetivo ya fue revelado por el reloj
- **WHEN** se consulta `GET .../historical/{fecha}/forecasts` o se envía `POST .../reviews`
- **THEN** ambos aplican el mismo evaluador (`_historical_review_block`): objetivo no revelado → `review_not_open`; sin valor de la variable objetivo en esa fecha exacta → `target_observation_missing`; valor imputado → `target_observation_imputed`; procedencia no verificada → `target_observation_unverified` (reutilizando `data_ingestion.history.query_readings`, incluida la exigencia de marcadores para Melchor Romero)
- **AND** el GET devuelve `reviewable=false` con ese `blocked_reason`, y el POST devuelve HTTP 409 con el mismo código sin persistir ninguna revisión, incluso si se omite la interfaz
- **AND** una variable auxiliar imputada no bloquea; no se busca una fecha vecina ni se imputa; una falla de almacenamiento sigue siendo un error técnico (503), nunca "observación ausente"; una revisión ya registrada se conserva sin modificarse.

#### Scenario: Interfaz

- **WHEN** `reviewable=false` por observación objetivo
- **THEN** la tarjeta muestra el motivo explícito (imputado / ausente / no verificado), no ofrece confirmar ni rechazar, y un formulario ya abierto deshabilita guardar y reintentar conservando el texto y permitiendo cancelar
- **AND** el envío vuelve a comprobar la elegibilidad y un 409 real del backend se muestra tal cual.

## Limitaciones conocidas

- **Verificación pendiente (laboratorio de sensores de prueba, 2026-09-28):** la verificación visual en navegador (escritorio y 390px) del tercer modo no se realizó en esta entrega; quedó completada la verificación HTTP real de punta a punta (los cuatro escenarios, aislamiento cruzado, revisión humana permitida/no permitida) y la automatizada (`vitest`, build, lint). Los 120 `POST /sensors/{sensor_id}/readings` secuenciales del backfill del Escenario A (mismo tamaño ya validado por `demo-simulation`, `history_days=120`) hacen que ese primer paso tome varios segundos reales por sesión — aceptable para una demostración de laboratorio puntual, pero no pensado para prepararse repetidamente de forma automática.
- **Verificación pendiente (HU6, demostración acelerada, entrega 4, 2026-09-18):** el viewport móvil real y la navegación exclusivamente por teclado sobre la vista de demostración no pudieron confirmarse con la misma herramienta de automatización que verificó el resto de esta entrega — `resize_window` no tuvo efecto sobre la resolución real del navegador (fija en 1280×800 en este entorno), la misma limitación ya documentada más abajo para `improve-alerting-ui-decision-workflow`. Se hizo una aproximación (contenedor angosto de 390px inyectado por CSS, sin disparar los `@media` reales) que no mostró desbordes ni recortes, y se confirmó por inspección del DOM que el orden de tabulación llega a los controles Iniciar/Pausar/Continuar (botones nativos sin `tabIndex` ni manejadores de teclado propios) y que `Enter` los activa igual que un clic. La verificación en un dispositivo o navegador real con redimensionado genuino queda pendiente.
- ~~Un único modelo fijo (Random Forest, configuración base) genera el veredicto; el motor de selección/ensamble entre varios modelos queda para una iteración futura (`openspec/changes/add-alerting-ui/proposal.md`, "Fuera de alcance").~~ **Actualización (2026-08-22):** por un tiempo resuelto mediante selección automática entre candidatos (`openspec/specs/predictive-modeling/spec.md`, requirement "Selección automática del mejor modelo candidato"). **Actualización posterior (ver "Modelo operativo vs. selección automática experimental" más abajo):** el backend operativo volvió a usar un contrato Random Forest explícito, por una decisión deliberada distinta del motivo original de esta limitación — no es un regreso a la limitación original, sino una decisión operativa para evitar que la UI falle ante folds de validación degenerados.
- ~~No hay ingesta de datos de sensores en vivo; el dataset es el mismo consolidado histórico de HU2, configurable por nombre pero no por fuente en tiempo real.~~ **Actualización:** resuelto mediante ingesta de sensores mock/en vivo (`POST /sensors/{sensor_id}/readings`, ADR-0007) y ruteo/aislamiento multi-sensor (ADR-0008) — ver la sección "Multi-sensor" más abajo. El dataset consumido por esta capacidad para un `sensor_id` dado puede ser el generado por ese flujo de ingesta mock, separado por construcción del dataset histórico formal de HU7/HU8 (`melchor_romero_2024_consolidado`, sin prefijo `sensor__`). La ingesta de sensores sigue siendo una fuente de datos y contexto experimental, no la contribución central del proyecto (que permanece siendo la arquitectura de IA).
- ~~El disparo de recalibración supervisada (HU5) no está conectado a la UI todavía.~~ **Actualización (2026-08-19):** resuelto — ver el requirement "Disparo manual de recalibración desde la interfaz" más arriba.
- El registro de retroalimentación asume un único pronóstico por fecha calendario — no distingue entre pronósticos recalculados en momentos distintos para la misma fecha objetivo. Esto no se expone con el dataset histórico estático actual, pero deberá resolverse antes de soportar datos de sensores en vivo con recálculo continuo a mayor frecuencia.
- ~~El backend entrena el modelo en cada corrida (sin cachear) cuando no hay un modelo recalibrado registrado; aceptable con el tamaño de dataset actual (~357 filas), a revisar si el dataset crece significativamente~~ **Actualización (2026-08-23):** resuelto — ver el requirement "Reutilización del modelo cacheado por sensor mientras el dataset no cambie" más arriba (`openspec/changes/add-selection-caching/`).
- El campo `model_version` persistido en el registro de retroalimentación (`src/human_feedback/schema.py`) conserva ese nombre por compatibilidad histórica, pero en el flujo operativo vigente contiene `FittedPredictor.model_id` (un identificador lógico e inmutable del predictor), no un número de versión del Model Registry de MLflow — ver `openspec/specs/human-feedback/spec.md` para el detalle completo de esta distinción.

## Multi-sensor

Todas las rutas de esta capacidad exigen un `sensor_id` explícito (`POST /forecast/{sensor_id}/run`, `GET /feedback/{sensor_id}`, `POST /feedback/{sensor_id}/{fecha}/confirm`, `POST /feedback/{sensor_id}/{fecha}/reject`, `POST /recalibrate/{sensor_id}`, `POST /sensors/{sensor_id}/readings`, `GET /quality/{sensor_id}`, `GET /models/{sensor_id}/active`, `GET /lineage/{sensor_id}`; ver ADR-0008). Por cada sensor: el dataset consolidado, el registro de retroalimentación, el modelo recalibrado en el Model Registry de MLflow y el caché de modelo (`_selection_cache`) están aislados entre sí mediante la convención de nombres de `data_ingestion.sensor_naming`, sin estado global compartido entre sensores.

El frontend consume estas rutas con `sensor_id` desde `frontend/src/App.tsx` (estado del sensor compartido entre secciones) y sus features `forecast/`, `quality/` y `lineage/`, tras el breaking change deliberado introducido por PR #163 (que exigió `sensor_id` en todos los endpoints) y su resolución posterior, que incorporó el selector/input de sensor en la interfaz. No queda ninguna llamada del frontend a una ruta sin `sensor_id`.

**Actualización (Entrega 1 de `openspec/changes/improve-alerting-ui-decision-workflow/`) — sensor borrador/activo y aislamiento de solicitudes:** `App.tsx` separa el identificador en edición (`draftSensorId`) del sensor activo (`activeSensorId`); solo "Aplicar" (o Enter) con un identificador válido (`^[a-zA-Z0-9_-]{1,64}$`) cambia el contexto propagado a `QualityPanel`, `ForecastPage` y `LineageChain` — ver requirement "Contexto global de sensor y aislamiento de solicitudes" más abajo.

## Modelo operativo vs. selección automática experimental

El backend operativo (`backend/app/pipeline.py::execute_configured_pipeline`) usa actualmente un contrato Random Forest explícito (`build_candidate_models(...)["random_forest"]`) cuando no existe un predictor recalibrado o cacheado reutilizable para el sensor, en vez de invocar la selección automática entre candidatos. Esta es una decisión operativa deliberada, documentada inline en el código: la selección automática (`select_best_candidate`, `openspec/specs/predictive-modeling/spec.md`) falla explícitamente cuando algún fold de validación temporal carece de ambas clases, y la UI necesita poder producir un pronóstico incluso en esa situación.

La selección automática entre candidatos permanece disponible y vigente en el núcleo experimental (`predictive-modeling`, `architecture-integration`) y es la que efectivamente usa el protocolo experimental formal (`controlled_daily_v3`) cuando no se fija un modelo explícito para una comparación controlada. Esta divergencia entre el backend operativo y el núcleo experimental es intencional y no debe interpretarse como que `alerting-ui` usa selección automática de modelos: no la usa actualmente.
