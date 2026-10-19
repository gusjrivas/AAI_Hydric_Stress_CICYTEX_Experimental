# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Registro de decisiones y límites de la interfaz de defensa

El repositorio DEBE mantener un ADR de la arquitectura de la interfaz de defensa y un paquete de defensa cuyos límites, verificaciones y elementos «no verificado» coincidan con el estado real de `main`.

#### Scenario: Límite declarado

- **GIVEN** una verificación que cubre sólo un sitio
- **WHEN** se redacta el paquete de defensa
- **THEN** el documento nombra el alcance real y no extiende la afirmación a otros sitios.
