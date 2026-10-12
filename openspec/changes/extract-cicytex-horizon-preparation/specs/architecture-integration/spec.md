## ADDED Requirements

### Requirement: Preparación científica compartida por horizonte CICYTEX
La solución MUST preparar cada horizonte CICYTEX mediante una composición única
de features temporales, eliminación contractual de faltantes, split temporal,
cuatro particiones y cálculo P20 exclusivo sobre entrenamiento.

#### Scenario: Horizontes autorizados
- **WHEN** cualquiera de los runners prepara los horizontes 1, 2 o 3
- **THEN** obtiene exactamente las mismas filas, índices, orden, tipos, cortes y
  threshold que la composición histórica.

#### Scenario: Threshold train-only
- **WHEN** cambian observaciones pertenecientes exclusivamente al período final
- **THEN** el P20 y la partición de entrenamiento permanecen sin cambios.

#### Scenario: Copias aisladas
- **WHEN** un runner añade su etiqueta a una partición preparada
- **THEN** no modifica el dataset recibido ni ninguna otra partición.

### Requirement: El protocolo no asume políticas específicas del runner
La preparación compartida MUST terminar antes del etiquetado, validación de
clases, entrenamiento, evaluación y publicación de artefactos.

#### Scenario: Runner experimental
- **WHEN** consume la preparación compartida
- **THEN** conserva `stress_proxy`, sus mensajes y su selección de candidato.

#### Scenario: Ensemble causal
- **WHEN** consume la preparación compartida
- **THEN** conserva `observed_label`, sus mensajes, componentes, ensemble y
  persistencia.
