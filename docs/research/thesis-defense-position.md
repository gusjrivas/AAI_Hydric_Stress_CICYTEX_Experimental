# Posición para la tesis y la defensa

Síntesis vigente para completar la memoria técnica y preparar la defensa.
Revisada contra el commit `d173215` (rama `docs/actualizacion-memoria-defensa`,
2026-10-20). Este documento no modifica resultados, hipótesis, configuración ni
arquitectura. No declara cerrado científicamente el trabajo.

## Commits de referencia

Cada resultado se asocia a un commit de código y a un commit de evidencia o
documentación. No deben intercambiarse.

| Referencia | Commit | Papel | Fuente |
| --- | --- | --- | --- |
| Commit revisado para esta síntesis | `d173215` | Estado del repositorio sobre el que se verificaron las citas. No produjo ningún resultado | `git log` |
| CICYTEX, evaluación inicial, ejecución declarada | `80853b1` (2026-10-10 17:14) | Commit que el reporte declara como ejecutado. No consta en `results/cicytex/summary.json`. Que la corrida padre de MLflow lo registre no fue verificado | `docs/research/cicytex-external-validation-report.md` |
| CICYTEX, evaluación inicial, documental | `2e165aa` (17:15) | Registra resultados y reporte | `git log` |
| CICYTEX, replay causal, código ejecutado | `e74d8b2` (2026-10-10 22:01) | Valor de `git_commit` en el resumen del replay | `results/cicytex/causal_replay/summary.json` |
| CICYTEX, replay causal, evidencia archivada | `1582812` (22:05) | Archiva CSV, resumen e informe | `git log` |
| Evaluación retrospectiva del ensamble de Pergamino | `1e27ad46c1533dffd5b087c824f6e4cf710cbc17` | SHA ejecutable declarado | `docs/research/ensemble-retrospective-evaluation-results.md` |

Los artefactos de CICYTEX no registran si el árbol de trabajo estaba modificado
al ejecutar. `results/cicytex/dependencies.txt` muestra una instalación editable
que apunta a un worktree de agente, sin control de versiones. Ambos hechos son
limitaciones de trazabilidad.

## Tesis central defendible

El trabajo muestra que es posible construir e integrar, con trazabilidad
temporal y reproducibilidad, un sistema de apoyo a la decisión para anticipar un
proxy estadístico de baja humedad de suelo a uno, dos y tres días (la evidencia v3 y de las campañas v4 es a +3 días,
y los horizontes +1 y +2 provienen del ensamble demostrativo y de CICYTEX). La
contribución principal es la arquitectura de IA, su integración y una evaluación
crítica que conserva tanto los resultados favorables como los negativos y las
desviaciones metodológicas. El sistema apoya decisiones. No automatiza el riego.

## Contribuciones

Las contribuciones se apoyan en cinco elementos y no presuponen superioridad de
ningún modelo.

1. **Arquitectura.** Pipeline modular de ingestión, calidad, modelado, alertas,
   feedback e interfaz, con varios sitios representados en la misma arquitectura.
2. **Formulación predictiva.** Anticipar la condición «humedad futura menor que
   el percentil 20 del entrenamiento» como problema de clasificación binaria con
   baseline de persistencia.
3. **Control temporal.** Particiones cronológicas, umbral y calibración ajustados
   solo con datos anteriores, fechas objetivo y de emisión distinguidas.
4. **Trazabilidad.** Hashes de datos, commit, semilla y política del ensamble en
   los resúmenes archivados de CICYTEX y expuestos por su API de procedencia. En
   Pergamino y Melchor Romero el commit figura «no registrado» en las emisiones
   previas a #64.
5. **Evaluación crítica.** Resultados negativos, límites de soporte y
   desviaciones de gobernanza documentados en lugar de omitidos.

Elementos complementarios: comparación temporal de cuatro familias en Pergamino
con regla de simplicidad predeclarada cuando no apareció un ganador estable,
análisis de episodios, calibración y falsos avisos, y el complemento H en dos
pistas (simulada y humana controlada). Ninguna pista acredita beneficio humano.

## Matriz de evidencias

Siete filas con fuente, propósito, resultados disponibles, afirmaciones
admisibles y limitaciones. Las filas no se agregan ni se promedian. Cada una
responde a un diseño, un dato y un objetivo distintos.

### 1. Melchor Romero, evaluación histórica y condiciones

- **Fuente.** `docs/research/reference-v3-formal-table.md`,
  `docs/research/reference-v3-formal-results.json`,
  `docs/research/hu8-resultados-discusion-conclusiones.md` §8. Protocolo v3
  congelado: `docs/research/protocolo-experimental-v3.md`.
- **Propósito.** Comparar ocho configuraciones de `controlled_daily_v3` con cinco
  semillas, dataset `melchor_romero_2024_consolidado`, horizonte t+3.
- **Resultados disponibles.** MCC medio entre −0,0706 (`completa`) y 0,1417
  (`recent_fraction_0.5`). La configuración `base` tiene −0,0135.
- **Afirmaciones admisibles.** Describir el comportamiento comparativo histórico
  dentro de ese diseño. Los aportes de sintéticos y anomalías fueron mixtos.
- **Limitaciones.** No es evidencia v4. No se extrapola a Pergamino ni a
  CICYTEX. Debe declararse la imputación causal de huecos de humedad. No prueba
  detección de anomalías reales ni robustez general. La demo con emisiones
  2024-10-20 a 2024-10-24 (`docs/seguimiento-tareas.md`, sección Melchor Romero
  2026-09-28) es un recorrido técnico y no tiene evaluación retrospectiva
  agregada propia.

### 2. Pergamino, campaña experimental y estado de gobernanza

- **Fuente.** `docs/research/scientific-closure-synthesis-2026-09-22.md`
  (cabecera y §7.4 gobiernan), `openspec/scientific-closure/current-execution-checkpoint.md`
  (cabecera), `openspec/scientific-closure/traceability.md`.
- **Propósito.** Campaña `controlled_daily_v4` con reanálisis ERA5-Land y NASA
  POWER, etapas A, B, C y complemento H.
- **Resultados disponibles.** A: `SIN_GANADOR_ESTABLE`, regresión logística fijada
  por desempate de simplicidad (MCC fuera de muestra: voto suave 0,708,
  regresión logística 0,698, Random Forest 0,695, HGB 0,686). B:
  `CANDIDATE_VALIDATED` por no inferioridad (MCC 0,7014 frente a 0,6147 de
  persistencia, intervalo de la diferencia [−0,0146, 0,2092] que incluye cero).
  C: 0,6648 frente a 0,5734, intervalo [+0,0227, +0,1784]. H: pista simulada con
  efectos mixtos y pista humana con 20 aceptaciones, 0 correcciones,
  `NO_RECALIBRATION` y detección 0/4.
- **Afirmaciones admisibles.** Los valores se presentan con sus límites. B y C
  son evidencia retrospectiva exploratoria.
- **Limitaciones.** B se ejecutó antes del veredicto independiente de A y C
  antes del de B (M-01/RK-20). `SC-GOV-025`, `GF` y RB-05 terminaron en `FAIL`.
  El holdout 2024–2025 se abrió una vez y no se reabre. Un sitio, un año de
  holdout, objetivo bajo P20 sin estrés fisiológico medido. No se evaluó con
  usuarios finales ni se midieron costos agronómicos. Existe un incumplimiento
  adicional del cierre previo a la ejecución: dos `git push` durante la
  preparación del 2026-09-20 (`current-execution-checkpoint.md`, sección
  histórica).

### 3. Pergamino, ensamble demostrativo y evaluación retrospectiva

Este carril es distinto de la campaña de la fila 2.

- **Fuente.** `docs/design/ensemble-real-execution-report-2026-09-26.md`,
  `docs/research/ensemble-retrospective-evaluation-protocol.md`,
  `docs/research/ensemble-retrospective-evaluation-results.md`,
  `docs/research/tables/ensemble-retrospective-2023/`,
  `src/experiment_runner/pergamino_ensemble_demo_runner.py`.
- **Propósito.** Refit técnico propio de tres familias para +1/+2/+3 (nueve
  modelos y nueve calibradores) y evaluación retrospectiva exploratoria sobre
  2023.
- **Resultados disponibles.** Casos 364/363/362. MCC del promedio 0,8376 /
  0,7566 / 0,6804. Persistencia 0,8255 / 0,7146 / 0,6159. Regresión logística
  0,8287 / 0,7941 / 0,7079. Solo la regresión logística frente a persistencia en
  +2 y +3 tuvo intervalo pareado por encima de cero. El bin superior del
  promedio sobreestima (media 0,958 frente a observado 0,913, n=103, en +1).
- **Afirmaciones admisibles.** Integración técnica (carga, inferencia, linaje).
  Desempeño histórico exploratorio no independiente de estos artefactos.
- **Limitaciones.** No reutiliza artefactos ajustados de v4 y no reejecuta A/B/C.
  Año ya usado antes. Comparaciones múltiples. `display_probability` debe seguir
  deshabilitado. Una segunda corrida involuntaria, iniciada después de cerrar la
  primera, produjo veredicto de auditoría final `FAIL` de gobernanza. T05 y T06
  siguen abiertas y no habrá tercera ejecución. Los artefactos de la demo residen
  fuera del repositorio y no están en un clon limpio
  (`docs/design/defense-demo-startup-guide.md`).
- **Garantía de exclusión.** Los CSV completos se cargan de forma transitoria en
  memoria. Los años 2024–2025 se descartan antes de agregar, calcular el umbral,
  construir variables o objetivos (`pergamino_ensemble_demo_runner.py:40-50`,
  `build_daily_frame` en `:288`). Esto es una garantía del runner y no equivale a
  no reabrir el holdout custodiado.

### 4. CICYTEX, evaluación inicial con selección de familia

- **Fuente.** `docs/research/cicytex-external-validation-report.md`,
  `docs/research/cicytex-dataset-manifest.json`, `results/cicytex/summary.json`,
  `src/experiment_runner/cicytex/experiment.py:131-149`,
  `src/experiment_runner/cicytex/training_protocol.py:91-101`. MLflow:
  experimento `cicytex-external-validation`, corrida padre
  `d70d1468c70c4c269bc4888ab83bc8aa`.
- **Propósito.** Evaluar si el pipeline de clasificación del proxy opera sobre
  mediciones de sondas de una fuente externa a Pergamino, entrenando con datos
  CICYTEX.
- **Datos.** 2.205 observaciones diarias de 21 sondas Teros 10 a 20 cm entre el
  2023-04-12 y el 2023-07-25 (105 días por sonda) en Talavera la Real (Badajoz),
  tomate de industria, una campaña. DOI 10.5281/zenodo.17583691, licencia
  CC-BY-4.0. Sin nulos de humedad ni duplicados sensor-fecha, con 112 filas-día de
  cobertura intradiaria parcial. Variables: humedad actual, rezagos 1/2/3 y
  medias móviles de 3 y 7 días por sonda. No hay meteorología utilizable en el
  paquete.
- **Diseño.** Objetivo proxy: humedad futura menor que el P20 del entrenamiento
  (+1: 0,21036 / +2: 0,21048 / +3: 0,20947). Partición cronológica por fecha
  objetivo: 50 % entrenamiento, 15 % calibración sigmoide, 15 % validación y 20 %
  evaluación. La familia se elige por MCC en validación con umbral 0,5 entre
  regresión logística, Random Forest y HGB. Luego se evalúa una sola vez.
- **Resultados disponibles.** 420 casos por horizonte (21 sondas por 20 fechas
  objetivo, del 6 al 25 de julio). Familia elegida y MCC: +1 regresión logística
  0,894 (matriz [[227,15],[7,171]]). +2 Random Forest 0,784 ([[213,28],[17,162]]).
  +3 Random Forest 0,738 ([[214,31],[23,152]]). Prevalencia 0,424 / 0,426 /
  0,417. Persistencia figura aquí solo con MAE/RMSE de humedad. No hay MCC de
  persistencia ni ensamble en este análisis.
- **Afirmaciones admisibles.** El pipeline produce una clasificación coherente
  del proxy sobre una fuente medida con sondas, en un sitio y una campaña.
- **Limitaciones.** El objetivo es un proxy estadístico. No hay etiquetas
  fisiológicas independientes. Las 2.205 observaciones no son 2.205 días
  independientes (21 sondas comparten calendario) ni 21 campañas. Los modelos se
  ajustan con datos CICYTEX, de modo que no se demuestra transferencia desde
  Pergamino. La corrida fallida por codificación CP1252 se repitió completa y existió
  además una ejecución completa anterior (autodeclarado en el reporte). Los
  datos crudos no se versionan.

### 5. CICYTEX, replay y evaluación retrospectiva posterior del ensamble

- **Fuente.** `docs/research/cicytex-causal-ensemble-replay.md`,
  `docs/research/cicytex-causal-ensemble-replay-report.md`,
  `results/cicytex/causal_replay/summary.json`,
  `results/cicytex/causal_replay/metrics.csv`,
  `src/experiment_runner/cicytex/causal_ensemble.py`. MLflow: experimento
  `cicytex-causal-ensemble-replay`, corrida padre
  `4a6b15cbf8834ffc9fd750c7a1167cea`.
- **Propósito.** Archivar emisiones causales del ensamble de tres familias sobre
  el período final y compararlas con cada familia y con persistencia.
- **Diseño.** Semilla 42. Calibrador sigmoide (`CalibratedClassifierCV` con
  `FrozenEstimator`) ajustado en la partición de calibración, uno por familia y
  horizonte (nueve en total, ignorados por git). Ensamble: media aritmética de
  los tres scores calibrados con pesos 1/3 y umbral 0,5. La votación mayoritaria
  se informa solo como comparación secundaria. Persistencia clasifica con la
  humedad en T contra el P20 congelado.
- **Por qué 399/378/357 y no 420.** La evaluación inicial toma las filas cuya
  fecha objetivo cae en (fin de validación, fin de evaluación]
  (`training_protocol.py:99`), lo que incluye emisiones anteriores al 6 de julio.
  El replay conserva solo emisiones con `emission_date > validation_end`
  (`causal_ensemble.py:238`), de modo que quedan 20−h días de emisión por 21
  sondas: 19×21=399, 18×21=378 y 17×21=357. Es otro denominador, no una
  discrepancia.
- **Resultados disponibles.** MCC diario:

| Horizonte | Casos | Regresión logística | Ensamble | Persistencia |
| --- | ---: | ---: | ---: | ---: |
| +1 | 399 | 0,904 | 0,888 | 0,898 |
| +2 | 378 | 0,806 | 0,802 | 0,838 |
| +3 | 357 | 0,772 | 0,774 | 0,816 |

  Fuente: `results/cicytex/causal_replay/metrics.csv`. La regresión logística de
  esta tabla se ajusta en el replay y no es la familia elegida en la evaluación
  inicial de la fila 4. Los valores 0,904 y 0,894 no son comparables entre sí.
  El ensamble no supera de forma consistente a las familias individuales y no
  supera a persistencia en ningún horizonte. La mejor opción diaria por MCC es la regresión logística en +1 y
  persistencia en +2 y +3.
- **Episodios (descriptivo, soporte reducido).** Inicios anticipados, ensamble
  frente a persistencia: +1 3/7 frente a 0/7, +2 2/6 frente a 1/6, +3 3/7 frente
  a 2/7. Días de falsa alerta: 13/22/25 frente a 8/14/14. A +1 el ensamble
  anticipó 3 de 7 inicios frente a 0 de 7 de persistencia, con 13 falsos
  positivos frente a 8. Con 6 o 7 episodios por horizonte y dependencia temporal
  no se atribuye significación estadística ni superioridad.
- **Afirmaciones admisibles.** Comportamiento retrospectivo exploratorio del
  ensamble y de las familias sobre un período y una campaña. Trazabilidad de
  hashes, commit y corridas.
- **Limitaciones.** El período ya había sido inspeccionado por la evaluación
  inicial. Es un análisis retrospectivo adicional y no una confirmación ciega.
  Los calibradores sigmoides ajustados no prueban probabilidades adecuadas para
  uso agronómico. CICYTEX no subsana los incumplimientos de gobernanza previos de
  la fila 2 ni de la fila 3. Los resultados no se transfieren a Pergamino ni a
  otros sitios.

### 6. Laboratorio sintético

- **Fuente.** `frontend/src/features/guided-demo/` (paso Laboratorio),
  `docs/design/sensor-lab-defense-guide.md`.
- **Propósito.** Demostrar el flujo extremo a extremo (ingesta, calidad,
  pronóstico) con datos sintéticos generados en el navegador (escenario normal y
  escenario con temperatura imposible).
- **Resultados disponibles.** Comportamiento del flujo y de las reglas de
  calidad. No hay métricas predictivas.
- **Afirmaciones admisibles.** Que la arquitectura procesa lecturas, detecta un
  valor fuera de rango y emite un pronóstico etiquetado como simulación.
- **Limitaciones.** No es evidencia experimental. No sustituye ningún resultado
  de las filas 1 a 5. El commit y el dataset se muestran como no disponibles.

### 7. Laya

- **Fuente.** `docs/adr/0014-arquitectura-multisitio-y-laya-consultiva.md`,
  `backend/app/dependencies.py:208-227`,
  `backend/app/routers/feedback_triage.py`,
  `src/human_feedback/offline_readiness.py:476-489`,
  `openspec/changes/define-laya-human-evaluation-corpus-contract/proposal.md`.
- **Propósito.** Clasificar comentarios de feedback de forma consultiva. Un
  humano decide siempre (`human_review_required=true`).
- **Resultados disponibles.** Ninguna evaluación de utilidad sobre texto real.
  Existen pruebas de humo sintéticas y contratos de cadena de suministro. El
  repositorio no contiene corpus humano versionado.
- **Afirmaciones admisibles.** Existe un componente opcional, apagado por
  defecto, con un contrato definido y una puerta fuera de línea que nunca emite
  `PASS`. La puerta devuelve como máximo `BLOCKED_SCIENTIFIC_METHOD_PENDING`.
- **Limitaciones.** No validada. Desactivada por defecto: sin `LAYA_DECISION_URL`
  ni `LAYA_MODEL_REVISION` se usa `DisabledDecisionPolicyEngine`. El frontend no
  invoca `/api/v2/feedback/triage`. ADR-0014 documenta sobreconfianza y
  desempeño cercano al azar en modo sin ejemplos, y exige corpus etiquetado,
  evaluación fuera de muestra, calibración y umbral por costo antes de habilitar
  sugerencias. No participa en pronóstico, estrés, recalibración, evidencia ni
  riego.

## Qué significa hoy una alerta del ensamble

La decisión vigente **no es una votación mayoritaria**. Para cada horizonte se
calcula el promedio aritmético de las tres probabilidades calibradas y se emite
`combined_alert` cuando `combined_probability >= decision_threshold`. El umbral
debe ser único entre componentes y su valor operativo archivado es 0,5. El
contrato de Pergamino está en `src/predictive_modeling/ensemble_bundle.py:343-358`
(promedio en `:355`, alerta en `:356`, votos en `:357`) y se valida de nuevo en
`backend/app/schemas_v2.py:264-266`. `positive_votes` y `agreement_category` son
metadata descriptiva y no gobiernan la alerta. El ensamble de CICYTEX aplica la
misma regla en `src/experiment_runner/cicytex/causal_ensemble.py:247-250` (promedio) y `:256` (alerta).

Los tests de discrepancia hacen observable la distinción:
`tests/test_ensemble_bundle.py:440` y `:463` (dos votos positivos con alerta
combinada negativa y un voto positivo con alerta combinada positiva), y
`backend/tests/test_producer_v2_ensemble.py:200`, que confirma que el feedback
valida `combined_alert` y no el voto. Adoptar mayoría sería un cambio futuro de
contrato.

La probabilidad del ensamble no está habilitada para presentación al usuario. La
emisión persiste `display_probability=None`, `probability_status="not_qualified"`
y `probability_reason_code="incompatible_assessment"`
(`src/architecture_integration/producer_emission.py:156-158`).
`combined_probability` existe para el contrato técnico y la decisión binaria y no
debe mostrarse como riesgo calibrado.

## Circuitos de feedback

Ninguno de los circuitos de ensamble recalibra ni reentrena. Confirmar o
rechazar una alerta no es recalibrar. No existe aprendizaje continuo autónomo.

| Circuito | Qué hace | Qué no hace | Fuente |
| --- | --- | --- | --- |
| CICYTEX, por sesión: `POST /api/v2/cicytex/replay/sessions/{id}/feedback` | Registra `estado_validacion`, `etiqueta_corregida` 0/1 opcional y observación. Solo cuando el reloj de sesión alcanzó el objetivo (si no, 409). Identidad sensor, emisión y horizonte (duplicado, 409). SQLite propio | El alcance registrado declara que es una demostración que no recalibra ni reentrena. No llama a recalibración | `backend/app/routers/cicytex_replay.py:133-163`, `src/historical_replay/cicytex_feedback.py:12` |
| Pergamino y Melchor, operativo: `POST /api/v2/sensors/{sensor_id}/forecasts/{forecast_id}/reviews` | Registra `confirm` o `reject` con comentario e idempotencia, solo desde la madurez del objetivo. En modo ensamble el `alert` superior coincide con `combined_alert` | No cambia los bundles. `applied` no se alcanza en este repositorio. Una corrección madura del ensamble resulta `incompatible_source_model` por carecer de una única `calibration_version` | `backend/app/routers/producer_v2.py:391` (`create_review`), `src/human_feedback/operational_repository.py:765` (`submit_review`), `:877` (`_training_eligibility`) |
| Pergamino y Melchor, recorrido histórico: `POST .../historical/{as_of_date}/forecasts/{forecast_id}/reviews` | Revisión de prueba técnica bajo reloj simulado, en un store separado | No es opinión real. No escribe en el repositorio operativo ni en los bundles | `backend/app/routers/producer_v2.py:656` (`create_historical_review`), `src/human_feedback/historical_review_store.py`, `backend/tests/test_pergamino_ensemble_historical_reproduction.py:236`, `:422` |
| Legacy HU5: `POST /feedback/{sensor_id}/{fecha}/confirm\|reject` y `POST /recalibrate/{sensor_id}` | Confirma o rechaza con etiqueta corregida. La recalibración refitea un único predictor con correcciones maduras y registra un sucesor con linaje | No recalibra el ensamble de tres familias. Circuito manual | `backend/app/routers/feedback.py:79`, `:105`, `backend/app/routers/recalibration.py:35`, `src/human_feedback/recalibration.py:51-125` |

El complemento H es otra cosa. La pista simulada evaluó correcciones y
recalibración con efectos mixtos. La humana controlada registró veinte
aceptaciones, cero correcciones, `NO_RECALIBRATION` y detección 0/4. Ninguna
acredita beneficio humano ni mejora causada por feedback.

## Procedencia visible en la interfaz

- CICYTEX: `GET /api/v2/cicytex/replay/provenance` expone hash del dataset,
  commit, semilla, proxy, política del ensamble, corrida padre de MLflow, hash de
  predicciones y, por horizonte, umbral, cortes y corridas componente. El paso
  guiado muestra solo el hash del dataset y el commit.
- Pergamino y Melchor Romero: `GET /api/v2/sensors/{sensor_id}/batches/{batch_id}/provenance`.
  `code_identity` nulo se muestra como «no registrado». Que los bundles actuales
  lo registren no fue verificado.
- Laboratorio: sin commit ni hash de dataset, con semilla del escenario.
- El recorrido `#demo-guiada` no muestra Laya ni feedback humano.

## Resultados que sí pueden presentarse

Hechos.

- En Pergamino, A terminó en `SIN_GANADOR_ESTABLE` y el modelo se fijó por
  desempate predeclarado. B observó no inferioridad y C una diferencia favorable
  en MCC, ambos como evidencia retrospectiva exploratoria.
- En CICYTEX, con 420 casos por horizonte, el pipeline alcanzó MCC 0,894, 0,784 y
  0,738 con la familia elegida en validación. En el replay posterior, el ensamble
  alcanzó 0,888, 0,802 y 0,774, sin superar a persistencia en ningún horizonte.
- En el replay CICYTEX a +1 el ensamble anticipó más inicios de episodio que
  persistencia a costa de más falsas alertas.

Interpretación admisible. El ensamble es una opción de integración trazable cuyo
valor frente a persistencia depende del costo relativo de omitir un inicio y de
emitir una falsa alerta. Ese costo no se midió.

## Limitaciones

- Cada evaluación corresponde a un sitio. Que la arquitectura represente varios
  sitios no equivale a una validación predictiva multisitio con protocolo común.
- Los objetivos son proxies estadísticos de baja humedad. No hay etiquetas
  fisiológicas independientes ni validación agronómica.
- B y C de Pergamino no son confirmatorias por la secuencia de gates. El replay
  de CICYTEX es retrospectivo sobre un período ya inspeccionado.
- Las diferencias entre métodos no tienen significación estadística establecida
  en CICYTEX y el número de episodios es pequeño.
- Los calibradores no prueban probabilidades adecuadas para uso agronómico.
- No hubo evaluación con usuarios finales.

## Afirmaciones prohibidas

- Superioridad general de IA, del ensamble o del modelo elegido.
- Confirmación de la hipótesis mediante B, C o el replay de CICYTEX.
- Transferencia de Pergamino a CICYTEX ni de CICYTEX a otros sitios.
- Generalización geográfica ni validación multisitio con protocolo común.
- Operación productiva demostrada.
- Estrés fisiológico medido, validación agronómica, ahorro de agua o riego
  automático.
- Beneficio humano, mejora causada por feedback o aprendizaje continuo autónomo.
- Probabilidades calibradas aptas para decisión agronómica.
- Utilidad o validación de Laya.
- Que los datos de CICYTEX sean 2.205 días independientes o 21 campañas.
- Robustez ante sensores ausentes, detección reservada de corrupciones o error
  continuo de humedad, que no se evaluaron.

## Estructura sugerida de la presentación

1. Problema y alcance: apoyo a la decisión, no automatización del riego.
2. Arquitectura y contribución de IA, con el recorrido guiado `#demo-guiada`
   (CICYTEX, Pergamino, Melchor Romero, Laboratorio) como apoyo visual.
3. Formulación, diseño temporal, baselines y criterios predeclarados.
4. Evidencia por carril, siguiendo la matriz: Melchor Romero, Pergamino (campaña
   y ensamble), CICYTEX (evaluación inicial y replay), sin mezclar métricas.
5. Qué dice el ensamble y qué no: promedio y umbral 0,5, comparación con
   persistencia, episodios frente a falsas alertas.
6. Feedback y componente Laya: qué circuitos existen, cuáles no recalibran y por
   qué Laya permanece desactivada.
7. Limitaciones y no conformidades de gobernanza.
8. Contribuciones vigentes y trabajo futuro.

## Preguntas probables del tribunal

**¿La hipótesis quedó confirmada?** No de manera confirmatoria. En Pergamino A no
encontró ganador estable y la secuencia de auditoría de B y C incumplió el
protocolo predeclarado
(`docs/research/scientific-closure-synthesis-2026-09-22.md`, cabecera). En
CICYTEX el replay se hizo sobre un período ya inspeccionado
(`docs/research/cicytex-causal-ensemble-replay-report.md`).

**¿Entonces el experimento fracasó?** No. Produjo resultados reproducibles,
incluido un resultado negativo de selección, y permitió cuantificar desempeño,
falsos avisos y límites. Lo que no corresponde es elevarlo a confirmación.

**¿Por qué no repetir B y C desde otra rama?** Cambiar de rama no recupera
cegamiento. El holdout ya fue observado
(`openspec/scientific-closure/current-execution-checkpoint.md`, cabecera).
Una confirmación exigiría datos nuevos.

**¿Por qué CICYTEX tiene 420 casos en un análisis y 399, 378 y 357 en otro?**
Son análisis distintos con distinto filtro temporal. La evaluación inicial toma
filas por fecha objetivo (`training_protocol.py:99`) y el replay conserva
emisiones posteriores al fin de validación (`causal_ensemble.py:238`). Las
métricas y los modelos seleccionados de ambos no deben mezclarse. La regresión
logística del replay (MCC 0,904 a +1) no es la de la evaluación inicial (0,894).

**¿Los datos de CICYTEX sirven como validación externa de Pergamino?** No como
transferencia. Los modelos se ajustan con datos CICYTEX. Sirve para mostrar que el
mismo pipeline puede aplicarse a mediciones de sondas de otro sitio y otro
cultivo (`docs/research/cicytex-external-validation-report.md`).

**¿Son 2.205 observaciones independientes?** No. Son 21 sondas por 105 días de
una sola campaña que comparten calendario
(`results/cicytex/summary.json`, `docs/research/cicytex-dataset-manifest.json`).

**¿El ensamble es mejor que persistencia?** No de forma consistente. En MCC diario
persistencia fue mejor a +2 y +3 y el ensamble no la superó en ningún horizonte
(`results/cicytex/causal_replay/metrics.csv`). A +1 anticipó 3 de 7 inicios de
episodio frente a 0 de 7, con 13 falsos positivos frente a 8. Es un resultado
descriptivo de soporte reducido.

**¿La alerta del ensamble sale por mayoría?** No. Sale del promedio aritmético de
tres probabilidades calibradas comparado con 0,5
(`src/predictive_modeling/ensemble_bundle.py:355-356`). Los votos son metadata. La
mayoría se informó solo como comparación secundaria.

**¿Las probabilidades están calibradas?** Se aplicó calibración sigmoide, pero
eso no prueba probabilidades adecuadas para uso agronómico. En Pergamino el bin
superior sobreestima (0,958 frente a 0,913) y `display_probability` permanece
deshabilitado.

**¿Confirmar o rechazar una alerta recalibra el modelo?** No. Cada circuito se
describe en la tabla de feedback. Ninguno recalibra el ensamble. La recalibración
HU5 es un endpoint manual aparte que opera sobre un único predictor.

**¿Qué hace Laya?** Es un componente consultivo opcional que clasifica
comentarios. Está desactivado por defecto, no se validó y su puerta fuera de línea
nunca emite `PASS` (`src/human_feedback/offline_readiness.py:476-489`,
`docs/adr/0014-arquitectura-multisitio-y-laya-consultiva.md`).

**¿El sistema es multisitio?** La arquitectura representa varios sitios
(ADR-0014). Cada evaluación predictiva corresponde a un sitio y no existe
protocolo común entre sitios.

**¿Qué hace que el trabajo sea una tesis de IA?** La formulación predictiva, la
comparación de modelos, el control temporal, el análisis de calibración y de
episodios y la integración del ciclo de feedback. Los sensores son fuentes de
datos, no la contribución central.

## Trabajo futuro (no realizado)

- Confirmación con datos nuevos y protocolo común entre sitios.
- Etiquetas fisiológicas independientes y costos agronómicos para elegir el
  umbral y entre promedio y mayoría.
- Evaluación con usuarios finales.
- Corpus humano etiquetado y evaluación fuera de muestra antes de considerar
  habilitar Laya.

## Pendientes de verificación

- Que la corrida padre de MLflow de la evaluación inicial registre `80853b1` y que
  las corridas del replay existan en un servidor vivo.
- Estado del árbol de trabajo al ejecutar ambos análisis.
- Funcionamiento extremo a extremo del stack `compose.cicytex.yml` y de
  `#demo-guiada` contra un backend real.
- Si los bundles actuales de Pergamino y Melchor Romero registran `code_identity`.
- Estado efectivo del servicio de Laya fuera del código.
