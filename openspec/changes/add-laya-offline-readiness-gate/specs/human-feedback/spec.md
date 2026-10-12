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

#### Scenario: Confianza por debajo del umbral productivo

- **GIVEN** una predicción grabada cuya categoría es válida pero su confianza es menor a 0.85
- **WHEN** se calculan cobertura, exactitud selectiva y costo
- **THEN** la predicción cuenta como abstención
- **AND** `answer_confidence` tiene precedencia sobre la probabilidad de la categoría
- **AND** una confianza exactamente igual a 0.85 permanece aceptada.

#### Scenario: Trazabilidad de supply en el reporte

- **GIVEN** dos identidades de supply verificadas con cualquier commit, hash o tamaño diferente
- **WHEN** se serializan sus reportes canónicos
- **THEN** cada reporte contiene su `supply_digest`
- **AND** los digests son diferentes.

#### Scenario: Métricas puntuales aprobadas sin protocolo científico completo

- **GIVEN** evidencia marcada como humana, supply chain verificada y todos los point estimates aprobados
- **WHEN** se ejecuta el gate
- **THEN** el estado es `BLOCKED_SCIENTIFIC_METHOD_PENDING`
- **AND** no puede emitirse `ELIGIBLE_FOR_SHADOW_REVIEW` hasta incorporar corpus suficiente, LOSO, intervalos de confianza y delta pareado contra baseline
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
