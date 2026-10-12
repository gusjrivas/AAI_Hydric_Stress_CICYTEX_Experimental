## Context

`ReplaySessionService` ya depende de `SessionRepository` y exige una operación
atómica `with_session`. SQLite reemplaza únicamente el adaptador in-memory usado
por el backend; el dominio permanece puro.

## Decisions

### Esquema cerrado y arranque conservador

Una ruta inexistente se inicializa mediante una transacción con `user_version=1`,
tabla de metadata y tabla de sesiones. Un archivo existente vacío, corrupto,
ajeno, parcial o de versión futura no se migra ni se reemplaza silenciosamente.
Cada fila se reconstruye mediante `ReplaySession`, por lo que datos inválidos
fallan cerrados.

### Transacciones entre procesos

`add`, `update` y `with_session` usan transacciones de escritura acotadas. La
lectura, transición y escritura pertenecen a una misma transacción. Un callback
que falla provoca rollback y siempre libera conexión y lock. El timeout de busy
es finito y se traduce a un error de repositorio controlado; nunca activa un
fallback in-memory.

### Wiring y privacidad

`CICYTEX_REPLAY_SESSION_DB` selecciona el archivo; la dependencia cacheada crea
un servicio por proceso y puede reconstruirse tras reinicio. Errores de apertura,
schema, fila o busy se traducen a 503 sin rutas, SQL ni contenido privado. El
router no conoce SQLite ni la política de paths.

## Out of Scope

No se persiste feedback en SQLite, no se cambia el paquete causal, no se agregan
TTL, replicación, migraciones futuras ni coordinación distribuida fuera de las
garantías transaccionales del archivo SQLite compartido.
