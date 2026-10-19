# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Laboratorio de sensores con acciones jerarquizadas y trazabilidad declarada

El recorrido del laboratorio DEBE presentar el paso de la fase actual como acción primaria, explicar por qué los demás pasos están deshabilitados y mostrar la trazabilidad de la sesión declarando los datos y la revisión como sintéticos, el reloj como ficticio y «no disponible» lo que este recorrido no produce.

#### Scenario: Paso deshabilitado

- **GIVEN** un paso que no corresponde a la fase actual
- **WHEN** se muestra el laboratorio
- **THEN** el paso está deshabilitado y una nota enlazada con `aria-describedby` explica por qué.

#### Scenario: Procedencia sintética

- **GIVEN** una sesión de prueba
- **WHEN** se muestra la trazabilidad
- **THEN** la procedencia figura «sintético» y commit, SHA-256 del dataset, MLflow, versión de modelo y linaje figuran «no disponible».
