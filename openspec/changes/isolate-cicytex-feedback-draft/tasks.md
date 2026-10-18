# Tasks

- [x] RED: 4 tests (cambio de sonda, reinicio, nueva sesión sobre la misma selección, respuesta tardía de otra sesión) fallaron por conservar el borrador.
- [x] GREEN: borrador ligado a `session_id` y descarte explícito al abrir, reiniciar o cambiar la selección.
- [x] Revisión independiente sin P0/P1/P2 y CI verde sobre el HEAD exacto. Evidencia: PR #51 mergeado (`2ce2cc2`) con `--match-head-commit 384784e`; 16 checks en `pass` (`gh pr checks 51`); re-revisión independiente sin P0/P1/P2 (un P3). El informe del revisor quedó en la sesión, no en el repo.
