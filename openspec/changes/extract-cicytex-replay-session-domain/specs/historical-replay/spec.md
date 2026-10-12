## ADDED Requirements

### Requirement: Frontera de sesión de replay CICYTEX

El sistema MUST mantener el dominio, las transiciones y el repositorio in-memory de
sesiones CICYTEX fuera del router HTTP, preservando exactamente el contrato público
existente.

#### Scenario: Crear y consultar una sesión

- **GIVEN** una selección archivada válida
- **WHEN** se crea y luego consulta la sesión
- **THEN** create responde 201 y get responde 200 con el mismo estado público
- **AND** la fecha revelada inicial coincide con la fecha de emisión.

#### Scenario: Avanzar y reiniciar el reloj

- **GIVEN** una sesión existente
- **WHEN** se avanza o reinicia
- **THEN** el avance suma un día sin superar `2023-07-25`
- **AND** reset vuelve a la fecha de emisión y oculta nuevamente el futuro.

#### Scenario: Sesión ausente

- **GIVEN** un identificador que no existe
- **WHEN** se ejecuta get, advance o reset
- **THEN** el endpoint responde 404 con `Sesion inexistente`.

#### Scenario: Router sin almacenamiento de sesión

- **WHEN** se inspecciona el módulo del router CICYTEX
- **THEN** no define el modelo de dominio, `_sessions`, `_lock` ni generación de IDs
- **AND** recibe un caso de uso respaldado por `SessionRepository` mediante inyección.
