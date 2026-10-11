## ADDED Requirements

### Requirement: API v2 aditiva para triaje consultivo de feedback

La API MUST exponer `POST /api/v2/feedback/triage` con `site_id` y `comment`, delegar
el caso de uso de `human-feedback` y devolver una respuesta tipada que siempre indique
revisión humana obligatoria. La ruta MUST NOT persistir, confirmar, rechazar ni recalibrar.

#### Scenario: Dependencia consultiva disponible

- **WHEN** se envía una observación válida y el motor responde
- **THEN** se devuelve HTTP 200 con categoría, confianza, proveedor, revisión,
  abstención, motivo y `human_review_required=true`.

#### Scenario: Laya no está configurada

- **WHEN** se envía una observación válida sin configuración de Laya
- **THEN** se devuelve HTTP 200 con fallback explícito y abstención
- **AND** ninguna ruta o artefacto operacional existente cambia.

