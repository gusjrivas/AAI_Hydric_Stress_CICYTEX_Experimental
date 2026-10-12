## ADDED Requirements

### Requirement: Gate offline y fail-closed para readiness de Laya

El sistema MUST evaluar evidencia grabada de Laya sin red y MUST producir un reporte
determinista que nunca autorice activación productiva.

#### Scenario: Fixture sintética perfecta

- **GIVEN** un corpus sintético con predicciones perfectas
- **WHEN** se ejecuta el gate offline
- **THEN** la decisión es `CHARACTERIZATION_ONLY`
- **AND** `production_enablement_authorized` es falso.

#### Scenario: Artefacto ausente, alterado o puntero LFS

- **GIVEN** un manifest con tamaño y SHA-256 fijados
- **WHEN** el artefacto local falta, no coincide o sólo contiene un puntero Git LFS
- **THEN** la verificación de supply chain falla de forma cerrada
- **AND** no se realiza ninguna descarga.

#### Scenario: Degradación oculta por el promedio

- **GIVEN** métricas agregadas aceptables y un sitio científico bajo el límite fijado
- **WHEN** se evalúa el gate
- **THEN** la decisión es `FAIL_QUALITY`
- **AND** el sitio fallido queda identificado en razones ordenadas y estables.

#### Scenario: Evidencia humana suficiente y gates aprobados

- **GIVEN** corpus humano adjudicado de CICYTEX, Pergamino y Melchor Romero, supply chain verificada y todos los límites aprobados
- **WHEN** se ejecuta el gate
- **THEN** el máximo estado es `ELIGIBLE_FOR_SHADOW_REVIEW`
- **AND** la revisión humana sigue siendo obligatoria
- **AND** la activación productiva sigue desautorizada.

### Requirement: Aislamiento del evaluador offline

El evaluador offline MUST NOT ser una dependencia de backend, forecast, ingesta,
entrenamiento, recalibración o runners experimentales.

#### Scenario: Corridas existentes

- **GIVEN** Laya sin configurar
- **WHEN** se ejecutan las corridas de CICYTEX, Pergamino, Melchor Romero y laboratorio mock
- **THEN** conservan sus contratos y resultados previos
- **AND** el gate offline no se invoca.
