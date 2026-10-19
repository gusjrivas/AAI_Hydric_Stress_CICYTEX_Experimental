# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Laboratorio legible a 360 px y 1366 px sin repetición de no disponibles

El laboratorio DEBE usar el ancho útil para sus notas, declarar en una sola frase los artefactos no disponibles de su trazabilidad y no producir desbordes horizontales reales a 360 px.

#### Scenario: Declaración única

- **GIVEN** el panel de trazabilidad de la sesión de prueba
- **WHEN** se muestra
- **THEN** una sola declaración nombra commit, SHA-256 del dataset, corridas de MLflow, versión de modelo y linaje como no disponibles.
