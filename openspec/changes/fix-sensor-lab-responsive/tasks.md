# Tasks

- [x] RED observado por el implementador en la sesión (4 tests: declaración única de no disponibles, sin repetición por campo, ancho de la nota por CSS, motivo de bloqueo por CSS); no reproducible desde el commit final.
- [x] GREEN: `src/features/lab` 35/35; `tsc -b` limpio; `oxlint` con los 3 warnings preexistentes. La suite completa dio 486/486 y 485/486 (un test de feedback inestable bajo carga, ajeno al laboratorio).
- [x] Observación en Chrome real (CDP, sin desbordes reales a 360 ni a 1366 px): inicio, pasos B/C/D y final a 360 px, final a 1366 px y estado de error con POST bloqueados. Los pasos intermedios a 1366 px solo se midieron.
- [ ] Revisión independiente sin P0/P1/P2 y CI verde sobre el HEAD exacto (completar con evidencia tras el merge).
- [ ] Pendientes de tamaño táctil, mensaje de error en español y backend apagado de verdad (ver proposal).
