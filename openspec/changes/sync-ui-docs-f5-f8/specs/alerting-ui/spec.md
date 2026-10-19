# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Documentación de UI sincronizada con los cambios fusionados

La documentación de la interfaz de defensa (ADR, paquete de defensa, verificación de navegador y seguimiento) DEBE reflejar los PR fusionados en `main` y separar los pendientes técnicos de los pendientes de validación humana, sin atribuir al dueño del proyecto una aprobación que no haya dado.

#### Scenario: Funcionalidad entregada y límites vigentes

- **GIVEN** un PR fusionado que reemplaza una limitación documentada
- **WHEN** se actualiza el paquete de defensa
- **THEN** la limitación obsoleta se elimina o se reformula con el alcance real
- **AND** los pendientes restantes figuran como tales y el ADR conserva su estado hasta que el dueño lo cambie.
