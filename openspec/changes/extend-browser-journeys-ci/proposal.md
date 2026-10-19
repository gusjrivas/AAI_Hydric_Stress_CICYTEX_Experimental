# Proposal: recorridos de navegador multi-sitio integrados en CI (F7, F8)

- HU: HU6 (UI). Capacidad: `alerting-ui`. Fase CRISP-DM: despliegue/evaluación.
- Impacto científico: ninguno. No cambia modelos, umbrales, datos, protocolo ni resultados históricos; no abre holdouts ni ejecuta A/B/C.
- Problema: la verificación en navegador real sólo cubría CICYTEX, era manual (ruta de Chrome de Windows, backend real) y J6 sólo observaba.

## Cambio
1. `scripts/ui/verify-journeys.mjs` cubre Melchor Romero, Pergamino, CICYTEX, Laboratorio y la ficha de Laya (`#arquitectura`): decisión visible,
   trazabilidad, acciones, avance sin revelar el futuro, backend desconectado y recuperación, Tab sin trampa con foco visible, feedback sin
   preselección y recuperación de sesión (restaurada o explicada ante 404).
2. `scripts/ui/fixture-server.mjs` (sin dependencias) sirve el build y respuestas JSON grabadas de backends reales (`frontend/e2e/fixtures`),
   con modos normal, desconectado y sesión-404 y estado de sesión CICYTEX en memoria.
3. Helpers puros con pruebas `node --test` (Chrome portable, manejador de fixtures, análisis de Tab, resultados).
4. Job `browser-journeys` en `ci.yml` (job nuevo; los existentes no se tocan), con artefacto de resultados.

## Decisiones y costo
- Sin dependencias nuevas (ni Playwright ni axe): Node 22 + Chrome del runner por CDP. Costo: sin auditoría de accesibilidad automatizada.
- Las fixtures fijan un contrato grabado; no prueban el backend. Se regrabaron con `record_fixtures.py` (README del directorio).
- No confundir con pruebas de componente: aquí el navegador carga el bundle de producción y habla HTTP con el servidor de fixtures.
