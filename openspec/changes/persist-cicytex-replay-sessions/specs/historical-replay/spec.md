## ADDED Requirements

### Requirement: Persistencia durable de sesiones CICYTEX

El sistema MUST persistir `ReplaySession` mediante el puerto `SessionRepository`
en un SQLite v1 cerrado, conservando el contrato HTTP existente.

#### Scenario: Reinicio y colisión

- **GIVEN** una sesión creada y avanzada
- **WHEN** se reconstruye repositorio y servicio sobre el mismo archivo
- **THEN** la sesión conserva exactamente su reloj y límite
- **AND** un ID duplicado falla sin sobrescribir la fila previa.

#### Scenario: Store inválido

- **GIVEN** un archivo vacío, corrupto, ajeno, parcial o de versión futura
- **WHEN** se abre el repositorio
- **THEN** falla cerrado sin reinitializar ni filtrar path o contenido
- **AND** una fila que viola el dominio también falla cerrado.

#### Scenario: Transiciones concurrentes

- **GIVEN** dos adaptadores o procesos sobre el mismo archivo
- **WHEN** avanzan una sesión concurrentemente
- **THEN** cada transición se conserva exactamente una vez
- **AND** bootstrap concurrente produce un único schema v1 completo.

#### Scenario: Exclusión de feedback y reset

- **GIVEN** un callback `with_session` activo
- **WHEN** otro proceso intenta resetear la misma sesión
- **THEN** reset espera al cierre del callback
- **AND** el orden inverso observa el reset ya confirmado
- **AND** una excepción del callback hace rollback y libera la transacción.

#### Scenario: Contención acotada

- **GIVEN** el archivo bloqueado más allá del timeout configurado
- **WHEN** se intenta una transición
- **THEN** se obtiene un error de repositorio controlado y privado
- **AND** nunca se usa un fallback in-memory.

#### Scenario: Wiring HTTP durable

- **GIVEN** `CICYTEX_REPLAY_SESSION_DB` apuntando a un store válido
- **WHEN** se reinicia la dependencia del proceso
- **THEN** get conserva la sesión y el payload previo
- **AND** un store inválido responde 503 sanitizado
- **AND** el router no contiene imports SQLite ni política del path.
