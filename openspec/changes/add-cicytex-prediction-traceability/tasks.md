# Tasks

- [x] RED backend: 4 tests del endpoint (hechos del paquete, sin métricas ni filas, 503 sin summary, delegación a la aplicación inyectada).
- [x] GREEN backend: `CicytexProvenanceApplication`, esquemas cerrados, dependencia y ruta. Guardas de OpenAPI (identidad congelada, superficie de replay) actualizadas; `api:check` correcto.
- [x] RED frontend: 4 tests (hechos por horizonte, no disponible declarado, falla de la proyección, sin métricas).
- [x] GREEN frontend: cliente tipado y `CicytexTraceability`.
- [x] Revisión visual renderizada con datos reales.
- [x] Revisión independiente sin P0/P1/P2 y CI verde sobre el HEAD exacto. Evidencia: PR #53 mergeado (`a4a6ba4`) con `--match-head-commit 5098fd9`; 16 checks en `pass`; revisiones independientes de 8c78b68, 606eec7 y 5098fd9 sin P0/P1/P2. Los informes quedaron en la sesión, no en el repo.
