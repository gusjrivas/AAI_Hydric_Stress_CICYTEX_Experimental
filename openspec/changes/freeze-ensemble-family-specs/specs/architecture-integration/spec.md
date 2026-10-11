## ADDED Requirements

### Requirement: Configuración ensemble profundamente inmutable
Cada plan de demostración ensemble MUST contener especificaciones de familias
profundamente inmutables con valores escalares serializables y finitos.

#### Scenario: Mutación del dict público compatible
- **WHEN** un consumidor modifica temporalmente `FAMILY_PARAMS`
- **THEN** el entrenamiento y el manifiesto continúan usando los parámetros
  científicos congelados en el plan.

#### Scenario: Materialización en un borde mutable
- **WHEN** el fitter o serializador solicita parámetros
- **THEN** recibe una copia dict independiente, con orden, valores y tipos exactos.

#### Scenario: Configuración inválida
- **WHEN** una familia contiene nombres vacíos, claves duplicadas, valores anidados
  o floats no finitos
- **THEN** el contrato falla antes de entrenar o escribir artefactos.

### Requirement: Independencia científica por sitio
Pergamino y Melchor Romero MUST declarar sus propias specs aunque actualmente
coincidan, sin centralizar decisiones científicas ni incorporar tuning automático.

#### Scenario: Divergencia futura explícita
- **WHEN** un sitio requiera parámetros científicamente distintos
- **THEN** su plan puede versionarlos sin modificar el plan del otro sitio ni
  introducir selección automática basada en resultados.
