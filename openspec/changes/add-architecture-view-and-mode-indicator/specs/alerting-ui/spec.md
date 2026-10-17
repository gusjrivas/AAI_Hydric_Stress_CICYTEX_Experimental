# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Indicador de modo y destino de arquitectura

La interfaz DEBE rotular cada vista con su modo (Operación, Replay histórico, Laboratorio sintético o Documentación de diseño) mediante texto visible derivado únicamente de la ruta, y DEBE ofrecer el destino «Arquitectura» sin retirar ni renombrar ningún destino ni ancla existente.

#### Scenario: Distinguir replay, laboratorio y operación

- **GIVEN** cualquier vista de la aplicación
- **WHEN** se abre
- **THEN** se muestra su modo con texto (no sólo color) y cambiar de vista no ejecuta modelos, no borra sesiones ni inicia recalibraciones.

#### Scenario: Consultar la arquitectura

- **GIVEN** la aplicación abierta
- **WHEN** se abre `#arquitectura`
- **THEN** se muestra `ArchitectureFlow` con sus etapas existentes, rotulado como documentación de diseño, y `#evidencia` enlaza a ese destino.

## MODIFIED Requirements

### Requirement: Navegación centrada en la decisión y resumen fiel

La interfaz DEBE ofrecer Resumen, Alertas y revisión, Calidad de datos, Modelo y trazabilidad, y Evidencia y arquitectura, agrupados en seis secciones de la navegación principal (Seguimiento histórico, Mi cultivo, Laboratorio, Evidencia, Arquitectura y Herramientas técnicas). El Resumen DEBE priorizar el último pronóstico registrado, sus fechas y el acceso a revisión humana.

#### Scenario: Leer el resumen

- **GIVEN** un historial disponible
- **WHEN** se abre Resumen
- **THEN** se presenta la fila con mayor fecha de referencia, su alerta, probabilidad disponible y fecha objetivo
- **AND** se distingue esa fecha de la cobertura de datos y se conserva la aclaración de señal predictiva relativa, no diagnóstico ni probabilidad agronómicamente calibrada.

#### Scenario: Navegar sin perder contexto

- **GIVEN** un sensor activo y un resultado consultado o generado
- **WHEN** se cambia de destino o se usa Atrás/Adelante
- **THEN** se conserva el contexto compartido, se identifica el destino activo y se enfoca su encabezado, sin iniciar POST
- **AND** los enlaces previos a calidad, predicción, linaje y evidencia siguen resolviendo al destino correspondiente.
