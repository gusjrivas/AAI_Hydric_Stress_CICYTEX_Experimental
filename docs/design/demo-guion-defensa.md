# Guion de demo de defensa (3-5 min) y ensayo técnico cronometrado

HU6 (`architecture-integration`) y UI (`alerting-ui`). Fase CRISP-DM: despliegue/comunicación. Sin impacto
sobre configuración experimental, hipótesis, alcance ni arquitectura. La UI es apoyo a la decisión; no automatiza
riego. Este documento **detalla** la sección 1 de `docs/design/f8-paquete-defensa.md` (la tabla breve de allí
sigue siendo el resumen; arranque general en `docs/design/defense-demo-startup-guide.md`, verificación de
navegador en `docs/design/f7-verificacion-navegador.md`). No reabre holdouts ni usa datos privados.

Convención: **hecho** = comprobado en el ensayo técnico de la sección 6; «no verificado» = no comprobado.

## 1. Datos identificados (todos existen en `frontend/e2e/fixtures/`, grabados de backends reales)

| Sitio | Ruta | Datos de la demo |
| --- | --- | --- |
| CICYTEX | `#defensa-cicytex` | Sonda `CP1_S1`, horizonte +1 día, emisión `2023-07-06` (primera legítima), objetivo `2023-07-07`. Decisión: **sin alerta de humedad baja**, ensamble 0.005, 0/3 modelos alertan; P20 de entrenamiento 0.210 (0.2104). Al avanzar un día: observado 0.2322 m³/m³ (2023-07-07), por encima del P20, resultado VN en los cinco métodos. Trazabilidad: dataset SHA-256 `06d662bc…6482`, commit `e74d8b2c…e481`, semilla 42, política «equal-weight arithmetic mean; threshold 0.5». |
| Pergamino | `#defensa-pergamino` | Emisión `2023-06-13` (hay cinco, 13-17 jun 2023), ERA5-Land / NASA POWER (reanálisis). Veredicto +1: **sin alerta**, los 3 modelos coinciden. Avanzar un día lleva el reloj al 14 jun. |
| Melchor Romero | `#defensa-melchor-romero` | Emisión `2024-10-20` (hay cinco, 20-24 oct 2024), ESA CCI / NASA POWER. +1: sin alerta (3/3 coinciden); +2: sin alerta (1/3 indica alerta); **+3 (23 oct): alerta prevista (2/3 modelos)**. «Sin evaluación agregada equivalente»: no se le atribuyen resultados de Pergamino. |
| Laboratorio | `#laboratorio-sensores` | Sintético: escenario A (120 lecturas normales) y B (anomalía de medición, no alerta de estrés). Opcional. |
| Arquitectura | `#arquitectura` | Tabla de nodos y ficha de Laya («Desactivado por defecto», «sin efecto automático»). |

Límite de los datos de CICYTEX en la demo: la sesión grabada solo cubre CP1_S1 / +1 / 2023-07-06 y tres avances
(2023-07-07 a 2023-07-09), todos VN. **La demo con fixtures no muestra ninguna alerta de CICYTEX ni MCC/F1
(aparecen como «—» con n=1)**; la única alerta visible es la de Melchor Romero (+3). Otras sondas, horizontes y
emisiones del catálogo solo se ejercen contra el backend real (plan A), no verificado en este ensayo.
La UI no muestra probabilidades en Pergamino ni Melchor Romero («Probabilidad no disponible»); no citar porcentajes.

## 2. Arranque exacto

**Plan A (backend real CICYTEX + frontend, no ejecutado en este ensayo)**, desde la raíz del repositorio:

```
# terminal 1: backend con el paquete causal (CICYTEX_REPLAY_DIR por defecto: results/cicytex/causal_replay)
$env:PYTHONPATH="src;backend;."; python -m uvicorn backend.app.main:app --port 8010
# terminal 2: frontend con proxy /api -> 8010 (puerto 5199)
cd frontend; npx vite --config vite.verify.config.mjs
```

Abrir `http://localhost:5199/#arquitectura`. Pergamino, Melchor Romero y laboratorio requieren además los
arranques de `start_defense_demo.ps1` (`-Mode all`, ver guía de arranque).

**Plan B (fixtures, sin backend; es lo que se ensayó)**, desde la raíz (Node >= 22, Chrome para el ensayo):

```
cd frontend; npm ci
$env:VITE_API_BASE_URL=""; npm run build -- --outDir dist/e2e --emptyOutDir
cd ..; $env:PORT="4173"; node scripts/ui/fixture-server.mjs     # dejar corriendo; guardar el PID si se lanza en segundo plano
```

Abrir `http://127.0.0.1:4173/#arquitectura`. Reinicio entre pasadas: `POST http://127.0.0.1:4173/__fixture/reset`
(o recargar y limpiar `sessionStorage`). Detener: cerrar esa terminal o terminar **solo el PID lanzado**
(nunca `taskkill /IM node.exe`).

## 3. Guion paso a paso

Tiempos de habla estimados a 140 palabras/min sobre el texto de «Decir» (conteo de palabras del ensayo); los
clics y la lectura de pantalla se suman. Ruta completa objetivo: 5:00; **ruta corta de 3:00**: pasos 1, 3, 4, 5
y 7 de CICYTEX (sin Pergamino/Melchor Romero).

| # | Acum. | Ruta y acción | Se muestra | Se dice |
| --- | --- | --- | --- | --- |
| 1 | 0:00-0:30 | `#arquitectura`; clic en «Laya» | Mapa/tabla por nodos; nota «no es monitoreo en vivo»; ficha de Laya: «Desactivado por defecto», salida «sin efecto automático». | «Esta es la arquitectura final. Los datos de sensores son una fuente, no la contribución; el núcleo es el modelado. Laya existe como adaptador consultivo pero está desactivada por defecto, y nada en esta pantalla es monitoreo en vivo.» (39 palabras, ~17 s) |
| 2 | 0:30-1:00 | `#defensa-cicytex` | Selectores Sonda `CP1_S1`, Horizonte +1 día, Fecha `2023-07-06`; sin «Día siguiente» ni feedback. Aviso del evento (humedad bajo P20 de entrenamiento; no es estrés fisiológico). | «Este es el recorrido sobre el paquete causal archivado de CICYTEX: tomate de industria, Talavera la Real, 21 sondas. Elijo la sonda CP1_S1, horizonte más uno y la emisión del 6 de julio de 2023, la primera legítima. Los modelos se congelaron validando hasta el 5 de julio. Sin sesión abierta no hay avance de reloj ni feedback.» (58, ~25 s) |
| 3 | 1:00-1:40 | «Abrir emisión congelada» | Tarjetas EMISIÓN 2023-07-06, RELOJ REVELADO 2023-07-06, OBJETIVO 2023-07-07; «SIN ALERTA DE HUMEDAD BAJA — Ensamble 0.005 · acuerdo 0/3 alertan»; «La realidad permanece oculta…». | «Abro la emisión congelada. La arquitectura decide solo con lo observado hasta el 6 de julio: sin alerta de humedad baja, ensamble 0,005, cero de tres modelos alertan. La realidad permanece oculta hasta que el reloj alcance el 7 de julio. Es apoyo a la decisión, no riego automático. El evento es humedad por debajo del P20 de entrenamiento, no estrés fisiológico observado.» (63, ~27 s) |
| 4 | 1:40-2:15 | Desplegar «Identidad del paquete y de los modelos» | Dataset SHA-256 `06d662bc…`, commit `e74d8b2c…` · semilla 42, política del ensamble, particiones (entrenamiento hasta 2023-06-06, calibración 2023-06-20, validación 2023-07-05), corridas MLflow de los tres modelos. **Declarado no disponible:** «Versión del modelo: no disponible (los modelos están congelados por corrida)» y «Linaje de recalibración: no disponible». | «Cada predicción se rastrea al paquete archivado: hash del dataset, commit de ejecución, semilla 42, política del ensamble, particiones y corridas de MLflow de los tres modelos. Lo que no tenemos lo declaramos: versión de modelo y linaje de recalibración figuran como no disponibles, no los inventamos.» (47, ~20 s) |
| 5 | 2:15-2:50 | «Día siguiente» | Reloj 2023-07-06 → 2023-07-07; «Última observación revelada: 0.232 m³/m³ (2023-07-07), por encima del P20 (0.210)»; el gráfico solo dibuja hasta el reloj. | «Avanzo el reloj un día: ahora es el 7 de julio y recién ahora aparece la observación, 0,232 metros cúbicos por metro cúbico, por encima del P20 de 0,210. El gráfico solo dibuja lo revelado hasta el reloj; el futuro no está en la vista.» (45, ~19 s) |
| 6 | 2:50-3:20 | misma pantalla | «Realidad revelada: no hubo humedad baja · resultado VN»; tabla por método (cinco métodos, observado 0.2322, VN); «Comparación acumulada revelada» n=1 con MCC, precisión, recall y F1 en «—». | «Con la realidad revelada comparamos: no hubo humedad baja, resultado verdadero negativo para los cinco métodos. Con una sola observación no hay MCC ni F1; la tabla acumulada lo muestra como guion, y es un recorrido, no una campaña de evaluación.» (41, ~18 s) |
| 7 | 3:20-3:50 | Elegir «Sí, coincide», «Registrar feedback»; luego «Reiniciar» | Sin opción preseleccionada y botón deshabilitado hasta elegir; confirmación «Feedback registrado: confirmada.»; tras «Reiniciar» la confirmación desaparece (el ensayo comprueba solo eso; el borrador limpio entre sesiones lo cubren los tests de componente). | «El feedback humano recién se habilita con la realidad revelada, sin opción preseleccionada. Registro una opción; queda aislado por sesión, no recalibra ni reentrena. Si reinicio la sesión, el borrador vuelve limpio.» (32, ~14 s) |
| 8a | 3:50-4:20 | `#defensa-pergamino` | Emisión 13 jun 2023, «SIN ALERTA DE HUMEDAD BAJA», «Los 3 modelos coinciden»; trazabilidad con versión/identidad SHA-256 del ensamble y bloque «No disponible en este recorrido»: SHA-256 del dataset, commit, semilla, corridas MLflow, particiones, linaje. | «Pergamino comparte un recorrido histórico con el payload de producer v2, emisión del 13 de junio de 2023, sin alerta por unanimidad. Muestra versión y SHA-256 del ensamble, pero SHA-256 de dataset, commit, semilla y MLflow figuran no disponibles, porque el backend no los expone.» (45, ~19 s) |
| 8b | 4:20-4:50 | `#defensa-melchor-romero` | Emisión 20 oct 2024; «1 de 3 horizontes disponibles con alerta prevista»; +3 (23 oct): «Alerta prevista» (2 de 3 modelos); «Sin evaluación agregada equivalente». | «Melchor Romero, emisión del 20 de octubre de 2024: sin alerta a un día y alerta prevista a tres días, con dos de tres modelos. No se le atribuyen resultados de Pergamino, y la trazabilidad no disponible se declara igual.» |
| 8c | 4:50-5:00 (opcional) | `#laboratorio-sensores` | Insignia «SIMULACIÓN», «Sin sensor físico conectado». | «El laboratorio es sintético: no hay sensor físico y no tiene valor de evidencia científica.» |

Si hay que recortar a 3:00, omitir 2 (decirlo dentro de 3), 6 y 8. Preguntas probables: sección 7 de F8.

Lo que **no** debe afirmarse: que el sistema funciona (es un recorrido, no una campaña), probabilidades en %
(no se muestran), alertas de CICYTEX en esta demo con fixtures, telemetría en vivo, versión de modelo o linaje
de recalibración de CICYTEX, commit/MLflow/dataset de Pergamino, Melchor Romero o laboratorio.

## 4. Alternativas ante fallos

| Fallo | Qué hacer | Evidencia |
| --- | --- | --- |
| Backend caído a mitad de recorrido (plan A) | Mostrar el mensaje `role=alert` (no queda decisión vigente en productores), restablecer el backend y pulsar «Día siguiente» / «Reintentar emisión» / «Reintentar lecturas»; el reloj se conserva. | Ensayo y `verify-journeys.mjs` (C4-C5, M/P11-13) |
| Backend nunca arranca | Pasar al plan B (sección 2) y decir que son respuestas grabadas del backend real, no el backend en vivo. Mismas rutas y mismos datos. | Ensayo de la sección 6 |
| Chrome no arranca (el script de ensayo/CI) | `CHROME_PATH=<ruta a chrome.exe>`; si no hay Chrome, abrir `http://127.0.0.1:4173/` con otro navegador y seguir el guion a mano; capturas de reserva: `docs/design/capturas/f7-cicytex-*.png` (solo CICYTEX, versión previa de la UI). | `scripts/ui/lib/chrome.mjs` |
| Sesión CICYTEX no recuperable al recargar | Aparece «No se pudo recuperar la sesión anterior» con «Iniciar otra emisión»; pulsarlo y repetir el paso 3 (foco queda en «Abrir emisión congelada»). | Ensayo R, C10-C10c |
| Catálogo no carga (plan A) | «Reintentar»; si persiste, plan B. | Test de componente; en navegador no verificado |
| Fixture-server en modo erróneo tras una prueba | `POST /__fixture/mode {"mode":"normal"}` y `POST /__fixture/reset`. | `fixture-server.mjs` |
| Puerto 4173 ocupado | `$env:PORT="4180"` en el servidor y `BASE_URL` acorde. | `fixture-server.mjs` |

## 5. Ensayo técnico: cómo repetirlo

```
$env:BASE_URL="http://127.0.0.1:4173"; $env:OUT_DIR="demo-rehearsal-out"; node scripts/ui/rehearse-demo.mjs
```

`scripts/ui/rehearse-demo.mjs` recorre en Chrome real (CDP) los tramos 1-8c contra el fixture-server, cronometra cada
tramo con `performance.now()` y escribe `rehearsal.json` y capturas. **Mide tiempo de máquina**, no tiempo de
habla; no reemplaza `verify-journeys.mjs` (78 PASS en su última corrida). Comprueba los textos concretos de
la sección 1 (reloj 2023-07-06 → 2023-07-07, SHA `06d662bc`, «no disponible», VN con n=1, feedback sin
preselección, avance en Pergamino y Melchor Romero, laboratorio A).

## 6. Resultados del ensayo técnico (2026-10-19, worktree sobre `584bd94`, Windows 11, Node 24.16, fixture-server + build `dist/e2e`)

| Medición | Resultado |
| --- | --- |
| `npm ci` (frontend) | 36,6 s (144 paquetes) |
| Build `dist/e2e` | 8,0 s (Vite: 362 ms de bundling) |
| `verify-journeys.mjs` completo | **78 PASS, 0 FAIL, 1 INFO**, 29,1 s (melchor-romero 17/0/0, pergamino 17/0/0, cicytex 26/0/0, laboratorio 12/0/0, arquitectura-laya 6/0/1) |
| `rehearse-demo.mjs` (3 corridas válidas consecutivas) | 22 PASS, 0 FAIL cada una; total 16,2 s, 25,7 s y 12,4 s (incluye arranque de Chrome) |

Tiempos de máquina por tramo en ms (corridas 1 / 2 / 3). Son el costo de la UI, no del discurso:

| Tramo | Corrida 1 | Corrida 2 | Corrida 3 |
| --- | --- | --- | --- |
| 1 Arquitectura + ficha de Laya | 297 | 493 | 351 |
| 2 CICYTEX selectores | 293 | 534 | 242 |
| 3 Abrir emisión | 184 | 115 | 173 |
| 4 Trazabilidad | 31 | 37 | 22 |
| 5 Día siguiente | 85 | 148 | 116 |
| 6 Realidad revelada | 12 | 168 | 29 |
| 7 Feedback + reinicio | 237 | 255 | 213 |
| R Recarga + sesión no recuperable (plan de fallos) | 955 | 1391 | 1060 |
| 8a Pergamino (carga + «Día siguiente») | 783 + 82 | 801 + 37 | 479 + 86 |
| 8b Melchor Romero (carga + «Día siguiente») | 793 + 128 | 666 + 74 | 365 + 162 |
| 8c Laboratorio escenario A | 6129 | 2912 | 3637 |

Conclusión: ninguna acción de UI supera 1,5 s salvo el escenario A del laboratorio (2,9-11,9 s según la corrida; la revisión midió 4,5 s y 11,9 s, con 120 lecturas
sintéticas generadas por la UI); el presupuesto de 5:00 lo consume el discurso, no la aplicación. Tiempo de habla
Nota: el ensayo automatizado no comprueba la alerta de Melchor Romero (+3 días, 2 de 3 modelos); esa afirmación se verifica en `verify-journeys.mjs` y en los fixtures, no en `rehearse-demo.mjs`.

estimado del texto de «Decir» de los pasos 1-8a/8b/8c: ~442 palabras ≈ 3:09 a 140 ppm, **sin** medir el habla real ni los
movimientos del ratón, por lo que 5:00 deja ~1:50 de margen para clics y silencios.

**No ejecutado / no verificado:** plan A (backend real, `start_defense_demo.ps1`, otras sondas/horizontes/emisiones de
CICYTEX); el catálogo caído, el 503 por paquete ausente y el backend apagado del laboratorio en navegador;
el tiempo de habla humano real; pasos C y D del laboratorio; revisiones POST de Pergamino y Melchor Romero; ejecución en
otro equipo o proyector. Fixtures no prueban el backend real.

### Hallazgos de demo (no corregidos; no son cambios de código de producto)

1. **La demo con fixtures nunca muestra una alerta de CICYTEX ni métricas discriminantes** (todo VN, MCC/F1 «—» con n<=3). El mensaje
   de «comparación» es débil; mostrarlo como recorrido, no como resultado, o usar otro punto contra el backend real (no verificado).
2. **Intermitencia del ensayo automatizado:** una primera tanda de tres ejecuciones consecutivas de `rehearse-demo.mjs` falló
   por `Timeout tras 30000 ms: Page.navigate` y una sonda aislada devolvió `undefined` al evaluar la página; la
   ejecución inmediata posterior pasó, igual que la de `verify-journeys.mjs`. Causa no determinada (carga del equipo con otros
   procesos Chrome/Node, o arranque en frío); riesgo real si el equipo de la defensa está cargado.
   Al ensayar, reservar margen y no depender de una sola carga.
3. El script de ensayo localiza botones por su texto exacto («Día siguiente», «Reiniciar», «Registrar feedback»); si cambia un rótulo se rompe el ensayo.
4. La «Identidad del paquete y de los modelos» de CICYTEX está plegada: si no se despliega en el paso 4, el tribunal no ve hash ni commit.
5. En Pergamino y Melchor Romero la UI no expone probabilidades; el guion no debe citarlas aunque estén en los JSON.
6. `docs/design/f8-paquete-defensa.md` atribuía al «dueño del proyecto» decisiones y la etiqueta «BLOCKED» sin respaldo en el repositorio; se corrigió (sección 7).

## 7. Validación humana pendiente y estados

- **Ensayo con Gustavo (persona que defiende): validación humana PENDIENTE.** No bloquea tareas técnicas. Debe cronometrar el
  habla real de la ruta completa y de la corta, decidir qué pasos recortar y confirmar el equipo y el proyector. Hasta entonces
  los tiempos de habla de la sección 3 son estimaciones, no mediciones.
- **BLOCKED** se reserva para impedimentos concretos con causa, alcance y condición de desbloqueo. No hay ninguno para esta demo.
  Ejemplo ajustado de lo existente: la evaluación de Laya con corpus humano. Causa: no hay corpus adjudicado de los sitios
  científicos; alcance: solo la evaluación de Laya, no la arquitectura ni la UI; desbloqueo: corpus adjudicado y protocolo humano
  intersitio implementado (ADR-0014).
- **Literal «BLOCKED» de Laya:** el ADR-0014 no lo contiene, pero sí el código: `src/human_feedback/offline_readiness.py` define
  `ReadinessDecision` con `BLOCKED_INSUFFICIENT_EVIDENCE` y `BLOCKED_SCIENTIFIC_METHOD_PENDING` (se asigna el primero si el corpus
  no está adjudicado o faltan sitios; el segundo cuando el protocolo humano intersitio no está implementado). Comprobado por
  lectura del código; no se ejecutó la compuerta ni se verificó qué decisión produce hoy el repositorio. La UI no usa ese literal:
  muestra «Desactivado por defecto».
