# Tasks

- [x] RED/GREEN helpers: `chrome.test.mjs` (módulo ausente, 1 suite fallida), `fixture-handler.test.mjs` (módulo ausente; luego pronóstico/feedback/modelo del laboratorio, 1 fallo), `tab-audit.test.mjs` (módulo ausente). `results.test.mjs` se escribió junto con su módulo (sin RED observado). 23 pruebas verdes.
- [x] Fixtures grabadas de backends reales (CICYTEX, producer_v2 Pergamino/Melchor, laboratorio) y README con el procedimiento.
- [x] Script multi-sitio: 78 PASS, 0 FAIL, 1 INFO; dos corridas consecutivas con JSON idénticos (CI=true, build limpio con `VITE_API_BASE_URL=`).
- [x] Mutaciones (build del frontend en copia temporal): ventana de objetivos futuros siempre visible (M9, P9 fallan); feedback preseleccionado (C6b); sin recuperación de sesión (C7, C10); paso B habilitado al inicio (L2, L4); Laya «documentado» (A1). Mutación de fixture: `dataset_sha256` inválido (C3c). Todas fallan y se restauraron.
- [x] Job `browser-journeys` en `ci.yml`: YAML válido, pruebas de contrato de CI existentes verdes, pasos equivalentes ejecutados localmente en Windows.
- [x] P2 revisión PR #62 (1): `EXPECTED_MIN_CHECKS` por sitio (17/17/26/12/7) en `results.mjs`; `summarize` falla y lista `shortSites` si un sitio queda por debajo. RED observado (módulo sin exportaciones), luego verde; mutación (cicytex mínimo 27) da exit 1 y se restauró.
- [x] P2 (2): timeouts en `lib/timeout.mjs` (`withTimeout`, `fetchWithTimeout`; 30 s por comando CDP, 10 s por fetch, `CDP_TIMEOUT_MS`) con error que nombra método/URL. RED observado (módulo ausente). No se probó contra un Chrome colgado real, solo con promesa que no resuelve.
- [x] P2 (3): `KNOWN_UNMATCHED` (`GET /api/v2/sectors`, `GET /api/v2/sensors`: panel de resumen sin fixture, 404 inocuo) sigue como INFO; cualquier otra ruta sin fixture es FAIL en A9. RED observado en el helper `classifyUnmatched`; la rama FAIL de A9 en el flujo completo no se ejercitó (solo el helper).
- [x] Tras los P2: 29 pruebas verdes; dos corridas completas 78 PASS, 0 FAIL, 1 INFO con JSON idénticos (los PNG difieren byte a byte).
- [ ] Ejecución del job en GitHub Actions real (no validable localmente; pendiente en el primer PR).
- [ ] Revisión independiente (auditor) sobre el snapshot final.
