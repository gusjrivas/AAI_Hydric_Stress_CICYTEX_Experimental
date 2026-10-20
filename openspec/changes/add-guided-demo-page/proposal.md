# Proposal: recorrido guiado `#demo-guiada` para grabar la demostración

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: despliegue/evaluación.
- Impacto científico: ninguno. No cambia modelos, umbrales, datos, protocolo v3/v4, resultados históricos ni holdouts; no calcula nada nuevo ni abre A/B/C.
- Impacto sobre hipótesis, alcance o arquitectura: ninguno. Es una vista de frontend sobre clientes ya existentes; sin endpoints nuevos, sin cambios de backend y sin regenerar el cliente OpenAPI. Apoyo a la decisión: no automatiza ni recomienda riego.
- Problema: para grabar un video de 3 a 5 minutos hace falta una pantalla simple y secuencial. Las pantallas actuales (Seguimiento histórico por sitio, Laboratorio) muestran mucho detalle técnico a la vez y exigen elegir fechas, sondas y escenarios.

## Cambio
1. Nueva ruta hash `#demo-guiada` (distinta de `#demo`, la demostración acelerada ya existente), enlazada desde la navegación de Herramientas técnicas como «Recorrido guiado». App la resuelve con un hook propio y una rama aparte; no modifica `useHashRoute`, `viewMode` ni las pantallas existentes.
2. Stepper de cuatro sitios en este orden: CICYTEX, Pergamino, Melchor Romero y Sensores simulados (laboratorio), con «Paso N de 4» y barra de progreso. Cada paso se monta al llegar y se descarta al salir (volver lo reinicia; no se reutiliza estado entre sitios).
3. Por sitio, sólo: (a) semáforo «Sin alerta» / «Alerta prevista» y «N de 3 modelos coinciden con este resultado»; (b) «Avanzar un día», que revela el valor observado y si hubo o no humedad baja (laboratorio: escenario A normal y B anomalía de medición, rotulado SIMULACIÓN); (c) una línea «De dónde sale» y un `<details>` «Ver detalle técnico» con hashes/commit sólo si existen, «no disponible» o «no registrado» si no.
4. Reutilización: `features/defense/cicytexApi.ts` (sesión causal), `features/producer/historicalApi.ts` y `EmissionProvenancePanel` (lecturas y procedencia de Pergamino/Melchor Romero) y `useForecastWorkspace` + `useSensorLabScenarios` (laboratorio). No se añaden consumidores de `api/generated/schema`; las listas cerradas de consumidores no cambian.
5. Honestidad: es un recorrido, no una evaluación; no se muestran probabilidades; el laboratorio declara que la comparación entre modelos no está disponible; un valor imputado, no verificado o ausente en el día objetivo no se presenta como observación independiente; ningún resultado se atribuye a otro sitio; Laya no aparece.
6. Verificación en navegador: `scripts/ui/verify-journeys.mjs` suma el sitio `demo-guiada` (23 chequeos) con las fixtures existentes; `EXPECTED_MIN_CHECKS` y su test pasan a incluirlo.

## No verificado / fuera de alcance
Revisión visual contra un backend real (sólo fixtures grabadas y pruebas de componente); lectores de pantalla y zoom; el laboratorio contra un backend real con el predictor operativo; el guion o la duración del video. No se añaden revisiones humanas (feedback) en este recorrido.
