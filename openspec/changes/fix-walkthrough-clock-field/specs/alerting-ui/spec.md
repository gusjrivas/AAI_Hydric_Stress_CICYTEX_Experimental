# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Campo de reloj del recorrido histórico con valor efectivo

El campo «Recorrido hasta» DEBE mostrar la fecha del reloj efectivo del recorrido, también antes de que la persona lo modifique.

#### Scenario: Estado inicial

- **GIVEN** una emisión seleccionada y el reloj sin modificar
- **WHEN** se muestra el recorrido
- **THEN** el campo muestra la fecha de la emisión y no está vacío.
