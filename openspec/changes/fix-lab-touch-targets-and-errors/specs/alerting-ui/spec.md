# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Laboratorio usable en pantallas táctiles y con backend apagado

El laboratorio de sensor simulado DEBE ofrecer objetivos táctiles de al menos 44 px a <=600 px de ancho y DEBE presentar los fallos de conexión con el servidor en español claro, sin exponer textos crudos del navegador, permitiendo reintentar sin quedar bloqueado.

#### Scenario: Objetivos táctiles a <=600 px

- **GIVEN** el laboratorio en un viewport de 600 px o menos
- **WHEN** se muestran los selects de filtros, los `summary` de detalles y el enlace «Ir al Laboratorio»
- **THEN** cada uno mide al menos 44 px de alto.

#### Scenario: Backend apagado

- **GIVEN** el backend no responde y `fetch` se rechaza con «Failed to fetch»
- **WHEN** se pulsa «A — Generar historial de prueba»
- **THEN** se muestra un `role="alert"` en español («No se pudo conectar con el servidor…») y no aparece el texto «Failed to fetch».

#### Scenario: Reintento tras el error

- **GIVEN** el laboratorio en estado de error por falta de conexión
- **WHEN** se pulsa «Iniciar una sesión nueva»
- **THEN** el error desaparece, el paso A vuelve a estar habilitado y puede volver a intentarse.
