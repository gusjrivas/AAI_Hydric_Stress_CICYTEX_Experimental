# Tasks

- [x] RED observado por el implementador en la sesión (no reproducible desde el commit final): 5 tests nuevos (`SensorLabPage.journey.test.tsx`) fallaron antes de implementar.
- [x] GREEN: `src/features/lab` 31/31; `src/features/lab` 32/32 tras la revisión; suite completa previa a la revisión 56 archivos / 451 tests; `tsc -b` limpio; `oxlint` con los 3 warnings preexistentes.
- [x] Revisión independiente, P2: la nota por fase solo se probaba en `idle`; test nuevo que recorre A→D y comprueba el texto de cada fase alcanzable. Mutación verificada (cambiar el texto de `normal` hace fallar el test).
- [ ] Re-confirmación: CI verde sobre el HEAD exacto; revisión independiente sin P0/P1/P2 y CI verde sobre el HEAD exacto (completar con evidencia tras el merge).
- [ ] Verificación visual renderizada y en navegador real del laboratorio: pendiente.
