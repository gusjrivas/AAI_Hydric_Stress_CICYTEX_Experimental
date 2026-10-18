# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Recorrido de decisión legible con detalle progresivo

El recorrido de reproducción DEBE presentar la decisión con su acción principal, un gráfico con escala y unidad cuyo resumen textual compare la última observación revelada con el P20, el detalle por método como divulgación progresiva y una explicación cuando aún no haya objetivos revelados. NO DEBE mostrar fechas ni valores posteriores al reloj revelado.

#### Scenario: Resumen del gráfico sin datos futuros

- **GIVEN** una sesión con observaciones reveladas hasta una fecha
- **WHEN** se muestra el gráfico
- **THEN** el resumen indica la última observación revelada y si está por encima o por debajo del P20
- **AND** no menciona fechas posteriores al reloj.

#### Scenario: Comparación acumulada sin objetivos revelados

- **GIVEN** una sesión recién abierta
- **WHEN** se muestra la comparación acumulada
- **THEN** se explica que aún no hay objetivos revelados en lugar de una tabla vacía.
