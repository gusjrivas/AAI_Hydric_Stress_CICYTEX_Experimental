# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Operación robusta del recorrido de reproducción

El recorrido de reproducción DEBE ignorar respuestas de peticiones iniciadas bajo una selección anterior, impedir envíos concurrentes de una misma acción y ofrecer reintento y estado de carga cuando el catálogo no se puede obtener.

#### Scenario: Respuesta tardía tras cambiar la selección

- **GIVEN** una sesión en proceso de apertura
- **WHEN** la persona cambia la sonda antes de que responda el servidor
- **THEN** la respuesta tardía no se muestra y los controles quedan disponibles.

#### Scenario: Doble envío de feedback

- **GIVEN** un formulario de feedback con una petición en curso
- **WHEN** se vuelve a enviar el formulario
- **THEN** no se emite una segunda petición.

#### Scenario: Catálogo no disponible

- **GIVEN** un fallo al obtener el catálogo
- **WHEN** se muestra el error
- **THEN** se ofrece "Reintentar" y, al tener éxito, el error desaparece.
