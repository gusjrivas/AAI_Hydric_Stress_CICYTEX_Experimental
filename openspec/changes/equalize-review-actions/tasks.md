# Tasks

- [x] RED observado por el implementador en la sesión (6 tests fallaron antes de implementar; dos siguieron fallando por errores del propio test y se corrigieron); no reproducible desde el commit final.
- [x] Mutaciones del implementador: añadir una clase primaria a un botón y quitar los guards de doble envío hicieron fallar los tests correspondientes; revertidas.
- [x] GREEN: `src/features/producer` 19 archivos / 163 tests; `tsc -b` limpio; `oxlint` con los 3 warnings preexistentes. En la corrida completa fallaron por carga 2 tests ajenos (timeout de 5 s) que pasan aislados.
- [x] Correcciones P2 de la revisión del PR #60 (guard síncrono vacuo, foco perdido en caminos de error, comentario de `serverBlock`): RED observado = 7 tests de foco fallaron (conflicto de revisión, de idempotencia, demo bloqueada, revisión no abierta, pronóstico inexistente, `TargetObservationBlockedError`, error de red) antes de corregir; el test de doble submit en el mismo `act` pasó con el guard y, al quitar `|| submittingRef.current`, falló (`submitReview` llamado 2 veces en vez de 1); restaurado. GREEN: `src/features/producer` 19 archivos / 171 tests; `tsc -b` limpio; lint con los 3 warnings preexistentes.
- [ ] Revisión independiente sin P0/P1/P2 y CI verde sobre el HEAD exacto (completar con evidencia tras el merge).
- [ ] Verificación en navegador real del tamaño táctil y del foco (bloque de recorridos de navegador).
