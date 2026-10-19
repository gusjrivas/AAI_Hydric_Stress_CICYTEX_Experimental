# Tasks

- [x] RED/GREEN helpers: `chrome.test.mjs` (módulo ausente, 1 suite fallida), `fixture-handler.test.mjs` (módulo ausente; luego pronóstico/feedback/modelo del laboratorio, 1 fallo), `tab-audit.test.mjs` (módulo ausente). `results.test.mjs` se escribió junto con su módulo (sin RED observado). 23 pruebas verdes.
- [x] Fixtures grabadas de backends reales (CICYTEX, producer_v2 Pergamino/Melchor, laboratorio) y README con el procedimiento.
- [x] Script multi-sitio: 78 PASS, 0 FAIL, 1 INFO; dos corridas consecutivas con JSON idénticos (CI=true, build limpio con `VITE_API_BASE_URL=`).
- [x] Mutaciones (build del frontend en copia temporal): ventana de objetivos futuros siempre visible (M9, P9 fallan); feedback preseleccionado (C6b); sin recuperación de sesión (C7, C10); paso B habilitado al inicio (L2, L4); Laya «documentado» (A1). Mutación de fixture: `dataset_sha256` inválido (C3c). Todas fallan y se restauraron.
- [x] Job `browser-journeys` en `ci.yml`: YAML válido, pruebas de contrato de CI existentes verdes, pasos equivalentes ejecutados localmente en Windows.
- [ ] Ejecución del job en GitHub Actions real (no validable localmente; pendiente en el primer PR).
- [ ] Revisión independiente (auditor) sobre el snapshot final.
