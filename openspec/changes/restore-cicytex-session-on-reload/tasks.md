# Tasks

- [x] RED observado por el implementador en la sesión (29 fallas antes de implementar, incluidas restauración válida/inválida, registros corruptos, `sessionStorage` que lanza, respuestas tardías, arrastre de borrador y sin preselección); no reproducible desde el commit final.
- [x] GREEN: `src/features/defense` y `src/features/producer` 21 archivos / 216 tests, dos corridas seguidas; `tsc -b` limpio; `oxlint` con los 3 warnings preexistentes. En la corrida completa (484 tests) fallaron por carga 2 tests de `producer` que pasan aislados; se registra como inestabilidad bajo carga, no como causa de este cambio.
- [ ] Revisión independiente sin P0/P1/P2 y CI verde sobre el HEAD exacto (completar con evidencia tras el merge).
- [ ] Verificación en navegador real de la recarga (bloque de recorridos de navegador).
- [x] Revisión independiente (P2): el aviso de «no recuperable» era `role="status"` con un botón dentro; ahora es un `alert` de solo texto con el botón fuera. RED observado (el test con `getByRole("alert")` y sin botón dentro falló en los casos no recuperables) y GREEN (216 tests en `defense` y `producer`). El foco de «Iniciar otra emisión» ya estaba cubierto.
