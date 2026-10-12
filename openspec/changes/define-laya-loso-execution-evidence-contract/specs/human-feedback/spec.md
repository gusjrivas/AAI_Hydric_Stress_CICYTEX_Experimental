## ADDED Requirements

### Requirement: Contrato ligado a identidades declaradas

El sistema MUST ligar el contrato de ejecución al digest del plan LOSO, al digest
del corpus, a una referencia de runtime, al protocolo de ejecución, al proveedor
`laya-http` y a una revisión de modelo SHA-1 lowercase completa y no nula. MUST NOT
presentar esas identidades declaradas como verificaciones de origen o suministro.

#### Scenario: Construcción consistente

- **GIVEN** un plan LOSO válido, una referencia `laya-runtime-identity-v1`, un protocolo y una revisión válida
- **WHEN** se construye `laya-loso-execution-contract-v1`
- **THEN** los digests de plan y corpus coinciden con los artefactos recibidos
- **AND** proveedor, revisión, runtime y protocolo quedan ligados al contrato.

#### Scenario: Identidad inconsistente o nula

- **GIVEN** un digest inconsistente, un proveedor distinto de `laya-http`, una revisión parcial/no canónica o un sentinel nulo
- **WHEN** se construye o reemplaza el contrato
- **THEN** la operación falla de forma cerrada.

#### Scenario: Attestations todavía no verificadas

- **GIVEN** un contrato estructuralmente válido
- **WHEN** no se verificaron runtime, origen, ejecución gold-blind ni supply chain externamente
- **THEN** `runtime_identity_verified`, `origin_verified`, `gold_blind_execution_attested` y `supply_identity_verified` son falsos.

### Requirement: Cobertura outer-test exacta

El sistema MUST aceptar exactamente una predicción por cada registro de test de cada
fold LOSO y MUST rechazar faltantes, extras, duplicados, asignaciones al fold
incorrecto y registros pertenecientes a fit o calibración.

#### Scenario: Cobertura completa

- **GIVEN** una fila por cada par de sitio retenido y ejemplo outer-test
- **WHEN** se valida el lote
- **THEN** su cobertura coincide exactamente con todos los tests del plan
- **AND** `execution_evidence_validated` es verdadero.

#### Scenario: Cobertura contaminada

- **GIVEN** una fila faltante, extra, duplicada, de otro fold o de entrenamiento
- **WHEN** se valida el lote
- **THEN** el lote completo es rechazado
- **AND** el error no expone IDs ni payload privados.

#### Scenario: Mezcla de identidades

- **GIVEN** una fila cuyo proveedor o revisión no coincide con el contrato
- **WHEN** se valida el lote
- **THEN** el lote es rechazado como evidencia de ese contrato.

### Requirement: Predicciones numéricamente cerradas

Cada predicción MUST usar las categorías en su orden contractual, MUST contener
probabilidades numéricas no booleanas, finitas, no negativas y normalizadas, y MUST
tener un argmax único que coincida con la categoría seleccionada. La confidence
opcional MUST estar en `[0, 1]` y la latencia MUST ser finita y no negativa.

#### Scenario: Predicción inequívoca

- **GIVEN** probabilidades ordenadas que suman uno y tienen un máximo único
- **WHEN** categoría, confidence y latencia satisfacen el contrato
- **THEN** la fila puede integrar el lote validado.

#### Scenario: Estado ambiguo o inválido

- **GIVEN** categorías desordenadas, `unclassified`, suma inválida, empate del máximo, booleanos, no finitos o valores fuera de rango
- **WHEN** se construye o reemplaza la fila
- **THEN** la operación falla de forma cerrada.

### Requirement: Canonicalización y commitment privado completo

El sistema MUST ordenar las filas por orden contractual de fold e ID de ejemplo,
MUST normalizar representaciones numéricas equivalentes y MUST sellar todo el
contenido canónico con un `prediction_content_sha256` privado.

#### Scenario: Orden y representación equivalentes

- **GIVEN** dos lotes equivalentes con distinto orden o con enteros/floats y cero negativo equivalentes
- **WHEN** se validan y canonicalizan
- **THEN** sus predicciones ordenadas, commitments y summaries son idénticos.

#### Scenario: Contenido privado alterado

- **GIVEN** dos lotes que difieren en cualquier campo de una predicción
- **WHEN** se calculan sus commitments privados
- **THEN** los commitments son distintos
- **AND** un objeto reemplazado con filas o digest inconsistentes es rechazado.

### Requirement: Summary público seguro

El sistema MUST producir un summary JSON canónico con identidad segura, conteo,
attestations, estados y un agregado de latencia compuesto sólo por `count`,
`minimum`, `maximum` y `mean`. MUST NOT publicar filas, IDs, payload humano,
categorías, probabilidades, hashes por fila, digest del corpus privado ni el
commitment de predicciones.

#### Scenario: Publicación sin superficie de diccionario

- **GIVEN** evidencia validada que contiene IDs y predicciones privadas
- **WHEN** se serializa el summary público o se renderiza `repr`
- **THEN** no aparecen ejemplos, grupos, comentarios, actores humanos, categorías, probabilidades ni commitments privados
- **AND** el summary contiene únicamente el agregado de latencia permitido para esos valores observacionales.

#### Scenario: Separación entre summary y commitment

- **GIVEN** dos lotes con los mismos agregados públicos pero contenido predictivo diferente
- **WHEN** se comparan sus artefactos
- **THEN** sus summaries públicos pueden ser iguales
- **AND** sus commitments privados son distintos.

### Requirement: Validez estructural sin afirmar ejecución

La evidencia validada MUST declarar únicamente que el lote satisface el contrato
estructural y MUST mantener en falso ejecución completada, suficiencia científica,
elegibilidad para shadow review y autorización productiva.

#### Scenario: Evidencia estructural válida

- **GIVEN** un lote completo, consistente y canónico
- **WHEN** se valida contra el contrato
- **THEN** `execution_evidence_validated` es verdadero
- **AND** `execution_completed` es falso
- **AND** `scientifically_sufficient` es falso
- **AND** `eligible_for_shadow_review` es falso
- **AND** `production_enablement_authorized` es falso.

#### Scenario: Sin executor ni verificación de runtime

- **GIVEN** evidencia estructural validada
- **WHEN** todavía no existen runtime verificado, lock/SBOM, executor real, attestación gold-blind y métricas preregistradas
- **THEN** no se afirma que Laya haya sido ejecutado
- **AND** no se habilita readiness, shadow review ni producción.

### Requirement: Aislamiento de flujos existentes

El contrato de ejecución MUST NOT ser importado ni invocado por adapters, backend,
gate offline, forecast, ingesta, predictive modeling, experiment runners o scripts.

#### Scenario: Corridas preexistentes sin evidencia LOSO

- **GIVEN** ningún executor Laya conectado
- **WHEN** se ejecutan CICYTEX, Pergamino, Melchor Romero y laboratorio mock
- **THEN** conservan sus contratos previos
- **AND** el contrato de evidencia LOSO no se invoca.
