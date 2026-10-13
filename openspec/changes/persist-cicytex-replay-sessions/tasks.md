## 1. TDD

- [x] 1.1 Especificar schema v1, metadata, reinicio, colisión y corrupción.
- [x] 1.2 Especificar concurrencia de threads, procesos y bootstrap.
- [x] 1.3 Especificar exclusión `with_session`, orden inverso y rollback.
- [x] 1.4 Especificar timeout busy, privacidad, wiring HTTP y aislamiento.
- [x] 1.5 Registrar RED de corrupción post-bootstrap y schema SQL exacto.

## 2. Implementación

- [ ] 2.1 Implementar `SQLiteSessionRepository` sin dependencias de backend.
- [ ] 2.2 Implementar transacciones acotadas y errores controlados.
- [ ] 2.3 Conectar el adaptador mediante dependencia cacheada y path configurable.
- [ ] 2.4 Traducir fallas del store a 503 sanitizado sin fallback.
- [ ] 2.5 Normalizar corrupción tardía sin envolver excepciones del caller.
- [ ] 2.6 Validar objetos y DDL exactos del schema sin mutar el archivo.

## 3. Verificación

- [ ] 3.1 Dejar verdes tests unitarios, multiproceso y HTTP.
- [ ] 3.2 Ejecutar regresiones de replay, CICYTEX y escenarios históricos.
- [ ] 3.3 Validar Black, Ruff, OpenSpec y diff-check.
