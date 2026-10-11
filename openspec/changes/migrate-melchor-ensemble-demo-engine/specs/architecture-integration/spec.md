## ADDED Requirements

### Requirement: Segundo adaptador del motor ensemble común
Melchor Romero MUST consumir el mismo motor de entrenamiento ensemble que
Pergamino mediante un plan inmutable, sin introducir condicionales por sitio en
el motor.

#### Scenario: Ejecución sobre el dataset real
- **WHEN** se ejecuta la demostración Melchor sobre el snapshot versionado
- **THEN** conserva imputación causal, cortes 2024, threshold P20, tres familias,
  identidades y bundles operacionales anteriores al refactor.

#### Scenario: Fallo después de un horizonte
- **WHEN** un horizonte posterior falla tras completar el primero
- **THEN** la fachada registra `fallido`, conserva threshold y progreso previo y
  propaga el error original.

### Requirement: Aislamiento de integraciones externas
La migración MUST NOT agregar dependencias entre el motor científico y Laya,
feedback humano, API o interfaz.

#### Scenario: Regresión multicontexto
- **WHEN** se integra el segundo adaptador
- **THEN** Pergamino, CICYTEX, Laboratorio y el triaje consultivo Laya conservan
  sus contratos y pruebas existentes.
