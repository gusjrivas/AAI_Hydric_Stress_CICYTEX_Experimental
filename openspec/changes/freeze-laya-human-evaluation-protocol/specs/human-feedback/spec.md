## ADDED Requirements

### Requirement: Preregistro inmutable ligado al corpus y al plan

El sistema MUST aceptar únicamente un manifest cerrado cuyos digests coincidan
con un `EvaluationCorpus` y un `LosoEvaluationPlan` ya validados. El plan MUST
pertenecer al mismo corpus, conservar los tres sitios requeridos y coincidir en
su `assignment_sha256` exacto.

#### Scenario: binding íntegro

- **GIVEN** un corpus, su plan LOSO y un manifest con identidades coincidentes
- **WHEN** se verifica el preregistro
- **THEN** se obtiene una autoridad estructural inmutable y determinística

#### Scenario: identidad divergente

- **GIVEN** cualquier digest, corpus o plan divergente
- **WHEN** se verifica el preregistro
- **THEN** el sistema falla cerrado sin revelar payload privado

### Requirement: Artefactos externos verificados por bytes

El sistema MUST requerir exactamente los seis roles contratados, incluido
`baseline_protocol`, y comprobar
`size_bytes` y SHA-256 contra el contenido recibido, el manifest y las referencias
del corpus o del protocolo de análisis.

#### Scenario: artefacto alterado

- **GIVEN** contenido, tamaño, rol o digest no coincidente
- **WHEN** se verifica el preregistro
- **THEN** el sistema lo rechaza sin tratar attestations como evidencia verificada

### Requirement: Cohorte fijada antes de resultados

El sistema MUST validar pisos preregistrados de N, sitio, grupo, celda y alpha
nominal pre-adjudicación. El verificador MUST NOT elegir N ni afirmar suficiencia
de potencia.

#### Scenario: cohorte insuficiente

- **GIVEN** una cohorte que no satisface cualquiera de los pisos congelados
- **WHEN** se verifica el preregistro
- **THEN** falla cerrado y el criterio no se relaja

#### Scenario: corpus privado no provisto

- **GIVEN** que sólo existen fixtures sintéticos versionados
- **WHEN** se informa el estado científico real
- **THEN** permanece `BLOCKED_CORPUS_NOT_PROVIDED`

### Requirement: Análisis fijado antes de resultados

El sistema MUST fijar las labels y zero-division de macro-F1, los estimandos
global y por sitio, el baseline y sus mismos folds, los márgenes global/por sitio
y el bootstrap estratificado pareado sobre los mismos grupos/sitio. Estos criterios
y los umbrales legacy MUST quedar congelados antes de aceptar predicciones.

#### Scenario: criterio estadístico alterado

- **GIVEN** un manifest con cualquier criterio diferente del preregistro cerrado
- **WHEN** se intenta verificar el protocolo
- **THEN** el sistema falla cerrado antes de ejecutar Laya o el baseline

### Requirement: Multiplicidad ejecutable y sin decisión post hoc

El sistema MUST fijar la fórmula de probabilidad de cola, el orden y desempate
Holm, los umbrales step-down, la regla de parada y la condición final de PASS.

#### Scenario: Step-down Holm preregistrado

- **GIVEN** réplicas bootstrap pareadas por los mismos grupos y sitios
- **WHEN** se calcula `p_h=(1+count(delta_h_bootstrap<=margin_h))/(B+1)`
- **THEN** Holm ordena por `(p_h, índice preregistrado)`
- **AND** compara el rango `r` con `alpha/(m-r+1)`
- **AND** se detiene en el primer no rechazo
- **AND** el PASS exige rechazar las cuatro hipótesis

#### Scenario: intervalo descriptivo no habilita el gate

- **GIVEN** intervalos bootstrap del 95 % y probabilidades de cola calculadas
  sobre las mismas réplicas pareadas
- **WHEN** se decide el resultado estadístico
- **THEN** sólo la regla Holm preregistrada gobierna el PASS
- **AND** las cuatro hipótesis deben ser rechazadas

### Requirement: Summary público con privacidad y sin habilitación

El sistema MUST producir bytes canónicos y un digest reproducible sin texto ni
identificadores privados. Una verificación exitosa MUST NOT afirmar ejecución,
suficiencia científica, elegibilidad shadow ni habilitación productiva.

#### Scenario: Publicación de evidencia estructural

- **GIVEN** un preregistro verificado con corpus y artefactos privados
- **WHEN** se genera su summary público
- **THEN** los bytes son canónicos y no contienen payload ni identificadores privados
- **AND** todos los claims de ejecución, suficiencia y habilitación permanecen falsos
