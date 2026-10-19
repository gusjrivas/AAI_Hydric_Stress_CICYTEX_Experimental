# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Recuperación segura de la sesión CICYTEX al recargar

La interfaz DEBE recuperar la sesión CICYTEX abierta al recargar solo si el servidor la devuelve y coincide en sitio, sonda, horizonte, fecha de emisión e id; NO DEBE enviar ninguna operación de escritura al restaurar ni restaurar borradores de feedback. Si no es recuperable DEBE explicarlo y ofrecer iniciar otra emisión.

#### Scenario: Sesión válida

- **GIVEN** un registro de sesión que coincide con la respuesta del servidor
- **WHEN** se recarga la página
- **THEN** se muestra la sesión y la selección, y el formulario de feedback está vacío y sin elección.

#### Scenario: Sesión inexistente o incoherente

- **GIVEN** un registro cuyo servidor responde 404 o con otra sonda, horizonte, emisión o id
- **WHEN** se recarga la página
- **THEN** se explica que no se pudo recuperar la sesión y se ofrece «Iniciar otra emisión», sin abrirla automáticamente.

### Requirement: Feedback sin respuesta preseleccionada

El formulario de feedback DEBE iniciar sin elección y DEBE mantener deshabilitado el envío hasta que la persona elija; ambas opciones DEBEN tener la misma jerarquía visual.

#### Scenario: Estado inicial

- **GIVEN** una realidad revelada
- **WHEN** se muestra el formulario
- **THEN** ninguna opción está marcada y «Registrar feedback» está deshabilitado.
