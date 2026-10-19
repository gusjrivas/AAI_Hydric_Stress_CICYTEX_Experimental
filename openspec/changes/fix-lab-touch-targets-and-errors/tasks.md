# Tasks

- [x] (a) Objetivos táctiles >=44 px a <=600 px. Test: `frontend/src/features/lab/SensorLabPage.touchTargets.test.ts`.
  - RED: 4 fallos (`expected null not to be null`; `.toMatch() expects to receive a string, but got undefined`) por no existir el bloque `@media (max-width: 600px)`.
  - GREEN: bloque agregado en `SensorLabPage.css`; 4/4 pasan.
- [x] (b) Traducción de «Failed to fetch». Test: `frontend/src/features/shared/errorMessage.test.ts`.
  - RED: `Failed to resolve import "./errorMessage"` (el helper no existía).
  - GREEN: `userFacingErrorMessage` implementado y aplicado en `useSensorLabScenarios`, `QualityPanel`, `useForecastWorkspace`; tests pasan.
- [x] (c) Backend apagado en el laboratorio. Test: `frontend/src/features/lab/SensorLabPage.offline.test.tsx`.
  - RED: `Unable to find an element with the text: /No se pudo conectar con el servidor/` (se mostraba «Failed to fetch»).
  - GREEN: 1/1 pasa (alerta en español, «Iniciar una sesión nueva» habilitado, paso A reintentable).
- [x] Bloque 7: test de regresión de Laya en `frontend/src/features/architecture-flow/architectureCatalog.test.ts` (pasa sin cambios de texto: la UI ya era correcta).
- [x] Verificación: `npx vitest run` de shared, lab, quality, forecast, architecture-flow y App.resilience; `npm run lint` (sólo warnings previos); `npm run build` OK.
- [ ] Revisión independiente y CI verde sobre el HEAD exacto (completar tras el merge).
