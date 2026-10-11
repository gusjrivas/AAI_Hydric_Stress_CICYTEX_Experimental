## ADDED Requirements

### Requirement: Triaje consultivo y abstencionista de observaciones humanas

El sistema MUST poder solicitar a un motor de decisión una categoría sugerida para una
observación textual. La sugerencia MUST ser consultiva, exigir revisión humana y no
puede confirmar/rechazar alertas, alterar etiquetas, recalibrar ni entrenar modelos.

#### Scenario: Sugerencia con confianza suficiente

- **GIVEN** una observación y una respuesta válida por encima del umbral configurado
- **WHEN** se ejecuta el triaje
- **THEN** se devuelve categoría, confianza, proveedor y revisión del modelo
- **AND** `human_review_required` permanece verdadero.

#### Scenario: Confianza insuficiente

- **GIVEN** una respuesta válida por debajo del umbral configurado
- **WHEN** se ejecuta el triaje
- **THEN** el resultado se marca como abstención y categoría `unclassified`
- **AND** no se realiza ninguna mutación.

#### Scenario: Motor deshabilitado, lento o inválido

- **GIVEN** que el motor no está configurado, excede el timeout o devuelve un contrato inválido
- **WHEN** se ejecuta el triaje
- **THEN** se devuelve un fallback determinista `unclassified`
- **AND** el flujo de feedback existente no se bloquea ni cambia.

