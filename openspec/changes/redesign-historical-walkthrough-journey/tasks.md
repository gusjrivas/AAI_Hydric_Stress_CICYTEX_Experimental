# Tasks

- [x] RED observado por el implementador en la sesión (no reproducible desde el commit final): 6 tests nuevos (`HistoricalWalkthrough.verdict.test.tsx`) fallaron antes de implementar: veredicto con alerta, veredicto sin alerta con realidad revelada, jerarquía de botones y nota de fin, trazabilidad, versión del modelo nula, fila futura filtrada.
- [x] GREEN: 55 archivos y 443 tests en verde (corrida completa previa a la revisión); tras la revisión, `src/features/producer` 18 archivos / 151 tests; `tsc -b` limpio; `oxlint` con los 3 warnings preexistentes.
- [x] Revisión independiente (P2): id de la nota por `useId`, `role=status` y foco en la nota al llegar al final. RED observado quitando el fix (1 test falló), GREEN con él.
- [ ] Revisión independiente sin P0/P1/P2 y CI verde sobre el HEAD exacto (completar con evidencia tras el merge).
- [ ] Verificación visual renderizada (escritorio y estrecho) y en navegador real de Pergamino y Melchor Romero: pendiente, requiere el backend `producer_v2` con el recorrido de demostración.
