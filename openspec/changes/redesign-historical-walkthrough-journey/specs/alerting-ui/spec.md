# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Recorrido histórico con veredicto, acciones jerarquizadas y trazabilidad declarada

El recorrido histórico compartido DEBE mostrar la decisión del ensamble como veredicto legible, jerarquizar avanzar como acción primaria, explicar por qué avanzar está deshabilitado, mostrar la trazabilidad de la predicción con los datos disponibles declarando «no disponible» los que no existen, y no mostrar observaciones posteriores al reloj revelado.

#### Scenario: Veredicto y realidad oculta

- **GIVEN** una emisión cuyo objetivo es posterior al reloj revelado
- **WHEN** se muestra el recorrido
- **THEN** aparece el veredicto del ensamble sin la realidad revelada.

#### Scenario: Fin del recorrido

- **GIVEN** el reloj en su máximo
- **WHEN** se muestra «Día siguiente»
- **THEN** está deshabilitado y una nota explica que no quedan días por revelar.

#### Scenario: Procedencia no disponible

- **GIVEN** una predicción sin hash de dataset, commit ni corridas en el payload
- **WHEN** se muestra la trazabilidad
- **THEN** esos datos figuran como «no disponible» y no se simulan.

#### Scenario: Observación futura

- **GIVEN** una respuesta de lecturas que incluye una fila posterior al reloj
- **WHEN** se muestra la tabla de observaciones
- **THEN** esa fila no se muestra.
