## ADDED Requirements

### Requirement: Contrato fail-closed para un corpus humano candidato

El sistema MUST cargar el corpus humano privado únicamente cuando manifest y
registros satisfacen exactamente el schema versionado, y MUST tratar el resultado
como un candidato estructural que no acredita suficiencia científica ni producción.

#### Scenario: Corpus privado válido

- **GIVEN** un manifest `laya-human-evaluation-corpus-v1` y registros privados coherentes
- **WHEN** se carga el corpus desde rutas explícitas externas al repositorio
- **THEN** `structurally_valid` es verdadero
- **AND** `scientifically_sufficient` es falso
- **AND** `production_enablement_authorized` es falso.

#### Scenario: Schema ambiguo o no canónico

- **GIVEN** un manifest o registro con campos faltantes, adicionales o duplicados, valores no finitos o strings no canónicos
- **WHEN** se intenta cargar el corpus
- **THEN** la carga falla de forma cerrada
- **AND** no se construye un corpus estructuralmente válido.

#### Scenario: Construcción directa inconsistente

- **GIVEN** un objeto de corpus construido o reemplazado con metadata, conteo, cohorte o digest inconsistente
- **WHEN** se valida su construcción
- **THEN** la construcción falla
- **AND** el caller no puede autoafirmar validez estructural.

### Requirement: Procedencia declarada y ligada al contenido privado

El manifest MUST identificar la rúbrica y los protocolos de muestreo, anotación,
adjudicación y desidentificación mediante IDs y digests SHA-256, MUST declarar
custodia, congelamiento UTC, origen humano de campo y revisión de privacidad, y MUST
ligarse criptográficamente a los registros cargados.

#### Scenario: Digest de registros alterado

- **GIVEN** un manifest cuyo `records_sha256` no coincide con la serialización canónica de los registros privados
- **WHEN** se carga el corpus
- **THEN** la carga falla por discrepancia de digest.

#### Scenario: Procedencia o privacidad incompleta

- **GIVEN** un manifest sin un ID o SHA-256 contractual, con timestamp UTC inválido, con origen distinto de `human_field`, o sin attestations verdaderas de desidentificación y revisión de privacidad
- **WHEN** se carga el corpus
- **THEN** la carga falla de forma cerrada.

#### Scenario: Attestations sintácticamente válidas

- **GIVEN** IDs, digests y flags de procedencia con formato contractual
- **WHEN** el loader acepta el manifest
- **THEN** el resultado registra esas declaraciones
- **AND** no afirma haber verificado automáticamente los documentos externos, la cadena de custodia ni la veracidad de las attestations.

### Requirement: Cohorte exacta y grupos aislados por sitio

El corpus MUST cubrir exactamente `cicytex`, `melchor-romero` y `pergamino`, MUST
rechazar cualquier sitio adicional o ausente y MUST impedir que un `group_id` cruce
límites de sitio.

#### Scenario: Cobertura exacta de sitios

- **GIVEN** registros que contienen al menos un ejemplo de cada sitio requerido y ningún otro sitio
- **WHEN** se valida la cohorte
- **THEN** la cobertura estructural de sitios es válida.

#### Scenario: Grupo compartido entre sitios

- **GIVEN** dos registros con el mismo `group_id` y distintos `site_id`
- **WHEN** se valida la cohorte
- **THEN** el corpus es rechazado por contaminación cross-site.

### Requirement: Adjudicación independiente y trazable

Cada ejemplo MUST tener al menos dos anotadores distintos. Ante consenso, el gold
label MUST coincidir con ese consenso y no MUST existir adjudicación. Ante desacuerdo,
MUST existir una adjudicación con `decision_ref` realizada por una tercera persona
distinta de los anotadores, y el gold label MUST coincidir con su decisión.

#### Scenario: Consenso sin adjudicación

- **GIVEN** dos o más anotadores distintos que asignan la misma categoría
- **WHEN** se valida el registro
- **THEN** el gold label coincide con el consenso
- **AND** una adjudicación presente hace fallar la validación.

#### Scenario: Desacuerdo adjudicado por un tercero

- **GIVEN** anotadores distintos que discrepan y una adjudicación con referencia de decisión
- **WHEN** el adjudicador no participó como anotador y su categoría coincide con el gold label
- **THEN** el registro satisface el contrato de adjudicación.

#### Scenario: Desacuerdo no independiente

- **GIVEN** anotadores que discrepan
- **WHEN** falta la adjudicación, el adjudicador es uno de los anotadores o su categoría no coincide con el gold label
- **THEN** el corpus es rechazado.

### Requirement: Summary público determinista y sin PII

El sistema MUST producir un summary JSON canónico que preserve metadata y digests
de procedencia, incluya `records_sha256` y los flags de estado, y MUST excluir el
payload de registros y toda traza humana privada.

#### Scenario: Publicación segura del summary

- **GIVEN** un corpus privado validado con comentarios, ejemplos, grupos, anotadores y adjudicaciones
- **WHEN** se serializa el summary público
- **THEN** no contiene registros, comentarios, `example_id`, `group_id`, `annotator_id`, `adjudicator_id` ni `decision_ref`
- **AND** contiene `records_sha256`, metadata de protocolo y flags de estado.

#### Scenario: Identidad estable y ligada al corpus

- **GIVEN** dos cargas equivalentes con diferente orden de registros o anotaciones
- **WHEN** se calcula su digest público
- **THEN** los digests son iguales
- **AND** un cambio material en los registros exige otro `records_sha256` y produce otra identidad pública.

### Requirement: Aislamiento total del gate y de la operación

El contrato de corpus candidato MUST NOT ser importado ni invocado por el gate
offline, backend, forecast, ingesta, entrenamiento, recalibración o runners
experimentales.

#### Scenario: Ejecución de flujos existentes

- **GIVEN** ningún corpus humano configurado
- **WHEN** se ejecutan el gate offline y las corridas existentes de CICYTEX, Pergamino, Melchor Romero y laboratorio mock
- **THEN** conservan sus contratos previos
- **AND** el loader del corpus humano no se invoca.

#### Scenario: Protocolo científico aún diferido

- **GIVEN** un corpus que cumple todo el contrato estructural
- **WHEN** todavía no existen N y balance preregistrados, LOSO, calibración independiente, baseline pareado e intervalos bootstrap
- **THEN** `scientifically_sufficient` permanece falso
- **AND** no se emite elegibilidad para shadow review
- **AND** la producción permanece desautorizada.
