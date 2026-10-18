# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Mapa de arquitectura veraz y accesible

El mapa de arquitectura DEBE presentarse como diseño documentado (no monitoreo en vivo), ofrecer una ficha por componente con responsabilidad, entrada, salida, frontera, evidencia y límites, y una alternativa textual en tabla. Laya DEBE figurar como adaptador consultivo desactivado, sin sugerencias reales.

#### Scenario: Consultar un componente

- **GIVEN** la vista Arquitectura
- **WHEN** se selecciona un componente
- **THEN** se muestra su ficha con rutas de evidencia existentes en el repositorio y sus límites
- **AND** ninguna etapa se presenta como en ejecución ni se muestran métricas o trazas.
