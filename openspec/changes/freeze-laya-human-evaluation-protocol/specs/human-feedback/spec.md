## ADDED Requirements

### Requirement: Preregistro inmutable ligado al corpus y al plan

El sistema MUST aceptar únicamente un manifest cerrado cuyos digests coincidan
con un `EvaluationCorpus` y un `LosoEvaluationPlan` ya validados. El plan MUST
pertenecer al mismo corpus y conservar los tres sitios requeridos.

#### Scenario: binding íntegro

- **GIVEN** un corpus, su plan LOSO y un manifest con identidades coincidentes
- **WHEN** se verifica el preregistro
- **THEN** se obtiene una autoridad estructural inmutable y determinística

#### Scenario: identidad divergente

- **GIVEN** cualquier digest, corpus o plan divergente
- **WHEN** se verifica el preregistro
- **THEN** el sistema falla cerrado sin revelar payload privado

### Requirement: Artefactos externos verificados por bytes

El sistema MUST requerir exactamente los cinco roles contratados y comprobar
`size_bytes` y SHA-256 contra el contenido recibido, el manifest y las referencias
del corpus.

#### Scenario: artefacto alterado

- **GIVEN** contenido, tamaño, rol o digest no coincidente
- **WHEN** se verifica el preregistro
- **THEN** el sistema lo rechaza sin tratar attestations como evidencia verificada

### Requirement: Cohorte y análisis fijados antes de resultados

El sistema MUST validar pisos preregistrados de N, sitio, grupo, celda y alpha
nominal pre-adjudicación, y MUST fijar macro-F1, baseline legacy en idénticos
folds, delta pareado mínimo 0,05, bootstrap percentil estratificado con unidad
`group_within_site` y 10.000/95 %/semilla, Holm/0,05 y los umbrales legacy
vigentes. El verificador NO DEBE elegir N ni afirmar suficiencia de potencia.

#### Scenario: cohorte insuficiente

- **GIVEN** una cohorte que no satisface cualquiera de los pisos congelados
- **WHEN** se verifica el preregistro
- **THEN** falla cerrado y el criterio no se relaja

#### Scenario: corpus privado no provisto

- **GIVEN** que sólo existen fixtures sintéticos versionados
- **WHEN** se informa el estado científico real
- **THEN** permanece `BLOCKED_CORPUS_NOT_PROVIDED`

### Requirement: Summary público con privacidad y sin habilitación

El sistema MUST producir bytes canónicos y un digest reproducible sin texto ni
identificadores privados. Una verificación exitosa MUST NOT afirmar ejecución,
suficiencia científica, elegibilidad shadow ni habilitación productiva.

#### Scenario: Publicación de evidencia estructural

- **GIVEN** un preregistro verificado con corpus y artefactos privados
- **WHEN** se genera su summary público
- **THEN** los bytes son canónicos y no contienen payload ni identificadores privados
- **AND** todos los claims de ejecución, suficiencia y habilitación permanecen falsos
