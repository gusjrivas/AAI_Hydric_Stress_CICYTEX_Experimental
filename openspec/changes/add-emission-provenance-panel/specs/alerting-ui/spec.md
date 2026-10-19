# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Procedencia de una emisión producer_v2

El recorrido histórico de producer_v2 DEBE mostrar, en un panel de sólo lectura, la procedencia de la emisión visible a partir de una lista blanca de identidad entregada por el backend: SHA-256 del dataset, `model_version`, `trained_through`, `calibration_version`, identidad del ensamble y la identidad de código (commit y estado del árbol) registrada al entrenar. El backend NO DEBE exponer el `input_snapshot` ni campos fuera de la lista. Lo que un bundle anterior no registró DEBE mostrarse «no registrado» y NUNCA inferirse del checkout actual; lo que el backend no persiste (configuración completa, corrida MLflow, semilla) DEBE declararse «no disponible».

#### Scenario: Emisión con identidad de código registrada

- **GIVEN** una emisión cuyo bundle registró `code_identity`
- **WHEN** se muestra el panel
- **THEN** se ven el commit, si el árbol tenía cambios, el SHA-256 del dataset, la versión del modelo, la calibración y «entrenado hasta».

#### Scenario: Emisión sin identidad de código

- **GIVEN** un lote cuyo bundle no registró `code_identity`
- **WHEN** se muestra el panel
- **THEN** el commit figura «no registrado»
- **AND** no se muestra ningún commit tomado del repositorio actual.

#### Scenario: Lote inexistente

- **GIVEN** un `batch_id` que no existe para el sensor
- **WHEN** se consulta la procedencia
- **THEN** el backend responde 404 con el formato de error v2.

#### Scenario: Backend no disponible

- **GIVEN** que la consulta de procedencia falla
- **WHEN** se abre el recorrido
- **THEN** el recorrido sigue operativo
- **AND** el panel informa el error y ofrece reintentar.
