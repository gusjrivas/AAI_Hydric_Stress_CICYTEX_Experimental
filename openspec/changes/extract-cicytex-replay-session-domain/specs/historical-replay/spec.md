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

#### Scenario: Avances concurrentes

- **GIVEN** varias solicitudes que avanzan la misma sesión
- **WHEN** el repositorio aplica las transiciones concurrentes
- **THEN** cada avance válido se conserva exactamente una vez, sin actualizaciones perdidas.

#### Scenario: Colisión de identificador generado

- **GIVEN** una sesión existente y un nuevo create cuyo generador repite su ID
- **WHEN** el repositorio intenta crear la segunda sesión
- **THEN** falla cerrado y conserva intacta la sesión original.

#### Scenario: Pureza del dominio

- **WHEN** se inspeccionan dominio, caso de uso, puerto y adaptador in-memory
- **THEN** no dependen de FastAPI, pandas, JSON, variables de entorno, paths ni filesystem
- **AND** la serialización y sincronización del feedback permanecen fuera de esa frontera.
