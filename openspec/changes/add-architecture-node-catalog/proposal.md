# Change: Catálogo de arquitectura con fichas por nodo

- HU6/HU7 (presentación) · `alerting-ui` · CRISP-DM Deployment. Sin impacto científico, de API ni de permisos.
- Evoluciona `ArchitectureFlow` (no crea otro mapa): conserva las siete etapas y sus enlaces; añade catálogo tipado, fichas (responsabilidad, entrada, salida, frontera, evidencia, límites), alternativa textual en tabla y Laya como adaptador consultivo desactivado.
- Es diseño documentado y versionado: no simula salud, métricas ni trazas. Una prueba verifica que toda ruta de evidencia exista en el repositorio.
- Non-goals: telemetría real, activar Laya, cambiar datos o modelos. Rollback: revertir el PR.
