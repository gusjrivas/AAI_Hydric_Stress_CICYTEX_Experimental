# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Acciones de revisión con jerarquía equivalente

Las acciones «Confirmar resultado» y «Rechazar resultado» DEBEN presentarse con el mismo estilo, tamaño y orden estable, sin preselección ni foco inicial, con una descripción común y un mínimo táctil de 44 px en pantallas estrechas. El envío DEBE bloquearse tras el primer intento y el foco NO DEBE perderse al deshabilitarse un control.

#### Scenario: Igual jerarquía

- **GIVEN** una tarjeta de pronóstico con revisión abierta
- **WHEN** se muestran las acciones
- **THEN** ambos botones comparten clase, ninguno es primario y ninguno está seleccionado.

#### Scenario: Doble envío

- **GIVEN** una opinión lista para guardar
- **WHEN** se intenta enviar dos veces seguidas
- **THEN** se realiza un solo envío.
