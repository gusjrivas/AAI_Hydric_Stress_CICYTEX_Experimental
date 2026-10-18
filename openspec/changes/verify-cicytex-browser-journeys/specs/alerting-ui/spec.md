# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Verificación reproducible del recorrido CICYTEX en navegador real

El repositorio DEBE incluir un procedimiento reproducible, sin dependencias nuevas, que ejercite el recorrido CICYTEX en un navegador real y registre sus resultados, distinguiendo pruebas de componente, verificación en navegador y validación visual.

#### Scenario: Desconexión y recuperación

- **GIVEN** una sesión abierta en el navegador
- **WHEN** se corta la red y se pulsa «Día siguiente»
- **THEN** aparece un mensaje de error, el botón queda habilitado y, al volver la red, el reloj avanza y el error desaparece.

#### Scenario: Recarga

- **GIVEN** una sesión abierta
- **WHEN** se recarga la página
- **THEN** se conserva la ruta y se declara que la sesión no se reabre automáticamente.

#### Scenario: Foco por teclado

- **GIVEN** la carga inicial del recorrido
- **WHEN** se recorre con Tab
- **THEN** cada elemento enfocado muestra indicador de foco y no hay trampa de teclado.
