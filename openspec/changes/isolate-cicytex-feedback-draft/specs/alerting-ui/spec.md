# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Borrador de feedback aislado por sesión

El borrador de feedback del recorrido de reproducción (elección y comentario) DEBE pertenecer a la sesión en la que se escribió y DEBE descartarse al cambiar sonda, horizonte o fecha, al abrir otra sesión y al reiniciar la actual. Una respuesta tardía de otra sesión no DEBE registrarse ni alterar el borrador vigente.

#### Scenario: Cambio de sonda con borrador escrito

- **GIVEN** un borrador con elección "No coincide" y un comentario en la sesión de una sonda
- **WHEN** se cambia la sonda y se abre una nueva sesión
- **THEN** el formulario muestra la elección por defecto y el comentario vacío.

#### Scenario: Reinicio de la sesión

- **GIVEN** un borrador escrito
- **WHEN** se reinicia la sesión
- **THEN** el borrador se descarta.

#### Scenario: Respuesta tardía de otra sesión

- **GIVEN** un feedback enviado y aún sin respuesta
- **WHEN** se cambia la selección y se abre otra sesión antes de que responda el servidor
- **THEN** la respuesta tardía no se muestra como registrada en la sesión nueva.
