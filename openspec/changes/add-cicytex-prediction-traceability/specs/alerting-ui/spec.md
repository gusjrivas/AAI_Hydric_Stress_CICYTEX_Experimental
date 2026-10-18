# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Trazabilidad de una predicción concreta

El recorrido de reproducción DEBE mostrar, para la predicción visible, su fuente de datos, emisión, objetivo y la identidad del paquete archivado (dataset, commit, semilla, particiones y corridas de los modelos del horizonte) obtenidas por una proyección de sólo lectura de lista cerrada. NO DEBE incluir métricas, resultados ni observaciones posteriores al reloj, y DEBE declarar «no disponible» lo que no exista (versión del modelo, linaje de recalibración).

#### Scenario: Identidad por horizonte

- **GIVEN** una sesión de horizonte +2
- **WHEN** se muestra la trazabilidad
- **THEN** se listan las corridas de modelos del horizonte +2 y no las de otro horizonte.

#### Scenario: Proyección no disponible

- **GIVEN** que la proyección de identidad falla
- **WHEN** se abre una sesión
- **THEN** el recorrido sigue operativo
- **AND** el panel indica que la trazabilidad del paquete no está disponible.
