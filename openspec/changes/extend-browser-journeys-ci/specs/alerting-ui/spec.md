# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Recorridos de navegador reales en CI con fixtures deterministas

El repositorio DEBE ejecutar en CI recorridos de navegador reales para Melchor Romero, Pergamino, CICYTEX, el laboratorio y la ficha de Laya contra un servidor de fixtures versionado, con resultados deterministas, sin dependencias nuevas y declarando que las fixtures fijan un contrato grabado y no prueban el backend.

#### Scenario: Backend desconectado

- **GIVEN** un recorrido con datos cargados
- **WHEN** el servidor de fixtures simula la desconexión
- **THEN** la interfaz muestra un error con `role=alert`, no deja una decisión vigente y se recupera al reintentar.

#### Scenario: Laya deshabilitada

- **GIVEN** la ficha de arquitectura
- **WHEN** se muestra Laya
- **THEN** figura «Desactivado por defecto» y sin acciones.
