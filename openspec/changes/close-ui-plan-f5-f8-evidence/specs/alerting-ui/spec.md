# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Cierre documental del plan de UI sin promover fases con pendientes

La documentación de seguimiento de la interfaz DEBE reflejar los PR fusionados hasta el último verificado, distinguir el estado histórico de un PR de su estado vigente y marcar una fase como completada sólo si cumple su criterio de aceptación, separando los pendientes humanos de los técnicos.

#### Scenario: Fase con pendientes humanos y técnicos

- **GIVEN** una fase del plan cuyo criterio de aceptación no se cumple por completo
- **WHEN** se actualiza el seguimiento con la evidencia de los PR fusionados
- **THEN** la fase conserva el estado en curso y lista aparte los pendientes humanos y los técnicos
- **AND** el ADR conserva su estado Propuesto hasta que el dueño lo cambie y no se le atribuye aprobación.

#### Scenario: Limitación superada por un PR posterior

- **GIVEN** una limitación documentada en el estado de un PR anterior que un PR posterior reemplaza
- **WHEN** se actualiza la fila de la fase
- **THEN** la frase indica que es el estado en el PR anterior y que fue superada por el posterior.
