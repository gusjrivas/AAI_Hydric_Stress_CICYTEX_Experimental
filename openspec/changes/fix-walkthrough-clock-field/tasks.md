# Tasks

- [x] RED: el test «shows the effective reveal date in the clock field from the start» falló (valor vacío).
- [x] GREEN: `src/features/producer` 18 archivos / 154 tests en verde; `tsc -b` limpio; `oxlint` con los 3 warnings preexistentes.
- [x] Revisión independiente, P2 1: editar por segmentos reiniciaba el campo; se agregó un borrador local con `base` del reloj efectivo. RED observado y GREEN.
- [x] Revisión independiente, P2 2: el borrador viejo reaparecía en un ciclo A→B→A; se descarta cuando cambia el reloj efectivo. RED observado quitando la línea (1 test falló) y GREEN con ella.
- [ ] Re-revisión independiente sin P0/P1/P2 y CI verde sobre el HEAD exacto (completar con evidencia tras el merge).
